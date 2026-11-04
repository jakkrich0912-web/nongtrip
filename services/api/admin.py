"""แดชบอร์ดผู้ดูแล (CONTRACT ข้อ 3.6)

สิทธิ์ผู้ดูแลมาจาก ADMIN_EMAILS (อีเมลคั่นด้วยจุลภาค) ไม่ตั้ง = ไม่มีใครเป็นผู้ดูแล
ทุกตัวเลขเป็นยอดรวมของทั้งระบบ ไม่มีอีเมล ข้อความแชต หรือข้อมูลของใครเป็นรายคน
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.places.provinces import REGION_ORDER, REGIONS

from .accounts import COOKIE, session_user
from .metrics import TH
from .roles import is_admin
from .store import Store

DAYS = 14        # กราฟรายวันย้อนหลัง
WINDOW = 30      # ยอดรวมย้อนหลัง (วัน)


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def summarize(rows: list[dict], today: datetime) -> dict:
    """แปลงแถว (วัน ชนิด ค่า จำนวน) เป็นกราฟรายวันและยอดรวม"""
    days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DAYS - 1, -1, -1)]
    daily = {d: {"day": d, "chat": 0, "llm": 0, "rule": 0, "search": 0} for d in days}
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        totals[r["kind"]][r["key"]] += r["n"]
        if r["day"] in daily:
            d = daily[r["day"]]
            if r["kind"] == "chat":
                d["chat"] += r["n"]
                d["llm" if r["key"] == "llm" else "rule"] += r["n"]
            elif r["kind"] == "search":
                d["search"] += r["n"]
    top = lambda kind, n=8: [{"key": k, "n": v} for k, v in sorted(totals[kind].items(), key=lambda kv: (-kv[1], kv[0]))[:n]]  # noqa: E731
    chat_modes = dict(totals["chat"])
    return {
        "daily": list(daily.values()),
        "chat_total": sum(chat_modes.values()),
        "chat_modes": chat_modes,
        "guard": top("guard"),
        "search_total": sum(totals["search"].values()),
        "top_provinces": top("search_province"),
        "top_province_pages": top("province_view", 5),
    }


def build_admin_router(store: Store, secret: str, svc, rag) -> APIRouter:
    r = APIRouter()

    @r.get("/api/admin/overview")
    def overview(req: Request):
        user = session_user(store, secret, req.cookies.get(COOKIE))
        if not user:
            return _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")
        if not is_admin(user["email"]):
            return _err(403, "forbidden", "หน้านี้สำหรับผู้ดูแลระบบเท่านั้น")
        now = datetime.now(timezone.utc)
        local = now.astimezone(TH)
        since = (local - timedelta(days=WINDOW - 1)).strftime("%Y-%m-%d")
        counts = store.admin_counts((now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        usage = summarize(store.metric_rows(since), local)

        snap = svc.snapshot
        snap_set: set[str] = set()
        if snap.available():
            snap._load()
            snap_set = {_nfc(p) for p in snap.provinces}
        regions = []
        verified_by = defaultdict(int)
        for c in svc.verified:
            verified_by[_nfc(c.province)] += 1
        for reg in REGION_ORDER:
            regions.append({"region": reg, "provinces": [
                {"name": p, "verified": verified_by[_nfc(p)], "snapshot": _nfc(p) in snap_set} for p in REGIONS[reg]]})
        all_p = [p for reg in regions for p in reg["provinces"]]
        return {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_days": WINDOW,
            "system": {"llm": bool(rag and rag.enabled), "rag_docs": rag.health()["docs"] if rag else 0,
                       "osm_live": svc.osm_live, "verified_places": len(svc.verified),
                       "snapshot_built_on": snap.built_on},
            "users": {k: counts[k] for k in ("users", "users_google", "users_new", "users_signed_in", "active_sessions")},
            "content": {k: counts[k] for k in ("saved_searches", "favorites", "chats", "messages")},
            "ratings": counts["ratings"],
            "top_favorites": counts["top_favorites"],
            "usage": usage,
            "coverage": {
                "provinces": len(all_p),
                "with_snapshot": sum(p["snapshot"] for p in all_p),
                "with_verified": sum(1 for p in all_p if p["verified"] > 0),
                "missing_snapshot": [p["name"] for p in all_p if not p["snapshot"]],
                "regions": regions,
            },
        }

    return r
