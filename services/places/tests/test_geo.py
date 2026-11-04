from services.places.geo import directions_url, haversine_km, in_thailand, place_url


def test_haversine_known_distance():
    # กรุงเทพ - เชียงใหม่ เส้นตรงประมาณ 580 กม.
    d = haversine_km(13.7563, 100.5018, 18.7883, 98.9853)
    assert 570 < d < 590


def test_haversine_zero_and_symmetric():
    assert haversine_km(18.0, 99.0, 18.0, 99.0) == 0
    assert abs(haversine_km(18, 99, 19, 100) - haversine_km(19, 100, 18, 99)) < 1e-9


def test_in_thailand():
    assert in_thailand(18.79, 98.98)
    assert not in_thailand(35.68, 139.69)  # โตเกียว


def test_google_maps_links_need_no_key():
    u = place_url("วัดเจดีย์หลวง", 18.78, 98.98)
    assert u.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "key=" not in u
    d = directions_url((18.0, 99.0), (18.1, 99.1))
    assert "origin=18.000000%2C99.000000" in d and "destination=18.100000%2C99.100000" in d
