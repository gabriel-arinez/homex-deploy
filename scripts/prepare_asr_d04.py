#!/usr/bin/env python3
"""Descarga y verifica exactamente el snapshot ASR fijado para D04."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


REPOSITORY = "Systran/faster-whisper-small"
REVISION = "536b0662742c02347bc0e980a01041f333bce120"
MODEL_SHA256 = "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: prepare_asr_d04.py <directorio-destino>")

    destination = Path(sys.argv[1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=REPOSITORY,
        revision=REVISION,
        local_dir=destination,
    )

    missing = [name for name in REQUIRED_FILES if not (destination / name).is_file()]
    if missing:
        raise SystemExit(f"Artefacto ASR incompleto; faltan: {', '.join(missing)}")

    actual = sha256(destination / "model.bin")
    if actual != MODEL_SHA256:
        raise SystemExit(
            f"Hash ASR distinto: expected={MODEL_SHA256}, actual={actual}"
        )

    print(
        "d04-asr-model-ok "
        f"repository={REPOSITORY} revision={REVISION} sha256={actual}"
    )


if __name__ == "__main__":
    main()
