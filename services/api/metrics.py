"""ตัวนับรวมรายวันสำหรับแดชบอร์ดผู้ดูแล

เก็บแค่ "วัน ชนิด ค่า จำนวน" เช่น (2026-11-04, chat, llm, 12) ไม่เก็บข้อความ IP หรือรหัสผู้ใช้ จึงย้อนกลับไปหาตัวคนไม่ได้
นับไม่สำเร็จ (ฐานข้อมูลล็อก ฯลฯ) ต้องไม่ทำให้คำขอของผู้ใช้ล้ม จึงกลืนข้อผิดพลาดทุกชนิด
"""
from __future__ import annotations

import logging
import math

from .store import Store

log = logging.getLogger(__name__)

KINDS = {"chat", "guard", "search", "search_province", "province_view"}
_store: Store | None = None


def attach(store: Store | None) -> None:
    """create_app เรียกครั้งเดียว ให้ตัวนับเขียนลงฐานข้อมูลเดียวกับระบบ"""
    global _store
    _store = store


def count(kind: str, key: str, n: int = 1) -> None:
    if _store is None or kind not in KINDS or not key:
        return
    try:
        _store.bump_metric(kind, str(key)[:80], n)
    except Exception:  # noqa: BLE001 ตัวนับห้ามทำให้คำขอล้ม
        log.warning("นับ %s/%s ไม่สำเร็จ", kind, key, exc_info=True)


def nearest_province(lat: float, lon: float, places: list, max_km: float = 60.0) -> str | None:
    """จังหวัดของจุดค้นแบบประมาณ: ใช้จังหวัดของสถานที่ที่ตรวจแล้วที่ใกล้ที่สุดในรัศมี max_km"""
    best, best_d = None, max_km
    for p in places:
        prov = getattr(p, "province", None)
        if not prov:
            continue
        dlat = math.radians(p.lat - lat)
        dlon = math.radians(p.lon - lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(p.lat)) * math.sin(dlon / 2) ** 2
        d = 6371.0 * 2 * math.asin(math.sqrt(min(1.0, a)))
        if d < best_d:
            best, best_d = prov, d
    return best
