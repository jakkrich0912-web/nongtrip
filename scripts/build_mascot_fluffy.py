"""Build the approved fluffy mascot as one validated, consistent asset set.

Inputs: <pose>-fluffy.png and <pose>/<expression>.png. Requires Pillow.
All outputs are staged and checked before publishing to the asset directory.
"""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RELATIVE_ASSETS = Path("apps/web/src/assets/mascot")
ASSETS = ROOT / RELATIVE_ASSETS
SIZES = {"front": (373, 520), "wave": (400, 517), "think": (400, 499),
         "happy": (397, 517), "head": (256, 256), "side": (332, 519), "back": (383, 508)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layout(image, size):
    # Ignore detached near-transparent pixels when measuring. Keep an 8px raw
    # fringe around visible fur; preserve alpha within that crop.
    bbox = image.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    if not bbox:
        raise ValueError("Empty artwork")
    if bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= image.width or bbox[3] >= image.height:
        raise ValueError("Raw artwork touches edge; repair the clipped silhouette first")
    crop = (max(0, bbox[0]-8), max(0, bbox[1]-8),
            min(image.width, bbox[2]+8), min(image.height, bbox[3]+8))
    scale = min((size[0]-20)/(crop[2]-crop[0]), (size[1]-20)/(crop[3]-crop[1]))
    resized = (round((crop[2]-crop[0])*scale), round((crop[3]-crop[1])*scale))
    offset = ((size[0]-resized[0])//2, (size[1]-resized[1])//2)
    return {"raw_size": list(image.size), "visible_raw_bbox": list(bbox), "crop": list(crop),
            "resized": list(resized), "offset": list(offset), "size": list(size)}


def normalize(image, spec):
    image = image.convert("RGBA")
    raw_size = tuple(spec["raw_size"])
    if abs((image.width/image.height)/(raw_size[0]/raw_size[1])-1) > 0.01:
        raise ValueError("Expression aspect ratio differs from its base")
    if image.size != raw_size:
        image = image.resize(raw_size, Image.Resampling.LANCZOS)
    # Premultiplied resizing prevents matte fringes around fine fur.
    crop = image.crop(tuple(spec["crop"])).convert("RGBa")
    crop = crop.resize(tuple(spec["resized"]), Image.Resampling.LANCZOS).convert("RGBA")
    result = Image.new("RGBA", tuple(spec["size"]), (0, 0, 0, 0))
    result.paste(crop, tuple(spec["offset"]))
    return result


def preflight(inputs):
    import build_mascot_expressions as front
    import mascot_pose_expressions as poses
    groups = {"front": front.LABELS, **{p: poses.POSES[p]["masks"] for p in poses.POSES}}
    specs = {}
    for pose, size in SIZES.items():
        path = inputs/f"{pose}-fluffy.png"
        with Image.open(path) as raw:
            if raw.mode != "RGBA" or raw.format != "PNG":
                raise ValueError(f"{path.name}: expected PNG RGBA")
            specs[pose] = layout(raw, size)
        for name in groups.get(pose, {}):
            path = inputs/pose/f"{name}.png"
            with Image.open(path) as edited:
                if edited.mode != "RGBA" or edited.format != "PNG":
                    raise ValueError(f"{pose}/{name}: expected PNG RGBA")
                raw_size = specs[pose]["raw_size"]
                if abs((edited.width/edited.height)/(raw_size[0]/raw_size[1])-1) > 0.01:
                    raise ValueError(f"{pose}/{name}: aspect ratio differs from base")
    return groups, specs


def build(inputs):
    import build_mascot_expressions as front
    import build_mascot_gaze as gaze
    import mascot_pose_expressions as poses

    groups, specs = preflight(inputs)
    with tempfile.TemporaryDirectory(prefix="nongtrip-fluffy-") as temporary:
        stage_root = Path(temporary)
        stage = stage_root/RELATIVE_ASSETS
        shutil.copytree(ASSETS, stage)
        normalized_dir = stage_root/"normalized"
        normalized_dir.mkdir()
        for pose in SIZES:
            path = inputs/f"{pose}-fluffy.png"
            with Image.open(path) as raw:
                normalized = normalize(raw, specs[pose])
            normalized.save(stage/f"{pose}.webp", lossless=True, exact=True, method=6)
            specs[pose].update(input_sha256=digest(path), output_sha256=digest(stage/f"{pose}.webp"))
        old_source, old_out = front.SOURCE, front.OUT
        front.SOURCE, front.OUT = stage/"front.webp", stage/"expressions-v2"
        try:
            for pose, names in groups.items():
                normalized_inputs = []
                for name in names:
                    path = inputs/pose/f"{name}.png"
                    target = normalized_dir/f"{pose}-{name}.png"
                    with Image.open(path) as edited:
                        normalize(edited, specs[pose]).save(target)
                    normalized_inputs.append({"name": name, "path": str(target)})
                if pose == "front":
                    front.compose(normalized_inputs)
                    gaze.build(out=front.OUT)
                    entries = front.inspect(require_complete=True)
                    front.contact_sheet(entries)
                else:
                    poses.compose_pose(pose, normalized_inputs, root=stage_root)
            poses.validate_all(root=stage_root)
        finally:
            front.SOURCE, front.OUT = old_source, old_out
        sheet = Image.new("RGB", (7*210, 300), "#F5F3ED")
        draw = ImageDraw.Draw(sheet)
        for i, pose in enumerate(SIZES):
            with Image.open(stage/f"{pose}.webp") as opened:
                image = opened.convert("RGBA")
            image.thumbnail((200,270), Image.Resampling.LANCZOS)
            sheet.paste(image, (i*210+(210-image.width)//2,270-image.height), image)
            draw.text((i*210+12,280), pose, fill="#22301F")
        sheet.save(stage/"expressions-v2/poses-contact-sheet.jpg", quality=94)
        (stage/"fluffy-manifest.json").write_text(json.dumps({
            "design": "fluffy-v2", "source_images": specs,
            "all_edges_have_transparent_padding": True
        }, indent=2)+"\n", encoding="utf-8")
        report = validate_sources(stage)
        # Publish only after all source/pose/expression/gaze checks have passed.
        shutil.copytree(stage, ASSETS, dirs_exist_ok=True)
    return report


def validate_sources(assets=ASSETS):
    saved = json.loads((assets/"fluffy-manifest.json").read_text(encoding="utf-8"))
    if saved.get("design") != "fluffy-v2" or set(saved.get("source_images", {})) != set(SIZES):
        raise ValueError("Incomplete or wrong fluffy source manifest")
    report = {}
    for pose, size in SIZES.items():
        path = assets/f"{pose}.webp"
        spec = saved["source_images"][pose]
        with Image.open(path) as image:
            if image.size != size or image.mode != "RGBA" or image.format != "WEBP":
                raise ValueError(f"{pose}: source geometry or alpha missing")
            bbox = image.getchannel("A").getbbox()
            if not bbox or bbox[0] < 8 or bbox[1] < 8 or bbox[2] > size[0]-8 or bbox[3] > size[1]-8:
                raise ValueError(f"{pose}: silhouette touches edge")
            if path.stat().st_size > 5_000_000:
                raise ValueError(f"{pose}: file exceeds 5 MB")
            if spec["size"] != list(size) or spec["output_sha256"] != digest(path):
                raise ValueError(f"{pose}: stale source manifest/hash")
            raw_bbox, raw_size = spec["visible_raw_bbox"], spec["raw_size"]
            if raw_bbox[0] <= 0 or raw_bbox[1] <= 0 or raw_bbox[2] >= raw_size[0] or raw_bbox[3] >= raw_size[1]:
                raise ValueError(f"{pose}: raw artwork was clipped")
            report[pose] = {"size": list(size), "alpha_bbox": list(bbox),
                           "transparent_margins": [bbox[0],bbox[1],size[0]-bbox[2],size[1]-bbox[3]]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inputs-dir", type=Path)
    group.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.inputs_dir:
        print(json.dumps(build(args.inputs_dir)))
    else:
        import mascot_pose_expressions as poses
        print(json.dumps(validate_sources()))
        poses.validate_all()
