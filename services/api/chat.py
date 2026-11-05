"""POST /api/chat: แชตแบบกฎ ตอบเป็น Server-Sent Events (docs/CONTRACT.md ข้อ 3.2)

หลักการ:
- เรียกเครื่องมือค้นตัวเดียวกับหน้าค้นหา (places_nearby / lodgings_near / lodgings_search) ไม่ใช้ LLM
- ชื่อสถานที่ ระยะ ในข้อความตอบ มาจากผลค้นที่ผ่านตัวตรวจอิสระแล้วเท่านั้น (ไม่ผ่านตัวตรวจ = ไม่แสดงรายชื่อ)
- ข้อความผู้ใช้และชื่อจาก OSM เป็นข้อมูล ไม่ใช่คำสั่ง (หน้าเว็บต้องแสดงเป็นข้อความธรรมดา ห้ามแปลงเป็น HTML)
- ผู้ที่ไม่ได้ล็อกอินคุยได้ แต่ไม่ถูกบันทึกอะไรเลย
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import deque
from typing import Iterator, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.places import PlacesService, SearchError
from services.places.geo import in_thailand
from services.places.provinces import PROVINCES, REGION_ORDER, REGIONS, province_en

from .accounts import COOKIE, MAX_ID, session_user
from . import metrics
from .answer_guard import GUARD_NOTICE
from .chat_rules import MAX_MESSAGE, SUBJECT_SUBTYPES, Intent, clean, drop_province, find_place, generic_stay_words, parse
from .rag import MAX_HISTORY, Rag, RagResult, is_no_info
from .store import Store
from .validator import validate_lodgings_near, validate_nearby

log = logging.getLogger("nongtrip.chat")

KIND_TH = {"attraction": "สถานที่เที่ยว", "cafe": "คาเฟ่"}
KIND_EN = {"attraction": "attractions", "cafe": "cafés"}
INVALID_NOTICE = "ผลค้นนี้ไม่ผ่านการตรวจอิสระ โปรดอย่าเชื่อถือจนกว่าจะตรวจสอบ"
INVALID_NOTICE_EN = "These results failed the independent check. Please do not rely on them until verified."

HELP = ("สวัสดีค่ะ น้องทริปช่วยหาสถานที่เที่ยวและคาเฟ่รอบที่พักของคุณได้ ในรัศมีไม่เกิน 30 กม. เรียงจากใกล้ไปไกล\n"
        "ลองพิมพ์ เช่น \"คาเฟ่ใกล้ๆ\" (ถ้าปักหมุดไว้แล้ว) \"ที่เที่ยวในเชียงใหม่ 5 แห่ง\" หรือ \"ที่พักแถวภูเก็ต\"\n"
        "ระบบไม่มีราคา ค่าเข้า รีวิว หรือคะแนน และไม่จองหรือชำระเงินให้")
HELP_HINT = ("ลองพิมพ์ เช่น \"คาเฟ่ใกล้ๆ\" (ถ้าปักหมุดไว้แล้ว) \"ที่เที่ยวในเชียงใหม่ 5 แห่ง\" หรือ \"ที่พักแถวภูเก็ต\"")
# คุยเล่นสั้นๆ: ตอบสำเร็จรูปตามชนิด (ไม่ค้น ไม่ใช้ LLM จึงไม่เดาและไม่ใช้เครดิต) ปิดท้ายชวนกลับมาเรื่องที่เที่ยวเสมอ
SMALLTALK_TH = {
    "name": ["เราชื่อน้องทริปค่ะ เป็นผู้ช่วยหาที่เที่ยว คาเฟ่ และที่พักรอบ ๆ ที่คุณอยู่ ในรัศมีไม่เกิน 30 กม. เรียงจากใกล้ไปไกล"],
    "bot": ["น้องทริปเป็นผู้ช่วยในแชตค่ะ ไม่ใช่คนจริง ๆ แต่ข้อมูลสถานที่ทุกแห่งที่แสดงมาจากแหล่งที่ตรวจสอบได้ และมีลิงก์ให้กดดูต้นทาง"],
    "maker": ["น้องทริปเป็นโครงงานของนักศึกษา มหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี (RMUTT) ค่ะ"],
    "wellbeing": ["สบายดีค่ะ พร้อมพาไปเที่ยวเสมอ"],
    "thanks": ["ยินดีค่ะ"],
    "ok": ["ได้เลยค่ะ"],
    "bye": ["ไว้เจอกันใหม่นะคะ เที่ยวให้สนุกค่ะ"],
    "praise": ["ขอบคุณค่ะ ดีใจที่ชอบ"],
    "weather": ["น้องทริปยังไม่มีข้อมูลสภาพอากาศค่ะ ก่อนออกเดินทางลองดูพยากรณ์จากกรมอุตุนิยมวิทยาอีกที"],
    "bored": ["เบื่อใช่ไหมคะ ไปเที่ยวเปลี่ยนบรรยากาศกันดีกว่า"],
    "eaten": ["น้องทริปไม่ได้กินข้าวค่ะ แต่ถ้าหิว ไปชิมอาหารพื้นถิ่นระหว่างเที่ยวกันดีกว่า"],
}
SMALLTALK_ASK = "วันนี้อยากไปเที่ยวแถวไหนดีคะ บอกชื่อจังหวัดหรือที่พักได้เลย"
SMALLTALK_EN = {
    "name": ["I'm NongTrip, an assistant that finds attractions, cafés and stays around where you are, within 30 km, nearest first."],
    "bot": ["I'm a chat assistant, not a real person. Every place I show comes from a checked source, with a link to the original."],
    "maker": ["NongTrip is a student project at Rajamangala University of Technology Thanyaburi (RMUTT)."],
    "wellbeing": ["I'm doing well and always ready to plan a trip."],
    "thanks": ["You're welcome!"],
    "ok": ["Sure!"],
    "bye": ["See you next time. Have a great trip!"],
    "praise": ["Thank you, I'm glad you like it."],
    "weather": ["NongTrip has no weather data yet. Please check the Thai Meteorological Department forecast before you travel."],
    "bored": ["Bored? Let's find somewhere new to go."],
    "eaten": ["I don't eat, but if you're hungry, local food on the road is part of the trip!"],
}
SMALLTALK_ASK_EN = "Where would you like to go? Tell me a province or your stay."



HELP_EN = ("Hi! NongTrip finds attractions and cafés around your stay, within 30 km, nearest first.\n"
           "Try: \"cafés nearby\" (once you have pinned your stay), \"attractions in Chiang Mai, 5 places\" or \"stays around Phuket\".\n"
           "The system has no prices, entry fees, reviews or scores, and does not book or take payment.")
HELP_HINT_EN = "Try: \"cafés nearby\" (once you have pinned your stay), \"attractions in Chiang Mai, 5 places\" or \"stays around Phuket\"."

# ข้อความสำเร็จรูปที่ระบบสร้างเอง (ภาษาไทย -> อังกฤษ) ใช้เมื่อผู้ใช้เลือกหน้าเว็บภาษาอังกฤษ
# หมายเหตุที่มาจากบริการค้นที่ไม่อยู่ในรายการนี้ ยังเป็นภาษาไทย
NOTE_EN = {
    "ค้นรอบจุดกลางจังหวัด ไม่ใช่รอบที่พักของคุณ ปักหมุดที่พักเพื่อให้ตรงขึ้น":
        "Searched around the province centre, not your stay. Pin your stay for a closer result.",
    "ระยะเป็นเส้นตรง ไม่ใช่ระยะขับรถ": "Distances are straight-line, not driving distances.",
    "ระบบไม่มีข้อมูลราคา ค่าเข้า หรืองบประมาณ จึงไม่แสดงและไม่ประมาณให้":
        "The system has no price, entry fee or budget data, so none is shown or estimated.",
    "ระบบไม่เก็บรีวิวหรือคะแนน กดลิงก์ Google Maps ที่การ์ดสถานที่เพื่อดูรีวิวจริง":
        "The system does not hold reviews or scores. Use the Google Maps link on a place card to see real reviews.",
    "ระบบไม่จองหรือชำระเงินแทนผู้ใช้": "The system does not book or pay on your behalf.",
    "ระบบยังไม่มีข้อมูลเวลาเปิดปิด กดลิงก์ Google Maps ที่การ์ดสถานที่เพื่อดูเวลาล่าสุด":
        "The system has no opening hours yet. Open the Google Maps link on a place card for the latest hours.",
    "ระบบไม่วางเส้นทางให้ กดปุ่ม \"นำทางด้วย Google Maps\" ที่การ์ดสถานที่เพื่อดูวิธีเดินทาง (ระยะที่แสดงเป็นเส้นตรง)":
        "The system does not plan routes. Use \"Directions with Google Maps\" on a place card (distances shown are straight-line).",
    GUARD_NOTICE: "The automatic answer check failed, so a basic result is shown instead.",
    "พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง": "Several stays match. Please choose the one you booked.",
    "ไม่พบที่พักที่ตรงตัวกรอง ลองเอาตัวกรองออกบางข้อ หรือปักหมุดบนแผนที่":
        "No stay matches the filters. Try removing some filters or pin the map.",
    "ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น หรือปักหมุดบนแผนที่": "No stay with this name. Try another name or pin the map.",
    "ข้อมูลที่บันทึกไว้ยังกรองตามย่านไม่ได้ ผลที่เห็นไม่ได้ถูกกรองด้วยย่าน":
        "Saved data cannot be filtered by area yet, so the results are not filtered by area.",
    "ใช้ค่าเฉลี่ยพิกัดสถานที่ที่ตรวจแล้ว เพราะหาจุดกลางจังหวัดจาก OpenStreetMap ไม่ได้":
        "Used the average of verified places because the province centre could not be found on OpenStreetMap.",
    "ยังหาจุดกลางของจังหวัดนี้ไม่ได้ ให้ค้นด้วยชื่อที่พักหรือปักหมุดแทน":
        "Cannot find this province's centre yet. Search by a stay's name or pin the map instead.",
}


class Context(BaseModel):
    lat: float
    lon: float


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    context: Context | None = None
    chat_id: int | None = Field(default=None, ge=1, le=MAX_ID)
    # จังหวัดที่ถามไว้ล่าสุด (หน้าเว็บจำจาก event done) ใช้เมื่อข้อความใหม่ไม่ระบุที่ เช่น "แล้วคาเฟ่ล่ะ"
    last_province: str | None = Field(default=None, max_length=60)
    lang: Literal["th", "en"] = "th"
    # แก้คำถาม/ถามใหม่ (ต้องล็อกอินและส่ง chat_id): รหัสข้อความผู้ใช้ในแชตนี้ ลบตั้งแต่ข้อความนั้นลงไปแล้วถามใหม่
    edit_from: int | None = Field(default=None, ge=1, le=MAX_ID)
    # บทสนทนาก่อนหน้าในแชตเดียวกัน (หน้าเว็บส่งมา ใช้ไม่เกิน 6 ข้อความท้าย) ให้ LLM เข้าใจคำถามต่อเนื่อง ไม่ได้บันทึกเพิ่ม
    history: list[Turn] | None = Field(default=None, max_length=20)


class ChatThrottle:
    """จำกัดจำนวนคำขอแชตต่อ IP ต่อนาที (แชตเรียก OSM จริง กันถูกยิงรัว)"""

    def __init__(self, limit: int | None = None, window: float = 60.0, clock=time.monotonic, max_keys: int = 10000):
        if limit is None:
            try:
                limit = int(os.environ.get("CHAT_RATE_PER_MIN") or 20)
            except ValueError:
                limit = 20
        self.limit, self.window, self.clock, self.max_keys = max(1, limit), window, clock, max_keys
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            if key not in self._hits and len(self._hits) >= self.max_keys:
                self._hits = {k: q for k, q in self._hits.items() if q and now - q[-1] < self.window}
                if len(self._hits) >= self.max_keys:
                    return False
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _one_line(s: str) -> str:
    """ชื่อจาก OSM ในข้อความตอบต้องอยู่บรรทัดเดียว (กันแทรกบรรทัดปลอม)"""
    return " ".join(str(s).split())[:120]


def _t(lang: str, th: str, en: str) -> str:
    return en if lang == "en" else th


def _tail(it: Intent, lang: str = "th") -> list[str]:
    """หมายเหตุเรื่องที่ระบบไม่มี/ไม่ทำ บอกตรงๆ แทนการเดา"""
    out = []
    if it.asks_money:
        out.append("ระบบไม่มีข้อมูลราคา ค่าเข้า หรืองบประมาณ จึงไม่แสดงและไม่ประมาณให้")
    if it.asks_review:
        out.append("ระบบไม่เก็บรีวิวหรือคะแนน กดลิงก์ Google Maps ที่การ์ดสถานที่เพื่อดูรีวิวจริง")
    if it.asks_booking:
        out.append("ระบบไม่จองหรือชำระเงินแทนผู้ใช้")
    if it.asks_hours:
        out.append("ระบบยังไม่มีข้อมูลเวลาเปิดปิด กดลิงก์ Google Maps ที่การ์ดสถานที่เพื่อดูเวลาล่าสุด")
    if it.asks_directions:
        out.append("ระบบไม่วางเส้นทางให้ กดปุ่ม \"นำทางด้วย Google Maps\" ที่การ์ดสถานที่เพื่อดูวิธีเดินทาง (ระยะที่แสดงเป็นเส้นตรง)")
    return [_note_en(x) for x in out] if lang == "en" else out


def _lines(parts: list[str]) -> str:
    return "\n".join(p for p in parts if p)


# หมายเหตุจากบริการค้น (รูปแบบมีตัวเลข) -> อังกฤษ
_NOTE_EN_PATTERNS = (
    (r"ค้นได้ไกลสุด ([\d.]+) กม\. จึงใช้ ([\d.]+) กม\. แทน", "The maximum search radius is {0} km, so {1} km was used."),
    (r"แสดงได้ครั้งละไม่เกิน (\d+) แห่ง", "At most {0} places are shown at a time."),
    (r"แสดงผลในรัศมี ([\d.]+) กม\. เท่านั้น", "Results are shown within {0} km only."),
    (r"ไม่พบที่พักในรัศมี ([\d.]+) กม\. จึงขยายเป็น ([\d.]+) กม\.", "No stays within {0} km, so the search was widened to {1} km."),
    (r"ไม่พบที่พักในรัศมี ([\d.]+) กม\. จากหมุดนี้", "No stays within {0} km of this pin."),
    (r"พบที่พัก (\d+) แห่ง แสดง (\d+) แห่งที่ใกล้หมุดที่สุด", "Found {0} stays; showing the {1} nearest to the pin."),
    (r"พื้นที่หนาแน่นมาก ข้อมูลจาก OpenStreetMap จึงครอบคลุมแค่ ([\d.]+) กม\.",
     "This area is very dense, so OpenStreetMap data covers only {0} km."),
    (r"(.+) แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว", "{r} Only places with a verified source are shown."),
    (r"(.+) ให้ปักหมุดบนแผนที่แทน", "{r} Please pin your stay on the map instead."),
)
_REASON_EN = {
    "ปิดการค้นหาจาก OpenStreetMap อยู่": "OpenStreetMap search is switched off.",
    "ค้นชื่อที่พักออนไลน์ไม่ได้ในตอนนี้": "Cannot search stay names online right now.",
    "เชื่อมต่อ OpenStreetMap ไม่ได้ในตอนนี้": "Cannot reach OpenStreetMap right now.",
    "ดึงข้อมูลจาก OpenStreetMap ไม่สำเร็จ": "Could not fetch data from OpenStreetMap.",
}


def _note_en(n: str) -> str:
    if n in NOTE_EN:
        return NOTE_EN[n]
    for rx, tpl in _NOTE_EN_PATTERNS:
        m = re.fullmatch(rx, n)
        if m:
            if "{r}" in tpl:
                return tpl.format(r=_REASON_EN.get(m[1], m[1]))
            return tpl.format(*m.groups())
    return n


def _notes(notices: list[str], lang: str = "th") -> list[str]:
    if lang == "en":
        return [f"Note: {_note_en(n)}" for n in notices]
    return [f"หมายเหตุ: {n}" for n in notices]


OFF_TOPIC_TH = {
    "health": "เรื่องสุขภาพน้องทริปให้คำแนะนำไม่ได้ค่ะ ถ้าไม่สบาย ปรึกษาแพทย์หรือเภสัชกรจะดีที่สุด ถ้าอาการหนักโทร 1669 ได้ทันที",
    "tech": "เรื่องคอมพิวเตอร์และมือถือ น้องทริปไม่ถนัดเลยค่ะ ลองถามช่างหรือศูนย์บริการของยี่ห้อนั้นดูนะ",
    "study": "เรื่องเรียนกับการบ้าน น้องทริปช่วยไม่ได้ค่ะ แต่ถ้าสอบเสร็จแล้วอยากไปเที่ยวพักสมอง บอกได้เลย",
    "money": "เรื่องการเงินและการลงทุน น้องทริปให้คำแนะนำไม่ได้ค่ะ ลองปรึกษาผู้เชี่ยวชาญด้านการเงินดูนะ",
    "love": "เรื่องหัวใจน้องทริปไม่ถนัดเลยค่ะ แต่ถ้าอยากไปเที่ยวเปลี่ยนบรรยากาศ น้องทริปหาที่สวย ๆ ให้ได้นะ",
    "news": "น้องทริปไม่มีข้อมูลข่าวค่ะ ลองติดตามจากสำนักข่าวที่เชื่อถือได้นะ",
    "food": "ตอนนี้น้องทริปยังไม่มีข้อมูลร้านอาหารค่ะ มีเฉพาะที่เที่ยว คาเฟ่ และที่พัก ถ้าอยากนั่งคาเฟ่ใกล้ ๆ หาให้ได้นะ",
}
OFF_TOPIC_EN_KIND = {
    "health": "I can't give health advice. If you feel unwell, please see a doctor or pharmacist. In an emergency in Thailand, call 1669.",
    "tech": "Computers and phones aren't my thing. A technician or the brand's service centre can help you better.",
    "study": "I can't help with study or homework, but if you need a break after exams, I can find you somewhere to go.",
    "money": "I can't give financial or investment advice. Please talk to a financial professional.",
    "love": "Matters of the heart aren't my thing, but if you need a change of scene, I can find somewhere lovely.",
    "news": "I don't have news. Please check a trusted news source.",
    "food": "I don't have restaurant data yet, only attractions, cafés and stays. I can find a café nearby, though.",
}
GENERAL_DISCLAIMER = "เรื่องนี้ไม่ใช่งานหลักของน้องทริปนะคะ ตอบจากความรู้ทั่วไป ข้อมูลอาจไม่ถูกต้อง 100% ควรตรวจสอบกับแหล่งที่เชื่อถือได้อีกครั้ง"
GENERAL_DISCLAIMER_EN = "This isn't my main job, so this is general knowledge and may not be 100% accurate. Please double-check with a reliable source."
# คำถามเรื่องเที่ยวที่ระบบไม่มีข้อมูลตรวจแล้ว (ฤดู การเดินทาง แผนเที่ยว อาหารท้องถิ่น) ตอบจากความรู้ทั่วไป ขึ้นต้นด้วยคำเตือนนี้เสมอ
TRAVEL_DISCLAIMER = "เรื่องนี้ระบบยังไม่มีข้อมูลที่ตรวจแล้ว น้องทริปตอบจากความรู้ทั่วไป อาจไม่ถูกต้อง 100% ควรตรวจสอบอีกครั้งนะคะ"
TRAVEL_DISCLAIMER_EN = "The system has no verified data on this, so this is general knowledge and may not be 100% accurate. Please double-check."
OFF_TOPIC_SHORT = "ขอโทษนะคะ อันนี้น้องทริปตอบไม่ได้จริง ๆ"
OFF_TOPIC_SHORT_EN = "Sorry, that's outside what I know."
CAN_DO = "น้องทริปช่วยได้เรื่องที่เที่ยว คาเฟ่ และที่พักรอบตัวคุณ ลองพิมพ์ เช่น \"ที่เที่ยวในเชียงใหม่\" หรือ \"คาเฟ่ใกล้ๆ\""
CAN_DO_EN = "I can help with attractions, cafés and stays around you. Try \"attractions in Chiang Mai\" or \"cafés nearby\"."


def _off_topic_parts(it: Intent, lang: str = "th") -> list[str]:
    """ข้อความตอบเมื่อข้อความไม่เกี่ยวกับที่เที่ยว/คาเฟ่/ที่พัก ตอบให้ตรงหัวข้อที่ถาม (สุขภาพ คอม อาหาร …) แล้วชวนกลับมาเรื่องเที่ยว"""
    kind = "food" if it.asks_food else it.off_topic_kind
    table = OFF_TOPIC_EN_KIND if lang == "en" else OFF_TOPIC_TH
    first = table.get(kind) if kind else None
    sorry = _t(lang, "ขอโทษนะคะ ", "Sorry, ")
    if first and lang == "en":
        first = sorry + first[0].lower() + first[1:]
    elif first:
        first = sorry + first
    return [first or _t(lang, OFF_TOPIC_SHORT, OFF_TOPIC_SHORT_EN), _t(lang, CAN_DO, CAN_DO_EN)]


# ยังไม่รู้ว่าแถวไหน (โหมด LLM): เสนอสถานที่ที่ตรวจแล้วจากหลายภาค ให้ LLM แนะนำพร้อมชื่อจังหวัด แล้วชวนบอกที่พัก
SUGGEST_LIMIT = 8
THAI = re.compile(r"[\u0e00-\u0e7f]")
# คำในชื่อสถานที่ที่ตรวจแล้ว และประเภทของไฟล์สถานที่ที่ตรวจแล้ว (temple nature museum activity market cafe craft) ต่อเรื่องที่อยากหา
_SUGGEST_WORDS = {
    "น้ำตก": ("น้ำตก",), "ชายหาด": ("หาด", "ทะเล", "เกาะ"), "ทะเล": ("หาด", "ทะเล", "เกาะ"), "เกาะ": ("เกาะ",),
    "ดอยและภูเขา": ("ดอย", "ภู", "เขา"), "อุทยาน": ("อุทยาน",), "จุดชมวิว": ("ชมวิว", "ดอย", "ภู"),
}
_SUGGEST_SUBTYPES = {
    "วัด": {"temple"}, "พิพิธภัณฑ์": {"museum"}, "ตลาด": {"market"}, "ธรรมชาติ": {"nature"},
    "วัดและประวัติศาสตร์": {"temple", "museum"},
}
SUGGEST_DISCLAIMER = "ชื่อสถานที่ด้านล่างมาจากรายการที่ตรวจที่มาแล้ว ส่วนคำอธิบายเป็นความรู้ทั่วไป อาจไม่ถูกต้องทั้งหมด ควรตรวจสอบอีกครั้งนะคะ"
SUGGEST_DISCLAIMER_EN = "The places below come from our source-checked list. The descriptions are general knowledge and may not be fully accurate, so please double-check."
NARRATE_DISCLAIMER = "ชื่อสถานที่และระยะมาจากผลค้นของระบบ ส่วนคำอธิบายเป็นความรู้ทั่วไป อาจไม่ถูกต้องทั้งหมด ควรตรวจสอบอีกครั้งนะคะ"
NARRATE_DISCLAIMER_EN = "Place names and distances come from our search results. The descriptions are general knowledge and may not be fully accurate, so please double-check."
NARRATE_TASK = ("<places> คือผลค้นจริงของระบบรอบจุดที่ผู้ใช้ถาม เรียงใกล้ไปไกล ตอบคำถามของผู้ใช้ให้ตรงประเด็นก่อน "
                "ถ้าเกี่ยวข้อง แนะนำ 3-5 แห่งจาก <places> ที่ตรงกับสิ่งที่ผู้ใช้อยากได้ บอกระยะตามรายการว่าเป็นระยะเส้นตรง "
                "และเล่าสั้น ๆ ว่าน่าไปเพราะอะไรจากความรู้ทั่วไป ถ้าคำถามไม่ใช่การหาสถานที่ (เช่น เวลาเดินทาง ฤดูกาล) ตอบคำถามนั้นก่อน "
                "แล้วค่อยเอ่ยถึงสถานที่ในรายการถ้าช่วยได้ ห้ามใช้ตัวหนาหรือ markdown")
NARRATE_TASK_EN = ("<places> are the system's real search results around where the user asked, nearest first. Answer the user's question first. "
                   "If it helps, recommend 3-5 places from <places> that fit what they want, give the listed straight-line distance, "
                   "and say briefly why from general knowledge. If the question is not about finding places (travel time, season), "
                   "answer that first and mention listed places only if useful. No bold or markdown.")
SUGGEST_ELSEWHERE = ("ในพื้นที่ที่ผู้ใช้ถามไม่มีสิ่งที่อยากหา ให้บอกสั้น ๆ ว่าแถวนั้นไม่มี แล้วเสนอ 3-5 แห่งจาก <places> ที่น่าจะไปได้สะดวกจากพื้นที่นั้น "
                     "บอกชื่อจังหวัดของแต่ละแห่ง ห้ามบอกระยะทาง ห้ามใช้ตัวหนาหรือ markdown")
SUGGEST_ELSEWHERE_EN = ("There is none of what the user wants in the area they asked about. Say so briefly, then suggest 3-5 places from <places> "
                        "that are likely convenient from that area, with each one's province. Do not give distances. No bold or markdown.")
SUGGEST_TASK = ("ผู้ใช้ยังไม่ได้บอกว่าอยู่หรือจะไปแถวไหน ให้เสนอ 3-5 แห่งจาก <places> ที่ตรงกับสิ่งที่ผู้ใช้อยากหา "
                "บอกชื่อจังหวัดของแต่ละแห่ง และเล่าสั้น ๆ ว่าน่าไปเพราะอะไรจากความรู้ทั่วไป ห้ามบอกระยะทาง "
                "ปิดท้ายด้วยการชวนให้บอกจังหวัด ชื่อที่พัก หรือกดใช้ตำแหน่งปัจจุบัน เพื่อค้นสถานที่รอบตัวจริง ห้ามใช้ตัวหนาหรือ markdown")
SUGGEST_TASK_EN = ("The user has not said where they are or are going. Suggest 3-5 places from <places> that fit what they want, "
                   "give each one's province and a short reason from general knowledge. Do not give distances. "
                   "End by inviting them to name a province or their stay, or use their current location, to search around it. No bold or markdown.")


def suggestion_places(verified, it: Intent, prev: str = "") -> list[dict]:
    """สถานที่ที่ตรวจแล้วสำหรับเสนอเมื่อยังไม่รู้ว่าแถวไหน: ตรงเรื่องที่อยากหา (จากข้อความนี้หรือคำถามก่อนหน้า)
    จังหวัดละ 1 แห่ง สลับไปทีละภาค (ไม่ใช่การจัดอันดับความนิยม) ไม่ตรงเรื่องเลยใช้ทุกประเภท"""
    subject, kinds = it.subject, it.kinds
    if not subject and prev:
        before = parse(prev)
        if before.subject or before.kinds != it.kinds:
            subject, kinds = before.subject, before.kinds
    words = _SUGGEST_WORDS.get(subject[0]) if subject else None
    subs = _SUGGEST_SUBTYPES.get(subject[0]) if subject else None
    if kinds == ("cafe",):
        subs = {"cafe"}

    def fits(c) -> bool:
        if words:
            return any(w in (c.name_th or "") for w in words)
        if subs:
            return c.subtype in subs
        return c.subtype != "cafe" if kinds == ("attraction",) else True

    pool = [c for c in verified if fits(c)] or ([] if (words or subs) else list(verified))
    by_prov: dict[str, object] = {}
    for c in pool:
        by_prov.setdefault(c.province, c)
    lanes = [[by_prov[p] for p in REGIONS[r] if p in by_prov] for r in REGION_ORDER]
    out = []
    for i in range(max((len(x) for x in lanes), default=0)):
        for lane in lanes:
            if i < len(lane):
                c = lane[i]
                out.append({"name_th": c.name_th, "name_en": c.name_en, "province": c.province})
    return out[:SUGGEST_LIMIT]


def _ask_location(it: Intent, lang: str = "th") -> list[str]:
    """ถามว่าให้ค้นแถวไหน โดยพูดทวนสิ่งที่ผู้ใช้อยากหา ("อยากหาวัดใช่ไหมคะ")"""
    if it.subject:
        th, en = it.subject
    elif it.kinds == ("cafe",):
        th, en = "คาเฟ่", "cafés"
    elif it.kinds == ("attraction",):
        th, en = "ที่เที่ยว", "attractions"
    else:
        th, en = "ที่เที่ยวกับคาเฟ่", "attractions and cafés"
    # ตัวอย่างจังหวัดให้เข้ากับสิ่งที่หา (ทะเล/เกาะ ยกตัวอย่างเชียงใหม่ไม่ได้)
    ex_th, ex_en = ("ภูเก็ต", "Phuket") if en in ("beaches", "islands") else ("เชียงใหม่", "Chiang Mai")
    return [_t(lang, f"อยากหา{th}ใช่ไหมคะ บอกน้องทริปหน่อยว่าแถวไหน",
               f"Looking for {en}? Tell me where."),
            _t(lang, f"พิมพ์ชื่อจังหวัด (เช่น \"{th}ใน{ex_th}\") ชื่อที่พัก หรือปักหมุดบนแผนที่ก็ได้ค่ะ",
               f"Type a province (for example \"{en} in {ex_en}\"), your stay's name, or pin the map.")]


def _smalltalk_parts(kind: str, lang: str = "th") -> list[str]:
    """คำตอบคุยเล่นตามชนิด ปิดท้ายด้วยคำชวนกลับมาเรื่องที่เที่ยว (ชนิด name/bot/maker มีคำแนะนำวิธีใช้ต่อท้ายด้วย)"""
    table = SMALLTALK_EN if lang == "en" else SMALLTALK_TH
    body = table.get(kind) or table["name"]
    out = list(body) + [_t(lang, SMALLTALK_ASK, SMALLTALK_ASK_EN)]
    if kind in ("name", "bot", "maker"):
        out.append(_t(lang, HELP_HINT, HELP_HINT_EN))
    return out


def answer(it: Intent, ctx: Context | None, svc: PlacesService, known: set[str],
           lang: str = "th") -> Iterator[tuple[str, dict]]:
    """สร้าง event ทีละขั้น (tool, places/lodgings, token) lang = th/en เฉพาะข้อความที่ระบบสร้างเอง"""
    tail = _tail(it, lang)
    L = lambda th, en: _t(lang, th, en)  # noqa: E731

    def say(*parts: str) -> Iterator[tuple[str, dict]]:
        for line in _lines(list(parts)).split("\n"):
            yield "token", {"text": line + "\n"}

    if it.smalltalk:
        yield from say(*_smalltalk_parts(it.smalltalk, lang))
        return

    if it.greeting:
        yield from say(L(HELP, HELP_EN))
        return

    if it.off_topic:
        yield from say(*_off_topic_parts(it, lang))
        return

    notes = list(it.notes)
    where = ""
    if it.province:
        yield "tool", {"name": "province_center", "args": {"province": it.province}}
        pc = svc.province_center(it.province)
        if pc.get("lat") is None:
            yield from say(L("หาจุดกลางของจังหวัดนี้ไม่ได้ในตอนนี้ กรุณาปักหมุดที่พักบนแผนที่หรือพิมพ์ชื่อที่พักแทน",
                             "Cannot find the centre of this province right now. Please pin your stay on the map or type its name."), *tail)
            return
        lat, lon = pc["lat"], pc["lon"]
        where = L(f"จุดกลางจังหวัด{it.province}", f"the centre of {province_en(it.province)}")
        notes.append("ค้นรอบจุดกลางจังหวัด ไม่ใช่รอบที่พักของคุณ ปักหมุดที่พักเพื่อให้ตรงขึ้น")
        # จุดกลางจากค่าเฉลี่ยพิกัดเป็นทางเลือกปกติของโหมดสแนปช็อต ไม่ต้องบอกผู้ใช้ด้วยศัพท์เทคนิค (ข้อความข้างบนบอกอยู่แล้วว่าไม่ใช่รอบที่พัก)
        if pc.get("notice") and pc.get("source") != "verified_centroid":
            notes.append(pc["notice"])
    elif ctx:
        lat, lon = ctx.lat, ctx.lon
        where = _one_line(it.anchor) if it.anchor else L("หมุดของคุณ", "your pin")
    elif it.lodging_query:
        yield "tool", {"name": "lodgings_search", "args": {"q": it.lodging_query}}
        res = svc.find_lodging(it.lodging_query)
        yield "lodgings", {"source": "search", "items": res["items"], "notices": res["notices"],
                           "osm_available": res["osm_available"], "osm_mode": res["osm_mode"]}
        if len(res["items"]) != 1:
            head = (L("พบที่พักหลายแห่ง กรุณาเลือกที่พักที่ตรงกับที่จอง แล้วถามใหม่พร้อมปักหมุดที่พักนั้น",
                      "Several stays match. Choose the one you booked, then ask again with that stay pinned.")
                    if res["items"] else L("ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น ปักหมุดบนแผนที่ หรือพิมพ์ชื่อจังหวัด",
                                           "No stay with this name. Try another name, pin the map, or type a province."))
            yield from say(head, *_notes(res["notices"], lang), *tail)
            return
        lod = res["items"][0]
        lat, lon = lod["lat"], lod["lon"]
        where = L(f"ที่พัก {_one_line(lod['name'])}", f"the stay {_one_line(lod['name'])}")
        notes += res["notices"]
    else:
        yield "ask", {"what": "location"}       # ภายในเท่านั้น: บอกหน้าเว็บผ่าน done.ask ให้แสดงปุ่มเลือกตำแหน่ง
        if it.asks_booking:
            yield from say(L("น้องทริปจองหรือชำระเงินแทนไม่ได้ค่ะ แต่ช่วยหาที่พักรอบจุดที่สนใจได้",
                             "I can't book or pay for you, but I can find places to stay around where you're going."),
                           L("บอกจังหวัดหรือปักหมุดบนแผนที่ เช่น \"ที่พักแถวภูเก็ต\" แล้วไปจองต่อกับผู้ให้บริการที่คุณใช้ได้เลย",
                             "Tell me a province or pin the map, for example \"stays in Phuket\", then book with the provider you use."))
            return
        yield from say(*_ask_location(it, lang), *tail)
        return

    if it.want_lodgings:
        yield "tool", {"name": "lodgings_near", "args": {"lat": lat, "lon": lon}}
        res = svc.lodgings_near(lat, lon)
        res["validation"] = validate_lodgings_near(res, known)
        res_notes = list(res.get("notices", []))
        if not res["validation"]["ok"]:
            res_notes.append(L(INVALID_NOTICE, INVALID_NOTICE_EN))
            res = {**res, "items": []}
        yield "lodgings", {"source": "near", "items": res["items"], "notices": res_notes,
                           "validation": res["validation"], "osm_available": res.get("osm_available"),
                           "osm_mode": res.get("osm_mode"), "radius_km": res.get("radius_km"),
                           "lodgings_total": res.get("lodgings_total"), "attribution": res.get("attribution")}
        items = res["items"]
        if not items:
            yield from say(L(f"ยังไม่พบที่พักรอบ{where}", f"No stays found around {where}"), *_notes(notes + res_notes, lang), *tail)
            return
        shown = items[: it.limit]
        rows = [L(f"{i}. {_one_line(x['name'])} ห่างหมุด {x['distance_from_pin_km']:g} กม. (เส้นตรง)",
                  f"{i}. {_one_line(x['name'])} — {x['distance_from_pin_km']:g} km from the pin (straight-line)")
                for i, x in enumerate(shown, 1)]
        yield from say(L(f"พบที่พักรอบ{where} {len(items)} แห่ง แสดง {len(shown)} แห่งที่ใกล้ที่สุด",
                         f"Found {len(items)} stays around {where}; showing the nearest {len(shown)}"), *rows,
                       L("ข้อมูลที่พักจาก OpenStreetMap ไม่มีราคาหรือห้องว่าง",
                         "Stay data from OpenStreetMap has no prices or availability."),
                       *_notes(notes + res_notes, lang), *tail)
        return

    # อยากหาเรื่องเจาะจงที่มีประเภทย่อยตรง (น้ำตก วัด จุดชมวิว ...): ค้นทุกแห่งในรัศมีแล้วกรองตาม subtype
    # ข้อความที่เอ่ยชื่อสถานที่ (anchor/named_place) ไม่กรอง เพราะคำว่า "วัด" เป็นส่วนของชื่อ ไม่ใช่สิ่งที่อยากหา
    subs = (SUBJECT_SUBTYPES.get(it.subject[0])
            if it.subject and not it.anchor and not it.named_place and "attraction" in it.kinds else None)
    kinds = ["attraction"] if subs else list(it.kinds)
    yield "tool", {"name": "places_nearby", "args": {"lat": lat, "lon": lon, "radius_km": it.radius_km, "kinds": kinds,
                                                     **({"subtypes": sorted(subs)} if subs else {})}}
    if subs:
        full = svc.nearby(lat, lon, it.radius_km, kinds, None, 0).to_dict()
        picked = [p for p in full["items"] if p.get("subtype") in subs]
        if picked:
            res = {**full, "items": picked[: it.limit], "total": len(picked), "counts": {"attraction": len(picked)},
                   "sources": {s: sum(1 for p in picked if p.get("source") == s) for s in ("verified", "osm")}}
        else:
            # ไม่มีประเภทนี้ในรัศมี (เช่น ทะเลรอบกรุงเทพ): ไม่ยื่นรายชื่อที่ไม่ตรงคำถาม บอกตรง ๆ แล้วให้เสนอที่อื่น (โหมด LLM)
            yield "ask", {"what": "location"}
            yield from say(L(f"ไม่พบ{it.subject[0]}ในรัศมี {full['radius_km']:g} กม. รอบ{where}",
                             f"No {it.subject[1]} within {full['radius_km']:g} km of {where}."),
                           L("ลองพิมพ์จังหวัดอื่น หรือปักหมุดที่พักบนแผนที่ได้ค่ะ", "Try another province or pin your stay on the map."),
                           *tail)
            return
    else:
        res = svc.nearby(lat, lon, it.radius_km, kinds, it.limit, 0).to_dict()
    res["validation"] = validate_nearby(res, known)
    res_notes = list(res["notices"])
    ok = res["validation"]["ok"]
    if not ok:
        res_notes.append(L(INVALID_NOTICE, INVALID_NOTICE_EN))
    items = res["items"] if ok else []
    yield "places", {"items": items, "validation": res["validation"], "notices": res_notes,
                     "center": res["center"], "radius_km": res["radius_km"], "total": res["total"],
                     "counts": res["counts"], "sources": res["sources"], "osm_mode": res["osm_mode"],
                     "osm_available": res["osm_available"], "attribution": res["attribution"],
                     "distance_note": res["distance_note"]}
    if not ok:
        yield from say(L("ผลค้นไม่ผ่านการตรวจอิสระ จึงยังไม่แสดงรายชื่อ ลองใหม่อีกครั้งภายหลัง",
                         "These results failed the independent check, so no names are shown. Please try again later."), *tail)
        return
    kinds_th = it.subject[0] if subs else " และ".join(KIND_TH[k] for k in kinds)
    kinds_en = it.subject[1] if subs else " and ".join(KIND_EN[k] for k in kinds)
    if not items:
        yield from say(L(f"ไม่พบ{kinds_th}ในรัศมี {res['radius_km']:g} กม. รอบ{where}",
                         f"No {kinds_en} within {res['radius_km']:g} km of {where}"),
                       *_notes(notes + res_notes, lang), *tail)
        return
    rows = [L(f"{i}. {_one_line(p['name_th'])} ห่าง {p['distance_km']:g} กม.",
              f"{i}. {_one_line(p['name_en'] or p['name_th'])} — {p['distance_km']:g} km")
            for i, p in enumerate(items, 1)]
    more = (L(f"ยังมีอีก {res['total'] - len(items)} แห่งในรัศมีนี้ บอกจำนวนที่อยากดูได้ เช่น \"10 แห่ง\"",
              f"{res['total'] - len(items)} more within this radius. Tell me how many you want, e.g. \"10 places\".")
            if res["total"] > len(items) else "")
    yield from say(L(f"พบ{kinds_th} {res['total']} แห่งในรัศมี {res['radius_km']:g} กม. รอบ{where} "
                     f"แสดง {len(items)} แห่งที่ใกล้ที่สุด",
                     f"Found {res['total']} {kinds_en} within {res['radius_km']:g} km of {where}; "
                     f"showing the nearest {len(items)}"), *rows, more, L(res["distance_note"], NOTE_EN.get(res["distance_note"], res["distance_note"])),
                   *_notes(notes + res_notes, lang), *tail)


def _footer(places_ev: dict | None, it: Intent, lang: str = "th") -> list[str]:
    """ข้อความที่โค้ดของเราเติมท้ายคำตอบ LLM (ไม่ผ่านด่านตรวจเพราะเป็นข้อความสำเร็จรูป): หมายเหตุระยะ ข้อความเตือน"""
    ev = places_ev or {}
    out = []
    note = (ev.get("distance_note") or "").strip()      # ที่มา © OSM แสดงที่ท้ายหน้าเว็บ ไม่ใส่ในข้อความแชท
    if note:
        out.append(_note_en(note) + "\n" if lang == "en" else note + "\n")
    out += [n + "\n" for n in _notes(list(ev.get("notices") or []), lang)]
    out += [t + "\n" for t in _tail(it, lang)]
    return out


def build_chat_router(store: Store, secret: str, svc: PlacesService, known: set[str],
                      throttle: ChatThrottle | None = None, rag: Rag | None = None) -> APIRouter:
    r = APIRouter()
    throttle = throttle or ChatThrottle()

    def user_of(req: Request) -> dict | None:
        return session_user(store, secret, req.cookies.get(COOKIE))

    @r.post("/api/chat")
    def chat(body: ChatIn, req: Request):
        if not throttle.allow(req.client.host if req.client else "?"):
            return _err(429, "rate_limited", "ส่งข้อความถี่เกินไป กรุณารอสักครู่แล้วลองใหม่")
        text = clean(body.message)
        if not text:
            return _err(400, "invalid_param", "ข้อความว่างเปล่า")
        ctx = body.context
        if ctx and not in_thailand(ctx.lat, ctx.lon):
            return _err(400, "invalid_param", "พิกัดอยู่นอกประเทศไทย")
        user = user_of(req)
        chat_id = None
        user_msg_id = None
        if user:
            if body.chat_id is not None:
                if not store.get_chat(user["id"], body.chat_id):
                    return _err(404, "not_found", "ไม่พบแชตนี้")
                chat_id = body.chat_id
                if body.edit_from is not None and not store.truncate_from(user["id"], chat_id, body.edit_from):
                    return _err(404, "not_found", "ไม่พบข้อความที่จะแก้")
            else:
                chat_id = store.create_chat(user["id"], text)
            user_msg_id = store.add_message(user["id"], chat_id, "user", text) or None

        hist = [(t.role, t.content) for t in (body.history or [])][-MAX_HISTORY:]

        def stream():
            parts: list[str] = []
            saved = False
            shown: dict = {}              # การ์ดที่ส่งให้ผู้ใช้จริง (places lodgings sources) เก็บไว้กับคำตอบ เปิดแชตเก่าแล้วเห็นเหมือนเดิม
            bot_msg_id = None

            def emit(ev: str, data: dict) -> str:
                if ev in ("places", "lodgings", "sources"):
                    shown[ev] = data
                return _sse(ev, data)

            def save(mode: str | None = None):
                nonlocal saved, bot_msg_id
                if user and chat_id and parts and not saved:
                    saved = True
                    try:
                        extra = {**shown, **({"mode": mode} if mode else {})}
                        bot_msg_id = store.add_message(user["id"], chat_id, "assistant", "".join(parts).strip(), extra or None) or None
                    except Exception:  # noqa: BLE001 บันทึกไม่ได้ไม่ควรทำให้คำตอบที่ส่งไปแล้วพัง
                        log.exception("save chat message failed")

            try:
                # พิมพ์ภาษาอังกฤษล้วน ตอบเป็นภาษาอังกฤษแม้หน้าเว็บตั้งภาษาไทยไว้
                if body.lang == "th" and not THAI.search(text) and len(re.findall(r"[A-Za-z]{2,}", text)) >= 3:
                    body.lang = "en"
                intent = parse(text)
                if intent.lodging_query and generic_stay_words(intent.lodging_query):
                    intent.lodging_query = None          # "ช่วยจองโรงแรมให้หน่อย" ไม่ใช่ชื่อที่พัก
                # ตอบต่อสั้น ๆ ที่บอกแค่ที่ ("เอาที่เชียงใหม่"): ใช้เรื่องที่อยากหาจากคำถามก่อนหน้า
                prev_user = next((c for r, c in reversed(hist) if r == "user" and c.strip()), "")
                if (prev_user and not intent.subject and intent.kinds == ("attraction", "cafe") and len(text) <= 30
                        and (intent.province or ctx)):
                    before = parse(clean(prev_user))
                    if before.subject:
                        intent.subject, intent.kinds = before.subject, before.kinds
                if intent.subject and find_place(drop_province(text), svc.verified):
                    intent.named_place = True
                # ข้อความใหม่ไม่ระบุที่ (ไม่มีจังหวัด ไม่มีหมุด ไม่มีชื่อที่พัก): ใช้จังหวัดที่ถามไว้ล่าสุด
                eff_ctx = ctx
                remember = None
                if not ctx and not intent.province and not intent.lodging_query and not intent.greeting and not intent.smalltalk:
                    # ไม่มีหมุด/จังหวัด แต่เอ่ยชื่อสถานที่ที่ตรวจแล้ว: ใช้ตำแหน่งสถานที่นั้นเป็นจุดค้น ไม่ต้องถามหาหมุดก่อน
                    # (ไม่ถือว่าเป็นหมุดของผู้ใช้ จึงไม่ย้ายหมุดบนหน้าเว็บ)
                    hit = find_place(text, svc.verified)
                    if not hit:
                        # คำถามต่อเนื่องที่ไม่เอ่ยชื่อที่ ("เล่าเพิ่มหน่อย"): ใช้สถานที่ที่เอ่ยในคำถามก่อนหน้าของแชตเดียวกัน
                        prev = next((c for r, c in reversed(hist) if r == "user" and c.strip()), "")
                        hit = find_place(drop_province(clean(prev)), svc.verified) if prev else None
                    if hit:
                        eff_ctx = Context(lat=hit.lat, lon=hit.lon)
                        intent.anchor = hit.name_th
                        intent.off_topic = False
                        remember = hit.province if hit.province in PROVINCES else None
                last = body.last_province if body.last_province in PROVINCES else None
                if last and not intent.province and not eff_ctx and not intent.lodging_query and not intent.greeting and not intent.smalltalk:
                    intent.province = last
                use_rag = rag is not None and rag.enabled and not intent.smalltalk  # คุยเล่นตอบสำเร็จรูป ไม่ส่งให้ LLM
                off_topic = intent.off_topic
                if use_rag:
                    # โหมด LLM ต้องได้ผลค้นรอบจุดเดิมไปเป็นบริบทเหมือนเดิม (คำถามข้อเท็จจริงอย่าง "พระธาตุพนมสูงกี่เมตร" ไม่มีคำค้น)
                    # จึงไม่ตัดก่อนถึง LLM แต่ถ้า LLM ไม่ได้ตอบ (ไม่มีก้อนความรู้ตรงคำถาม ฯลฯ) และเป็นข้อความนอกเรื่อง
                    # จะบอกว่านอกเรื่องแทนการแสดงรายชื่อที่ไม่เกี่ยวกับคำถาม
                    intent.off_topic = False
                held: list[str] = []          # ข้อความแบบกฎที่พักไว้จนรู้ว่า LLM ผ่านด่านตรวจหรือไม่
                places_ev: dict | None = None
                pending: list[tuple[str, dict]] = []
                t0 = time.perf_counter()
                ask = None
                for ev, data in answer(intent, eff_ctx, svc, known, body.lang):
                    if ev == "ask":
                        ask = data["what"]
                        continue
                    if ev == "places":
                        places_ev = data
                    if ev == "token" and use_rag:
                        held.append(data["text"])
                        continue
                    if ev != "token" and off_topic and use_rag:
                        pending.append((ev, data))        # นอกเรื่อง: ยังไม่ส่งการ์ดสถานที่จนกว่า LLM จะตอบจริง
                        continue
                    if ev == "token":
                        parts.append(data["text"])
                    yield emit(ev, data)
                mode = "rule"
                t_search = time.perf_counter() - t0
                t1 = time.perf_counter()
                general_used = False
                if use_rag:
                    items = (places_ev or {}).get("items") or []
                    # ยังไม่รู้ว่าแถวไหนไม่มีผลค้นให้ตอบ ข้ามไปเสนอสถานที่เลย ไม่เสียการเรียก LLM อีกรอบ
                    res = (RagResult("rule", reason="no_places") if ask == "location"
                           else rag.answer(text, items, (places_ev or {}).get("radius_km"), body.lang, hist))
                    # คลังความรู้ไม่มีเรื่องนี้ หรือเป็นคำถามเรื่องเที่ยวทั่วไป (ฤดู การเดินทาง แผนเที่ยว อาหารท้องถิ่น) ที่ค้นได้แค่รายชื่อ:
                    # ให้ LLM ตอบจากความรู้ทั่วไปพร้อมคำเตือน ดีกว่าบอกว่าไม่มีข้อมูลแล้วยื่นรายชื่อที่ไม่ตรงคำถาม
                    no_info = res.mode == "llm" and is_no_info(res.text)
                    wants_general = (intent.asks_general or intent.asks_food) and not intent.smalltalk
                    trav = None
                    suggested = narrated = False
                    if ask == "location" and not off_topic and not intent.asks_booking:
                        # ยังไม่รู้ว่าแถวไหน: แทนการถามกลับอย่างเดียว ให้เสนอสถานที่ที่ตรวจแล้วจากหลายภาคก่อน ปุ่มเลือกตำแหน่งยังอยู่
                        prev = next((c for r, c in reversed(hist) if r == "user" and c.strip()), "")
                        sugg = suggestion_places(svc.verified, intent, clean(prev))
                        if sugg:
                            elsewhere = bool(intent.province or eff_ctx)   # ถามแถวที่ไม่มีของที่อยากหา
                            task = ((SUGGEST_ELSEWHERE_EN if body.lang == "en" else SUGGEST_ELSEWHERE) if elsewhere
                                    else (SUGGEST_TASK_EN if body.lang == "en" else SUGGEST_TASK))
                            trav = rag.travel(text, sugg, body.lang, hist, task=task)
                            suggested = True
                    elif not off_topic and (no_info or (wants_general and res.mode == "rule" and res.reason in ("no_places", "no_chunks"))):
                        trav = rag.travel(text, items, body.lang, hist)
                    elif (not off_topic and items and res.mode == "rule" and res.reason in ("no_places", "no_chunks", "guard")
                          and not intent.asks_money):
                        # ค้นเจอแต่ไม่มีก้อนความรู้ตรงคำถาม: ให้ LLM เรียบเรียงจากผลค้นจริง แทนการยื่นรายชื่อเปล่า ๆ
                        trav = rag.travel(text, items, body.lang, hist,
                                          task=NARRATE_TASK_EN if body.lang == "en" else NARRATE_TASK)
                        narrated = True
                    if trav is not None and trav.mode == "llm":
                        mode = "llm"
                        general_used = True
                        for ev, data in pending:
                            yield emit(ev, data)
                        head = (_t(body.lang, SUGGEST_DISCLAIMER, SUGGEST_DISCLAIMER_EN) if suggested
                                else _t(body.lang, NARRATE_DISCLAIMER, NARRATE_DISCLAIMER_EN) if narrated
                                else _t(body.lang, TRAVEL_DISCLAIMER, TRAVEL_DISCLAIMER_EN))
                        lines = [head + "\n"]
                        lines += [ln + "\n" for ln in trav.text.split("\n") if ln.strip()]
                        if items:
                            foot = _footer(places_ev, intent, body.lang)
                            # หมายเหตุของคำตอบแบบกฎ (เช่น ค้นรอบจุดกลางจังหวัด ไม่ใช่รอบที่พัก) ยังต้องบอกผู้ใช้
                            foot += [h for h in held if h.startswith(("หมายเหตุ:", "Note:")) and h not in foot]
                            lines += foot
                    elif res.mode == "llm" and not (off_topic and no_info):
                        mode = "llm"
                        for ev, data in pending:
                            yield emit(ev, data)
                        yield emit("sources", {"items": res.sources})
                        lines = [ln + "\n" for ln in res.text.split("\n") if ln.strip()]
                        lines += _footer(places_ev, intent, body.lang)
                    elif off_topic:
                        # นอกเรื่อง: ให้ LLM ตอบจากความรู้ทั่วไป ขึ้นต้นด้วยคำเตือนที่โค้ดใส่เอง ไม่ผ่านด่านตรวจใช้คำตอบสำเร็จรูปเดิม
                        # ถามเรื่องอาหาร: ตอบเรื่องอาหารท้องถิ่นแบบทั่วไป (ห้ามแนะนำร้านเฉพาะแห่ง ระบบไม่มีข้อมูลร้านอาหาร)
                        if intent.asks_food:
                            gen = rag.travel(text, [], body.lang, hist)
                            head = _t(body.lang, TRAVEL_DISCLAIMER, TRAVEL_DISCLAIMER_EN)
                        else:
                            gen = rag.general(text, body.lang, hist)
                            head = _t(body.lang, GENERAL_DISCLAIMER, GENERAL_DISCLAIMER_EN)
                        if gen is not None and gen.mode == "llm":
                            mode = "llm"
                            general_used = True
                            lines = [head + "\n"]
                            lines += [ln + "\n" for ln in gen.text.split("\n") if ln.strip()]
                            lines.append(_t(body.lang, CAN_DO, CAN_DO_EN) + "\n")
                        else:
                            lines = [ln + "\n" for ln in _lines(_off_topic_parts(intent, body.lang)).split("\n") if ln.strip()]
                    else:
                        if intent.asks_money:
                            # ถามราคา/ค่าเข้า: บอกก่อนเลยว่าไม่มีข้อมูล แล้วค่อยรายชื่อ (ด่านตรวจตีตกเรื่องราคาเป็นเรื่องปกติ ไม่ต้องบอก)
                            money = [h for h in held if h.strip() in [x.strip() for x in _tail(intent, body.lang)[:1]]]
                            lines = money + [h for h in held if h not in money]
                        else:
                            lines = held + ([_notes([GUARD_NOTICE], body.lang)[0] + "\n"] if res.guard_failed else [])
                    for ln in lines:
                        parts.append(ln)
                        yield emit("token", {"text": ln})
                save(mode)
                metrics.count("chat", mode)
                # เวลาของแต่ละขั้น ไว้ดูว่าช้าที่ไหน (ไม่มีข้อความของผู้ใช้ในบรรทัดนี้) ขึ้นใน log ของ uvicorn
                logging.getLogger("uvicorn.error").info(
                    "chat timing: ค้นสถานที่ %.1f วินาที, ขั้น RAG/LLM %.1f วินาที, โหมด %s",
                    t_search, time.perf_counter() - t1, mode)
                yield emit("done", {"chat_id": chat_id, "mode": mode,
                                   **({"message_id": bot_msg_id} if bot_msg_id else {}),
                                   **({"user_message_id": user_msg_id} if user_msg_id else {}), **({"province": intent.province or remember} if (intent.province or remember) else {}),
                                   **({"ask": ask} if ask and (mode == "rule" or general_used) else {})})
            except SearchError as e:
                yield emit("error", {"error": str(e), "code": "invalid_param"})
            except Exception:  # noqa: BLE001 ไม่ส่งรายละเอียดภายในให้ผู้ใช้
                log.exception("chat failed")
                yield emit("error", {"error": "เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่", "code": "internal"})
            finally:
                save()

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return r
