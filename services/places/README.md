# services/places

ค้นที่พักและสถานที่รอบจุด: เรียก OpenStreetMap รวมกับสถานที่ที่ตรวจที่มาแล้ว เรียงใกล้ไปไกล รัศมีไม่เกิน 30 กม. มีแคชและหน่วงเวลาตามข้อจำกัดของบริการสาธารณะ

ใช้ไลบรารีมาตรฐานของ Python อย่างเดียว (ไม่ต้องติดตั้งอะไรเพิ่ม)

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `search.py` | `PlacesService`: `find_lodging`, `nearby`, `lodgings_near` (บังคับรัศมี ตัดซ้ำ เรียงระยะ) |
| `osm.py` | ตัวเรียก Overpass (สถานที่รอบจุด) และ Nominatim (ค้นที่พักจากชื่อ) |
| `fetch.py` | HTTP client: User-Agent, หน่วง Nominatim 1.1 วินาที, แปลงข้อผิดพลาดเป็น `UpstreamError` |
| `cache.py` | แคช JSON มีอายุ (ค่าเริ่มต้น 7 วัน) |
| `verified.py` | โหลดสถานที่ที่ตรวจที่มาแล้วจาก `data/` |
| `geo.py` | ระยะเส้นตรง (haversine) และลิงก์ Google Maps |
| `models.py` | รูปแบบข้อมูลที่คืน |
| `provinces.py` | รายชื่อ 77 จังหวัด |
| `data/` | ข้อมูลที่ตรวจที่มาแล้ว (ดู `docs/DATA_SOURCES.md`) |

## ตัวอย่าง

```python
from services.places import PlacesService

svc = PlacesService()
svc.find_lodging("โรงแรมตัวอย่าง เชียงใหม่")["items"]     # ให้ผู้ใช้เลือกที่พัก
res = svc.nearby(18.7883, 98.9853, radius_km=30, limit=20)  # เรียงใกล้ไปไกล
res.to_dict()["items"][0]["directions_url"]
svc.lodgings_near(18.7883, 98.9853)                       # ผู้ที่ยังไม่ได้จอง
```

ตัวแปร env ที่เกี่ยวข้อง: `OSM_LIVE` (0 = ปิด OSM ใช้เฉพาะข้อมูลที่ตรวจแล้ว), `PLACES_CACHE_DIR` (โฟลเดอร์แคชบนดิสก์ ถ้าไม่ตั้งจะแคชในหน่วยความจำ)

## ทดสอบ

`python -m pytest services/places -q` เทสต์ใช้ตัวจำลอง OSM ไม่เรียกเน็ตจริง

## สถานะ

บริการค้นเสร็จพร้อมเทสต์ ยังไม่ได้ลองกับ OpenStreetMap จริงจากเครื่องที่ต่อเน็ตได้ (ดู `docs/RUNBOOK.md`)
