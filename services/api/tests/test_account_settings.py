"""ตั้งค่าบัญชีและเซสชัน: ออกจากระบบแล้วคุกกี้เดิมใช้ไม่ได้ เปลี่ยนรหัสผ่าน ออกจากระบบอุปกรณ์อื่น (CONTRACT ข้อ 3.3)"""
import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from services.api import auth
from services.api.tests.test_accounts import PW, make, signup

NEW_PW = "รหัสใหม่ที่ยาวพอ-456"


@pytest.fixture
def env(tmp_path):
    return make(tmp_path)


def second_device(c, email="a@example.com", pw=PW):
    """เข้าสู่ระบบบัญชีเดิมจากอีกเครื่อง (client ใหม่ คุกกี้แยกกัน)"""
    other = TestClient(c.app)
    assert other.post("/api/auth/login", json={"email": email, "password": pw}).status_code == 200
    return other


def test_logout_revokes_the_cookie_on_the_server(env):
    c, _, _ = env
    signup(c)
    copied = c.cookies.get("nt_session")
    assert c.post("/api/auth/logout").status_code == 204
    c.cookies.set("nt_session", copied)                  # คนที่คัดลอกคุกกี้ไว้ก่อนออกจากระบบ
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/me/searches").status_code == 401


def test_logout_only_ends_this_device(env):
    c, _, _ = env
    signup(c)
    other = second_device(c)
    c.post("/api/auth/logout")
    assert other.get("/api/auth/me").status_code == 200


def test_old_token_format_without_session_is_rejected(env):
    c, _, _ = env
    signup(c)
    uid = int(c.cookies.get("nt_session").split(".")[0])
    exp = auth.session_expiry()
    payload = f"{uid}.{exp}"
    sig = auth._sign(payload, "test-secret")
    c.cookies.clear()
    c.cookies.set("nt_session", f"{payload}.{sig}")      # รูปแบบเดิมก่อนมีตาราง sessions
    assert c.get("/api/auth/me").status_code == 401


def test_signed_token_with_unknown_session_is_rejected(env):
    c, _, _ = env
    signup(c)
    uid = int(c.cookies.get("nt_session").split(".")[0])
    c.cookies.clear()
    c.cookies.set("nt_session", auth.make_token(uid, "test-secret", sid=auth.new_session_id()))
    assert c.get("/api/auth/me").status_code == 401


def test_database_keeps_only_a_hash_of_the_session_id(env):
    c, _, db = env
    signup(c)
    sid = c.cookies.get("nt_session").split(".")[2]
    stored = [r[0] for r in sqlite3.connect(db).execute("select id_hash from sessions")]
    assert stored == [hashlib.sha256(sid.encode()).hexdigest()]
    assert sid not in stored


def test_account_info(env):
    c, _, _ = env
    assert c.get("/api/me/account").status_code == 401
    signup(c)
    second_device(c)
    d = c.get("/api/me/account").json()
    assert d["email"] == "a@example.com" and d["has_password"] is True and d["google"] is False
    assert d["sessions"] == 2 and d["created_at"].endswith("Z")
    assert "pw_hash" not in d


def test_revoke_other_devices_keeps_this_one(env):
    c, _, _ = env
    signup(c)
    others = [second_device(c), second_device(c)]
    r = c.post("/api/me/sessions/revoke-others")
    assert r.status_code == 200 and r.json() == {"signed_out": 2}
    assert all(o.get("/api/auth/me").status_code == 401 for o in others)
    assert c.get("/api/auth/me").status_code == 200
    assert c.get("/api/me/account").json()["sessions"] == 1


def test_change_password_signs_out_everywhere_else(env):
    c, _, _ = env
    signup(c)
    other = second_device(c)
    before = c.cookies.get("nt_session")
    r = c.post("/api/me/password", json={"current_password": PW, "new_password": NEW_PW})
    assert r.status_code == 200 and r.json() == {"signed_out": 1}
    assert c.cookies.get("nt_session") != before         # เครื่องนี้ได้คุกกี้ใหม่
    assert c.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    stale = TestClient(c.app)
    stale.cookies.set("nt_session", before)               # คุกกี้เดิมของเครื่องนี้ก็ใช้ไม่ได้แล้ว
    assert stale.get("/api/auth/me").status_code == 401
    fresh = TestClient(c.app)
    assert fresh.post("/api/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "a@example.com", "password": NEW_PW}).status_code == 200


@pytest.mark.parametrize("body,code", [
    ({"current_password": "ผิด-ผิด-ผิด", "new_password": NEW_PW}, "wrong_password"),
    ({"current_password": PW, "new_password": "สั้น"}, "invalid_param"),
    ({"current_password": PW, "new_password": "x" * (auth.MAX_PASSWORD + 1)}, "invalid_param"),
    ({"current_password": PW, "new_password": PW}, "invalid_param"),
])
def test_change_password_rejects_bad_input(env, body, code):
    c, _, _ = env
    signup(c)
    r = c.post("/api/me/password", json=body)
    assert r.status_code == 400 and r.json()["code"] == code
    assert c.get("/api/auth/me").status_code == 200       # ไม่โดนออกจากระบบเพราะกรอกผิด
    fresh = TestClient(c.app)
    assert fresh.post("/api/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 200


def test_change_password_needs_login(env):
    c, _, _ = env
    r = c.post("/api/me/password", json={"current_password": PW, "new_password": NEW_PW})
    assert r.status_code == 401


def test_guessing_current_password_is_throttled(tmp_path):
    c, _, _ = make(tmp_path, throttle=auth.LoginThrottle(max_fails=3, window=300))
    signup(c)
    for _ in range(3):
        assert c.post("/api/me/password", json={"current_password": "เดาผิด-123", "new_password": NEW_PW}).status_code == 400
    r = c.post("/api/me/password", json={"current_password": PW, "new_password": NEW_PW})
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"


def test_google_account_has_no_password_to_change(env):
    c, store, _ = env
    u = store.create_google_user("g@example.com", "sub-1")
    sid, exp = auth.new_session_id(), auth.session_expiry()
    store.create_session(u["id"], sid, exp)
    c.cookies.set("nt_session", auth.make_token(u["id"], "test-secret", sid=sid, exp=exp))
    d = c.get("/api/me/account").json()
    assert d["google"] is True and d["has_password"] is False
    r = c.post("/api/me/password", json={"current_password": "google", "new_password": NEW_PW})
    assert r.status_code == 400 and r.json()["code"] == "no_password"


def test_expired_sessions_are_pruned_on_next_login(env):
    c, store, db = env
    signup(c)
    uid = c.get("/api/auth/me").json()["user"]["id"]
    store.create_session(uid, auth.new_session_id(), 1_000)   # หมดอายุไปนานแล้ว
    assert c.get("/api/me/account").json()["sessions"] == 1    # ไม่นับที่หมดอายุ
    second_device(c)
    n = sqlite3.connect(db).execute("select count(*) from sessions where expires_at < 2000").fetchone()[0]
    assert n == 0
