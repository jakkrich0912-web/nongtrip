import pytest

from services.places.fetch import UpstreamError, UpstreamTooBig
from services.places.osm import NominatimClient, OverpassClient, build_query, classify, parse_elements, unsuitable
from .helpers import FakeHttp, el


def test_classify_main_types():
    assert classify({"amenity": "cafe"}) == ("cafe", "cafe")
    assert classify({"tourism": "hotel"}) == ("lodging", "hotel")
    assert classify({"tourism": "viewpoint"}) == ("attraction", "viewpoint")
    assert classify({"natural": "waterfall"}) == ("attraction", "waterfall")
    assert classify({"amenity": "place_of_worship", "wikidata": "Q1"}) == ("attraction", "place_of_worship")
    # วัดทั่วไปที่ไม่มี wikidata ไม่นับเป็นที่เที่ยว (กันรายการล้น)
    assert classify({"amenity": "place_of_worship"}) is None
    assert classify({"shop": "convenience"}) is None


def test_parse_skips_nameless_and_dupes_and_uses_center_for_ways():
    els = [
        el(1, "กาแฟ A", 18.1, 99.1, {"amenity": "cafe"}),
        {"type": "node", "id": 2, "lat": 18.2, "lon": 99.2, "tags": {"amenity": "cafe"}},  # ไม่มีชื่อ
        {"type": "way", "id": 3, "center": {"lat": 18.3, "lon": 99.3},
         "tags": {"name": "สวนสาธารณะ", "leisure": "park"}},
        el(1, "กาแฟ A", 18.1, 99.1, {"amenity": "cafe"}),  # ซ้ำ
    ]
    out = parse_elements(els)
    assert [c.id for c in out] == ["osm:node/1", "osm:way/3"]
    assert out[1].lat == 18.3 and out[1].source == "osm"


def test_query_has_radius_and_requires_name():
    q = build_query(18.78, 98.98, 31000, ("attraction", "cafe"))
    assert "around:31000,18.78000,98.98000" in q
    assert '["amenity"="cafe"]["name"]' in q
    assert "out center tags" in q


def test_overpass_fallback_to_second_mirror():
    calls = []

    class H:
        def post_form(self, url, data):
            calls.append(url)
            if len(calls) == 1:
                raise UpstreamError("down")
            return {"elements": [el(1, "กาแฟ ก", 18.1, 99.1, {"amenity": "cafe"})]}

    out = OverpassClient(H(), endpoints=("a", "b")).fetch(18, 99, 5, ("cafe",))
    assert calls == ["a", "b"] and len(out) == 1


def test_overpass_timeout_remark_means_too_big():
    class H:
        def post_form(self, url, data):
            return {"elements": [], "remark": "runtime error: Query timed out"}

    with pytest.raises(UpstreamTooBig):
        OverpassClient(H(), endpoints=("a",)).fetch(18, 99, 5, ("cafe",))


def test_nominatim_puts_real_lodging_first():
    rows = [
        {"lat": "18.80", "lon": "98.97", "osm_type": "node", "osm_id": 5, "category": "highway", "type": "bus_stop",
         "name": "ป้ายรถเมล์", "display_name": "ป้ายรถเมล์, เชียงใหม่"},
        {"lat": "18.79", "lon": "98.98", "osm_type": "way", "osm_id": 9, "category": "tourism", "type": "hotel",
         "name": "โรงแรมตัวอย่าง", "display_name": "โรงแรมตัวอย่าง, เชียงใหม่"},
    ]
    out = NominatimClient(FakeHttp(nominatim=rows)).search_lodging("ตัวอย่าง")
    assert out[0].name == "โรงแรมตัวอย่าง" and out[0].subtype == "hotel"
    assert out[0].id == "osm:way/9"


def test_overpass_busy_runtime_error_is_not_empty_result():
    """Overpass ตอบ 200 + remark runtime error + ผลว่างตอนแน่น ต้องลองเซิร์ฟเวอร์ถัดไป ไม่ใช่ถือว่าไม่มีสถานที่"""
    calls = []

    class H:
        def post_form(self, url, data):
            calls.append(url)
            if len(calls) == 1:
                return {"elements": [], "remark": "runtime error: open64: 0 Success Dispatcher_Client::request_read_and_idx::timeout. The server is probably too busy"}
            return {"elements": [el(1, "กาแฟ ก", 18.1, 99.1, {"amenity": "cafe"})]}

    out = OverpassClient(H(), endpoints=("a", "b")).fetch(18, 99, 5, ("cafe",))
    assert calls == ["a", "b"] and len(out) == 1


def test_overpass_all_busy_raises_instead_of_returning_empty():
    class H:
        def post_form(self, url, data):
            return {"elements": [], "remark": "runtime error: Dispatcher_Client::request_read_and_idx::timeout"}

    with pytest.raises(UpstreamError):
        OverpassClient(H(), endpoints=("a", "b")).fetch(18, 99, 5, ("cafe",))


@pytest.mark.parametrize("name,en,sub,ref", [
    ("H", None, "attraction", "node/1"),               # ตัวอักษรตัวเดียว
    ("101", None, "chalet", "node/2"),                 # เลขห้องพัก
    ("#96", None, "cafe", "node/3"),                   # ไม่มีตัวอักษรเลย
    ("สนามชนไก่เจ้านายน้อย", None, "museum", "node/4"),
    ("สวนสาธารณะที่ 1 หมู่บ้านพฤกษา20", None, "park", "way/5"),
    ("casa ville klong 2 park", None, "park", "node/6"),
    ("TRS", None, "park", "node/11175880428"),          # ตรวจด้วยตาแล้ว
])
def test_unsuitable_names_are_dropped(name, en, sub, ref):
    assert unsuitable(name, en, sub, ref)


@pytest.mark.parametrize("name,en,sub", [
    ("S&P", None, "cafe"), ("Zoo", None, "attraction"), ("เขาชนไก่", None, "peak"),
    ("บ่อน้ำพุร้อนผาบ่อง", None, "hot_spring"), ("Village Coffee", None, "cafe"),
    ("ดรีมเวิลด์", "Dream World", "theme_park"),
])
def test_real_places_are_kept(name, en, sub):
    assert not unsuitable(name, en, sub, "node/9")


def test_parse_drops_unsuitable():
    els = [el(1, "H", 14.0, 100.5, {"tourism": "attraction"}),
           el(2, "สวนหมู่บ้านพฤกษา", 14.0, 100.5, {"leisure": "park"}),
           el(3, "สวนสาธารณะเมือง", 14.0, 100.5, {"leisure": "park"})]
    assert [c.id for c in parse_elements(els)] == ["osm:node/3"]
