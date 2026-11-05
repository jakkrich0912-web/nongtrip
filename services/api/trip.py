"""ถามต่อจากทริปที่บันทึก (POST /api/me/trip/ask, CONTRACT v0.26)

ทริป = สถานที่โปรดทั้งหมดของผู้ใช้ จุดเริ่ม = ที่พักที่ค้นไว้ (ระบุ stay_id หรือใช้ครั้งล่าสุด)
ตอบแบบกฎจากข้อมูลในฐานข้อมูลเท่านั้น ไม่ส่งให้ LLM: นับประเภท จุดที่อยู่ใกล้กัน ลำดับจากที่พัก ระยะไกลสุด
ถามหาประเภทที่ทริปยังไม่มี (เช่นคาเฟ่) ค้นรอบที่พักให้ ผลค้นผ่านตัวตรวจเดิมก่อนแสดง
ระยะทั้งหมดเป็นเส้นตรง ไม่จัดอันดับว่าที่ไหนดีกว่า
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.places import PlacesService
from services.places.geo import haversine_km

from .accounts import COOKIE, session_user
from .chat import ChatThrottle
from .chat_rules import SUBJECT_SUBTYPES, clean, find_subject
from .store import Store
from .validator import validate_nearby

GROUP_KM = 2.0          # จุดที่ห่างกันไม่เกินนี้ถือว่าไปวันเดียวกันได้
SEARCH_KM = 5.0         # ค้นประเภทที่ยังไม่มีรอบที่พัก
SHOW = 5

_CAFE = re.compile(r"คาเฟ่|กาแฟ|ร้านกาแฟ|\bcaf[eé]s?\b|\bcoffee\b", re.I)
_ATTR = re.compile(r"ที่เที่ยว|สถานที่เที่ยว|\battractions?\b|\bsights?\b", re.I)
_GROUP = re.compile(r"ใกล้กัน|วันเดียว|กลุ่ม|รวมกัน|\bclose (?:to each other|together)\b|\bsame day\b|\bgroup", re.I)
_ORDER = re.compile(r"ลำดับ|ไปไหนก่อน|ไปที่ไหนก่อน|เริ่มที่ไหน|\border\b|\bfirst\b|\broute\b", re.I)
_FAR = re.compile(r"ไกล|ระยะ|\bfar\w*\b|\bdistance\b", re.I)


class TripAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    stay_id: int | None = Field(default=None, ge=1, le=2**53)
    lang: Literal["th", "en"] = "th"


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


def _km(a: dict, b: dict) -> float:
    return round(haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]), 2)


def groups_of(places: list[dict], max_km: float = GROUP_KM) -> list[list[dict]]:
    """จับกลุ่มแบบต่อกันเป็นสาย (ห่างกันไม่เกิน max_km) คืนเฉพาะกลุ่มที่มีตั้งแต่ 2 จุด"""
    parent = list(range(len(places)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(places)):
        for j in range(i + 1, len(places)):
            if _km(places[i], places[j]) <= max_km:
                parent[find(i)] = find(j)
    out: dict[int, list[dict]] = {}
    for i, p in enumerate(places):
        out.setdefault(find(i), []).append(p)
    return [g for g in out.values() if len(g) >= 2]


def answer_trip(question: str, favs: list[dict], stay: dict | None, svc: PlacesService, known: set[str],
                lang: str = "th") -> dict:
    """คืน {"answer": ข้อความ, "places": ผลค้นที่ผ่านตัวตรวจ หรือ None}"""
    en = lang == "en"
    L = (lambda th, e: e if en else th)  # noqa: E731
    name = (lambda p: (p.get("name_en") or p["name_th"]) if en else p["name_th"])  # noqa: E731
    if not favs:
        return {"answer": L("ทริปยังว่างอยู่ กดรูปหัวใจบนการ์ดสถานที่ในหน้าค้นหาเพื่อเพิ่มเข้าทริปก่อน",
                            "Your trip is empty. Tap the heart on a place card in search to add places first."), "places": None}
    q = clean(question)
    stops = sorted(favs, key=lambda p: _km(stay, p)) if stay else list(favs)
    where = (L(f"รอบ {stay['name']}", f"around {stay['name']}") if stay else "")
    n_cafe = sum(1 for p in favs if p["kind"] == "cafe")
    n_attr = len(favs) - n_cafe
    lines: list[str] = []
    places = None

    want_cafe, want_attr = bool(_CAFE.search(q)), bool(_ATTR.search(q))
    subject = find_subject(q)
    subs = SUBJECT_SUBTYPES.get(subject[0]) if subject else None
    if subs:
        have = [p for p in stops if p.get("subtype") in subs]
        label = L(subject[0], subject[1])
        if have:
            lines.append(L(f"ทริปนี้มี{label} {len(have)} แห่ง: ", f"Your trip has {len(have)} {label}: ") + ", ".join(name(p) for p in have))
        else:
            lines.append(L(f"ทริปนี้ยังไม่มี{label}", f"Your trip has no {label} yet."))
    elif want_cafe or want_attr:
        kind = "cafe" if want_cafe else "attraction"
        have = [p for p in stops if (p["kind"] == "cafe") == (kind == "cafe")]
        label = L("คาเฟ่", "cafés") if kind == "cafe" else L("ที่เที่ยว", "attractions")
        if have:
            lines.append(L(f"ทริปนี้มี{label} {len(have)} แห่ง: ", f"Your trip has {len(have)} {label}: ") + ", ".join(name(p) for p in have))
        else:
            lines.append(L(f"ทริปนี้ยังไม่มี{label}", f"Your trip has no {label} yet."))
            if stay:
                res = svc.nearby(stay["lat"], stay["lon"], SEARCH_KM, [kind], SHOW, 0).to_dict()
                res["validation"] = validate_nearby(res, known)
                if res["validation"]["ok"] and res["items"]:
                    places = {"items": res["items"], "total": res["total"], "attribution": res["attribution"],
                              "distance_note": res["distance_note"]}
                    lines.append(L(f"{label}ในรัศมี {SEARCH_KM:g} กม. (เส้นตรง) {where} มี {res['total']} แห่ง ใกล้สุด {len(res['items'])} แห่งอยู่ด้านล่าง กดหัวใจเพื่อเพิ่มเข้าทริป",
                                   f"There are {res['total']} {label} within {SEARCH_KM:g} km (straight-line) {where}. The nearest {len(res['items'])} are below; tap the heart to add one."))
                elif res["validation"]["ok"]:
                    lines.append(L(f"ไม่พบ{label}ในรัศมี {SEARCH_KM:g} กม. {where}", f"No {label} within {SEARCH_KM:g} km {where}."))
            else:
                lines.append(L("ค้นที่พักในหน้าค้นหาก่อน แล้วน้องทริปจะหาให้รอบที่พัก", "Search for your stay first and NongTrip can look around it."))
    elif _GROUP.search(q):
        groups = groups_of(stops)
        if not groups:
            lines.append(L(f"ไม่มีจุดไหนห่างกันไม่เกิน {GROUP_KM:g} กม. (เส้นตรง)", f"No places are within {GROUP_KM:g} km (straight-line) of each other."))
        for g in groups:
            span = max(_km(a, b) for a in g for b in g)
            lines.append(L(f"กลุ่ม {len(g)} แห่ง ห่างกันไม่เกิน {span:g} กม. (เส้นตรง): ", f"{len(g)} places within {span:g} km (straight-line): ") + ", ".join(name(p) for p in g))
    elif _ORDER.search(q):
        if stay:
            lines.append(L(f"เรียงจากใกล้ไปไกล{where}:", f"Nearest to farthest {where}:"))
            lines += [L(f"{i}. {name(p)} ห่าง {_km(stay, p):g} กม. (เส้นตรง)", f"{i}. {name(p)} — {_km(stay, p):g} km (straight-line)")
                      for i, p in enumerate(stops, 1)]
        else:
            lines.append(L("ยังไม่รู้ที่พัก ค้นที่พักในหน้าค้นหาก่อน แล้วน้องทริปจะเรียงจุดให้จากที่พัก",
                           "No stay yet. Search for your stay first and NongTrip will order the stops from it."))
    elif _FAR.search(q) and stay:
        far = stops[-1]
        lines.append(L(f"จุดที่ไกลสุดจากที่พักคือ {name(far)} ห่าง {_km(stay, far):g} กม. (เส้นตรง)",
                       f"The farthest stop from your stay is {name(far)}, {_km(stay, far):g} km (straight-line)."))
    else:
        lines.append(L(f"ทริปนี้มี {len(favs)} แห่ง: ที่เที่ยว {n_attr} คาเฟ่ {n_cafe}",
                       f"Your trip has {len(favs)} places: {n_attr} attractions and {n_cafe} cafés."))
        groups = groups_of(stops)
        if groups:
            lines.append(L(f"มี {len(groups)} กลุ่มที่อยู่ใกล้กัน (ไม่เกิน {GROUP_KM:g} กม.) ไปวันเดียวกันได้",
                           f"{len(groups)} group(s) are within {GROUP_KM:g} km of each other and fit in one day."))
        if stay:
            lines.append(L(f"จุดที่ไกลสุดจากที่พักห่าง {_km(stay, stops[-1]):g} กม. (เส้นตรง)",
                           f"The farthest stop is {_km(stay, stops[-1]):g} km (straight-line) from your stay."))
        lines.append(L("ถามต่อได้ เช่น ทริปนี้ขาดคาเฟ่ไหม จุดไหนอยู่ใกล้กัน ไปที่ไหนก่อนดี",
                       "Try: does my trip have cafés? Which places are close together? Which order?"))
    return {"answer": "\n".join(lines), "places": places}


def build_trip_router(store: Store, secret: str, svc: PlacesService, known: set[str],
                      throttle: ChatThrottle | None = None) -> APIRouter:
    r = APIRouter()
    throttle = throttle or ChatThrottle()

    @r.post("/api/me/trip/ask")
    def ask(body: TripAskIn, req: Request):
        user = session_user(store, secret, req.cookies.get(COOKIE))
        if not user:
            return _err(401, "unauthorized", "กรุณาเข้าสู่ระบบก่อน")
        if not throttle.allow(f"trip:{user['id']}"):
            return _err(429, "rate_limited", "ถามถี่เกินไป กรุณารอสักครู่แล้วลองใหม่")
        if not clean(body.question):
            return _err(400, "invalid_param", "คำถามว่างเปล่า")
        favs = [{"id": f["place_id"], "name_th": f["name_th"], "name_en": f["name_en"], "kind": f["kind"],
                 "subtype": f["subtype"], "lat": f["lat"], "lon": f["lon"], "source": f["source"]}
                for f in store.list_favorites(user["id"])]
        searches = store.list_searches(user["id"])
        stay = next((s for s in searches if s["id"] == body.stay_id), None) if body.stay_id else (searches[0] if searches else None)
        if body.stay_id and not stay:
            return _err(404, "not_found", "ไม่พบที่พักนี้ในรายการของคุณ")
        out = answer_trip(body.question, favs, stay, svc, known, body.lang)
        return {**out, "mode": "rule", "stay": ({"id": stay["id"], "name": stay["name"]} if stay else None)}

    return r
