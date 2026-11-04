"""ไกด์ที่เที่ยว: อ่านสถานที่ที่ตรวจที่มาแล้วจากไฟล์ข้อมูล (docs/CONTRACT.md ข้อ 3.5)

หน้าแรก หน้าจังหวัด และหน้ารายละเอียดสถานที่ใช้ข้อมูลชุดนี้ ต่างจาก Candidate ที่ใช้ค้นรอบที่พัก
ตรงที่เก็บคำอธิบาย หมายเหตุ และแหล่งที่มาไว้แสดง ไม่เปิดเผยฟิลด์ราคา (cost_thb) ในทุกกรณี
ค่าที่ไม่มีแหล่งอ้างอิงเป็น null / ว่าง และหน้าเว็บต้องไม่เติมเอง
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.places.geo import in_thailand, place_url
from services.places.provinces import PROVINCES, REGION_ORDER, REGIONS, region_of
from services.places.verified import DATA_DIR, FILES

from . import metrics

ID_RE = re.compile(r"^v:[A-Za-z0-9_-]{1,40}$")
MAX_FEATURED = 50
MAX_PAGE = 200


def load_guide(data_dir: Path | str = DATA_DIR) -> list[dict]:
    """สถานที่ที่ตรวจแล้ว (verified=true) ตามลำดับในไฟล์ ไฟล์หลังทับ id เดียวกันของไฟล์ก่อน (เหมือน load_verified)"""
    out: dict[str, dict] = {}
    for fname in FILES:
        path = Path(data_dir) / fname
        if not path.exists():
            continue
        for p in json.loads(path.read_text(encoding="utf-8"))["places"]:
            lat, lon = p.get("lat"), p.get("lon")
            if not p.get("verified") or lat is None or lon is None or not in_thailand(float(lat), float(lon)):
                continue
            srcs = p.get("sources") or []
            first = srcs[0] if srcs else {}
            province = p.get("province")
            area = (p.get("area") or "").strip() or None
            pid = f"v:{p['id']}"
            out[pid] = {
                "id": pid,
                "name_th": p["name_th"],
                "name_en": p.get("name_en"),
                "kind": "cafe" if p.get("category") == "cafe" else "attraction",
                "subtype": p.get("category") or "other",
                "province": province,
                "area": None if area == province else area,
                "description": (p.get("description") or "").strip() or None,
                "notes": [str(n) for n in (p.get("notes") or []) if str(n).strip()],
                "lat": float(lat),
                "lon": float(lon),
                "maps_url": place_url(p["name_th"], float(lat), float(lon)),
                "source_url": first.get("url"),
                "source_title": first.get("title"),
                "source_checked_on": first.get("checked_on"),
            }
    return list(out.values())


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


def _counts(items: list[dict]) -> dict[str, int]:
    c: dict[str, int] = {}
    for x in items:
        c[x["subtype"]] = c.get(x["subtype"], 0) + 1
    return dict(sorted(c.items()))


def featured(items: list[dict], limit: int, category: str | None) -> list[dict]:
    """ชุดแสดงหน้าแรก: จังหวัดละ 1 แห่ง (ถ้าจังหวัดนั้นมีคำอธิบายก็เลือกแห่งที่มี ไม่งั้นแห่งแรกในไฟล์)
    สลับไปทีละภาคให้หลากหลาย ไม่ใช่การจัดอันดับความนิยม (ระบบไม่มีข้อมูลความนิยมหรือรีวิว)"""
    pool = [x for x in items if not category or x["subtype"] == category]
    by_prov: dict[str, dict] = {}
    for x in pool:
        cur = by_prov.get(x["province"])
        if cur is None or (not cur["description"] and x["description"]):
            by_prov[x["province"]] = x
    lanes = [[by_prov[p] for p in REGIONS[r] if p in by_prov] for r in REGION_ORDER]
    out: list[dict] = []
    for i in range(max((len(lane) for lane in lanes), default=0)):
        for lane in lanes:
            if i < len(lane):
                out.append(lane[i])
    return out[:limit]


def build_guide_router(items: list[dict]) -> APIRouter:
    r = APIRouter()
    by_id = {x["id"]: x for x in items}

    @r.get("/api/guide/featured")
    def guide_featured(limit: int = Query(12, ge=1, le=MAX_FEATURED), category: str | None = Query(None, max_length=40)):
        return {"items": featured(items, limit, category), "categories": _counts(items), "total": len(items)}

    @r.get("/api/provinces/{name}/places")
    def province_places(name: str, category: str | None = Query(None, max_length=40),
                        limit: int = Query(50, ge=1, le=MAX_PAGE), offset: int = Query(0, ge=0, le=100000)):
        name = name.strip()
        if name not in PROVINCES:
            return _err(400, "invalid_param", "ไม่รู้จักชื่อจังหวัดนี้ (ต้องเป็นหนึ่งใน 77 จังหวัด)")
        mine = [x for x in items if x["province"] == name]
        if offset == 0 and not category:
            metrics.count("province_view", name)
        shown = [x for x in mine if not category or x["subtype"] == category]
        return {"province": name, "region": region_of(name), "verified_count": len(mine),
                "categories": _counts(mine), "total": len(shown), "items": shown[offset:offset + limit],
                "has_more": offset + limit < len(shown)}

    @r.get("/api/places/{place_id:path}")
    def place_detail(place_id: str):
        # ไกด์มีเฉพาะสถานที่ที่ตรวจแล้ว (v:...) สถานที่จาก OpenStreetMap ไม่มีหน้ารายละเอียด
        item = by_id.get(place_id) if ID_RE.match(place_id) else None
        return item or _err(404, "not_found", "ไม่พบสถานที่นี้ในไกด์")

    return r
