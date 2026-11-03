"""เส้นทางผู้ใช้ ประวัติ สถานที่โปรด แชต (docs/CONTRACT.md ข้อ 3.3-3.4)

ผู้ที่ไม่ได้ล็อกอินไม่ถูกบันทึกอะไรเลย: ทุกเส้นทางใต้ /api/me ตอบ 401
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.places.geo import in_thailand, place_url

from . import auth
from .google import GoogleInvalid, GoogleUnavailable, GoogleVerifier
from .store import EmailTaken, Store

COOKIE = "nt_session"
MAX_ID = 2 ** 31 - 1  # เกินนี้ SQLite รับไม่ได้ (เคยทำให้ตอบ 500)
KINDS = {"attraction", "cafe"}
OSM_ID_RE = re.compile(r"^osm:(node|way|relation)/\d+$")
REGISTER_PER_HOUR = 20  # สมัครได้ไม่เกินนี้ต่อ IP ต่อชั่วโมง (นับทุกครั้งที่ลอง)


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


class Credentials(BaseModel):
    email: str = Field(max_length=300)
    password: str = Field(max_length=auth.MAX_PASSWORD + 100)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=1, max_length=5000)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=auth.MAX_PASSWORD + 100)
    new_password: str = Field(max_length=auth.MAX_PASSWORD + 100)


class DeleteAccountIn(BaseModel):
    email: str = Field(max_length=300)  # พิมพ์อีเมลของตัวเองยืนยัน กันกดลบพลาด


class SearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    lat: float
    lon: float


class FavoriteIn(BaseModel):
    place_id: str = Field(min_length=1, max_length=100)
    name_th: str | None = Field(default=None, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    kind: str | None = None
    subtype: str | None = Field(default=None, max_length=60)
    lat: float | None = None
    lon: float | None = None
    province: str | None = Field(default=None, max_length=60)


def session_of(store: Store, secret: str, token: str | None) -> tuple[dict, str] | None:
    """(ผู้ใช้, รหัสเซสชัน) จากคุกกี้ ต้องผ่านทั้งลายเซ็น วันหมดอายุ และยังมีเซสชันนี้ในฐานข้อมูล"""
    got = auth.read_session(token, secret)
    if not got:
        return None
    uid, sid = got
    if not store.session_valid(uid, sid):
        return None
    user = store.user_by_id(uid)
    return (user, sid) if user else None


def session_user(store: Store, secret: str, token: str | None) -> dict | None:
    got = session_of(store, secret, token)
    return got[0] if got else None


def build_router(store: Store, secret: str, verified: list, secure_cookie: bool = True,
                 throttle: auth.LoginThrottle | None = None, google: GoogleVerifier | None = None,
                 register_throttle: auth.LoginThrottle | None = None) -> APIRouter:
    r = APIRouter()
    throttle = throttle or auth.LoginThrottle()
    # กันสคริปต์สมัครบัญชีรัวๆ จาก IP เดียว (แต่ละครั้งแฮชรหัสผ่านด้วย scrypt ซึ่งกินเครื่อง และเพิ่มแถวในฐานข้อมูล)
    register_throttle = register_throttle or auth.LoginThrottle(max_fails=REGISTER_PER_HOUR, window=3600)
    google = google or GoogleVerifier()
    google_throttle = auth.LoginThrottle(max_fails=30, window=60)  # กันคนยิงให้เราเรียก Google รัวๆ (นับทุกคำขอต่อ IP)
    verified_by_id = {c.id: c for c in verified}

    def set_session(resp: Response, user_id: int) -> None:
        sid, exp = auth.new_session_id(), auth.session_expiry()
        store.create_session(user_id, sid, exp)
        resp.set_cookie(COOKIE, auth.make_token(user_id, secret, sid=sid, exp=exp), max_age=auth.SESSION_DAYS * 86400,
                        httponly=True, secure=secure_cookie, samesite="lax", path="/")

    def current_user(req: Request) -> dict | None:
        return session_user(store, secret, req.cookies.get(COOKIE))

    def need_login(req: Request):
        """คืน (ผู้ใช้, None) หรือ (None, คำตอบ 401)"""
        u = current_user(req)
        if u:
            return u, None
        return None, _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")

    # ---- ผู้ใช้ ----
    @r.post("/api/auth/register", status_code=201)
    def register(body: Credentials, req: Request, response: Response):
        ip = req.client.host if req.client else "?"
        if register_throttle.blocked(ip):
            return _err(429, "rate_limited", "สมัครบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่")
        register_throttle.fail(ip)
        email = auth.normalize_email(body.email)
        if not auth.valid_email(email):
            return _err(400, "invalid_param", "รูปแบบอีเมลไม่ถูกต้อง")
        if not (auth.MIN_PASSWORD <= len(body.password) <= auth.MAX_PASSWORD):
            return _err(400, "invalid_param", f"รหัสผ่านต้องยาว {auth.MIN_PASSWORD}-{auth.MAX_PASSWORD} ตัวอักษร")
        try:
            user = store.create_user(email, auth.hash_password(body.password))
        except EmailTaken:
            return _err(409, "email_taken", "อีเมลนี้สมัครไว้แล้ว")
        set_session(response, user["id"])
        return {"user": user}

    @r.post("/api/auth/login")
    def login(body: Credentials, response: Response):
        email = auth.normalize_email(body.email)
        if throttle.blocked(email):
            return _err(429, "rate_limited", "ใส่รหัสผ่านผิดหลายครั้งเกินไป กรุณารอสักครู่แล้วลองใหม่")
        row = store.user_by_email(email)
        ok = auth.verify_password(body.password, row["pw_hash"]) if row else (auth.burn_verify(body.password) or False)
        if not ok:
            throttle.fail(email)
            return _err(401, "unauthorized", "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
        throttle.reset(email)
        set_session(response, row["id"])
        return {"user": {"id": row["id"], "email": row["email"]}}

    @r.post("/api/auth/google")
    def login_google(body: GoogleIn, req: Request, response: Response):
        if not google.configured:
            return _err(501, "google_not_configured", "ยังไม่เปิดใช้การเข้าสู่ระบบด้วย Google")
        ip = req.client.host if req.client else "?"
        if google_throttle.blocked(ip):
            return _err(429, "rate_limited", "ลองบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่")
        google_throttle.fail(ip)
        try:
            who = google.verify(body.credential)
        except GoogleInvalid:
            return _err(401, "unauthorized", "ยืนยันตัวตนกับ Google ไม่สำเร็จ กรุณาลองใหม่")
        except GoogleUnavailable:
            return _err(502, "upstream_unavailable", "ติดต่อ Google ไม่ได้ในตอนนี้ กรุณาลองใหม่อีกครั้ง")
        user = store.user_by_google_sub(who["sub"])
        if user is None:
            # อีเมลนี้สมัครด้วยรหัสผ่านไว้แล้ว: ไม่ผูกให้เอง เพราะระบบเราไม่ได้ยืนยันอีเมลตอนสมัคร
            # (ถ้าผูกให้ ผู้ที่สมัครอีเมลของคนอื่นไว้ล่วงหน้าจะเข้าบัญชีเดียวกับเจ้าของอีเมลได้)
            if store.user_by_email(who["email"]):
                return _err(409, "email_taken", "อีเมลนี้สมัครด้วยรหัสผ่านไว้แล้ว กรุณาเข้าสู่ระบบด้วยอีเมลและรหัสผ่าน")
            try:
                user = store.create_google_user(who["email"], who["sub"])
            except EmailTaken:
                return _err(409, "email_taken", "อีเมลนี้สมัครไว้แล้ว")
            response.status_code = 201
        set_session(response, user["id"])
        return {"user": {"id": user["id"], "email": user["email"]}}

    @r.post("/api/auth/logout", status_code=204)
    def logout(req: Request):
        # ยกเลิกเซสชันนี้ในฐานข้อมูลด้วย ใครคัดลอกคุกกี้ไปก่อนหน้าก็ใช้ต่อไม่ได้
        got = auth.read_session(req.cookies.get(COOKIE), secret)
        if got:
            store.delete_session(got[1])
        resp = Response(status_code=204)
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @r.get("/api/auth/me")
    def me(req: Request):
        u, bad = need_login(req)
        return bad or {"user": u}

    # ---- ตั้งค่าบัญชี ----
    @r.get("/api/me/account")
    def account(req: Request):
        got = session_of(store, secret, req.cookies.get(COOKIE))
        if not got:
            return _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")
        a = store.account(got[0]["id"])
        return {"email": a["email"], "created_at": a["created_at"], "has_password": a["has_password"],
                "google": a["google"], "sessions": store.count_sessions(a["id"])}

    @r.post("/api/me/password")
    def change_password(body: PasswordChangeIn, req: Request, response: Response):
        """เปลี่ยนรหัสผ่าน ต้องใส่รหัสเดิม แล้วยกเลิกทุกเซสชันเดิม (อุปกรณ์อื่นต้องเข้าสู่ระบบใหม่)"""
        got = session_of(store, secret, req.cookies.get(COOKIE))
        if not got:
            return _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")
        user = got[0]
        stored = store.password_hash(user["id"]) or ""
        if not stored.startswith("scrypt$"):
            return _err(400, "no_password", "บัญชีนี้เข้าสู่ระบบด้วย Google จึงไม่มีรหัสผ่านให้เปลี่ยน")
        # ใช้ตัวนับเดียวกับหน้าเข้าสู่ระบบ กันเดารหัสเดิมผ่านหน้านี้แทน
        if throttle.blocked(user["email"]):
            return _err(429, "rate_limited", "ใส่รหัสผ่านผิดหลายครั้งเกินไป กรุณารอสักครู่แล้วลองใหม่")
        if not auth.verify_password(body.current_password, stored):
            throttle.fail(user["email"])
            return _err(400, "wrong_password", "รหัสผ่านปัจจุบันไม่ถูกต้อง")
        throttle.reset(user["email"])
        if not (auth.MIN_PASSWORD <= len(body.new_password) <= auth.MAX_PASSWORD):
            return _err(400, "invalid_param", f"รหัสผ่านใหม่ต้องยาว {auth.MIN_PASSWORD}-{auth.MAX_PASSWORD} ตัวอักษร")
        if body.new_password == body.current_password:
            return _err(400, "invalid_param", "รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม")
        store.set_password(user["id"], auth.hash_password(body.new_password))
        others = store.delete_sessions(user["id"], keep=got[1])
        store.delete_session(got[1])
        set_session(response, user["id"])  # เซสชันใหม่สำหรับเครื่องนี้ คุกกี้เดิมทุกใบใช้ไม่ได้แล้ว
        return {"signed_out": others}

    @r.post("/api/me/sessions/revoke-others")
    def revoke_others(req: Request):
        """ออกจากระบบทุกอุปกรณ์ ยกเว้นเครื่องที่กดอยู่"""
        got = session_of(store, secret, req.cookies.get(COOKIE))
        if not got:
            return _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")
        return {"signed_out": store.delete_sessions(got[0]["id"], keep=got[1])}

    @r.post("/api/me/delete", status_code=204)
    def delete_account(body: DeleteAccountIn, req: Request):
        """ลบบัญชีและข้อมูลทั้งหมดถาวร ต้องส่งอีเมลของตัวเองมายืนยัน"""
        u, bad = need_login(req)
        if bad:
            return bad
        if body.email.strip().lower() != u["email"]:
            return _err(400, "invalid_param", "อีเมลที่พิมพ์ไม่ตรงกับบัญชีนี้")
        store.delete_user(u["id"])
        resp = Response(status_code=204)
        resp.delete_cookie(COOKIE, path="/")
        return resp

    # ---- ที่พักที่เคยค้น ----
    @r.get("/api/me/searches")
    def searches(req: Request):
        u, bad = need_login(req)
        return bad or {"items": store.list_searches(u["id"])}

    @r.post("/api/me/searches", status_code=201)
    def add_search(body: SearchIn, req: Request):
        u, bad = need_login(req)
        if bad:
            return bad
        if not in_thailand(body.lat, body.lon):
            return _err(400, "invalid_param", "พิกัดอยู่นอกประเทศไทย")
        name = body.name.strip()
        if not name:
            return _err(400, "invalid_param", "ชื่อที่พักว่าง")
        return store.add_search(u["id"], name, body.lat, body.lon)

    @r.delete("/api/me/searches", status_code=204)
    def delete_all_searches(req: Request):
        u, bad = need_login(req)
        if bad:
            return bad
        store.delete_all_searches(u["id"])
        return Response(status_code=204)

    @r.delete("/api/me/searches/{search_id}", status_code=204)
    def delete_search(req: Request, search_id: int = Path(ge=1, le=MAX_ID)):
        u, bad = need_login(req)
        if bad:
            return bad
        store.delete_search(u["id"], search_id)
        return Response(status_code=204)

    # ---- สถานที่โปรด ----
    def fav_out(row: dict) -> dict:
        return {"id": row["place_id"], "name_th": row["name_th"], "name_en": row["name_en"], "kind": row["kind"],
                "subtype": row["subtype"], "lat": row["lat"], "lon": row["lon"], "source": row["source"],
                "province": row["province"], "maps_url": place_url(row["name_th"], row["lat"], row["lon"]),
                "saved_at": row["created_at"]}

    @r.get("/api/me/favorites")
    def favorites(req: Request):
        u, bad = need_login(req)
        return bad or {"items": [fav_out(x) for x in store.list_favorites(u["id"])]}

    @r.post("/api/me/favorites", status_code=201)
    def add_favorite(body: FavoriteIn, req: Request, response: Response):
        u, bad = need_login(req)
        if bad:
            return bad
        pid = body.place_id.strip()
        if pid.startswith("v:"):
            # สถานที่ที่ตรวจแล้ว: ใช้ข้อมูลจากไฟล์ของเรา ไม่เชื่อค่าที่ไคลเอนต์ส่งมา
            c = verified_by_id.get(pid)
            if not c:
                return _err(400, "invalid_param", "ไม่พบสถานที่ที่ตรวจแล้วรหัสนี้")
            p = {"place_id": pid, "name_th": c.name_th, "name_en": c.name_en, "kind": c.kind,
                 "subtype": c.subtype, "lat": c.lat, "lon": c.lon, "source": "verified", "province": c.province}
        elif OSM_ID_RE.match(pid):
            if not body.name_th or not body.name_th.strip() or body.lat is None or body.lon is None:
                return _err(400, "invalid_param", "สถานที่จาก OpenStreetMap ต้องส่ง name_th, lat, lon มาด้วย")
            if body.kind not in KINDS:
                return _err(400, "invalid_param", "kind ต้องเป็น attraction หรือ cafe")
            if not in_thailand(body.lat, body.lon):
                return _err(400, "invalid_param", "พิกัดอยู่นอกประเทศไทย")
            p = {"place_id": pid, "name_th": body.name_th.strip(), "name_en": body.name_en, "kind": body.kind,
                 "subtype": body.subtype, "lat": body.lat, "lon": body.lon, "source": "osm",
                 "province": body.province}
        else:
            return _err(400, "invalid_param", "รหัสสถานที่ต้องขึ้นต้นด้วย v: หรือ osm:")
        try:
            row, created = store.add_favorite(u["id"], p)
        except OverflowError as e:
            return _err(400, "invalid_param", str(e))
        if not created:
            response.status_code = 200
        return fav_out(row)

    @r.delete("/api/me/favorites", status_code=204)
    def delete_all_favorites(req: Request):
        u, bad = need_login(req)
        if bad:
            return bad
        store.delete_all_favorites(u["id"])
        return Response(status_code=204)

    @r.delete("/api/me/favorites/{place_id:path}", status_code=204)
    def delete_favorite(place_id: str, req: Request):
        u, bad = need_login(req)
        if bad:
            return bad
        store.delete_favorite(u["id"], place_id)
        return Response(status_code=204)

    # ---- แชต ----
    @r.get("/api/me/chats")
    def chats(req: Request):
        u, bad = need_login(req)
        return bad or {"items": store.list_chats(u["id"])}

    @r.get("/api/me/chats/{chat_id}")
    def chat(req: Request, chat_id: int = Path(ge=1, le=MAX_ID)):
        u, bad = need_login(req)
        if bad:
            return bad
        c = store.get_chat(u["id"], chat_id)
        return c or _err(404, "not_found", "ไม่พบแชตนี้")

    @r.delete("/api/me/chats", status_code=204)
    def delete_all_chats(req: Request):
        u, bad = need_login(req)
        if bad:
            return bad
        store.delete_all_chats(u["id"])
        return Response(status_code=204)

    @r.delete("/api/me/chats/{chat_id}", status_code=204)
    def delete_chat(req: Request, chat_id: int = Path(ge=1, le=MAX_ID)):
        u, bad = need_login(req)
        if bad:
            return bad
        store.delete_chat(u["id"], chat_id)
        return Response(status_code=204)

    return r
