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

## 3. API (ร่าง v0.2 รอตกลงก่อนเขียนโค้ด)

หน้าเว็บคุยกับ `services/api` ที่เดียว ทุก endpoint ขึ้นต้นด้วย `/api` รับส่ง JSON (UTF-8) ยกเว้นแชตที่สตรีม

### 3.1 กติการ่วม

- พิกัดเป็นทศนิยมองศา WGS84 ชื่อฟิลด์ `lat`, `lon`
- ระยะเป็นกิโลเมตร ทศนิยม 1 ตำแหน่ง ฟิลด์ `distance_km` วัดเป็นเส้นตรง
- `radius_km` ที่เกิน 30 ระบบลดเหลือ 30 และบอกใน `meta.radius_km` (ไม่ error)
- ทุกผลค้นมี `meta` บอกที่มา: `{"radius_km": 30, "sources": ["verified", "osm"], "osm_available": true, "notes": []}`
  - `osm_available: false` เมื่อเรียก OpenStreetMap ไม่ได้ (เน็ตหลุด, โดนจำกัดความถี่, `OSM_LIVE=0`) หน้าเว็บต้องบอกผู้ใช้ว่าตอนนี้แสดงเฉพาะข้อมูลที่ตรวจที่มาแล้ว
  - `notes` คือข้อความที่ระบบอยากให้ผู้ใช้รู้ เช่น "ขยายรัศมีเป็น 10 กม. เพราะไม่พบที่พักใน 5 กม."
- ผลค้นต้องผ่านตัวตรวจก่อนส่ง ถ้าไม่ผ่านตอบ `502` พร้อม `{"error": "validation_failed"}`

รูปแบบ error ทุกตัว:

```json
{ "error": "invalid_coords", "message": "lat ต้องอยู่ระหว่าง -90 ถึง 90" }
```

| HTTP | error | เมื่อไร |
|---|---|---|
| 400 | `invalid_coords`, `invalid_param` | พารามิเตอร์ผิด |
| 401 | `unauthorized` | ยังไม่ล็อกอิน (เฉพาะ endpoint ที่ต้องล็อกอิน) |
| 409 | `email_taken` | สมัครด้วยอีเมลที่มีแล้ว |
| 429 | `rate_limited` | เรียกถี่เกิน |
| 502 | `upstream_unavailable`, `validation_failed` | บริการภายนอกล่ม หรือผลไม่ผ่านตัวตรวจ |

### 3.2 ค้นที่พักจากชื่อ

`GET /api/lodging/search?q=<ชื่อ>&province=<จังหวัด>`

`province` ไม่บังคับ ใช้ช่วยแยกชื่อซ้ำ คืนสูงสุด 10 รายการให้ผู้ใช้เลือก ชื่อกำกวมไม่เลือกให้เอง

```json
{
  "items": [
    { "id": "osm:way/123456", "name": "โรงแรมตัวอย่าง", "lat": 18.79, "lon": 98.98,
      "province": "เชียงใหม่", "address": null, "source": "osm" }
  ],
  "meta": { "osm_available": true, "notes": [] }
}
```

ไม่พบตอบ `200` กับ `items: []`

### 3.3 ค้นสถานที่รอบจุด

`GET /api/places/nearby?lat=<>&lon=<>&radius_km=30&category=<ประเภท>`

`radius_km` ค่าเริ่มต้น 30 สูงสุด 30 `category` ไม่บังคับ ใส่ได้หลายค่าคั่นด้วย `,` (เช่น `temple,cafe`) ผลเรียงใกล้ไปไกลเสมอ

```json
{
  "origin": { "lat": 18.7965, "lon": 98.9677 },
  "items": [ { "...รูปแบบสถานที่ ข้อ 4..." } ],
  "meta": { "radius_km": 30, "sources": ["verified", "osm"], "osm_available": true, "notes": [] }
}
```

### 3.4 ค้นที่พักรอบหมุด (ยังไม่ได้จองที่พัก)

`GET /api/lodging/nearby?lat=<>&lon=<>&preview=3`

เริ่มที่ 5 กม. ถ้าไม่พบขยายเป็น 10 กม. อัตโนมัติและใส่ข้อความใน `meta.notes` ไม่ขยายเกิน 10 กม. แต่ละที่พักแนบสถานที่เที่ยวใกล้สุด `preview` แห่ง (ค่าเริ่มต้น 3) และจำนวนทั้งหมดในรัศมี 30 กม. ของที่พักนั้น

ระบบดึงสถานที่ทั้งพื้นที่จาก OpenStreetMap ครั้งเดียว แล้วคำนวณระยะของแต่ละที่พักในเครื่อง (ตาม SPEC)

```json
{
  "items": [
    { "id": "osm:node/987", "name": "เกสต์เฮาส์ตัวอย่าง", "lat": 18.80, "lon": 98.97,
      "distance_km": 1.2, "source": "osm",
      "places_preview": [ { "...สถานที่ ข้อ 4..." } ],
      "places_total": 18 }
  ],
  "meta": { "radius_km": 10, "osm_available": true, "notes": ["ขยายรัศมีเป็น 10 กม. เพราะไม่พบที่พักใน 5 กม."] }
}
```

กด "ดูทั้งหมด" หน้าเว็บเรียก `/api/places/nearby` ด้วยพิกัดของที่พักนั้น

### 3.5 แชต

`POST /api/chat` ส่ง `{"message": "...", "context": {"lat": 18.79, "lon": 98.98}}` (`context` ไม่บังคับ)

ตอบเป็น Server-Sent Events (`text/event-stream`) ทีละขั้น:

| event | data | ความหมาย |
|---|---|---|
| `tool` | `{"name": "places_nearby", "args": {...}}` | กำลังเรียกเครื่องมือค้น (ตัวเดียวกับข้อ 3.2-3.4) |
| `places` | `{"items": [...], "meta": {...}}` | ผลค้นที่ผ่านตัวตรวจแล้ว หน้าเว็บแสดงเป็นการ์ด |
| `token` | `{"text": "..."}` | ข้อความตอบทีละส่วน |
| `done` | `{"chat_id": "..."}` | จบ (มี `chat_id` เฉพาะผู้ที่ล็อกอิน) |
| `error` | `{"error": "...", "message": "..."}` | ผิดพลาด |

สถานที่ที่บอทพูดถึงต้องมาจาก event `places` เท่านั้น บอทห้ามพิมพ์ชื่อสถานที่ ระยะ หรือพิกัดเอง

### 3.6 ผู้ใช้

เซสชันเก็บในคุกกี้ `HttpOnly; Secure; SameSite=Lax` เซ็นด้วย `SESSION_SECRET` หน้าเว็บไม่เก็บ token เอง

| Method | Path | ส่ง | ตอบ |
|---|---|---|---|
| POST | `/api/auth/register` | `{"email", "password"}` รหัสผ่านอย่างน้อย 8 ตัว | `201 {"user": {"id", "email"}}` |
| POST | `/api/auth/login` | `{"email", "password"}` | `200 {"user": {...}}` ผิดตอบ `401` (ไม่บอกว่าผิดอีเมลหรือรหัส) |
| POST | `/api/auth/logout` | - | `204` |
| GET | `/api/auth/me` | - | `200 {"user": {...}}` หรือ `401` |

### 3.7 ประวัติ (ต้องล็อกอิน)

| Method | Path | ใช้ทำอะไร |
|---|---|---|
| GET / POST | `/api/me/searches` | ที่พักที่เคยค้น POST ส่ง `{"name", "lat", "lon"}` |
| GET / POST | `/api/me/favorites` | สถานที่โปรด POST ส่ง `{"place_id"}` |
| DELETE | `/api/me/favorites/{place_id}` | เอาออกจากสถานที่โปรด |
| GET | `/api/me/chats` | รายการแชต |
| GET | `/api/me/chats/{chat_id}` | ข้อความในแชตนั้น |

## 4. รูปแบบข้อมูลสถานที่ (ร่าง v0.2)

```json
{
  "id": "verified:p01",
  "name_th": "วัดพระธาตุดอยสุเทพ",
  "name_en": "Wat Phra That Doi Suthep",
  "category": "temple",
  "lat": 18.80498,
  "lon": 98.92156,
  "distance_km": 0.8,
  "province": "เชียงใหม่",
  "source": "verified",
  "verified": true,
  "open": null,
  "description": null,
  "maps_url": "https://www.google.com/maps/search/?api=1&query=18.80498,98.92156",
  "directions_url": "https://www.google.com/maps/dir/?api=1&destination=18.80498,98.92156",
  "attribution": null
}
```

| ฟิลด์ | หมายเหตุ |
|---|---|
| `id` | ขึ้นต้นด้วยแหล่ง `verified:` หรือ `osm:` กันชนกันระหว่างแหล่ง |
| `name_th` | ถ้าไม่มีชื่อไทยใช้ชื่อจาก OSM ตามที่มี ไม่แปลเอง |
| `name_en`, `open`, `description`, `province` | ไม่ทราบเป็น `null` |
| `category` | หนึ่งใน `temple`, `museum`, `nature`, `activity`, `market`, `cafe`, `viewpoint`, `beach`, `other` |
| `source` | `verified` หรือ `osm` |
| `verified` | `true` เมื่อตรวจที่มาแล้ว สถานที่ `source: verified` ที่ยังไม่ตรวจเป็น `false` และหน้าเว็บติดป้าย "ยังไม่ผ่านการตรวจที่มา" |
| `attribution` | สถานที่จาก OSM เป็น `"© OpenStreetMap contributors"` |

ห้ามส่งฟิลด์ราคาหรือค่าเข้า (`cost_thb` ในไฟล์ข้อมูลต้องตัดออกก่อนส่ง) ตามข้อ 1.4

### คำถามที่ต้องตกลงกัน

1. ใช้ Server-Sent Events สำหรับแชตตามร่าง หรือ WebSocket
2. ฐานข้อมูลผู้ใช้และประวัติใช้อะไร (SQLite พอไหมสำหรับเดโม)
3. แคชผล OpenStreetMap นานเท่าไร และเก็บที่ไหน
4. `category` ของ OSM แมปจากแท็กไหน (เช่น `amenity=cafe`, `tourism=museum`, `historic=*`)

## 5. ตัวแปร env

ดู `.env.example` ทุกตัวต้องอยู่ในไฟล์นั้น

## 6. ขั้นตอนแก้ CONTRACT

1. แก้ไฟล์นี้และเพิ่มแถวใน Changelog
2. แจ้งอีกคนทันที (ถ้าลบหรือเปลี่ยนชื่อฟิลด์ ให้ใส่ "breaking")
3. แก้โค้ดให้ตรงใน PR เดียวกัน

## Changelog

| เวอร์ชัน | วันที่ | เปลี่ยนอะไร |
|---|---|---|
| v0.2-draft | 2026-11-02 | ร่าง API ละเอียด: endpoint, รูปแบบ JSON, error, แชตแบบ SSE, ผู้ใช้และประวัติ, ฟิลด์ `id` ขึ้นต้นด้วยแหล่ง, `verified`, `directions_url`, `attribution` (เพิ่มฟิลด์ ไม่ breaking) |
| v0.1-draft | 2026-11-01 | ร่างแรก: ค้นรอบที่พัก 77 จังหวัด เว็บ 4 หน้า ล็อกอิน (ตัวจัดแผนรายวันไม่อยู่ในรอบแรก) |
