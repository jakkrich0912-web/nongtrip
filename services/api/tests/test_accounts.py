import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from services.api import auth
from services.api.main import create_app
from services.api.store import MAX_SEARCHES, Store
from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.models import Candidate
from services.places.snapshot import Snapshot
from services.places.tests.helpers import CM, FakeHttp

LAT, LON = CM
PW = "รหัสผ่านยาวพอ-123"
VERIFIED = [Candidate(id="v:p01", name_th="วัดพระธาตุดอยสุเทพ", name_en="Wat Phra That Doi Suthep", kind="attraction",
                      subtype="temple", lat=18.80498, lon=98.92156, source="verified", province="เชียงใหม่")]


def make(tmp_path, throttle=None):
    svc = PlacesService(http=FakeHttp(), cache=TTLCache(None), verified=VERIFIED, osm_live=True, snapshot=Snapshot(None))
    store = Store(tmp_path / "t.db")
    app = create_app(svc, store=store, session_secret="test-secret", secure_cookie=False, throttle=throttle)
    return TestClient(app), store, tmp_path / "t.db"


def rows(db, table):
    """จำนวนแถว (ยังไม่เคยเปิดฐานข้อมูลเลย = ไม่มีอะไรถูกบันทึก = 0)"""
    if not db.exists():
        return 0
    try:
        return sqlite3.connect(db).execute(f"select count(*) from {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


@pytest.fixture
def env(tmp_path):
    return make(tmp_path)


def signup(c, email="a@example.com", pw=PW):
    r = c.post("/api/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    return r


# ---------- ผู้ใช้ ----------

def test_register_logs_in_and_me_works(env):
    c, _, _ = env
    r = signup(c, "  A@Example.COM ")
    assert r.json()["user"]["email"] == "a@example.com"
    assert "pw_hash" not in r.text and "password" not in r.text
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["user"]["email"] == "a@example.com"


def test_cookie_flags(tmp_path):
    svc = PlacesService(http=FakeHttp(), cache=TTLCache(None), verified=[], snapshot=Snapshot(None))
    c = TestClient(create_app(svc, store=Store(tmp_path / "x.db"), session_secret="s", secure_cookie=True))
    r = c.post("/api/auth/register", json={"email": "a@example.com", "password": PW})
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "secure" in sc and "samesite=lax" in sc


def test_register_validation(env):
    c, _, _ = env
    assert c.post("/api/auth/register", json={"email": "ไม่ใช่อีเมล", "password": PW}).status_code == 400
    r = c.post("/api/auth/register", json={"email": "a@example.com", "password": "short"})
    assert r.status_code == 400 and r.json()["code"] == "invalid_param"
    assert c.post("/api/auth/register", json={"email": "a@example.com"}).status_code == 400
    assert c.post("/api/auth/register", json={"email": "a@example.com", "password": "x" * 201}).status_code == 400


def test_duplicate_email_is_409_case_insensitive(env):
    c, _, _ = env
    signup(c, "a@example.com")
    r = c.post("/api/auth/register", json={"email": "A@EXAMPLE.com", "password": PW})
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


def test_password_is_hashed_not_stored_plain(env):
    c, _, db = env
    signup(c)
    row = sqlite3.connect(db).execute("select pw_hash from users").fetchone()[0]
    assert PW not in row and row.startswith("scrypt$")
    assert auth.verify_password(PW, row) and not auth.verify_password("ผิด", row)


def test_two_users_same_password_get_different_hashes(env):
    c, _, db = env
    signup(c, "a@example.com")
    signup(c, "b@example.com")
    hs = [r[0] for r in sqlite3.connect(db).execute("select pw_hash from users")]
    assert hs[0] != hs[1]


def test_login_ok_and_wrong_password_and_unknown_email_look_the_same(env):
    c, _, _ = env
    signup(c)
    c.post("/api/auth/logout")
    ok = c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert ok.status_code == 200 and c.get("/api/auth/me").status_code == 200
    c.post("/api/auth/logout")
    wrong = c.post("/api/auth/login", json={"email": "a@example.com", "password": "ผิดนะ-12345"})
    nouser = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "ผิดนะ-12345"})
    assert wrong.status_code == nouser.status_code == 401
    assert wrong.json() == nouser.json()


def test_logout_clears_session(env):
    c, _, _ = env
    signup(c)
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401


def test_me_without_cookie_is_401(env):
    c, _, _ = env
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"


def test_tampered_and_expired_tokens_rejected(env):
    c, _, _ = env
    signup(c)
    good = c.cookies.get("nt_session")
    uid, exp, sig = good.split(".")
    c.cookies.clear()
    c.cookies.set("nt_session", f"2.{exp}.{sig}")          # สวมรอยผู้ใช้อื่น
    assert c.get("/api/auth/me").status_code == 401
    c.cookies.clear()
    c.cookies.set("nt_session", f"{uid}.{exp}.{'0' * 64}")  # ลายเซ็นมั่ว
    assert c.get("/api/auth/me").status_code == 401
    c.cookies.clear()
    c.cookies.set("nt_session", "garbage")
    assert c.get("/api/auth/me").status_code == 401
    old = auth.make_token(int(uid), "test-secret", now=1_000_000)  # หมดอายุแล้ว
    c.cookies.clear()
    c.cookies.set("nt_session", old)
    assert c.get("/api/auth/me").status_code == 401


def test_token_signed_with_other_secret_rejected(env):
    c, _, _ = env
    signup(c)
    uid = int(c.cookies.get("nt_session").split(".")[0])
    c.cookies.clear()
    c.cookies.set("nt_session", auth.make_token(uid, "other-secret"))
    assert c.get("/api/auth/me").status_code == 401


def test_login_throttle_blocks_after_5_fails_then_resets_on_time(tmp_path):
    th = auth.LoginThrottle(max_fails=3, window=300)
    c, _, _ = make(tmp_path, throttle=th)
    signup(c)
    c.post("/api/auth/logout")
    for _ in range(3):
        assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "ผิดนะ-12345"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})  # ถูกก็ยังโดนบล็อก
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"
    assert th.blocked("a@example.com", now=10 ** 12) is False  # เลยเวลาแล้วปลดเอง


# ---------- ไม่ล็อกอิน = ไม่บันทึกอะไร ----------

@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/me/searches", None), ("post", "/api/me/searches", {"name": "x", "lat": LAT, "lon": LON}),
    ("delete", "/api/me/searches/1", None), ("get", "/api/me/favorites", None),
    ("post", "/api/me/favorites", {"place_id": "v:p01"}), ("delete", "/api/me/favorites/v:p01", None),
    ("get", "/api/me/chats", None), ("get", "/api/me/chats/1", None), ("delete", "/api/me/chats/1", None),
])
def test_everything_under_me_needs_login_and_writes_nothing(env, method, path, body):
    c, _, db = env
    r = getattr(c, method)(path, **({"json": body} if body else {}))
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    for t in ("users", "searches", "favorites", "chats", "chat_messages"):
        assert rows(db, t) == 0


def test_search_endpoints_do_not_save_anything_for_anonymous(env):
    c, _, db = env
    c.get("/api/places/nearby", params={"lat": LAT, "lon": LON})
    c.get("/api/lodgings/search", params={"q": "ที่พัก"})
    for t in ("users", "searches", "favorites", "chats", "chat_messages"):
        assert rows(db, t) == 0


# ---------- ประวัติที่พัก ----------

def test_searches_add_list_newest_first_and_dedupe(env):
    c, _, _ = env
    signup(c)
    c.post("/api/me/searches", json={"name": "โรงแรม ก", "lat": LAT, "lon": LON})
    c.post("/api/me/searches", json={"name": "โรงแรม ข", "lat": LAT + 0.1, "lon": LON})
    c.post("/api/me/searches", json={"name": "โรงแรม ก", "lat": LAT, "lon": LON})  # ค้นซ้ำ: ยกขึ้นบน
    items = c.get("/api/me/searches").json()["items"]
    assert [i["name"] for i in items] == ["โรงแรม ก", "โรงแรม ข"]


def test_searches_validation_and_cap(env):
    c, _, _ = env
    signup(c)
    assert c.post("/api/me/searches", json={"name": "ญี่ปุ่น", "lat": 35.6, "lon": 139.7}).status_code == 400
    assert c.post("/api/me/searches", json={"name": "   ", "lat": LAT, "lon": LON}).status_code == 400
    assert c.post("/api/me/searches", json={"lat": LAT, "lon": LON}).status_code == 400
    for i in range(MAX_SEARCHES + 5):
        c.post("/api/me/searches", json={"name": f"ที่พัก {i}", "lat": LAT, "lon": LON})
    items = c.get("/api/me/searches").json()["items"]
    assert len(items) == MAX_SEARCHES and items[0]["name"] == f"ที่พัก {MAX_SEARCHES + 4}"


def test_delete_search_only_own(env):
    c, store, _ = env
    signup(c, "a@example.com")
    sid = c.post("/api/me/searches", json={"name": "ของ A", "lat": LAT, "lon": LON}).json()["id"]
    c.post("/api/auth/logout")
    signup(c, "b@example.com")
    c.delete(f"/api/me/searches/{sid}")  # B ลบของ A ไม่ได้ (ตอบ 204 แต่ไม่ลบ)
    assert len(store.list_searches(1)) == 1
    assert c.get("/api/me/searches").json()["items"] == []  # B ไม่เห็นของ A
    c.post("/api/auth/logout")
    c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert c.delete(f"/api/me/searches/{sid}").status_code == 204
    assert c.get("/api/me/searches").json()["items"] == []


# ---------- สถานที่โปรด ----------

def test_favorite_verified_uses_server_data_not_client_values(env):
    c, _, _ = env
    signup(c)
    r = c.post("/api/me/favorites", json={"place_id": "v:p01", "name_th": "ชื่อที่ไคลเอนต์แกล้งส่ง", "lat": 1, "lon": 1})
    j = r.json()
    assert r.status_code == 201 and j["name_th"] == "วัดพระธาตุดอยสุเทพ" and j["source"] == "verified"
    assert (j["lat"], j["lon"]) == (18.80498, 98.92156)
    assert j["maps_url"].startswith("https://www.google.com/maps/search/")


def test_favorite_unknown_verified_id_is_400(env):
    c, _, _ = env
    signup(c)
    assert c.post("/api/me/favorites", json={"place_id": "v:ไม่มีจริง"}).status_code == 400


def test_favorite_osm_requires_fields_and_valid_kind(env):
    c, _, _ = env
    signup(c)
    pid = "osm:node/12345"
    assert c.post("/api/me/favorites", json={"place_id": pid}).status_code == 400
    assert c.post("/api/me/favorites", json={"place_id": pid, "name_th": "คาเฟ่", "lat": LAT, "lon": LON,
                                             "kind": "lodging"}).status_code == 400
    assert c.post("/api/me/favorites", json={"place_id": pid, "name_th": "คาเฟ่", "lat": 35.6, "lon": 139.7,
                                             "kind": "cafe"}).status_code == 400
    ok = c.post("/api/me/favorites", json={"place_id": pid, "name_th": "คาเฟ่", "lat": LAT, "lon": LON, "kind": "cafe"})
    assert ok.status_code == 201 and ok.json()["source"] == "osm"


def test_favorite_bad_ids_rejected(env):
    c, _, _ = env
    signup(c)
    for pid in ("p01", "osm:foo/1", "osm:node/abc", "http://evil", "osm:node/1; drop table users"):
        assert c.post("/api/me/favorites", json={"place_id": pid, "name_th": "x", "lat": LAT, "lon": LON,
                                                 "kind": "cafe"}).status_code == 400


def test_favorite_idempotent_list_and_delete_with_slash_in_id(env):
    c, _, _ = env
    signup(c)
    body = {"place_id": "osm:node/777", "name_th": "ร้านกาแฟ", "lat": LAT, "lon": LON, "kind": "cafe"}
    assert c.post("/api/me/favorites", json=body).status_code == 201
    assert c.post("/api/me/favorites", json=body).status_code == 200  # ซ้ำ ไม่เกิดรายการใหม่
    c.post("/api/me/favorites", json={"place_id": "v:p01"})
    items = c.get("/api/me/favorites").json()["items"]
    assert [i["id"] for i in items] == ["v:p01", "osm:node/777"]
    assert c.delete("/api/me/favorites/osm:node/777").status_code == 204
    assert [i["id"] for i in c.get("/api/me/favorites").json()["items"]] == ["v:p01"]


def test_favorites_are_private_per_user(env):
    c, _, _ = env
    signup(c, "a@example.com")
    c.post("/api/me/favorites", json={"place_id": "v:p01"})
    c.post("/api/auth/logout")
    signup(c, "b@example.com")
    assert c.get("/api/me/favorites").json()["items"] == []
    c.delete("/api/me/favorites/v:p01")
    c.post("/api/auth/logout")
    c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert len(c.get("/api/me/favorites").json()["items"]) == 1


def test_no_money_rating_or_review_fields_anywhere(env):
    c, _, _ = env
    signup(c)
    c.post("/api/me/favorites", json={"place_id": "v:p01", "price": 100, "rating": 5, "cost_thb": 50})
    c.post("/api/me/searches", json={"name": "ที่พัก", "lat": LAT, "lon": LON, "price": 999})
    blob = c.get("/api/me/favorites").text + c.get("/api/me/searches").text
    assert not re.search(r"price|cost|rating|review|score|baht|thb", blob, re.I)


# ---------- แชต ----------

def test_chats_list_get_delete_and_privacy(env):
    c, store, _ = env
    signup(c, "a@example.com")
    uid = c.get("/api/auth/me").json()["user"]["id"]
    cid = store.create_chat(uid, "หาคาเฟ่แถวนิมมาน")
    store.add_message(uid, cid, "user", "ขอคาเฟ่ใกล้ที่พัก")
    store.add_message(uid, cid, "assistant", "นี่คือคาเฟ่ใกล้ที่สุด")
    lst = c.get("/api/me/chats").json()["items"]
    assert lst[0]["title"] == "หาคาเฟ่แถวนิมมาน" and lst[0]["message_count"] == 2
    full = c.get(f"/api/me/chats/{cid}").json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant"]
    c.post("/api/auth/logout")
    signup(c, "b@example.com")
    assert c.get(f"/api/me/chats/{cid}").status_code == 404   # ของคนอื่น = ไม่พบ
    assert c.get("/api/me/chats").json()["items"] == []
    c.delete(f"/api/me/chats/{cid}")                           # ลบของคนอื่นไม่ได้
    assert store.get_chat(uid, cid) is not None
    c.post("/api/auth/logout")
    c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert c.delete(f"/api/me/chats/{cid}").status_code == 204
    assert c.get(f"/api/me/chats/{cid}").status_code == 404


def test_add_message_to_someone_elses_chat_refused(env):
    c, store, _ = env
    signup(c, "a@example.com")
    cid = store.create_chat(1, "แชตของ A")
    signup(c, "b@example.com")
    assert store.add_message(2, cid, "user", "แอบเพิ่ม") is False


def test_bad_params_still_400_thai(env):
    c, _, _ = env
    signup(c)
    r = c.get("/api/me/chats/abc")
    assert r.status_code == 400 and "พารามิเตอร์ไม่ถูกต้อง" in r.json()["error"]


def test_non_ascii_cookie_is_just_not_logged_in(env):
    """คุกกี้แปลกๆ จากผู้โจมตีต้องได้ 401 ไม่ใช่ 500"""
    c, _, _ = env
    r = c.get("/api/auth/me", headers={"cookie": "nt_session=1.99999999999.éé".encode("latin-1")})
    assert r.status_code == 401
    assert auth.read_token("1.99999999999.é", "s") is None


@pytest.mark.parametrize("path", ["/api/me/chats/{}", "/api/me/searches/{}"])
@pytest.mark.parametrize("bad", ["99999999999999999999999", "0", "-5"])
def test_out_of_range_ids_are_400_not_500(env, path, bad):
    c, _, _ = env
    signup(c)
    for method in ("get", "delete"):
        if method == "get" and "searches" in path:
            continue  # ไม่มี GET รายตัวของประวัติค้น
        r = getattr(c, method)(path.format(bad))
        assert r.status_code == 400, (method, path, bad, r.status_code)
        assert "พารามิเตอร์ไม่ถูกต้อง" in r.json()["error"]


def test_register_is_rate_limited_per_ip(tmp_path):
    from services.api.accounts import REGISTER_PER_HOUR
    c, store, _ = make(tmp_path)
    for i in range(REGISTER_PER_HOUR):
        assert c.post("/api/auth/register", json={"email": f"u{i}@example.com", "password": PW}).status_code == 201
    r = c.post("/api/auth/register", json={"email": "one-more@example.com", "password": PW})
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"
    assert store.user_by_email("one-more@example.com") is None
