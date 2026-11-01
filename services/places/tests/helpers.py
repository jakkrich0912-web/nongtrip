"""ตัวจำลองบริการ OSM สำหรับเทสต์ (ไม่เรียกเน็ตจริง)"""
from services.places.fetch import UpstreamError, UpstreamTooBig
from services.places.models import Candidate

CM = (18.7883, 98.9853)  # กลางเมืองเชียงใหม่


def el(i, name, lat, lon, tags, typ="node"):
    return {"type": typ, "id": i, "lat": lat, "lon": lon, "tags": {"name": name, **tags}}


class FakeHttp:
    """post_form = Overpass, get_json = Nominatim; ตอบตามที่ตั้งไว้และนับจำนวนครั้งที่ถูกเรียก"""

    def __init__(self, overpass=None, nominatim=None, overpass_error=None, nominatim_error=None, too_big_above_km=None):
        self.overpass = overpass or []
        self.nominatim = nominatim or []
        self.overpass_error = overpass_error
        self.nominatim_error = nominatim_error
        self.too_big_above_km = too_big_above_km
        self.calls = []

    def post_form(self, url, data):
        self.calls.append(("overpass", url, data["data"]))
        if self.overpass_error:
            raise self.overpass_error
        if self.too_big_above_km is not None:
            r = int(data["data"].split("around:")[1].split(",")[0]) / 1000
            if r > self.too_big_above_km:
                raise UpstreamTooBig("too big")
        return {"elements": self.overpass}

    def get_json(self, url, params=None):
        self.calls.append(("nominatim", url, params))
        if self.nominatim_error:
            raise self.nominatim_error
        return self.nominatim

    def count(self, kind):
        return sum(1 for c in self.calls if c[0] == kind)


def cand(i, name, lat, lon, kind="attraction", source="osm", en=None):
    return Candidate(id=i, name_th=name, name_en=en, kind=kind, subtype="x", lat=lat, lon=lon, source=source)
