"""Validate delivery plus corruptions applied only to temporary fixtures.

Run: python -m unittest discover -s scripts -p test_mascot_motion.py
"""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image, ImageDraw

import validate_mascot_motion as motion


# Deliberately independent from the production validator and asset builder.
EXPECTED = {"walk": (8, 10, [0] * 8), "hop": (6, 10, [0, 0, 26, 55, 0, 10]),
            "look-around": (6, 6, [0] * 6), "tail-wag": (4, 6, [0] * 4)}


def read_image(path):
    with Image.open(path) as image:
        return image.copy()


def statistics(path):
    with Image.open(path) as image:
        bbox = list(image.getchannel("A").getbbox())
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "alpha_bbox": bbox}


def make_fixture(root):
    for name, (count, fps, clearances) in EXPECTED.items():
        folder = root / name
        folder.mkdir(parents=True)
        entries = []
        for index, clearance in enumerate(clearances):
            image = Image.new("RGBA", (360, 480))
            draw = ImageDraw.Draw(image)
            draw.rectangle((80, 85 - clearance, 279, 447 - clearance), fill=(230, 140, 60, 255))
            # Distinct head detail above the fixed feet region.
            draw.rectangle((130 + index * 3, 150 - clearance, 160 + index * 3, 180 - clearance),
                           fill=(40, 60 + index * 3, 20, 255))
            filename = f"{index:02d}.webp"
            path = folder / filename
            image.save(path, format="WEBP", lossless=True, exact=True)
            entries.append({"file": filename, "anchor": [180, 447],
                            "ground_clearance_px": clearance, **statistics(path)})
        manifest = {"schema_version": 1, "name": name, "canvas_size": [360, 480],
                    "frame_count": count, "fps": fps, "loop": True, "anchor": [180, 447],
                    "anchor_semantics": "fixed ground registration; feet lift only during hop",
                    "frames": entries}
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def snapshot(root):
    return {str(path.relative_to(root)): (hashlib.sha256(path.read_bytes()).digest(),
                                        path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


class MotionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.fixture_root = Path(cls.fixture.name)
        make_fixture(cls.fixture_root)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name) / "motion"
        shutil.copytree(self.fixture_root, self.out)
        self.frame = self.out / "walk/00.webp"

    def edit_manifest(self, name, change):
        path = self.out / name / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        change(manifest)
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def refresh(self, path):
        self.edit_manifest(path.parent.name,
                           lambda manifest: manifest["frames"][int(path.stem)].update(statistics(path)))

    def reject(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            motion.validate(self.out)

    def test_valid_contract_and_read_only_validation(self):
        before = snapshot(self.out)
        report = motion.validate(self.out)
        self.assertEqual(report["frames"], 24)
        self.assertEqual(set(report["animations"]), set(EXPECTED))
        self.assertEqual(snapshot(self.out), before)

    def test_missing_frame(self):
        self.frame.unlink()
        self.reject("expected exactly frames")

    def test_extra_numbered_frame(self):
        shutil.copyfile(self.frame, self.frame.with_name("08.webp"))
        self.reject("expected exactly frames")

    def test_extra_misnamed_webp_frame(self):
        shutil.copyfile(self.frame, self.frame.with_name("extra.webp"))
        self.reject("expected exactly frames")

    def test_wrong_canvas(self):
        read_image(self.frame).crop((0, 0, 359, 480)).save(self.frame, format="WEBP", lossless=True)
        self.reject("expected WEBP RGBA 360x480")

    def test_wrong_file_format(self):
        read_image(self.frame).save(self.frame, format="PNG")
        self.reject("expected WEBP RGBA 360x480")

    def test_missing_alpha(self):
        read_image(self.frame).convert("RGB").save(self.frame, format="WEBP", lossless=True)
        self.reject("expected WEBP RGBA 360x480")

    def test_animated_webp(self):
        first = read_image(self.frame)
        second = read_image(self.frame.with_name("01.webp"))
        first.save(self.frame, format="WEBP", save_all=True, append_images=[second],
                   duration=100, loop=0, lossless=True)
        self.reject("animated WebP")

    def test_shifted_vertical_pixels_even_with_fresh_manifest(self):
        shifted = Image.new("RGBA", (360, 480))
        shifted.paste(read_image(self.frame), (0, 1))
        shifted.save(self.frame, format="WEBP", lossless=True, exact=True)
        self.refresh(self.frame)
        self.reject("ground registration mismatch")

    def test_shifted_horizontal_pixels_even_with_fresh_manifest(self):
        shifted = Image.new("RGBA", (360, 480))
        shifted.paste(read_image(self.frame), (2, 0))
        shifted.save(self.frame, format="WEBP", lossless=True, exact=True)
        self.refresh(self.frame)
        self.reject("horizontal head registration mismatch")

    def test_margin_check_uses_pixels_even_with_fresh_manifest(self):
        image = read_image(self.frame)
        image.putpixel((7, 200), (230, 140, 60, 1))
        image.save(self.frame, format="WEBP", lossless=True, exact=True)
        self.refresh(self.frame)
        self.reject("transparent margins")

    def test_stale_hash_catches_rgb_only_change(self):
        image = read_image(self.frame)
        r, g, b, a = image.getpixel((100, 200))
        image.putpixel((100, 200), (r ^ 1, g, b, a))
        image.save(self.frame, format="WEBP", lossless=True, exact=True)
        self.reject("stale sha256")

    def test_stale_bbox(self):
        self.edit_manifest("walk", lambda manifest: manifest["frames"][0].update(alpha_bbox=[79, 85, 280, 448]))
        self.reject("stale alpha_bbox")

    def test_stale_byte_count(self):
        self.edit_manifest("walk", lambda manifest: manifest["frames"][0].update(bytes=1))
        self.reject("stale bytes")

    def test_top_level_anchor_cannot_redefine_registration(self):
        self.edit_manifest("walk", lambda manifest: manifest.update(anchor=[181, 447]))
        self.reject("anchor must be")

    def test_frame_anchor_cannot_redefine_registration(self):
        self.edit_manifest("walk", lambda manifest: manifest["frames"][0].update(anchor=[180, 448]))
        self.reject("frame anchor must be")

    def test_invalid_fps(self):
        for value in (0, -1, 12, 10.0, True):
            with self.subTest(value=value):
                self.edit_manifest("walk", lambda manifest: manifest.update(fps=value))
                self.reject("fps must be 10")

    def test_hop_clearance_cannot_be_redefined(self):
        self.edit_manifest("hop", lambda manifest: manifest["frames"][2].update(ground_clearance_px=0))
        self.reject("ground_clearance_px must be 26")

    def test_frame_size_budget(self):
        data = self.frame.read_bytes()
        self.frame.write_bytes(data + bytes(60_001 - len(data)))
        self.reject("frame size .* exceeds 60000")

    def test_total_size_includes_all_auxiliary_files(self):
        total = sum(path.stat().st_size for path in self.out.rglob("*") if path.is_file())
        (self.out / "contact-sheet.webp").write_bytes(bytes(1_200_001 - total))
        self.reject("total size .* exceeds 1200000")

    def test_duplicate_frame(self):
        target = self.frame.with_name("01.webp")
        shutil.copyfile(self.frame, target)
        self.refresh(target)
        self.reject("duplicate encoded frame")

    def test_duplicate_pixels_with_different_encoded_bytes(self):
        target = self.frame.with_name("01.webp")
        target.write_bytes(self.frame.read_bytes() + b"padding")
        self.refresh(target)
        self.reject("duplicate decoded frame")

    def test_invisible_rgb_does_not_make_a_distinct_frame(self):
        target = self.frame.with_name("01.webp")
        image = read_image(self.frame)
        image.putpixel((0, 0), (255, 0, 0, 0))
        image.save(target, format="WEBP", lossless=True, exact=True)
        self.refresh(target)
        self.reject("duplicate (encoded|decoded) frame")

    def test_stationary_feet_pixels_even_with_fresh_manifest(self):
        path = self.out / "look-around/01.webp"
        image = read_image(path)
        image.putpixel((100, 430), (230, 140, 60, 200))
        image.save(path, format="WEBP", lossless=True, exact=True)
        self.refresh(path)
        self.reject("stationary feet alpha changed")

    def test_actual_foot_need_not_cover_anchor_x(self):
        # A walk can plant its left or right foot without filling (180, 447).
        image = read_image(self.frame)
        ImageDraw.Draw(image).rectangle((150, 430, 210, 447), fill=(0, 0, 0, 0))
        image.save(self.frame, format="WEBP", lossless=True, exact=True)
        self.refresh(self.frame)
        self.assertEqual(motion.validate(self.out)["frames"], 24)


class DeliveredMotionTests(unittest.TestCase):
    def test_actual_delivery_satisfies_contract_without_writes(self):
        before = snapshot(motion.ASSETS)
        report = motion.validate()
        self.assertEqual(report["frames"], 24)
        self.assertLessEqual(report["total_bytes"], 1_200_000)
        self.assertEqual(snapshot(motion.ASSETS), before)


if __name__ == "__main__":
    unittest.main()
