"""Composite approved face edits onto the unchanged front sprite, and validate RGBA.

Requires Pillow. Build: python scripts/build_mascot_expressions.py --inputs <json>
Validate saved deliverables: python scripts/build_mascot_expressions.py --validate
Input JSON: [{"name": "blink-half", "path": "absolute generated image path"}, ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps/web/src/assets/mascot/front.webp"
OUT = ROOT / "apps/web/src/assets/mascot/expressions-v2"
CANVAS = (420, 540)
BAND_ORIGINAL = (60, 140, 340, 300)
LABELS = {
    "blink-half": "กะพริบตาครึ่งหนึ่ง", "blink-closed": "กะพริบตาปิด",
    "ouch": "ตกใจ / โอ๊ย", "afraid": "ตกใจกลัว", "squint": "หน้าย่น ตาหยี",
    "dizzy": "มึนหัว ตาหมุน", "angry": "โกรธ", "crying": "ร้องไห้",
    "grin": "ยิ้มกว้าง ตาโค้ง", "shy": "หลับตา ยิ้มเขิน",
    "wink-left": "ขยิบตาซ้ายของตัวละคร", "wink-right": "ขยิบตาขวาของตัวละคร",
    "cross-eyed": "ตาเหล่ มองจมูก", "tongue": "แลบลิ้น", "kiss": "จุ๊บปาก",
    "heart-eyes": "ตารูปหัวใจ", "star-eyes": "ตารูปดาว", "yawn": "หาว",
    "pre-sneeze": "ก่อนจาม", "sneeze": "ขณะจาม", "whistle": "เป่าปาก ผิวปาก",
    "neutral": "ตาเฉย ไม่แสดงอารมณ์", "smirk": "แกล้งฉลาด ยิ้มมุมปาก",
}


def reference():
    original = Image.open(SOURCE).convert("RGBA")
    offset = ((CANVAS[0] - original.width) // 2, CANVAS[1] - original.height)
    base = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    base.paste(original, offset)  # No resampling and no alpha multiplication.
    band = tuple(v + offset[i % 2] for i, v in enumerate(BAND_ORIGINAL))
    return original, base, offset, band


def face_mask(size):
    # Preserve silhouette, whiskers, hat, ears and camera. The soft transition is
    # strictly clipped to the requested original-coordinate face rectangle.
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon([
        (96, 174), (141, 174), (272, 174), (311, 174), (329, 193),
        (329, 265), (302, 289), (126, 289), (83, 266), (75, 218),
    ], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(4))
    clip = Image.new("L", size, 0)
    # Original brows touch y=136, outside the editable y=140 boundary. Preserve
    # the entire brow strip to avoid partial/double brows at that strict boundary.
    ImageDraw.Draw(clip).rectangle((60, 166, 339, 299), fill=255)
    return ImageChops.multiply(mask, clip)


def compose(inputs):
    original, base, offset, band = reference()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "faces").mkdir(exist_ok=True)
    base.save(OUT / "front.png")
    base.crop(band).save(OUT / "faces/front.png")
    mask = face_mask(original.size)
    for item in inputs:
        name = item["name"]
        if name not in LABELS:
            raise ValueError(f"Unknown expression: {name}")
        edited = Image.open(item["path"]).convert("RGBA").resize(original.size, Image.Resampling.LANCZOS)
        # Keep original alpha exactly. Only RGB facial detail is taken from edit.
        edited.putalpha(original.getchannel("A"))
        face = Image.composite(edited, original, mask)
        full = base.copy()
        full.paste(face.crop(BAND_ORIGINAL), (band[0], band[1]))
        full.save(OUT / f"{name}.png", optimize=True)
        full.crop(band).save(OUT / "faces" / f"{name}.png", optimize=True)


def inspect(require_complete=False):
    original, base, offset, band = reference()
    saved_base = Image.open(OUT / "front.png").convert("RGBA")
    if saved_base.size != CANVAS or saved_base.tobytes() != base.tobytes():
        raise ValueError("front.png does not match the original padded reference")
    entries = []
    for name, label in LABELS.items():
        path = OUT / f"{name}.png"
        if not path.exists():
            continue
        full = Image.open(path).convert("RGBA")
        if full.size != CANVAS:
            raise ValueError(f"Wrong canvas size: {path}")
        diff = ImageChops.difference(base, full)
        # Include hidden RGB channels as well as alpha in exact byte comparison.
        outside = diff.copy()
        ImageDraw.Draw(outside).rectangle((band[0], band[1], band[2] - 1, band[3] - 1), fill=(0, 0, 0, 0))
        pixels_outside = sum(p != (0, 0, 0, 0) for p in outside.getdata())
        pixels_inside = sum(p != (0, 0, 0, 0) for p in diff.crop(band).getdata())
        crop = Image.open(OUT / "faces" / f"{name}.png").convert("RGBA")
        crop_matches = crop.size == (280, 160) and crop.tobytes() == full.crop(band).tobytes()
        alpha_matches = full.getchannel("A").tobytes() == base.getchannel("A").tobytes()
        if pixels_outside or not crop_matches or not alpha_matches or not pixels_inside:
            raise ValueError(f"Invariant failed: {name}")
        entries.append({"name": name, "expression_th": label, "full": f"{name}.png",
                        "face": f"faces/{name}.png", "outside_changed_pixels": pixels_outside,
                        "inside_changed_pixels": pixels_inside, "alpha_matches": alpha_matches,
                        "crop_matches": crop_matches, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"schema_version": 1, "source": "../front.webp", "source_size": list(original.size),
                "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "canvas_size": list(CANVAS), "source_offset": list(offset),
                "face_band_source_xyxy_exclusive": list(BAND_ORIGINAL),
                "face_band_canvas_xyxy_exclusive": list(band),
                "face_crop_size": [280, 160], "base": "front.png",
                "expected_expression_count": len(LABELS), "actual_expression_count": len(entries),
                "complete": len(entries) == len(LABELS), "expressions": entries}
    manifest_path = OUT / "manifest.json"
    if manifest_path.is_file():
        saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "gaze" in saved_manifest or any(OUT.glob("gaze-*.png")):
            # Rebuilding the legacy expressions must not erase the separate
            # gaze set or silently retain metadata for invalid gaze images.
            from build_mascot_gaze import validate as validate_gaze
            validate_gaze(out=OUT)
            manifest["gaze"] = saved_manifest["gaze"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"expressions": len(entries), "expected": len(LABELS),
                      "complete": manifest["complete"], "outside_changed_pixels": sum(x["outside_changed_pixels"] for x in entries),
                      "alpha_and_crop_checks": "passed"}, ensure_ascii=False))
    if require_complete and not manifest["complete"]:
        raise ValueError(f"Incomplete expression set: {len(entries)}/{len(LABELS)}")
    return entries


def contact_sheet(entries):
    rows = (len(entries) + 3) // 4
    sheet = Image.new("RGB", (840, rows * 298), "#F5F3ED")
    draw = ImageDraw.Draw(sheet)
    for i, entry in enumerate(entries):
        x, y = (i % 4) * 210, (i // 4) * 298
        sprite = Image.open(OUT / entry["full"]).convert("RGBA")
        sprite.thumbnail((210, 270), Image.Resampling.LANCZOS)
        sheet.paste(sprite, (x, y), sprite)
        draw.text((x + 12, y + 274), entry["name"], fill="#22301F")
    sheet.save(OUT / "contact-sheet.jpg", quality=92)


if __name__ == "__main__":
    from mascot_pose_expressions import POSES, compose_pose, validate_all, validate_front, validate_pose

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--pose", choices=["front", *POSES], default=None)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.inputs:
        inputs = json.loads(args.inputs.read_text(encoding="utf-8-sig"))
        if args.pose in POSES:
            print(json.dumps(compose_pose(args.pose, inputs), ensure_ascii=False))
        else:
            compose(inputs)
            entries = inspect(require_complete=args.validate)
            contact_sheet(entries)
    if args.validate:
        if args.pose in POSES:
            print(json.dumps(validate_pose(args.pose), ensure_ascii=False))
        elif args.pose == "front":
            print(json.dumps(validate_front(), ensure_ascii=False))
        else:
            validate_all()
    if not args.inputs and not args.validate:
        parser.error("Pass --inputs or --validate")
