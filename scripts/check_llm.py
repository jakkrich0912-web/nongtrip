"""ตรวจว่าตัวเชื่อม LLM ใช้ได้จริงไหม (เรียก 1 ครั้ง ใช้โทเค็นไม่กี่สิบตัว)

    python scripts/check_llm.py

อ่านค่าจาก .env ในโฟลเดอร์โปรเจกต์ (ถ้ามี) และจากตัวแปรสภาพแวดล้อม โดยตัวแปรสภาพแวดล้อมมาก่อน
ตัวแปรที่ใช้: LLM_PROVIDER, LLM_MODEL, คีย์ของผู้ให้บริการ และ LLM_FALLBACK ถ้ามีตัวสำรอง (ดู .env.example)
มีตัวสำรอง: ลองเรียกทุกตัวทีละตัว รหัสออกดูจากตัวหลัก
ไม่พิมพ์คีย์ออกหน้าจอ ไม่ว่ากรณีใด

รหัสออก: 0 = เรียกสำเร็จ, 1 = ตั้งค่าครบแต่เรียกไม่สำเร็จ, 2 = ยังตั้งค่าไม่ครบ (ระบบจะใช้โหมดกฎ)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable, Mapping, MutableMapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.llm import KEY_VAR, PROVIDERS, LLMClient, LLMError, from_env  # noqa: E402


def load_dotenv(path: Path, env: MutableMapping[str, str]) -> bool:
    """อ่าน KEY=VALUE จากไฟล์ .env ใส่ใน env เฉพาะตัวแปรที่ยังไม่มีค่า (ไม่ทับของที่ตั้งไว้แล้ว)"""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k and not env.get(k):
            env[k] = v
    return True


def diagnose(env: Mapping[str, str]) -> list[str]:
    """บอกว่าตัวแปรไหนยังขาด (บอกแค่ชื่อและมี/ไม่มี ไม่บอกค่า)"""
    provider = (env.get("LLM_PROVIDER") or "mock").strip().lower()
    out = [f"LLM_PROVIDER = {provider}"]
    if provider == "mock":
        out.append(f"ตั้ง LLM_PROVIDER เป็น {' / '.join(PROVIDERS)} เพื่อเปิดโหมด LLM")
        return out
    if provider not in PROVIDERS:
        out.append(f"ไม่รู้จักผู้ให้บริการนี้ ใช้ได้: {', '.join(PROVIDERS)}")
        return out
    key_var = KEY_VAR[provider]
    out.append(f"{key_var}: {'ตั้งแล้ว' if (env.get(key_var) or '').strip() else 'ยังไม่ได้ตั้ง'}")
    out.append(f"LLM_MODEL: {'ตั้งแล้ว' if (env.get('LLM_MODEL') or '').strip() else 'ยังไม่ได้ตั้ง'}")
    return out


def main(argv: list[str] | None = None, env: MutableMapping[str, str] | None = None,
         factory: Callable[..., LLMClient | None] = from_env, dotenv: Path | None = ROOT / ".env") -> int:
    env = os.environ if env is None else env
    if dotenv is not None and load_dotenv(dotenv, env):
        print(f"อ่านค่าจาก {dotenv.name}")
    client = factory(env)
    if client is None:
        print("ยังตั้งค่า LLM ไม่ครบ ระบบจะใช้แชตโหมดกฎ")
        for line in diagnose(env):
            print("  " + line)
        return 2
    code = 0
    for i, c in enumerate(getattr(client, "clients", [client])):
        print(f"{'ตัวหลัก' if i == 0 else f'ตัวสำรอง {i}'}: ผู้ให้บริการ {c.provider} รุ่น {c.model}")
        start = time.monotonic()
        try:
            # เพดาน 200 โทเคน: รุ่นที่คิดก่อนตอบ (thinking) ใช้โทเคนคิดด้วย เพดานต่ำไปจะได้ข้อความว่าง
            reply = c.complete("ตอบสั้นที่สุด", "ตอบคำว่า พร้อม เพียงคำเดียว", max_tokens=200)
        except LLMError as e:
            print(f"  เรียกไม่สำเร็จ: {e}")
            print("  ตรวจคีย์ ชื่อรุ่น เครดิต และการเชื่อมต่ออินเทอร์เน็ต")
            if i == 0:
                code = 1
            continue
        ms = int((time.monotonic() - start) * 1000)
        print(f"  สำเร็จ ใช้เวลา {ms} ms ตอบกลับ {len(reply)} ตัวอักษร")
    return code

if __name__ == "__main__":
    raise SystemExit(main())
