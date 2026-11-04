"""Check delivered gaze pixels, measured directions, and rejected corruptions.

Run: python -m unittest discover -s scripts -p test_mascot_gaze.py
Only temporary copies are modified. Feature tracking deliberately does not call
the generator's displacement/frame helpers, so shared direction bugs are caught.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

import build_mascot_gaze as gaze
import build_mascot_expressions as expressions
from mascot_pose_expressions import validate_front


ASSETS = Path(__file__).resolve().parents[1] / "apps/web/src/assets/mascot/expressions-v2"
DIRECTIONS = (
    "e", "ene", "ne", "nne", "n", "nnw", "nw", "wnw",
    "w", "wsw", "sw", "ssw", "s", "sse", "se", "ese",
)
FILENAMES = tuple(f"gaze-{direction}.png" for direction in DIRECTIONS)
# Eye interiors measured on fluffy front.webp, with (23, 20) padding added.
# Keep these explicit so a generator-geometry change must be reviewed separately.
APERTURES = ((155.5, 236.0, 25.0, 26.5), (280.0, 243.5, 23.5, 26.0))


def load(path):
    with Image.open(path) as opened:
        return opened.copy()


def highlight_center(image, aperture):
    """Track the white eye glint; exclude fur and the fixed aperture boundary."""
    cx, cy, rx, ry = aperture
    weighted_x = weighted_y = total = 0.0
    for y in range(math.floor(cy - ry), math.ceil(cy + ry) + 1):
        for x in range(math.floor(cx - rx), math.ceil(cx + rx) + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 >= 0.85 ** 2:
                continue
            weight = max(0, min(image.getpixel((x, y))[:3]) - 195)
            weighted_x += x * weight
            weighted_y += y * weight
            total += weight
    if not total:
        raise AssertionError("Original white eye glint is missing")
    return weighted_x / total, weighted_y / total


class DeliveredGazeTests(unittest.TestCase):
    def test_exact_names_rgba_and_only_eye_interiors_change(self):
        self.assertEqual({path.name for path in ASSETS.glob("gaze-*.png")}, set(FILENAMES))
        base = load(ASSETS / "front.png")
        outside = Image.new("L", (420, 540), 255)
        for cx, cy, rx, ry in APERTURES:
            for y in range(math.floor(cy - ry), math.ceil(cy + ry) + 1):
                for x in range(math.floor(cx - rx), math.ceil(cx + rx) + 1):
                    if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1:
                        outside.putpixel((x, y), 0)
        hashes = set()
        for name in FILENAMES:
            with self.subTest(name=name), Image.open(ASSETS / name) as current:
                self.assertEqual((current.format, current.mode, current.size), ("PNG", "RGBA", (420, 540)))
                self.assertLessEqual((ASSETS / name).stat().st_size, 5_000_000)
                self.assertEqual(current.getchannel("A").tobytes(), base.getchannel("A").tobytes())
                # RGB comparison also checks hidden pixels with alpha zero.
                difference = ImageChops.difference(base.convert("RGB"), current.convert("RGB"))
                self.assertIsNotNone(difference.getbbox())
                self.assertIsNone(ImageChops.multiply(difference, outside.convert("RGB")).getbbox())
                hashes.add(hashlib.sha256(current.tobytes()).digest())
        self.assertEqual(len(hashes), 16)

    def test_measured_eye_glints_follow_all_named_directions_continuously(self):
        base = load(ASSETS / "front.png")
        for eye, aperture in enumerate(APERTURES):
            origin = highlight_center(base, aperture)
            centers = []
            for index, name in enumerate(FILENAMES):
                with self.subTest(eye=eye, name=name):
                    center = highlight_center(load(ASSETS / name), aperture)
                    centers.append(center)
                    dx, dy = center[0] - origin[0], center[1] - origin[1]
                    self.assertGreater(math.hypot(dx, dy), 2.0)
                    measured = math.degrees(math.atan2(-dy, dx))
                    error = (measured - index * 22.5 + 180) % 360 - 180
                    # Each feature must stay in its own compass sector.
                    self.assertLess(abs(error), 11.25)
            for index, center in enumerate(centers):
                with self.subTest(eye=eye, edge=index):
                    step = math.dist(center, centers[(index + 1) % 16])
                    self.assertGreater(step, 0.5)
                    self.assertLess(step, 2.0)

    def test_validation_is_read_only(self):
        paths = [ASSETS / name for name in (*FILENAMES, "front.png", "manifest.json")]
        def snapshot():
            return {path.name: (hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns)
                    for path in paths}
        before = snapshot()
        report = gaze.validate(out=ASSETS)
        self.assertEqual(report["frames"], 16)
        self.assertEqual(report["outside_eye_changed_pixels"], 0)
        self.assertEqual(snapshot(), before)

    def test_legacy_operations_check_gaze_files_even_without_manifest_section(self):
        manifest_path = ASSETS / "manifest.json"
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        saved.pop("gaze")
        read_text = Path.read_text

        def missing_gaze_section(path, *args, **kwargs):
            if path == manifest_path:
                return json.dumps(saved)
            return read_text(path, *args, **kwargs)

        for operation in (validate_front, expressions.inspect):
            with self.subTest(operation=operation.__name__):
                # Test dispatch only: malformed gaze metadata is already tested
                # directly below. Prevent any write even if the guard regresses.
                with patch.object(Path, "read_text", missing_gaze_section), \
                        patch.object(Path, "write_text", side_effect=AssertionError("Unexpected write")), \
                        patch.object(gaze, "validate", side_effect=ValueError("Gaze section required")) as validator:
                    with self.assertRaisesRegex(ValueError, "Gaze section required"):
                        operation()
                    validator.assert_called_once_with(out=ASSETS)


class CorruptGazeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name)
        for name in (*FILENAMES, "front.png", "manifest.json"):
            shutil.copyfile(ASSETS / name, self.out / name)
        self.frame_path = self.out / "gaze-e.png"

    def reject(self, message):
        with self.assertRaisesRegex(ValueError, message):
            gaze.validate(out=self.out)

    def test_rejects_edits_to_mouth_or_transparent_background(self):
        original = self.frame_path.read_bytes()
        for point in ((218, 279), (0, 0)):
            with self.subTest(point=point):
                self.frame_path.write_bytes(original)
                current = load(self.frame_path)
                r, g, b, a = current.getpixel(point)
                current.putpixel(point, (r ^ 1, g, b, a))
                current.save(self.frame_path)
                self.reject("outside eyes")

    def test_rejects_alpha_change_inside_eye(self):
        current = load(self.frame_path)
        r, g, b, a = current.getpixel((155, 236))
        current.putpixel((155, 236), (r, g, b, a ^ 1))
        current.save(self.frame_path)
        self.reject("alpha changed")

    def test_rejects_wrong_canvas(self):
        load(self.frame_path).crop((0, 0, 419, 540)).save(self.frame_path)
        self.reject("expected PNG RGBA 420x540")

    def test_rejects_rgb_instead_of_rgba(self):
        load(self.frame_path).convert("RGB").save(self.frame_path)
        self.reject("expected PNG RGBA 420x540")

    def test_rejects_missing_direction(self):
        self.frame_path.unlink()
        self.reject("exactly the 16 compass directions")

    def test_rejects_misspelled_direction(self):
        self.frame_path.rename(self.out / "gaze-east.png")
        self.reject("exactly the 16 compass directions")

    def test_rejects_west_pixels_labelled_east(self):
        shutil.copyfile(self.out / "gaze-w.png", self.frame_path)
        self.reject("declared gaze direction")

    def test_rejects_stale_or_missing_gaze_manifest(self):
        path = self.out / "manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        expected = copy.deepcopy(original["gaze"])
        # Isolate saved-metadata comparison; pixel validation is exercised above.
        with patch.object(gaze, "inspect", return_value=expected):
            stale = copy.deepcopy(original)
            stale["gaze"]["actual_frame_count"] = 15
            missing = {key: value for key, value in original.items() if key != "gaze"}
            for manifest in (stale, missing):
                with self.subTest(has_gaze="gaze" in manifest):
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                    before = path.read_bytes()
                    self.reject("manifest missing/stale")
                    self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
