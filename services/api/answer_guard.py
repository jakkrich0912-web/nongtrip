"""ด่านตรวจคำตอบที่ LLM เขียน (RAG ขั้น 3) ตรวจในโค้ดล้วน ไม่ใช้ LLM ตรวจ และไม่ใช้โค้ดของตัวค้นหาร่วมกัน

ตาม docs/RAG_PLAN.md ข้อ 6 ข้อใดไม่ผ่านให้ทิ้งคำตอบของ LLM ทั้งก้อนแล้วใช้คำตอบแบบกฎของรอบนั้น (ผู้เรียกเป็นคนทำ)
ตัวนี้ตอบแค่ ok กับรายการปัญหา ไม่แก้ข้อความให้ เพราะข้อความที่ผ่านการแก้ไม่ใช่ข้อความที่ตรวจแล้ว

ตรวจอะไร
1. ชื่อสถานที่: ชื่อที่รู้จักในระบบ (คลังที่ตรวจแล้ว ชื่อเรื่องของคลังความรู้) ต้องอยู่ในรายการผลค้นรอบนั้นเท่านั้น
   และข้อความที่ใส่เครื่องหมายเน้น (อัญประกาศ ตัวหนา โค้ด) ถือว่าเป็นชื่อ ต้องอยู่ในรายการที่อนุญาต คำถามของผู้ใช้ หรือก้อนความรู้
2. ตัวเลขระยะ: ตัวเลขที่ตามด้วย กม. หรือ km ต้องตรงกับระยะในผลค้น (หรือรัศมีที่ใช้ค้น) พิกัดทศนิยมต้องตรงกับพิกัดในผลค้น
3. ที่มา: รหัส [k:...] ต้องมีจริงในก้อนที่ส่งไป และต้องมีอย่างน้อยหนึ่งรหัสเมื่อมีก้อนความรู้ส่งไป
4. คำต้องห้าม: ราคา ค่าเข้า บาท ดาว คะแนน รีวิว จอง ชำระเงิน และการจัดอันดับความนิยม
5. รูปแบบ: ไม่มีแท็ก HTML ลิงก์ หรือโค้ดบล็อก เป็นภาษาไทยเป็นหลัก ความยาวไม่เกินเพดาน
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

GUARD_NOTICE = "ระบบตรวจคำตอบอัตโนมัติไม่ผ่าน จึงแสดงผลแบบพื้นฐานแทน"
MAX_ANSWER_CHARS = 2500
DIST_TOLERANCE_KM = 0.05
COORD_TOLERANCE = 0.001
MIN_NAME_LEN = 4           # ชื่อที่สั้นกว่านี้ (หลังตัดเว้นวรรค) ไม่ใช้ตรวจแบบค้นสตริง เสี่ยงตรงกับคำทั่วไป
MIN_THAI_SHARE = 0.4       # สัดส่วนอักษรไทยในตัวอักษรทั้งหมด (ตรวจเมื่อมีตัวอักษร 30 ตัวขึ้นไป)

_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_DROP = re.compile(r"[\s\-–—_.,;:!?'\"“”‘’()\[\]{}/\\|*`«»「」・•·…]+")
_PAREN = re.compile(r"[(（][^)）]*[)）]")

CITE = re.compile(r"\[(k:[^\]\s]*)\]")
CITE_LIKE = re.compile(r"k:[A-Za-z0-9_.\-]+:\d+")
KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:กม\.?|กิโลเมตร|กิโล(?!กรัม)|km)(?![A-Za-z])", re.IGNORECASE)
DECIMAL = re.compile(r"(?<![\d.])(\d{1,3}\.\d{3,})(?![\d])")
MARKED = re.compile(r"“([^”]{2,80})”|\"([^\"]{2,80})\"|‘([^’]{2,80})’|\*\*([^*]{2,80})\*\*|`([^`]{2,80})`|「([^」]{2,80})」")
HTML_TAG = re.compile(r"</?[A-Za-z][^>]{0,80}>")
URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

_NUM_WORD = r"(?:\d|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ|ร้อย|พัน|หมื่น|แสน|ล้าน)"
_TH = r"[\u0E00-\u0E7F]"
# "บาท" นับเฉพาะที่เป็นหน่วยเงิน (ตามหลังตัวเลข หรือเป็นคำเดี่ยว) ไม่นับ "พระบาท" "พุทธบาท" "บาทหลวง" ที่อยู่ในชื่อและคำอื่น
FORBIDDEN = {
    "ราคา/ค่าใช้จ่าย": re.compile(
        r"ราคา|ค่าเข้า|ค่าบัตร|ค่าตั๋ว|ค่าธรรมเนียม|ค่าใช้จ่าย|งบประมาณ|" + _NUM_WORD + r"\s*บาท|(?<!" + _TH + r")บาท(?!" + _TH + r")"
        r"|฿|\bTHB\b|\bbaht\b|\bprices?\b|\btickets?\b|\badmission\b|\bfees?\b|\bcost\b", re.IGNORECASE),
    "คะแนน/รีวิว": re.compile(
        r"รีวิว|คะแนน|\d\s*ดาว|(?:หนึ่ง|สอง|สาม|สี่|ห้า)\s*ดาว|ดาว(?:รีวิว|โรงแรม)|★|⭐|\breviews?\b|\bratings?\b|\bstars?\b", re.IGNORECASE),
    "จอง/ชำระเงิน": re.compile(r"จอง|ชำระเงิน|จ่ายเงิน|ซื้อตั๋ว|ซื้อบัตร|\bbook(?:ing)?\b|\bpay(?:ment)?\b", re.IGNORECASE),
    "จัดอันดับความนิยม": re.compile(r"ยอดนิยม|ยอดฮิต|ดีที่สุด|อันดับ\s*\d|ขายดี|\bmost popular\b|\btop\s*\d", re.IGNORECASE),
}


def _norm(s: str) -> str:
    return _DROP.sub("", unicodedata.normalize("NFC", s or "").lower())


def _variants(name: str) -> set[str]:
    """ชื่อเต็มกับชื่อที่ตัดวงเล็บออก (เช่น "วัดท่าไม้ (จังหวัดสมุทรสาคร)")"""
    out = {_norm(name), _norm(_PAREN.sub("", name or ""))}
    return {v for v in out if v}


def _related(a: str, b: str) -> bool:
    """เทียบชื่อที่ตัดเว้นวรรคแล้ว: เท่ากัน หรืออันหนึ่งอยู่ในอีกอัน (ยอมให้เรียกชื่อสั้น/ชื่อเต็ม)"""
    return a == b or (len(a) >= MIN_NAME_LEN and a in b) or (len(b) >= MIN_NAME_LEN and b in a)


def _names(item: dict) -> list[str]:
    return [str(item[k]) for k in ("name_th", "name_en", "name", "title") if item.get(k)]


def _num(s: str) -> float:
    return float(s.translate(_DIGITS).replace(",", "."))


def check_answer(text: str, *, places: Iterable[dict] = (), chunks: Iterable[dict] = (),
                 known_names: Iterable[str] = (), question: str = "",
                 radius_km: float | None = None, require_citation: bool | None = None, lang: str = "th") -> dict:
    """ตรวจคำตอบหนึ่งก้อน คืน {"ok": bool, "problems": [{"rule","detail"}], "problem_count": int}

    places: รายการที่ผ่านตัวตรวจผลค้นแล้ว (name_th/name_en/name, distance_km หรือ distance_from_pin_km, lat, lon)
    chunks: ก้อนความรู้ที่ส่งให้ LLM (id, title, text)
    known_names: ชื่อที่รู้จักทั้งระบบ (ชื่อสถานที่ที่ตรวจแล้ว ชื่อเรื่องของคลังความรู้) ไว้จับชื่อที่ LLM เอามาจากที่อื่น
    question: ข้อความของผู้ใช้ (คำที่ผู้ใช้พิมพ์เองใส่เครื่องหมายเน้นได้)
    require_citation: บังคับให้มีรหัสที่มา (ค่าเริ่มต้น: เมื่อมีก้อนความรู้)
    lang: th/en ภาษาที่คาดหวังของคำตอบ (กฎอื่นทุกข้อเหมือนกัน ตรวจคำต้องห้ามทั้งไทยและอังกฤษอยู่แล้ว)
    """
    places, chunks = list(places), list(chunks)
    problems: list[dict] = []

    def bad(rule: str, detail: str) -> None:
        problems.append({"rule": rule, "detail": detail[:200]})

    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "problems": [{"rule": "ว่าง", "detail": "คำตอบว่าง"}], "problem_count": 1}
    t = unicodedata.normalize("NFC", text)
    if len(t) > MAX_ANSWER_CHARS:
        bad("ความยาว", f"{len(t)} ตัวอักษร เกินเพดาน {MAX_ANSWER_CHARS}")

    # 1. ชื่อสถานที่
    allowed: set[str] = set()
    for p in places:
        for n in _names(p):
            allowed |= _variants(n)
    for c in chunks:
        allowed |= _variants(c.get("title", ""))
    t_norm = _norm(t)
    for n in sorted({v for k in known_names for v in _variants(k)}):
        if len(n) < MIN_NAME_LEN or n not in t_norm:
            continue
        if not any(_related(n, a) for a in allowed):
            bad("ชื่อสถานที่", f"กล่าวถึง {n!r} ซึ่งไม่อยู่ในผลค้นรอบนี้")
    context = _norm(question) + "".join(_norm(c.get("text", "")) for c in chunks)
    for m in MARKED.finditer(t):
        span = next(g for g in m.groups() if g)
        s = _norm(span)
        if len(s) < MIN_NAME_LEN or CITE.fullmatch(f"[{span}]"):
            continue
        if any(_related(s, a) for a in allowed) or s in context:
            continue
        bad("ชื่อสถานที่", f"ข้อความที่เน้นเป็นชื่อ {span!r} ไม่อยู่ในผลค้น คำถาม หรือก้อนความรู้")

    # 2. ตัวเลขระยะและพิกัด
    km_ok = [float(d) for p in places for d in (p.get("distance_km"), p.get("distance_from_pin_km")) if d is not None]
    if radius_km is not None:
        km_ok.append(float(radius_km))
    for m in KM.finditer(t):
        v = _num(m.group(1))
        if not any(abs(v - d) <= DIST_TOLERANCE_KM + 1e-9 for d in km_ok):
            bad("ระยะ", f"{m.group(0).strip()} ไม่ตรงกับระยะในผลค้น")
    coords = [float(c) for p in places for c in (p.get("lat"), p.get("lon")) if c is not None]
    for m in DECIMAL.finditer(t.translate(_DIGITS)):
        v = float(m.group(1))
        if not any(abs(v - c) <= COORD_TOLERANCE + 1e-9 for c in coords):
            bad("พิกัด", f"ตัวเลข {m.group(1)} ไม่ตรงกับพิกัดในผลค้น")

    # 3. ที่มา
    ids = {str(c.get("id")) for c in chunks if c.get("id")}
    cited = [m.group(1) for m in CITE.finditer(t)]
    for code in cited:
        if code not in ids:
            bad("ที่มา", f"รหัส [{code}] ไม่มีในก้อนที่ส่งไป")
    in_brackets = {m.start(1) for m in CITE.finditer(t)}
    for m in CITE_LIKE.finditer(t):
        if m.start() not in in_brackets:
            bad("ที่มา", f"รหัส {m.group(0)} ไม่อยู่ในรูป [k:...]")
    need = bool(chunks) if require_citation is None else require_citation
    if need and not cited:
        bad("ที่มา", "ใช้ก้อนความรู้แต่ไม่มีรหัสที่มาในคำตอบ")

    # 4. คำต้องห้าม (ข้อความตัดรหัสที่มาออกก่อน เพราะรหัสมีตัวอักษรที่ไม่เกี่ยวกับเนื้อหา)
    body = CITE.sub(" ", t)
    for rule, rx in FORBIDDEN.items():
        m = rx.search(body)
        if m:
            bad("คำต้องห้าม", f"{rule}: พบ {m.group(0)!r}")

    # 5. รูปแบบ
    if HTML_TAG.search(t):
        bad("รูปแบบ", "มีแท็ก HTML หรือแท็กอื่น")
    if URL.search(t):
        bad("รูปแบบ", "มีลิงก์ (ที่มาแสดงผ่าน event sources เท่านั้น)")
    if "```" in t:
        bad("รูปแบบ", "มีโค้ดบล็อก")
    thai = len(re.findall(r"[฀-๿]", t))
    latin = len(re.findall(r"[A-Za-z]", t))
    if thai + latin >= 30:
        if lang == "en" and latin / (thai + latin) < MIN_THAI_SHARE:
            bad("ภาษา", "ไม่ใช่ภาษาอังกฤษเป็นหลัก")
        elif lang != "en" and thai / (thai + latin) < MIN_THAI_SHARE:
            bad("ภาษา", "ไม่ใช่ภาษาไทยเป็นหลัก")

    return {"ok": not problems, "problems": problems[:20], "problem_count": len(problems)}
