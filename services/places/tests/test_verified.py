from services.places.geo import in_thailand
from services.places.provinces import PROVINCES
from services.places.verified import load_verified


def test_loads_only_verified_with_sources():
    v = load_verified()
    assert len(v) >= 296
    assert all(c.source == "verified" for c in v)
    assert len({c.id for c in v}) == len(v)


def test_coordinates_inside_thailand_and_provinces_known():
    v = load_verified()
    assert all(in_thailand(c.lat, c.lon) for c in v)
    assert all(c.province in PROVINCES for c in v if c.province)


def test_77_provinces():
    assert len(PROVINCES) == 77


# ---------- ภาค ----------
from services.places.provinces import REGION_ORDER, REGIONS, region_of
from services.places.verified import coverage_by_province

# ขั้นต่ำสถานที่ที่ตรวจแล้วต่อจังหวัดของภาคที่ "ทำเสร็จ" แล้ว 
DONE_REGIONS = {"เหนือ": 5}

# ภาคอีสาน: Wikipedia มีสถานที่ให้ไม่ครบ 5 ต่อจังหวัด จึงล็อกไว้ไม่ให้ต่ำกว่าที่ได้จริง (ณ 2026-11-01)
# จังหวัดเหล่านี้พึ่งข้อมูลจาก OpenStreetMap เป็นหลัก ดู docs/REGIONS.md
NE_FLOOR = {"กาฬสินธุ์": 3, "ขอนแก่น": 5, "ชัยภูมิ": 4, "นครพนม": 3, "นครราชสีมา": 4, "บึงกาฬ": 4, "บุรีรัมย์": 4,
            "มหาสารคาม": 2, "มุกดาหาร": 2, "ยโสธร": 0, "ร้อยเอ็ด": 2, "เลย": 5, "สกลนคร": 5, "สุรินทร์": 3,
            "ศรีสะเกษ": 5, "หนองคาย": 2, "หนองบัวลำภู": 1, "อุดรธานี": 5, "อุบลราชธานี": 5, "อำนาจเจริญ": 2}


def test_regions_partition_all_77_provinces():
    allp = [p for r in REGIONS.values() for p in r]
    assert len(allp) == 77 and set(allp) == set(PROVINCES)
    assert set(REGION_ORDER) == set(REGIONS)
    assert [len(REGIONS[r]) for r in REGION_ORDER] == [9, 20, 22, 7, 5, 14]
    assert region_of("เชียงใหม่") == "เหนือ" and region_of("ภูเก็ต") == "ใต้"


def test_finished_regions_meet_minimum_coverage():
    cov = coverage_by_province()
    for region, minimum in DONE_REGIONS.items():
        low = {p: cov[p] for p in REGIONS[region] if cov[p] < minimum}
        assert not low, f"ภาค{region} มีจังหวัดที่ข้อมูลตรวจแล้วน้อยกว่า {minimum}: {low}"


def test_northeast_coverage_does_not_regress():
    assert set(NE_FLOOR) == set(REGIONS["ตะวันออกเฉียงเหนือ"])
    cov = coverage_by_province()
    low = {p: (cov[p], m) for p, m in NE_FLOOR.items() if cov[p] < m}
    assert not low, f"ข้อมูลภาคอีสานลดลง: {low}"
