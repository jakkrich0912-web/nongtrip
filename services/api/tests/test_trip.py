from fastapi.testclient import TestClient

from services.api.chat import ChatThrottle
from services.api.main import create_app
from services.api.store import Store
from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.snapshot import Snapshot
from services.places.tests.helpers import CM, FakeHttp, el

LAT, LON = CM
PW = "รหัสผ่านยาวพอ-123"


def up(km):
    return LAT + km / 111.19


def make(tmp_path, overpass=None):
    http = FakeHttp(overpass=overpass or [el(7, "คาเฟ่ใกล้ที่พัก", up(1), LON, {"amenity": "cafe"})])
    svc = PlacesService(http=http, cache=TTLCache(None), verified=[], osm_live=True, snapshot=Snapshot(None))
    app = create_app(svc, store=Store(tmp_path / "t.db"), session_secret="s", secure_cookie=False,
                     chat_throttle=ChatThrottle(limit=1000))
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"email": "a@example.com", "password": PW}).status_code == 201
    return c


def fav(c, pid, name, km, kind="attraction", subtype="attraction"):
    body = {"place_id": pid, "name_th": name, "kind": kind, "subtype": subtype, "lat": up(km), "lon": LON}
    assert c.post("/api/me/favorites", json=body).status_code in (200, 201)


def ask(c, q, **kw):
    return c.post("/api/me/trip/ask", json={"question": q, **kw})


def test_trip_ask_needs_login_and_handles_empty_trip(tmp_path):
    c = make(tmp_path)
    assert TestClient(c.app).post("/api/me/trip/ask", json={"question": "x"}).status_code == 401
    r = ask(c, "ทริปนี้ขาดคาเฟ่ไหม").json()
    assert "ทริปยังว่าง" in r["answer"] and r["places"] is None and r["mode"] == "rule"


def test_missing_cafe_searches_around_latest_stay(tmp_path):
    c = make(tmp_path)
    c.post("/api/me/searches", json={"name": "ที่พักทดสอบ", "lat": LAT, "lon": LON})
    fav(c, "osm:node/1", "น้ำตกหนึ่ง", 3, subtype="waterfall")
    r = ask(c, "ทริปนี้ขาดคาเฟ่ไหม").json()
    assert "ยังไม่มีคาเฟ่" in r["answer"] and "(เส้นตรง)" in r["answer"]
    assert [p["name_th"] for p in r["places"]["items"]] == ["คาเฟ่ใกล้ที่พัก"] and r["stay"]["name"] == "ที่พักทดสอบ"
    assert "ดีที่สุด" not in r["answer"]


def test_groups_order_and_subject(tmp_path):
    c = make(tmp_path)
    c.post("/api/me/searches", json={"name": "ที่พักทดสอบ", "lat": LAT, "lon": LON})
    fav(c, "osm:node/1", "ไกล", 12)
    fav(c, "osm:node/2", "ใกล้", 1, subtype="viewpoint")
    fav(c, "osm:node/3", "ใกล้ด้วย", 2.5, kind="cafe", subtype="cafe")
    groups = ask(c, "จุดไหนอยู่ใกล้กันบ้าง").json()["answer"]
    assert "กลุ่ม 2 แห่ง" in groups and "ใกล้" in groups and "ไกล," not in groups
    order = ask(c, "ไปที่ไหนก่อนดี").json()["answer"].splitlines()
    assert order[1].startswith("1. ใกล้ ห่าง") and order[3].startswith("3. ไกล")
    assert "มีจุดชมวิว 1 แห่ง" in ask(c, "มีจุดชมวิวไหม").json()["answer"]
    summary = ask(c, "สรุปทริปหน่อย").json()["answer"]
    assert "ที่เที่ยว 2 คาเฟ่ 1" in summary
    assert ask(c, "x", stay_id=999).status_code == 404
