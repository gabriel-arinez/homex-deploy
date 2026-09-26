#!/usr/bin/env python3
"""Verifica el artefacto ASR fijado en el manifiesto D01."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

import yaml


MAX_POINTER_BYTES = 4096
REQUIRED_LOCAL_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")


def manifest_asr() -> dict[str, str]:
    manifest = yaml.safe_load(Path("releases/manifest.yaml").read_text(encoding="utf-8"))
    return manifest["runtime"]["asr_model"]


def split_version(version: str) -> tuple[str, str]:
    try:
        repository, revision = version.rsplit("@", 1)
    except ValueError as exc:
        raise SystemExit(f"Versión ASR sin revisión inmutable: {version}") from exc
    if not repository or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SystemExit(f"Versión ASR inválida: {version}")
    return repository, revision


def verify_local(expected: dict[str, str]) -> None:
    model_root = Path(os.environ.get("ASR_MODEL_SOURCE", "artifacts/asr/faster-whisper-small"))
    missing = [name for name in REQUIRED_LOCAL_FILES if not (model_root / name).is_file()]
    if missing:
        raise SystemExit(f"Artefacto ASR incompleto; faltan: {', '.join(missing)}")

    digest = hashlib.sha256()
    with (model_root / "model.bin").open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected["sha256"]:
        raise SystemExit(f"Hash ASR distinto: expected={expected['sha256']}, actual={actual}")
    print(f"asr-model-ok: {expected['version']} sha256={actual}")


def verify_remote_pointer(expected: dict[str, str]) -> None:
    repository, revision = split_version(expected["version"])
    url = f"https://huggingface.co/{repository}/raw/{revision}/model.bin"
    request = Request(url, headers={"User-Agent": "homex-deploy-d01/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = response.read(MAX_POINTER_BYTES + 1)
    if len(payload) > MAX_POINTER_BYTES:
        raise SystemExit("El endpoint raw no devolvió un puntero LFS acotado")

    text = payload.decode("utf-8", errors="strict")
    match = re.search(r"^oid sha256:([0-9a-f]{64})$", text, flags=re.MULTILINE)
    if not match:
        raise SystemExit("No se encontró oid sha256 en el puntero LFS remoto")
    actual = match.group(1)
    if actual != expected["sha256"]:
        raise SystemExit(
            f"OID LFS ASR distinto: expected={expected['sha256']}, actual={actual}"
        )
    print(f"asr-model-pointer-ok: {expected['version']} sha256={actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--remote-lfs-pointer",
        action="store_true",
        help="Verifica el oid LFS del model.bin del snapshot remoto sin descargar 484 MB.",
    )
    args = parser.parse_args()

    expected = manifest_asr()
    if args.remote_lfs_pointer:
        verify_remote_pointer(expected)
    else:
        verify_local(expected)


if __name__ == "__main__":
    main()
