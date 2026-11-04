"""แจ้งข้อมูลสถานที่ผิด (CONTRACT v0.26)

POST /api/reports                     ใครก็แจ้งได้ ไม่ต้องล็อกอิน จำกัดจำนวนต่อ IP (ไม่บันทึก IP)
GET  /api/admin/reports               ผู้ดูแลดูรายการ
DELETE /api/admin/reports/{id}        ผู้ดูแลตรวจแล้ว ลบรายการ
ไม่เก็บว่าใครแจ้ง ชื่อสถานที่ที่ตรวจแล้วใช้ชื่อจากไฟล์ของเรา ไม่เชื่อค่าที่ส่งมา
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .accounts import COOKIE, session_user
from .chat import ChatThrottle
from .chat_rules import clean
from .roles import is_admin
from .store import Store

OSM_ID = re.compile(r"^osm:(node|way|relation)/\d{1,15}$")
REASONS = ("closed", "wrong_location", "wrong_name", "wrong_type", "other")


class ReportIn(BaseModel):
    place_id: str = Field(min_length=1, max_length=100)
    place_name: str | None = Field(default=None, max_length=200)
    reason: Literal["closed", "wrong_location", "wrong_name", "wrong_type", "other"]
    note: str | None = Field(default=None, max_length=300)


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


def build_reports_router(store: Store, secret: str, verified: list, throttle: ChatThrottle | None = None) -> APIRouter:
    r = APIRouter()
    throttle = throttle or ChatThrottle(limit=5, window=600.0)
    names = {c.id: c.name_th for c in verified}

    def admin(req: Request):
        user = session_user(store, secret, req.cookies.get(COOKIE))
        if not user:
            return _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")
        if not is_admin(user["email"]):
            return _err(403, "forbidden", "หน้านี้สำหรับผู้ดูแลระบบเท่านั้น")
        return None

    @r.post("/api/reports", status_code=201)
    def add(body: ReportIn, req: Request):
        if not throttle.allow(f"report:{req.client.host if req.client else '?'}"):
            return _err(429, "rate_limited", "แจ้งถี่เกินไป กรุณาลองใหม่ภายหลัง")
        pid = body.place_id.strip()
        if pid.startswith("v:"):
            name = names.get(pid)
            if not name:
                return _err(400, "invalid_param", "ไม่พบสถานที่ที่ตรวจแล้วรหัสนี้")
        elif OSM_ID.match(pid):
            name = clean(body.place_name or "")
            if not name:
                return _err(400, "invalid_param", "สถานที่จาก OpenStreetMap ต้องส่ง place_name มาด้วย")
        else:
            return _err(400, "invalid_param", "รหัสสถานที่ต้องขึ้นต้นด้วย v: หรือ osm:")
        note = clean(body.note or "") or None
        try:
            row = store.add_report(pid, name[:200], body.reason, note)
        except OverflowError as e:
            return _err(503, "busy", str(e))
        return {"id": row["id"], "created_at": row["created_at"]}

    @r.get("/api/admin/reports")
    def list_(req: Request):
        bad = admin(req)
        return bad or {"items": store.list_reports(), "total": store.count_reports()}

    @r.delete("/api/admin/reports/{report_id}", status_code=204)
    def done(req: Request, report_id: int = Path(ge=1, le=2**53)):
        bad = admin(req)
        if bad:
            return bad
        if not store.delete_report(report_id):
            return _err(404, "not_found", "ไม่พบรายการนี้")
        return None

    return r
