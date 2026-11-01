"""รหัสผ่านและเซสชัน ใช้เฉพาะไลบรารีมาตรฐาน

- รหัสผ่านแฮชด้วย scrypt พร้อม salt สุ่มต่อผู้ใช้ ไม่เก็บรหัสผ่านจริง
- เซสชันเป็นคุกกี้ที่เซ็นด้วย HMAC-SHA256 (SESSION_SECRET) มีวันหมดอายุ ไม่มีข้อมูลอื่นนอกจากรหัสผู้ใช้
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
SESSION_DAYS = 7
MIN_PASSWORD = 8
MAX_PASSWORD = 200
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(EMAIL_RE.match(email))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p),
                            dklen=len(hash_hex) // 2)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ใช้เทียบเวลาให้เท่ากันเมื่อไม่พบอีเมล (กันเดาว่าอีเมลไหนมีบัญชี)
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def burn_verify(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def resolve_secret(explicit: str | None = None) -> str:
    """ไม่ได้ตั้ง SESSION_SECRET: สุ่มต่อการรัน (เซสชันหายเมื่อรีสตาร์ท) ดีกว่าใช้ค่าตายตัวที่เดาได้"""
    return explicit or os.environ.get("SESSION_SECRET") or secrets.token_hex(32)


def make_token(user_id: int, secret: str, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + SESSION_DAYS * 86400)
    payload = f"{user_id}.{exp}"
    return f"{payload}.{_sign(payload, secret)}"


def read_token(token: str | None, secret: str, now: float | None = None) -> int | None:
    """คืนรหัสผู้ใช้ถ้าโทเคนถูกต้องและยังไม่หมดอายุ ไม่งั้น None"""
    if not token:
        return None
    try:
        uid, exp, sig = token.split(".")
        if not hmac.compare_digest(_sign(f"{uid}.{exp}", secret), sig):
            return None
        if int(exp) < (now if now is not None else time.time()):
            return None
        return int(uid)
    except ValueError:
        return None


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


class LoginThrottle:
    """จำกัดการเดารหัสผ่าน: ผิดครบ max_fails ครั้งภายใน window วินาที ต่ออีเมล แล้วรอก่อน"""

    def __init__(self, max_fails: int = 5, window: int = 300):
        self.max_fails, self.window = max_fails, window
        self._fails: dict[str, list[float]] = {}

    def _recent(self, key: str, now: float) -> list[float]:
        xs = [t for t in self._fails.get(key, []) if now - t < self.window]
        if xs:
            self._fails[key] = xs
        else:
            self._fails.pop(key, None)
        return xs

    def blocked(self, key: str, now: float | None = None) -> bool:
        return len(self._recent(key, now if now is not None else time.time())) >= self.max_fails

    def fail(self, key: str, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self._recent(key, now)
        self._fails.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)
