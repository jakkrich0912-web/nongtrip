import pytest

from services.places import PlacesService, RadiusError, OutOfThailandError
from services.places.cache import TTLCache
from services.places.fetch import UpstreamError
from services.places.search import SearchError, dedupe
from .helpers import CM, FakeHttp, cand, el

LAT, LON = CM


def svc(http, verified=None, **kw):
    return PlacesService(http=http, cache=TTLCache(None), verified=verified or [], osm_live=True, **kw)


def offset_lat(km):  # เลื่อนไปทางเหนือ km กม.
    return LAT + km / 111.19


def sample_http():
    return FakeHttp(overpass=[
        el(1, "ไกลสุด", offset_lat(20), LON, {"tourism": "attraction"}),
        el(2, "ใกล้สุด", offset_lat(1), LON, {"tourism": "attraction"}),
        el(3, "คาเฟ่กลาง", offset_lat(5), LON, {"amenity": "cafe"}),
        el(4, "นอกรัศมี", offset_lat(35), LON, {"tourism": "attraction"}),
    ])


def test_sorted_nearest_first_and_within_radius():
    r = svc(sample_http()).nearby(LAT, LON, 30)
    names = [p.name_th for p in r.items]
    assert names == ["ใกล้สุด", "คาเฟ่กลาง", "ไกลสุด"]
    d = [p.distance_km for p in r.items]
    assert d == sorted(d) and all(x <= 30 for x in d)


def test_radius_is_enforced_in_code():
    s = svc(sample_http())
    with pytest.raises(RadiusError):
        s.nearby(LAT, LON, 30.01)
    with pytest.raises(RadiusError):
        s.nearby(LAT, LON, 0)


def test_outside_thailand_rejected():
    with pytest.raises(OutOfThailandError):
        svc(sample_http()).nearby(35.68, 139.69, 10)


def test_smaller_radius_and_kind_filter():
    r = svc(sample_http()).nearby(LAT, LON, 10, kinds=["cafe"])
    assert [p.name_th for p in r.items] == ["คาเฟ่กลาง"]
    assert r.counts == {"cafe": 1}


def test_pagination_keeps_total():
    r = svc(sample_http()).nearby(LAT, LON, 30, limit=2, offset=1)
    assert r.total == 3 and [p.name_th for p in r.items] == ["คาเฟ่กลาง", "ไกลสุด"]


def test_verified_beats_osm_duplicate():
    v = [cand("v:1", "วัดเจดีย์หลวง", offset_lat(1), LON, source="verified")]
    http = FakeHttp(overpass=[el(7, "วัดเจดีย์หลวง", offset_lat(1.05), LON, {"tourism": "attraction"})])
    r = svc(http, verified=v).nearby(LAT, LON, 30)
    assert len(r.items) == 1 and r.items[0].source == "verified"
    assert r.sources == {"verified": 1, "osm": 0}


def test_same_name_far_apart_is_not_duplicate():
    a = cand("a", "ตลาดเช้า", 18.0, 99.0)
    b = cand("b", "ตลาดเช้า", 18.5, 99.0)
    assert len(dedupe([a, b])) == 2


def test_osm_down_falls_back_to_verified_only_with_notice():
    v = [cand("v:1", "วัดตัวอย่าง", offset_lat(2), LON, source="verified")]
    http = FakeHttp(overpass_error=UpstreamError("down"))
    r = svc(http, verified=v).nearby(LAT, LON, 30)
    assert r.osm_available is False and len(r.items) == 1
    assert any("OpenStreetMap" in n for n in r.notices)


def test_cache_prevents_second_fetch_nearby_point():
    http = sample_http()
    s = svc(http)
    s.cache = TTLCache(None)
    s.nearby(LAT, LON, 30)
    s.nearby(LAT + 0.001, LON + 0.001, 30)  # ใกล้กันมาก ปัดเป็นช่องเดียวกัน
    assert http.count("overpass") == 1


def test_too_big_reduces_radius_and_tells_user():
    http = sample_http()
    http.too_big_above_km = 20
    r = svc(http).nearby(LAT, LON, 30)
    assert r.radius_km <= 14
    assert any("หนาแน่น" in n for n in r.notices) and any("รัศมี" in n for n in r.notices)
    assert all(p.distance_km <= r.radius_km for p in r.items)


def test_items_have_navigation_and_review_links_but_no_money_or_rating():
    r = svc(sample_http()).nearby(LAT, LON, 30).to_dict()
    for it in r["items"]:
        assert it["maps_url"].startswith("https://www.google.com/maps/")
        assert "origin=" in it["directions_url"]
        for k in it:
            assert not any(w in k.lower() for w in ("cost", "price", "fee", "budget", "rating", "review"))
    assert "OpenStreetMap" in r["attribution"] and "เส้นตรง" in r["distance_note"]


# ---------- ค้นที่พักจากชื่อ ----------
def test_find_lodging_returns_choices_and_asks_to_pick():
    rows = [
        {"lat": "18.79", "lon": "98.98", "osm_type": "node", "osm_id": 1, "category": "tourism", "type": "hotel", "name": "A", "display_name": "A, CM"},
        {"lat": "18.80", "lon": "98.99", "osm_type": "node", "osm_id": 2, "category": "tourism", "type": "hotel", "name": "A2", "display_name": "A2, CM"},
    ]
    out = svc(FakeHttp(nominatim=rows)).find_lodging("โรงแรม A")
    assert len(out["items"]) == 2 and any("เลือก" in n for n in out["notices"])


def test_find_lodging_degrades_when_nominatim_down():
    out = svc(FakeHttp(nominatim_error=UpstreamError("x"))).find_lodging("โรงแรม")
    assert out["items"] == [] and out["osm_available"] is False and any("ปักหมุด" in n for n in out["notices"])


def test_find_lodging_rejects_tiny_query():
    with pytest.raises(SearchError):
        svc(FakeHttp()).find_lodging("ก")


# ---------- ที่พักรอบหมุด ----------
def lodging_http(lodgings_near=True):
    pois = [el(10 + i, f"จุด{i}", offset_lat(i + 1), LON, {"tourism": "attraction"}) for i in range(6)]
    lods = []
    if lodgings_near:
        lods = [
            {"type": "node", "id": 100, "lat": offset_lat(0.5), "lon": LON, "tags": {"name": "ที่พัก ก", "tourism": "hotel"}},
            {"type": "node", "id": 101, "lat": offset_lat(3), "lon": LON, "tags": {"name": "ที่พัก ข", "tourism": "hostel"}},
        ]
    return FakeHttp(overpass=lods + pois)


def test_lodgings_near_shows_top3_and_count_with_has_more():
    http = lodging_http()
    out = svc(http).lodgings_near(LAT, LON)
    assert [i["name"] for i in out["items"]] == ["ที่พัก ก", "ที่พัก ข"]
    first = out["items"][0]
    assert len(first["nearest"]) == 3 and first["places_total"] == 6 and first["has_more"] is True
    d = [p["distance_km"] for p in first["nearest"]]
    assert d == sorted(d)
    # ดึงที่พัก 1 ครั้ง + ดึงสถานที่ครั้งเดียวสำหรับทุกที่พัก
    assert http.count("overpass") == 2


def test_lodgings_near_expands_5_to_10_km():
    far = [{"type": "node", "id": 200, "lat": offset_lat(8), "lon": LON, "tags": {"name": "ที่พักไกล", "tourism": "hotel"}}]
    http = FakeHttp(overpass=far)
    out = svc(http).lodgings_near(LAT, LON)
    assert out["radius_km"] == 10 and [i["name"] for i in out["items"]] == ["ที่พักไกล"]
    assert any("ขยาย" in n for n in out["notices"])


def test_lodgings_near_none_found_says_so():
    out = svc(FakeHttp(overpass=[])).lodgings_near(LAT, LON)
    assert out["items"] == [] and any("ไม่พบที่พัก" in n for n in out["notices"])


# ---------- จุดกลางจังหวัด ----------
from services.places.provinces import REGIONS


def test_province_center_from_osm_and_cached():
    rows = [{"lat": "18.79", "lon": "98.98", "category": "boundary", "type": "administrative"}]
    http = FakeHttp(nominatim=rows)
    s = svc(http)
    a = s.province_center("เชียงใหม่")
    b = s.province_center("เชียงใหม่")
    assert a["source"] == "osm" and a["region"] == "เหนือ" and a["lat"] == 18.79 and b == a
    assert http.count("nominatim") == 1


def test_province_center_falls_back_to_verified_centroid():
    v = [cand("v:1", "ก", 18.0, 99.0, source="verified"), cand("v:2", "ข", 19.0, 100.0, source="verified")]
    for c in v:
        c.province = "ลำปาง"
    out = svc(FakeHttp(nominatim_error=UpstreamError("x")), verified=v).province_center("ลำปาง")
    assert out["source"] == "verified_centroid" and (out["lat"], out["lon"]) == (18.5, 99.5) and out["notice"]


def test_province_center_unknown_everything_says_so():
    out = svc(FakeHttp(nominatim_error=UpstreamError("x"))).province_center("ยโสธร")
    assert out["lat"] is None and out["notice"]


def test_province_center_rejects_non_province():
    with pytest.raises(SearchError):
        svc(FakeHttp()).province_center("โตเกียว")


def test_every_province_resolves_in_every_region():
    # ทุกจังหวัดต้องถามจุดกลางได้โดยไม่ error (ข้อมูลจริงใช้ OSM ที่เครื่องผู้ใช้)
    s = PlacesService(http=FakeHttp(nominatim_error=UpstreamError("x")), cache=TTLCache(None), osm_live=True)
    for provs in REGIONS.values():
        for p in provs:
            out = s.province_center(p)
            assert out["province"] == p and out["region"]
