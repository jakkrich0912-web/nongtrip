"""ตรวจ Google ID token สำหรับปุ่ม "ดำเนินการต่อด้วย Google"

หน้าเว็บได้ ID token (credential) จาก Google Identity Services แล้วส่งมาที่ POST /api/auth/google
เราให้ Google เป็นผู้ตรวจลายเซ็น (endpoint tokeninfo) แล้วตรวจต่อเองว่า
  - aud ตรงกับ GOOGLE_CLIENT_ID ของเรา (กัน token ที่ออกให้แอปอื่น)
  - iss เป็น Google, ยังไม่หมดอายุ, อีเมลผ่านการยืนยันแล้ว
ไม่ตั้ง GOOGLE_CLIENT_ID = ปิดฟีเจอร์ (ตอบ 501) ไม่มีค่าเริ่มต้นที่เดาได้
"""
from __future__ import annotations

import os
import time

import httpx

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
MAX_CREDENTIAL = 4096


class GoogleInvalid(Exception):
    """token ไม่ถูกต้อง หมดอายุ หรือออกให้แอปอื่น"""


class GoogleUnavailable(Exception):
    """ติดต่อ Google ไม่ได้ (เครือข่ายล่ม/ช้า)"""


class GoogleVerifier:
    def __init__(self, client_id: str | None = None, http: httpx.Client | None = None, clock=time.time):
        self.client_id = (client_id if client_id is not None else os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
        self._http, self._clock = http, clock

    @property
    def configured(self) -> bool:
        return bool(self.client_id)

    def verify(self, credential: str) -> dict:
        """คืน {"sub", "email"} ของผู้ใช้ Google หรือโยน GoogleInvalid / GoogleUnavailable"""
        if not self.configured:
            raise GoogleInvalid("not configured")
        if not credential or len(credential) > MAX_CREDENTIAL:
            raise GoogleInvalid("bad credential")
        try:
            if self._http is not None:
                r = self._http.get(TOKENINFO_URL, params={"id_token": credential}, timeout=5.0)
            else:
                r = httpx.get(TOKENINFO_URL, params={"id_token": credential}, timeout=5.0)
        except httpx.HTTPError as e:
            raise GoogleUnavailable(str(e)) from e
        if r.status_code in (400, 401):
            raise GoogleInvalid("rejected by google")
        if r.status_code != 200:
            raise GoogleUnavailable(f"status {r.status_code}")
        try:
            d = r.json()
            if not isinstance(d, dict):
                raise ValueError("not an object")
            exp = int(d.get("exp"))
        except (ValueError, TypeError):
            raise GoogleInvalid("unreadable response") from None
        sub, email = d.get("sub"), (d.get("email") or "").strip().lower()
        if d.get("aud") != self.client_id or d.get("iss") not in ISSUERS or exp <= self._clock():
            raise GoogleInvalid("claims mismatch")
        if str(d.get("email_verified")).lower() != "true" or not isinstance(sub, str) or not sub or not email:
            raise GoogleInvalid("email not verified")
        return {"sub": sub, "email": email}
