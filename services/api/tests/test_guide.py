"""ไกด์ที่เที่ยว: /api/guide/featured, /api/provinces/{name}/places, /api/places/{id}"""
import json

import pytest
from fastapi.testclient import TestClient

from services.api.guide import featured, load_guide
from services.api.main import create_app
from services.api.store import Store
from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.provinces import PROVINCES, region_of
from services.places.snapshot import Snapshot
from services.places.tests.helpers import FakeHttp


def place(i, province, category="temple", description=None, notes=None, verified=True, lat=18.8, lon=98.9, **extra):
    return {"id": i, "name_th": f"สถานที่ {i}", "name_en": None, "category": category, "area": province, "lat": lat,
            "lon": lon, "cost_thb": 500, "open": None, "tags": [], "description": description, "notes": notes or [],
            "province": province, "verified": verified,
            "sources": [{"url": f"https://example.org/{i}", "title": f"{i} (Wikipedia)", "checked_on": "2026-11-01",
                         "fields": ["lat"]}], **extra}


def write(tmp_path, first, second=None):
    (tmp_path / "places.json").write_text(json.dumps({"_meta": {}, "places": first}), encoding="utf-8")
    if second is not None:
        (tmp_path / "places_all_provinces.json").write_text(json.dumps({"_meta": {}, "places": second}),
                                                            encoding="utf-8")
    return tmp_path


def client(tmp_path, items):
    svc = PlacesService(http=FakeHttp(), cache=TTLCache(None), verified=[], osm_live=True, snapshot=Snapshot(None))
    app = create_app(svc, store=Store(tmp_path / "t.db"), session_secret="s", secure_cookie=False, guide=items)
    return TestClient(app)


@pytest.fixture
def sample(tmp_path):
    d = write(tmp_path, [
        place("a1", "เชียงใหม่", "temple", notes=["ควรแต่งกายสุภาพ", "  "]),
        place("a2", "เชียงใหม่", "nature", description="คำอธิบายที่มีแหล่ง"),
        place("a3", "เชียงใหม่", "cafe"),
        place("b1", "เชียงราย", "temple"),
        place("c1", "ภูเก็ต", "nature"),
        place("x1", "ภูเก็ต", "temple", verified=False),
    ])
    return client(tmp_path, load_guide(d))


# ---------- โหลดข้อมูล ----------

def test_load_keeps_only_verified_and_never_exposes_price(tmp_path):
    g = load_guide(write(tmp_path, [place("a1", "เชียงใหม่"), place("x", "เชียงใหม่", verified=False),
                                    place("n", "เชียงใหม่", lat=None), place("far", "เชียงใหม่", lat=51.5, lon=0.1)]))
    assert [x["id"] for x in g] == ["v:a1"]
    assert "cost_thb" not in json.dumps(g) and "500" not in json.dumps(g)


def test_load_maps_fields_and_cleans_blanks(tmp_path):
    g = load_guide(write(tmp_path, [place("a1", "เชียงใหม่", description="  ", notes=["ข้อ 1", " ", ""], area="ดอยสุเทพ"),
                                    place("a2", "เชียงใหม่", "cafe")]))
    a1, a2 = g
    assert a1["description"] is None and a1["notes"] == ["ข้อ 1"] and a1["area"] == "ดอยสุเทพ"
    assert a1["kind"] == "attraction" and a2["kind"] == "cafe" and a2["area"] is None  # area เท่าชื่อจังหวัด = ไม่มีข้อมูลย่าน
    assert a1["source_url"] == "https://example.org/a1" and a1["source_checked_on"] == "2026-11-01"
    assert a1["maps_url"].startswith("https://www.google.com/maps/")


def test_load_later_file_overrides_same_id_and_missing_source_is_null(tmp_path):
    second = place("a1", "ลำปาง")
    second["sources"] = []
    g = load_guide(write(tmp_path, [place("a1", "เชียงใหม่")], [second]))
    assert len(g) == 1 and g[0]["province"] == "ลำปาง" and g[0]["source_url"] is None


def test_load_missing_files_is_empty(tmp_path):
    assert load_guide(tmp_path) == []


def test_real_data_is_clean():
    g = load_guide()
    assert len(g) > 300
    assert len({x["id"] for x in g}) == len(g)
    assert all(x["province"] in PROVINCES for x in g), {x["province"] for x in g if x["province"] not in PROVINCES}
    assert all(x["source_url"] for x in g), "สถานที่ verified ทุกแห่งต้องมีแหล่งที่มา"
    assert "cost_thb" not in json.dumps(g)


# ---------- featured ----------

def test_featured_one_per_province_prefers_described(sample):
    r = sample.get("/api/guide/featured").json()
    assert [x["id"] for x in r["items"] if x["province"] == "เชียงใหม่"] == ["v:a2"]
    assert len({x["province"] for x in r["items"]}) == len(r["items"]) == 3
    assert r["total"] == 5 and r["categories"] == {"cafe": 1, "nature": 2, "temple": 2}


def test_featured_limit_category_and_validation(sample):
    assert len(sample.get("/api/guide/featured?limit=2").json()["items"]) == 2
    t = sample.get("/api/guide/featured?category=temple").json()["items"]
    assert {x["subtype"] for x in t} == {"temple"} and {x["province"] for x in t} == {"เชียงใหม่", "เชียงราย"}
    assert sample.get("/api/guide/featured?category=nope").json()["items"] == []
    for bad in ["limit=0", "limit=51", "limit=x"]:
        assert sample.get(f"/api/guide/featured?{bad}").status_code == 400


def test_featured_interleaves_regions():
    mk = lambda i, p: {"id": f"v:{i}", "province": p, "subtype": "temple", "description": None}  # noqa: E731
    items = [mk(1, "เชียงใหม่"), mk(2, "เชียงราย"), mk(3, "เชียงรายx"), mk(4, "ภูเก็ต"), mk(5, "ขอนแก่น")]
    out = featured([x for x in items if x["province"] in PROVINCES], 10, None)
    provs = [x["province"] for x in out]
    assert sorted(provs) == sorted(["เชียงใหม่", "เชียงราย", "ขอนแก่น", "ภูเก็ต"])
    assert len({region_of(p) for p in provs[:3]}) == 3  # สามแห่งแรกมาจากสามภาคต่างกัน


def test_featured_on_empty_data(tmp_path):
    assert client(tmp_path, []).get("/api/guide/featured").json() == {"items": [], "categories": {}, "total": 0}


# ---------- รายการตามจังหวัด ----------

def test_province_places(sample):
    r = sample.get("/api/provinces/เชียงใหม่/places").json()
    assert r["province"] == "เชียงใหม่" and r["region"] == "เหนือ" and r["verified_count"] == r["total"] == 3
    assert [x["id"] for x in r["items"]] == ["v:a1", "v:a2", "v:a3"] and r["has_more"] is False
    assert r["categories"] == {"cafe": 1, "nature": 1, "temple": 1}


def test_province_places_filter_and_paging(sample):
    r = sample.get("/api/provinces/เชียงใหม่/places?category=temple").json()
    assert r["total"] == 1 and r["verified_count"] == 3  # verified_count ไม่ขึ้นกับตัวกรอง
    p1 = sample.get("/api/provinces/เชียงใหม่/places?limit=2").json()
    p2 = sample.get("/api/provinces/เชียงใหม่/places?limit=2&offset=2").json()
    assert [len(p1["items"]), p1["has_more"], len(p2["items"]), p2["has_more"]] == [2, True, 1, False]


def test_province_without_data_is_empty_not_error(sample):
    r = sample.get("/api/provinces/ลำพูน/places").json()
    assert r["verified_count"] == 0 and r["items"] == [] and r["has_more"] is False and r["categories"] == {}


@pytest.mark.parametrize("bad", ["กรุงเทพ", "chiang mai", "%20", "เชียงใหม่x"])
def test_unknown_province_is_400(sample, bad):
    r = sample.get(f"/api/provinces/{bad}/places")
    assert r.status_code == 400 and r.json()["code"] == "invalid_param"


@pytest.mark.parametrize("q", ["limit=0", "limit=201", "offset=-1", "offset=100001"])
def test_province_paging_validation(sample, q):
    assert sample.get(f"/api/provinces/เชียงใหม่/places?{q}").status_code == 400


def test_province_center_route_still_works(sample):
    assert sample.get("/api/provinces/ไม่มีจังหวัดนี้/center").status_code == 400


# ---------- รายละเอียดสถานที่ ----------

def test_place_detail(sample):
    r = sample.get("/api/places/v:a2")
    assert r.status_code == 200
    d = r.json()
    assert d["name_th"] == "สถานที่ a2" and d["description"] == "คำอธิบายที่มีแหล่ง" and d["province"] == "เชียงใหม่"
    assert set(d) >= {"id", "name_th", "name_en", "kind", "subtype", "province", "area", "description", "notes", "lat",
                      "lon", "maps_url", "source_url", "source_title", "source_checked_on"}
    assert "cost_thb" not in r.text


@pytest.mark.parametrize("pid", ["v:nope", "v:x1", "a2", "osm:node/1", "v:" + "a" * 80, "v:a2/extra", "v:%00"])
def test_place_detail_unknown_is_404(sample, pid):
    r = sample.get(f"/api/places/{pid}")
    assert r.status_code == 404 and r.json()["code"] == "not_found"


def test_nearby_route_not_shadowed_by_place_detail(sample):
    r = sample.get("/api/places/nearby", params={"lat": 18.8, "lon": 98.9})
    assert r.status_code == 200 and "items" in r.json()
