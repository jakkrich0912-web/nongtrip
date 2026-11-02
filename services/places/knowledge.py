"""คลังความรู้ท่องเที่ยวสำหรับ RAG (docs/RAG_PLAN.md ข้อ 3)

เก็บข้อความส่วนนำของบทความ Wikipedia ที่เป็นที่มาของสถานที่ที่ตรวจที่มาแล้ว ต่อสถานที่ละไม่เกิน 2 ก้อน
ก้อนละไม่เกิน 1,200 ตัวอักษร ข้อความ © ผู้เขียน Wikipedia ใช้ภายใต้ CC BY-SA 4.0 ต้องแสดงที่มาและบอกว่ามีการตัดทอน

กติกา: ไม่เก็บย่อหน้าที่พูดถึงราคา ค่าเข้า คะแนน รีวิว การจอง (CONTRACT ข้อ 1) ไม่แต่งข้อความเอง
ที่หาไม่ได้ปล่อยว่าง และตรวจว่าบทความตรงกับสถานที่ (ชื่อ และพิกัดห่างไม่เกิน 3 กม.) ก่อนใช้
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from .fetch import UpstreamError
from .geo import haversine_km

DEFAULT_DIR = Path(__file__).parent / "data" / "knowledge"
LICENSE = "CC BY-SA 4.0"
MAX_CHARS = 1200       # ต่อก้อน
MAX_CHUNKS = 2         # ต่อสถานที่
MIN_PARAGRAPH = 20     # สั้นกว่านี้ถือว่าเป็นหัวข้อหรือเศษ ไม่เก็บ
MAX_COORD_KM = 3.0     # พิกัดบทความห่างจากพิกัดสถานที่ได้ไม่เกินนี้
BATCH = 20             # Wikipedia ให้ข้อความส่วนนำได้ไม่เกิน 20 หน้าต่อคำขอ

# ย่อหน้าที่มีคำเหล่านี้ถูกตัดทิ้งทั้งย่อหน้า (ราคา ค่าเข้า คะแนน รีวิว การจอง)
FORBIDDEN = re.compile(
    r"ราคา|ค่าเข้า|ค่าธรรมเนียม|ค่าผ่านประตู|ค่าบัตร|ค่าตั๋ว|บาท|\d\s*ดาว|คะแนน|รีวิว|จอง|ชำระเงิน|฿"
    r"|\b(?:prices?|priced|tickets?|admission|entrance fees?|fees?|baht|thb|reviews?|ratings?|rated|"
    r"booking|bookings|book now|tripadvisor)\b",
    re.IGNORECASE,
)
_REF_MARK = re.compile(r"\[(?:\d+|[a-z]|หมายเหตุ \d+|note \d+)\]", re.IGNORECASE)


# ---------- ข้อความ ----------

def norm(s: str) -> str:
    """ตัวพิมพ์เล็ก เก็บเฉพาะตัวอักษร (รวมสระวรรณยุกต์ไทย) และตัวเลข"""
    return "".join(ch for ch in s.lower() if unicodedata.category(ch)[0] in "LMN")


def strip_parens(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", title).strip()


def clean_paragraphs(text: str) -> tuple[list[str], int]:
    """แยกย่อหน้า ตัดเลขอ้างอิง และตัดย่อหน้าที่มีคำต้องห้าม คืน (ย่อหน้าที่เก็บ, จำนวนที่ตัดเพราะคำต้องห้าม)"""
    kept, dropped = [], 0
    for raw in (text or "").splitlines():
        p = re.sub(r"\s+", " ", _REF_MARK.sub("", raw)).strip()
        if len(p) < MIN_PARAGRAPH:
            continue
        if FORBIDDEN.search(p):
            dropped += 1
            continue
        kept.append(p)
    return kept, dropped


def _cut(p: str, limit: int) -> str:
    if len(p) <= limit:
        return p
    cut = p[:limit]
    # ตัดที่ท้ายประโยคหรือช่องว่างสุดท้าย ถ้าไม่มี (ข้อความไทยติดกัน) ตัดตรงๆ
    for sep in (". ", "! ", "? "):
        i = cut.rfind(sep)
        if i > limit // 2:
            return cut[: i + 1]
    i = cut.rfind(" ")
    return (cut[:i] if i > limit // 2 else cut).rstrip()


def chunk_paragraphs(paras: list[str], limit: int = MAX_CHARS, max_chunks: int = MAX_CHUNKS) -> list[str]:
    """รวมย่อหน้าเป็นก้อนไม่เกิน limit ตัวอักษร ไม่เกิน max_chunks ก้อน ย่อหน้าที่ยาวเกินถูกตัดท้าย"""
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + 1 + len(p) <= limit:
            cur = f"{cur}\n{p}"
            continue
        if cur:
            chunks.append(cur)
            if len(chunks) == max_chunks:
                return chunks
        cur = _cut(p, limit)
    if cur and len(chunks) < max_chunks:
        chunks.append(cur)
    return chunks


# ---------- ที่มา ----------

def parse_wiki_url(url: str) -> tuple[str, str] | None:
    """https://en.wikipedia.org/wiki/Grand_Palace -> ("en", "Grand Palace")"""
    u = urllib.parse.urlparse(url or "")
    m = re.fullmatch(r"([a-z\-]{2,12})\.wikipedia\.org", u.netloc.lower())
    if not m or not u.path.startswith("/wiki/"):
        return None
    title = urllib.parse.unquote(u.path[len("/wiki/"):]).replace("_", " ").strip()
    return (m.group(1), title) if title else None


def wiki_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="_()")


def name_matches(names: list[str | None], title: str) -> bool:
    """ชื่อสถานที่ตัวใดตัวหนึ่ง (ยาวพอ) ต้องอยู่ในชื่อบทความ หรือชื่อบทความอยู่ในชื่อสถานที่"""
    t = norm(strip_parens(title))
    if not t:
        return False
    for n in names:
        n = norm(n or "")
        if len(n) >= 3 and (n in t or (len(t) >= 3 and t in n)):
            return True
    return False


def coords_ok(place: dict, page: dict, max_km: float = MAX_COORD_KM) -> bool | None:
    """True/False ตามระยะ None ถ้าบทความไม่มีพิกัด (ตรวจไม่ได้)"""
    if page.get("lat") is None or page.get("lon") is None:
        return None
    return haversine_km(place["lat"], place["lon"], page["lat"], page["lon"]) <= max_km


# ---------- สร้างก้อนจากหน้าที่ดึงมา ----------

def make_docs(place: dict, page: dict, lang: str, today: str) -> tuple[str, list[dict], int]:
    """คืน (สถานะ, ก้อนข้อความ, จำนวนย่อหน้าที่ตัดเพราะคำต้องห้าม) สถานะ: ok | no_text"""
    paras, dropped = clean_paragraphs(page.get("extract") or "")
    chunks = chunk_paragraphs(paras)
    if not chunks:
        return "no_text", [], dropped
    docs = [{
        "id": f"k:{place['id']}:{i}",
        "place_id": f"v:{place['id']}",
        "title": page["title"],
        "text": text,
        "url": wiki_url(lang, page["title"]),
        "lang": lang,
        "license": LICENSE,
        "checked_on": today,
    } for i, text in enumerate(chunks)]
    return "ok", docs, dropped


# ---------- MediaWiki API ----------

def api_params(lang: str, titles: list[str]) -> dict:
    p = {
        "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
        "prop": "extracts|coordinates|langlinks", "exintro": "1", "explaintext": "1", "exlimit": "max",
        "colimit": "max", "lllimit": "max", "titles": "|".join(titles),
    }
    if lang != "th":
        p["lllang"] = "th"
    return p


def parse_pages(resp: dict, requested: list[str]) -> dict[str, dict]:
    """แปลงคำตอบ MediaWiki เป็น {ชื่อที่ขอ: หน้า} ตามการแปลงชื่อ (normalized) และการเปลี่ยนเส้นทาง (redirects)
    หน้า = {title, extract, lat, lon, th_title} หน้าที่ไม่มีไม่อยู่ในผล"""
    q = (resp or {}).get("query") or {}
    hop = {}
    for key in ("normalized", "redirects"):
        for m in q.get(key) or []:
            hop[m["from"]] = m["to"]
    by_title = {}
    for pg in q.get("pages") or []:
        if pg.get("missing") or pg.get("invalid"):
            continue
        coord = (pg.get("coordinates") or [{}])[0]
        th = next((ll.get("title") for ll in pg.get("langlinks") or [] if ll.get("lang") == "th"), None)
        by_title[pg["title"]] = {"title": pg["title"], "extract": pg.get("extract") or "",
                                 "lat": coord.get("lat"), "lon": coord.get("lon"), "th_title": th}
    out = {}
    for t in requested:
        cur, seen = t, set()
        while cur in hop and cur not in seen:   # normalized แล้ว redirects
            seen.add(cur)
            cur = hop[cur]
        if cur in by_title:
            out[t] = by_title[cur]
    return out


def fetch_pages(client: Any, lang: str, titles: list[str], pause: float = 1.0,
                sleep: Callable[[float], None] = time.sleep) -> dict[str, dict]:
    out: dict[str, dict] = {}
    uniq = list(dict.fromkeys(titles))
    for i in range(0, len(uniq), BATCH):
        batch = uniq[i:i + BATCH]
        if i:
            sleep(pause)
        resp = client.get_json(f"https://{lang}.wikipedia.org/w/api.php", api_params(lang, batch))
        out.update(parse_pages(resp, batch))
    return out


# ---------- สร้างคลังของหนึ่งจังหวัด ----------

def build_province(client: Any, places: list[dict], today: str, pause: float = 1.0,
                   include_review: bool = False, sleep: Callable[[float], None] = time.sleep) -> tuple[list[dict], dict]:
    """คืน (ก้อนข้อความ, รายงาน) รายงาน: counts ต่อสถานะ + review/far/name_check = รายการให้คนตรวจ (review ไม่ถูกบันทึกเว้นแต่ include_review)

    สถานะ: ok | no_page (หาบทความไม่เจอ) | no_text (ไม่มีข้อความที่ใช้ได้) | review (ชื่อไม่ตรง) | far (พิกัดห่างเกิน)
    ภาษาไทยก่อน: ถ้าบทความที่เป็นที่มาเป็นอังกฤษและมีลิงก์ภาษาไทย จะดึงฉบับไทยมาใช้แทน (เชื่อลิงก์ภาษาเพราะบรรณาธิการโยงไว้)
    """
    report = {"counts": {"ok": 0, "no_page": 0, "no_text": 0, "review": 0, "far": 0, "th": 0, "en": 0},
              "dropped_paragraphs": 0, "review": [], "name_check": [], "far": []}
    wanted: list[tuple[dict, str, str]] = []
    for p in places:
        src = next((w for s in p.get("sources") or [] if (w := parse_wiki_url(s.get("url", "")))), None)
        if src is None:
            report["counts"]["no_page"] += 1
            continue
        wanted.append((p, src[0], src[1]))

    pages: dict[tuple[str, str], dict] = {}
    for lang in sorted({w[1] for w in wanted}):
        titles = [w[2] for w in wanted if w[1] == lang]
        for t, pg in fetch_pages(client, lang, titles, pause, sleep).items():
            pages[(lang, t)] = pg

    # ฉบับไทยของบทความอังกฤษ
    th_titles = [pg["th_title"] for (lang, _), pg in pages.items() if lang != "th" and pg.get("th_title")]
    if th_titles:
        sleep(pause)
        for t, pg in fetch_pages(client, "th", th_titles, pause, sleep).items():
            pages[("th", t)] = pg

    docs: list[dict] = []
    for p, lang, title in wanted:
        src_page = pages.get((lang, title))
        if src_page is None:
            report["counts"]["no_page"] += 1
            continue
        near = coords_ok(p, src_page)
        if near is False:
            report["counts"]["far"] += 1
            report["far"].append((p["id"], p["name_th"], src_page["title"]))
            continue
        matched = name_matches([p.get("name_th"), p.get("name_en")], src_page["title"])
        if not matched and near is not True:
            # ชื่อไม่ตรงและไม่มีพิกัดยืนยัน = ให้คนตรวจ
            report["counts"]["review"] += 1
            report["review"].append((p["id"], p["name_th"], src_page["title"]))
            if not include_review:
                continue
        elif not matched:
            # ชื่อไม่ตรงแต่พิกัดตรง: ใช้ได้ แต่แจ้งให้คนตรวจชื่อ
            report["name_check"].append((p["id"], p["name_th"], src_page["title"]))
        candidates = []
        th = pages.get(("th", src_page["th_title"])) if lang != "th" and src_page.get("th_title") else None
        if th is not None and coords_ok(p, th) is not False:
            candidates.append(("th", th))
        candidates.append((lang, src_page))
        for use_lang, pg in candidates:
            status, got, dropped = make_docs(p, pg, use_lang, today)
            report["dropped_paragraphs"] += dropped
            if status == "ok":
                docs.extend(got)
                report["counts"]["ok"] += 1
                report["counts"][use_lang if use_lang in ("th", "en") else "en"] += 1
                break
        else:
            report["counts"]["no_text"] += 1
    return docs, report


# ---------- เก็บและอ่านไฟล์ ----------

def write_province(directory: Path | str, province: str, docs: list[dict], built_on: str) -> Path:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{province}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"_meta": {"province": province, "built_on": built_on, "count": len(docs),
                                         "source": "Wikipedia (CC BY-SA 4.0) ตัดทอนส่วนนำของบทความ"},
                               "docs": docs}, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def load_all(directory: Path | str = DEFAULT_DIR) -> list[dict]:
    d = Path(directory)
    out: list[dict] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            out.extend(json.loads(f.read_text(encoding="utf-8")).get("docs", []))
        except (OSError, ValueError):
            continue
    return out


REQUIRED = ("id", "place_id", "title", "text", "url", "lang", "license", "checked_on")


def validate(docs: list[dict], known_place_ids: set[str]) -> list[str]:
    """คืนรายการปัญหา (ว่าง = ใช้ได้) ตามกติกาใน docs/RAG_PLAN.md ข้อ 3"""
    problems, seen = [], set()
    for d in docs:
        i = d.get("id", "?")
        missing = [k for k in REQUIRED if not d.get(k)]
        if missing:
            problems.append(f"{i}: ขาดฟิลด์ {', '.join(missing)}")
            continue
        if i in seen:
            problems.append(f"{i}: id ซ้ำ")
        seen.add(i)
        if d["place_id"] not in known_place_ids:
            problems.append(f"{i}: place_id {d['place_id']} ไม่มีในสถานที่ที่ตรวจแล้ว")
        if len(d["text"]) > MAX_CHARS:
            problems.append(f"{i}: ข้อความยาว {len(d['text'])} เกิน {MAX_CHARS}")
        if FORBIDDEN.search(d["text"]):
            problems.append(f"{i}: มีคำต้องห้าม (ราคา คะแนน รีวิว จอง)")
        if d["license"] != LICENSE:
            problems.append(f"{i}: สัญญาอนุญาตต้องเป็น {LICENSE}")
        if parse_wiki_url(d["url"]) is None:
            problems.append(f"{i}: url ไม่ใช่บทความ Wikipedia")
    return problems
