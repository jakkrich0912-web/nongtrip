"""ตัวเชื่อม LLM (RAG ขั้น 4) ไม่ผูกกับผู้ให้บริการรายใด: เลือกด้วย LLM_PROVIDER ใน .env

- mock หรือไม่ตั้งค่า/ไม่มีคีย์/ไม่ระบุ LLM_MODEL = ไม่มี LLM (แชตใช้โหมดกฎตามเดิม)
- anthropic / openai เรียกผ่าน HTTPS ด้วย urllib ไม่เพิ่มไลบรารี
- timeout 30 วินาที ลองซ้ำไม่เกิน 1 ครั้ง (เฉพาะเน็ต/5xx/429) ล้มเหลวแล้วผู้เรียกถอยไปโหมดกฎ
- ไม่บันทึกคีย์ ข้อความถาม หรือเนื้อคำตอบลง log
"""
from __future__ import annotations

import json
import re
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping

log = logging.getLogger("nongtrip.llm")

TIMEOUT = 30
RETRIES = 1
MAX_TOKENS = 2000      # รวมโทเคนที่โมเดลใช้คิด (Sonnet 5.5 เปิดโหมดคิดเองโดยปริยาย) เพดานต่ำเกินไปทำให้ได้ข้อความว่าง
MAX_RESPONSE_BYTES = 200_000
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
PROVIDERS = ("anthropic", "openai")


class LLMError(Exception):
    """เรียก LLM ไม่สำเร็จ (ข้อความไม่มีความลับ ผู้เรียกถอยไปโหมดกฎ)"""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _post_json(url: str, headers: Mapping[str, str], body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL ตายตัว https)
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise LLMError(f"LLM ตอบ HTTP {e.code}", retryable=e.code == 429 or e.code >= 500) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMError(f"เชื่อมต่อ LLM ไม่ได้ ({type(e).__name__})", retryable=True) from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise LLMError("คำตอบจาก LLM ใหญ่ผิดปกติ")
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise LLMError("คำตอบจาก LLM ไม่ใช่ JSON") from None
    if not isinstance(data, dict):
        raise LLMError("รูปแบบคำตอบจาก LLM ไม่ถูกต้อง")
    return data


class LLMClient:
    def __init__(self, provider: str, model: str, api_key: str, timeout: float = TIMEOUT, retries: int = RETRIES,
                 post: Callable[[str, Mapping[str, str], dict, float], dict] = _post_json):
        if provider not in PROVIDERS:
            raise ValueError(f"ไม่รู้จักผู้ให้บริการ {provider}")
        self.provider, self.model, self._key = provider, model, api_key
        self.timeout, self.retries, self._post = timeout, max(0, retries), post

    def __repr__(self) -> str:      # กันคีย์หลุดตอนพิมพ์ object ลง log
        return f"LLMClient(provider={self.provider!r}, model={self.model!r})"

    def _request(self, system: str, user: str, max_tokens: int) -> tuple[str, Mapping[str, str], dict]:
        if self.provider == "anthropic":
            return ANTHROPIC_URL, {"x-api-key": self._key, "anthropic-version": "2023-06-01"}, {
                "model": self.model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        return OPENAI_URL, {"Authorization": f"Bearer {self._key}"}, {
            "model": self.model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

    def _extract(self, data: dict) -> str:
        try:
            if self.provider == "anthropic":
                text = "".join(b.get("text", "") for b in data["content"] if isinstance(b, dict) and b.get("type") == "text")
            else:
                text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, AttributeError):
            raise LLMError("รูปแบบคำตอบจาก LLM ไม่ถูกต้อง") from None
        if not isinstance(text, str) or not text.strip():
            raise LLMError(f"LLM ตอบว่างเปล่า ({self._why_empty(data)})")
        return text.strip()

    def _why_empty(self, data: dict) -> str:
        """เหตุที่ได้ข้อความว่าง ไว้วินิจฉัย: เก็บเฉพาะค่าสั้นๆ ที่ไม่ใช่เนื้อหาคำตอบ (stop_reason ชนิดบล็อก จำนวนโทเคน)"""
        def clean(v: object) -> str:
            return re.sub(r"[^A-Za-z0-9_.\-]", "", str(v))[:40] or "?"
        try:
            if self.provider == "anthropic":
                kinds = ",".join(clean(b.get("type")) for b in data.get("content", []) if isinstance(b, dict)) or "ไม่มีบล็อก"
                out = (data.get("usage") or {}).get("output_tokens")
                return f"stop_reason={clean(data.get('stop_reason'))} blocks={kinds} output_tokens={clean(out)}"
            choice = data["choices"][0]
            return f"finish_reason={clean(choice.get('finish_reason'))}"
        except (KeyError, IndexError, TypeError, AttributeError):
            return "ไม่ทราบเหตุ"

    def complete(self, system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
        url, headers, body = self._request(system, user, max_tokens)
        last: LLMError | None = None
        for _ in range(1 + self.retries):
            try:
                return self._extract(self._post(url, headers, body, self.timeout))
            except LLMError as e:
                last = e
                if not e.retryable:
                    break
        assert last is not None
        raise last


def from_env(env: Mapping[str, str] | None = None, **kw: Any) -> LLMClient | None:
    """สร้างตัวเชื่อมจาก LLM_PROVIDER, LLM_MODEL และคีย์ของผู้ให้บริการ ไม่ครบ = None (ใช้โหมดกฎ)"""
    env = os.environ if env is None else env
    provider = (env.get("LLM_PROVIDER") or "mock").strip().lower()
    if provider == "mock":
        return None
    if provider not in PROVIDERS:
        log.warning("LLM_PROVIDER=%r ไม่รู้จัก ใช้โหมดกฎ", provider)
        return None
    key = (env.get("ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY") or "").strip()
    model = (env.get("LLM_MODEL") or "").strip()
    if not key or not model:
        log.warning("LLM_PROVIDER=%s แต่ยังไม่ตั้งคีย์หรือ LLM_MODEL ใช้โหมดกฎ", provider)
        return None
    return LLMClient(provider, model, key, **kw)
