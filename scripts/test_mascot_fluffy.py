"""Focused checks for fluffy source integrity and publishing only validated sets."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

import build_mascot_expressions as front
import build_mascot_fluffy as fluffy
import mascot_pose_expressions as poses


def artwork(size=(100, 140)):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((20, 20, size[0]-21, size[1]-21),
                                   fill=(241, 165, 79, 255))
    return image


def snapshot(folder):
    return {str(path.relative_to(folder)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in folder.rglob("*") if path.is_file()}


class FluffyBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = self.root / "assets"
        self.inputs = self.root / "inputs"
        self.assets.mkdir()
        self.inputs.mkdir()
        (self.assets / "expressions-v2").mkdir()
        self.specs = {}
        for pose, size in fluffy.SIZES.items():
            raw = artwork()
            input_path = self.inputs / f"{pose}-fluffy.png"
            raw.save(input_path)
            spec = fluffy.layout(raw, size)
            output_path = self.assets / f"{pose}.webp"
            fluffy.normalize(raw, spec).save(output_path, lossless=True, exact=True)
            spec.update(input_sha256=fluffy.digest(input_path),
                        output_sha256=fluffy.digest(output_path))
            self.specs[pose] = spec
        self.manifest = {"design": "fluffy-v2", "source_images": self.specs,
                         "all_edges_have_transparent_padding": True}
        self.write_manifest()

    def write_manifest(self):
        (self.assets / "fluffy-manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def test_rejects_visible_raw_pixels_on_each_edge(self):
        for point in ((0, 70), (99, 70), (50, 0), (50, 139)):
            with self.subTest(point=point):
                raw = artwork()
                raw.putpixel(point, (240, 160, 80, 255))
                with self.assertRaisesRegex(ValueError, "Raw artwork touches edge"):
                    fluffy.layout(raw, (373, 520))

    def test_rejects_expression_with_different_aspect_ratio(self):
        with self.assertRaisesRegex(ValueError, "aspect ratio"):
            fluffy.normalize(artwork((140, 100)), self.specs["front"])

    def test_sources_validate_read_only_including_head_side_and_back(self):
        before = snapshot(self.assets)
        report = fluffy.validate_sources(self.assets)
        self.assertEqual(set(report), set(fluffy.SIZES))
        for pose in ("head", "side", "back"):
            self.assertTrue(all(margin >= 8 for margin in report[pose]["transparent_margins"]))
        self.assertEqual(snapshot(self.assets), before)

    def test_same_size_recolor_is_rejected_by_source_hash(self):
        for pose in ("head", "side", "back"):
            with self.subTest(pose=pose):
                path = self.assets / f"{pose}.webp"
                original = path.read_bytes()
                with Image.open(path) as opened:
                    image = opened.copy()
                x, y = image.width // 2, image.height // 2
                r, g, b, a = image.getpixel((x, y))
                image.putpixel((x, y), (r ^ 1, g, b, a))
                image.save(path, lossless=True, exact=True)
                with self.assertRaisesRegex(ValueError, "stale source manifest/hash"):
                    fluffy.validate_sources(self.assets)
                path.write_bytes(original)

    def test_head_side_back_edge_checks_do_not_depend_on_hash(self):
        for pose in ("head", "side", "back"):
            with self.subTest(pose=pose):
                path = self.assets / f"{pose}.webp"
                original = path.read_bytes()
                old_hash = self.specs[pose]["output_sha256"]
                with Image.open(path) as opened:
                    image = opened.copy()
                image.putpixel((0, image.height // 2), (241, 165, 79, 255))
                image.save(path, lossless=True, exact=True)
                self.specs[pose]["output_sha256"] = fluffy.digest(path)
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, "silhouette touches edge"):
                    fluffy.validate_sources(self.assets)
                path.write_bytes(original)
                self.specs[pose]["output_sha256"] = old_hash
                self.write_manifest()

    def test_rejects_manifest_claiming_raw_artwork_was_clipped(self):
        self.specs["front"]["visible_raw_bbox"][2] = self.specs["front"]["raw_size"][0]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "raw artwork was clipped"):
            fluffy.validate_sources(self.assets)

    def test_missing_last_input_fails_before_any_staging_or_asset_writes(self):
        groups = {"front": front.LABELS,
                  **{pose: spec["masks"] for pose, spec in poses.POSES.items()}}
        for pose, names in groups.items():
            folder = self.inputs / pose
            folder.mkdir()
            for name in names:
                artwork().save(folder / f"{name}.png")
        (self.inputs / "back-fluffy.png").unlink()
        before = snapshot(self.assets)
        with patch.object(fluffy, "ASSETS", self.assets), \
                patch.object(fluffy.shutil, "copytree") as copytree:
            with self.assertRaises(FileNotFoundError):
                fluffy.build(self.inputs)
        copytree.assert_not_called()
        self.assertEqual(snapshot(self.assets), before)

    def test_failed_stage_validation_does_not_publish_and_restores_front_globals(self):
        before = snapshot(self.assets)
        old_source, old_out = front.SOURCE, front.OUT
        checked_stages = []

        def reject_stage(*, root):
            stage = root / fluffy.RELATIVE_ASSETS
            checked_stages.append(stage)
            self.assertNotEqual(stage, self.assets)
            self.assertTrue((stage / "front.webp").is_file())
            raise ValueError("Deliberate staged set rejection")

        # Isolate the publish boundary: source normalization runs for all seven
        # poses; individual expression composition is covered by its own tests.
        with patch.object(fluffy, "ASSETS", self.assets), \
                patch.object(fluffy, "preflight", return_value=({}, self.specs)), \
                patch.object(poses, "validate_all", side_effect=reject_stage):
            with self.assertRaisesRegex(ValueError, "staged set rejection"):
                fluffy.build(self.inputs)
        self.assertEqual(len(checked_stages), 1)
        self.assertEqual((front.SOURCE, front.OUT), (old_source, old_out))
        self.assertEqual(snapshot(self.assets), before)


if __name__ == "__main__":
    unittest.main()
