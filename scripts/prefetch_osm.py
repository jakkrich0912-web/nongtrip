"""ดึงสถานที่เที่ยว คาเฟ่ และที่พักจาก OpenStreetMap ของแต่ละจังหวัดเก็บไว้ล่วงหน้า (สแนปช็อต)
ตอนสอบถ้าออนไลน์ไม่ได้ ระบบจะใช้ไฟล์เหล่านี้แทน (ดู docs/DATA_SOURCES.md)

ต้องมีอินเทอร์เน็ตที่เข้า Overpass ได้ ใช้เวลานาน (ราว 1-2 ชั่วโมงทั้งประเทศ) รันซ้ำได้ ข้ามจังหวัดที่ทำเสร็จแล้ว

ใช้:
  python scripts/prefetch_osm.py                    ทุกจังหวัด เรียงตามภาค (เหนือก่อน)
  python scripts/prefetch_osm.py --region เหนือ     เฉพาะภาค
  python scripts/prefetch_osm.py เชียงใหม่ ลำปาง    เฉพาะจังหวัดที่ระบุ
  python scripts/prefetch_osm.py --force            ดึงใหม่แม้มีไฟล์แล้ว
"""
import argparse
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.places.fetch import HttpClient, UpstreamError  # noqa: E402
from services.places.models import Candidate  # noqa: E402
from services.places.osm import OverpassClient, build_area_query  # noqa: E402
from services.places.provinces import PROVINCES, REGION_ORDER, REGIONS  # noqa: E402
from services.places.snapshot import DEFAULT_DIR, write_province  # noqa: E402

KINDS = ("attraction", "cafe", "lodging")   # ดึงทีละประเภท ลดโอกาส Overpass ตัดเพราะผลใหญ่เกิน
PAUSE = 8          # วินาทีพักระหว่างคำขอ (ใจดีกับเซิร์ฟเวอร์สาธารณะ)
RETRIES = 3
SUSPICIOUS = 10    # จังหวัดที่ได้น้อยกว่านี้น่าสงสัย (เขตจังหวัดอาจหาไม่เจอ)


def fetch_province(client: OverpassClient, province: str) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for kind in KINDS:
        query = build_area_query(province, (kind,))
        for attempt in range(1, RETRIES + 1):
            try:
                got = client.run(query)
                break
            except UpstreamError as e:
                print(f"    {kind}: ลองครั้งที่ {attempt}/{RETRIES} ไม่สำเร็จ ({e})", flush=True)
                if attempt == RETRIES:
                    raise
                time.sleep(PAUSE * attempt * 2)
        for c in got:
            seen[c.id] = c
        print(f"    {kind}: {len(got)}", flush=True)
        time.sleep(PAUSE)
    return list(seen.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("provinces", nargs="*")
    ap.add_argument("--region", choices=list(REGIONS))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", default=str(DEFAULT_DIR))
    a = ap.parse_args()

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

    out = Path(a.out)
    client = OverpassClient(HttpClient(timeout=200))
    today = date.today().isoformat()
    failed, suspicious = [], []
    for i, prov in enumerate(todo, 1):
        if (out / f"{prov}.json").exists() and not a.force:
            print(f"[{i}/{len(todo)}] {prov}: มีแล้ว ข้าม")
            continue
        print(f"[{i}/{len(todo)}] {prov}", flush=True)
        try:
            cands = fetch_province(client, prov)
        except UpstreamError as e:
            print(f"  ล้มเหลว: {e}")
            failed.append(prov)
            continue
        write_province(out, prov, cands, today)
        print(f"  บันทึก {len(cands)} แห่ง")
        if len(cands) < SUSPICIOUS:
            suspicious.append((prov, len(cands)))
    print("\nสรุป")
    print("ล้มเหลว (รันซ้ำได้):", ", ".join(failed) or "ไม่มี")
    print("น่าสงสัย (ได้น้อยกว่า", SUSPICIOUS, "แห่ง):", ", ".join(f"{p}={n}" for p, n in suspicious) or "ไม่มี")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
