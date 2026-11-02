# RUNBOOK: วิธีรันและแก้ปัญหา

> สถานะ: อยู่ระหว่างพัฒนา ส่วนที่ยังไม่มีโค้ดจะเขียนเมื่อบริการพร้อม

## เตรียมเครื่อง

1. ติดตั้ง Python 3.12 และ Docker Desktop
2. `copy .env.example .env` แล้วใส่ค่าตามต้องการ (ไม่ใส่คีย์ LLM ก็รันได้ด้วยโหมดสำรอง `LLM_PROVIDER=mock`) ใส่ `SESSION_SECRET` เป็นข้อความสุ่มยาวๆ ด้วย ถ้าเว้นว่าง ระบบสุ่มใหม่ทุกครั้งที่เริ่ม ทำให้ทุกคนถูกล็อกเอาต์เมื่อรีสตาร์ต

## รันทั้งระบบ (Docker)

```
make up        # หรือ docker compose up -d --build --wait
make smoke     # ทดสอบเร็วว่าตอบได้
make down
```

เปิดหน้าเว็บที่ http://localhost:8080 (เปลี่ยนพอร์ตด้วย `WEB_PORT` ใน `.env`) มี 2 คอนเทนเนอร์:

| บริการ | หน้าที่ | สร้างจาก |
|---|---|---|
| `web` | nginx เสิร์ฟหน้าเว็บที่ build แล้ว และส่งต่อ `/api/` ไปที่ `api` (ไม่พักข้อมูล เพื่อให้แชต SSE ไหลทันที) | `apps/web/Dockerfile` |
| `api` | API กลางพร้อมบริการค้นสถานที่ ไม่เปิดพอร์ตออกนอก เข้าได้ผ่าน `web` เท่านั้น | `services/api/Dockerfile` |

ข้อมูลที่ต้องอยู่รอด (ฐานข้อมูลผู้ใช้ SQLite และแคชค้นหา) เก็บใน volume ชื่อ `nongtrip-data` ที่ `/data` ในคอนเทนเนอร์ `api` `make down` ไม่ลบข้อมูลนี้ ถ้าอยากเริ่มใหม่หมดใช้ `docker compose down -v`

หมายเหตุ

- คุกกี้เซสชันตั้งเป็น Secure ตามค่าเริ่มต้น (`SESSION_SECURE=1`) เข้าที่ `http://localhost` ใช้ได้ปกติ แต่ถ้าเข้าด้วยชื่ออื่นบน http (เช่น IP ของเครื่อง) ให้ตั้ง `SESSION_SECURE=0` ใน `.env` และตอนใช้จริงต้องมี https
- แก้โค้ดแล้วต้อง `make up` อีกครั้งเพื่อ build ภาพใหม่ ตอนพัฒนาที่ต้องเห็นผลทันทีให้รันแบบข้างล่าง (ไม่ใช้ Docker) จะเร็วกว่า
- ค่าใน `.env` ส่งเข้าคอนเทนเนอร์ `api` ยกเว้น `DB_PATH` กับ `PLACES_CACHE_DIR` ที่ถูกบังคับให้ชี้ไป volume
- ถ้ากด `make up` แล้วค้าง ดู log ด้วย `make logs` หรือ `make logs s=api`

## รันตอนพัฒนา (ไม่ใช้ Docker)

```
python -m uvicorn services.api.main:app --port 8000
cd apps/web && npm install && npm run dev      # http://localhost:5173 (ส่งต่อ /api ไปพอร์ต 8000 ให้เอง)
```

ตอนพัฒนาบน http ตั้ง `SESSION_SECURE=0` ใน `.env`

## รันเทสต์

```
make test
```

## ลองค้นกับ OpenStreetMap จริง

```
python scripts/try_places.py ที่พัก "ชื่อโรงแรม เชียงใหม่"
python scripts/try_places.py รอบจุด 18.7883 98.9853
python scripts/try_places.py หมุด 18.7883 98.9853
```

## เตรียมสแนปช็อต OpenStreetMap (ทำก่อนวันเดโม ครั้งเดียว)

ใช้เป็นตัวสำรองตอนอินเทอร์เน็ตที่ห้องเดโมเข้า Overpass ไม่ได้ ต้องรันบนเครือข่ายที่เข้า Overpass ได้ (ลองฮอตสปอตมือถือถ้าเน็ตบ้านไม่ผ่าน)

```
python scripts/prefetch_osm.py --region เหนือ    # ลองภาคเดียวก่อน
python scripts/prefetch_osm.py                   # ทั้งประเทศ รันซ้ำได้ ข้ามจังหวัดที่เสร็จแล้ว
```

ดูบรรทัด "น่าสงสัย" ตอนท้าย จังหวัดที่ได้น้อยกว่า 10 แห่งแปลว่าหาเขตจังหวัดไม่เจอ แล้ว commit โฟลเดอร์ `services/places/data/osm_snapshot/`

## สร้างคลังความรู้สำหรับ RAG (ครั้งเดียว แล้วรันซ้ำเมื่อมีสถานที่เพิ่ม)

ดึงข้อความส่วนนำของบทความ Wikipedia ของสถานที่ที่ตรวจที่มาแล้วแต่ละแห่ง (ดู `docs/RAG_PLAN.md` ข้อ 3) ต้องรันบนเครือข่ายที่เข้า Wikipedia ได้ ใช้เวลาราว 5-10 นาทีทั้งประเทศ

```
python scripts/build_knowledge.py --region เหนือ   # ลองภาคเดียวก่อน
python scripts/build_knowledge.py                  # ทุกจังหวัด รันซ้ำได้ ข้ามจังหวัดที่มีไฟล์แล้ว
python scripts/build_knowledge.py --check          # ตรวจไฟล์ที่มี ไม่ต้องใช้เน็ต
```

อ่านท้ายผลลัพธ์: "ให้คนตรวจ" คือบทความที่ชื่อไม่ตรงสถานที่ ถ้าเห็นว่าผิดแห่งให้ลบไฟล์จังหวัดนั้นแล้วแจ้ง Jakkrich ก่อน commit โฟลเดอร์ `services/places/data/knowledge/` ข้อความมาจาก Wikipedia ภายใต้ CC BY-SA 4.0 หน้าเว็บต้องแสดงที่มาเมื่อใช้

วัดตัวค้นคืนกับชุดคำถาม (ไม่ต้องใช้เน็ต ตัวเลข Hit@3 ที่ขึ้นสไลด์ต้องมาจากคลังจริง):

```bash
python scripts/eval_retrieval.py                                   # ชุดตัวอย่างในเทสต์
python scripts/eval_retrieval.py --docs services/places/data/knowledge --golden tests/rag/golden.json
```

## เปิดโหมด LLM

1. ใน `.env` ตั้ง `LLM_PROVIDER=anthropic` (หรือ `openai`) ใส่ `ANTHROPIC_API_KEY` (หรือ `OPENAI_API_KEY`) และ `LLM_MODEL` ให้ครบ
2. มีคลังความรู้ที่ `services/places/data/knowledge/` (สร้างด้วย `python scripts/build_knowledge.py` ต้องเข้า Wikipedia ได้)
3. รัน API แล้วเปิด `/api/health` ดู `rag`: `{"docs": จำนวนก้อน, "llm": true}` ถ้า `llm` เป็น `false` แปลว่าตั้งค่าไม่ครบ ระบบอยู่โหมดกฎ
4. ถามเรื่องที่ในคลังมี เช่น ประวัติวัด แล้วดู event สุดท้าย `done.mode` ต้องเป็น `llm` และมี event `sources` ถ้าเป็น `rule` ตลอด ดูว่าคลังมีก้อนของสถานที่นั้นไหม
5. ถ้า LLM ตอบผิดกฎ ด่านตรวจจะทิ้งคำตอบและตอบโหมดกฎพร้อมบรรทัด `หมายเหตุ:` ไม่ต้องทำอะไร คีย์ไม่ถูกเขียนลง log และไม่ปรากฏในข้อความผิดพลาด
6. ตรวจว่าคีย์และรุ่นใช้ได้จริงก่อนเปิดระบบ: `python scripts/check_llm.py` (อ่านจาก `.env` เรียก LLM 1 ครั้ง ไม่พิมพ์คีย์) รหัสออก 0 = ใช้ได้, 1 = เรียกไม่สำเร็จ (ตรวจคีย์ ชื่อรุ่น เครดิต เน็ต), 2 = ตั้งค่าไม่ครบ
7. วัดผลครบวงจรกับ LLM จริง (RAG_PLAN ขั้น 6): `python scripts/eval_rag.py --docs services/places/data/knowledge --golden tests/rag/golden_e2e.json --sleep 1 --out ผลวัด.json` (ชุดนี้ 200 ข้อ มีชนิดคำถามครบ ส่วน `tests/rag/golden.json` ใช้กับ `scripts/eval_retrieval.py` ที่วัดเฉพาะตัวค้นคืน) แล้วนำผลลง `docs/COVERAGE.md` พร้อมวันที่และรุ่นโมเดล ถ้าไม่ใส่ `--docs` และ `--golden` สคริปต์ใช้ชุดตัวอย่างในเทสต์ซึ่งไม่ใช่ผลวัดจริง และ `--mock` ไว้ตรวจว่าสคริปต์ทำงานเท่านั้น

## เช็กก่อนวันเดโม

- ลองค้นที่พักจริงบนเครื่องที่ใช้เดโม ด้วยอินเทอร์เน็ตที่จะใช้จริง (OpenStreetMap ต้องใช้เน็ต)
- หน้าเว็บไม่มีป้ายบอกโหมด ให้เช็กด้วย `python scripts/check_llm.py` และดู `/api/health` ว่า `rag.llm` เป็น `true` ห้ามพูดในเดโมว่าใช้ LLM ถ้า `rag.llm` เป็น `false` (ระบบอยู่โหมดกฎ)
- เตรียมวิดีโอสำรองเผื่อเน็ตล่ม

## ปัญหาที่พบบ่อย

| อาการ | สาเหตุ | แก้ |
|---|---|---|
| `make up` ได้ error ว่า build ไม่ผ่านที่ขั้น pull image | Docker Desktop ยังไม่เปิด หรือเน็ตเข้า Docker Hub ไม่ได้ | เปิด Docker Desktop รอจนขึ้นว่า running แล้วลองใหม่ |
| หน้าเว็บขึ้นแต่ทุกอย่างตอบว่าระบบไม่เปิดใช้ | คอนเทนเนอร์ `api` ยังไม่พร้อมหรือล้ม | `docker compose ps` แล้ว `make logs s=api` |
| ค้นชื่อที่พักไม่เจอ | OSM ไม่มีชื่อนั้น หรือถูกจำกัดความถี่ | ใช้ปักหมุดแทน รอสักครู่แล้วลองใหม่ |
| ผลค้นช้ามาก | Overpass สาธารณะแน่น | รอ หรือใช้ข้อมูลที่แคชไว้ |
| คาเฟ่ไม่มีเวลาเปิด | OSM ไม่มีข้อมูลนี้ | เป็นเรื่องปกติ ระบบแสดง "ไม่ทราบ" |
