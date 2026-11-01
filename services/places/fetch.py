"""ตัวเรียก HTTP แบบมีมารยาทต่อบริการสาธารณะ (User-Agent, หน่วงเวลา Nominatim)"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

USER_AGENT = "NongTrip-student-project/0.1 (course project, RMUTT)"
# นโยบาย Nominatim: ไม่เกิน 1 คำขอต่อวินาที
MIN_INTERVAL = {"nominatim.openstreetmap.org": 1.1}


class UpstreamError(Exception):
    """เรียกบริการภายนอกไม่สำเร็จ (เน็ตหลุด หมดเวลา ตอบผิดรูปแบบ)"""


class UpstreamTooBig(UpstreamError):
    """คำขอใหญ่เกินที่เซิร์ฟเวอร์ภายนอกยอมรับ (ลดรัศมีแล้วลองใหม่ได้)"""


class HttpClient:
    def __init__(self, timeout: float = 30, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}

    def _throttle(self, url: str) -> None:
        host = urllib.parse.urlparse(url).netloc
        gap = MIN_INTERVAL.get(host)
        if gap:
            wait = self._last.get(host, -1e9) + gap - self._clock()
            if wait > 0:
                self._sleep(wait)
            self._last[host] = self._clock()

    def _open(self, req: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (413, 414):
                raise UpstreamTooBig(f"HTTP {e.code}") from e
            raise UpstreamError(f"HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise UpstreamError(str(e)) from e

    def get_json(self, url: str, params: dict | None = None) -> Any:
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        self._throttle(url)
        return self._open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}))

    def post_form(self, url: str, data: dict) -> Any:
        self._throttle(url)
        body = urllib.parse.urlencode(data).encode("utf-8")
        return self._open(urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT}))
