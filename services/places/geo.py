"""คำนวณระยะทางเส้นตรงและสร้างลิงก์ Google Maps (ไม่ต้องใช้ API key)"""
from __future__ import annotations

import math
from urllib.parse import quote, urlencode

EARTH_RADIUS_KM = 6371.0088
# กรอบประเทศไทยแบบหยาบ ใช้กันพิกัดผิดที่
THAILAND_BOUNDS = (5.4, 20.6, 97.3, 105.7)  # lat_min, lat_max, lon_min, lon_max


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """ระยะเส้นตรงบนผิวโลก หน่วย กม."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def in_thailand(lat: float, lon: float) -> bool:
    la0, la1, lo0, lo1 = THAILAND_BOUNDS
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


def place_url(name: str, lat: float, lon: float) -> str:
    """เปิดหน้าสถานที่บน Google Maps (ผู้ใช้กดดูรีวิวเองที่นั่น)"""
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": 1, "query": f"{name} {lat:.6f},{lon:.6f}"}, quote_via=quote
    )


def directions_url(origin: tuple[float, float], dest: tuple[float, float]) -> str:
    """ปุ่ม 'นำทางด้วย Google Maps' จากที่พักไปสถานที่"""
    return "https://www.google.com/maps/dir/?" + urlencode(
        {
            "api": 1,
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{dest[0]:.6f},{dest[1]:.6f}",
            "travelmode": "driving",
        }
    )
