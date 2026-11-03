"""ตัวทำความเข้าใจข้อความแชตแบบกฎ (ไม่ใช้ LLM) แปลงข้อความเป็นความตั้งใจที่ค้นได้จริง

ข้อความผู้ใช้ถือเป็นข้อมูล ไม่ใช่คำสั่ง: ตัวนี้แค่ดึงคำสำคัญ (ประเภท จังหวัด รัศมี จำนวน ชื่อที่พัก)
ไม่ทำอย่างอื่นนอกจากเลือกว่าจะเรียกเครื่องมือค้นตัวไหน
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.places.provinces import PROVINCES, PROVINCES_EN

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
REVIEW_WORDS = ("รีวิว", "คะแนน", "ยอดนิยม", "ดีที่สุด", "อันดับ", "คนไปบ่อย", "คนไปเยอะ", "คนเยอะ", "ฮิต", "นิยม")
BOOKING_WORDS = ("จอง", "ชำระ", "จ่ายเงิน", "ซื้อตั๋ว", "ซื้อบัตร")
# คำถามกว้างๆ ที่ยังนับว่าอยากค้นรอบจุดเดิม ("มีอะไรบ้าง" "แนะนำหน่อย" "อีก") ถ้าไม่มีคำพวกนี้หรือคำอื่นที่ระบบรู้จักเลย ถือว่านอกเรื่อง
GENERIC_WORDS = ("มีอะไร", "แนะนำ", "ใกล้", "รอบ", "แถว", "หา", "ไหน", "บ้าง", "อีก", "ต่อ", "เพิ่ม", "สถานที่", "พาไป",
                 "ไปดี", "จุดเริ่ม", "ระยะ", "รัศมี", "เรียง", "เปลี่ยน")
FOOD_WORDS = ("กินข้าว", "ร้านอาหาร", "อาหาร", "หิว", "อร่อย", "ข้าว", "กินอะไร", "ของกิน", "เมนู")
GREETING_WORDS = ("สวัสดี", "หวัดดี", "hello", "hi ", "ช่วยอะไรได้", "ทำอะไรได้", "ใช้ยังไง", "วิธีใช้")

# คุยเล่นสั้นๆ ที่ตอบได้ตรงๆ โดยไม่ต้องเดาและไม่ต้องใช้ LLM (ชื่อ ทักทายสบายดีไหม ขอบคุณ ลาก่อน ฯลฯ)
# ใช้เฉพาะข้อความสั้นที่ไม่มีชื่อจังหวัด/ประเภทสถานที่ปนมา ("ขอบคุณ แล้วคาเฟ่ล่ะ" ยังค้นตามปกติ)
SMALLTALK_MAX_CHARS = 40
SMALLTALK_TH = {
    "bot": ("เป็นคนหรือ", "เป็นคนรึ", "เป็นเอไอ", "เป็น ai", "เป็นบอท", "บอทหรือ", "คนหรือบอท", "คนหรือเปล่า", "หุ่นยนต์หรือ"),
    "wellbeing": ("สบายดีไหม", "สบายดีมั้ย", "สบายดีป่าว", "สบายดีหรือเปล่า", "เป็นไงบ้าง", "เป็นยังไงบ้าง"),
    "thanks": ("ขอบคุณ", "ขอบใจ", "แต๊งกิ้ว"),
    "bye": ("บ๊ายบาย", "บายนะ", "ลาก่อน", "ไว้เจอกัน", "ไปแล้วนะ"),
    "praise": ("เก่งจัง", "เก่งมาก", "น่ารักจัง", "น่ารักมาก", "เจ๋งมาก", "เจ๋งจัง", "ดีมาก", "สุดยอด"),
    "weather": ("ฝนตก", "อากาศ", "พยากรณ์"),
    "bored": ("เบื่อ", "เหงา"),
}
# ถามชื่อ/ผู้สร้าง "ของน้องทริป" จับเฉพาะทั้งข้อความที่เป็นคำถามนั้นจริง ๆ ไม่จับ "เขื่อนภูมิพลเดิมชื่ออะไร" หรือ "ชื่อไร่เลย์มาจากไหน"
_ADDRESS = r"(?:สวัสดี\S*\s*)?(?:คุณ|เธอ|เรา|น้อง(?:ทริป)?|ตัวเอง|แก|ท่าน)?\s*"
_END = r"(?:\s*(?:หน่อย|เหรอ|หรอ|ครับ|ค่ะ|คะ|นะ|จ๊ะ|จ้ะ|ล่ะ|อะ|ฮะ|เนี่ย))*\s*[?？]*$"
_NAME_TH = re.compile("^" + _ADDRESS + r"(?:ชื่ออะไร|ชื่อไร|ชื่อว่าอะไร|คือใคร|เป็นใคร|แนะนำตัว)" + _END)
_MAKER_TH = re.compile("^" + _ADDRESS + r"(?:ใคร(?:เป็นคน)?(?:สร้าง|ทำ|พัฒนา)(?:ขึ้นมา)?(?:เธอ|เรา|คุณ|น้องทริป)?)" + _END)
_WEATHER_MAX_CHARS = 20  # ข้อความยาว ("พยากรณ์อากาศโตเกียวพรุ่งนี้") ปล่อยให้ผู้ตอบหลักตัดสิน
SMALLTALK_EN = {
    "bot": re.compile(r"\bare you (?:a |an )?(?:human|real|robot|bot|ai|person)\b", re.I),
    "name": re.compile(r"\b(?:your name|who are you|what are you called|introduce yourself)\b", re.I),
    "maker": re.compile(r"\bwho (?:made|built|created|developed) you\b", re.I),
    "wellbeing": re.compile(r"\bhow are you|how(?:'s| is) it going\b", re.I),
    "thanks": re.compile(r"\bthank(?:s| you)\b|\bthx\b", re.I),
    "bye": re.compile(r"\b(?:bye|goodbye|see you|good night)\b", re.I),
    "praise": re.compile(r"\b(?:you(?:'re| are) (?:great|awesome|smart|cute|amazing)|well done|good job)\b", re.I),
    "weather": re.compile(r"\b(?:weather|forecast|will it rain|is it raining)\b", re.I),
    "bored": re.compile(r"\b(?:i(?:'m| am) bored|so bored|i(?:'m| am) lonely)\b", re.I),
}


_BYE_EXACT = re.compile(r"^(?:บ๊?าย|บ๊ายบาย)(?:บาย)?\s*(?:ค่ะ|คะ|ครับ|นะ|จ้า|จ้ะ)*$")  # "บาย" อยู่ในคำว่า "สบาย" จึงจับเฉพาะทั้งข้อความ


def smalltalk_kind(text: str) -> str | None:
    """ชนิดของการคุยเล่นสั้นๆ ที่ตอบสำเร็จรูปได้ หรือ None ถ้าไม่ใช่"""
    if len(text) > SMALLTALK_MAX_CHARS:
        return None
    t = text.strip()
    if _BYE_EXACT.match(t):
        return "bye"
    if _NAME_TH.match(t):
        return "name"
    if _MAKER_TH.match(t):
        return "maker"
    for kind, words in SMALLTALK_TH.items():
        if any(w in text for w in words):
            if kind == "weather" and len(text) > _WEATHER_MAX_CHARS:
                continue
            return kind
    for kind, pattern in SMALLTALK_EN.items():
        if pattern.search(text) and not (kind == "weather" and len(text) > _WEATHER_MAX_CHARS):
            return kind
    return None

# สิ่งที่ผู้ใช้อยากหาแบบเจาะจง ใช้พูดทวนตอนถามว่าให้ค้นแถวไหน ("อยากหาวัดใช่ไหม")
SUBJECTS = (("วัด", "วัด", "temples"), ("น้ำตก", "น้ำตก", "waterfalls"), ("ทะเล", "ทะเล", "beaches"), ("หาด", "ชายหาด", "beaches"),
            ("ดอย", "ดอยและภูเขา", "mountains"), ("ภูเขา", "ดอยและภูเขา", "mountains"), ("พิพิธภัณฑ์", "พิพิธภัณฑ์", "museums"),
            ("ตลาด", "ตลาด", "markets"), ("อุทยาน", "อุทยาน", "national parks"), ("จุดชมวิว", "จุดชมวิว", "viewpoints"),
            ("เกาะ", "เกาะ", "islands"))
_EN_SUBJECTS = ((re.compile(r"\btemples?\b", re.I), "วัด", "temples"), (re.compile(r"\bwaterfalls?\b", re.I), "น้ำตก", "waterfalls"),
                (re.compile(r"\bbeach(?:es)?\b", re.I), "ชายหาด", "beaches"), (re.compile(r"\bmuseums?\b", re.I), "พิพิธภัณฑ์", "museums"),
                (re.compile(r"\bmarkets?\b", re.I), "ตลาด", "markets"), (re.compile(r"\bviewpoints?\b", re.I), "จุดชมวิว", "viewpoints"),
                (re.compile(r"\bnational parks?\b", re.I), "อุทยาน", "national parks"), (re.compile(r"\bislands?\b", re.I), "เกาะ", "islands"),
                (re.compile(r"\bmountains?\b", re.I), "ดอยและภูเขา", "mountains"))

# หัวข้อนอกเรื่องที่พบบ่อย ตอบให้ตรงหัวข้อแทนข้อความกลาง ๆ (เรียงตามลำดับที่ตรวจ)
OFF_TOPIC_KINDS = {
    "health": ("ปวดหัว", "ปวดท้อง", "ปวด", "ป่วย", "เป็นไข้", "ไม่สบาย", "กินยา", "ยาอะไร", "หาหมอ", "โรค", "เจ็บคอ", "ท้องเสีย"),
    "tech": ("คอม", "โน้ตบุ๊ก", "โน๊ตบุ๊ค", "โน้ตบุ๊ค", "มือถือ", "โทรศัพท์", "ไวไฟ", "wifi", "เน็ตช้า", "เน็ตหลุด", "อินเทอร์เน็ต",
             "โปรแกรม", "เขียนโค้ด", "โค้ด", "ปริ้น", "แบตเตอรี่", "แบตหมด", "ไอโฟน", "แอนดรอยด์"),
    "study": ("การบ้าน", "ข้อสอบ", "สอบตก", "สอบเข้า", "อ่านหนังสือสอบ", "สอบปลายภาค", "สอบกลางภาค", "ทำรายงาน", "วิทยานิพนธ์",
              "เรียนต่อ", "ติวหนังสือ"),
    "money": ("หุ้น", "ลงทุน", "คริปโต", "บิตคอยน์", "กู้เงิน", "ภาษี", "ดอกเบี้ย"),
    "love": ("แฟน", "อกหัก", "จีบ", "เลิกกัน", "คนที่ชอบ"),
    "news": ("ข่าว", "การเมือง", "เลือกตั้ง", "นายก"),
}
_EN_OFF_TOPIC = {
    "health": re.compile(r"\b(?:headache|sick|fever|medicine|doctor|illness|pain|cough|flu)\b", re.I),
    "tech": re.compile(r"\b(?:computer|laptop|phone|wi-?fi|internet|code|coding|program(?:ming)?|printer|battery|iphone|android|windows)\b", re.I),
    "study": re.compile(r"\b(?:homework|exam|essay|thesis|assignment)\b", re.I),
    "money": re.compile(r"\b(?:stocks?|invest\w*|crypto|bitcoin|loan|tax(?:es)?|interest rate)\b", re.I),
    "love": re.compile(r"\b(?:girlfriend|boyfriend|crush|break ?up|dating)\b", re.I),
    "news": re.compile(r"\b(?:news|politics|election|prime minister)\b", re.I),
}


def off_topic_kind(text: str) -> str | None:
    for kind, words in OFF_TOPIC_KINDS.items():
        if any(w in text for w in words):
            return kind
    for kind, pattern in _EN_OFF_TOPIC.items():
        if pattern.search(text):
            return kind
    return None


def find_subject(text: str) -> tuple[str, str] | None:
    """สิ่งที่อยากหาแบบเจาะจง คืน (คำไทย, คำอังกฤษ) หรือ None"""
    for word, th, en in SUBJECTS:
        if word in text:
            return th, en
    for pattern, th, en in _EN_SUBJECTS:
        if pattern.search(text):
            return th, en
    return None


# ชื่อเรียกอื่นของจังหวัด
ALIASES = {
    "กรุงเทพ": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร", "โคราช": "นครราชสีมา", "อยุธยา": "พระนครศรีอยุธยา",
    "ปราจีน": "ปราจีนบุรี", "สุราษฎร์": "สุราษฎร์ธานี", "อุบล": "อุบลราชธานี", "อุดร": "อุดรธานี",
    "นครศรี": "นครศรีธรรมราช", "ประจวบ": "ประจวบคีรีขันธ์", "ภูเก็ต": "ภูเก็ต", "เมืองกาญจน์": "กาญจนบุรี",
}
# ชื่อจังหวัดที่เป็นคำไทยทั่วไปด้วย ต้องมีคำนำหน้าชัดเจนถึงจะนับ ("ไปเลย" ไม่ใช่จังหวัดเลย)
AMBIGUOUS = {"เลย", "ตาก", "แพร่", "น่าน"}
_PREFIX = r"(?:จังหวัด|จ\.|แถว|ใน|ที่|ของ)\s*"

_RADIUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:กม|km|kilomet(?:er|re)s?|กิโล)", re.I)
_LIMIT_RE = re.compile(r"(\d+)\s*(?:แห่ง|ที่|อัน|ร้าน|รายการ|(?:places?|spots?|results?|items?|options?|attractions?|"
                       r"cafes?|cafés?|hotels?|stays|resorts?)\b)(?!\s*(?:กม|km))", re.I)
_LODGING_NAME_RE = re.compile(r"(" + "|".join(LODGING_WORDS[:-1]) + r")\s*([^\s]{2,60}(?:\s[A-Za-z0-9&'.-]{1,30}){0,3})")
_NAME_STOP = re.compile(r"(มี|แนะนำ|หา|ไหม|บ้าง|หน่อย|ครับ|ค่ะ|คะ|นะ|อยาก|ช่วย|ที่เที่ยว|คาเฟ่|ร้านกาแฟ|เที่ยว|ใกล้|รอบ|แถว|ใน |ภายใน|อะไร)")


# ---------- ภาษาอังกฤษ ----------
# คำอังกฤษจับแบบคำเต็ม (กัน "village" ถูกนับเป็น "villa") ส่วนคำไทยยังจับแบบมีอยู่ในข้อความ
_EN_CAFE = re.compile(r"\b(?:cafes?|cafés?|coffee(?: shops?)?)\b|café", re.I)
_EN_ATTRACTION = re.compile(
    r"\b(?:attractions?|sightseeing|sights?|things to do|places? to (?:visit|go|see)|tourist|landmarks?|temples?|"
    r"waterfalls?|beach(?:es)?|museums?|viewpoints?|markets?|national parks?|mountains?|islands?|visit)\b", re.I)
_EN_LODGING = re.compile(
    r"\b(?:hotels?|resorts?|hostels?|homestays?|guest ?houses?|villas?|bungalows?|lodgings?|accommodations?|"
    r"stays|places? to stay|where to stay)\b", re.I)
_EN_MONEY = re.compile(
    r"\b(?:prices?|pricing|costs?|how much|fees?|tickets?|admission|budget|cheap|expensive|free|baht|thb)\b", re.I)
_EN_REVIEW = re.compile(r"\b(?:reviews?|ratings?|rated|scores?|rankings?|ranked|best|most popular|popular)\b", re.I)
_EN_BOOKING = re.compile(r"\b(?:book|booking|bookings|reserve|reservations?|pay|payments?)\b", re.I)
_EN_GENERIC = re.compile(
    r"\b(?:near(?:by)?|around|recommend\w*|suggest\w*|show|find|search|more|another|other|what(?:'s| is)? (?:there|here|nearby)|"
    r"where|any|radius|closest|nearest|distance)\b", re.I)
_EN_FOOD = re.compile(r"\b(?:restaurants?|food|eat|eating|hungry|dinner|lunch|breakfast|meal|menu)\b", re.I)
_EN_GREETING = re.compile(
    r"\b(?:hi|hello|hey)\b|what can you do|what do you do|how (?:do|can) i use|how to use|^help\b", re.I)

# ชื่อจังหวัดภาษาอังกฤษ: เว้นวรรค/ขีดจะมีหรือไม่มีก็ได้ ("Chonburi" "Chon Buri" "chon-buri")
def _en_pattern(name: str) -> re.Pattern:
    words = re.split(r"[\s-]+", name.lower())
    return re.compile(r"(?<![a-z])" + r"[\s-]*".join(map(re.escape, words)) + r"(?![a-z])")


_EN_ALIASES = {
    "krung thep": "กรุงเทพมหานคร", "bkk": "กรุงเทพมหานคร", "korat": "นครราชสีมา", "khorat": "นครราชสีมา",
    "ayutthaya": "พระนครศรีอยุธยา", "ayudhya": "พระนครศรีอยุธยา", "pattaya": "ชลบุรี",
    "nakhon si": "นครศรีธรรมราช", "prachuap": "ประจวบคีรีขันธ์", "ubon": "อุบลราชธานี", "udon": "อุดรธานี",
}
# "Nan" เป็นชื่อขนมปังด้วย ต้องมีคำนำหน้า/ตามด้วย province ถึงจะนับ
_EN_AMBIGUOUS = {"Nan"}
_EN_PREFIX = r"(?:in|at|near|around|to|of|from|province)\s+"
_EN_PROVINCE = sorted(
    [(_en_pattern(en), th, en in _EN_AMBIGUOUS) for th, en in PROVINCES_EN.items()]
    + [(_en_pattern(a), th, False) for a, th in _EN_ALIASES.items()],
    key=lambda t: -len(t[0].pattern))
_NAN_OK = re.compile(r"(?<![a-z])(?:" + _EN_PREFIX + r"nan\b|nan\s+province)", re.I)

_EN_LODGING_WORD = r"(?:hotel|resort|hostel|homestay|guest ?house|villa|bungalow)s?"
_EN_NAME_RE = re.compile(r"\b(" + _EN_LODGING_WORD + r")\b", re.I)
_EN_STOP = frozenset((
    "near nearby around close in at to by from of the my a an and or with for show find any some are is there what "
    "which where how best good great nice cheap luxury budget cozy quiet beautiful new old top me i we you want need "
    "looking recommend about place places within km kms cafe cafes café cafés attractions attraction restaurants "
    "other another here this that these those please can could would should next").split())


@dataclass
class Intent:
    kinds: tuple[str, ...] = ("attraction", "cafe")
    radius_km: float = MAX_RADIUS
    limit: int = DEFAULT_LIMIT
    province: str | None = None
    lodging_query: str | None = None
    want_lodgings: bool = False          # อยากได้รายชื่อที่พักรอบจุด
    greeting: bool = False
    smalltalk: str | None = None         # คุยเล่นสั้นๆ (ชื่อ/ขอบคุณ/ลาก่อน …) ตอบสำเร็จรูปตามชนิด
    anchor: str | None = None            # ชื่อสถานที่ที่ถูกเอ่ย ใช้ตำแหน่งสถานที่นั้นเป็นจุดค้น (ไม่มีหมุด/จังหวัด)
    off_topic: bool = False              # ไม่มีคำที่ระบบรู้จักเลย (เช่น "กินข้าวยัง") อย่าเดาว่าให้ค้นรายชื่อ
    asks_food: bool = False              # ถามเรื่องอาหาร ระบบไม่มีข้อมูลร้านอาหาร
    off_topic_kind: str | None = None    # หัวข้อนอกเรื่อง (health/tech/study/money/love/news) ตอบให้ตรงหัวข้อ
    subject: tuple[str, str] | None = None  # สิ่งที่อยากหาแบบเจาะจง (เช่น วัด) ใช้พูดทวนตอนถามว่าแถวไหน
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
    low = text.lower()
    for rx, p, ambiguous in _EN_PROVINCE:
        if rx.search(low) and (not ambiguous or _NAN_OK.search(low)):
            return p
    return None


# คำนำหน้าชนิดสถานที่ที่ซ้ำกันเยอะ ตัดออกก่อนเทียบชื่อ ไม่งั้น "วัด" "อุทยานแห่งชาติ" จะทำให้จับชื่อผิดที่
_GENERIC_NAME = ("อุทยานแห่งชาติ", "อุทยานประวัติศาสตร์", "วนอุทยาน", "พิพิธภัณฑ์", "ปราสาทหิน", "ปราสาท", "น้ำตก", "เขื่อน",
                 "วัด", "ถ้ำ", "เกาะ", "หาด", "ตลาด", "สวน")
_PAREN = re.compile(r"\s*[(（].*?[)）]")
PLACE_MIN_CHARS = 6
PLACE_MIN_SHARE = 0.45


def _core(name: str) -> str:
    n = re.sub(r"\s+", "", _PAREN.sub("", name or "")).lower()
    for g in sorted(_GENERIC_NAME, key=len, reverse=True):
        if n.startswith(g) and len(n) > len(g) + 2:
            n = n[len(g):]
            break
    return n


def _longest_common(a: str, b: str) -> int:
    best = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def find_place(text: str, places) -> object | None:
    """หาสถานที่ที่ตรวจที่มาแล้วซึ่งถูกเอ่ยชื่อในข้อความ (ชื่อเต็มหรือชื่อสั้น) ใช้เป็นจุดค้นเมื่อไม่มีหมุด/จังหวัด
    ต้องมีส่วนที่ตรงกันยาวพอและครอบคลุมชื่ออย่างน้อยครึ่งหนึ่ง ถ้ามีสองที่ที่ตรงเท่ากันถือว่าไม่ชัด คืน None"""
    t = re.sub(r"\s+", "", (text or "")).lower()
    best, best_len, tie = None, 0, False
    for p in places:
        for name in (p.name_th, p.name_en):
            core = _core(name or "")
            if len(core) < PLACE_MIN_CHARS:
                continue
            n = _longest_common(t, core)
            if n < PLACE_MIN_CHARS or n / len(core) < PLACE_MIN_SHARE:
                continue
            if n > best_len:
                best, best_len, tie = p, n, False
            elif n == best_len and best is not None and best.id != p.id:
                tie = True
    return None if tie else best


def _has(text: str, words) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def _en_lodging_name(text: str) -> tuple[str, tuple[int, int]] | None:
    """ชื่อที่พักภาษาอังกฤษ: "Sunshine Hotel" (ชื่อนำหน้า) หรือ "hotel Sunshine" (ชื่อตามหลัง)
    เก็บคำติดกับคำว่า hotel/resort/... จนเจอคำหยุด (near, in, the, ...) ถ้าไม่มีชื่อเลยคืน None"""
    m = _EN_NAME_RE.search(text)
    if not m:
        return None
    clean_word = lambda w: w.strip(" .,!?\"'()")  # noqa: E731
    before = [(mm.group(0), mm.start()) for mm in re.finditer(r"[^\s,;:]+", text[:m.start()])]
    start, pre = m.start(), []
    for w, pos in reversed(before):
        if clean_word(w).lower() in _EN_STOP or not clean_word(w) or len(pre) >= 4:
            break
        pre.insert(0, clean_word(w))
        start = pos
    if pre:
        name, span = " ".join(pre + [m.group(1)]), (start, m.end())
    else:
        after = []
        end = m.end()
        for mm in re.finditer(r"[^\s,;:]+", text[m.end():]):
            w = clean_word(mm.group(0))
            if not w or w.lower() in _EN_STOP or len(after) >= 4:
                break
            after.append(w)
            end = m.end() + mm.end()
        if not after:
            return None
        name, span = " ".join([m.group(1)] + after), (m.start(), end)
    return name[:80], span


def _lodging_query(text: str) -> tuple[str, tuple[int, int]] | None:
    """คืน (คำค้นชื่อที่พัก, ช่วงตำแหน่งในข้อความ) ช่วงนี้ถูกตัดออกก่อนจับประเภท
    ไม่งั้นชื่ออย่าง "โรงแรมสวนดอก" จะถูกนับว่าถามหา "สวน" """
    m = _LODGING_NAME_RE.search(text)
    if not m:
        return _en_lodging_name(text)
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
    lodging = _has(text, LODGING_WORDS) or bool(_EN_LODGING.search(text))
    scan = text
    if lodging and not it.province:
        found = _lodging_query(text)
        if found:
            it.lodging_query = found[0]
            scan = text[:found[1][0]] + " " + text[found[1][1]:]
    cafe = _has(scan, CAFE_WORDS) or bool(_EN_CAFE.search(scan))
    attr = _has(scan, ATTRACTION_WORDS) or bool(_EN_ATTRACTION.search(scan))
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
    it.asks_money = _has(text, MONEY_WORDS) or bool(_EN_MONEY.search(text))
    it.asks_review = _has(text, REVIEW_WORDS) or bool(_EN_REVIEW.search(text))
    it.asks_booking = _has(text, BOOKING_WORDS) or bool(_EN_BOOKING.search(text))
    hello = _has(text, GREETING_WORDS) or bool(_EN_GREETING.search(text))
    it.greeting = hello and not (it.province or cafe or attr or lodging)
    has_number = bool(_RADIUS_RE.search(text) or _LIMIT_RE.search(text))
    it.asks_food = _has(text, FOOD_WORDS) or bool(_EN_FOOD.search(text))
    known = (it.province or cafe or attr or lodging or has_number or hello or it.asks_money or it.asks_review
             or it.asks_booking or _has(text, GENERIC_WORDS) or bool(_EN_GENERIC.search(text)))
    it.off_topic = (not known and not it.greeting) or (it.asks_food and not (cafe or attr or lodging))
    it.subject = find_subject(scan)
    if not it.asks_food and not (it.province or cafe or attr or lodging or has_number):
        # หัวข้อนอกเรื่องชัด ๆ ("หุ้นตัวไหนดี" "คอมช้าแก้ยังไง") นับเป็นนอกเรื่องแม้มีคำกว้าง ๆ อย่าง "ไหน" "แนะนำ"
        it.off_topic_kind = off_topic_kind(text)
        if it.off_topic_kind:
            it.off_topic = True
    if not (it.province or cafe or attr or lodging or has_number):
        it.smalltalk = smalltalk_kind(text)
        if it.smalltalk:
            it.off_topic = False
            it.greeting = False
    return it
