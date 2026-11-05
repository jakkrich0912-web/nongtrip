"""สแนปช็อต OpenStreetMap ที่ดึงไว้ล่วงหน้า (scripts/prefetch_osm.py) ใช้เมื่อออนไลน์ไม่ได้
ข้อมูล © OpenStreetMap contributors (ODbL) เก็บแค่ ชื่อ ประเภท พิกัด"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .models import Candidate, LodgingCandidate
from .osm import unsuitable

DEFAULT_DIR = Path(__file__).parent / "data" / "osm_snapshot"
DEG_PER_KM = 1 / 111.0


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def write_province(directory: Path | str, province: str, cands: list[Candidate], built_on: str) -> Path:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    rows = [[c.id[4:], c.name_th, c.name_en, c.kind, c.subtype, round(c.lat, 5), round(c.lon, 5)] for c in cands]
    path = d / f"{province}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"_meta": {"province": province, "built_on": built_on, "count": len(rows),
                                         "source": "© OpenStreetMap contributors (ODbL)"}, "items": rows},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return path


class Snapshot:
    def __init__(self, directory: Path | str | None = DEFAULT_DIR):
        self.dir = Path(directory) if directory else None
        self._items: list[Candidate] | None = None
        self.built_on: str | None = None
        self.provinces: list[str] = []
        self.dates: dict[str, str] = {}      # จังหวัด -> วันที่ดึงข้อมูล (_meta.built_on)

    def available(self) -> bool:
        return bool(self.dir and self.dir.is_dir() and any(self.dir.glob("*.json")))

    def _load(self) -> list[Candidate]:
        if self._items is not None:
            return self._items
        items: list[Candidate] = []
        dates = []
        if self.available():
            for f in sorted(self.dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                meta = data.get("_meta", {})
                if meta.get("built_on"):
                    dates.append(meta["built_on"])
                prov = meta.get("province") or f.stem
                self.provinces.append(prov)
                if meta.get("built_on"):
                    self.dates[prov] = meta["built_on"]
                for ref, th, en, kind, sub, lat, lon in data.get("items", []):
                    if unsuitable(th, en, sub, ref):
                        continue
                    items.append(Candidate(id=f"osm:{ref}", name_th=th, name_en=en, kind=kind, subtype=sub,
                                           lat=lat, lon=lon, source="osm", province=prov,
                                           source_url=f"https://www.openstreetmap.org/{ref}"))
        self.built_on = min(dates) if dates else None
        self._items = items
        return items

    def date_of(self, provinces) -> str | None:
        """วันที่ดึงข้อมูลเก่าสุดของจังหวัดที่ระบุ (ใช้แสดงความสดของข้อมูล) ไม่รู้วันที่คืน None"""
        self._load()
        dates = [self.dates[p] for p in set(provinces) if p in self.dates]
        return min(dates) if dates else None

    def around(self, lat: float, lon: float, radius_km: float, kinds: tuple[str, ...]) -> list[Candidate]:
        """คัดแบบกรอบสี่เหลี่ยมก่อน (ระยะจริงคิดต่อทีหลังในตัวจัดอันดับ)"""
        dlat = radius_km * DEG_PER_KM
        dlon = dlat / max(0.2, abs(math.cos(math.radians(lat))))
        return [c for c in self._load()
                if c.kind in kinds and abs(c.lat - lat) <= dlat and abs(c.lon - lon) <= dlon]

    def find_lodging(self, query: str, limit: int = 8, province: str | None = None,
                     subtype: str | None = None) -> list[LodgingCandidate]:
        """ค้นชื่อที่พักแบบออฟไลน์: ทุกคำในคำค้นต้องอยู่ในชื่อ (ไทยหรืออังกฤษ) กรองจังหวัด/ประเภทได้"""
        words = [_norm(w) for w in query.split() if _norm(w)]
        if not words:
            return []
        out = []
        for c in self._load():
            if c.kind != "lodging" or (province and c.province != province) or (subtype and c.subtype != subtype):
                continue
            hay = _norm(c.name_th) + _norm(c.name_en or "")
            if all(w in hay for w in words):
                out.append(LodgingCandidate(id=c.id, name=c.name_th, address=None, subtype=c.subtype, lat=c.lat, lon=c.lon,
                                            province=c.province))
        out.sort(key=lambda x: len(x.name))
        return out[:limit]
