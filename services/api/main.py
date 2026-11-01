"""API กลางของน้องทริป: ประตูเดียวที่หน้าเว็บคุยด้วย (ดู docs/CONTRACT.md)

รัน:  python -m uvicorn services.api.main:app --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.places import PlacesService, SearchError
from services.places.provinces import REGION_ORDER, REGIONS
from services.places.verified import coverage_by_province

from .validator import load_verified_ids, validate_lodgings_near, validate_nearby


def create_app(service: PlacesService | None = None) -> FastAPI:
    app = FastAPI(title="น้องทริป API", version="0.4")
    svc = service or PlacesService()
    known = load_verified_ids()
    origins = [o for o in (os.environ.get("WEB_ORIGINS") or "*").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(SearchError)
    async def _search_error(_: Request, e: SearchError):
        return JSONResponse({"error": str(e)}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def _bad_params(_: Request, e: RequestValidationError):
        fields = ", ".join(".".join(str(x) for x in err["loc"][1:]) for err in e.errors())
        return JSONResponse({"error": f"พารามิเตอร์ไม่ถูกต้อง: {fields}"}, status_code=400)

    @app.get("/api/health")
    def health():
        snap = svc.snapshot
        return {"ok": True, "osm_live": svc.osm_live, "snapshot_available": snap.available(),
                "verified_places": len(svc.verified)}

    @app.get("/api/provinces")
    def provinces():
        cov = coverage_by_province(svc.verified)
        return {"regions": [
            {"region": r, "provinces": [{"name": p, "verified_count": cov[p]} for p in REGIONS[r]]}
            for r in REGION_ORDER]}

    @app.get("/api/provinces/{name}/center")
    def province_center(name: str):
        return svc.province_center(name)

    @app.get("/api/lodgings/search")
    def lodgings_search(q: str = Query(..., min_length=1)):
        return svc.find_lodging(q)

    @app.get("/api/places/nearby")
    def places_nearby(lat: float, lon: float, radius_km: float = 30.0,
                      kinds: str = "attraction,cafe", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        res = svc.nearby(lat, lon, radius_km, [k.strip() for k in kinds.split(",") if k.strip()], limit, offset).to_dict()
        res["validation"] = validate_nearby(res, known)
        if not res["validation"]["ok"]:
            res["notices"] = res["notices"] + ["ผลค้นนี้ไม่ผ่านการตรวจอิสระ โปรดอย่าเชื่อถือจนกว่าจะตรวจสอบ"]
        return res

    @app.get("/api/lodgings/near")
    def lodgings_near(lat: float, lon: float):
        res = svc.lodgings_near(lat, lon)
        res["validation"] = validate_lodgings_near(res, known)
        if not res["validation"]["ok"]:
            res["notices"] = res["notices"] + ["ผลค้นนี้ไม่ผ่านการตรวจอิสระ โปรดอย่าเชื่อถือจนกว่าจะตรวจสอบ"]
        return res

    return app


app = create_app()
