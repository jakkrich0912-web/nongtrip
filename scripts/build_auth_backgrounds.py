"""Resize approved authentication backgrounds and validate the exported assets.

Requires Pillow. Build:
  python scripts/build_auth_backgrounds.py --inputs ../nongtrip-design/motion-inputs/backgrounds
Validate existing exports:
  python scripts/build_auth_backgrounds.py --validate

Only technical resizing and compression are performed. Source artwork remains
external to runtime assets; backgrounds contain no baked-in mascot.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps/web/src/assets/mascot/auth-backgrounds"
NAMES = ("login", "signup")
VARIANTS = {"desktop": (1080, 1440), "mobile": (600, 800)}
PALETTE = ["#22301f", "#3d6a4b", "#f5f3ed", "#f9a620"]
QUALITY = 82
MAX_FILE_BYTES = 250_000
SHEET_SIZE = (720, 510)
COPY_REGION = {
    "coordinate_system": "normalized",
    "left": 0.20,
    "top": 0.0,
    "right": 0.80,
    "bottom": 0.52,
    "text_color": "#ffffff",
    "description": "Upper 52%, with side insets to keep white copy clear of foliage.",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def filename(name, variant):
    return f"{name}{'-mobile' if variant == 'mobile' else ''}.webp"


def file_record(path, size, format_name):
    return {
        "file": path.name,
        "width": size[0],
        "height": size[1],
        "format": format_name,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def read_source(path):
    with Image.open(path) as opened:
        if opened.format != "PNG":
            raise ValueError(f"{path.name}: expected approved PNG artwork")
        image = ImageOps.exif_transpose(opened).convert("RGB")
    if image.width * 4 != image.height * 3:
        raise ValueError(f"{path.name}: expected 3:4 artwork; refusing to crop")
    return image


def build(inputs):
    # Check both sources before creating any output.
    sources = {name: read_source(inputs / f"{name}.png") for name in NAMES}
    OUT.mkdir(parents=True, exist_ok=True)
    entries = []
    desktops = {}
    for name, source in sources.items():
        source_path = inputs / f"{name}.png"
        for variant, size in VARIANTS.items():
            resized = source.resize(size, Image.Resampling.LANCZOS)
            path = OUT / filename(name, variant)
            resized.save(path, format="WEBP", quality=QUALITY, method=6)
            entry = file_record(path, size, "WEBP")
            entry.update({
                "name": name,
                "variant": variant,
                "webp_quality": QUALITY,
                "source_file": source_path.name,
                "source_sha256": digest(source_path),
                "source_size": list(source.size),
            })
            entries.append(entry)
            if variant == "desktop":
                with Image.open(path) as decoded:
                    desktops[name] = decoded.convert("RGB")

    sheet = Image.new("RGB", SHEET_SIZE, PALETTE[2])
    draw = ImageDraw.Draw(sheet)
    for index, name in enumerate(NAMES):
        thumbnail = desktops[name].resize((360, 480), Image.Resampling.LANCZOS)
        sheet.paste(thumbnail, (index * 360, 0))
        draw.text((index * 360 + 12, 490), name, fill=PALETTE[0])
    sheet_path = OUT / "contact-sheet.jpg"
    sheet.save(sheet_path, format="JPEG", quality=82, optimize=True)

    manifest = {
        "schema_version": 1,
        "name": "auth-backgrounds",
        "palette": PALETTE,
        "safe_copy_region": COPY_REGION,
        "mascot_baked_in": False,
        "framing": "3:4 source aspect ratio preserved without cropping",
        "budget_scope": "Authentication backgrounds are separate from the motion asset budget.",
        "webp_quality": QUALITY,
        "max_file_bytes": MAX_FILE_BYTES,
        "runtime_bytes": sum(entry["bytes"] for entry in entries),
        "assets": entries,
        "contact_sheet": file_record(sheet_path, SHEET_SIZE, "JPEG"),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return validate(inputs)


def check_record(entry, expected_name, expected_size, expected_format):
    if entry["file"] != expected_name:
        raise ValueError(f"Unexpected manifest filename: {entry['file']}")
    path = OUT / expected_name
    with Image.open(path) as image:
        image.load()
        if image.format != expected_format or image.size != expected_size:
            raise ValueError(f"{expected_name}: wrong image format or dimensions")
        if image.mode != "RGB":
            raise ValueError(f"{expected_name}: expected opaque RGB image")
    if (entry["width"], entry["height"]) != expected_size:
        raise ValueError(f"{expected_name}: incorrect manifest dimensions")
    if entry["format"] != expected_format:
        raise ValueError(f"{expected_name}: incorrect manifest format")
    size = path.stat().st_size
    if size != entry["bytes"] or digest(path) != entry["sha256"]:
        raise ValueError(f"{expected_name}: byte count or SHA-256 mismatch")
    if size > MAX_FILE_BYTES:
        raise ValueError(f"{expected_name}: exceeds {MAX_FILE_BYTES:,} bytes")
    return size


def validate(inputs=None):
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1 or manifest["palette"] != PALETTE:
        raise ValueError("Unexpected manifest version or palette")
    if manifest["safe_copy_region"] != COPY_REGION or manifest["mascot_baked_in"] is not False:
        raise ValueError("Incorrect copy region or mascot metadata")
    if manifest["webp_quality"] != QUALITY or manifest["max_file_bytes"] != MAX_FILE_BYTES:
        raise ValueError("Incorrect compression metadata")
    expected = {
        filename(name, variant): (name, variant, size)
        for name in NAMES for variant, size in VARIANTS.items()
    }
    entries = manifest["assets"]
    if len(entries) != len(expected) or {entry["file"] for entry in entries} != set(expected):
        raise ValueError("Manifest must list exactly four background exports")
    runtime_bytes = 0
    for entry in entries:
        name, variant, size = expected[entry["file"]]
        if entry["name"] != name or entry["variant"] != variant or entry["webp_quality"] != QUALITY:
            raise ValueError(f"{entry['file']}: incorrect variant metadata")
        runtime_bytes += check_record(entry, filename(name, variant), size, "WEBP")
        if inputs is not None:
            source_path = inputs / f"{name}.png"
            source = read_source(source_path)
            if entry["source_file"] != source_path.name or entry["source_size"] != list(source.size):
                raise ValueError(f"{entry['file']}: source metadata mismatch")
            if entry["source_sha256"] != digest(source_path):
                raise ValueError(f"{entry['file']}: approved source SHA-256 mismatch")
    if runtime_bytes != manifest["runtime_bytes"]:
        raise ValueError("Incorrect total background byte count")
    preview_bytes = check_record(
        manifest["contact_sheet"], "contact-sheet.jpg", SHEET_SIZE, "JPEG"
    )
    expected_files = set(expected) | {"manifest.json", "contact-sheet.jpg"}
    if {path.name for path in OUT.iterdir() if path.is_file()} != expected_files:
        raise ValueError("Unexpected or missing files in auth-backgrounds")
    return {
        "validated": True,
        "background_count": len(entries),
        "runtime_bytes": runtime_bytes,
        "preview_bytes": preview_bytes,
        "assets": [{"file": entry["file"], "bytes": entry["bytes"]} for entry in entries],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, help="Folder containing approved login.png and signup.png")
    parser.add_argument("--validate", action="store_true", help="Validate existing exports without rebuilding")
    args = parser.parse_args()
    if not args.validate and args.inputs is None:
        parser.error("--inputs is required when building")
    try:
        result = validate(args.inputs) if args.validate else build(args.inputs)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(1, f"Background asset check failed: {exc}\n")
    print(json.dumps(result, indent=2))
