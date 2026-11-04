"""สร้าง apps/web/src/dark.css (โหมดมืด) จากไฟล์ CSS ของหน้าเว็บ

    python scripts/build_dark_css.py           เขียนไฟล์ใหม่
    python scripts/build_dark_css.py --check   ตรวจว่าไฟล์ล่าสุดแล้ว (รหัสออก 1 = ต้องรันสร้างใหม่)

หลักการ: ไม่แก้ไฟล์ CSS เดิม อ่านทุกกฎที่มีสีเขียนตายตัว แล้วสร้างกฎคู่กันใต้ html[data-theme=dark]
- พื้นหลัง/เส้นขอบสีอ่อน -> สีเข้ม (คงเฉดสีเดิม ลดความสด) สีเข้มอยู่แล้ว (ปุ่มเขียว) คงไว้
- สีตัวอักษรเข้ม -> สีอ่อน สีอ่อนอยู่แล้ว (ตัวอักษรขาวบนปุ่ม) คงไว้
- ตัวแปรสีหลักใน :root ตั้งค่าโหมดมืดไว้ในส่วนหัวของไฟล์ที่สร้าง
แก้ CSS เมื่อไรให้รันสคริปต์นี้ใหม่ (มีเทสต์ตรวจว่าไฟล์ตรงกับ CSS ปัจจุบัน)
ใช้ไลบรารีมาตรฐานเท่านั้น
"""
from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "web" / "src"
FILES = ["styles.css", "landing.css", "auth-v2.css", "pages/chat-v2.css", "pages/chat-gpt.css", "pages/info.css", "components/companion.css"]
OUT = SRC / "dark.css"
PREFIX = "html[data-theme=dark]"
# ใช้ :where() ครอบ ไม่เพิ่มความเจาะจงของตัวเลือก กฎโหมดมืดจึงแทนกฎเดิมแบบตัวต่อตัว ไม่ไปชนะกฎที่เจาะจงกว่า (เช่น .btn.ghost)
SCOPE = f":where({PREFIX})"

HEADER = f"""/* สร้างอัตโนมัติด้วย scripts/build_dark_css.py ห้ามแก้ด้วยมือ (แก้ CSS ต้นทางแล้วรันสคริปต์ใหม่) */
{PREFIX} {{
  color-scheme: dark;
  --rice:#141a14; --ink:#e3eadf; --mist:#2c362a; --muted:#a8b4a2;
  --glass:rgba(26,33,26,.82); --glass-line:1px solid rgba(140,199,154,.16);
  --soft:0 1px 2px rgba(0,0,0,.3), 0 18px 44px rgba(0,0,0,.45);
  --nt-cream:#121712; --nt-ink:#e3eadf; --nt-muted:#a8b4a2; --nt-line:#2f3a2c; --nt-sage:#25301f;
}}
{PREFIX} body {{ background:#121712; color:#e3eadf; }}
{PREFIX} .leaflet-tile-pane {{ filter:brightness(.78) contrast(1.05) saturate(.85); }}
{PREFIX} .leaflet-container {{ background:#1b221b; }}
{PREFIX} .leaflet-bar a, {PREFIX} .leaflet-control-attribution {{ background:#1d251d; color:#cfd9ca; border-color:#33402f; }}
{PREFIX} .leaflet-control-attribution a {{ color:#8cc79a; }}
{PREFIX} .leaflet-popup-content-wrapper, {PREFIX} .leaflet-popup-tip {{ background:#1d251d; color:#e3eadf; }}
{PREFIX} input, {PREFIX} textarea, {PREFIX} select {{ color:#e3eadf; }}
{PREFIX} input::placeholder, {PREFIX} textarea::placeholder {{ color:#7f8c7a; }}
"""

TEXT_PROPS = {"color", "caret-color", "fill", "stroke", "text-decoration-color", "-webkit-text-fill-color", "column-rule-color"}
LINE_PROPS = ("border", "outline")
BG_PROPS = ("background", "box-shadow", "text-shadow")
GREEN_VARS = ("--nt-green", "--lagoon", "--lagoon-2")
LIGHT_GREEN = "#8cc79a"

HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+%?)\s*)?\)", re.I)
NAMED = re.compile(r"(?<![\w-])(white|black)(?![\w-])", re.I)
VAR_GREEN = re.compile(r"var\((" + "|".join(re.escape(v) for v in GREEN_VARS) + r")\)")


def _rgb(hexs: str) -> tuple[float, float, float, float]:
    h = hexs
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r, g, b, a


def _fmt(r: float, g: float, b: float, a: float) -> str:
    rr, gg, bb = (max(0, min(255, round(x * 255))) for x in (r, g, b))
    if a >= 0.999:
        return f"#{rr:02x}{gg:02x}{bb:02x}"
    return f"rgba({rr},{gg},{bb},{round(a, 3):g})"


def _map(r: float, g: float, b: float, a: float, kind: str) -> tuple[float, float, float, float]:
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if kind == "text":
        if l >= 0.6:
            return r, g, b, a                       # ตัวอักษรสีอ่อนอยู่แล้ว (เช่น ขาวบนปุ่มเขียว)
        l2 = min(0.92, 0.94 - l * 0.45)
        return (*colorsys.hls_to_rgb(h, l2, min(s, 0.45)), a)
    if kind == "line":
        if l < 0.6:
            return r, g, b, a
        l2 = 0.17 + (1 - l) * 0.55
        return (*colorsys.hls_to_rgb(h, l2, s * 0.35), a)
    if kind == "shadow":
        return 0.0, 0.0, 0.0, min(1.0, a * 2.2)
    # พื้นหลัง: เปลี่ยนเฉพาะพื้นสีอ่อนแบบกลาง ๆ (ขาว ครีม เขียวอ่อน) สีสดอย่างปุ่มเหลืองอำพันหรือปุ่มเขียวคงไว้
    if l < 0.6 or (l < 0.8 and s > 0.45):
        return r, g, b, a
    l2 = 0.075 + (1 - l) * 0.75
    return (*colorsys.hls_to_rgb(h, l2, s * 0.4), a)


def _kind(prop: str) -> str | None:
    p = prop.lower()
    if p in TEXT_PROPS:
        return "text"
    if p.startswith(LINE_PROPS) and "radius" not in p and "width" not in p and "style" not in p:
        return "line"
    if p in ("box-shadow", "text-shadow", "filter", "drop-shadow"):
        return "shadow"
    if p.startswith(BG_PROPS) or p in ("accent-color",):
        return "bg"
    return None


def map_value(prop: str, value: str) -> str | None:
    """คืนค่าใหม่สำหรับโหมดมืด หรือ None ถ้าไม่ต้องเปลี่ยน"""
    kind = _kind(prop)
    if kind is None:
        return None
    out = value

    def hex_sub(m):
        return _fmt(*_map(*_rgb(m.group(1)), kind))

    def rgb_sub(m):
        r, g, b = (float(m.group(i)) / 255 for i in (1, 2, 3))
        a = m.group(4)
        a = (float(a[:-1]) / 100 if a.endswith("%") else float(a)) if a else 1.0
        return _fmt(*_map(r, g, b, a, kind))

    def named_sub(m):
        rgb = (1.0, 1.0, 1.0) if m.group(1).lower() == "white" else (0.0, 0.0, 0.0)
        return _fmt(*_map(*rgb, 1.0, kind))

    if "url(" in out:
        return None
    out = HEX.sub(hex_sub, out)
    out = RGB.sub(rgb_sub, out)
    out = NAMED.sub(named_sub, out)
    if kind == "text":
        out = VAR_GREEN.sub(LIGHT_GREEN, out)
    return out if out != value else None


# ---------- ตัวอ่าน CSS อย่างง่าย (พอสำหรับไฟล์ของโปรเจกต์นี้) ----------
COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _blocks(css: str):
    """แยกเป็น (prelude, body) ระดับบนสุด รองรับปีกกาซ้อน"""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            c = css[k]
            if c in "\"'":
                q = c
                k += 1
                while k < n and css[k] != q:
                    k += 2 if css[k] == "\\" else 1
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            k += 1
        yield prelude, css[j + 1:k - 1]
        i = k


def _decls(body: str):
    for part in re.split(r";(?![^()]*\))", body):
        if ":" in part:
            prop, val = part.split(":", 1)
            prop = prop.strip()
            if prop:
                yield prop, val.strip()


def _scope(selector: str) -> str:
    parts = []
    for sel in re.split(r",(?![^()]*\))", selector):
        sel = sel.strip()
        if not sel:
            continue
        if sel.startswith(":root"):
            sel = SCOPE + sel[5:]
        elif sel.startswith("html"):
            sel = SCOPE + sel[4:]
        else:
            sel = f"{SCOPE} {sel}"
        parts.append(sel)
    return ", ".join(parts)


INK_VAR = re.compile(r"var\(--(?:nt-)?ink\)")


def _bright_bg(value: str) -> bool:
    """พื้นสีสด (เหลืองอำพัน) ที่โหมดมืดคงไว้ ตัวอักษรบนพื้นนี้ต้องเข้มเหมือนเดิม"""
    if re.search(r"var\(--(?:nt-amber|mango)\)", value):
        return True
    for m in HEX.finditer(value):
        r, g, b, _ = _rgb(m.group(1))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if 0.45 <= l < 0.85 and s > 0.6 and 0.05 < h < 0.2:
            return True
    return False


def _rules(css: str) -> list[str]:
    out = []
    for prelude, body in _blocks(css):
        if prelude.startswith("@"):
            if prelude.startswith(("@media", "@supports")):
                inner = _rules(body)
                if inner:
                    out.append(prelude + " {\n" + "\n".join("  " + r for r in inner) + "\n}")
            continue                                 # @keyframes @font-face ฯลฯ ไม่ยุ่ง
        changed = []
        decls = list(_decls(body))
        bright = any(p.startswith("background") and _bright_bg(v) for p, v in decls)
        for prop, val in decls:
            if prop.startswith("--"):
                continue                             # ตัวแปรหลักตั้งไว้ใน HEADER แล้ว
            if bright and prop == "color":
                if INK_VAR.search(val):              # ตัวอักษรสีหมึกบนปุ่มเหลือง: คงสีเข้ม (ตัวแปร --ink เปลี่ยนเป็นสีอ่อนในโหมดมืด)
                    changed.append("color:#22301f")
                continue
            new = map_value(prop, val)
            if new is not None:
                changed.append(f"{prop}:{new}")
        if changed:
            out.append(f"{_scope(prelude)} {{ {'; '.join(changed)}; }}")
    return out


def build() -> str:
    parts = [HEADER]
    for name in FILES:
        css = COMMENT.sub("", (SRC / name).read_text(encoding="utf-8"))
        rules = _rules(css)
        if rules:
            parts.append(f"/* จาก {name} */\n" + "\n".join(rules) + "\n")
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    text = build()
    if "--check" in argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("dark.css ล่าสุดแล้ว" if ok else "dark.css ไม่ตรงกับ CSS ปัจจุบัน รัน python scripts/build_dark_css.py")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"เขียน {OUT.relative_to(ROOT)} ({text.count(chr(10))} บรรทัด)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
