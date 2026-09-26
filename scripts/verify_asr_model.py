#!/usr/bin/env python3
"""Verifica versión y hash del binario principal del modelo ASR fijado."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml


def main() -> None:
    manifest = yaml.safe_load(Path("releases/manifest.yaml").read_text(encoding="utf-8"))
    expected = manifest["runtime"]["asr_model"]
    model_root = Path(os.environ.get("ASR_MODEL_SOURCE", "artifacts/asr/faster-whisper-small"))
    model_file = model_root / "model.bin"
    if not model_file.is_file():
        raise SystemExit(f"Falta el artefacto ASR: {model_file}")

    digest = hashlib.sha256()
    with model_file.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected["sha256"]:
        raise SystemExit(f"Hash ASR distinto: expected={expected['sha256']}, actual={actual}")
    print(f"asr-model-ok: {expected['version']} sha256={actual}")


if __name__ == "__main__":
    main()
