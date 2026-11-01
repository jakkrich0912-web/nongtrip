# Git flow

- มี 2 branch หลัก
  - `main` คือรุ่นที่นิ่งแล้ว ใช้ส่งสอบ/เดโม ห้าม push ตรง
  - `develop` คือที่รวมงานระหว่างพัฒนา ห้าม push ตรง
- แตก branch จาก `develop` ชื่อ `feature/<ชื่อสั้น>` `fix/<ชื่อสั้น>` หรือ `docs/<ชื่อสั้น>` แล้วเปิด PR เข้า `develop` (ใช้ Squash merge)
- เมื่อ `develop` ใช้งานได้และเทสต์ผ่าน เปิด PR จาก `develop` เข้า `main` (ใช้ Create a merge commit ไม่ใช้ Squash เพื่อไม่ให้สองสายประวัติไม่ตรงกัน)
- แก้ด่วนบน `main`: แตก `fix/<ชื่อ>` จาก `main` เปิด PR เข้า `main` แล้วเปิด PR เอาการแก้นั้นเข้า `develop` ตามด้วย
- ข้อความ commit และชื่อ PR ใช้รูปแบบ `type(scope): ทำอะไร` เช่น `feat(places): ค้นสถานที่ในรัศมี 30 กม.`
  type ที่ใช้: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- ก่อนเปิด PR: `make test` ผ่าน และกรอก `.github/pull_request_template.md` ครบ
- PR ต้องผ่าน CI และมีคนรีวิวอย่างน้อย 1 คนก่อน merge
- ถ้าแก้ `docs/CONTRACT.md` ต้องเพิ่มแถวใน Changelog และแจ้งอีกคนทันที
- ห้าม commit `.env`, API key, `data/` และไฟล์เกิน 5 MB
- เช็กชื่อผู้เขียน commit ก่อน push ทุกครั้ง: `git log -1 --format='%an <%ae>'`
- ช่วงใกล้สอบ (freeze): ไม่เพิ่มฟีเจอร์ใหม่ แก้บั๊กเท่านั้น และให้ `main` เป็นรุ่นที่ใช้เดโม

## ตั้งค่า branch protection บน GitHub (ทำครั้งเดียว)

Settings > Branches > Add rule สำหรับ `main` และ `develop` (ทั้งสอง branch): เปิด "Require a pull request before merging", "Require status checks to pass" (เลือก `structure` และ `test`) และ "Require review from Code Owners"
