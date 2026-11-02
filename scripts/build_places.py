"""สร้างข้อมูลสถานที่ทั้ง 77 จังหวัดจาก Wikipedia (พิกัด + ชื่อภาษาไทย) แล้วเขียน services/places/data/places_all_provinces.json

ใช้:  python scripts/build_places.py          (ต้องต่ออินเทอร์เน็ต ใช้เฉพาะไลบรารีมาตรฐานของ Python ไม่ต้องติดตั้งอะไรเพิ่ม)
      python scripts/build_places.py --dry     (ดึงและแสดงสรุป ไม่เขียนไฟล์)

หลักการ (กฎข้อมูลจริง):
- ข้อเท็จจริงที่ใส่ในไฟล์ผลลัพธ์มีเพียง ชื่อ (en) พิกัด และชื่อไทย ซึ่งมาจาก Wikipedia ที่ดึงตอนรันสคริปต์นี้เท่านั้น พร้อม sources (url + วันที่ตรวจ)
- เวลาเปิด-ปิด ค่าเข้า คำอธิบาย = null (ยังไม่มีแหล่งทางการ) ไม่เดา
- ชื่อบทความที่หาไม่เจอ / ไม่มีพิกัด / พิกัดอยู่นอกประเทศไทย จะถูกข้ามและรายงานไว้ใน docs/COVERAGE.md ไม่มีการเติมค่าจากความจำ
- category/tags/duration_min เป็นป้ายของทีม (ดู seed_places.py) ไม่ใช่ข้อเท็จจริงที่ตรวจแล้ว
"""
import argparse
import re
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services" / "places")]

from seed_places import CODES, SEED  # noqa: E402
from provinces import PROVINCES  # noqa: E402  (รายชื่อ 77 จังหวัด เรียงตามอักษร)

API = "https://en.wikipedia.org/w/api.php"
UA = "NongTripCourseProject/1.0 (university course project, one-off data build) python-urllib"
BATCH = 20
LAT_RANGE, LON_RANGE = (5.5, 20.6), (97.3, 105.7)   # กรอบประเทศไทยคร่าวๆ ใช้กันค่าผิดมหันต์เท่านั้น
OUT = ROOT / "services" / "places" / "data" / "places_all_provinces.json"
REPORT = ROOT / "docs" / "COVERAGE.md"


def fetch_json(params: dict, api: str = API) -> dict:
    """เรียก API พร้อมลองใหม่เมื่อเจอ 429/5xx (รอตาม Retry-After ถ้ามี) และแสดงรหัส+ข้อความของเซิร์ฟเวอร์เมื่อผิดพลาด"""
    url = api + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    tries = 8
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = int(ra) if ra and ra.isdigit() else min(10 * 2 ** attempt, 120)
                wait = min(max(wait, 5), 180)
                print(f"  HTTP {e.code} รอ {wait} วินาทีแล้วลองใหม่ (ครั้งที่ {attempt + 2}/{tries})...", flush=True)
                time.sleep(wait)
                continue
            print(f"\nHTTP {e.code} {e.reason} จาก Wikipedia ข้อความ: {body}")
            print("URL (ยาว", len(url), "ตัวอักษร):", url[:200], "...")
            raise SystemExit(1)
        except urllib.error.URLError as e:
            print(f"\nต่ออินเทอร์เน็ต/Wikipedia ไม่ได้: {e.reason}")
            raise SystemExit(1)


def lookup(titles: list[str], fetch=fetch_json) -> dict[str, dict]:
    """คืน {ชื่อที่ขอ: {"title","lat","lon","th"} หรือ {"error": เหตุผล}}"""
    params = {"action": "query", "format": "json", "redirects": 1, "prop": "coordinates|langlinks", "coprimary": "primary",
              "colimit": 50, "lllang": "th", "lllimit": 50, "titles": "|".join(t.replace("_", " ") for t in titles)}
    pages: dict = {}
    norm: dict = {}
    redir: dict = {}
    cont: dict = {}
    for _ in range(10):
        data = fetch({**params, **cont})
        q = data.get("query", {})
        for n in q.get("normalized", []):
            norm[n["from"]] = n["to"]
        for r in q.get("redirects", []):
            redir[r["from"]] = r["to"]
        for pid, pg in q.get("pages", {}).items():
            cur = pages.setdefault(pg["title"], {"title": pg["title"], "missing": "missing" in pg, "lat": None, "lon": None, "th": None})
            if pg.get("coordinates"):
                c = pg["coordinates"][0]
                cur["lat"], cur["lon"] = c["lat"], c["lon"]
            if pg.get("langlinks"):
                cur["th"] = pg["langlinks"][0].get("*") or pg["langlinks"][0].get("title")
        if "continue" not in data:
            break
        cont = data["continue"]
    out = {}
    for t in titles:
        name = t.replace("_", " ")
        name = norm.get(name, name)
        name = redir.get(name, name)
        pg = pages.get(name)
        if pg is None or pg["missing"]:
            out[t] = {"error": "ไม่พบบทความ"}
        elif pg["lat"] is None:
            out[t] = {"error": "บทความไม่มีพิกัด"}
        elif not (LAT_RANGE[0] <= pg["lat"] <= LAT_RANGE[1] and LON_RANGE[0] <= pg["lon"] <= LON_RANGE[1]):
            out[t] = {"error": f"พิกัดอยู่นอกกรอบประเทศไทย ({pg['lat']}, {pg['lon']})"}
        else:
            out[t] = {"title": pg["title"], "lat": pg["lat"], "lon": pg["lon"], "th": pg["th"]}
    return out


def _tokens(title: str) -> set[str]:
    base = title.replace("_", " ")
    base = base.split("(")[0]
    return {w for w in "".join(ch.lower() if ch.isalnum() else " " for ch in base).split() if len(w) > 1}


API_TH = "https://th.wikipedia.org/w/api.php"
# บทความประเภทนี้ไม่ใช่ "สถานที่เที่ยว" แม้ชื่อซ้อนกัน (เช่น อำเภอเกาะช้าง ≠ เกาะสีชัง) ปฏิเสธเสมอ
BAD_WORDS = {"district", "railway", "halt", "university", "college", "school", "subdistrict", "amphoe", "province", "station", "hospital", "airport"}
# จับคู่ผิดที่ตรวจเจอแล้วจากตารางใน COVERAGE.md (ชื่อไม่ตรงสถานที่ที่ตั้งใจ) ห้ามใช้ผลค้นหา
NO_SEARCH = {"Wat_Luang_(Phrae)", "Prasat_Ban_Samor", "Phu_Pha_Mok", "Nong_Han_(Sakon_Nakhon)", "Bueng_Kaen_Nakhon",
             "Mae_Fah_Luang_Garden", "Ko_Si_Chang", "Ban_Ta_Klang", "Bo_Kluea", "Si_Mahosot", "Sam_Chuk_Market"}


def resolve_by_search(title: str, fetch=fetch_json) -> dict | None:
    """ชื่อที่ขอไม่มีบทความ -> ค้นหาด้วยชื่อนั้น + Thailand แล้วรับเฉพาะผลที่ชื่อซ้อนกับชื่อที่ขอ >= 60% ของคำ
    และมีพิกัดในไทย (ไม่เอาผลแรกมั่วๆ) คืน {"title","lat","lon","th","via_search"} หรือ None"""
    want = _tokens(title)
    if not want or title in NO_SEARCH:
        return None
    q = " ".join(sorted(want, key=lambda w: -len(w))[:6]) + " Thailand"
    data = fetch({"action": "query", "format": "json", "list": "search", "srsearch": q, "srlimit": 5, "srnamespace": 0})
    for hit in data.get("query", {}).get("search", []):
        got = _tokens(hit["title"])
        if got & BAD_WORDS or len(want & got) / len(want) < 0.6:
            continue
        r = lookup([hit["title"]], fetch).get(hit["title"])
        if r and "error" not in r:
            r["via_search"] = title
            return r
    return None


TH_KEYS = [  # (คำที่ชื่อบทความไทย "ขึ้นต้นด้วย", รหัสหมวดใน CODES) ต้องขึ้นต้นเท่านั้น ไม่ใช่แค่มีคำอยู่ข้างใน (เช่น "จังหวัด" มีคำว่า "วัด")
    ("อุทยานแห่งชาติ", "N"), ("น้ำตก", "N"), ("น้ำพุร้อน", "N"), ("หาด", "B"), ("เกาะ", "B"), ("อ่าว", "B"), ("ถ้ำ", "N"), ("เขื่อน", "N"),
    ("พิพิธภัณฑ์", "M"), ("พระธาตุ", "T"), ("วัด", "T"), ("มัสยิด", "T"), ("ศาลหลักเมือง", "T"), ("ศาลพระ", "T"), ("ปราสาท", "H"), ("พระราชวัง", "H"),
    ("ป้อม", "H"), ("อนุสาวรีย์", "H"), ("ตลาด", "K"), ("บึง", "N"), ("ภู", "N"), ("สวนสาธารณะ", "N"), ("ปรางค์", "H")]
TH_REJECT = ("โรงเรียน", "มหาวิทยาลัย", "อำเภอ", "ตำบล", "สถานี", "ถนน", "โรงพยาบาล", "เทศบาล", "หมู่บ้าน", "แก้ความกำกวม", "ราชภัฏ", "วิทยาลัย",
             "ทางหลวง", "สนาม", "ทางแยก", "หอดู", "ที่ว่าการ", "องค์การ", "สำนักงาน", "กองพัน", "กรมทหาร", "ธนารักษ์", "ศูนย์")


def discover_th(prov: str, fetch=fetch_json, limit: int = 8) -> list[dict]:
    """จังหวัดที่ชื่อบทความที่ตั้งไว้หาไม่เจอ: ดึงบทความ th.wikipedia ที่มีพิกัดอยู่ใกล้ตัวเมืองจริง (geosearch รัศมี 10 กม.) แล้วกรองด้วยคำนำหน้าชนิดสถานที่
    ทุกแห่งเป็นบทความจริงที่มีพิกัดจริง แต่ไม่ใช่การจัดอันดับความโดดเด่น จึงระบุใน COVERAGE.md ให้ตรวจ"""
    ctr = fetch({"action": "query", "format": "json", "prop": "coordinates", "titles": "กรุงเทพมหานคร" if prov == "กรุงเทพมหานคร" else "จังหวัด" + prov}, API_TH)
    pg = next(iter(ctr.get("query", {}).get("pages", {}).values()), {})
    if not pg.get("coordinates"):
        return []
    c = pg["coordinates"][0]
    g = fetch({"action": "query", "format": "json", "list": "geosearch", "gscoord": f"{c['lat']}|{c['lon']}", "gsradius": 10000,
               "gslimit": 100, "gsnamespace": 0}, API_TH)
    out, seen = [], set()
    for h in g.get("query", {}).get("geosearch", []):
        t = h["title"]
        m = re.search(r"\(จังหวัด([^)]+)\)", t)
        if any(b in t for b in TH_REJECT) or (m and m.group(1).strip() != prov):   # ตัดบทความของจังหวัดอื่น เช่น "วัดหงษ์ (จังหวัดพระนครศรีอยุธยา)"
            continue
        code = _th_ok(t, prov)
        if not code or t in seen or not (LAT_RANGE[0] <= h["lat"] <= LAT_RANGE[1] and LON_RANGE[0] <= h["lon"] <= LON_RANGE[1]):
            continue
        seen.add(t)
        out.append({"title": t, "lat": h["lat"], "lon": h["lon"], "code": code, "dist": h.get("dist", 0)})
    out.sort(key=lambda r: r["dist"])
    return out[:limit]


# ตรวจพิกัดเทียบจังหวัดแล้วพบว่าอยู่ผิดจังหวัด/ไม่ใช่สถานที่ (province, name_th) ตัดทิ้งเสมอ แม้ผลจากแหล่งจะซ้ำมาอีก
DROP = {("นราธิวาส", "พิพิธภัณฑ์เมืองยะลา"), ("ปราจีนบุรี", "พิพิธภัณฑ์ห้างขายยาเบอร์ลิน"), ("ลำพูน", "พิพิธภัณฑ์สักทอง"),
        ("นครสวรรค์", "พิพิธภัณฑ์บ้านดงโฮจิมินห์"), ("นนทบุรี", "พิพิธภัณฑ์หุ่นขี้ผึ้งไทย"), ("สิงห์บุรี", "พิพิธภัณฑ์หนังใหญ่วัดบ้านดอน"),
        ("ระนอง", "พิพิธภัณฑ์พระยารัษฎานุประดิษฐ์มหิศรภักดี (คอซิมบี๊ ณ ระนอง)"), ("ชุมพร", "อุทยานแห่งชาติน้ำตกหงาว"), ("ชุมพร", "เกาะพะลวย"),
        ("ศรีสะเกษ", "ปราสาทบ้านปราสาท"), ("ศรีสะเกษ", "ปราสาทตาเล็ง"), ("สระบุรี", "ปราสาทนครหลวง"), ("นครราชสีมา", "ภูเรือ"),
        ("ปทุมธานี", "อำเภอวัดสิงห์"), ("แม่ฮ่องสอน", "อุทยานแห่งชาติศรีลานนา")}

# ตัดตามรหัส: สถานที่เดียวกันที่ได้มาสองรอบ (en-wiki กับ th-wiki) เก็บรหัสเดิมที่ขึ้นต้นด้วยเลขต่ำ
DROP_IDS = {"p1243", "p1945", "p2244", "p6943"}


def apply_drop(places: list[dict]) -> list[dict]:
    return [p for p in places if (p["province"], p["name_th"]) not in DROP and p["id"] not in DROP_IDS
            and not p["name_th"].startswith("อำเภอ")]


def _th_ok(t: str, prov: str) -> str | None:
    """คืนรหัสหมวดถ้าชื่อบทความไทยดูเป็นสถานที่เที่ยว ไม่ใช่ของจังหวัดอื่น/ไม่ใช่สิ่งปลูกสร้างทั่วไป"""
    m = re.search(r"\(จังหวัด([^)]+)\)", t)
    if any(b in t for b in TH_REJECT) or (m and m.group(1).strip() != prov):
        return None
    if any(o in t for o in PROVINCES if o != prov and len(o) > 4):      # ชื่อบทความมีชื่อจังหวัดอื่น (เช่น พิพิธภัณฑ์เมืองยะลา ในนราธิวาส)
        return None
    return next((cd for k, cd in TH_KEYS if t.startswith(k)), None)


def discover_th_search(prov: str, fetch=fetch_json, limit: int = 6) -> list[dict]:
    """ชั้นสอง สำหรับจังหวัดที่ยังมีน้อย: ค้น "<ชนิด> จังหวัด<ชื่อ>" ใน th.wikipedia รับเฉพาะบทความที่ข้อความตัวอย่างหรือชื่อระบุจังหวัดนั้นจริง
    แล้วดึงพิกัดของบทความนั้น ไม่มีพิกัดหรืออยู่นอกประเทศไทยตัดทิ้ง"""
    cand: dict[str, str] = {}
    for key in ("วัด", "น้ำตก", "พิพิธภัณฑ์", "อุทยานแห่งชาติ", "ปราสาท", "ตลาด"):
        d = fetch({"action": "query", "format": "json", "list": "search", "srsearch": f"{key} จังหวัด{prov}", "srlimit": 15,
                   "srnamespace": 0, "srprop": "snippet"}, API_TH)
        for h in d.get("query", {}).get("search", []):
            t = h["title"]
            text = re.sub(r"<[^>]+>", "", h.get("snippet", ""))
            code = _th_ok(t, prov)
            if code and ("จังหวัด" + prov in text or prov in t):
                cand.setdefault(t, code)
    out = []
    names = list(cand)
    for i in range(0, len(names), 40):
        d = fetch({"action": "query", "format": "json", "prop": "coordinates", "coprimary": "primary", "colimit": 50,
                   "titles": "|".join(names[i:i + 40])}, API_TH)
        for pg in d.get("query", {}).get("pages", {}).values():
            co = (pg.get("coordinates") or [None])[0]
            if co and LAT_RANGE[0] <= co["lat"] <= LAT_RANGE[1] and LON_RANGE[0] <= co["lon"] <= LON_RANGE[1]:
                out.append({"title": pg["title"], "lat": co["lat"], "lon": co["lon"], "code": cand.get(pg["title"], "T"), "dist": 0})
    order = {t: i for i, t in enumerate(names)}
    out.sort(key=lambda r: order.get(r["title"], 99))
    return out[:limit]


def build(fetch=fetch_json, today: str | None = None, sleep: float = 1.0, cache_path: Path | None = None, discover: bool = False):
    today = today or date.today().isoformat()
    order = [(prov, t, c) for prov in PROVINCES for (t, c) in SEED.get(prov, [])]
    titles = list(dict.fromkeys(t for _, t, _ in order))
    found: dict[str, dict] = {}
    if cache_path and cache_path.exists():              # รันซ้ำแล้วไม่ต้องดึงชุดที่ได้แล้วใหม่
        found = json.loads(cache_path.read_text(encoding="utf-8"))
        found = {t: r for t, r in found.items()          # ทิ้งผลจับคู่ที่ตรวจแล้วว่าผิด เพื่อให้ตัวกรองใหม่ทำงาน
                 if not (r.get("via_search") and (t in NO_SEARCH or _tokens(r["title"]) & BAD_WORDS))}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        if all(t in found for t in chunk):
            continue
        found.update(lookup(chunk, fetch))
        if cache_path:
            cache_path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
        print(f"  ดึงแล้ว {min(i + BATCH, len(titles))}/{len(titles)} ชื่อบทความ", flush=True)
        if sleep:
            time.sleep(sleep)
    for t in titles:
        if found[t].get("error") == "ไม่พบบทความ" and not found[t].get("searched"):
            res = resolve_by_search(t, fetch)
            found[t] = res if res else {"error": "ไม่พบบทความ (ค้นหาแล้วไม่มีชื่อใกล้เคียงที่มีพิกัดในไทย)", "searched": True}
            if sleep:
                time.sleep(sleep)
            if cache_path:
                cache_path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    places, skipped, seen_pos = [], [], set()
    counters: dict[str, int] = {}
    for prov, t, code in order:
        r = found[t]
        if "error" in r:
            skipped.append((prov, t, r["error"]))
            continue
        pos = (round(r["lat"], 4), round(r["lon"], 4))
        if pos in seen_pos:                       # ชื่อต่างกันแต่ชี้บทความ/พิกัดเดียวกัน (เช่น redirect) ไม่ซ้ำ
            skipped.append((prov, t, "ซ้ำกับสถานที่อื่น (พิกัดเดียวกัน)"))
            continue
        seen_pos.add(pos)
        cat, tags, dur = CODES[code]
        idx = PROVINCES.index(prov) + 1
        counters[prov] = counters.get(prov, 0) + 1
        notes = [] if r["th"] else ["ยังไม่พบชื่อภาษาไทยใน Wikipedia จึงแสดงชื่ออังกฤษ"]
        places.append({
            "id": f"p{idx}{counters[prov]:02d}",
            "name_th": r["th"] or r["title"], "name_en": r["title"], "category": cat, "area": prov,
            "lat": round(r["lat"], 5), "lon": round(r["lon"], 5), "duration_min": dur,
            "cost_thb": None, "open": None, "tags": list(tags), "description": None, "notes": notes,
            "province": prov, "verified": True, **({"matched_from_seed": r["via_search"]} if r.get("via_search") else {}),
            "sources": [{"url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(r["title"].replace(" ", "_"), safe="_(),-"),
                         "title": f"{r['title']} (Wikipedia)", "checked_on": today,
                         "fields": ["lat", "lon", "name_th", "name_en"] if r["th"] else ["lat", "lon", "name_en"]}],
        })
    if discover:
        cnt = {}
        for q in places:
            cnt[q["province"]] = cnt.get(q["province"], 0) + 1
        for prov in PROVINCES:
            if prov == "เชียงใหม่" or cnt.get(prov, 0) >= 5:
                continue
            try:
                found_th = discover_th(prov, fetch)
                if cnt.get(prov, 0) + len(found_th) < 3:          # ชั้นสอง: จังหวัดที่ยังน้อยมาก
                    have = {r["title"] for r in found_th}
                    found_th += [r for r in discover_th_search(prov, fetch) if r["title"] not in have]
            except SystemExit:
                continue
            if sleep:
                time.sleep(sleep)
            idx = PROVINCES.index(prov) + 1
            for r in found_th:
                pos = (round(r["lat"], 4), round(r["lon"], 4))
                if pos in seen_pos or cnt.get(prov, 0) >= 6:
                    continue
                seen_pos.add(pos)
                cnt[prov] = cnt.get(prov, 0) + 1
                cat, tags, dur = CODES[r["code"]]
                places.append({
                    "id": f"p{idx}{cnt[prov] + 40:02d}", "name_th": r["title"], "name_en": r["title"], "category": cat, "area": prov,
                    "lat": round(r["lat"], 5), "lon": round(r["lon"], 5), "duration_min": dur, "cost_thb": None, "open": None, "tags": list(tags),
                    "description": None, "notes": ["พบจากการค้นหาบทความที่มีพิกัดใกล้ตัวเมือง (Wikipedia ภาษาไทย) ยังไม่ได้ตรวจว่าเป็นที่เที่ยวเด่น"],
                    "province": prov, "verified": True, "matched_from_seed": "th-wiki",
                    "sources": [{"url": "https://th.wikipedia.org/wiki/" + urllib.parse.quote(r["title"].replace(" ", "_"), safe="_(),-"),
                                 "title": f"{r['title']} (Wikipedia ภาษาไทย)", "checked_on": today, "fields": ["lat", "lon", "name_th"]}],
                })
    return apply_drop(places), skipped, today


def keep_ids(places: list[dict], previous: list[dict]) -> list[dict]:
    """คงรหัสเดิมของสถานที่ที่เคยมีอยู่แล้ว (จับคู่ด้วย URL แหล่งที่มา) เพื่อไม่ให้รหัสเลื่อนเมื่อเพิ่มชื่อบทความใหม่
    รหัสถูกใช้ต่อในสถานที่โปรดของผู้ใช้ (v:<id>) และคลังความรู้ (place_id) ถ้าเลื่อนจะชี้ผิดแห่ง
    สถานที่ใหม่ได้เลขถัดไปที่ยังว่างในจังหวัดนั้น (seed ช่วง 01-39, จากการค้น th-wiki ช่วง 41 ขึ้นไป)
    รหัสของสถานที่เดิมที่หายไปจะไม่ถูกนำมาใช้ซ้ำ"""
    def url(p):
        return (p.get("sources") or [{}])[0].get("url")
    # จับคู่ด้วย (จังหวัด, URL) เพราะรหัสขึ้นต้นด้วยเลขจังหวัด สถานที่ที่คร่อมสองจังหวัด (เช่น อุทยานแห่งชาติภูลังกา)
    # อาจถูกค้นเจอในอีกจังหวัด ห้ามเอารหัสของจังหวัดหนึ่งไปให้อีกจังหวัด
    prev_by_key = {(p["province"], url(p)): p["id"] for p in previous if url(p)}
    used = {p["id"] for p in previous}
    out, fresh = [], []
    for p in places:
        old = prev_by_key.get((p["province"], url(p)))
        if old and old not in {q["id"] for q in out}:
            out.append({**p, "id": old})
        else:
            fresh.append(p)
    used |= {q["id"] for q in out}
    # สถานที่ใหม่ที่ชื่อซ้ำกับที่มีอยู่แล้วในจังหวัดเดียวกัน (บทความไทยกับอังกฤษของที่เดียวกัน) ไม่เพิ่ม
    names = {(q["province"], q["name_th"]) for q in [*previous, *out]}
    for p in fresh:
        if (p["province"], p["name_th"]) in names:
            continue
        names.add((p["province"], p["name_th"]))
        idx = PROVINCES.index(p["province"]) + 1
        n = 41 if p.get("matched_from_seed") == "th-wiki" else 1
        while f"p{idx}{n:02d}" in used:
            n += 1
        p = {**p, "id": f"p{idx}{n:02d}"}
        used.add(p["id"])
        out.append(p)
    return out


def keep_previous(places: list[dict], previous: list[dict]) -> tuple[list[dict], list[dict]]:
    """สถานที่จากรอบก่อนที่รอบนี้ดึงไม่เจอ ให้คงไว้ตามเดิม (การค้น th-wiki ได้ผลไม่เหมือนกันทุกครั้ง และ Wikipedia อาจจำกัดความถี่)
    ไม่อย่างนั้นสถานที่โปรดและคลังความรู้ที่อ้างรหัสเดิมจะชี้ไปที่ไม่มีอยู่ ถ้าต้องการเอาออกจริงให้ใส่ใน DROP"""
    def url(p):
        return (p.get("sources") or [{}])[0].get("url")
    have = {url(p) for p in places}
    have_ids = {p["id"] for p in places}
    kept = [p for p in apply_drop(previous) if url(p) not in have and p["id"] not in have_ids]
    return places + kept, kept


def write_report(places, skipped, today, kept=()):
    by = {}
    for p in places:
        by[p["province"]] = by.get(p["province"], 0) + 1
    lines = [f"# ความครอบคลุมของข้อมูล (สร้างอัตโนมัติโดย scripts/build_places.py เมื่อ {today})", "",
             f"ชื่อบทความที่ตั้งต้น {sum(len(v) for v in SEED.values())} รายการ ได้สถานที่ {len(places)} แห่ง ข้ามไป {len(skipped)} รายการ",
             "ทุกแห่งมีที่มาเฉพาะ **ชื่อ พิกัด** (Wikipedia) เวลาเปิด-ปิด ค่าเข้า คำอธิบาย = ไม่ทราบ (null) ไม่ใช่ข้อมูลที่ตรวจกับแหล่งทางการ", "",
             "| จังหวัด | จำนวนแห่ง |", "|---|---|"]
    for prov in PROVINCES:
        lines.append(f"| {prov} | {by.get(prov, 0) if prov != 'เชียงใหม่' else '24 (ไฟล์ places.json)'} |")
    via = [p for p in places if p.get("matched_from_seed")]
    none = [p for p in PROVINCES if p != "เชียงใหม่" and not by.get(p)]
    lines += ["", f"## จังหวัดที่ยังไม่มีสถานที่ ({len(none)})", ", ".join(none) or "ไม่มี", "",
              f"## แห่งที่จับคู่ด้วยการค้นหา ({len(via)}) ควรตรวจว่าชื่อตรงกับสถานที่ที่ตั้งใจ",
              "| จังหวัด | ชื่อที่ขอ | บทความที่ได้ |", "|---|---|---|",
              *[f"| {p['province']} | {p['matched_from_seed']} | {p['name_en']} |" for p in via], "",
              f"## รายการที่ข้าม ({len(skipped)})", "| จังหวัด | บทความ | เหตุผล |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in skipped]
    if kept:
        lines += ["", f"## คงไว้จากรอบก่อน ({len(kept)}) รอบนี้ดึงไม่เจอแต่ยังเก็บไว้เพื่อไม่ให้รหัสที่ผู้ใช้บันทึกไว้หาย", "| จังหวัด | ชื่อ | รหัส |", "|---|---|---|"]
        lines += [f"| {p['province']} | {p['name_th']} | {p['id']} |" for p in kept]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    places, skipped, today = build(sleep=3.0, cache_path=ROOT / "scripts" / ".wiki_cache.json", discover=True)
    previous = json.loads(OUT.read_text(encoding="utf-8"))["places"] if OUT.exists() else []
    places = keep_ids(places, previous)
    places, kept_prev = keep_previous(places, previous)
    kept = sum(1 for p in places if p["id"] in {q["id"] for q in previous})
    print(f"คงรหัสเดิม {kept} แห่ง (ในนั้นเก็บจากรอบก่อน {len(kept_prev)} แห่งที่รอบนี้ดึงไม่เจอ) สถานที่ใหม่ {len(places) - kept} แห่ง")
    by = {}
    for p in places:
        by[p["province"]] = by.get(p["province"], 0) + 1
    print(f"ได้ {len(places)} แห่ง ข้าม {len(skipped)} รายการ · จังหวัดที่มีข้อมูล {len(by)} (+เชียงใหม่)")
    print("จังหวัดที่ไม่ได้เลย:", ", ".join(p for p in PROVINCES if p != "เชียงใหม่" and not by.get(p)) or "ไม่มี")
    if a.dry:
        return
    meta = {"note": "สร้างโดย scripts/build_places.py จาก Wikipedia (ชื่อ พิกัด ชื่อไทย) เวลาเปิด ค่าเข้า คำอธิบายเป็น null ดู docs/COVERAGE.md และ docs/DATA_SOURCES.md",
            "built_on": today, "weekday_index": "0=จันทร์ ... 6=อาทิตย์"}
    OUT.write_text(json.dumps({"_meta": meta, "places": places}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_report(places, skipped, today, kept_prev)
    print("เขียน", OUT, "และ", REPORT)


if __name__ == "__main__":
    main()
