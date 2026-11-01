import importlib.util
import sys
from pathlib import Path

from services.places.fetch import UpstreamError
from services.places.models import Candidate

spec = importlib.util.spec_from_file_location("prefetch_osm", Path(__file__).parents[3] / "scripts" / "prefetch_osm.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)


def c(i):
    return Candidate(id=f"osm:node/{i}", name_th="ก", name_en=None, kind="lodging", subtype="hotel", lat=17.6, lon=100.1, source="osm")


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.queries = []

    def run(self, q):
        self.queries.append(q)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_empty_result_is_retried_not_accepted():
    cl = FakeClient([[], [c(1), c(2)]])
    assert len(pf.fetch_kind(cl, "อุตรดิตถ์", "lodging", pause=0)) == 2 and len(cl.queries) == 2


def test_persistent_empty_splits_by_filter():
    n = len(pf.split_filters("lodging"))
    cl = FakeClient([[]] * pf.RETRIES + [[c(1)]] + [[]] * (n - 1))
    out = pf.fetch_kind(cl, "อุตรดิตถ์", "lodging", pause=0)
    assert len(out) == 1 and len(cl.queries) == pf.RETRIES + n


def test_error_retries_then_raises():
    import pytest
    cl = FakeClient([UpstreamError("x")] * pf.RETRIES)
    with pytest.raises(UpstreamError):
        pf.fetch_kind(cl, "ลำปาง", "cafe", pause=0)
