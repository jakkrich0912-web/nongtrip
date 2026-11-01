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
