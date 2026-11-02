"""ตัวทำความเข้าใจข้อความแชตแบบกฎ (ไม่ใช้ LLM) แปลงข้อความเป็นความตั้งใจที่ค้นได้จริง

ข้อความผู้ใช้ถือเป็นข้อมูล ไม่ใช่คำสั่ง: ตัวนี้แค่ดึงคำสำคัญ (ประเภท จังหวัด รัศมี จำนวน ชื่อที่พัก)
ไม่ทำอย่างอื่นนอกจากเลือกว่าจะเรียกเครื่องมือค้นตัวไหน
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.places.provinces import PROVINCES

MAX_MESSAGE = 500
DEFAULT_LIMIT = 5
MAX_LIMIT = 10
MAX_RADIUS = 30.0

_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

CAFE_WORDS = ("คาเฟ่", "คาเฟ", "ร้านกาแฟ", "กาแฟ", "cafe", "coffee")
ATTRACTION_WORDS = ("ที่เที่ยว", "สถานที่เที่ยว", "สถานที่ท่องเที่ยว", "ท่องเที่ยว", "แหล่งท่องเที่ยว", "วัด", "น้ำตก",
                    "ภูเขา", "ดอย", "ชายหาด", "ทะเล", "พิพิธภัณฑ์", "จุดชมวิว", "ธรรมชาติ", "สวน", "ตลาด", "เที่ยว",
                    "attraction")
LODGING_WORDS = ("โรงแรม", "รีสอร์ท", "รีสอร์ต", "โฮสเทล", "โฮมสเตย์", "เกสต์เฮาส์", "วิลล่า", "บังกะโล", "ที่พัก")
# หัวข้อที่ระบบไม่มีข้อมูล/ไม่ทำ (CONTRACT ข้อ 1) บอกผู้ใช้ตรงๆ แทนการเดา
MONEY_WORDS = ("ราคา", "ค่าเข้า", "ค่าใช้จ่าย", "งบ", "บาท", "แพง", "ฟรี")
REVIEW_WORDS = ("รีวิว", "คะแนน", "ยอดนิยม", "ดีที่สุด", "อันดับ")
BOOKING_WORDS = ("จอง", "ชำระ", "จ่ายเงิน", "ซื้อตั๋ว", "ซื้อบัตร")
GREETING_WORDS = ("สวัสดี", "หวัดดี", "hello", "hi ", "ช่วยอะไรได้", "ทำอะไรได้", "ใช้ยังไง", "วิธีใช้")

# ชื่อเรียกอื่นของจังหวัด
ALIASES = {
    "กรุงเทพ": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร", "โคราช": "นครราชสีมา", "อยุธยา": "พระนครศรีอยุธยา",
    "ปราจีน": "ปราจีนบุรี", "สุราษฎร์": "สุราษฎร์ธานี", "อุบล": "อุบลราชธานี", "อุดร": "อุดรธานี",
    "นครศรี": "นครศรีธรรมราช", "ประจวบ": "ประจวบคีรีขันธ์", "ภูเก็ต": "ภูเก็ต", "เมืองกาญจน์": "กาญจนบุรี",
}
# ชื่อจังหวัดที่เป็นคำไทยทั่วไปด้วย ต้องมีคำนำหน้าชัดเจนถึงจะนับ ("ไปเลย" ไม่ใช่จังหวัดเลย)
AMBIGUOUS = {"เลย", "ตาก", "แพร่", "น่าน"}
_PREFIX = r"(?:จังหวัด|จ\.|แถว|ใน|ที่|ของ)\s*"

_RADIUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:กม|km|กิโล)", re.I)
_LIMIT_RE = re.compile(r"(\d+)\s*(?:แห่ง|ที่|อัน|ร้าน|รายการ)(?!\s*(?:กม|km))", re.I)
_LODGING_NAME_RE = re.compile(r"(" + "|".join(LODGING_WORDS[:-1]) + r")\s*([^\s]{2,60}(?:\s[A-Za-z0-9&'.-]{1,30}){0,3})")
_NAME_STOP = re.compile(r"(มี|แนะนำ|หา|ไหม|บ้าง|หน่อย|ครับ|ค่ะ|คะ|นะ|อยาก|ช่วย|ที่เที่ยว|คาเฟ่|ร้านกาแฟ|เที่ยว|ใกล้|รอบ|แถว|ใน |ภายใน|อะไร)")


@dataclass
class Intent:
    kinds: tuple[str, ...] = ("attraction", "cafe")
    radius_km: float = MAX_RADIUS
    limit: int = DEFAULT_LIMIT
    province: str | None = None
    lodging_query: str | None = None
    want_lodgings: bool = False          # อยากได้รายชื่อที่พักรอบจุด
    greeting: bool = False
    asks_money: bool = False
    asks_review: bool = False
    asks_booking: bool = False
    notes: list[str] = field(default_factory=list)   # หมายเหตุที่ต้องบอกผู้ใช้ เช่น ปรับรัศมีลงเหลือ 30


def clean(message: str) -> str:
    """ตัดอักขระควบคุม ยุบช่องว่าง ตัดความยาว (ข้อมูลจากผู้ใช้ ไม่ใช่คำสั่ง)"""
    m = _CONTROL.sub(" ", message or "").translate(_DIGITS)
    return re.sub(r"\s+", " ", m).strip()[:MAX_MESSAGE]


def find_province(text: str) -> str | None:
    for p in sorted(PROVINCES, key=len, reverse=True):
        if p in AMBIGUOUS:
            if re.search(_PREFIX + re.escape(p), text):
                return p
        elif p in text:
            return p
    for alias, p in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in text:
            return p
    return None


def _has(text: str, words) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def _lodging_query(text: str) -> tuple[str, tuple[int, int]] | None:
    """คืน (คำค้นชื่อที่พัก, ช่วงตำแหน่งในข้อความ) ช่วงนี้ถูกตัดออกก่อนจับประเภท
    ไม่งั้นชื่ออย่าง "โรงแรมสวนดอก" จะถูกนับว่าถามหา "สวน" """
    m = _LODGING_NAME_RE.search(text)
    if not m:
        return None
    name = m.group(2)
    stop = _NAME_STOP.search(name)
    if stop and stop.start() > 0:
        name = name[:stop.start()]
    elif stop:                       # ขึ้นต้นด้วยคำหยุดเลย (เช่น "โรงแรมใกล้ ...") ไม่ใช่ชื่อ
        return None
    name = name.strip(" .,!?\"'")
    if len(name) < 2:
        return None
    return (m.group(1) + name)[:80], (m.start(), m.start(2) + len(name))


def parse(message: str) -> Intent:
    text = clean(message)
    it = Intent()
    if not text:
        return it
    it.province = find_province(text)
    lodging = _has(text, LODGING_WORDS)
    scan = text
    if lodging and not it.province:
        found = _lodging_query(text)
        if found:
            it.lodging_query = found[0]
            scan = text[:found[1][0]] + " " + text[found[1][1]:]
    cafe, attr = _has(scan, CAFE_WORDS), _has(scan, ATTRACTION_WORDS)
    if cafe and not attr:
        it.kinds = ("cafe",)
    elif attr and not cafe:
        it.kinds = ("attraction",)
    it.want_lodgings = lodging and not cafe and not attr and not it.lodging_query
    m = _RADIUS_RE.search(text)
    if m:
        r = float(m.group(1))
        if r > MAX_RADIUS:
            it.notes.append(f"ค้นได้ไกลสุด {MAX_RADIUS:g} กม. จึงใช้ {MAX_RADIUS:g} กม. แทน")
        elif r > 0:
            it.radius_km = r
    m = _LIMIT_RE.search(text)
    if m and 1 <= int(m.group(1)) <= MAX_LIMIT:
        it.limit = int(m.group(1))
    elif m and int(m.group(1)) > MAX_LIMIT:
        it.limit = MAX_LIMIT
        it.notes.append(f"แสดงได้ครั้งละไม่เกิน {MAX_LIMIT} แห่ง")
    it.asks_money = _has(text, MONEY_WORDS)
    it.asks_review = _has(text, REVIEW_WORDS)
    it.asks_booking = _has(text, BOOKING_WORDS)
    it.greeting = _has(text, GREETING_WORDS) and not (it.province or cafe or attr or lodging)
    return it
