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
from services.places.provinces import PROVINCES, province_en

from . import auth
from .accounts import COOKIE, MAX_ID
from .answer_guard import GUARD_NOTICE
from .chat_rules import MAX_MESSAGE, Intent, clean, find_place, parse
from .rag import Rag
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
OFF_TOPIC = "เรื่องนี้น้องทริปช่วยไม่ได้นะ น้องทริปช่วยหาสถานที่เที่ยวและคาเฟ่รอบที่พักของคุณ ในรัศมีไม่เกิน 30 กม. เรียงจากใกล้ไปไกล"
HELP_HINT = ("ลองพิมพ์ เช่น \"คาเฟ่ใกล้ๆ\" (ถ้าปักหมุดไว้แล้ว) \"ที่เที่ยวในเชียงใหม่ 5 แห่ง\" หรือ \"ที่พักแถวภูเก็ต\"")
ASK_LOCATION = ("ยังไม่รู้ว่าให้ค้นรอบไหน กรุณาปักหมุดที่พักบนแผนที่ พิมพ์ชื่อจังหวัด (เช่น \"คาเฟ่ในเชียงใหม่\") "
                "หรือพิมพ์ชื่อที่พัก (เช่น \"ที่เที่ยวใกล้โรงแรมชื่อนี้\")")


HELP_EN = ("Hi! NongTrip finds attractions and cafés around your stay, within 30 km, nearest first.\n"
           "Try: \"cafés nearby\" (once you have pinned your stay), \"attractions in Chiang Mai, 5 places\" or \"stays around Phuket\".\n"
           "The system has no prices, entry fees, reviews or scores, and does not book or take payment.")
OFF_TOPIC_EN = "NongTrip cannot help with that. It finds attractions and cafés around your stay, within 30 km, nearest first."
HELP_HINT_EN = "Try: \"cafés nearby\" (once you have pinned your stay), \"attractions in Chiang Mai, 5 places\" or \"stays around Phuket\"."
ASK_LOCATION_EN = ("I do not know where to search yet. Pin your stay on the map, type a province "
                   "(for example \"cafés in Chiang Mai\") or type your stay's name.")

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


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    context: Context | None = None
    chat_id: int | None = Field(default=None, ge=1, le=MAX_ID)
    # จังหวัดที่ถามไว้ล่าสุด (หน้าเว็บจำจาก event done) ใช้เมื่อข้อความใหม่ไม่ระบุที่ เช่น "แล้วคาเฟ่ล่ะ"
    last_province: str | None = Field(default=None, max_length=60)
    lang: Literal["th", "en"] = "th"


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


def _off_topic_parts(it: Intent, lang: str = "th") -> list[str]:
    """ข้อความตอบเมื่อข้อความไม่เกี่ยวกับที่เที่ยว/คาเฟ่/ที่พัก ถ้าถามเรื่องอาหารบอกด้วยว่ายังไม่มีข้อมูลร้านอาหาร"""
    food = _t(lang, "ตอนนี้ระบบยังไม่มีข้อมูลร้านอาหาร มีเฉพาะที่เที่ยว คาเฟ่ และที่พัก",
              "The system has no restaurant data yet, only attractions, cafés and stays.") if it.asks_food else ""
    return [_t(lang, OFF_TOPIC, OFF_TOPIC_EN), food, _t(lang, HELP_HINT, HELP_HINT_EN)]


def answer(it: Intent, ctx: Context | None, svc: PlacesService, known: set[str],
           lang: str = "th") -> Iterator[tuple[str, dict]]:
    """สร้าง event ทีละขั้น (tool, places/lodgings, token) lang = th/en เฉพาะข้อความที่ระบบสร้างเอง"""
    tail = _tail(it, lang)
    L = lambda th, en: _t(lang, th, en)  # noqa: E731

    def say(*parts: str) -> Iterator[tuple[str, dict]]:
        for line in _lines(list(parts)).split("\n"):
            yield "token", {"text": line + "\n"}

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
        yield from say(L(ASK_LOCATION, ASK_LOCATION_EN), *tail)
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

    yield "tool", {"name": "places_nearby", "args": {"lat": lat, "lon": lon, "radius_km": it.radius_km,
                                                     "kinds": list(it.kinds)}}
    res = svc.nearby(lat, lon, it.radius_km, list(it.kinds), it.limit, 0).to_dict()
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
    kinds_th = " และ".join(KIND_TH[k] for k in it.kinds)
    kinds_en = " and ".join(KIND_EN[k] for k in it.kinds)
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
        uid = auth.read_token(req.cookies.get(COOKIE), secret)
        return store.user_by_id(uid) if uid else None

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
        if user:
            if body.chat_id is not None:
                if not store.get_chat(user["id"], body.chat_id):
                    return _err(404, "not_found", "ไม่พบแชตนี้")
                chat_id = body.chat_id
            else:
                chat_id = store.create_chat(user["id"], text)
            store.add_message(user["id"], chat_id, "user", text)

        def stream():
            parts: list[str] = []
            saved = False

            def save():
                nonlocal saved
                if user and chat_id and parts and not saved:
                    saved = True
                    try:
                        store.add_message(user["id"], chat_id, "assistant", "".join(parts).strip())
                    except Exception:  # noqa: BLE001 บันทึกไม่ได้ไม่ควรทำให้คำตอบที่ส่งไปแล้วพัง
                        log.exception("save chat message failed")

            try:
                intent = parse(text)
                # ข้อความใหม่ไม่ระบุที่ (ไม่มีจังหวัด ไม่มีหมุด ไม่มีชื่อที่พัก): ใช้จังหวัดที่ถามไว้ล่าสุด
                eff_ctx = ctx
                remember = None
                if not ctx and not intent.province and not intent.lodging_query and not intent.greeting:
                    # ไม่มีหมุด/จังหวัด แต่เอ่ยชื่อสถานที่ที่ตรวจแล้ว: ใช้ตำแหน่งสถานที่นั้นเป็นจุดค้น ไม่ต้องถามหาหมุดก่อน
                    # (ไม่ถือว่าเป็นหมุดของผู้ใช้ จึงไม่ย้ายหมุดบนหน้าเว็บ)
                    hit = find_place(text, svc.verified)
                    if hit:
                        eff_ctx = Context(lat=hit.lat, lon=hit.lon)
                        intent.anchor = hit.name_th
                        intent.off_topic = False
                        remember = hit.province if hit.province in PROVINCES else None
                last = body.last_province if body.last_province in PROVINCES else None
                if last and not intent.province and not eff_ctx and not intent.lodging_query and not intent.greeting:
                    intent.province = last
                use_rag = rag is not None and rag.enabled
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
                for ev, data in answer(intent, eff_ctx, svc, known, body.lang):
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
                    yield _sse(ev, data)
                mode = "rule"
                t_search = time.perf_counter() - t0
                t1 = time.perf_counter()
                if use_rag:
                    res = rag.answer(text, (places_ev or {}).get("items") or [], (places_ev or {}).get("radius_km"), body.lang)
                    if res.mode == "llm":
                        mode = "llm"
                        for ev, data in pending:
                            yield _sse(ev, data)
                        yield _sse("sources", {"items": res.sources})
                        lines = [ln + "\n" for ln in res.text.split("\n") if ln.strip()]
                        lines += _footer(places_ev, intent, body.lang)
                    elif off_topic:
                        lines = [ln + "\n" for ln in _lines(_off_topic_parts(intent, body.lang)).split("\n") if ln.strip()]
                    else:
                        lines = held + ([_notes([GUARD_NOTICE], body.lang)[0] + "\n"] if res.guard_failed else [])
                    for ln in lines:
                        parts.append(ln)
                        yield _sse("token", {"text": ln})
                save()
                # เวลาของแต่ละขั้น ไว้ดูว่าช้าที่ไหน (ไม่มีข้อความของผู้ใช้ในบรรทัดนี้) ขึ้นใน log ของ uvicorn
                logging.getLogger("uvicorn.error").info(
                    "chat timing: ค้นสถานที่ %.1f วินาที, ขั้น RAG/LLM %.1f วินาที, โหมด %s",
                    t_search, time.perf_counter() - t1, mode)
                yield _sse("done", {"chat_id": chat_id, "mode": mode, **({"province": intent.province or remember} if (intent.province or remember) else {})})
            except SearchError as e:
                yield _sse("error", {"error": str(e), "code": "invalid_param"})
            except Exception:  # noqa: BLE001 ไม่ส่งรายละเอียดภายในให้ผู้ใช้
                log.exception("chat failed")
                yield _sse("error", {"error": "เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่", "code": "internal"})
            finally:
                save()

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return r
