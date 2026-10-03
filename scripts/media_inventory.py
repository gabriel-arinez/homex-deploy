#!/usr/bin/env python3
"""Inventario reproducible y extracción segura de media HOMEX."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tarfile
from pathlib import Path, PurePosixPath

AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm"}
RESERVED_PARTS = {"audio", "audio-temporal", "audio_temporal", "asr", "asr-temporal"}


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"Ruta insegura en media: {value!r}")
    if any(part.lower() in RESERVED_PARTS for part in path.parts):
        raise ValueError(f"Ruta temporal/ASR prohibida en media: {value!r}")
    if path.suffix.lower() in AUDIO_SUFFIXES:
        raise ValueError(f"Audio prohibido en backup de media: {value!r}")
    return path


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def build_inventory(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"No existe el directorio de media: {root}")
    entries = []
    for path in sorted(root.rglob("*")):
        relative = safe_relative(path.relative_to(root).as_posix())
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"No se respaldan symlinks en media: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Tipo de archivo no soportado en media: {relative}")
        entries.append(
            {
                "path": str(relative),
                "sha256": digest(path),
                "size": path.stat().st_size,
                "mode": f"{stat.S_IMODE(mode):04o}",
            }
        )
    return {"schema_version": "1.0", "algorithm": "sha256", "files": entries}


def verify_inventory(root: Path, manifest: dict) -> None:
    actual = build_inventory(root)
    if actual != manifest:
        expected_by_path = {item["path"]: item for item in manifest.get("files", [])}
        actual_by_path = {item["path"]: item for item in actual["files"]}
        missing = sorted(expected_by_path.keys() - actual_by_path.keys())
        unexpected = sorted(actual_by_path.keys() - expected_by_path.keys())
        changed = sorted(
            path
            for path in expected_by_path.keys() & actual_by_path.keys()
            if expected_by_path[path] != actual_by_path[path]
        )
        raise ValueError(
            f"Inventario de media no coincide; faltantes={missing}, "
            f"no_referenciados={unexpected}, modificados={changed}"
        )


def create_archive(root: Path, archive: Path) -> None:
    root = root.resolve()
    build_inventory(root)
    with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as output:
        for path in sorted(root.rglob("*")):
            relative = safe_relative(path.relative_to(root).as_posix())
            if path.is_symlink():
                raise ValueError(f"No se respaldan symlinks en media: {relative}")
            info = output.gettarinfo(str(path), arcname=str(relative))
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            if info.isfile():
                with path.open("rb") as source:
                    output.addfile(info, source)
            elif info.isdir():
                output.addfile(info)
            else:
                raise ValueError(f"Tipo no soportado en media: {relative}")


def extract_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            safe_relative(member.name)
            if not (member.isfile() or member.isdir()):
                raise ValueError(
                    f"Entrada no soportada en archivo de media: {member.name}"
                )
        for member in members:
            relative = safe_relative(member.name)
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, stat.S_IMODE(member.mode))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = source.extractfile(member)
            if extracted is None:
                raise ValueError(f"No se pudo leer {member.name}")
            with extracted, target.open("wb") as output:
                shutil.copyfileobj(extracted, output)
            os.chmod(target, stat.S_IMODE(member.mode))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("root", type=Path)
    inventory.add_argument("output", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("root", type=Path)
    verify.add_argument("manifest", type=Path)
    archive = subparsers.add_parser("archive")
    archive.add_argument("root", type=Path)
    archive.add_argument("output", type=Path)
    extract = subparsers.add_parser("extract")
    extract.add_argument("archive", type=Path)
    extract.add_argument("destination", type=Path)
    args = parser.parse_args()

    if args.command == "inventory":
        args.output.write_text(
            json.dumps(build_inventory(args.root), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    elif args.command == "verify":
        verify_inventory(
            args.root, json.loads(args.manifest.read_text(encoding="utf-8"))
        )
        print("media-checksums-ok")
    elif args.command == "archive":
        create_archive(args.root, args.output)
    elif args.command == "extract":
        extract_archive(args.archive, args.destination)


if __name__ == "__main__":
    main()
