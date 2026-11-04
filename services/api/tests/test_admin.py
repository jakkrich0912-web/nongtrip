"""แดชบอร์ดผู้ดูแล: สิทธิ์ ตัวนับรวม และไม่มีข้อมูลรายคน (CONTRACT ข้อ 3.6)"""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from services.api import metrics
from services.api.admin import summarize
from services.api.tests.test_accounts import LAT, LON, make, signup

ADMIN = "boss@example.com"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", f" {ADMIN.upper()} , other@example.com")
    return make(tmp_path)


def test_overview_needs_login_and_admin(env):
    c, _, _ = env
    assert c.get("/api/admin/overview").status_code == 401
    signup(c, "user@example.com")
    r = c.get("/api/admin/overview")
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    assert c.get("/api/auth/me").json()["user"]["is_admin"] is False


def test_admin_flag_follows_admin_emails_case_insensitively(env):
    c, _, _ = env
    r = signup(c, ADMIN)
    assert r.json()["user"]["is_admin"] is True
    assert c.get("/api/auth/me").json()["user"]["is_admin"] is True
    assert c.get("/api/admin/overview").status_code == 200


def test_no_admin_emails_means_nobody_is_admin(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    c, _, _ = make(tmp_path)
    signup(c, ADMIN)
    assert c.get("/api/admin/overview").status_code == 403


def test_counts_searches_province_views_and_chat_modes(env):
    c, _, _ = env
    signup(c, ADMIN)
    assert c.get(f"/api/places/nearby?lat={LAT}&lon={LON}").status_code == 200
    c.get(f"/api/places/nearby?lat={LAT}&lon={LON}&offset=50")           # โหลดเพิ่ม ไม่นับซ้ำ
    c.get("/api/provinces/เชียงใหม่/places")
    c.get("/api/provinces/เชียงใหม่/places?offset=50")                     # หน้าถัดไป ไม่นับซ้ำ
    with c.stream("POST", "/api/chat", json={"message": "ที่เที่ยวในเชียงใหม่"}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())
    d = c.get("/api/admin/overview").json()
    u = d["usage"]
    assert u["search_total"] == 1
    assert u["top_provinces"] == [{"key": "เชียงใหม่", "n": 1}]
    assert u["top_province_pages"] == [{"key": "เชียงใหม่", "n": 1}]
    assert u["chat_total"] == 1 and sum(u["chat_modes"].values()) == 1
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert u["daily"][-1]["day"] == today and u["daily"][-1]["search"] == 1 and u["daily"][-1]["chat"] == 1
    assert len(u["daily"]) == 14


def test_overview_totals_and_coverage(env):
    c, _, _ = env
    signup(c, "user@example.com")
    c.post("/api/me/searches", json={"name": "ที่พัก", "lat": LAT, "lon": LON})
    signup(c, ADMIN)
    d = c.get("/api/admin/overview").json()
    assert d["users"]["users"] == 2 and d["users"]["users_new"] == 2
    assert d["content"]["saved_searches"] == 1
    cov = d["coverage"]
    assert cov["provinces"] == 77 and len(cov["regions"]) == 6
    assert cov["with_snapshot"] + len(cov["missing_snapshot"]) == 77
    assert d["system"]["verified_places"] >= 1


def test_overview_has_no_personal_data(env):
    c, store, _ = env
    signup(c, ADMIN)
    signup(c, "secret-person@example.com")
    uid = c.get("/api/auth/me").json()["user"]["id"]
    cid = store.create_chat(uid, "ข้อความลับของผู้ใช้")
    store.add_message(uid, cid, "user", "ข้อความลับของผู้ใช้")
    c.post("/api/me/favorites", json={"place_id": "v:p01"})
    signup(c, ADMIN.replace("boss", "boss2"))
    c.cookies.clear()
    c.post("/api/auth/login", json={"email": ADMIN, "password": "รหัสผ่านยาวพอ-123"})
    body = json.dumps(c.get("/api/admin/overview").json(), ensure_ascii=False)
    assert "secret-person" not in body and "ข้อความลับ" not in body
    assert c.get("/api/admin/overview").json()["top_favorites"] == []   # บันทึกคนเดียว ไม่แสดง


def test_metric_rows_hold_only_day_kind_key_count(env):
    c, _, db = env
    c.get(f"/api/places/nearby?lat={LAT}&lon={LON}")
    cols = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(metrics)")]
    assert cols == ["day", "kind", "key", "n"]


def test_counter_never_breaks_requests(env, monkeypatch):
    c, store, _ = env
    def boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(store, "bump_metric", boom)
    assert c.get(f"/api/places/nearby?lat={LAT}&lon={LON}").status_code == 200


def test_unknown_kind_is_ignored(env):
    _, store, db = env
    store.user_by_id(1)                                   # เปิดฐานข้อมูลให้มีตารางก่อน
    metrics.count("email", "someone@example.com")
    metrics.count("search", "")
    assert sqlite3.connect(db).execute("select count(*) from metrics").fetchone()[0] == 0


def test_summarize_fills_missing_days_and_sorts_tops():
    today = datetime(2026, 11, 4, tzinfo=timezone.utc)
    rows = [{"day": "2026-11-04", "kind": "chat", "key": "llm", "n": 3},
            {"day": "2026-11-03", "kind": "chat", "key": "rule", "n": 2},
            {"day": "2026-10-01", "kind": "chat", "key": "rule", "n": 5},
            {"day": "2026-11-04", "kind": "guard", "key": "names", "n": 1},
            {"day": "2026-11-02", "kind": "guard", "key": "cite", "n": 4}]
    s = summarize(rows, today)
    assert [d["day"] for d in s["daily"]][0] == "2026-10-22" and len(s["daily"]) == 14
    assert s["daily"][-1] == {"day": "2026-11-04", "chat": 3, "llm": 3, "rule": 0, "search": 0}
    assert s["chat_total"] == 10 and s["chat_modes"] == {"llm": 3, "rule": 7}
    assert s["guard"] == [{"key": "cite", "n": 4}, {"key": "names", "n": 1}]
