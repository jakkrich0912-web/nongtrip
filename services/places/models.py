"""รูปแบบข้อมูลที่บริการคืน (ตรงกับ docs/CONTRACT.md หัวข้อ 4) ไม่มีฟิลด์ราคา รีวิว หรือคะแนน"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ATTRIBUTION_OSM = "© OpenStreetMap contributors (ODbL)"


@dataclass
class Candidate:
    """สถานที่ดิบ ยังไม่มีระยะ ใช้เก็บในแคชต่อได้"""
    id: str
    name_th: str
    name_en: str | None
    kind: str            # attraction | cafe | lodging
    subtype: str         # temple, waterfall, hotel ฯลฯ
    lat: float
    lon: float
    source: str          # verified | osm
    province: str | None = None
    source_url: str | None = None

    def to_cache(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_cache(cls, d: dict) -> "Candidate":
        return cls(**d)


@dataclass
class Place:
    id: str
    name_th: str
    name_en: str | None
    kind: str
    subtype: str
    lat: float
    lon: float
    distance_km: float
    source: str
    province: str | None
    source_url: str | None
    maps_url: str
    directions_url: str

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class SearchResult:
    center: dict
    radius_km: float
    items: list[Place]
    total: int
    offset: int
    limit: int | None
    counts: dict
    sources: dict
    osm_available: bool
    notices: list[str] = field(default_factory=list)
    osm_mode: str = "live"      # live | snapshot | none
    attribution: str = ATTRIBUTION_OSM
    data_as_of: str | None = None   # v0.26: วันที่ดึงข้อมูล OSM ที่เก็บไว้ (โหมด snapshot) โหมดอื่นเป็น None

    def to_dict(self) -> dict[str, Any]:
        return {
            "center": self.center,
            "radius_km": self.radius_km,
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "counts": self.counts,
            "sources": self.sources,
            "osm_available": self.osm_available,
            "osm_mode": self.osm_mode,
            "data_as_of": self.data_as_of,
            "notices": self.notices,
            "attribution": self.attribution,
            "distance_note": "ระยะเป็นเส้นตรง ไม่ใช่ระยะขับรถ",
            "items": [p.to_dict() for p in self.items],
        }


@dataclass
class LodgingCandidate:
    id: str
    name: str
    address: str | None
    subtype: str | None
    lat: float
    lon: float
    province: str | None = None  # รู้จากที่อยู่ (ออนไลน์) หรือไฟล์สแนปช็อตของจังหวัดนั้น ไม่รู้ = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)
