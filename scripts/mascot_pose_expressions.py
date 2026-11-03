"""Build and validate pose-specific full-frame expression assets.

Original pose pixels are never resized. Only generated edit inputs are normalized;
all compositing is clipped to the independently measured mask for that expression.
Validation is read-only and checks the saved manifest instead of repairing it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path("apps/web/src/assets/mascot")
OUTPUT = ASSETS / "expressions-v2"
MAX_FILE_BYTES = 5_000_000
LABELS = {"blink-half": "ตาปิดครึ่ง", "blink-closed": "ตาปิด", "grin": "ยิ้มกว้าง ตาโค้ง"}

# Coordinates are measured on each original pose, not copied from front.
POSES = {
    "wave": {
        "source_size": [400, 517], "band": [100, 112, 328, 260],
        "masks": {name: {"polygons": [
            [[116,125],[171,116],[195,142],[184,190],[140,199],[113,172]],
            [[259,157],[306,161],[325,184],[320,224],[278,238],[253,211]],
        ] + ([[[190,181],[237,189],[253,216],[239,244],[204,252],[183,232]]] if name == "grin" else []),
            "feather_px": 3} for name in ("blink-half", "blink-closed", "grin")},
    },
    "think": {
        "source_size": [400, 499], "band": [48, 126, 267, 250],
        "masks": {name: {"polygons": [
            [[62,139],[102,129],[128,148],[125,182],[104,201],[66,194],[57,169]],
            [[185,162],[226,164],[253,187],[249,221],[220,234],[183,219],[176,191]],
        ] + ([[[122,185],[169,194],[181,221],[160,244],[125,234],[117,210]]] if name == "grin" else []),
            "feather_px": 3} for name in ("blink-half", "blink-closed", "grin")},
    },
    "happy": {
        "source_size": [397, 517], "band": [98, 145, 312, 230],
        "masks": {name: {"polygons": [
            [[103,151],[155,148],[181,168],[181,199],[106,193]],
            [[231,170],[281,175],[308,194],[306,224],[234,217]],
        ], "feather_px": 3} for name in ("blink-half", "blink-closed")},
    },
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(pose, root=ROOT):
    spec = POSES[pose]
    source = root / ASSETS / f"{pose}.webp"
    original = Image.open(source).convert("RGBA")
    if list(original.size) != spec["source_size"]:
        raise ValueError(f"{pose}: original dimensions changed; remeasure face geometry")
    if not spec["band"] or not spec["masks"]:
        raise ValueError(f"{pose}: face geometry is not configured")
    width, height = original.size
    band = tuple(spec["band"])
    if not (0 <= band[0] < band[2] <= width and 0 <= band[1] < band[3] <= height):
        raise ValueError(f"{pose}: invalid original face band")
    canvas = (width + 20, height + 20)
    offset = (10, 20)
    base = Image.new("RGBA", canvas, (0, 0, 0, 0))
    base.paste(original, offset)
    mapped = tuple(value + offset[index % 2] for index, value in enumerate(band))
    return original, base, offset, mapped


def expression_mask(pose, name, size):
    spec = POSES[pose]
    edit = spec["masks"][name]
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for polygon in edit["polygons"]:
        draw.polygon([tuple(point) for point in polygon], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(edit["feather_px"]))
    band = spec["band"]
    clip = Image.new("L", size, 0)
    ImageDraw.Draw(clip).rectangle((band[0], band[1], band[2] - 1, band[3] - 1), fill=255)
    return ImageChops.multiply(mask, clip)


def png(path, size):
    if not path.is_file():
        raise ValueError(f"Missing required image: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds 5 MB: {path}")
    with Image.open(path) as opened:
        if opened.format != "PNG" or opened.mode != "RGBA" or opened.size != size:
            raise ValueError(f"Expected PNG RGBA {size}: {path}")
        return opened.copy()


def check_frames(out, base, band, labels):
    crop_size = (band[2] - band[0], band[3] - band[1])
    entries = []
    for name, label in labels.items():
        path = out / f"{name}.png"
        full = png(path, base.size)
        diff = ImageChops.difference(base, full)
        outside = diff.copy()
        ImageDraw.Draw(outside).rectangle((band[0], band[1], band[2]-1, band[3]-1), fill=(0,0,0,0))
        changed_outside = sum(pixel != (0,0,0,0) for pixel in outside.getdata())
        changed_inside = sum(pixel != (0,0,0,0) for pixel in diff.crop(band).getdata())
        alpha_matches = full.getchannel("A").tobytes() == base.getchannel("A").tobytes()
        crop = png(out / "faces" / f"{name}.png", crop_size)
        crop_matches = crop.tobytes() == full.crop(band).tobytes()
        if changed_outside or not alpha_matches or not crop_matches or not changed_inside:
            raise ValueError(f"{out.name}/{name}: invariant failed (outside={changed_outside}, alpha={alpha_matches}, crop={crop_matches}, inside={changed_inside})")
        entries.append({"name": name, "expression_th": label, "full": f"{name}.png", "face": f"faces/{name}.png",
                        "outside_changed_pixels": changed_outside, "inside_changed_pixels": changed_inside,
                        "alpha_matches": alpha_matches, "crop_matches": crop_matches, "sha256": digest(path)})
    return entries


def pose_manifest(pose, root=ROOT):
    spec = POSES[pose]
    original, base, offset, band = geometry(pose, root)
    out = root / OUTPUT / pose
    saved = png(out / "base.png", base.size)
    if saved.tobytes() != base.tobytes():
        raise ValueError(f"{pose}: base differs from original padded pixels")
    crop_size = (band[2]-band[0], band[3]-band[1])
    if png(out / "faces/base.png", crop_size).tobytes() != base.crop(band).tobytes():
        raise ValueError(f"{pose}: base face crop differs")
    labels = {name: LABELS[name] for name in spec["masks"]}
    entries = check_frames(out, base, band, labels)
    expected_pngs = {"base.png", "faces/base.png"}
    for name in labels:
        expected_pngs.update([f"{name}.png", f"faces/{name}.png"])
    actual_pngs = {p.relative_to(out).as_posix() for p in out.rglob("*.png")}
    if expected_pngs != actual_pngs:
        raise ValueError(f"{pose}: unexpected/missing PNG files: {expected_pngs ^ actual_pngs}")
    return {"schema_version": 2, "pose": pose, "source": f"../../{pose}.webp",
            "source_size": list(original.size), "source_sha256": digest(root / ASSETS / f"{pose}.webp"),
            "canvas_size": list(base.size), "source_offset": list(offset),
            "face_band_source_xyxy_exclusive": spec["band"], "face_band_canvas_xyxy_exclusive": list(band),
            "face_crop_size": list(crop_size), "expression_masks_source": spec["masks"],
            "base": "base.png", "base_sha256": digest(out / "base.png"),
            "expected_expressions": list(labels), "expected_expression_count": len(labels),
            "actual_expression_count": len(entries), "complete": True, "expressions": entries}


def validate_pose(pose, root=ROOT):
    out = root / OUTPUT / pose
    expected = pose_manifest(pose, root)
    manifest_path = out / "manifest.json"
    if not manifest_path.is_file() or json.loads(manifest_path.read_text(encoding="utf-8")) != expected:
        raise ValueError(f"{pose}: saved manifest is missing, stale, or inconsistent")
    if not (out / "contact-sheet.jpg").is_file():
        raise ValueError(f"{pose}: contact sheet missing")
    for path in out.rglob("*"):
        if path.is_file() and path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"File exceeds 5 MB: {path}")
    return {"pose": pose, "expressions": len(expected["expressions"]), "complete": True,
            "outside_changed_pixels": 0, "alpha_and_crop_checks": "passed", "manifest_check": "passed"}


def contact_sheet(pose, root=ROOT):
    out = root / OUTPUT / pose
    names = ["base", *POSES[pose]["masks"]]
    sheet = Image.new("RGB", (210 * len(names), 300), "#F5F3ED")
    draw = ImageDraw.Draw(sheet)
    for index, name in enumerate(names):
        sprite = Image.open(out / f"{name}.png").convert("RGBA")
        sprite.thumbnail((200,270), Image.Resampling.LANCZOS)
        x = index*210 + (210-sprite.width)//2
        sheet.paste(sprite, (x,270-sprite.height), sprite)
        draw.text((index*210+12,280), f"{pose}/{name}", fill="#22301F")
    sheet.save(out / "contact-sheet.jpg", quality=92)


def compose_pose(pose, inputs, root=ROOT):
    names = [item["name"] for item in inputs]
    required = set(POSES[pose]["masks"])
    if len(names) != len(set(names)) or set(names) != required:
        raise ValueError(f"{pose}: provide exactly {sorted(required)}")
    original, base, offset, band = geometry(pose, root)
    out = root / OUTPUT / pose
    (out / "faces").mkdir(parents=True, exist_ok=True)
    base.save(out / "base.png", optimize=True)
    base.crop(band).save(out / "faces/base.png", optimize=True)
    for item in inputs:
        name = item["name"]
        edited = Image.open(item["path"]).convert("RGBA").resize(original.size, Image.Resampling.LANCZOS)
        edited.putalpha(original.getchannel("A"))
        face = Image.composite(edited, original, expression_mask(pose,name,original.size))
        full = base.copy()
        full.paste(face.crop(tuple(POSES[pose]["band"])), (band[0],band[1]))
        full.save(out / f"{name}.png", optimize=True)
        full.crop(band).save(out / "faces" / f"{name}.png", optimize=True)
    manifest = pose_manifest(pose,root)
    (out / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    contact_sheet(pose,root)
    return validate_pose(pose,root)


def validate_front(root=ROOT):
    # Legacy geometry and manifest format are retained exactly; never call its
    # inspect()/contact_sheet(), because those are writing build operations.
    import build_mascot_expressions as front
    source = root / ASSETS / "front.webp"
    original = Image.open(source).convert("RGBA")
    offset = ((front.CANVAS[0]-original.width)//2,front.CANVAS[1]-original.height)
    base = Image.new("RGBA",front.CANVAS,(0,0,0,0))
    base.paste(original,offset)
    band = tuple(v+offset[i%2] for i,v in enumerate(front.BAND_ORIGINAL))
    out = root / OUTPUT
    if png(out / "front.png",base.size).tobytes() != base.tobytes():
        raise ValueError("front: original padded base differs")
    if png(out / "faces/front.png",(280,160)).tobytes() != base.crop(band).tobytes():
        raise ValueError("front: base crop differs")
    entries = check_frames(out,base,band,front.LABELS)
    expected = {"schema_version": 1, "source": "../front.webp", "source_size": list(original.size),
                "source_sha256": digest(source), "canvas_size": list(front.CANVAS), "source_offset": list(offset),
                "face_band_source_xyxy_exclusive": list(front.BAND_ORIGINAL),
                "face_band_canvas_xyxy_exclusive": list(band), "face_crop_size": [280,160], "base": "front.png",
                "expected_expression_count": len(front.LABELS), "actual_expression_count": len(entries),
                "complete": True, "expressions": entries}
    if json.loads((out / "manifest.json").read_text(encoding="utf-8")) != expected:
        raise ValueError("front: manifest is stale or inconsistent")
    return {"pose": "front", "expressions": len(entries), "complete": True,
            "outside_changed_pixels": 0, "alpha_and_crop_checks": "passed", "manifest_check": "passed"}


def validate_all(root=ROOT):
    reports = [validate_front(root)] + [validate_pose(pose,root) for pose in POSES]
    for report in reports:
        print(json.dumps(report,ensure_ascii=False))
    return reports
