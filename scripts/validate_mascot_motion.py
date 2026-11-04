"""Read-only validation of the delivered mascot motion assets (Pillow only).

Run: python scripts/validate_mascot_motion.py [--out PATH]
The registration contract lives here independently of the asset builder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image


ASSETS = Path(__file__).resolve().parents[1] / "apps/web/src/assets/mascot/motion"
CANVAS = (360, 480)
ANCHOR = [180, 447]
ANCHOR_SEMANTICS = "fixed ground registration; feet lift only during hop"
FRAME_LIMIT = 60_000
TOTAL_LIMIT = 1_200_000
MIN_MARGIN = 8
SPECS = {
    "walk": {"count": 8, "fps": 10, "clearances": (0,) * 8},
    "hop": {"count": 6, "fps": 10, "clearances": (0, 0, 26, 55, 0, 10)},
    "look-around": {"count": 6, "fps": 6, "clearances": (0,) * 6},
    "tail-wag": {"count": 4, "fps": 6, "clearances": (0,) * 4},
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, expected):
    return type(value) is int and value == expected


def _integers(value, expected):
    return (type(value) is list and len(value) == len(expected)
            and all(_integer(item, wanted) for item, wanted in zip(value, expected)))


def _manifest(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{path.name}: missing or invalid manifest: {error}") from error
    _require(type(value) is dict, f"{path}: manifest must be an object")
    return value


def _frame(path):
    """Decode before checking geometry; never substitute declared statistics."""
    try:
        with Image.open(path) as opened:
            _require((opened.format, opened.mode, opened.size) == ("WEBP", "RGBA", CANVAS),
                     f"{path}: expected WEBP RGBA 360x480")
            _require(getattr(opened, "n_frames", 1) == 1
                     and not getattr(opened, "is_animated", False),
                     f"{path}: animated WebP is not a single frame")
            opened.load()
            return opened.copy()
    except (OSError, SyntaxError) as error:
        raise ValueError(f"{path}: invalid image: {error}") from error


def _head_center_x(alpha):
    """Measure the opaque upper silhouette without trusting registration metadata."""
    silhouette = alpha.point([0] * 33 + [255] * 223).getbbox()
    _require(silhouette is not None, "No substantial alpha silhouette")
    top, bottom = silhouette[1], silhouette[3] - 1
    cutoff = top + int((bottom - top) * 0.45)
    pixels = alpha.load()
    total_x = count = 0
    for y in range(top, cutoff):
        for x in range(alpha.width):
            if pixels[x, y] > 128:
                total_x += x
                count += 1
    _require(count > 0, "No opaque head silhouette")
    return total_x / count


def validate(out=ASSETS):
    """Raise ValueError for a failed contract; return measured statistics otherwise.

    Encoded and decoded uniqueness is per animation; a neutral pose may be
    shared by different animations. Hashes verify every byte of each frame.
    """
    out = Path(out)
    _require(out.is_dir(), f"Motion directory missing: {out}")
    directories = {path.name for path in out.iterdir() if path.is_dir()}
    _require(directories == set(SPECS),
             f"Expected exactly animation directories {sorted(SPECS)}; got {sorted(directories)}")
    total_bytes = sum(path.stat().st_size for path in out.rglob("*") if path.is_file())
    _require(total_bytes <= TOTAL_LIMIT,
             f"Motion directory total size {total_bytes} exceeds {TOTAL_LIMIT} bytes")
    report = {"frames": 0, "total_bytes": total_bytes, "animations": {}}
    for name, spec in SPECS.items():
        folder = out / name
        filenames = [f"{index:02d}.webp" for index in range(spec["count"])]
        numbered = {path.name for path in folder.iterdir()
                    if path.is_file() and (path.suffix.lower() == ".webp"
                                           or re.fullmatch(r"\d+\.[^.]+", path.name))}
        _require(numbered == set(filenames),
                 f"{name}: expected exactly frames {filenames}; got {sorted(numbered)}")
        manifest = _manifest(folder / "manifest.json")
        _require(_integer(manifest.get("schema_version"), 1), f"{name}: schema_version must be 1")
        _require(manifest.get("name") == name, f"{name}: manifest name mismatch")
        _require(_integers(manifest.get("canvas_size"), CANVAS), f"{name}: invalid canvas_size")
        _require(_integer(manifest.get("frame_count"), spec["count"]), f"{name}: invalid frame_count")
        _require(_integer(manifest.get("fps"), spec["fps"]),
                 f"{name}: fps must be {spec['fps']}")
        _require(manifest.get("loop") is True, f"{name}: loop must be true")
        _require(_integers(manifest.get("anchor"), ANCHOR), f"{name}: anchor must be {ANCHOR}")
        _require(manifest.get("anchor_semantics") == ANCHOR_SEMANTICS,
                 f"{name}: invalid anchor_semantics")
        entries = manifest.get("frames")
        _require(type(entries) is list and len(entries) == spec["count"],
                 f"{name}: invalid manifest frame list")
        encoded_hashes = set()
        pixel_hashes = set()
        fixed_feet = None
        measured = []
        for index, filename in enumerate(filenames):
            label = f"{name}/{filename}"
            entry = entries[index]
            _require(type(entry) is dict and entry.get("file") == filename,
                     f"{label}: manifest frame order or file mismatch")
            _require(_integers(entry.get("anchor"), ANCHOR),
                     f"{label}: frame anchor must be {ANCHOR}")
            clearance = spec["clearances"][index]
            _require(_integer(entry.get("ground_clearance_px"), clearance),
                     f"{label}: ground_clearance_px must be {clearance}")
            path = folder / filename
            data = path.read_bytes()
            _require(len(data) <= FRAME_LIMIT,
                     f"{label}: frame size {len(data)} exceeds {FRAME_LIMIT} bytes")
            current = _frame(path)
            alpha = current.getchannel("A")
            bbox = alpha.getbbox()
            _require(bbox is not None, f"{label}: empty alpha silhouette")
            margins = (bbox[0], bbox[1], CANVAS[0] - bbox[2], CANVAS[1] - bbox[3])
            _require(min(margins) >= MIN_MARGIN,
                     f"{label}: transparent margins must be at least {MIN_MARGIN}px; got {margins}")
            _require(alpha.getextrema()[0] == 0, f"{label}: background must be transparent")
            _require(bbox[3] - 1 == ANCHOR[1] - clearance,
                     f"{label}: ground registration mismatch: actual bottom {bbox[3] - 1}, "
                     f"expected {ANCHOR[1] - clearance}")
            if name in ("walk", "hop"):
                center_x = _head_center_x(alpha)
                _require(abs(center_x - ANCHOR[0]) <= 0.6,
                         f"{label}: horizontal head registration mismatch: "
                         f"actual center {center_x:.3f}, expected {ANCHOR[0]} +/- 0.6px")
            digest = hashlib.sha256(data).hexdigest()
            _require(entry.get("sha256") == digest, f"{label}: stale sha256")
            _require(_integer(entry.get("bytes"), len(data)), f"{label}: stale bytes")
            _require(_integers(entry.get("alpha_bbox"), bbox), f"{label}: stale alpha_bbox")
            _require(digest not in encoded_hashes, f"{label}: duplicate encoded frame")
            encoded_hashes.add(digest)
            # Ignore invisible RGB so altered transparent pixels cannot stand
            # in for a distinct animation pose. Encoded hashes still cover them.
            visible = Image.new("RGBA", CANVAS)
            visible.alpha_composite(current)
            pixels_digest = hashlib.sha256(visible.tobytes()).hexdigest()
            _require(pixels_digest not in pixel_hashes, f"{label}: duplicate decoded frame")
            pixel_hashes.add(pixels_digest)
            if name in ("look-around", "tail-wag"):
                feet = alpha.crop((0, 420, 360, 480)).tobytes()
                if fixed_feet is None:
                    fixed_feet = feet
                _require(feet == fixed_feet, f"{label}: stationary feet alpha changed")
            measured.append({"file": filename, "bytes": len(data), "sha256": digest,
                             "alpha_bbox": list(bbox), "ground_clearance_px": clearance})
        report["animations"][name] = {"frame_count": spec["count"], "fps": spec["fps"],
                                      "frames": measured}
        report["frames"] += spec["count"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ASSETS)
    args = parser.parse_args()
    try:
        report = validate(args.out)
    except ValueError as error:
        parser.exit(1, f"Motion validation failed: {error}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
