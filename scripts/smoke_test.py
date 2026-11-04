"""ทดสอบเร็วว่าระบบที่รันอยู่ตอบได้ (ใช้แต่ไลบรารีมาตรฐาน)

ใช้:
  python3 scripts/smoke_test.py                       ตรวจที่ http://localhost:8080 (หลัง make up)
  python3 scripts/smoke_test.py http://localhost:8000 ตรวจที่อยู่อื่น (เช่น API ที่รันตรงๆ ไม่ผ่านหน้าเว็บ)
ตรวจหน้าเว็บด้วยเมื่อที่อยู่นั้นเสิร์ฟหน้าเว็บ ถ้าไม่ใช่ (เช่นพอร์ต 8000) จะข้ามส่วนหน้าเว็บ
"""
import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
failed = []


def get(path: str):
    """คืน (สถานะ, เนื้อหา) ไม่โยนข้อผิดพลาดเมื่อได้ 4xx"""
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def check(name: str, ok: bool, detail: str = ""):
    print(("ผ่าน  " if ok else "ไม่ผ่าน ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failed.append(name)


def main() -> int:
    st, body = get("/api/health")
    health = json.loads(body) if st == 200 else {}
    check("GET /api/health ตอบ ok", st == 200 and health.get("ok") is True, f"status={st}")
    check("มีสถานที่ที่ตรวจที่มาแล้ว", health.get("verified_places", 0) > 0, str(health))

    st, body = get("/api/provinces")
    regions = json.loads(body).get("regions", []) if st == 200 else []
    total = sum(len(r["provinces"]) for r in regions)
    check("GET /api/provinces ครบ 77 จังหวัด", total == 77, f"status={st} total={total}")

    st, body = get("/api/places/nearby?lat=18.7883&lon=98.9853&limit=20")
    data = json.loads(body) if st == 200 else {}
    items = data.get("items", [])
    dist = [i["distance_km"] for i in items]
    check("GET /api/places/nearby (เชียงใหม่) มีผล", st == 200 and len(items) > 0, f"status={st} items={len(items)}")
    check("ผลเรียงจากใกล้ไปไกล", dist == sorted(dist))
    check("ไม่เกินรัศมี 30 กม.", all(d <= 30 for d in dist))
    check("ไม่มีฟิลด์ราคา", not any(k in i for i in items for k in ("price", "cost_thb", "rating")))
    check("มีข้อความอ้างอิง OpenStreetMap", "attribution" in data, f"keys={sorted(data)}")

    st, _ = get("/api/me/searches")
    check("GET /api/me/searches ตอนยังไม่ล็อกอินได้ 401", st == 401, f"status={st}")

    st, body = get("/")
    if st == 200 and '<div id="root"' in body:
        check("หน้าเว็บเสิร์ฟ index.html", True)
        st, _ = get("/search")
        check("เส้นทางในหน้าเว็บ (/search) กลับไป index.html", st == 200, f"status={st}")
    else:
        print("ข้าม  ส่วนหน้าเว็บ (ที่อยู่นี้ไม่ได้เสิร์ฟหน้าเว็บ)")

    print()
    if failed:
        print(f"ไม่ผ่าน {len(failed)} ข้อ: " + ", ".join(failed))
        return 1
    print("ผ่านทั้งหมด")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, OSError) as e:
        print(f"ต่อ {BASE} ไม่ได้: {e}")
        sys.exit(2)
