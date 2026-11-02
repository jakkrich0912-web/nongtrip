"""ฐานข้อมูลผู้ใช้ ประวัติ สถานที่โปรด และแชต (SQLite มาตรฐาน)

เก็บเฉพาะข้อมูลของผู้ที่ล็อกอิน ไม่มีฟิลด์ราคา คะแนน หรือรีวิวในตารางใดเลย
เปิดการเชื่อมต่อใหม่ทุกครั้งที่เรียก (ปลอดภัยกับเธรดของ FastAPI) และสร้างตารางเองเมื่อยังไม่มี
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

MAX_SEARCHES = 100
MAX_FAVORITES = 500
GOOGLE_PW_HASH = "google"  # ไม่ใช่รูปแบบ scrypt$... จึงล็อกอินด้วยรหัสผ่านไม่ได้

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  pw_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_searches_user ON searches(user_id, id);
CREATE TABLE IF NOT EXISTS favorites (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  place_id TEXT NOT NULL,
  name_th TEXT NOT NULL, name_en TEXT, kind TEXT NOT NULL, subtype TEXT,
  lat REAL NOT NULL, lon REAL NOT NULL, source TEXT NOT NULL, province TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, place_id)
);
CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id, updated_at);
CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EmailTaken(Exception):
    pass


class Store:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = str(path or os.environ.get("DB_PATH") or "data/nongtrip.db")
        self._ready = False
        self._lock = threading.Lock()

    @staticmethod
    def _migrate(c: sqlite3.Connection) -> None:
        """เพิ่มคอลัมน์ที่มาทีหลังให้ฐานข้อมูลเดิม (ไม่ลบหรือแก้ข้อมูลเก่า)"""
        cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        if "google_sub" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google ON users(google_sub)")
        c.commit()

    @contextmanager
    def _db(self):
        with self._lock:
            if not self._ready:
                if self.path != ":memory:":
                    Path(self.path).parent.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(self.path, timeout=10)) as c:
                    c.executescript(SCHEMA)
                    self._migrate(c)
                self._ready = True
        with closing(sqlite3.connect(self.path, timeout=10)) as c:
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys = ON")
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise

    # ---- ผู้ใช้ ----
    def create_user(self, email: str, pw_hash: str) -> dict:
        with self._db() as c:
            try:
                cur = c.execute("INSERT INTO users(email, pw_hash, created_at) VALUES (?,?,?)",
                                (email, pw_hash, now_iso()))
            except sqlite3.IntegrityError as e:
                raise EmailTaken(email) from e
            return {"id": cur.lastrowid, "email": email}

    def create_google_user(self, email: str, google_sub: str) -> dict:
        """ผู้ใช้ที่เข้าด้วย Google ไม่มีรหัสผ่าน: pw_hash เป็นค่าที่ verify_password ไม่มีวันผ่าน"""
        with self._db() as c:
            try:
                cur = c.execute("INSERT INTO users(email, pw_hash, created_at, google_sub) VALUES (?,?,?,?)",
                                (email, GOOGLE_PW_HASH, now_iso(), google_sub))
            except sqlite3.IntegrityError as e:
                raise EmailTaken(email) from e
            return {"id": cur.lastrowid, "email": email}

    def user_by_google_sub(self, google_sub: str) -> dict | None:
        with self._db() as c:
            r = c.execute("SELECT id, email FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
            return dict(r) if r else None

    def user_by_email(self, email: str) -> dict | None:
        with self._db() as c:
            r = c.execute("SELECT id, email, pw_hash FROM users WHERE email = ?", (email,)).fetchone()
            return dict(r) if r else None

    def user_by_id(self, user_id: int) -> dict | None:
        with self._db() as c:
            r = c.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(r) if r else None

    # ---- ประวัติที่พักที่เคยค้น ----
    def add_search(self, user_id: int, name: str, lat: float, lon: float) -> dict:
        """ที่พักเดิม (ชื่อและพิกัดเท่าเดิม) ถูกยกขึ้นบนสุดแทนการเพิ่มซ้ำ เก็บไม่เกิน MAX_SEARCHES"""
        with self._db() as c:
            c.execute("DELETE FROM searches WHERE user_id = ? AND name = ? AND ROUND(lat, 5) = ROUND(?, 5) "
                      "AND ROUND(lon, 5) = ROUND(?, 5)", (user_id, name, lat, lon))
            cur = c.execute("INSERT INTO searches(user_id, name, lat, lon, created_at) VALUES (?,?,?,?,?)",
                            (user_id, name, lat, lon, now_iso()))
            c.execute("DELETE FROM searches WHERE user_id = ? AND id NOT IN "
                      "(SELECT id FROM searches WHERE user_id = ? ORDER BY id DESC LIMIT ?)",
                      (user_id, user_id, MAX_SEARCHES))
            r = c.execute("SELECT id, name, lat, lon, created_at FROM searches WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(r)

    def list_searches(self, user_id: int) -> list[dict]:
        with self._db() as c:
            rows = c.execute("SELECT id, name, lat, lon, created_at FROM searches WHERE user_id = ? "
                             "ORDER BY id DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def delete_search(self, user_id: int, search_id: int) -> bool:
        with self._db() as c:
            return c.execute("DELETE FROM searches WHERE user_id = ? AND id = ?", (user_id, search_id)).rowcount > 0

    def delete_all_searches(self, user_id: int) -> int:
        with self._db() as c:
            return c.execute("DELETE FROM searches WHERE user_id = ?", (user_id,)).rowcount

    # ---- สถานที่โปรด ----
    def add_favorite(self, user_id: int, p: dict) -> tuple[dict, bool]:
        """คืน (รายการ, สร้างใหม่หรือไม่) บันทึกซ้ำได้โดยไม่เกิดรายการซ้ำ"""
        with self._db() as c:
            old = c.execute("SELECT 1 FROM favorites WHERE user_id = ? AND place_id = ?",
                            (user_id, p["place_id"])).fetchone()
            if not old:
                n = c.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)).fetchone()[0]
                if n >= MAX_FAVORITES:
                    raise OverflowError("สถานที่โปรดเต็มแล้ว")
                c.execute("INSERT INTO favorites(user_id, place_id, name_th, name_en, kind, subtype, lat, lon, "
                          "source, province, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (user_id, p["place_id"], p["name_th"], p.get("name_en"), p["kind"], p.get("subtype"),
                           p["lat"], p["lon"], p["source"], p.get("province"), now_iso()))
            r = c.execute("SELECT * FROM favorites WHERE user_id = ? AND place_id = ?",
                          (user_id, p["place_id"])).fetchone()
            return dict(r), old is None

    def list_favorites(self, user_id: int) -> list[dict]:
        with self._db() as c:
            rows = c.execute("SELECT * FROM favorites WHERE user_id = ? ORDER BY created_at DESC, rowid DESC",
                             (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def delete_favorite(self, user_id: int, place_id: str) -> bool:
        with self._db() as c:
            return c.execute("DELETE FROM favorites WHERE user_id = ? AND place_id = ?",
                             (user_id, place_id)).rowcount > 0

    def delete_all_favorites(self, user_id: int) -> int:
        with self._db() as c:
            return c.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,)).rowcount

    # ---- แชต (หน้าแชตจะเรียกสร้างและเพิ่มข้อความ ตอนนี้เปิดให้อ่านและลบ) ----
    def create_chat(self, user_id: int, title: str) -> int:
        with self._db() as c:
            t = now_iso()
            return c.execute("INSERT INTO chats(user_id, title, created_at, updated_at) VALUES (?,?,?,?)",
                             (user_id, title[:80] or "แชตใหม่", t, t)).lastrowid

    def add_message(self, user_id: int, chat_id: int, role: str, content: str) -> bool:
        with self._db() as c:
            if not c.execute("SELECT 1 FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)).fetchone():
                return False
            t = now_iso()
            c.execute("INSERT INTO chat_messages(chat_id, role, content, created_at) VALUES (?,?,?,?)",
                      (chat_id, role, content, t))
            c.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (t, chat_id))
            return True

    def list_chats(self, user_id: int) -> list[dict]:
        with self._db() as c:
            rows = c.execute(
                "SELECT ch.id, ch.title, ch.created_at, ch.updated_at, COUNT(m.id) AS message_count "
                "FROM chats ch LEFT JOIN chat_messages m ON m.chat_id = ch.id WHERE ch.user_id = ? "
                "GROUP BY ch.id ORDER BY ch.updated_at DESC, ch.id DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_chat(self, user_id: int, chat_id: int) -> dict | None:
        with self._db() as c:
            ch = c.execute("SELECT id, title, created_at, updated_at FROM chats WHERE id = ? AND user_id = ?",
                           (chat_id, user_id)).fetchone()
            if not ch:
                return None
            msgs = c.execute("SELECT role, content, created_at FROM chat_messages WHERE chat_id = ? ORDER BY id",
                             (chat_id,)).fetchall()
            return {**dict(ch), "messages": [dict(m) for m in msgs]}

    def delete_chat(self, user_id: int, chat_id: int) -> bool:
        with self._db() as c:
            return c.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)).rowcount > 0

    def delete_all_chats(self, user_id: int) -> int:
        """ลบแชตทั้งหมดของผู้ใช้ (ข้อความในแชตถูกลบตามด้วย ON DELETE CASCADE)"""
        with self._db() as c:
            return c.execute("DELETE FROM chats WHERE user_id = ?", (user_id,)).rowcount

    # ---- ลบบัญชี ----
    def delete_user(self, user_id: int) -> bool:
        """ลบผู้ใช้และข้อมูลทั้งหมดของเขา (ที่พักที่ค้น สถานที่โปรด แชตและข้อความ) ย้อนกลับไม่ได้"""
        with self._db() as c:
            return c.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount > 0
