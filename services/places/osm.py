"""ตัวเรียก OpenStreetMap: Overpass (สถานที่รอบจุด) และ Nominatim (หาที่พักจากชื่อ)
ข้อมูลที่ได้มีแค่ ชื่อ ประเภท พิกัด เท่านั้น ไม่มีเวลาเปิด ราคา หรือรีวิว"""
from __future__ import annotations

from .fetch import HttpClient, UpstreamError, UpstreamTooBig
from .models import Candidate, LodgingCandidate
from .provinces import province_in_address

# เซิร์ฟเวอร์สาธารณะหลายตัว ตัวแรกที่ตอบได้ชนะ (overpass-api.de เข้าไม่ได้จากเครือข่ายผู้พัฒนาตอนทดสอบ 2026-11-01)
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

LODGING_TYPES = ("hotel", "guest_house", "hostel", "motel", "resort", "apartment", "chalet")
_TOURISM_ATTR = ("attraction", "viewpoint", "museum", "gallery", "zoo", "theme_park", "aquarium")
_HISTORIC = ("temple", "monument", "castle", "ruins", "archaeological_site", "fort", "city_gate")
_NATURAL = ("waterfall", "peak", "beach", "hot_spring", "cave_entrance")
_LEISURE = ("park", "nature_reserve")

# ตัวกรอง Overpass ต่อประเภท (ทุกตัวต้องมีชื่อ)
FILTERS = {
    "attraction": [
        f'["tourism"~"^({"|".join(_TOURISM_ATTR)})$"]',
        f'["historic"~"^({"|".join(_HISTORIC)})$"]',
        f'["natural"~"^({"|".join(_NATURAL)})$"]',
        '["waterway"="waterfall"]',
        f'["leisure"~"^({"|".join(_LEISURE)})$"]',
        '["amenity"="place_of_worship"]["wikidata"]',
    ],
    "cafe": ['["amenity"="cafe"]'],
    "lodging": [f'["tourism"~"^({"|".join(LODGING_TYPES)})$"]'],
}


def split_filters(kind: str) -> list[str]:
    """ตัวกรองแบบแยกเล็กที่สุด ใช้ตอนคำขอรวมถูกตอบว่าง (ที่พัก = แยกทีละชนิด)"""
    if kind == "lodging":
        return [f'["tourism"="{t}"]' for t in LODGING_TYPES]
    return list(FILTERS[kind])


def build_query(lat: float, lon: float, radius_m: int, kinds: tuple[str, ...], timeout: int = 40) -> str:
    parts = []
    for k in kinds:
        for f in FILTERS[k]:
            parts.append(f'nwr(around:{radius_m},{lat:.5f},{lon:.5f}){f}["name"];')
    return f"[out:json][timeout:{timeout}];(" + "".join(parts) + ");out center tags;"


def build_area_query(province: str, kinds: tuple[str, ...], timeout: int = 180, filters: list[str] | None = None) -> str:
    """ทุกแห่งในเขตจังหวัด (ใช้ตอนดึงสแนปช็อตล่วงหน้า) หาเขตจากชื่อ ไม่ใช้รหัส ISO
    filters = ระบุตัวกรองเอง (ใช้แยกคำขอเล็กๆ เมื่อคำขอรวมถูกตอบว่าง)"""
    fl = filters if filters is not None else [f for k in kinds for f in FILTERS[k]]
    parts = [f'nwr(area.a){f}["name"];' for f in fl]
    return (f'[out:json][timeout:{timeout}];'
            f'area["boundary"="administrative"]["admin_level"="4"]["name"~"^(จังหวัด)?{province}$"]->.a;'
            f'({"".join(parts)});out center tags;')


def classify(tags: dict) -> tuple[str, str] | None:
    """แปลงแท็ก OSM เป็น (kind, subtype) คืน None ถ้าไม่ใช่ประเภทที่ระบบรองรับ"""
    if tags.get("amenity") == "cafe":
        return "cafe", "cafe"
    t = tags.get("tourism")
    if t in LODGING_TYPES:
        return "lodging", t
    if t in _TOURISM_ATTR:
        return "attraction", t
    if tags.get("historic") in _HISTORIC:
        return "attraction", tags["historic"]
    if tags.get("natural") in _NATURAL:
        return "attraction", tags["natural"]
    if tags.get("waterway") == "waterfall":
        return "attraction", "waterfall"
    if tags.get("leisure") in _LEISURE:
        return "attraction", tags["leisure"]
    if tags.get("amenity") == "place_of_worship" and tags.get("wikidata"):
        return "attraction", "place_of_worship"
    return None


def parse_elements(elements: list[dict]) -> list[Candidate]:
    out, seen = [], set()
    for el in elements:
        tags = el.get("tags") or {}
        cls = classify(tags)
        name = tags.get("name:th") or tags.get("name")
        if not cls or not name:
            continue
        lat = el.get("lat") if el.get("lat") is not None else (el.get("center") or {}).get("lat")
        lon = el.get("lon") if el.get("lon") is not None else (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        ref = f"{el.get('type', 'node')}/{el.get('id')}"
        if ref in seen:
            continue
        seen.add(ref)
        out.append(Candidate(
            id=f"osm:{ref}", name_th=name.strip(), name_en=(tags.get("name:en") or None),
            kind=cls[0], subtype=cls[1], lat=float(lat), lon=float(lon), source="osm",
            source_url=f"https://www.openstreetmap.org/{ref}",
        ))
    return out


class OverpassClient:
    def __init__(self, http: HttpClient, endpoints: tuple[str, ...] = OVERPASS_ENDPOINTS):
        self.http = http
        self.endpoints = endpoints

    def fetch(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...]) -> list[Candidate]:
        return self.run(build_query(lat, lon, int(radius_km * 1000), kinds))

    def run(self, query: str) -> list[Candidate]:
        last: Exception | None = None
        for ep in self.endpoints:
            try:
                data = self.http.post_form(ep, {"data": query})
            except UpstreamTooBig:
                raise
            except UpstreamError as e:
                last = e
                continue
            remark = (data.get("remark") or "").lower() if isinstance(data, dict) else ""
            if "timed out" in remark or "out of memory" in remark:
                raise UpstreamTooBig(remark)
            if "runtime error" in remark:
                # เช่น "Dispatcher_Client::...::timeout ... too busy" เซิร์ฟเวอร์ตอบ 200 แต่ผลว่าง ห้ามถือเป็น "ไม่มีข้อมูล"
                last = UpstreamError(remark)
                continue
            if not isinstance(data, dict) or "elements" not in data:
                last = UpstreamError("รูปแบบคำตอบ Overpass ไม่ถูกต้อง")
                continue
            return parse_elements(data["elements"])
        raise UpstreamError(str(last) if last else "Overpass ใช้ไม่ได้")


class NominatimClient:
    def __init__(self, http: HttpClient):
        self.http = http

    def search_area(self, query: str, limit: int = 5) -> list[dict]:
        """ค้นชื่อพื้นที่ (เช่น จังหวัด) คืนแถวดิบ ใช้หาจุดกลางจังหวัด"""
        data = self.http.get_json(NOMINATIM_URL, {
            "q": query, "format": "jsonv2", "countrycodes": "th", "limit": limit, "accept-language": "th,en",
        })
        if not isinstance(data, list):
            raise UpstreamError("รูปแบบคำตอบ Nominatim ไม่ถูกต้อง")
        return data

    def search_lodging(self, query: str, limit: int = 8) -> list[LodgingCandidate]:
        data = self.http.get_json(NOMINATIM_URL, {
            "q": query, "format": "jsonv2", "countrycodes": "th", "limit": limit,
            "accept-language": "th,en", "addressdetails": 0,
        })
        if not isinstance(data, list):
            raise UpstreamError("รูปแบบคำตอบ Nominatim ไม่ถูกต้อง")
        out = []
        for r in data:
            try:
                lat, lon = float(r["lat"]), float(r["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            typ = r.get("type")
            out.append(LodgingCandidate(
                id=f"osm:{r.get('osm_type', 'node')}/{r.get('osm_id')}",
                name=(r.get("name") or (r.get("display_name") or "").split(",")[0]).strip(),
                address=r.get("display_name"),
                subtype=typ if r.get("category") == "tourism" else None,
                lat=lat, lon=lon, province=province_in_address(r.get("display_name")),
            ))
        # ที่พักจริง (tourism=hotel ฯลฯ) ขึ้นก่อน แล้วค่อยผลลัพธ์อื่น
        out.sort(key=lambda c: 0 if c.subtype in LODGING_TYPES else 1)
        return out
