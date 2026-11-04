"""สิทธิ์ผู้ดูแลระบบ: อีเมลใน ADMIN_EMAILS (คั่นด้วยจุลภาค ไม่สนตัวพิมพ์) ไม่ตั้ง = ไม่มีใครเป็นผู้ดูแล"""
from __future__ import annotations

import os


def admin_emails() -> set[str]:
    return {e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "").split(",") if e.strip()}


def is_admin(email: str | None) -> bool:
    return bool(email) and email.strip().lower() in admin_emails()
