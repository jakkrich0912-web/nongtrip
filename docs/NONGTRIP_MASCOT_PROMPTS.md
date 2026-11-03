# แนวทางแก้สีหน้าน้องทริปเพิ่มเติม

เอกสารนี้เป็นแม่แบบสำหรับทำสีหน้าเพิ่มเติม ไม่ใช่บันทึก prompt แบบคำต่อคำของการสร้างไฟล์ทุกภาพ

ใช้ `apps/web/src/assets/mascot/front.webp` เป็นภาพอ้างอิง และสร้างแยกหนึ่งสีหน้าต่อคำขอ:

> Edit only the facial expression of the supplied orange explorer cat. Preserve its original 3D plush style, green bucket hat with red map pin, ears, whiskers, camera, hands, backpack, body, lighting, framing, and transparent background. Keep every part in the original position. Change only the face within original-image coordinates x=60–340, y=140–300. Expression: [describe one expression]. Do not add text, a new pose, props, or a background.

ระบุซ้าย/ขวาจากมุมของตัวละครเมื่อขอขยิบตา รายการสีหน้าและชื่อไฟล์อยู่ใน `NONGTRIP_MASCOT.md`

ผลจากการสร้างภาพอย่างเดียวไม่รับประกันตำแหน่งพิกเซล ต้องนำเฉพาะส่วนใบหน้ามาประกอบบนต้นฉบับด้วย `scripts/build_mascot_expressions.py` แล้วรัน `--validate` ทุกครั้ง

`scripts/mascot-expression-inputs.json` เป็นตัวอย่างรูปแบบ input ให้เปลี่ยน `path` เป็นตำแหน่งภาพแก้ใหม่ของคุณก่อนใช้ `--inputs` ส่วนการตรวจชุดที่ส่งมอบใช้ `--validate` ได้ทันที ไม่ต้องมีไฟล์ภาพระหว่างทาง
