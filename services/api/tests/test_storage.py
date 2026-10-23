import tempfile
import unittest
from pathlib import Path

from app.storage.local import LocalStorageProvider


class LocalStorageTests(unittest.TestCase):
    def test_generated_cutout_can_be_saved_with_character(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = LocalStorageProvider(Path(folder))
            pet_id = "pet_" + "a" * 32
            for name in ("cutout.png", "character.png"):
                saved = storage.save(pet_id, name, b"image-content")
                self.assertEqual(saved.read_bytes(), b"image-content")

    def test_allowing_cutout_does_not_allow_arbitrary_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = LocalStorageProvider(Path(folder))
            for name in ("../cutout.png", "cutout.png.exe", "cutout.png/other", "arbitrary.txt"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    storage.save("pet_" + "a" * 32, name, b"content")
