from services.places import PlacesService
from services.places.cache import TTLCache
from services.places.fetch import UpstreamError
from services.places.osm import build_area_query
from services.places.snapshot import Snapshot, write_province
from .helpers import CM, FakeHttp, cand

LAT, LON = CM


def up(km):
    return LAT + km / 111.19


def make_snapshot(tmp_path):
    items = [
        cand("osm:node/1", "วัดในสแนปช็อต", up(2), LON),
        cand("osm:node/2", "คาเฟ่ในสแนปช็อต", up(1), LON, kind="cafe"),
        cand("osm:node/3", "โรงแรมตัวอย่างเชียงใหม่", up(0.5), LON, kind="lodging", en="Example Hotel"),
        cand("osm:node/4", "ไกลเกิน", up(50), LON),
    ]
    write_province(tmp_path, "เชียงใหม่", items, "2026-11-01")
    return Snapshot(tmp_path)


def svc(tmp_path, http, live=True):
    return PlacesService(http=http, cache=TTLCache(None), verified=[], osm_live=live, snapshot=make_snapshot(tmp_path))


def test_write_and_load_roundtrip(tmp_path):
    snap = make_snapshot(tmp_path)
    assert snap.available() and len(snap.around(LAT, LON, 30, ("attraction", "cafe"))) == 2
    assert snap.built_on == "2026-11-01"


def test_missing_dir_is_not_available(tmp_path):
    assert not Snapshot(tmp_path / "nope").available()
    assert not Snapshot(None).available()


def test_offline_nearby_uses_snapshot_without_staleness_notice(tmp_path):
    r = svc(tmp_path, FakeHttp(overpass_error=UpstreamError("down"))).nearby(LAT, LON, 30)
    assert [p.name_th for p in r.items] == ["คาเฟ่ในสแนปช็อต", "วัดในสแนปช็อต"]
    assert r.osm_mode == "snapshot" and r.osm_available is True
    assert not any("บันทึกไว้ล่วงหน้า" in n or "ไม่ใช่ข้อมูลล่าสุด" in n for n in r.notices)   # CONTRACT v0.14
    d = [p.distance_km for p in r.items]
    assert d == sorted(d) and all(x <= 30 for x in d)


def test_live_off_still_uses_snapshot(tmp_path):
    http = FakeHttp()
    r = svc(tmp_path, http, live=False).nearby(LAT, LON, 30)
    assert r.osm_mode == "snapshot" and http.count("overpass") == 0 and len(r.items) == 2


def test_online_is_preferred_over_snapshot(tmp_path):
    from .helpers import el
    http = FakeHttp(overpass=[el(9, "ออนไลน์", up(3), LON, {"tourism": "attraction"})])
    r = svc(tmp_path, http).nearby(LAT, LON, 30)
    assert r.osm_mode == "live" and [p.name_th for p in r.items] == ["ออนไลน์"]


def test_find_lodging_offline_from_snapshot(tmp_path):
    out = svc(tmp_path, FakeHttp(nominatim_error=UpstreamError("x"))).find_lodging("โรงแรมตัวอย่าง")
    assert [i["name"] for i in out["items"]] == ["โรงแรมตัวอย่างเชียงใหม่"] and out["osm_mode"] == "snapshot"
    en = svc(tmp_path, FakeHttp(nominatim_error=UpstreamError("x"))).find_lodging("example hotel")
    assert len(en["items"]) == 1


def test_lodgings_near_offline(tmp_path):
    out = svc(tmp_path, FakeHttp(overpass_error=UpstreamError("down"))).lodgings_near(LAT, LON)
    assert out["osm_mode"] == "snapshot" and [i["name"] for i in out["items"]] == ["โรงแรมตัวอย่างเชียงใหม่"]
    assert len(out["items"][0]["nearest"]) == 2


def test_without_snapshot_behaviour_unchanged(tmp_path):
    s = PlacesService(http=FakeHttp(overpass_error=UpstreamError("d")), cache=TTLCache(None), verified=[],
                      osm_live=True, snapshot=Snapshot(tmp_path / "none"))
    r = s.nearby(LAT, LON, 30)
    assert r.osm_mode == "none" and r.osm_available is False and r.items == []


def test_area_query_matches_by_name_not_iso_code():
    q = build_area_query("ลำปาง", ("cafe",))
    assert 'admin_level"="4"' in q and "(จังหวัด)?ลำปาง$" in q and "nwr(area.a)" in q


def test_committed_snapshot_files_are_sane():
    """ไฟล์สแนปช็อตจริงใน repo: รูปแบบถูก พิกัดในไทย แต่ละประเภทไม่ว่าง (กัน Overpass ตอบว่างตอนแน่น)"""
    import json
    from services.places.geo import in_thailand
    from services.places.provinces import PROVINCES
    from services.places.snapshot import DEFAULT_DIR
    for f in sorted(DEFAULT_DIR.glob("*.json")) if DEFAULT_DIR.is_dir() else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d["_meta"]["province"] in PROVINCES and d["_meta"]["count"] == len(d["items"])
        kinds = {}
        for ref, th, en, kind, sub, lat, lon in d["items"]:
            assert th and in_thailand(lat, lon), (f.name, ref)
            kinds[kind] = kinds.get(kind, 0) + 1
        assert all(kinds.get(k, 0) >= 10 for k in ("attraction", "cafe", "lodging")), (f.name, kinds)


def test_load_skips_unsuitable_rows(tmp_path):
    import json
    (tmp_path / "ทดสอบ.json").write_text(json.dumps({"_meta": {"province": "ทดสอบ", "built_on": "2026-11-04"}, "items": [
        ["node/1", "H", None, "attraction", "attraction", LAT, LON],
        ["node/2", "สนามชนไก่บ้านนา", None, "attraction", "museum", LAT, LON],
        ["node/3", "วัดทดสอบ", None, "attraction", "place_of_worship", LAT, LON],
    ]}, ensure_ascii=False), encoding="utf-8")
    snap = Snapshot(tmp_path)
    assert [c.id for c in snap.around(LAT, LON, 5, ("attraction",))] == ["osm:node/3"]
