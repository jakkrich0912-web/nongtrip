"""ลบข้อมูลของตัวเองทั้งหมด และลบบัญชี (CONTRACT ข้อ 3.4)"""
import sqlite3

import pytest

from services.api import auth
from services.api.tests.test_accounts import LAT, LON, PW, make, rows, signup

COLLECTIONS = ["/api/me/searches", "/api/me/favorites", "/api/me/chats"]


@pytest.fixture
def env(tmp_path):
    return make(tmp_path)


def fill(c, store, email):
    """สร้างบัญชีพร้อมข้อมูลครบทุกชนิด คืน user id"""
    signup(c, email)
    uid = c.get("/api/auth/me").json()["user"]["id"]
    c.post("/api/me/searches", json={"name": f"ที่พักของ {email}", "lat": LAT, "lon": LON})
    c.post("/api/me/favorites", json={"place_id": "v:p01"})
    cid = store.create_chat(uid, f"แชตของ {email}")
    store.add_message(uid, cid, "user", "สวัสดี")
    store.add_message(uid, cid, "assistant", "สวัสดีครับ")
    return uid


def count(db, table, uid):
    col = "id" if table == "users" else "user_id"
    return sqlite3.connect(db).execute(f"select count(*) from {table} where {col} = ?", (uid,)).fetchone()[0]


# ---------- ลบทั้งหมดทีละชนิด ----------

@pytest.mark.parametrize("path", COLLECTIONS)
def test_delete_all_requires_login(env, path):
    c, _, _ = env
    assert c.delete(path).status_code == 401


def test_delete_account_requires_login(env):
    c, _, db = env
    assert c.post("/api/me/delete", json={"email": "a@example.com"}).status_code == 401
    assert rows(db, "users") == 0


def test_delete_all_searches_only_mine(env):
    c, store, db = env
    a = fill(c, store, "a@example.com")
    c.post("/api/auth/logout")
    b = fill(c, store, "b@example.com")
    assert c.delete("/api/me/searches").status_code == 204
    assert c.get("/api/me/searches").json()["items"] == []
    assert count(db, "searches", a) == 1                      # ของคนอื่นยังอยู่
    assert c.get("/api/me/favorites").json()["items"] and store.list_chats(b)  # ชนิดอื่นของตัวเองยังอยู่


def test_delete_all_favorites_only_mine(env):
    c, store, db = env
    a = fill(c, store, "a@example.com")
    c.post("/api/auth/logout")
    fill(c, store, "b@example.com")
    assert c.delete("/api/me/favorites").status_code == 204
    assert c.get("/api/me/favorites").json()["items"] == []
    assert count(db, "favorites", a) == 1
    assert c.get("/api/me/searches").json()["items"]


def test_delete_all_chats_removes_messages_too(env):
    c, store, db = env
    a = fill(c, store, "a@example.com")
    c.post("/api/auth/logout")
    b = fill(c, store, "b@example.com")
    before = rows(db, "chat_messages")
    assert c.delete("/api/me/chats").status_code == 204
    assert c.get("/api/me/chats").json()["items"] == []
    assert rows(db, "chat_messages") == before - 2            # หายแค่ของ b
    assert store.list_chats(a)[0]["message_count"] == 2
    assert c.delete("/api/me/chats").status_code == 204       # ลบซ้ำได้ ไม่ error


def test_item_delete_routes_still_work(env):
    c, store, _ = env
    fill(c, store, "a@example.com")
    sid = c.get("/api/me/searches").json()["items"][0]["id"]
    assert c.delete(f"/api/me/searches/{sid}").status_code == 204
    assert c.get("/api/me/searches").json()["items"] == []
    assert c.delete("/api/me/favorites/v:p01").status_code == 204
    assert c.get("/api/me/favorites").json()["items"] == []


# ---------- ลบบัญชี ----------

def test_delete_account_wrong_email_changes_nothing(env):
    c, store, db = env
    uid = fill(c, store, "a@example.com")
    r = c.post("/api/me/delete", json={"email": "other@example.com"})
    assert r.status_code == 400 and r.json()["code"] == "invalid_param"
    assert c.get("/api/auth/me").status_code == 200
    assert count(db, "users", uid) == 1 and count(db, "searches", uid) == 1


def test_delete_account_missing_body_is_400(env):
    c, store, db = env
    uid = fill(c, store, "a@example.com")
    assert c.post("/api/me/delete").status_code == 400
    assert c.post("/api/me/delete", json={}).status_code == 400
    assert count(db, "users", uid) == 1


def test_delete_account_removes_everything_and_clears_session(env):
    c, store, db = env
    a = fill(c, store, "a@example.com")
    c.post("/api/auth/logout")
    b = fill(c, store, "b@example.com")
    c.post("/api/auth/logout")
    c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    r = c.post("/api/me/delete", json={"email": "  A@Example.COM "})   # ไม่สนตัวพิมพ์และช่องว่าง
    assert r.status_code == 204
    assert "nt_session" in r.headers.get("set-cookie", "") and "Max-Age=0" in r.headers["set-cookie"]
    assert c.get("/api/auth/me").status_code == 401
    for t in ("users", "sessions", "searches", "favorites", "chats"):
        assert count(db, t, a) == 0, t
    assert rows(db, "chat_messages") == 2                      # เหลือแต่ของ b
    assert count(db, "users", b) == 1 and count(db, "searches", b) == 1 and count(db, "favorites", b) == 1


def test_deleted_user_cannot_login_and_cookie_is_dead(env):
    c, store, _ = env
    uid = fill(c, store, "a@example.com")
    old = c.cookies.get("nt_session")
    assert c.post("/api/me/delete", json={"email": "a@example.com"}).status_code == 204
    assert c.post("/api/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 401
    c.cookies.set("nt_session", old)                            # คุกกี้เก่ายังไม่หมดอายุ แต่ผู้ใช้ไม่มีแล้ว
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/me/searches").status_code == 401


def test_email_can_register_again_after_delete(env):
    c, store, _ = env
    fill(c, store, "a@example.com")
    c.post("/api/me/delete", json={"email": "a@example.com"})
    signup(c, "a@example.com")
    assert c.get("/api/me/searches").json()["items"] == []     # บัญชีใหม่ ไม่มีข้อมูลเก่าตกค้าง


def test_google_account_can_delete(env):
    c, store, db = env
    u = store.create_google_user("g@example.com", "sub-123")
    sid, exp = auth.new_session_id(), auth.session_expiry()
    store.create_session(u["id"], sid, exp)
    c.cookies.set("nt_session", auth.make_token(u["id"], "test-secret", sid=sid, exp=exp))
    assert c.post("/api/me/delete", json={"email": "g@example.com"}).status_code == 204
    assert store.user_by_google_sub("sub-123") is None
    assert count(db, "users", u["id"]) == 0
