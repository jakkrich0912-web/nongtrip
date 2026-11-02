"""สร้างคลังความรู้ท่องเที่ยวสำหรับ RAG จากบทความ Wikipedia ของสถานที่ที่ตรวจที่มาแล้ว (docs/RAG_PLAN.md ข้อ 3)

ต้องมีอินเทอร์เน็ตที่เข้า Wikipedia ได้ รันบนเครื่องของคุณ (เหมือน prefetch_osm.py) ใช้เวลาราว 5-10 นาทีทั้งประเทศ
รันซ้ำได้ ข้ามจังหวัดที่มีไฟล์แล้ว ผลเก็บที่ services/places/data/knowledge/<จังหวัด>.json

ใช้:
  python scripts/build_knowledge.py                    ทุกจังหวัดที่มีสถานที่ที่ตรวจแล้ว
  python scripts/build_knowledge.py เชียงใหม่ ลำปาง      เฉพาะจังหวัดที่ระบุ
  python scripts/build_knowledge.py --region เหนือ      เฉพาะภาค
  python scripts/build_knowledge.py --force             สร้างใหม่แม้มีไฟล์แล้ว
  python scripts/build_knowledge.py --include-review    เก็บรายการที่ชื่อบทความไม่ตรงและไม่มีพิกัดยืนยันด้วย (ปกติไม่เก็บ)
  python scripts/build_knowledge.py --check             ตรวจไฟล์ที่มีอยู่ตามกติกา ไม่ต้องใช้เน็ต

หลังรัน: อ่านบรรทัด "ให้คนตรวจ" ท้ายผลลัพธ์ ถ้าบทความไม่ตรงสถานที่ให้ลบไฟล์จังหวัดนั้นแล้วรายงานมา ก่อน commit
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.places.fetch import HttpClient, UpstreamError  # noqa: E402
from services.places.knowledge import DEFAULT_DIR, build_province, load_all, validate, write_province  # noqa: E402
from services.places.provinces import PROVINCES, REGION_ORDER, REGIONS  # noqa: E402
from services.places.verified import DATA_DIR, FILES  # noqa: E402


def verified_by_province() -> dict[str, list[dict]]:
    out: dict[str, dict[str, dict]] = {}
    for fname in FILES:
        path = DATA_DIR / fname
        if not path.exists():
            continue
        for p in json.loads(path.read_text(encoding="utf-8"))["places"]:
            if p.get("verified") and p.get("lat") is not None and p.get("lon") is not None and p.get("province"):
                out.setdefault(p["province"], {})[p["id"]] = p
    return {k: list(v.values()) for k, v in out.items()}


def check(directory: Path) -> int:
    docs = load_all(directory)
    known = {f"v:{p['id']}" for ps in verified_by_province().values() for p in ps}
    problems = validate(docs, known)
    print(f"ก้อนข้อความ {len(docs)} ก้อน ใน {len(set(d.get('place_id') for d in docs))} สถานที่")
    for pr in problems[:50]:
        print("  ปัญหา:", pr)
    print("ผ่าน" if not problems else f"ไม่ผ่าน {len(problems)} ข้อ")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("provinces", nargs="*")
    ap.add_argument("--region", choices=list(REGIONS))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--include-review", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pause", type=float, default=1.0, help="วินาทีพักระหว่างคำขอ")
    ap.add_argument("--out", default=str(DEFAULT_DIR))
    a = ap.parse_args()
    out = Path(a.out)
    if a.check:
        return check(out)

    by_prov = verified_by_province()
    if a.provinces:
        todo = a.provinces
    elif a.region:
        todo = list(REGIONS[a.region])
    else:
        todo = [p for r in REGION_ORDER for p in REGIONS[r]]
    bad = [p for p in todo if p not in PROVINCES]
    if bad:
        print("ไม่รู้จักจังหวัด:", ", ".join(bad))
        return 2
    todo = [p for p in todo if p in by_prov]   # จังหวัดที่ไม่มีสถานที่ที่ตรวจแล้วไม่มีอะไรให้สร้าง

    client = HttpClient(timeout=60)
    today = date.today().isoformat()
    failed, review, far, name_check = [], [], [], []
    total = {"places": 0, "ok": 0, "th": 0}
    for i, prov in enumerate(todo, 1):
        if (out / f"{prov}.json").exists() and not a.force:
            print(f"[{i}/{len(todo)}] {prov}: มีแล้ว ข้าม")
            continue
        places = by_prov[prov]
        print(f"[{i}/{len(todo)}] {prov} ({len(places)} แห่ง)", flush=True)
        try:
            docs, rep = build_province(client, places, today, pause=a.pause, include_review=a.include_review)
        except UpstreamError as e:
            print(f"  ล้มเหลว: {e}")
            failed.append(prov)
            continue
        write_province(out, prov, docs, today)
        c = rep["counts"]
        print(f"  มีเนื้อหา {c['ok']} (ไทย {c['th']} อังกฤษ {c['en']}) ไม่เจอบทความ {c['no_page']} "
              f"ไม่มีข้อความที่ใช้ได้ {c['no_text']} ชื่อไม่ตรง {c['review']} พิกัดห่าง {c['far']} "
              f"ย่อหน้าที่ตัด (ราคา/รีวิว/จอง) {rep['dropped_paragraphs']}")
        total["places"] += len(places)
        total["ok"] += c["ok"]
        total["th"] += c["th"]
        review += [(prov, *r) for r in rep["review"]]
        far += [(prov, *r) for r in rep["far"]]
        name_check += [(prov, *r) for r in rep["name_check"]]

    print("\nสรุป")
    if total["places"]:
        print(f"สถานที่ {total['places']} แห่ง มีเนื้อหา {total['ok']} แห่ง (ฉบับไทย {total['th']})")
    print("ล้มเหลว (รันซ้ำได้):", ", ".join(failed) or "ไม่มี")
    for title, rows in (("ให้คนตรวจ: ชื่อบทความไม่ตรงและไม่มีพิกัดยืนยัน (ยังไม่ได้เก็บ)", review),
                        ("ให้คนตรวจ: ชื่อไม่ตรงแต่พิกัดตรง (เก็บแล้ว ดูว่าบทความถูกแห่งไหม)", name_check),
                        ("ตัดออก: พิกัดบทความห่างเกิน 3 กม.", far)):
        if rows:
            print(title)
            for prov, pid, name, wiki in rows:
                print(f"  {prov} {pid} {name}  <-  {wiki}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
