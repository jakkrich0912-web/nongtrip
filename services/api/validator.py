"""ตัวตรวจผลค้นอิสระ: ไม่ใช้โค้ดค้นหาของ services/places ร่วมกัน คำนวณและตรวจจากผลที่ได้ด้วยตัวเอง
ตรวจตาม docs/CONTRACT.md: รัศมี ≤ 30 กม., เรียงใกล้ไปไกล, ไม่ซ้ำ, ไม่มีเงิน/คะแนน/รีวิว, ติดป้ายแหล่งข้อมูล, ที่ตรวจแล้วมีอยู่จริงในไฟล์ข้อมูล"""
from __future__ import annotations

import json
import math
from pathlib import Path

MAX_RADIUS_KM = 30.0
DIST_TOLERANCE_KM = 0.02            # ระยะในผลปัดทศนิยม 2 ตำแหน่ง
FORBIDDEN_KEY_WORDS = ("cost", "price", "fee", "budget", "rating", "review", "score", "baht", "thb")
KINDS = {"attraction", "cafe"}
SOURCES = {"verified", "osm"}
OSM_MODES = {"live", "snapshot", "none"}
THAILAND = (5.4, 20.6, 97.3, 105.7)
DATA_DIR = Path(__file__).resolve().parent.parent / "places" / "data"
DATA_FILES = ("places.json", "places_all_provinces.json")

_R = 6371.0088


def _hav(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * _R * math.asin(min(1.0, math.sqrt(a)))


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def load_verified_ids(data_dir: Path = DATA_DIR) -> set[str]:
    """อ่านไฟล์ข้อมูลที่ตรวจแล้วเอง (ไม่เรียก loader ของบริการค้นหา)"""
    ids: set[str] = set()
    for f in DATA_FILES:
        p = Path(data_dir) / f
        if p.exists():
            for row in json.loads(p.read_text(encoding="utf-8"))["places"]:
                if row.get("verified") and row.get("lat") is not None:
                    ids.add(f"v:{row['id']}")
    return ids


def _bad_keys(obj, path="") -> list[str]:
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(w in str(k).lower() for w in FORBIDDEN_KEY_WORDS):
                bad.append(f"{path}{k}")
            bad += _bad_keys(v, f"{path}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += _bad_keys(v, f"{path}{i}.")
    return bad


def _check_places(items: list[dict], origin: tuple[float, float], radius: float, known: set[str] | None,
                  label: str) -> list[str]:
    problems: list[str] = []
    seen_ids: set[str] = set()
    last = -1.0
    near: list[tuple[str, float, float]] = []
    for i, it in enumerate(items):
        w = f"{label}[{i}] {it.get('name_th')!r}"
        for k in ("id", "name_th", "kind", "lat", "lon", "distance_km", "source", "maps_url", "directions_url"):
            if it.get(k) is None:
                problems.append(f"{w}: ขาดฟิลด์ {k}")
        if problems and any(p.startswith(w) for p in problems):
            continue
        if it["kind"] not in KINDS:
            problems.append(f"{w}: kind ไม่รู้จัก {it['kind']}")
        if it["source"] not in SOURCES:
            problems.append(f"{w}: source ไม่รู้จัก {it['source']}")
        prefix_ok = (it["source"] == "verified" and it["id"].startswith("v:")) or \
                    (it["source"] == "osm" and it["id"].startswith("osm:"))
        if not prefix_ok:
            problems.append(f"{w}: id ไม่ตรงกับ source")
        if it["source"] == "verified" and known is not None and it["id"] not in known:
            problems.append(f"{w}: ไม่พบสถานที่ที่ตรวจแล้วนี้ในไฟล์ข้อมูล")
        la0, la1, lo0, lo1 = THAILAND
        if not (la0 <= it["lat"] <= la1 and lo0 <= it["lon"] <= lo1):
            problems.append(f"{w}: พิกัดอยู่นอกประเทศไทย")
        real = _hav(origin[0], origin[1], it["lat"], it["lon"])
        if abs(real - it["distance_km"]) > DIST_TOLERANCE_KM:
            problems.append(f"{w}: ระยะที่แจ้ง {it['distance_km']} ไม่ตรงกับที่คำนวณได้ {real:.2f}")
        if real > min(radius, MAX_RADIUS_KM) + DIST_TOLERANCE_KM:
            problems.append(f"{w}: อยู่ไกลเกินรัศมี ({real:.2f} กม.)")
        if it["distance_km"] < last - 1e-9:
            problems.append(f"{w}: เรียงไม่ถูก (ใกล้ไปไกลเท่านั้น)")
        last = max(last, it["distance_km"])
        if it["id"] in seen_ids:
            problems.append(f"{w}: id ซ้ำ")
        seen_ids.add(it["id"])
        n = _norm(it["name_th"])
        for nn, la, lo in near:
            if n and n == nn and _hav(la, lo, it["lat"], it["lon"]) < 0.03:
                problems.append(f"{w}: ซ้ำกับรายการอื่น (ชื่อเดียวกัน ตำแหน่งเดียวกัน)")
                break
        near.append((n, it["lat"], it["lon"]))
        if not str(it["maps_url"]).startswith("https://www.google.com/maps/"):
            problems.append(f"{w}: maps_url ไม่ใช่ลิงก์ Google Maps")
    return problems


def _finish(problems: list[str], checked: int) -> dict:
    return {"ok": not problems, "checked": checked, "problems": problems[:20], "problem_count": len(problems)}


def validate_nearby(resp: dict, known_verified_ids: set[str] | None = None) -> dict:
    problems: list[str] = []
    center = resp.get("center") or {}
    radius = resp.get("radius_km")
    if center.get("lat") is None or center.get("lon") is None:
        return _finish(["ไม่มี center"], 0)
    if not isinstance(radius, (int, float)) or not (0 < radius <= MAX_RADIUS_KM):
        problems.append(f"รัศมี {radius} ต้องมากกว่า 0 และไม่เกิน {MAX_RADIUS_KM:g} กม.")
        radius = MAX_RADIUS_KM
    items = resp.get("items") or []
    problems += _check_places(items, (center["lat"], center["lon"]), radius, known_verified_ids, "items")
    bad = _bad_keys(resp)
    if bad:
        problems.append("พบฟิลด์ที่ห้ามมี (ราคา/คะแนน/รีวิว): " + ", ".join(bad[:5]))
    mode = resp.get("osm_mode")
    if mode not in OSM_MODES:
        problems.append(f"osm_mode ไม่รู้จัก {mode}")
    if any(it.get("source") == "osm" for it in items):
        if "OpenStreetMap" not in (resp.get("attribution") or ""):
            problems.append("ใช้ข้อมูล OSM แต่ไม่มีข้อความ © OpenStreetMap contributors")
    # v0.14: โหมด snapshot ไม่ต้องมีข้อความเตือน (ดูจาก osm_mode) ส่วนโหมด none ยังต้องบอกผู้ใช้ว่าไม่มีข้อมูล OSM
    if mode == "none" and not resp.get("notices"):
        problems.append(f"osm_mode={mode} แต่ไม่มีข้อความแจ้งผู้ใช้")
    if len(items) > resp.get("total", 0):
        problems.append("จำนวนรายการมากกว่า total")
    return _finish(problems, len(items))


def validate_lodgings_near(resp: dict, known_verified_ids: set[str] | None = None, top_n: int = 3) -> dict:
    problems: list[str] = []
    checked = 0
    radius = resp.get("radius_km")
    if radius is not None and not (0 < radius <= 10):
        problems.append(f"รัศมีค้นที่พัก {radius} เกิน 10 กม.")
    for li, lod in enumerate(resp.get("items") or []):
        nearest = lod.get("nearest") or []
        checked += len(nearest)
        if len(nearest) > top_n:
            problems.append(f"ที่พัก {lod.get('name')!r}: แสดงสถานที่เกิน {top_n} แห่ง")
        if lod.get("has_more") != (lod.get("places_total", 0) > len(nearest)):
            problems.append(f"ที่พัก {lod.get('name')!r}: has_more ไม่ตรงกับจำนวน")
        problems += _check_places(nearest, (lod["lat"], lod["lon"]), min(30.0, lod.get("places_radius_km") or 30.0),
                                  known_verified_ids, f"items[{li}].nearest")
    bad = _bad_keys(resp)
    if bad:
        problems.append("พบฟิลด์ที่ห้ามมี (ราคา/คะแนน/รีวิว): " + ", ".join(bad[:5]))
    if resp.get("items") and "OpenStreetMap" not in (resp.get("attribution") or ""):
        problems.append("ไม่มีข้อความ © OpenStreetMap contributors")
    return _finish(problems, checked)
