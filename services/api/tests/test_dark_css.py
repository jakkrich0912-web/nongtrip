"""apps/web/src/dark.css สร้างจาก CSS ของหน้าเว็บ ต้องตรงกับ CSS ปัจจุบันเสมอ (แก้ CSS แล้วลืมรันสคริปต์ = เทสต์ตก)"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("build_dark_css", ROOT / "scripts" / "build_dark_css.py")
dark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dark)


def test_dark_css_is_up_to_date():
    assert (ROOT / "apps" / "web" / "src" / "dark.css").read_text(encoding="utf-8") == dark.build(), \
        "รัน python scripts/build_dark_css.py แล้ว commit dark.css"


def test_light_backgrounds_become_dark_and_dark_text_becomes_light():
    assert dark.map_value("background", "#fffefb") not in (None, "#fffefb")
    bg = dark.map_value("background", "#ffffff")
    assert bg.startswith("#") and int(bg[1:3], 16) < 60
    text = dark.map_value("color", "#22301f")
    assert int(text[1:3], 16) > 180


def test_bright_and_brand_colors_are_kept():
    assert dark.map_value("background", "#3d6a4b") is None      # ปุ่มเขียว
    assert dark.map_value("background", "#f9a620") is None      # ปุ่มเหลืองอำพัน
    assert dark.map_value("color", "#ffffff") is None           # ตัวอักษรขาวบนปุ่ม
    assert dark.map_value("border-radius", "12px") is None


def test_rules_are_scoped_without_raising_specificity():
    out = dark._rules(".btn { background:#fff; } .btn.ghost { background:transparent; }")
    assert out == [":where(html[data-theme=dark]) .btn { background:#131313; }"]
