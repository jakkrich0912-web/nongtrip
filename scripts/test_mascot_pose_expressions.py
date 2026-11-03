"""Regression checks for saved mascot assets and deliberate invariant violations.

Run from repository root: python -m unittest discover -s scripts -p test_mascot_pose_expressions.py
All negative mutations stay in temporary directories; delivered sprites stay intact.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image
from mascot_pose_expressions import ASSETS, OUTPUT, ROOT, validate_all, validate_pose


class PoseValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ASSETS).mkdir(parents=True)
        shutil.copyfile(ROOT / ASSETS / 'wave.webp', self.root / ASSETS / 'wave.webp')
        self.out = self.root / OUTPUT / 'wave'
        shutil.copytree(ROOT / OUTPUT / 'wave', self.out)

    def reject(self):
        with self.assertRaises(ValueError):
            validate_pose('wave', self.root)

    def change_pixel(self, point, color):
        path = self.out / 'blink-half.png'
        with Image.open(path) as im:
            changed = im.copy()
        changed.putpixel(point, color)
        changed.save(path)

    def test_delivered_frames_validate_without_writes(self):
        files = sorted(p for p in (ROOT / OUTPUT).rglob('*') if p.is_file())
        before = {p: (hashlib.sha256(p.read_bytes()).digest(), p.stat().st_mtime_ns) for p in files}
        with contextlib.redirect_stdout(io.StringIO()):
            reports = validate_all()
        self.assertEqual([r['expressions'] for r in reports], [23, 3, 3, 2])
        self.assertEqual(before, {p: (hashlib.sha256(p.read_bytes()).digest(), p.stat().st_mtime_ns) for p in files})

    def test_rejects_changed_rgb_outside_band_even_when_transparent(self):
        self.change_pixel((0, 0), (1, 0, 0, 0))
        self.reject()

    def test_rejects_alpha_change_inside_band(self):
        self.change_pixel((170, 180), (100, 100, 100, 0))
        self.reject()

    def test_rejects_wrong_canvas(self):
        path = self.out / 'blink-half.png'
        with Image.open(path) as im:
            changed = im.crop((0, 0, im.width - 1, im.height))
        changed.save(path)
        self.reject()

    def test_rejects_missing_required_expression(self):
        (self.out / 'blink-closed.png').unlink()
        self.reject()

    def test_rejects_missing_optional_grin_once_declared_in_set(self):
        (self.out / 'grin.png').unlink()
        self.reject()

    def test_rejects_wrong_base(self):
        path = self.out / 'base.png'
        with Image.open(path) as im:
            changed = im.copy()
        changed.putpixel((0, 0), (1, 0, 0, 0))
        changed.save(path)
        self.reject()

    def test_rejects_wrong_crop(self):
        path = self.out / 'faces/blink-half.png'
        with Image.open(path) as im:
            changed = im.copy()
        changed.putpixel((0, 0), (1, 0, 0, 0))
        changed.save(path)
        self.reject()

    def test_rejects_non_rgba(self):
        path = self.out / 'blink-half.png'
        with Image.open(path) as im:
            changed = im.convert('RGB')
        changed.save(path)
        self.reject()

    def test_rejects_stale_manifest(self):
        path = self.out / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['source_offset'] = [11, 20]
        path.write_text(json.dumps(data), encoding='utf-8')
        self.reject()

    def test_rejects_missing_manifest(self):
        (self.out / 'manifest.json').unlink()
        self.reject()

    def test_rejects_oversize_file(self):
        with (self.out / 'blink-half.png').open('ab') as f:
            f.write(b'0' * 5_000_001)
        self.reject()

    def test_rejects_unexpected_frame(self):
        shutil.copyfile(self.out / 'grin.png', self.out / 'extra.png')
        self.reject()


if __name__ == '__main__':
    unittest.main()
