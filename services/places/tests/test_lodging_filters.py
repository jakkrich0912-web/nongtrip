"""ตัวกรองค้นที่พัก (จังหวัด ย่าน ประเภท) สำหรับกรณีชื่อที่พักซ้ำกันหลายแห่ง"""
import pytest

from services.places import PlacesService, SearchError
from services.places.cache import TTLCache
from services.places.fetch import UpstreamError
from services.places.provinces import province_in_address
from services.places.snapshot import Snapshot, write_province
from .helpers import FakeHttp, cand


def row(i, name, display, typ="hotel", lat="18.79", lon="98.98"):
    return {"lat": lat, "lon": lon, "osm_type": "node", "osm_id": i, "category": "tourism", "type": typ,
            "name": name, "display_name": display}


ROWS = [
    row(1, "โรงแรมตัวอย่าง", "โรงแรมตัวอย่าง, ถนนช้างคลาน, ตำบลช้างคลาน, อำเภอเมืองเชียงใหม่, เชียงใหม่, 50100, ประเทศไทย"),
    row(2, "โรงแรมตัวอย่าง", "โรงแรมตัวอย่าง, ถนนราชดำเนิน, ตำบลในเมือง, อำเภอเมืองขอนแก่น, ขอนแก่น, 40000, ประเทศไทย"),
    row(3, "โรงแรมตัวอย่าง รีสอร์ต", "โรงแรมตัวอย่าง รีสอร์ต, ตำบลราไวย์, อำเภอเมืองภูเก็ต, ภูเก็ต, 83130, ประเทศไทย",
        typ="resort"),
    row(4, "โรงแรมตัวอย่าง", "โรงแรมตัวอย่าง, ถนนนิมมานเหมินท์, ตำบลสุเทพ, อำเภอเมืองเชียงใหม่, จังหวัดเชียงใหม่, ประเทศไทย"),
]


def svc(http, snapshot=None, live=True):
    return PlacesService(http=http, cache=TTLCache(None), verified=[], osm_live=live, snapshot=snapshot or Snapshot(None))


def ids(out):
    return [i["id"] for i in out["items"]]


# ---------- หาจังหวัดจากที่อยู่ ----------

@pytest.mark.parametrize("addr,exp", [
    ("A, ถนน X, อำเภอเมืองเชียงใหม่, เชียงใหม่, 50100, ประเทศไทย", "เชียงใหม่"),
    ("A, อำเภอเมืองเลย, จังหวัดเลย, 42000, ประเทศไทย", "เลย"),
    ("A, กรุงเทพมหานคร, 10200, ประเทศไทย", "กรุงเทพมหานคร"),
    ("ร้านเลยพ้น, ซอยตากสิน, ถนนแพร่หลาย, ประเทศไทย", None),  # ชื่อสั้นอย่าง เลย/ตาก/แพร่ ต้องไม่ไปตรงกับคำอื่น
    ("", None), (None, None),
])
def test_province_in_address(addr, exp):
    assert province_in_address(addr) == exp


# ---------- ค้นออนไลน์ ----------

def test_no_filter_behaves_as_before():
    http = FakeHttp(nominatim=ROWS)
    out = svc(http).find_lodging("โรงแรมตัวอย่าง")
    assert len(out["items"]) == 4 and any("เลือก" in n for n in out["notices"])
    assert http.calls[0][2]["q"] == "โรงแรมตัวอย่าง" and http.calls[0][2]["limit"] == 8
    assert {i["province"] for i in out["items"]} == {"เชียงใหม่", "ขอนแก่น", "ภูเก็ต"}


def test_province_filter_keeps_only_that_province_and_biases_query():
    http = FakeHttp(nominatim=ROWS)
    out = svc(http).find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่")
    assert ids(out) == ["osm:node/1", "osm:node/4"]
    assert http.calls[0][2]["q"] == "โรงแรมตัวอย่าง เชียงใหม่" and http.calls[0][2]["limit"] == 20


def test_area_filter_matches_address_text():
    out = svc(FakeHttp(nominatim=ROWS)).find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่", area="ช้างคลาน")
    assert ids(out) == ["osm:node/1"] and out["notices"] == []


def test_subtype_filter():
    out = svc(FakeHttp(nominatim=ROWS)).find_lodging("โรงแรมตัวอย่าง", subtype="resort")
    assert ids(out) == ["osm:node/3"]


def test_filters_combine_with_and():
    out = svc(FakeHttp(nominatim=ROWS)).find_lodging("โรงแรมตัวอย่าง", province="ภูเก็ต", subtype="hotel")
    assert out["items"] == [] and any("ตัวกรอง" in n for n in out["notices"])


def test_unknown_province_item_is_dropped_when_province_requested_not_guessed():
    rows = [row(9, "โรงแรมตัวอย่าง", "โรงแรมตัวอย่าง, ประเทศไทย")]
    assert svc(FakeHttp(nominatim=rows)).find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่")["items"] == []
    assert len(svc(FakeHttp(nominatim=rows)).find_lodging("โรงแรมตัวอย่าง")["items"]) == 1


def test_no_result_message_differs_with_and_without_filter_hits():
    assert any("ตัวกรอง" in n for n in svc(FakeHttp(nominatim=ROWS)).find_lodging("โรงแรมตัวอย่าง", area="ไม่มีย่านนี้")["notices"])
    assert any("ไม่พบที่พักชื่อนี้" in n for n in svc(FakeHttp(nominatim=[])).find_lodging("โรงแรมตัวอย่าง", area="x")["notices"])


def test_filtered_queries_are_cached_separately_from_unfiltered():
    http = FakeHttp(nominatim=ROWS)
    s = svc(http)
    s.find_lodging("โรงแรมตัวอย่าง")
    s.find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่")
    s.find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่", subtype="hotel")  # subtype กรองทีหลัง ใช้แคชเดิมได้
    assert http.count("nominatim") == 2


def test_cached_items_without_province_field_still_filter_by_address():
    s = svc(FakeHttp())
    s.cache.set("nominatim:โรงแรมตัวอย่าง เชียงใหม่:20", [{"id": "osm:node/1", "name": "x", "address": "x, เชียงใหม่, ไทย",
                                                         "subtype": "hotel", "lat": 1, "lon": 1}])
    assert ids(s.find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่")) == ["osm:node/1"]


@pytest.mark.parametrize("kw", [{"province": "เชียงใหม"}, {"province": "Chiang Mai"}, {"subtype": "castle"},
                                {"area": "ก" * 101}])
def test_invalid_filters_are_rejected(kw):
    with pytest.raises(SearchError):
        svc(FakeHttp(nominatim=ROWS)).find_lodging("โรงแรมตัวอย่าง", **kw)


def test_blank_filters_are_ignored():
    out = svc(FakeHttp(nominatim=ROWS)).find_lodging("โรงแรมตัวอย่าง", province="  ", area="", subtype=None)
    assert len(out["items"]) == 4


# ---------- ออฟไลน์ (สแนปช็อต) ----------

def make_snap(tmp_path):
    write_province(tmp_path, "เชียงใหม่", [cand("osm:node/1", "โรงแรมตัวอย่าง", 18.79, 98.98, kind="lodging"),
                                           cand("osm:node/2", "โรงแรมตัวอย่าง รีสอร์ต", 18.8, 98.99, kind="lodging")],
                   "2026-11-01")
    write_province(tmp_path, "ขอนแก่น", [cand("osm:node/3", "โรงแรมตัวอย่าง", 16.4, 102.8, kind="lodging")], "2026-11-01")
    return Snapshot(tmp_path)


def test_snapshot_province_filter_when_online_fails(tmp_path):
    s = svc(FakeHttp(nominatim_error=UpstreamError("x")), make_snap(tmp_path))
    both = s.find_lodging("โรงแรมตัวอย่าง")
    assert both["osm_mode"] == "snapshot" and sorted(ids(both)) == ["osm:node/1", "osm:node/2", "osm:node/3"]
    one = s.find_lodging("โรงแรมตัวอย่าง", province="ขอนแก่น")
    assert ids(one) == ["osm:node/3"] and one["items"][0]["province"] == "ขอนแก่น"


def test_snapshot_subtype_and_area_notice(tmp_path):
    s = svc(FakeHttp(), make_snap(tmp_path), live=False)
    out = s.find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่", area="ช้างคลาน")
    assert len(out["items"]) == 2 and any("ย่าน" in n for n in out["notices"])
    assert s.find_lodging("โรงแรมตัวอย่าง", subtype="resort")["items"] == []  # cand() ตั้ง subtype เป็น x


def test_offline_without_snapshot_still_degrades():
    out = svc(FakeHttp(nominatim_error=UpstreamError("x"))).find_lodging("โรงแรมตัวอย่าง", province="เชียงใหม่")
    assert out["items"] == [] and out["osm_available"] is False
