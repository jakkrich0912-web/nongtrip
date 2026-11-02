import copy

from services.api.validator import load_verified_ids, validate_lodgings_near, validate_nearby

LAT, LON = 18.7883, 98.9853


def up(km):
    return LAT + km / 111.19


def item(i, name, km, source="osm", kind="attraction"):
    la = up(km)
    return {"id": f"osm:node/{i}" if source == "osm" else f"v:{i}", "name_th": name, "name_en": None, "kind": kind,
            "subtype": "x", "lat": la, "lon": LON, "distance_km": round(km, 2), "source": source, "province": None,
            "source_url": None, "maps_url": "https://www.google.com/maps/search/?api=1&query=x",
            "directions_url": "https://www.google.com/maps/dir/?api=1&origin=1&destination=2"}


def good():
    return {"center": {"lat": LAT, "lon": LON}, "radius_km": 30, "total": 3, "offset": 0, "limit": 50,
            "counts": {"attraction": 2, "cafe": 1}, "sources": {"verified": 0, "osm": 3}, "osm_available": True,
            "osm_mode": "live", "notices": [], "attribution": "© OpenStreetMap contributors (ODbL)",
            "distance_note": "ระยะเป็นเส้นตรง",
            "items": [item(1, "ใกล้", 1), item(2, "กลาง", 5, kind="cafe"), item(3, "ไกล", 20)]}


def problems(resp, **kw):
    return validate_nearby(resp, **kw)["problems"]


def test_good_response_passes():
    assert validate_nearby(good())["ok"]


def test_detects_unsorted():
    r = good()
    r["items"][0], r["items"][2] = r["items"][2], r["items"][0]
    assert any("เรียง" in p for p in problems(r))


def test_detects_beyond_radius_and_wrong_distance():
    r = good()
    r["items"][2] = item(3, "ไกลเกิน", 45)
    assert any("ไกลเกินรัศมี" in p for p in problems(r))
    r = good()
    r["items"][1]["distance_km"] = 9.9
    assert any("ไม่ตรงกับที่คำนวณ" in p for p in problems(r))


def test_radius_over_30_rejected():
    r = good()
    r["radius_km"] = 31
    assert any("รัศมี" in p for p in problems(r))


def test_detects_money_rating_review_fields():
    for key in ("price_thb", "entrance_fee", "rating", "review_count", "budget"):
        r = good()
        r["items"][0][key] = 1
        assert any("ห้ามมี" in p for p in problems(r)), key


def test_detects_duplicates():
    r = good()
    r["items"][1] = copy.deepcopy(r["items"][0])
    ps = problems(r)
    assert any("id ซ้ำ" in p for p in ps)
    r = good()
    twin = item(9, "ใกล้", 1.0)
    r["items"].insert(1, twin)
    assert any("ซ้ำกับรายการอื่น" in p for p in problems(r))


def test_osm_requires_attribution_and_mode_notice():
    r = good()
    r["attribution"] = ""
    assert any("OpenStreetMap" in p for p in problems(r))
    r = good()
    r["osm_mode"] = "snapshot"
    r["notices"] = []
    assert validate_nearby(r)["ok"]          # v0.14 โหมดสแนปช็อตไม่ต้องมีข้อความเตือน
    r["osm_mode"] = "none"
    assert any("ไม่มีข้อความแจ้ง" in p for p in problems(r))
    r["notices"] = ["ไม่มีข้อมูล OpenStreetMap"]
    assert validate_nearby(r)["ok"]


def test_verified_must_exist_in_data_file():
    known = load_verified_ids()
    assert len(known) >= 296
    real = sorted(known)[0]
    r = good()
    r["items"][0] = item(real[2:], "ของจริง", 1, source="verified")
    assert validate_nearby(r, known)["ok"]
    r["items"][0]["id"] = "v:ไม่มีจริง"
    assert any("ไม่พบสถานที่ที่ตรวจแล้ว" in p for p in problems(r, known_verified_ids=known))


def test_source_and_id_must_agree():
    r = good()
    r["items"][0]["source"] = "verified"
    assert any("id ไม่ตรงกับ source" in p for p in problems(r))


def test_outside_thailand_flagged():
    r = good()
    r["items"][0]["lat"] = 35.0
    assert any("นอกประเทศไทย" in p for p in problems(r))


def lodging_resp(n_nearest=3, total=5):
    lod = {"id": "osm:node/100", "name": "ที่พัก", "lat": LAT, "lon": LON, "places_radius_km": 30, "places_total": total,
           "has_more": total > n_nearest, "counts": {"attraction": total, "cafe": 0},
           "nearest": [item(i, f"จุด{i}", i) for i in range(1, n_nearest + 1)]}
    return {"items": [lod], "radius_km": 5, "osm_available": True, "osm_mode": "live", "notices": [],
            "attribution": "© OpenStreetMap contributors (ODbL)"}


def test_lodgings_good_and_has_more_consistency():
    assert validate_lodgings_near(lodging_resp())["ok"]
    r = lodging_resp()
    r["items"][0]["has_more"] = False
    assert any("has_more" in p for p in validate_lodgings_near(r)["problems"])


def test_lodgings_more_than_top_n_rejected():
    assert any("เกิน 3" in p for p in validate_lodgings_near(lodging_resp(n_nearest=4, total=6))["problems"])


def test_lodgings_radius_over_10_rejected():
    r = lodging_resp()
    r["radius_km"] = 12
    assert any("เกิน 10" in p for p in validate_lodgings_near(r)["problems"])
