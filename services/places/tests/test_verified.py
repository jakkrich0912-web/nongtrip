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
