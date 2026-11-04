from fastapi.testclient import TestClient

from services.api.chat import ChatThrottle
from services.api.main import create_app
from services.api.store import Store
from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.models import Candidate
from services.places.snapshot import Snapshot
from services.places.tests.helpers import FakeHttp

PW = "รหัสผ่านยาวพอ-123"
VERIFIED = [Candidate(id="v:p01", name_th="วัดพระธาตุดอยสุเทพ", name_en=None, kind="attraction", subtype="temple",
                      lat=18.80498, lon=98.92156, source="verified", province="เชียงใหม่")]


def make(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    svc = PlacesService(http=FakeHttp(), cache=TTLCache(None), verified=VERIFIED, osm_live=False, snapshot=Snapshot(None))
    store = Store(tmp_path / "t.db")
    app = create_app(svc, store=store, session_secret="s", secure_cookie=False, chat_throttle=ChatThrottle(limit=1000))
    return TestClient(app), store


def login(c, email):
    assert c.post("/api/auth/register", json={"email": email, "password": PW}).status_code == 201


def test_anyone_can_report_and_verified_name_comes_from_our_data(tmp_path, monkeypatch):
    c, store = make(tmp_path, monkeypatch)
    r = c.post("/api/reports", json={"place_id": "v:p01", "place_name": "ชื่อปลอม", "reason": "closed", "note": " ปิด\nแล้ว "})
    assert r.status_code == 201
    row = store.list_reports()[0]
    assert row["place_name"] == "วัดพระธาตุดอยสุเทพ" and row["note"] == "ปิด แล้ว" and "user_id" not in row and "ip" not in row
    assert c.post("/api/reports", json={"place_id": "osm:node/5", "place_name": "คาเฟ่", "reason": "wrong_location"}).status_code == 201


def test_report_validation(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch)
    assert c.post("/api/reports", json={"place_id": "v:nope", "reason": "closed"}).status_code == 400
    assert c.post("/api/reports", json={"place_id": "osm:node/5", "reason": "closed"}).status_code == 400
    assert c.post("/api/reports", json={"place_id": "http://x", "place_name": "x", "reason": "closed"}).status_code == 400
    assert c.post("/api/reports", json={"place_id": "v:p01", "reason": "price"}).status_code == 400
    assert c.post("/api/reports", json={"place_id": "v:p01", "reason": "other", "note": "ก" * 301}).status_code == 400


def test_report_rate_limit(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch)
    codes = [c.post("/api/reports", json={"place_id": "v:p01", "reason": "closed"}).status_code for _ in range(6)]
    assert codes == [201] * 5 + [429]


def test_only_admin_lists_and_resolves(tmp_path, monkeypatch):
    c, store = make(tmp_path, monkeypatch)
    c.post("/api/reports", json={"place_id": "v:p01", "reason": "wrong_type"})
    assert c.get("/api/admin/reports").status_code == 401
    login(c, "user@example.com")
    assert c.get("/api/admin/reports").status_code == 403
    c.post("/api/auth/logout")
    login(c, "admin@example.com")
    data = c.get("/api/admin/reports").json()
    assert data["total"] == 1 and data["items"][0]["reason"] == "wrong_type"
    rid = data["items"][0]["id"]
    assert c.delete(f"/api/admin/reports/{rid}").status_code == 204
    assert c.delete(f"/api/admin/reports/{rid}").status_code == 404
    assert store.count_reports() == 0
