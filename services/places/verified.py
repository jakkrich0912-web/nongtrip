"""โหลดสถานที่ที่ตรวจที่มาแล้ว (verified=true เท่านั้น) จากไฟล์ใน data/"""
from __future__ import annotations

import json
from pathlib import Path

from .models import Candidate

DATA_DIR = Path(__file__).parent / "data"
FILES = ("places.json", "places_all_provinces.json")


def load_verified(data_dir: Path | str = DATA_DIR) -> list[Candidate]:
    out: dict[str, Candidate] = {}
    for fname in FILES:
        path = Path(data_dir) / fname
        if not path.exists():
            continue
        for p in json.loads(path.read_text(encoding="utf-8"))["places"]:
            if not p.get("verified") or p.get("lat") is None or p.get("lon") is None:
                continue
            kind = "cafe" if p.get("category") == "cafe" else "attraction"
            srcs = p.get("sources") or []
            out[f"v:{p['id']}"] = Candidate(
                id=f"v:{p['id']}",
                name_th=p["name_th"],
                name_en=p.get("name_en"),
                kind=kind,
                subtype=p.get("category") or "other",
                lat=float(p["lat"]),
                lon=float(p["lon"]),
                source="verified",
                province=p.get("province"),
                source_url=srcs[0]["url"] if srcs else None,
            )
    return list(out.values())
