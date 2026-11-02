"""ดึงสถานที่เที่ยว คาเฟ่ และที่พักจาก OpenStreetMap ของแต่ละจังหวัดเก็บไว้ล่วงหน้า (สแนปช็อต)
ตอนเดโมถ้าออนไลน์ไม่ได้ ระบบจะใช้ไฟล์เหล่านี้แทน (ดู docs/DATA_SOURCES.md)

ต้องมีอินเทอร์เน็ตที่เข้า Overpass ได้ ใช้เวลานาน (ราว 1-2 ชั่วโมงทั้งประเทศ) รันซ้ำได้ ข้ามจังหวัดที่ทำเสร็จแล้ว

ใช้:
  python scripts/prefetch_osm.py                    ทุกจังหวัด เรียงตามภาค (เหนือก่อน)
  python scripts/prefetch_osm.py --region เหนือ     เฉพาะภาค
  python scripts/prefetch_osm.py เชียงใหม่ ลำปาง    เฉพาะจังหวัดที่ระบุ
  python scripts/prefetch_osm.py --force            ดึงใหม่แม้มีไฟล์แล้ว
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.places.fetch import HttpClient, UpstreamError  # noqa: E402
from services.places.models import Candidate  # noqa: E402
from services.places.osm import OverpassClient, build_area_query, split_filters  # noqa: E402
from services.places.provinces import PROVINCES, REGION_ORDER, REGIONS  # noqa: E402
from services.places.snapshot import DEFAULT_DIR, write_province  # noqa: E402

KINDS = ("attraction", "cafe", "lodging")   # ดึงทีละประเภท ลดโอกาส Overpass ตัดเพราะผลใหญ่เกิน
PAUSE = 8          # วินาทีพักระหว่างคำขอ (ใจดีกับเซิร์ฟเวอร์สาธารณะ)
RETRIES = 3
SUSPICIOUS = 10    # จังหวัดที่ได้น้อยกว่านี้น่าสงสัย (เขตจังหวัดอาจหาไม่เจอ)
MIN_PER_KIND = 10  # แต่ละประเภทต้องได้อย่างน้อยเท่านี้ ไม่งั้นถือว่าดึงไม่ครบ (Overpass ตอบว่างตอนแน่นได้) และดึงใหม่


def kind_counts(path: Path) -> dict[str, int]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError):
        return {}
    counts = {k: 0 for k in KINDS}
    for r in rows:
        counts[r[3]] = counts.get(r[3], 0) + 1
    return counts


def is_complete(path: Path) -> bool:
    c = kind_counts(path)
    return bool(c) and all(c.get(k, 0) >= MIN_PER_KIND for k in KINDS)


def fetch_kind(client: OverpassClient, province: str, kind: str, pause: float = PAUSE) -> list[Candidate]:
    """ดึงหนึ่งประเภท: ผลว่างถือว่าผิดปกติ (Overpass แน่นอาจตอบว่างเงียบๆ) ลองใหม่ ถ้ายังว่างแยกคำขอทีละตัวกรอง"""
    for attempt in range(1, RETRIES + 1):
        try:
            got = client.run(build_area_query(province, (kind,)))
        except UpstreamError as e:
            print(f"    {kind}: ลองครั้งที่ {attempt}/{RETRIES} ไม่สำเร็จ ({e})", flush=True)
            if attempt == RETRIES:
                raise
            time.sleep(pause * attempt * 2)
            continue
        if got:
            return got
        print(f"    {kind}: ได้ 0 แห่ง น่าสงสัย ลองใหม่ครั้งที่ {attempt}/{RETRIES}", flush=True)
        time.sleep(pause * attempt * 2)
    print(f"    {kind}: ยังได้ 0 แยกคำขอทีละตัวกรอง", flush=True)
    merged: dict[str, Candidate] = {}
    for f in split_filters(kind):
        got = client.run(build_area_query(province, (kind,), filters=[f]))
        for c in got:
            merged[c.id] = c
        time.sleep(pause)
    return list(merged.values())


def fetch_province(client: OverpassClient, province: str, pause: float = PAUSE) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for kind in KINDS:
        got = fetch_kind(client, province, kind, pause)
        for c in got:
            seen[c.id] = c
        print(f"    {kind}: {len(got)}", flush=True)
        time.sleep(pause)
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
        existing = out / f"{prov}.json"
        if existing.exists() and not a.force:
            if is_complete(existing):
                print(f"[{i}/{len(todo)}] {prov}: มีแล้วและครบ ข้าม")
                continue
            print(f"[{i}/{len(todo)}] {prov}: มีไฟล์แต่บางประเภทน้อยผิดปกติ {kind_counts(existing)} ดึงใหม่")
        print(f"[{i}/{len(todo)}] {prov}", flush=True)
        try:
            cands = fetch_province(client, prov)
        except UpstreamError as e:
            print(f"  ล้มเหลว: {e}")
            failed.append(prov)
            continue
        write_province(out, prov, cands, today)
        per = {k: sum(1 for c in cands if c.kind == k) for k in KINDS}
        print(f"  บันทึก {len(cands)} แห่ง {per}")
        low = {k: n for k, n in per.items() if n < MIN_PER_KIND}
        if len(cands) < SUSPICIOUS or low:
            suspicious.append((prov, low or len(cands)))
    print("\nสรุป")
    print("ล้มเหลว (รันซ้ำได้):", ", ".join(failed) or "ไม่มี")
    print("น่าสงสัย (ประเภทใดได้น้อยกว่า", MIN_PER_KIND, "แห่ง รันซ้ำเพื่อดึงใหม่):", ", ".join(f"{p}={n}" for p, n in suspicious) or "ไม่มี")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
