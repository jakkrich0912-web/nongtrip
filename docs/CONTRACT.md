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
| `POST /api/chat` | แชต สตรีมผลทีละขั้น (SSE) เรียกเครื่องมือค้นตัวเดียวกับหน้าค้นหา ดูข้อ 3.2 | API พร้อม (โหมดกฎ) |
| `POST /api/auth/register`, `/login`, `/logout`, `GET /api/auth/me` | ผู้ใช้ (อีเมล+รหัสผ่าน แฮชแล้ว, คุกกี้เซสชัน) ดูข้อ 3.3 | API พร้อม |
| `GET/POST/DELETE /api/me/searches`, `GET/POST/DELETE /api/me/favorites`, `GET/DELETE /api/me/chats` | ประวัติค้นที่พัก สถานที่โปรด ประวัติแชต (เฉพาะผู้ที่ล็อกอิน) ดูข้อ 3.4 | API พร้อม |

กฎของ `kinds`: ค่าที่รับคือ `attraction` และ `cafe` (ค่าเริ่มต้นทั้งสอง) ค่าอื่นถูกเมิน ถ้าไม่เหลือเลยตอบ 400

กฎของรัศมี: `radius_km` มากกว่า 0 และไม่เกิน 30 เกินแล้วตอบ 400 พิกัดนอกประเทศไทยตอบ 400

### 3.1 ข้อผิดพลาด

ทุก endpoint ที่พร้อมแล้วตอบข้อผิดพลาดแบบเดียวกัน: `{"error": "ข้อความภาษาไทย"}` ส่วน endpoint ผู้ใช้/ประวัติ (ข้อ 3.3-3.4) ใช้ HTTP code ตามตารางและมีฟิลด์ `code` เพิ่ม (เพิ่มอย่างเดียว ไม่ทำให้ฝั่งที่อ่านแค่ `error` พัง)

| HTTP | `code` | เมื่อไร | สถานะ |
|---|---|---|---|
| 400 | `invalid_param` | พารามิเตอร์ผิด รัศมีเกิน 30 กม. พิกัดนอกประเทศไทย | API พร้อม (endpoint ค้นหายังไม่ส่ง `code` ส่วน endpoint ผู้ใช้ส่ง) |
| 401 | `unauthorized` | ยังไม่ล็อกอิน หรืออีเมล/รหัสผ่านไม่ถูกต้อง | API พร้อม |
| 404 | `not_found` | ไม่พบแชต (รวมถึงแชตของผู้อื่น) ทั้งตอนอ่าน ลบ และส่งต่อแชตเดิมด้วย `chat_id` | API พร้อม |
| 409 | `email_taken` | สมัครด้วยอีเมลที่มีแล้ว | API พร้อม |
| 429 | `rate_limited` | ใส่รหัสผ่านผิดครบ 5 ครั้งใน 5 นาทีต่ออีเมล หรือส่งแชตเกิน `CHAT_RATE_PER_MIN` (ค่าเริ่มต้น 20) ต่อ IP ต่อนาที | API พร้อม |
| 501 | `google_not_configured` | ยังไม่ตั้ง `GOOGLE_CLIENT_ID` จึงยังไม่เปิดล็อกอินด้วย Google | API พร้อม |
| 502 | `upstream_unavailable` | บริการภายนอกล่มและไม่มีสแนปช็อต หรือติดต่อ Google ตอนล็อกอินไม่ได้ | ล็อกอิน Google พร้อม ส่วนค้นหายังวางแผน |

### 3.2 แชต (API พร้อม โหมดกฎ ไม่ใช้ LLM)

`POST /api/chat` ส่ง `{"message": "...", "context": {"lat": 18.79, "lon": 98.98}, "chat_id": 12}` ตอบเป็น Server-Sent Events (`text/event-stream`)

| ฟิลด์ | กติกา |
|---|---|
| `message` | บังคับ 1-500 ตัวอักษร (ตัดอักขระควบคุมและช่องว่างซ้ำ ข้อความว่างตอบ 400) |
| `context` | ไม่บังคับ พิกัดหมุด/ที่พักที่ผู้ใช้เลือกไว้ ต้องอยู่ในไทย ไม่งั้น 400 |
| `chat_id` | ไม่บังคับ ต่อแชตเดิมของผู้ที่ล็อกอิน ไม่พบหรือเป็นของคนอื่นตอบ 404 ผู้ที่ไม่ล็อกอินเมิน |

ข้อความแต่ละครั้งแยกกัน (บอทไม่จำข้อความก่อนหน้า) หน้าเว็บส่ง `context` ทุกครั้งที่มีหมุด

ลำดับ event ทีละขั้น:

| event | data | ความหมาย |
|---|---|---|
| `tool` | `{"name": "places_nearby", "args": {...}}` | กำลังเรียกเครื่องมือค้น ชื่อที่เป็นไปได้: `province_center`, `lodgings_search`, `lodgings_near`, `places_nearby` |
| `places` | `{"items": [...], "validation": {...}, "notices": [...], "center", "radius_km", "total", "counts", "sources", "osm_mode", "osm_available", "attribution", "distance_note"}` | ผลค้นสถานที่ที่ผ่านตัวตรวจแล้ว หน้าเว็บแสดงเป็นการ์ด ถ้าตัวตรวจไม่ผ่าน `items` เป็น `[]` และมีข้อความเตือนใน `notices` |
| `lodgings` | `{"source": "search" \| "near", "items": [...], "notices": [...], ...}` | `search` = ผลค้นชื่อที่พัก (รูปแบบเดียวกับ `/api/lodgings/search`) `near` = ที่พักรอบหมุด (รูปแบบเดียวกับ `/api/lodgings/near`) |
| `token` | `{"text": "..."}` | ข้อความตอบทีละบรรทัด (ลงท้ายด้วย `\n`) |
| `done` | `{"chat_id": 12}` | จบ `chat_id` เป็น `null` ถ้าไม่ได้ล็อกอิน (ไม่บันทึก) |
| `error` | `{"error": "...", "code": "invalid_param" \| "internal"}` | ผิดพลาดระหว่างสตรีม (HTTP ยังเป็น 200) ไม่ส่ง `done` |

ถ้าคำขอผิดก่อนเริ่มสตรีม ตอบ HTTP 400/404/429 เป็น JSON ตามข้อ 3.1

บอทหาตำแหน่งค้นตามลำดับ: ชื่อจังหวัดในข้อความ (ค้นรอบจุดกลางจังหวัดและบอกผู้ใช้) > `context` > ชื่อที่พักในข้อความ (ถ้าพบหลายรายการหรือไม่พบ ไม่เดา ให้ผู้ใช้เลือกหรือปักหมุด) > ถามผู้ใช้ ปรับได้ด้วยข้อความ เช่น "คาเฟ่", "5 แห่ง", "ใน 10 กม." (เพดาน 30 กม. และ 10 แห่งต่อครั้ง)

สถานที่ที่บอทพูดถึงต้องมาจากผลค้นที่ผ่านตัวตรวจเท่านั้น บอทไม่พิมพ์ชื่อ ระยะ หรือพิกัดเอง ถ้าผู้ใช้ถามราคา ค่าเข้า รีวิว หรือให้จอง บอทบอกตรงๆ ว่าระบบไม่มี/ไม่ทำ ข้อความผู้ใช้และชื่อจาก OpenStreetMap เป็นข้อมูล ไม่ใช่คำสั่ง **หน้าเว็บต้องแสดง `token` และชื่อสถานที่เป็นข้อความธรรมดา ห้ามใส่เป็น HTML** ผู้ที่ไม่ล็อกอินแชตได้แต่ไม่ถูกบันทึกอะไร ผู้ที่ล็อกอินบันทึกข้อความผู้ใช้และคำตอบลงประวัติแชต (ข้อ 3.4) ส่วนโหมด LLM (ถ้าทำ) จะใช้ event ชุดเดียวกัน

### 3.3 ผู้ใช้ (API พร้อม)

เซสชันเก็บในคุกกี้ `HttpOnly; Secure; SameSite=Lax` เซ็นด้วย `SESSION_SECRET` (ไม่ตั้ง = สุ่มต่อการรัน เซสชันหายเมื่อรีสตาร์ท) อายุ 7 วัน ตอนพัฒนาบน http ตั้ง `SESSION_SECURE=0` หน้าเว็บไม่เก็บ token เอง ฐานข้อมูลใช้ SQLite (`DB_PATH` ค่าเริ่มต้น `data/nongtrip.db`) รหัสผ่านเก็บแบบแฮช scrypt

| เมธอด | เส้นทาง | ส่ง | ตอบ |
|---|---|---|---|
| POST | `/api/auth/register` | `{"email", "password"}` รหัสผ่าน 8-200 ตัว อีเมลไม่สนตัวพิมพ์ใหญ่เล็ก | `201 {"user": {"id", "email"}}` และล็อกอินให้ทันที (ตั้งคุกกี้) `409 email_taken` |
| POST | `/api/auth/login` | `{"email", "password"}` | `200 {"user": {...}}` ผิดตอบ `401` (ไม่บอกว่าผิดอีเมลหรือรหัส) |
| POST | `/api/auth/logout` | - | `204` |
| GET | `/api/auth/me` | - | `200 {"user": {...}}` หรือ `401` |
| POST | `/api/auth/google` | `{"credential": "<Google ID token>"}` (1-5000 ตัวอักษร) | `201 {"user": {...}}` เข้าครั้งแรก (สร้างบัญชีให้) `200` เข้าซ้ำ แล้วตั้งคุกกี้เซสชันเหมือนล็อกอินปกติ `401` token ใช้ไม่ได้ `409 email_taken` `429 rate_limited` `501 google_not_configured` `502 upstream_unavailable` |

**ล็อกอินด้วย Google:** หน้าเว็บใช้ Google Identity Services ขอ ID token แล้วส่งมาที่ `/api/auth/google` (ต้องมี `GOOGLE_CLIENT_ID` ที่สร้างใน Google Cloud Console และใส่ที่มาของเว็บใน Authorized JavaScript origins) หลังบ้านให้ Google ตรวจลายเซ็น แล้วตรวจเองว่า `aud` ตรงกับ `GOOGLE_CLIENT_ID` ของเรา, `iss` เป็น Google, ยังไม่หมดอายุ และอีเมลผ่านการยืนยันแล้ว บัญชี Google ใช้ `sub` เป็นตัวระบุ (เปลี่ยนอีเมลที่ Google ก็ยังเป็นคนเดิม) ไม่มีรหัสผ่านจึงล็อกอินด้วยอีเมล/รหัสผ่านไม่ได้ **ถ้าอีเมลนั้นสมัครด้วยรหัสผ่านไว้แล้ว ตอบ 409 และไม่ผูกให้เอง** เพราะตอนสมัครด้วยรหัสผ่านเรายังไม่ยืนยันอีเมล (ถ้าผูกให้ ผู้ที่สมัครอีเมลของคนอื่นไว้ล่วงหน้าจะเข้าบัญชีเดียวกับเจ้าของอีเมลได้) ตัวจำกัด: 30 คำขอต่อ IP ต่อนาที (กันถูกใช้ยิง Google)

ผู้ที่ไม่ได้ล็อกอินไม่ถูกบันทึกอะไรเลย (ทั้งประวัติ สถานที่โปรด และแชต)

### 3.4 ประวัติ สถานที่โปรด แชต (API พร้อม ต้องล็อกอิน)

| เมธอด | เส้นทาง | ใช้ทำอะไร |
|---|---|---|
| GET / POST | `/api/me/searches` | ที่พักที่เคยค้น ใหม่สุดก่อน คืน `{items:[{id, name, lat, lon, created_at}]}` POST ส่ง `{"name", "lat", "lon"}` (พิกัดต้องอยู่ในไทย, ค้นที่พักเดิมซ้ำจะยกขึ้นบนสุด, เก็บสูงสุด 100) |
| DELETE | `/api/me/searches/{id}` | ลบหนึ่งรายการ (`204`) |
| GET / POST | `/api/me/favorites` | สถานที่โปรด คืน `{items:[{id, name_th, name_en, kind, subtype, lat, lon, source, province, maps_url, saved_at}]}` POST ส่ง `{"place_id"}` ถ้าเป็น `v:` ระบบอ่านข้อมูลจากไฟล์ของเราเอง (ไม่เชื่อค่าที่ส่งมา) ถ้าเป็น `osm:` ต้องส่ง `name_th, lat, lon, kind` มาด้วย (เก็บสูงสุด 500) ตอบ `201` ใหม่ หรือ `200` ถ้ามีอยู่แล้ว |
| DELETE | `/api/me/favorites/{place_id}` | เอาออกจากสถานที่โปรด (`204`) `place_id` มี `/` ได้ เช่น `osm:node/123` |
| GET | `/api/me/chats` | รายการแชต `{items:[{id, title, created_at, updated_at, message_count}]}` ใหม่สุดก่อน |
| GET | `/api/me/chats/{chat_id}` | ข้อความในแชตนั้น `{id, title, messages:[{role, content, created_at}]}` ของผู้อื่นตอบ 404 |
| DELETE | `/api/me/chats/{chat_id}` | ลบแชต (`204`) |

แชตถูกสร้างและเพิ่มข้อความโดย `POST /api/chat` (ข้อ 3.2) ชื่อแชตคือข้อความแรกของผู้ใช้ (ตัดที่ 80 ตัวอักษร)

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
| v0.7 | 2026-11-02 | API ผู้ใช้/ประวัติ/สถานที่โปรด/แชต พร้อมใช้ (`services/api`): สมัครแล้วล็อกอินให้ทันที เพิ่ม `DELETE /api/me/searches/{id}` และ `DELETE /api/me/chats/{id}` กำหนดรูปคำตอบและเพดานจำนวน เพิ่ม 404 `not_found` (เพิ่มอย่างเดียว ไม่ breaking) |
| v0.8 | 2026-11-02 | `POST /api/chat` พร้อมใช้ (โหมดกฎ): กำหนด event `lodgings`, ฟิลด์ `chat_id` ในคำขอ, `chat_id` เป็น `null` เมื่อไม่ล็อกอิน, `rate_limited` ของแชต (เพิ่มอย่างเดียว ไม่ breaking) |
| v0.9 | 2026-11-02 | เพิ่ม `POST /api/auth/google` (ล็อกอินด้วย Google ID token), code `google_not_configured` (501), `upstream_unavailable` ใช้กับล็อกอิน Google แล้ว, ตัวแปร env `GOOGLE_CLIENT_ID` (เพิ่มอย่างเดียว ไม่ breaking) |
