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
import threading
import time
from collections import deque
from typing import Iterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.places import PlacesService, SearchError
from services.places.geo import in_thailand

from . import auth
from .accounts import COOKIE, MAX_ID
from .chat_rules import MAX_MESSAGE, Intent, clean, parse
from .store import Store
from .validator import validate_lodgings_near, validate_nearby

log = logging.getLogger("nongtrip.chat")

KIND_TH = {"attraction": "สถานที่เที่ยว", "cafe": "คาเฟ่"}
SOURCE_TH = {"verified": "ตรวจที่มาแล้ว", "osm": "ข้อมูล OpenStreetMap"}
INVALID_NOTICE = "ผลค้นนี้ไม่ผ่านการตรวจอิสระ โปรดอย่าเชื่อถือจนกว่าจะตรวจสอบ"

HELP = ("สวัสดีค่ะ น้องทริปช่วยหาสถานที่เที่ยวและคาเฟ่รอบที่พักของคุณได้ ในรัศมีไม่เกิน 30 กม. เรียงจากใกล้ไปไกล\n"
        "ลองพิมพ์ เช่น \"คาเฟ่ใกล้ๆ\" (ถ้าปักหมุดไว้แล้ว) \"ที่เที่ยวในเชียงใหม่ 5 แห่ง\" หรือ \"ที่พักแถวภูเก็ต\"\n"
        "ระบบไม่มีราคา ค่าเข้า รีวิว หรือคะแนน และไม่จองหรือชำระเงินให้")
ASK_LOCATION = ("ยังไม่รู้ว่าให้ค้นรอบไหน กรุณาปักหมุดที่พักบนแผนที่ พิมพ์ชื่อจังหวัด (เช่น \"คาเฟ่ในเชียงใหม่\") "
                "หรือพิมพ์ชื่อที่พัก (เช่น \"ที่เที่ยวใกล้โรงแรมชื่อนี้\")")


class Context(BaseModel):
    lat: float
    lon: float


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    context: Context | None = None
    chat_id: int | None = Field(default=None, ge=1, le=MAX_ID)


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


def _tail(it: Intent) -> list[str]:
    """หมายเหตุเรื่องที่ระบบไม่มี/ไม่ทำ บอกตรงๆ แทนการเดา"""
    out = []
    if it.asks_money:
        out.append("ระบบไม่มีข้อมูลราคา ค่าเข้า หรืองบประมาณ จึงไม่แสดงและไม่ประมาณให้")
    if it.asks_review:
        out.append("ระบบไม่เก็บรีวิวหรือคะแนน กดลิงก์ Google Maps ที่การ์ดสถานที่เพื่อดูรีวิวจริง")
    if it.asks_booking:
        out.append("ระบบไม่จองหรือชำระเงินแทนผู้ใช้")
    return out


def _lines(parts: list[str]) -> str:
    return "\n".join(p for p in parts if p)


def _notes(notices: list[str]) -> list[str]:
    return [f"หมายเหตุ: {n}" for n in notices]


def answer(it: Intent, ctx: Context | None, svc: PlacesService, known: set[str]) -> Iterator[tuple[str, dict]]:
    """สร้าง event ทีละขั้น (tool, places/lodgings, token)"""
    tail = _tail(it)

    def say(*parts: str) -> Iterator[tuple[str, dict]]:
        for line in _lines(list(parts)).split("\n"):
            yield "token", {"text": line + "\n"}

    if it.greeting:
        yield from say(HELP)
        return

    notes = list(it.notes)
    where = ""
    if it.province:
        yield "tool", {"name": "province_center", "args": {"province": it.province}}
        pc = svc.province_center(it.province)
        if pc.get("lat") is None:
            yield from say("หาจุดกลางของจังหวัดนี้ไม่ได้ในตอนนี้ กรุณาปักหมุดที่พักบนแผนที่หรือพิมพ์ชื่อที่พักแทน", *tail)
            return
        lat, lon = pc["lat"], pc["lon"]
        where = f"จุดกลางจังหวัด{it.province}"
        notes.append("ค้นรอบจุดกลางจังหวัด ไม่ใช่รอบที่พักของคุณ ปักหมุดที่พักเพื่อให้ตรงขึ้น")
        if pc.get("notice"):
            notes.append(pc["notice"])
    elif ctx:
        lat, lon = ctx.lat, ctx.lon
        where = "หมุดของคุณ"
    elif it.lodging_query:
        yield "tool", {"name": "lodgings_search", "args": {"q": it.lodging_query}}
        res = svc.find_lodging(it.lodging_query)
        yield "lodgings", {"source": "search", "items": res["items"], "notices": res["notices"],
                           "osm_available": res["osm_available"], "osm_mode": res["osm_mode"]}
        if len(res["items"]) != 1:
            head = ("พบที่พักหลายแห่ง กรุณาเลือกที่พักที่ตรงกับที่จอง แล้วถามใหม่พร้อมปักหมุดที่พักนั้น"
                    if res["items"] else "ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น ปักหมุดบนแผนที่ หรือพิมพ์ชื่อจังหวัด")
            yield from say(head, *_notes(res["notices"]), *tail)
            return
        lod = res["items"][0]
        lat, lon = lod["lat"], lod["lon"]
        where = f"ที่พัก {_one_line(lod['name'])}"
        notes += res["notices"]
    else:
        yield from say(ASK_LOCATION, *tail)
        return

    if it.want_lodgings:
        yield "tool", {"name": "lodgings_near", "args": {"lat": lat, "lon": lon}}
        res = svc.lodgings_near(lat, lon)
        res["validation"] = validate_lodgings_near(res, known)
        res_notes = list(res.get("notices", []))
        if not res["validation"]["ok"]:
            res_notes.append(INVALID_NOTICE)
            res = {**res, "items": []}
        yield "lodgings", {"source": "near", "items": res["items"], "notices": res_notes,
                           "validation": res["validation"], "osm_available": res.get("osm_available"),
                           "osm_mode": res.get("osm_mode"), "radius_km": res.get("radius_km"),
                           "lodgings_total": res.get("lodgings_total"), "attribution": res.get("attribution")}
        items = res["items"]
        if not items:
            yield from say(f"ยังไม่พบที่พักรอบ{where}", *_notes(notes + res_notes), *tail)
            return
        shown = items[: it.limit]
        rows = [f"{i}. {_one_line(x['name'])} ห่างหมุด {x['distance_from_pin_km']:g} กม. (เส้นตรง)"
                for i, x in enumerate(shown, 1)]
        yield from say(f"พบที่พักรอบ{where} {len(items)} แห่ง แสดง {len(shown)} แห่งที่ใกล้ที่สุด", *rows,
                       "ข้อมูลที่พักจาก OpenStreetMap ไม่มีราคาหรือห้องว่าง " + (res.get("attribution") or ""),
                       *_notes(notes + res_notes), *tail)
        return

    yield "tool", {"name": "places_nearby", "args": {"lat": lat, "lon": lon, "radius_km": it.radius_km,
                                                     "kinds": list(it.kinds)}}
    res = svc.nearby(lat, lon, it.radius_km, list(it.kinds), it.limit, 0).to_dict()
    res["validation"] = validate_nearby(res, known)
    res_notes = list(res["notices"])
    ok = res["validation"]["ok"]
    if not ok:
        res_notes.append(INVALID_NOTICE)
    items = res["items"] if ok else []
    yield "places", {"items": items, "validation": res["validation"], "notices": res_notes,
                     "center": res["center"], "radius_km": res["radius_km"], "total": res["total"],
                     "counts": res["counts"], "sources": res["sources"], "osm_mode": res["osm_mode"],
                     "osm_available": res["osm_available"], "attribution": res["attribution"],
                     "distance_note": res["distance_note"]}
    if not ok:
        yield from say("ผลค้นไม่ผ่านการตรวจอิสระ จึงยังไม่แสดงรายชื่อ ลองใหม่อีกครั้งภายหลัง", *tail)
        return
    kinds_th = " และ".join(KIND_TH[k] for k in it.kinds)
    if not items:
        yield from say(f"ไม่พบ{kinds_th}ในรัศมี {res['radius_km']:g} กม. รอบ{where}", *_notes(notes + res_notes), *tail)
        return
    rows = [f"{i}. {_one_line(p['name_th'])} ({KIND_TH[p['kind']]}, {SOURCE_TH[p['source']]}) "
            f"ห่าง {p['distance_km']:g} กม." for i, p in enumerate(items, 1)]
    more = (f"ยังมีอีก {res['total'] - len(items)} แห่งในรัศมีนี้ บอกจำนวนที่อยากดูได้ เช่น \"10 แห่ง\""
            if res["total"] > len(items) else "")
    attr = res["attribution"] if any(p["source"] == "osm" for p in items) else ""
    yield from say(f"พบ{kinds_th} {res['total']} แห่งในรัศมี {res['radius_km']:g} กม. รอบ{where} "
                   f"แสดง {len(items)} แห่งที่ใกล้ที่สุด", *rows, more, f"{res['distance_note']} {attr}".strip(),
                   *_notes(notes + res_notes), *tail)


def build_chat_router(store: Store, secret: str, svc: PlacesService, known: set[str],
                      throttle: ChatThrottle | None = None) -> APIRouter:
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
                for ev, data in answer(parse(text), ctx, svc, known):
                    if ev == "token":
                        parts.append(data["text"])
                    yield _sse(ev, data)
                save()
                yield _sse("done", {"chat_id": chat_id})
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
