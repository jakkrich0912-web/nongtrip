"""ตัวค้นหลัก: รวมสถานที่ที่ตรวจแล้ว + OpenStreetMap เรียงใกล้ไปไกล รัศมีไม่เกิน 30 กม."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .cache import TTLCache
from .geo import directions_url, haversine_km, in_thailand, place_url
from .fetch import HttpClient, UpstreamError, UpstreamTooBig
from .models import Candidate, LodgingCandidate, Place, SearchResult
from .osm import LODGING_TYPES, NominatimClient, OverpassClient
from .snapshot import DEFAULT_DIR, Snapshot
from .provinces import PROVINCES, province_in_address, region_of
from .verified import centroid, load_verified

MAX_RADIUS_KM = 30.0          # CONTRACT ข้อ 5 บังคับในโค้ด
PIN_LODGING_RADIUS_KM = (5.0, 10.0)  # ค้นที่พักรอบหมุด: เริ่ม 5 แล้วขยายเป็น 10
GRID_DEG = 0.01               # ปัดจุดค้นให้แชร์แคชกันได้ (~1.1 กม.)
GRID_MARGIN_KM = 1.0          # ขยายรัศมีดึงข้อมูลชดเชยการปัดจุด
FALLBACK_FETCH_KM = 15.0      # ถ้า Overpass บอกว่าคำขอใหญ่เกิน ลดเหลือเท่านี้
DUP_NEAR_KM = 0.3
KINDS_ALL = ("attraction", "cafe")
MAX_LODGINGS = 20             # ที่พักรอบหมุดที่แสดงสูงสุด (ใกล้หมุดที่สุดก่อน) กันหน้าเว็บยาวเป็นพันรายการ


def _filter_lodgings(items: list[dict], province: str | None, area: str | None, subtype: str | None) -> list[dict]:
    """กรองรายการที่พัก (dict จาก LodgingCandidate) ตามจังหวัด ย่าน ประเภท รายการที่ไม่รู้จังหวัดจะถูกตัดออก
    เมื่อขอกรองจังหวัด เพราะแยกไม่ได้ว่าใช่แห่งที่ต้องการหรือไม่ (ไม่เดาให้)"""
    out = []
    a = _norm(area) if area else ""
    for it in items:
        if province and (it.get("province") or province_in_address(it.get("address"))) != province:
            continue
        if subtype and it.get("subtype") != subtype:
            continue
        if a and a not in _norm((it.get("name") or "") + (it.get("address") or "")):
            continue
        out.append(it)
    return out


class SearchError(ValueError):
    """คำขอไม่ถูกต้อง (API แปลงเป็น HTTP 400)"""


class RadiusError(SearchError):
    pass


class OutOfThailandError(SearchError):
    pass


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def _similar(a: Candidate, b: Candidate) -> bool:
    names_a = {_norm(n) for n in (a.name_th, a.name_en) if n}
    names_b = {_norm(n) for n in (b.name_th, b.name_en) if n}
    for x in names_a:
        for y in names_b:
            if x == y or (min(len(x), len(y)) >= 4 and (x in y or y in x)):
                return True
    return False


def dedupe(cands: list[Candidate]) -> list[Candidate]:
    """ตัดสถานที่ซ้ำ: ชื่อคล้ายและอยู่ใกล้กัน; ตัวที่ตรวจแล้ว (verified) ชนะ OSM
    ใช้ตารางกริดช่องละ ~0.4 กม. ตรวจเฉพาะช่องข้างเคียง (เร็วพอสำหรับข้อมูลหลายพันแห่ง)"""
    cell = 0.004
    ordered = sorted(cands, key=lambda c: 0 if c.source == "verified" else 1)
    grid: dict[tuple[int, int], list[Candidate]] = {}
    kept: list[Candidate] = []
    for c in ordered:
        gx, gy = int(c.lat // cell), int(c.lon // cell)
        dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((gx + dx, gy + dy), ()):
                    if k.kind != c.kind:
                        continue
                    d = haversine_km(c.lat, c.lon, k.lat, k.lon)
                    if d < 0.03 or (d < DUP_NEAR_KM and _similar(c, k)):
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if not dup:
            kept.append(c)
            grid.setdefault((gx, gy), []).append(c)
    return kept


def _area_rank(r: dict) -> int:
    """จัดอันดับผลค้นชื่อจังหวัด: ตัวเมือง/เมือง ก่อน เทศบาลนคร/เมือง ถัดมา ที่เหลือท้ายสุด (สถานีรถไฟ ฯลฯ ไม่เอา)"""
    cat, typ = r.get("category"), r.get("type")
    if cat == "place" and typ in ("city", "town"):
        return 0
    first = (r.get("display_name") or "").split(",")[0]
    if cat == "boundary" and first.startswith(("เทศบาลนคร", "เทศบาลเมือง")):
        return 1
    if cat == "boundary":
        return 2
    return 3


@dataclass
class _Area:
    candidates: list[Candidate]
    covered_km: float            # รัศมีที่ OSM ครอบคลุมจริงรอบจุดค้น
    osm_ok: bool
    notices: list[str] = field(default_factory=list)
    center: tuple[float, float] | None = None   # จุดที่ใช้ดึงข้อมูล (ใช้คิดว่าครอบคลุมรอบที่พักอื่นได้แค่ไหน)
    mode: str = "live"                          # live = ออนไลน์ | snapshot = สแนปช็อตที่ดึงไว้


class PlacesService:
    def __init__(self, http: HttpClient | None = None, cache: TTLCache | None = None,
                 verified: list[Candidate] | None = None, osm_live: bool | None = None,
                 snapshot: Snapshot | None = None):
        self.http = http or HttpClient()
        self.cache = cache if cache is not None else TTLCache(os.environ.get("PLACES_CACHE_DIR") or None)
        self.verified = verified if verified is not None else load_verified()
        self.osm_live = (os.environ.get("OSM_LIVE", "1") != "0") if osm_live is None else osm_live
        self.snapshot = snapshot if snapshot is not None else Snapshot(os.environ.get("OSM_SNAPSHOT_DIR") or DEFAULT_DIR)
        self.overpass = OverpassClient(self.http)
        self.nominatim = NominatimClient(self.http)

    # ---------- ตรวจคำขอ ----------
    @staticmethod
    def _check(lat: float, lon: float, radius_km: float, max_radius: float = MAX_RADIUS_KM) -> None:
        if not (0 < radius_km <= max_radius):
            raise RadiusError(f"รัศมีต้องมากกว่า 0 และไม่เกิน {max_radius:g} กม.")
        if not in_thailand(lat, lon):
            raise OutOfThailandError("พิกัดอยู่นอกประเทศไทย")

    @staticmethod
    def _kinds(kinds) -> tuple[str, ...]:
        ks = tuple(k for k in (kinds or KINDS_ALL) if k in KINDS_ALL)
        if not ks:
            raise SearchError("kinds ต้องเป็น attraction และ/หรือ cafe")
        return ks

    # ---------- จังหวัด ----------
    def province_center(self, province: str) -> dict:
        """จุดกลางจังหวัดสำหรับเปิดแผนที่ (หน้าแรกเลือกจังหวัด) ลอง OSM ก่อน ไม่ได้ใช้ค่าเฉลี่ยพิกัดสถานที่ที่ตรวจแล้ว"""
        name = (province or "").strip()
        if name not in PROVINCES:
            raise SearchError("ไม่รู้จักชื่อจังหวัดนี้ (ต้องเป็นหนึ่งใน 77 จังหวัด)")
        base = {"province": name, "region": region_of(name)}
        key = f"province:{name}"
        hit = self.cache.get(key)
        if hit:
            return {**base, **hit}
        if self.osm_live:
            try:
                # ค้นด้วยชื่อล้วน ได้ตัวเมือง (ทดสอบกับ OSM จริง 9 จังหวัดภาคเหนือแล้ว) ส่วน "จังหวัด<ชื่อ>" ได้จุดกลางพื้นที่ซึ่งมักอยู่ในป่า
                rows = self.nominatim.search_area(name)
                rows.sort(key=_area_rank)
                for r in rows:
                    if _area_rank(r) > 2:
                        continue
                    lat, lon = float(r["lat"]), float(r["lon"])
                    if in_thailand(lat, lon):
                        res = {"lat": lat, "lon": lon, "source": "osm"}
                        self.cache.set(key, res)
                        return {**base, **res}
            except (UpstreamError, KeyError, ValueError):
                pass
        c = centroid(name, self.verified)
        if c:
            return {**base, "lat": c[0], "lon": c[1], "source": "verified_centroid",
                    "notice": "ใช้ค่าเฉลี่ยพิกัดสถานที่ที่ตรวจแล้ว เพราะหาจุดกลางจังหวัดจาก OpenStreetMap ไม่ได้"}
        return {**base, "lat": None, "lon": None, "source": None,
                "notice": "ยังหาจุดกลางของจังหวัดนี้ไม่ได้ ให้ค้นด้วยชื่อที่พักหรือปักหมุดแทน"}

    # ---------- ค้นที่พักจากชื่อ ----------
    def find_lodging(self, query: str, province: str | None = None, area: str | None = None,
                     subtype: str | None = None) -> dict:
        """ค้นที่พักด้วยชื่อ ถ้าชื่อซ้ำหลายแห่งให้ผู้ใช้เลือก ตัวกรองช่วยแยกที่พักชื่อซ้ำ:
        province (หนึ่งใน 77 จังหวัด), area (ย่าน/อำเภอ/ถนน ข้อความที่ปรากฏในที่อยู่), subtype (ประเภทที่พัก OSM)"""
        q = (query or "").strip()
        if len(q) < 2:
            raise SearchError("ชื่อที่พักสั้นเกินไป")
        province = (province or "").strip() or None
        area = (area or "").strip() or None
        subtype = (subtype or "").strip() or None
        if province and province not in PROVINCES:
            raise SearchError("ไม่รู้จักชื่อจังหวัดนี้ (ต้องเป็นหนึ่งใน 77 จังหวัด)")
        if subtype and subtype not in LODGING_TYPES:
            raise SearchError("ประเภทที่พักต้องเป็นหนึ่งใน " + ", ".join(LODGING_TYPES))
        if area and len(area) > 100:
            raise SearchError("ชื่อย่านยาวเกินไป")
        flt = {"province": province, "area": area, "subtype": subtype}
        if not self.osm_live:
            return self._lodging_offline(q, "ปิดการค้นหาจาก OpenStreetMap อยู่", flt)
        # ใส่จังหวัด/ย่านต่อท้ายคำค้นด้วย เพื่อให้ Nominatim ส่งแห่งที่อยู่ตรงนั้นมาแทนแห่งอื่นที่ชื่อเหมือนกัน
        text = " ".join(x for x in (q, area, province) if x)
        limit = 20 if (province or area) else 8
        key = f"nominatim:{text.lower()}" + (f":{limit}" if limit != 8 else "")
        cached = self.cache.get(key)
        try:
            if cached is None:
                items = [c.to_dict() for c in self.nominatim.search_lodging(text, limit=limit)]
                self.cache.set(key, items)
            else:
                items = cached
        except UpstreamError:
            return self._lodging_offline(q, "ค้นชื่อที่พักออนไลน์ไม่ได้ในตอนนี้", flt)
        total = len(items)
        items = _filter_lodgings(items, **flt)
        notices = []
        if len(items) > 1:
            notices.append("พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง")
        if not items:
            notices.append("ไม่พบที่พักที่ตรงตัวกรอง ลองเอาตัวกรองออกบางข้อ หรือปักหมุดบนแผนที่" if total
                           else "ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น หรือปักหมุดบนแผนที่")
        return {"items": items, "osm_available": True, "osm_mode": "live", "notices": notices}

    def _lodging_offline(self, q: str, reason: str, flt: dict | None = None) -> dict:
        flt = flt or {}
        if self.snapshot.available():
            items = [c.to_dict() for c in self.snapshot.find_lodging(q, province=flt.get("province"),
                                                                    subtype=flt.get("subtype"))]
            notices = []        # v0.14: ไม่แจ้งว่าใช้ข้อมูลที่บันทึกไว้ (ผู้ใช้ดูได้จาก osm_mode ถ้าต้องการ)
            if flt.get("area"):
                notices.append("ข้อมูลที่บันทึกไว้ยังกรองตามย่านไม่ได้ ผลที่เห็นไม่ได้ถูกกรองด้วยย่าน")
            if len(items) > 1:
                notices.append("พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง")
            if not items:
                notices.append("ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น หรือปักหมุดบนแผนที่")
            return {"items": items, "osm_available": True, "osm_mode": "snapshot", "notices": notices}
        return {"items": [], "osm_available": False, "osm_mode": "none",
                "notices": [f"{reason} ให้ปักหมุดบนแผนที่แทน"]}

    # ---------- ดึงสถานที่รอบจุด (ครั้งเดียวต่อพื้นที่) ----------
    def _fetch_osm(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...]) -> _Area:
        glat, glon = round(lat / GRID_DEG) * GRID_DEG, round(lon / GRID_DEG) * GRID_DEG
        notices: list[str] = []
        if not self.osm_live:
            return self._offline_area(lat, lon, radius_km, kinds, "ปิดการค้นหาจาก OpenStreetMap อยู่")
        fetch_km = radius_km + GRID_MARGIN_KM
        attempts = [fetch_km] + ([FALLBACK_FETCH_KM] if FALLBACK_FETCH_KM < fetch_km else [])
        for attempt in attempts:
            key = f"overpass:{glat:.2f}:{glon:.2f}:{attempt:g}:{','.join(kinds)}"
            data = self.cache.get(key)
            try:
                if data is None:
                    cands = self.overpass.fetch(glat, glon, attempt, kinds)
                    self.cache.set(key, [c.to_cache() for c in cands])
                else:
                    cands = [Candidate.from_cache(d) for d in data]
            except UpstreamTooBig:
                continue
            except UpstreamError:
                return self._offline_area(lat, lon, radius_km, kinds, "เชื่อมต่อ OpenStreetMap ไม่ได้ในตอนนี้")
            if attempt < fetch_km:
                notices.append(f"พื้นที่หนาแน่นมาก ข้อมูลจาก OpenStreetMap จึงครอบคลุมแค่ {attempt - GRID_MARGIN_KM:g} กม.")
            return _Area(cands, attempt - GRID_MARGIN_KM, True, notices, (lat, lon))
        return self._offline_area(lat, lon, radius_km, kinds, "ดึงข้อมูลจาก OpenStreetMap ไม่สำเร็จ")

    def _offline_area(self, lat, lon, radius_km, kinds, reason: str) -> _Area:
        """ออนไลน์ไม่ได้: ใช้สแนปช็อต OSM ที่ดึงไว้ล่วงหน้า (ถ้ามี) ไม่มีก็เหลือเฉพาะข้อมูลที่ตรวจแล้ว"""
        if self.snapshot.available():
            cands = self.snapshot.around(lat, lon, radius_km, kinds)
            return _Area(cands, radius_km, True, [], (lat, lon), "snapshot")   # v0.14: ไม่มีข้อความเตือน
        return _Area([], radius_km, False, [f"{reason} แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว"])

    def _area(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...]) -> _Area:
        area = self._fetch_osm(lat, lon, radius_km, kinds)
        return area

    # ---------- จัดอันดับรอบจุดหนึ่ง ----------
    def _rank(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...], area: _Area,
              pool: list[Candidate] | None = None) -> tuple[list[Place], float]:
        eff = radius_km
        if area.osm_ok:
            shift = haversine_km(area.center[0], area.center[1], lat, lon) if area.center else 0.0
            eff = round(max(0.0, min(radius_km, area.covered_km - shift)), 2)
        pre = pool is not None          # pool ที่ตัดซ้ำมาแล้วทั้งพื้นที่ (โหมดที่พักรอบหมุด)
        if pool is None:
            pool = [c for c in self.verified if c.kind in kinds] + [c for c in area.candidates if c.kind in kinds]
        scored = []
        for c in pool:
            d = haversine_km(lat, lon, c.lat, c.lon)
            if d <= eff:
                scored.append((d, c))
        scored.sort(key=lambda t: (t[0], t[1].name_th))
        # ตัดซ้ำหลังคัดรัศมีแล้ว (เร็วกว่าตัดทั้งพื้นที่)
        uniq = [c for _, c in scored] if pre else dedupe([c for _, c in scored])
        keep = {c.id for c in uniq}
        dist = {c.id: d for d, c in scored}
        places = []
        for d, c in scored:
            if c.id not in keep:
                continue
            places.append(Place(
                id=c.id, name_th=c.name_th, name_en=c.name_en, kind=c.kind, subtype=c.subtype,
                lat=c.lat, lon=c.lon, distance_km=round(dist[c.id], 2), source=c.source,
                province=c.province, source_url=c.source_url,
                maps_url=place_url(c.name_th, c.lat, c.lon),
                directions_url=directions_url((lat, lon), (c.lat, c.lon)),
            ))
        return places, eff

    # ---------- ค้นสถานที่รอบจุด ----------
    def nearby(self, lat: float, lon: float, radius_km: float = MAX_RADIUS_KM, kinds=None,
               limit: int | None = None, offset: int = 0) -> SearchResult:
        self._check(lat, lon, radius_km)
        ks = self._kinds(kinds)
        if offset < 0 or (limit is not None and limit < 1):
            raise SearchError("limit/offset ไม่ถูกต้อง")
        area = self._area(lat, lon, radius_km, ks)
        places, eff = self._rank(lat, lon, radius_km, ks, area)
        notices = list(area.notices)
        if eff < radius_km:
            notices.append(f"แสดงผลในรัศมี {eff:g} กม. เท่านั้น")
        page = places[offset: (offset + limit) if limit else None]
        return SearchResult(
            center={"lat": lat, "lon": lon}, radius_km=eff, items=page, total=len(places),
            offset=offset, limit=limit,
            counts={k: sum(1 for p in places if p.kind == k) for k in ks},
            sources={s: sum(1 for p in places if p.source == s) for s in ("verified", "osm")},
            osm_available=area.osm_ok, osm_mode=(area.mode if area.osm_ok else "none"), notices=notices,
            data_as_of=(self.snapshot.date_of(p.province for p in places if p.source == "osm")
                        if area.osm_ok and area.mode == "snapshot" else None),
        )

    # ---------- ค้นที่พักรอบหมุด + สถานที่เด่นของแต่ละที่พัก ----------
    def lodgings_near(self, lat: float, lon: float, top_n: int = 3, radius_km: float | None = None,
                      max_lodgings: int = MAX_LODGINGS) -> dict:
        self._check(lat, lon, PIN_LODGING_RADIUS_KM[-1], PIN_LODGING_RADIUS_KM[-1])
        radii = (radius_km,) if radius_km else PIN_LODGING_RADIUS_KM
        for r in radii:
            if not (0 < r <= PIN_LODGING_RADIUS_KM[-1]):
                raise RadiusError("รัศมีค้นที่พักรอบหมุดต้องไม่เกิน 10 กม.")
        notices: list[str] = []
        lodgings: list[Candidate] = []
        used = radii[0]
        for r in radii:
            area = self._fetch_osm(lat, lon, r, ("lodging",))
            if not area.osm_ok:
                return {"items": [], "osm_available": False, "osm_mode": "none", "radius_km": r, "notices": area.notices}
            used = r
            lodgings = [c for c in area.candidates
                        if c.kind == "lodging" and haversine_km(lat, lon, c.lat, c.lon) <= r]
            if lodgings:
                break
            if r != radii[-1]:
                notices.append(f"ไม่พบที่พักในรัศมี {r:g} กม. จึงขยายเป็น {radii[radii.index(r) + 1]:g} กม.")
        if not lodgings:
            notices.append(f"ไม่พบที่พักในรัศมี {used:g} กม. จากหมุดนี้")
            return {"items": [], "osm_available": True, "osm_mode": area.mode, "radius_km": used, "notices": notices}
        lodgings = dedupe(lodgings)
        lodgings.sort(key=lambda c: haversine_km(lat, lon, c.lat, c.lon))

        # ดึงสถานที่ครั้งเดียวทั้งพื้นที่ แล้วคำนวณระยะของแต่ละที่พักในเครื่อง
        lodgings_total = len(lodgings)
        if lodgings_total > max_lodgings:
            lodgings = lodgings[:max_lodgings]
            notices.append(f"พบที่พัก {lodgings_total} แห่ง แสดง {max_lodgings} แห่งที่ใกล้หมุดที่สุด")
        poi_area = self._area(lat, lon, MAX_RADIUS_KM + used, KINDS_ALL)
        notices += poi_area.notices
        # ตัดซ้ำทั้งพื้นที่ครั้งเดียว แล้วคิดระยะของแต่ละที่พักจากชุดเดียวกัน
        pool = dedupe([v for v in self.verified if v.kind in KINDS_ALL] + [c for c in poi_area.candidates if c.kind in KINDS_ALL])
        items = []
        for lod in lodgings:
            places, eff = self._rank(lod.lat, lod.lon, MAX_RADIUS_KM, KINDS_ALL, poi_area, pool)
            items.append({
                "id": lod.id, "name": lod.name_th, "subtype": lod.subtype,
                "lat": lod.lat, "lon": lod.lon,
                "distance_from_pin_km": round(haversine_km(lat, lon, lod.lat, lod.lon), 2),
                "maps_url": place_url(lod.name_th, lod.lat, lod.lon),
                "places_radius_km": eff,
                "places_total": len(places),
                "counts": {k: sum(1 for p in places if p.kind == k) for k in KINDS_ALL},
                "nearest": [p.to_dict() for p in places[:top_n]],
                "has_more": len(places) > top_n,
            })
        return {"items": items, "lodgings_total": lodgings_total, "osm_available": poi_area.osm_ok, "osm_mode": (poi_area.mode if poi_area.osm_ok else "none"), "radius_km": used,
                "notices": notices, "attribution": "© OpenStreetMap contributors (ODbL)"}
