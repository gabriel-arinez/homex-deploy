#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/media_inventory.py"


class MediaInventoryTests(unittest.TestCase):
    def run_script(
        self, *args: object, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(value) for value in args)],
            text=True,
            capture_output=True,
            check=check,
        )

    def test_round_trip_preserves_content_mode_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            (source / "productos/item").mkdir(parents=True)
            (source / "proformas/doc").mkdir(parents=True)
            product = source / "productos/item/original.webp"
            attachment = source / "proformas/doc/320.webp"
            product.write_bytes(b"product-image")
            attachment.write_bytes(b"attachment-image")
            product.chmod(0o640)
            attachment.chmod(0o644)
            manifest = base / "media-manifest.json"
            archive = base / "media.tar.gz"
            restored = base / "restored"

            self.run_script("inventory", source, manifest)
            self.run_script("archive", source, archive)
            self.run_script("extract", archive, restored)
            result = self.run_script("verify", restored, manifest)

            self.assertIn("media-checksums-ok", result.stdout)
            data = json.loads(manifest.read_text())
            self.assertEqual(2, len(data["files"]))
            mode = (restored / "productos/item/original.webp").stat().st_mode & 0o777
            self.assertEqual(0o640, mode)

    def test_audio_and_symlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "productos").mkdir()
            (root / "productos/asr.wav").write_bytes(b"not-backed-up")
            result = self.run_script("inventory", root, root / "out.json", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Audio prohibido", result.stderr)

            (root / "productos/asr.wav").unlink()
            (root / "productos/link.webp").symlink_to("/etc/passwd")
            result = self.run_script("archive", root, root / "out.tar.gz", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("symlinks", result.stderr)

    def test_unsafe_archive_path_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "bad.tar.gz"
            payload = base / "payload"
            payload.write_text("escape")
            with tarfile.open(archive, "w:gz") as output:
                output.add(payload, arcname="../escape")
            result = self.run_script("extract", archive, base / "restored", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((base / "escape").exists())


if __name__ == "__main__":
    unittest.main()
