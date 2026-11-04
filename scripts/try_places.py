"""ลองบริการค้นหากับ OpenStreetMap จริง (ต้องมีอินเทอร์เน็ต)

ใช้:
  python scripts/try_places.py ที่พัก "ชื่อโรงแรม จังหวัด"
  python scripts/try_places.py รอบจุด 18.7883 98.9853 [รัศมี_กม.]
  python scripts/try_places.py หมุด 18.7883 98.9853
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("PLACES_CACHE_DIR", "data/cache")

from services.places import PlacesService  # noqa: E402
from services.places.fetch import UpstreamError  # noqa: E402


def show(items, n=15):
    for i, p in enumerate(items[:n], 1):
        print(f"{i:>2}. {p['distance_km']:>6.2f} กม.  [{p['source']}/{p['kind']}] {p['name_th']}")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    svc = PlacesService()
    cmd = argv[1]
    if cmd == "ที่พัก":
        out = svc.find_lodging(argv[2])
        for c in out["items"]:
            print(f"- {c['name']}  ({c['lat']:.5f}, {c['lon']:.5f})  {c['address']}")
        print(out["notices"])
    elif cmd == "รอบจุด":
        r = svc.nearby(float(argv[2]), float(argv[3]), float(argv[4]) if len(argv) > 4 else 30).to_dict()
        print(f"พบ {r['total']} แห่ง  {r['counts']}  แหล่งข้อมูล {r['sources']}  OSM ใช้ได้={r['osm_available']}")
        show(r["items"])
        print(r["notices"], r["attribution"])
    elif cmd == "หมุด":
        r = svc.lodgings_near(float(argv[2]), float(argv[3]))
        print(f"รัศมีค้นที่พัก {r['radius_km']} กม.  {r['notices']}")
        for lod in r["items"][:10]:
            print(f"\n{lod['name']}  ห่างหมุด {lod['distance_from_pin_km']} กม.  สถานที่ทั้งหมด {lod['places_total']}")
            show(lod["nearest"], 3)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except UpstreamError as e:
        print("เชื่อมต่อไม่ได้:", e)
        sys.exit(1)
