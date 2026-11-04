"""ล็อกอินด้วย Google (POST /api/auth/google): ตรวจ token, ผูกบัญชี, ปิดทางยึดบัญชี"""
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from services.api import auth
from services.api.google import GoogleVerifier
from services.api.main import create_app
from services.api.store import Store
from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.snapshot import Snapshot
from services.places.tests.helpers import FakeHttp

CID = "client-123.apps.googleusercontent.com"
NOW = 1_800_000_000


def claims(**over):
    d = {"aud": CID, "iss": "https://accounts.google.com", "sub": "sub-1", "email": "Guest@Example.com",
         "email_verified": "true", "exp": str(NOW + 3000)}
    d.update(over)
    return d


class Google:
    """ตัวแทน tokeninfo ของ Google: คืนค่าที่ตั้งไว้ และนับจำนวนครั้งที่ถูกเรียก"""

    def __init__(self, status=200, body=None, error=None):
        self.status, self.body, self.error, self.calls = status, claims() if body is None else body, error, []

    def __call__(self, req: httpx.Request):
        self.calls.append(dict(req.url.params))
        if self.error:
            raise self.error
        return httpx.Response(self.status, json=self.body)


def make(tmp_path, g: Google, client_id=CID, throttle_client=None):
    http = httpx.Client(transport=httpx.MockTransport(g))
    verifier = GoogleVerifier(client_id, http=http, clock=lambda: NOW)
    svc = PlacesService(http=FakeHttp(), cache=TTLCache(None), verified=[], osm_live=True, snapshot=Snapshot(None))
    store = Store(tmp_path / "g.db")
    app = create_app(svc, store=store, session_secret="s", secure_cookie=False, google=verifier)
    return TestClient(app), store, tmp_path / "g.db"


def users(db):
    if not db.exists():
        return 0
    return sqlite3.connect(db).execute("select count(*) from users").fetchone()[0]


def go(c, cred="tok"):
    return c.post("/api/auth/google", json={"credential": cred})


def test_not_configured_is_501_and_stores_nothing(tmp_path):
    g = Google()
    c, _, db = make(tmp_path, g, client_id="")
    r = go(c)
    assert r.status_code == 501 and r.json()["code"] == "google_not_configured"
    assert g.calls == [] and users(db) == 0


def test_new_google_user_is_created_and_logged_in(tmp_path):
    g = Google()
    c, _, db = make(tmp_path, g)
    r = go(c, "my-id-token")
    assert r.status_code == 201
    assert r.json() == {"user": {"id": 1, "email": "guest@example.com", "is_admin": False}}
    assert g.calls == [{"id_token": "my-id-token"}]
    assert "pw_hash" not in r.text and "sub-1" not in r.text
    assert c.get("/api/auth/me").json()["user"]["email"] == "guest@example.com"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_same_google_account_logs_into_same_user(tmp_path):
    c, _, db = make(tmp_path, Google())
    first = go(c).json()["user"]["id"]
    c.post("/api/auth/logout")
    r = go(c)
    assert r.status_code == 200 and r.json()["user"]["id"] == first
    assert users(db) == 1


def test_same_sub_with_changed_email_still_same_user(tmp_path):
    g = Google()
    c, _, db = make(tmp_path, g)
    first = go(c).json()["user"]["id"]
    g.body = claims(email="new-address@example.com")
    r = go(c)
    assert r.status_code == 200 and r.json()["user"]["id"] == first and users(db) == 1


@pytest.mark.parametrize("over", [
    {"aud": "someone-elses-app"},
    {"iss": "https://evil.example.com"},
    {"exp": str(NOW - 1)},
    {"exp": "not-a-number"},
    {"exp": None},
    {"email_verified": "false"},
    {"email_verified": None},
    {"email": ""},
    {"sub": ""},
])
def test_bad_claims_are_rejected_without_creating_user(tmp_path, over):
    c, _, db = make(tmp_path, Google(body=claims(**over)))
    r = go(c)
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    assert "set-cookie" not in r.headers and users(db) == 0


def test_accepts_both_google_issuer_spellings_and_boolean_verified(tmp_path):
    c, _, _ = make(tmp_path, Google(body=claims(iss="accounts.google.com", email_verified=True)))
    assert go(c).status_code == 201


def test_non_object_json_is_rejected(tmp_path):
    c, _, db = make(tmp_path, Google(body=["x"]))
    assert go(c).status_code == 401 and users(db) == 0


def test_google_rejecting_token_is_401(tmp_path):
    c, _, db = make(tmp_path, Google(status=400, body={"error": "invalid_token"}))
    assert go(c).status_code == 401 and users(db) == 0


@pytest.mark.parametrize("g", [Google(status=500, body={}), Google(error=httpx.ConnectTimeout("slow"))])
def test_google_down_is_502(tmp_path, g):
    c, _, db = make(tmp_path, g)
    r = go(c)
    assert r.status_code == 502 and r.json()["code"] == "upstream_unavailable"
    assert users(db) == 0


def test_existing_password_account_is_not_taken_over(tmp_path):
    c, store, db = make(tmp_path, Google())
    victim = store.create_user("guest@example.com", auth.hash_password("รหัสผ่านของเจ้าของ-1"))
    r = go(c)
    assert r.status_code == 409 and r.json()["code"] == "email_taken"
    assert "set-cookie" not in r.headers and c.get("/api/auth/me").status_code == 401
    row = sqlite3.connect(db).execute("select id, google_sub, pw_hash from users").fetchall()
    assert len(row) == 1 and row[0][0] == victim["id"] and row[0][1] is None and row[0][2].startswith("scrypt$")


def test_google_user_cannot_login_with_any_password(tmp_path):
    c, _, _ = make(tmp_path, Google())
    go(c)
    c.post("/api/auth/logout")
    for pw in ["google", "", "รหัสผ่านอะไรก็ได้-123", "x" * 50]:
        r = c.post("/api/auth/login", json={"email": "guest@example.com", "password": pw})
        assert r.status_code == 401, pw
    assert c.get("/api/auth/me").status_code == 401


def test_cannot_register_over_a_google_email(tmp_path):
    c, _, db = make(tmp_path, Google())
    go(c)
    r = c.post("/api/auth/register", json={"email": "guest@example.com", "password": "รหัสผ่านยาวพอ-123"})
    assert r.status_code == 409 and users(db) == 1


@pytest.mark.parametrize("body", [{}, {"credential": ""}, {"credential": "x" * 5001}, {"credential": 5}])
def test_bad_request_body_is_400_and_never_calls_google(tmp_path, body):
    g = Google()
    c, _, _ = make(tmp_path, g)
    assert c.post("/api/auth/google", json=body).status_code == 400
    assert g.calls == []


def test_oversize_credential_within_body_limit_is_rejected_before_google(tmp_path):
    g = Google()
    c, _, _ = make(tmp_path, g)
    assert go(c, "x" * 4097).status_code == 401 and g.calls == []


def test_throttle_stops_hammering_google(tmp_path):
    g = Google(status=400, body={})
    c, _, _ = make(tmp_path, g)
    codes = [go(c).status_code for _ in range(35)]
    assert codes[:30] == [401] * 30 and codes[30:] == [429] * 5
    assert len(g.calls) == 30


def test_old_database_without_google_column_is_migrated(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE,
        pw_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        INSERT INTO users(email, pw_hash, created_at) VALUES ('old@example.com', 'scrypt$x', '2026-11-01T00:00:00Z');""")
    con.commit()
    con.close()
    http = httpx.Client(transport=httpx.MockTransport(Google()))
    svc = PlacesService(http=FakeHttp(), cache=TTLCache(None), verified=[], osm_live=True, snapshot=Snapshot(None))
    app = create_app(svc, store=Store(db), session_secret="s", secure_cookie=False,
                     google=GoogleVerifier(CID, http=http, clock=lambda: NOW))
    c = TestClient(app)
    assert go(c).status_code == 201
    emails = [r[0] for r in sqlite3.connect(db).execute("select email from users order by id")]
    assert emails == ["old@example.com", "guest@example.com"]
    Store(db).user_by_email("old@example.com")  # เปิดซ้ำได้ ไม่พังเพราะมีคอลัมน์อยู่แล้ว


def test_verifier_reads_client_id_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "  from-env  ")
    assert GoogleVerifier().client_id == "from-env" and GoogleVerifier().configured
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    assert not GoogleVerifier().configured
