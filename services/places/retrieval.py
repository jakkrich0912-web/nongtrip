"""ตัวค้นคืนจากคลังความรู้ (RAG ขั้น 2) ใช้ BM25 ในหน่วยความจำ ไม่พึ่งไลบรารีภายนอก

ตามแผน docs/RAG_PLAN.md ข้อ 4:
- ข้อความไทยตัดเป็น n-gram ตัวอักษร (3 ตัว) ไม่ต้องใช้ตัวตัดคำ ข้อความอังกฤษใช้คำเต็ม
- กรองด้วย place_id ก่อนค้น (ถามถึงที่เดียว หรือจำกัดตามผลค้นรอบนั้น)
- ส่งต่อไม่เกิน TOP_K ก้อน และรวมไม่เกิน MAX_CONTEXT_CHARS ตัวอักษร
- ก้อนที่คะแนนไม่ถึงเกณฑ์ไม่ถูกส่งต่อ (ถ้าไม่มีเลย ผู้เรียกต้องตอบว่าไม่มีข้อมูล ห้ามให้ LLM เดา)
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from .knowledge import DEFAULT_DIR, load_all

NGRAM = 3
K1 = 1.5
B = 0.75
TOP_K = 4
MAX_CONTEXT_CHARS = 4000
MIN_COVERAGE = 0.4     # สัดส่วนโทเค็นของคำถามที่ต้องพบในก้อน ต่ำกว่านี้ถือว่าไม่เกี่ยว (ยกเว้นคำถามที่มีชื่อสถานที่ของก้อนนั้นครบ)
MIN_COVERAGE_PLACE = 0.3   # เกณฑ์เมื่อจำกัดที่สถานที่เดียว (ผู้ใช้เลือกสถานที่แล้ว ถามสั้น ๆ ได้ ไม่ต้องเข้มเท่าถามทั้งคลัง)
MIN_NAME_TOKENS = 3    # ชื่อที่นับว่า "ถามชื่อตรง ๆ" ต้องมีโทเค็นอย่างน้อยเท่านี้ (ชื่อสั้นเกินไปจะชนคำทั่วไป)
_THAI_RUN = re.compile(r"[฀-๿]{4,}")
TITLE_WEIGHT = 2       # ชื่อเรื่องนับซ้ำเท่านี้ เพื่อให้ถามชื่อแล้วเจอก้อนของที่นั้นก่อน

_THAI = re.compile(r"[฀-๿]+")
_WORD = re.compile(r"[a-z0-9]+")
_EN_STOP = frozenset("the of is are was were a an in on at to and or for with what where when who how which".split())


def tokens(text: str) -> list[str]:
    """แยกโทเค็น: ไทยเป็น trigram ต่อช่วงตัวอักษรไทยที่ติดกัน (ช่วงสั้นกว่า 2 ตัวทิ้ง) อังกฤษเป็นคำ"""
    t = unicodedata.normalize("NFC", text or "").lower()
    out: list[str] = []
    for run in _THAI.findall(t):
        if len(run) < 2:
            continue
        if len(run) <= NGRAM:
            out.append(run)
        else:
            out.extend(run[i:i + NGRAM] for i in range(len(run) - NGRAM + 1))
    out.extend(w for w in _WORD.findall(t) if w not in _EN_STOP and (len(w) >= 2 or w.isdigit()))
    return out


def verified_names() -> dict[str, list[str]]:
    """ชื่อไทย/อังกฤษของสถานที่ที่ตรวจแล้ว (place_id -> ชื่อ) ไว้ให้ค้นด้วยชื่อไทยเจอก้อนที่เป็นภาษาอังกฤษล้วน"""
    from .verified import load_verified
    return {c.id: [n for n in (c.name_th, c.name_en) if n] for c in load_verified()}


def _alias_sets(doc: dict, place_names: list[str]) -> list[frozenset]:
    """ชื่อที่ใช้ตัดสินว่าคำถามพูดถึงสถานที่ของก้อนนี้โดยตรง: ชื่อที่ให้มา + title + ชื่อไทยในวงเล็บต้นข้อความ
    (บทความอังกฤษมักมี "(Thai: ชื่อไทย)" ซึ่งทำให้คำถามภาษาไทยจับคู่กับก้อนอังกฤษได้)"""
    title = doc.get("title", "")
    cands = [title, *place_names]
    if not _THAI_RUN.search(title):
        cands.extend(_THAI_RUN.findall(doc.get("text", "")[:300]))
    sets = {frozenset(tokens(c)) for c in cands if c}
    return [s for s in sets if len(s) >= MIN_NAME_TOKENS]


class Retriever:
    def __init__(self, docs: Iterable[dict], names: Mapping[str, Iterable[str]] | None = None):
        """names: place_id -> ชื่อสถานที่ (ไทย/อังกฤษ) นับเป็นชื่อเรื่องของทุกก้อนของที่นั้น ไม่ใส่ = ใช้เฉพาะ title ของก้อน"""
        self.docs: list[dict] = [d for d in docs if d.get("id") and d.get("text")]
        names = names or {}
        self._tf: list[Counter] = []
        self._len: list[int] = []
        self._post: dict[str, list[int]] = defaultdict(list)
        self._by_place: dict[str, list[int]] = defaultdict(list)
        self._alias: list[list[frozenset]] = []   # ชุดโทเค็นของชื่อสถานที่แต่ละชื่อของก้อน
        for i, d in enumerate(self.docs):
            place_names = list(names.get(d.get("place_id", ""), ()))
            self._alias.append(_alias_sets(d, place_names))
            head = tokens(d.get("title", "")) + tokens(" ".join(place_names))
            toks = head * TITLE_WEIGHT + tokens(d["text"])
            tf = Counter(toks)
            self._tf.append(tf)
            self._len.append(len(toks))
            for tok in tf:
                self._post[tok].append(i)
            self._by_place[d.get("place_id", "")].append(i)
        n = len(self.docs)
        self._avg = (sum(self._len) / n) if n else 0.0
        self._idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self._post.items()}

    @classmethod
    def from_dir(cls, directory: Path | str = DEFAULT_DIR, names: Mapping[str, Iterable[str]] | None = None) -> "Retriever":
        """names ไม่ใส่ = ใช้ชื่อจากสถานที่ที่ตรวจแล้ว (verified_names)"""
        return cls(load_all(directory), verified_names() if names is None else names)

    def __len__(self) -> int:
        return len(self.docs)

    def search(self, query: str, place_ids: Iterable[str] | None = None, k: int = TOP_K,
               min_coverage: float | None = None) -> list[dict]:
        """คืนรายการ {"doc", "score", "coverage"} เรียงคะแนนมากไปน้อย

        place_ids: จำกัดเฉพาะก้อนของสถานที่เหล่านี้ (None = ทั้งคลัง, ชุดว่าง = ไม่มีผล)
        min_coverage: ไม่ใส่ = MIN_COVERAGE (ทั้งคลัง) หรือ MIN_COVERAGE_PLACE (จำกัดสถานที่)
        """
        if min_coverage is None:
            min_coverage = MIN_COVERAGE if place_ids is None else MIN_COVERAGE_PLACE
        q = list(dict.fromkeys(tokens(query)))   # ไม่ซ้ำ คงลำดับ
        if not q or not self.docs or k <= 0:
            return []
        if place_ids is None:
            allowed = None
        else:
            allowed = {i for p in set(place_ids) for i in self._by_place.get(p, ())}
            if not allowed:
                return []
        scores: dict[int, float] = defaultdict(float)
        matched: dict[int, int] = defaultdict(int)
        for tok in q:
            idf = self._idf.get(tok)
            if idf is None:
                continue
            for i in self._post[tok]:
                if allowed is not None and i not in allowed:
                    continue
                f = self._tf[i][tok]
                norm = 1 - B + B * (self._len[i] / self._avg if self._avg else 1.0)
                scores[i] += idf * f * (K1 + 1) / (f + K1 * norm)
                matched[i] += 1
        qset = set(q)
        hits = [{"doc": self.docs[i], "score": round(s, 4), "coverage": round(matched[i] / len(q), 3)}
                for i, s in scores.items()
                if matched[i] / len(q) >= min_coverage or any(a <= qset for a in self._alias[i])]
        hits.sort(key=lambda h: (-h["score"], h["doc"]["id"]))
        return hits[:k]


def fit_context(hits: list[dict], max_chars: int = MAX_CONTEXT_CHARS) -> list[dict]:
    """เก็บก้อนตามลำดับคะแนนจนรวมตัวอักษรถึงเพดาน ก้อนที่ล้นเพดานข้ามไป (ไม่ตัดกลางข้อความ)"""
    out, used = [], 0
    for h in hits:
        n = len(h["doc"]["text"])
        if used + n > max_chars:
            continue
        out.append(h)
        used += n
    return out


def source_items(hits: list[dict]) -> list[dict]:
    """รายการที่มาสำหรับ event `sources` (CONTRACT v0.13 ร่าง) ไม่ซ้ำตาม id"""
    seen, items = set(), []
    for h in hits:
        d = h["doc"]
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        items.append({"id": d["id"], "place_id": d["place_id"], "title": d["title"], "url": d["url"],
                      "license": d["license"], "checked_on": d["checked_on"]})
    return items


def evaluate(retriever: Retriever, cases: list[dict], k: int = 3) -> dict:
    """วัดผลกับชุดคำถาม: case = {"q", "place_ids"?, "expect": id ก้อนที่ถูก หรือ null เมื่อคลังไม่ควรมีคำตอบ}

    hit@k นับเฉพาะข้อที่มีก้อนถูก, no_answer_ok นับข้อ expect=null ที่ไม่มีผลส่งต่อเลย
    """
    answerable = [c for c in cases if c.get("expect")]
    none_cases = [c for c in cases if not c.get("expect")]
    hits_ok, misses, none_ok, false_hits = 0, [], 0, []
    for c in answerable:
        got = [h["doc"]["id"] for h in retriever.search(c["q"], c.get("place_ids"), k=k)]
        if c["expect"] in got:
            hits_ok += 1
        else:
            misses.append({"q": c["q"], "expect": c["expect"], "got": got})
    for c in none_cases:
        got = [h["doc"]["id"] for h in retriever.search(c["q"], c.get("place_ids"), k=k)]
        if not got:
            none_ok += 1
        else:
            false_hits.append({"q": c["q"], "got": got})
    return {"answerable": len(answerable), "hit_at_k": (hits_ok / len(answerable)) if answerable else None,
            "k": k, "misses": misses, "no_answer": len(none_cases),
            "no_answer_ok": (none_ok / len(none_cases)) if none_cases else None, "false_hits": false_hits}
