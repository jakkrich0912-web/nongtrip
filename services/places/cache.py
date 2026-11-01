"""แคช JSON แบบมีอายุ (ในหน่วยความจำ + ไฟล์) ลดการเรียกบริการสาธารณะซ้ำ"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable


class TTLCache:
    def __init__(self, directory: str | os.PathLike | None, ttl_seconds: float = 7 * 86400,
                 clock: Callable[[], float] = time.time):
        self.dir = Path(directory) if directory else None
        self.ttl = ttl_seconds
        self.clock = clock
        self._mem: dict[str, tuple[float, Any]] = {}
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

    def get(self, key: str) -> Any | None:
        now = self.clock()
        hit = self._mem.get(key)
        if hit and now - hit[0] <= self.ttl:
            return hit[1]
        if self.dir:
            try:
                raw = json.loads(self._path(key).read_text(encoding="utf-8"))
                if now - raw["t"] <= self.ttl:
                    self._mem[key] = (raw["t"], raw["v"])
                    return raw["v"]
            except (OSError, ValueError, KeyError):
                pass
        return None

    def set(self, key: str, value: Any) -> None:
        now = self.clock()
        self._mem[key] = (now, value)
        if self.dir:
            try:
                tmp = self._path(key).with_suffix(".tmp")
                tmp.write_text(json.dumps({"t": now, "v": value}, ensure_ascii=False), encoding="utf-8")
                tmp.replace(self._path(key))
            except OSError:
                pass  # แคชเขียนไม่ได้ไม่ควรทำให้การค้นล้ม
