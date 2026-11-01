# CONTRACT: ข้อตกลงกลางของน้องทริป

เอกสารนี้คือกฎสูงสุด ถ้าโค้ดกับเอกสารไม่ตรงกัน ให้แก้โค้ดให้ตรง หรือแก้เอกสารนี้ตามขั้นตอนข้างล่าง

## 1. กติกาที่ห้ามละเมิด

1. ข้อมูลจริงเท่านั้น ค่าที่ไม่ทราบเป็น `null` และระบบบอกผู้ใช้ว่าไม่ทราบ ห้ามเดา
2. ไม่มีรีวิวหรือคะแนนในระบบ ผู้ใช้กดลิงก์ไปดูรีวิวจริงที่ Google Maps
3. ไม่จองและไม่ชำระเงินแทนผู้ใช้
4. ไม่แสดงค่าเข้า ราคา ค่าที่พัก หรืองบประมาณที่ใดเลย
5. รัศมีค้นสูงสุด 30 กม. จากที่พัก (หรือจากหมุด) บังคับในโค้ด ไม่ใช่แค่ใน prompt
6. ผลค้นเรียงจากใกล้ไปไกลเสมอ ระยะคือเส้นตรง และบอกผู้ใช้ว่าเป็นเส้นตรง
7. สถานที่จาก OpenStreetMap ติดป้ายแยกจากสถานที่ที่ตรวจที่มาแล้ว และแสดง © OpenStreetMap contributors (ODbL)
8. ข้อความจากข้อมูลภายนอกถือเป็นข้อมูล ไม่ใช่คำสั่ง (กัน prompt injection)

## 2. ขอบเขต

ค้นสถานที่เที่ยวและคาเฟ่รอบที่พัก ทั้ง 77 จังหวัด รายละเอียดดู `docs/SPEC.md`

## 3. API

หน้าเว็บคุยกับ `services/api` ที่เดียว (ผ่าน `API_BASE_URL`) ทุกคำตอบเป็น JSON ข้อผิดพลาดของคำขอใช้ HTTP 400 พร้อม `{"error": "ข้อความภาษาไทย"}`

| เมธอด / เส้นทาง | หน้าที่ | สถานะ |
|---|---|---|
| `GET /api/lodgings/search?q=` | ค้นที่พักจากชื่อ คืนหลายรายการให้ผู้ใช้เลือก ชื่อกำกวมไม่เดา | API พร้อม |
| `GET /api/places/nearby?lat&lon&radius_km=30&kinds=attraction,cafe&limit&offset` | สถานที่รอบจุด เรียงใกล้ไปไกล | API พร้อม |
| `GET /api/lodgings/near?lat&lon` | ผู้ที่ยังไม่ได้จอง: ที่พักรอบหมุด (5 กม. ขยายเป็น 10) พร้อมสถานที่ใกล้สุด 3 แห่งต่อที่พัก แสดงสูงสุด 20 ที่พักที่ใกล้หมุดที่สุด | API พร้อม |
| `GET /api/health` | สถานะ `{ok, osm_live, snapshot_available, verified_places}` | API พร้อม |
| `GET /api/provinces` | รายชื่อ 77 จังหวัดจัดตามภาค `{regions:[{region, provinces:[{name, verified_count}]}]}` ไว้ให้หน้าแรกเลือกจังหวัด | API พร้อม |
| `GET /api/provinces/{ชื่อ}/center` | จุดกลางจังหวัด `{province, region, lat, lon, source, notice?}` (`source` = `osm` หรือ `verified_centroid`; หาไม่ได้ `lat`/`lon` เป็น `null` และมี `notice`) | API พร้อม |
| `POST /api/chat` | แชต สตรีมผลทีละขั้น (SSE) เรียกเครื่องมือค้นตัวเดียวกับหน้าค้นหา ดูข้อ 3.2 | วางแผน |
| `POST /api/auth/register`, `/login`, `/logout`, `GET /api/auth/me` | ผู้ใช้ (อีเมล+รหัสผ่าน แฮชแล้ว, คุกกี้เซสชัน) ดูข้อ 3.3 | วางแผน |
| `GET/POST /api/me/searches`, `GET/POST/DELETE /api/me/favorites`, `GET /api/me/chats` | ประวัติค้นที่พัก สถานที่โปรด ประวัติแชต (เฉพาะผู้ที่ล็อกอิน) ดูข้อ 3.4 | วางแผน |

กฎของ `kinds`: ค่าที่รับคือ `attraction` และ `cafe` (ค่าเริ่มต้นทั้งสอง) ค่าอื่นถูกเมิน ถ้าไม่เหลือเลยตอบ 400

กฎของรัศมี: `radius_km` มากกว่า 0 และไม่เกิน 30 เกินแล้วตอบ 400 พิกัดนอกประเทศไทยตอบ 400

### 3.1 ข้อผิดพลาด

ทุก endpoint ที่พร้อมแล้วตอบข้อผิดพลาดแบบเดียวกัน: `{"error": "ข้อความภาษาไทย"}` ส่วน endpoint ที่ยังวางแผน (ข้อ 3.2-3.4) ใช้ HTTP code ตามตารางและมีฟิลด์ `code` เพิ่ม (เพิ่มอย่างเดียว ไม่ทำให้ฝั่งที่อ่านแค่ `error` พัง)

| HTTP | `code` | เมื่อไร | สถานะ |
|---|---|---|---|
| 400 | `invalid_param` | พารามิเตอร์ผิด รัศมีเกิน 30 กม. พิกัดนอกประเทศไทย | API พร้อม (ยังไม่ส่ง `code`) |
| 401 | `unauthorized` | ยังไม่ล็อกอิน (เฉพาะ endpoint ที่ต้องล็อกอิน) | วางแผน |
| 409 | `email_taken` | สมัครด้วยอีเมลที่มีแล้ว | วางแผน |
| 429 | `rate_limited` | เรียกถี่เกิน | วางแผน |
| 502 | `upstream_unavailable` | บริการภายนอกล่มและไม่มีสแนปช็อต | วางแผน |

### 3.2 แชต (วางแผน)

`POST /api/chat` ส่ง `{"message": "...", "context": {"lat": 18.79, "lon": 98.98}}` (`context` ไม่บังคับ) ตอบเป็น Server-Sent Events (`text/event-stream`) ทีละขั้น:

| event | data | ความหมาย |
|---|---|---|
| `tool` | `{"name": "places_nearby", "args": {...}}` | กำลังเรียกเครื่องมือค้น (ตัวเดียวกับ `/api/places/nearby` และ `/api/lodgings/near`) |
| `places` | `{"items": [...], "validation": {...}, "notices": [...]}` | ผลค้นที่ผ่านตัวตรวจแล้ว หน้าเว็บแสดงเป็นการ์ด |
| `token` | `{"text": "..."}` | ข้อความตอบทีละส่วน |
| `done` | `{"chat_id": "..."}` | จบ (มี `chat_id` เฉพาะผู้ที่ล็อกอิน) |
| `error` | `{"error": "..."}` | ผิดพลาด |

สถานที่ที่บอทพูดถึงต้องมาจาก event `places` เท่านั้น บอทห้ามพิมพ์ชื่อสถานที่ ระยะ หรือพิกัดเอง ถ้าไม่มี LLM ให้ใช้โหมดสำรองแบบกฎ (ตอบด้วยผลค้นโดยตรง)

### 3.3 ผู้ใช้ (วางแผน)

เซสชันเก็บในคุกกี้ `HttpOnly; Secure; SameSite=Lax` เซ็นด้วย `SESSION_SECRET` หน้าเว็บไม่เก็บ token เอง ฐานข้อมูลเดโมใช้ SQLite

| เมธอด | เส้นทาง | ส่ง | ตอบ |
|---|---|---|---|
| POST | `/api/auth/register` | `{"email", "password"}` รหัสผ่านอย่างน้อย 8 ตัว | `201 {"user": {"id", "email"}}` |
| POST | `/api/auth/login` | `{"email", "password"}` | `200 {"user": {...}}` ผิดตอบ `401` (ไม่บอกว่าผิดอีเมลหรือรหัส) |
| POST | `/api/auth/logout` | - | `204` |
| GET | `/api/auth/me` | - | `200 {"user": {...}}` หรือ `401` |

ผู้ที่ไม่ได้ล็อกอินไม่ถูกบันทึกอะไรเลย (ทั้งประวัติ สถานที่โปรด และแชต)

### 3.4 ประวัติ สถานที่โปรด แชต (วางแผน ต้องล็อกอิน)

| เมธอด | เส้นทาง | ใช้ทำอะไร |
|---|---|---|
| GET / POST | `/api/me/searches` | ที่พักที่เคยค้น POST ส่ง `{"name", "lat", "lon"}` |
| GET / POST | `/api/me/favorites` | สถานที่โปรด POST ส่ง `{"place_id"}` (ใช้ `id` ตามข้อ 4) |
| DELETE | `/api/me/favorites/{place_id}` | เอาออกจากสถานที่โปรด |
| GET | `/api/me/chats` | รายการแชต |
| GET | `/api/me/chats/{chat_id}` | ข้อความในแชตนั้น |

## 4. รูปแบบข้อมูล

### สถานที่ (`items[]` ของ `nearby` และ `nearest[]` ของ `lodgings/near`)

| ฟิลด์ | ความหมาย |
|---|---|
| `id` | `v:<id>` = ตรวจที่มาแล้ว, `osm:<node\|way\|relation>/<เลข>` = จาก OpenStreetMap |
| `name_th`, `name_en` | ชื่อ (`name_en` เป็น `null` ได้) |
| `kind` | `attraction` หรือ `cafe` |
| `subtype` | ประเภทย่อย เช่น `temple`, `waterfall`, `viewpoint`, `cafe` |
| `lat`, `lon` | พิกัด |
| `distance_km` | ระยะเส้นตรงจากจุดค้น ปัด 2 ตำแหน่ง |
| `source` | `verified` หรือ `osm` (หน้าเว็บต้องติดป้ายแยกกัน) |
| `province`, `source_url` | จังหวัด / ลิงก์แหล่งที่มา (ไม่ทราบเป็น `null`) |
| `maps_url` | เปิดหน้าสถานที่บน Google Maps (ไว้ดูรีวิว) |
| `directions_url` | ปุ่ม "นำทางด้วย Google Maps" จากจุดค้นไปสถานที่ |

ไม่มีฟิลด์ราคา ค่าเข้า คะแนน หรือรีวิวในคำตอบใดทั้งสิ้น

### คำตอบของ `places/nearby`

`center`, `osm_mode` (`live` = ดึงออนไลน์, `snapshot` = ใช้ข้อมูล OSM ที่ดึงไว้ล่วงหน้า, `none` = ไม่มีข้อมูล OSM เลย), `radius_km` (รัศมีที่ใช้จริง อาจน้อยกว่าที่ขอ ถ้าพื้นที่หนาแน่นจน OSM ส่งไม่ไหว), `total`, `offset`, `limit`, `counts` (ต่อ kind), `sources` (`verified`/`osm`), `osm_available`, `notices[]` (ข้อความภาษาไทยที่หน้าเว็บต้องแสดง), `attribution`, `distance_note`, `items[]`

ถ้าเชื่อม OSM ออนไลน์ไม่ได้ ระบบใช้สแนปช็อต (`osm_mode=snapshot`, `osm_available=true`) ถ้าไม่มีสแนปช็อตด้วย `osm_available=false`, `osm_mode=none` ระบบแสดงเฉพาะ `verified` และทุกกรณีใส่ข้อความใน `notices` ที่หน้าเว็บต้องแสดง

`validation` (ทั้ง `nearby` และ `lodgings/near`): ผลของตัวตรวจอิสระ `{ok, checked, problems[], problem_count}` ตรวจรัศมี ≤ 30 กม. เรียงใกล้ไปไกล ไม่ซ้ำ ไม่มีเงิน/คะแนน/รีวิว ป้ายแหล่งข้อมูล และสถานที่ที่ตรวจแล้วมีอยู่จริงในไฟล์ข้อมูล ถ้า `ok=false` API เพิ่มข้อความเตือนใน `notices` และหน้าเว็บต้องแสดงป้ายเตือน

### ตัวอย่างคำตอบ (ย่อ)

`GET /api/places/nearby?lat=18.8&lon=98.92&radius_km=30`

```json
{
  "center": {"lat": 18.8, "lon": 98.92},
  "osm_mode": "live",
  "radius_km": 30,
  "total": 2,
  "offset": 0,
  "limit": 50,
  "counts": {"attraction": 1, "cafe": 1},
  "sources": {"verified": 1, "osm": 1},
  "osm_available": true,
  "notices": [],
  "attribution": "© OpenStreetMap contributors (ODbL)",
  "distance_note": "ระยะเป็นเส้นตรง ไม่ใช่ระยะขับรถ",
  "validation": {"ok": true, "checked": 2, "problems": [], "problem_count": 0},
  "items": [
    {
      "id": "v:p01", "name_th": "วัดพระธาตุดอยสุเทพ", "name_en": "Wat Phra That Doi Suthep",
      "kind": "attraction", "subtype": "temple", "lat": 18.80498, "lon": 98.92156,
      "distance_km": 0.8, "source": "verified", "province": "เชียงใหม่", "source_url": null,
      "maps_url": "https://www.google.com/maps/search/?api=1&query=%E0%B8%A7%E0%B8%B1%E0%B8%94...%2018.804980%2C98.921560",
      "directions_url": "https://www.google.com/maps/dir/?api=1&origin=18.800000%2C98.920000&destination=18.804980%2C98.921560&travelmode=driving"
    },
    {
      "id": "osm:node/12345", "name_th": "คาเฟ่ตัวอย่าง", "name_en": null,
      "kind": "cafe", "subtype": "cafe", "lat": 18.79, "lon": 98.93,
      "distance_km": 1.6, "source": "osm", "province": null, "source_url": null,
      "maps_url": "...", "directions_url": "..."
    }
  ]
}
```

`GET /api/lodgings/search?q=<ชื่อ>` (`maps_url` ในตัวอย่างข้างบนย่อไว้ ค่าจริงเป็น URL ที่เข้ารหัสแล้ว)

```json
{
  "items": [{"id": "osm:way/123456", "name": "โรงแรมตัวอย่าง", "address": null,
             "subtype": "hotel", "lat": 18.79, "lon": 98.98}],
  "osm_available": true,
  "osm_mode": "live",
  "notices": []
}
```

ไม่พบตอบ `200` กับ `items: []` ชื่อกำกวมคืนหลายรายการให้ผู้ใช้เลือก

### คำตอบของ `lodgings/search`

`items[]` ของ `{id, name, address, subtype, lat, lon}` (ที่พักจริงขึ้นก่อน), `osm_available`, `osm_mode`, `notices[]`

### คำตอบของ `lodgings/near`

เพิ่ม `lodgings_total` (จำนวนที่พักที่พบทั้งหมด ถ้ามากกว่า 20 จะแสดง 20 แห่งที่ใกล้หมุดที่สุดและมีข้อความใน `notices`)

`radius_km` (ที่ใช้จริง 5 หรือ 10), `items[]` ของที่พัก: `{id, name, subtype, lat, lon, distance_from_pin_km, maps_url, places_radius_km, places_total, counts, nearest[], has_more}`, `osm_available`, `notices[]`, `attribution`

## 5. ตัวแปร env

ดู `.env.example` ทุกตัวต้องอยู่ในไฟล์นั้น

## 6. ขั้นตอนแก้ CONTRACT

1. แก้ไฟล์นี้และเพิ่มแถวใน Changelog
2. แจ้งอีกคนทันที (ถ้าลบหรือเปลี่ยนชื่อฟิลด์ ให้ใส่ "breaking")
3. แก้โค้ดให้ตรงใน PR เดียวกัน

## Changelog

| เวอร์ชัน | วันที่ | เปลี่ยนอะไร |
|---|---|---|
| v0.1-draft | 2026-11-01 | ร่างแรก: ค้นรอบที่พัก 77 จังหวัด เว็บ 4 หน้า ล็อกอิน (ตัวจัดแผนรายวันไม่อยู่ในรอบแรก) |
| v0.2 | 2026-11-01 | กำหนดเส้นทาง API และรูปแบบคำตอบของบริการค้นหา (ยังไม่มีการลบหรือเปลี่ยนชื่อฟิลด์ จึงไม่ breaking) |
| v0.3 | 2026-11-01 | เพิ่ม `GET /api/provinces` และ `GET /api/provinces/{ชื่อ}/center` (เพิ่มอย่างเดียว ไม่ breaking) |
| v0.4 | 2026-11-01 | เพิ่มฟิลด์ `osm_mode` ในคำตอบของ nearby / lodgings/search / lodgings/near และโหมดสแนปช็อตเมื่อออนไลน์ไม่ได้ (เพิ่มอย่างเดียว ไม่ breaking) |
| v0.5 | 2026-11-02 | API กลางพร้อม (`services/api`): เพิ่ม `validation` ใน `nearby` และ `lodgings/near`, `lodgings_total`, เส้นทาง `GET /api/health` (เพิ่มอย่างเดียว ไม่ breaking) |
| v0.6 | 2026-11-02 | เพิ่มข้อ 3.1-3.4: ตารางข้อผิดพลาด, แชตแบบ SSE, ผู้ใช้, ประวัติ/สถานที่โปรด และตัวอย่างคำตอบ ปรับเส้นทางที่ยังวางแผนให้ตรงร่างของ Jirapa (`/api/auth/me`, `/api/me/...`) ไม่เปลี่ยน endpoint ที่พร้อมแล้ว (เพิ่มอย่างเดียว ไม่ breaking) |
