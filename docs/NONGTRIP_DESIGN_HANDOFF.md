# ส่งมอบดีไซน์น้องทริป

งานต้นแบบอยู่ใน `apps/web` โดยคง React + Vite และเส้นทางค้นหา/ทริปเดิมไว้ ไม่มีการ commit, push หรือ deploy

## เปิดดู

```powershell
cd apps/web
npm install
npm run dev
```

เปิด URL ที่ Vite แสดง (ปกติ `http://localhost:5173/`)

- `/` หน้าแรกแบบเลื่อน พร้อมเดโมกดเล่นได้
- `/login` หน้าเข้าสู่ระบบเต็มจอ
- `/signup` หน้าสมัครใช้งานเต็มจอ
- `/search`, `/chat`, `/me` เชื่อมต่อจากหน้าแรก

ภาพที่ตรวจแล้วอยู่ใน `docs/design-preview/`: `landing-desktop.png`, `demo-desktop.png`, `login-desktop.png`, `landing-mobile.png`, `demo-mobile.png`, `login-mobile.png`

## ชุดมาสคอต

ไฟล์ดาวน์โหลด: [nongtrip-mascot-v2.zip](../output/nongtrip-mascot-v2.zip) มีครบ 23 สีหน้า ภาพฐาน ภาพแถบใบหน้า ตารางไฟล์ และสคริปต์ตรวจพิกเซล ดู [คู่มือมาสคอต](NONGTRIP_MASCOT.md)

## ทำจริงและตัวอย่าง

| ส่วน | สถานะ |
|---|---|
| ภาษา TH/EN | ใช้งานจริงในหน้าแรก หน้า auth และแชต จำภาษาในเครื่อง และเปลี่ยน `html lang`; ชื่อจังหวัดยังใช้ชื่อไทยจากชุดข้อมูลเดิม |
| เลือกจังหวัด/ประเภท/รัศมี | ใช้งานจริงบนข้อมูลสถานที่ที่ `verified` แล้วในโปรเจกต์ |
| ชื่อ พิกัด แหล่งที่มา จำนวนผล | มาจากข้อมูลจริงใน `services/places/data/`; ไม่มีตัวเลขสถิติหรือรีวิวแต่งขึ้น |
| ระยะทาง | คำนวณจากพิกัดด้วยฟังก์ชัน haversine เดิม เรียงจากใกล้ไปไกล แสดงว่าเป็นเส้นตรง |
| หมุดในหน้าแรก | หมุดสาธิต ไม่ใช่ที่พักจริงของผู้ใช้; เชียงใหม่ใช้จุดตัวอย่างย่านนิมมาน จังหวัดอื่นใช้พิกัดสถานที่แรกในข้อมูลจังหวัดนั้น ไม่อ้างว่าเป็นศูนย์กลางจังหวัด |
| แผนที่ | Leaflet + OpenStreetMap จริง แสดงวงรัศมีเส้นตรง 10/20/30 กม. มีเครดิตและลิงก์ ODbL; พื้นแผนที่ต้องใช้อินเทอร์เน็ต |
| บทสนทนาในกรอบหน้าแรก | ตัวอย่างสำเร็จรูป ใช้สถานที่จากผลกรองปัจจุบัน ไม่ส่งคำถามไป API |
| หน้า `/chat` | ต่อ `POST /api/chat` จริง อ่าน SSE แบบแบ่ง chunk ได้ ข้าม event ที่ไม่รู้จัก แสดง `sources` และสัญญาอนุญาต ไม่แสดงป้ายโหมดคำตอบ; ต้องเปิด API เพื่อใช้งาน |
| อีเมลเข้าสู่ระบบ/สมัคร | ต่อ API เดิม มี validation/loading/error ไม่จำลองการล็อกอินสำเร็จ; ยังไม่ได้ทดสอบด้วยบัญชีจริง |
| Google | ต่อ Google Identity Services + `/api/auth/google` แล้ว แต่ปิดปุ่มพร้อมคำอธิบายเมื่อยังไม่ตั้งค่า; ยังไม่ได้ทดสอบบัญชี Google จริง |
| มาสคอตบนหน้าเว็บ | ใช้ตัวละครต้นฉบับ พร้อมปุ่มแตะทักทายด้วยคีย์บอร์ดได้; ชุดสีหน้าใหม่ส่งแยกไว้ให้เอนจินนำไปใช้ |
| ราคา รีวิว คะแนน การจอง | ไม่มีองค์ประกอบหรือข้อมูลเหล่านี้ในหน้าที่ทำใหม่ |

แหล่งข้อมูลที่ไม่มี `license` จะไม่ถูกเดาสัญญาอนุญาตให้ หาก API ส่งมา จะแสดงตามค่าที่ได้รับ ลิงก์ภายนอกยอมรับเฉพาะ HTTP/HTTPS

Google ต้องตั้ง `VITE_GOOGLE_CLIENT_ID` ให้ฝั่งเว็บ และ `GOOGLE_CLIENT_ID` ค่าเดียวกันให้ API พร้อมลงทะเบียน origin ของเว็บใน Google Console ห้ามเก็บ secret ในตัวแปร `VITE_*` ข้อมูลเซสชันยังใช้คุกกี้ API เดิม

## โครงคอมโพเนนต์และการแบ่ง PR

เจ้าของงานเว็บ: จิราภา (`jirapa-gm`) · ผู้รีวิว: `Jakkrich`

| ชุดที่แนะนำ | ไฟล์/คอมโพเนนต์ | ขอบเขต |
|---|---|---|
| 1. โครงหน้าและภาษา | `App.jsx`, `lib/language.jsx`, `main.jsx`, `landing/SiteHeader.jsx` | เมนูบน ภาษา เส้นทาง `/signup` และการกลับขึ้นต้นหน้าเมื่อเปลี่ยนเส้นทาง |
| 2. หน้าแรกและเดโม | `pages/Home.jsx` (`Hero`, `HowItWorks`, `TrustSection`, `StartBanner`), `landing/ExploreDemo.jsx` (`DemoMap`, `DemoChat`, `PlaceSources`), `landing/Icon.jsx`, `landing.css` | ดีไซน์และปฏิสัมพันธ์ที่ใช้ข้อมูลจริงในเครื่อง |
| 3. หน้า auth | `pages/Login.jsx`, `auth-v2.css`, `lib/auth.jsx`, `lib/api.js` | login/signup เต็มจอและ Google GIS |
| 4. สัญญาแชต | `pages/Chat.jsx`, `pages/chat-v2.css`, `lib/chat.js`, `components/chat/SourceCards.jsx` และ tests | SSE, ที่มา, license, error/cancellation |
| 5. มาสคอต | `components/Mascot.jsx`, reset เฉพาะ `.mascot` ใน `styles.css`, `assets/mascot/expressions-v2/`, script และเอกสารสีหน้า | native button และชุดภาพแยก ไม่ทับต้นฉบับ |

ควรเปิด PR ตาม dependency ด้านบนและให้ Jakkrich รีวิว ไม่มีการสร้าง branch หรือ commit ในงานนี้

## การตรวจ

- Production build ผ่าน
- `npm test`: 25 tests / 5 files ผ่าน รวม stream ที่แบ่งภาษาไทยเป็น bytes, CRLF ข้าม chunk, unknown events, sources/licenses, URL safety
- ตรวจ browser จริงที่ 1440×1000 และ 390×844: ภาษา ตัวกรองจังหวัด/ประเภท/รัศมี ผลว่าง แท็บค้นหา/แชต เส้นทาง login/signup และเมนูมือถือ
- มี label ให้ icon buttons, ใช้ปุ่ม/ลิงก์จริง, `prefers-reduced-motion`, ปรับสีข้อความที่ตรวจพบคอนทราสต์ต่ำกว่า 4.5:1
- ตรวจ UI ใน browser ไม่พบ console error ระหว่างเส้นทางที่ลอง; การยืนยัน email/Google กับบัญชีจริงยังไม่อยู่ในการตรวจนี้

อ้างอิงทิศทางภาพจาก https://bebetter.education/ โดยใช้แบรนด์ มาสคอต และข้อมูลของน้องทริปเอง
