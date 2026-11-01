"""ตัวค้นหลัก: รวมสถานที่ที่ตรวจแล้ว + OpenStreetMap เรียงใกล้ไปไกล รัศมีไม่เกิน 30 กม."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .cache import TTLCache
from .geo import directions_url, haversine_km, in_thailand, place_url
from .fetch import HttpClient, UpstreamError, UpstreamTooBig
from .models import Candidate, LodgingCandidate, Place, SearchResult
from .osm import NominatimClient, OverpassClient
from .verified import load_verified

MAX_RADIUS_KM = 30.0          # CONTRACT ข้อ 5 บังคับในโค้ด
PIN_LODGING_RADIUS_KM = (5.0, 10.0)  # ค้นที่พักรอบหมุด: เริ่ม 5 แล้วขยายเป็น 10
GRID_DEG = 0.01               # ปัดจุดค้นให้แชร์แคชกันได้ (~1.1 กม.)
GRID_MARGIN_KM = 1.0          # ขยายรัศมีดึงข้อมูลชดเชยการปัดจุด
FALLBACK_FETCH_KM = 15.0      # ถ้า Overpass บอกว่าคำขอใหญ่เกิน ลดเหลือเท่านี้
DUP_NEAR_KM = 0.3
KINDS_ALL = ("attraction", "cafe")


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
    """ตัดสถานที่ซ้ำ: ชื่อคล้ายและอยู่ใกล้กัน; ตัวที่ตรวจแล้ว (verified) ชนะ OSM"""
    ordered = sorted(cands, key=lambda c: 0 if c.source == "verified" else 1)
    kept: list[Candidate] = []
    for c in ordered:
        dup = False
        for k in kept:
            if k.kind != c.kind:
                continue
            d = haversine_km(c.lat, c.lon, k.lat, k.lon)
            if d < 0.03 or (d < DUP_NEAR_KM and _similar(c, k)):
                dup = True
                break
        if not dup:
            kept.append(c)
    return kept


@dataclass
class _Area:
    candidates: list[Candidate]
    covered_km: float            # รัศมีที่ OSM ครอบคลุมจริงรอบจุดค้น
    osm_ok: bool
    notices: list[str] = field(default_factory=list)
    center: tuple[float, float] | None = None   # จุดที่ใช้ดึงข้อมูล (ใช้คิดว่าครอบคลุมรอบที่พักอื่นได้แค่ไหน)


class PlacesService:
    def __init__(self, http: HttpClient | None = None, cache: TTLCache | None = None,
                 verified: list[Candidate] | None = None, osm_live: bool | None = None):
        self.http = http or HttpClient()
        self.cache = cache if cache is not None else TTLCache(os.environ.get("PLACES_CACHE_DIR") or None)
        self.verified = verified if verified is not None else load_verified()
        self.osm_live = (os.environ.get("OSM_LIVE", "1") != "0") if osm_live is None else osm_live
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

    # ---------- ค้นที่พักจากชื่อ ----------
    def find_lodging(self, query: str) -> dict:
        q = (query or "").strip()
        if len(q) < 2:
            raise SearchError("ชื่อที่พักสั้นเกินไป")
        if not self.osm_live:
            return {"items": [], "osm_available": False,
                    "notices": ["ปิดการค้นหาจาก OpenStreetMap อยู่ ให้ปักหมุดบนแผนที่แทน"]}
        key = f"nominatim:{q.lower()}"
        cached = self.cache.get(key)
        try:
            if cached is None:
                items = [c.to_dict() for c in self.nominatim.search_lodging(q)]
                self.cache.set(key, items)
            else:
                items = cached
        except UpstreamError:
            return {"items": [], "osm_available": False,
                    "notices": ["ค้นชื่อที่พักไม่ได้ในตอนนี้ (เชื่อมต่อ OpenStreetMap ไม่ได้) ให้ปักหมุดบนแผนที่แทน"]}
        notices = []
        if len(items) > 1:
            notices.append("พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง")
        if not items:
            notices.append("ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น หรือปักหมุดบนแผนที่")
        return {"items": items, "osm_available": True, "notices": notices}

    # ---------- ดึงสถานที่รอบจุด (ครั้งเดียวต่อพื้นที่) ----------
    def _fetch_osm(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...]) -> _Area:
        glat, glon = round(lat / GRID_DEG) * GRID_DEG, round(lon / GRID_DEG) * GRID_DEG
        notices: list[str] = []
        if not self.osm_live:
            return _Area([], radius_km, False, ["ปิดการค้นหาจาก OpenStreetMap อยู่ แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว"])
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
                return _Area([], radius_km, False,
                             ["เชื่อมต่อ OpenStreetMap ไม่ได้ในตอนนี้ แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว"])
            if attempt < fetch_km:
                notices.append(f"พื้นที่หนาแน่นมาก ข้อมูลจาก OpenStreetMap จึงครอบคลุมแค่ {attempt - GRID_MARGIN_KM:g} กม.")
            return _Area(cands, attempt - GRID_MARGIN_KM, True, notices, (lat, lon))
        return _Area([], radius_km, False, ["ดึงข้อมูลจาก OpenStreetMap ไม่สำเร็จ แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว"])

    def _area(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...]) -> _Area:
        area = self._fetch_osm(lat, lon, radius_km, kinds)
        return area

    # ---------- จัดอันดับรอบจุดหนึ่ง ----------
    def _rank(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...], area: _Area) -> tuple[list[Place], float]:
        eff = radius_km
        if area.osm_ok:
            shift = haversine_km(area.center[0], area.center[1], lat, lon) if area.center else 0.0
            eff = round(max(0.0, min(radius_km, area.covered_km - shift)), 2)
        pool = [c for c in self.verified if c.kind in kinds] + [c for c in area.candidates if c.kind in kinds]
        scored = []
        for c in pool:
            d = haversine_km(lat, lon, c.lat, c.lon)
            if d <= eff:
                scored.append((d, c))
        scored.sort(key=lambda t: (t[0], t[1].name_th))
        # ตัดซ้ำหลังคัดรัศมีแล้ว (เร็วกว่าตัดทั้งพื้นที่)
        uniq = dedupe([c for _, c in scored])
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
            osm_available=area.osm_ok, notices=notices,
        )

    # ---------- ค้นที่พักรอบหมุด + สถานที่เด่นของแต่ละที่พัก ----------
    def lodgings_near(self, lat: float, lon: float, top_n: int = 3, radius_km: float | None = None) -> dict:
        self._check(lat, lon, PIN_LODGING_RADIUS_KM[-1], PIN_LODGING_RADIUS_KM[-1])
        if not self.osm_live:
            return {"items": [], "osm_available": False, "radius_km": None,
                    "notices": ["ปิดการค้นหาจาก OpenStreetMap อยู่ จึงค้นที่พักรอบหมุดไม่ได้"]}
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
                return {"items": [], "osm_available": False, "radius_km": r, "notices": area.notices}
            used = r
            lodgings = [c for c in area.candidates
                        if c.kind == "lodging" and haversine_km(lat, lon, c.lat, c.lon) <= r]
            if lodgings:
                break
            if r != radii[-1]:
                notices.append(f"ไม่พบที่พักในรัศมี {r:g} กม. จึงขยายเป็น {radii[radii.index(r) + 1]:g} กม.")
        if not lodgings:
            notices.append(f"ไม่พบที่พักในรัศมี {used:g} กม. จากหมุดนี้")
            return {"items": [], "osm_available": True, "radius_km": used, "notices": notices}
        lodgings = dedupe(lodgings)
        lodgings.sort(key=lambda c: haversine_km(lat, lon, c.lat, c.lon))

        # ดึงสถานที่ครั้งเดียวทั้งพื้นที่ แล้วคำนวณระยะของแต่ละที่พักในเครื่อง
        poi_area = self._area(lat, lon, MAX_RADIUS_KM + used, KINDS_ALL)
        notices += poi_area.notices
        items = []
        for lod in lodgings:
            places, eff = self._rank(lod.lat, lod.lon, MAX_RADIUS_KM, KINDS_ALL, poi_area)
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
        return {"items": items, "osm_available": poi_area.osm_ok, "radius_km": used,
                "notices": notices, "attribution": "© OpenStreetMap contributors (ODbL)"}
