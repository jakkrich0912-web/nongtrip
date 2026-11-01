import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.fetch import UpstreamError
from services.places.snapshot import Snapshot
from services.places.tests.helpers import CM, FakeHttp, el

LAT, LON = CM


def up(km):
    return LAT + km / 111.19


def client(http=None, verified=None):
    svc = PlacesService(http=http or FakeHttp(), cache=TTLCache(None), verified=verified or [], osm_live=True,
                        snapshot=Snapshot(None))
    return TestClient(create_app(svc))


def osm_http():
    return FakeHttp(overpass=[
        el(1, "ใกล้สุด", up(1), LON, {"tourism": "attraction"}),
        el(2, "คาเฟ่", up(5), LON, {"amenity": "cafe"}),
        el(3, "ไกล", up(20), LON, {"tourism": "attraction"}),
    ])


def test_health():
    r = client().get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_nearby_ok_sorted_and_validated():
    r = client(osm_http()).get("/api/places/nearby", params={"lat": LAT, "lon": LON})
    j = r.json()
    assert r.status_code == 200 and [i["name_th"] for i in j["items"]] == ["ใกล้สุด", "คาเฟ่", "ไกล"]
    assert j["validation"]["ok"] and j["osm_mode"] == "live" and "OpenStreetMap" in j["attribution"]


def test_nearby_radius_over_30_is_400_thai_error():
    r = client(osm_http()).get("/api/places/nearby", params={"lat": LAT, "lon": LON, "radius_km": 31})
    assert r.status_code == 400 and "30" in r.json()["error"]


def test_nearby_bad_params_is_400():
    c = client(osm_http())
    assert c.get("/api/places/nearby", params={"lat": "abc", "lon": LON}).status_code == 400
    assert c.get("/api/places/nearby", params={"lat": LAT}).status_code == 400
    assert c.get("/api/places/nearby", params={"lat": LAT, "lon": LON, "limit": 0}).status_code == 400
    assert c.get("/api/places/nearby", params={"lat": 35.6, "lon": 139.7}).status_code == 400


def test_nearby_osm_down_still_answers_with_notice():
    r = client(FakeHttp(overpass_error=UpstreamError("x"))).get("/api/places/nearby", params={"lat": LAT, "lon": LON})
    j = r.json()
    assert r.status_code == 200 and j["osm_available"] is False and j["notices"] and j["validation"]["ok"]


def test_validator_failure_is_flagged_to_user(monkeypatch):
    import services.api.main as m
    monkeypatch.setattr(m, "validate_nearby", lambda res, known: {"ok": False, "checked": 0, "problems": ["x"], "problem_count": 1})
    j = client(osm_http()).get("/api/places/nearby", params={"lat": LAT, "lon": LON}).json()
    assert any("ไม่ผ่านการตรวจอิสระ" in n for n in j["notices"])


def test_lodging_search():
    rows = [{"lat": "18.79", "lon": "98.98", "osm_type": "node", "osm_id": 1, "category": "tourism", "type": "hotel",
             "name": "โรงแรมตัวอย่าง", "display_name": "x"}]
    j = client(FakeHttp(nominatim=rows)).get("/api/lodgings/search", params={"q": "ตัวอย่าง"}).json()
    assert j["items"][0]["name"] == "โรงแรมตัวอย่าง"
    assert client().get("/api/lodgings/search", params={"q": ""}).status_code == 400
    assert client().get("/api/lodgings/search").status_code == 400


def test_lodgings_near_validated():
    pois = [el(10 + i, f"จุด{i}", up(i + 1), LON, {"tourism": "attraction"}) for i in range(5)]
    lods = [{"type": "node", "id": 100, "lat": up(0.5), "lon": LON, "tags": {"name": "ที่พัก ก", "tourism": "hotel"}}]
    j = client(FakeHttp(overpass=lods + pois)).get("/api/lodgings/near", params={"lat": LAT, "lon": LON}).json()
    assert j["items"][0]["name"] == "ที่พัก ก" and len(j["items"][0]["nearest"]) == 3 and j["validation"]["ok"]


def test_provinces_list_has_all_77_by_region():
    j = client().get("/api/provinces").json()
    assert [r["region"] for r in j["regions"]][0] == "เหนือ"
    assert sum(len(r["provinces"]) for r in j["regions"]) == 77


def test_province_center_and_unknown():
    assert client().get("/api/provinces/ลำปาง/center").status_code == 200
    r = client().get("/api/provinces/โตเกียว/center")
    assert r.status_code == 400 and "77" in r.json()["error"]
