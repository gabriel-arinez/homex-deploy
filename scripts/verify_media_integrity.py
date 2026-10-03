#!/usr/bin/env python3
"""Audita coherencia bidireccional entre PostgreSQL y media filesystem."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, "/app")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from apps.catalogo.models import Producto
from apps.documentos.models import ArchivoAdjunto
from django.conf import settings

ALLOWED_VARIANTS = {"320.webp", "640.webp", "1280.webp"}


def normalized(key: str) -> str:
    path = PurePosixPath(str(key))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Key de media insegura: {key!r}")
    return str(path)


def audit() -> dict:
    root = Path(settings.MEDIA_ROOT).resolve()
    referenced: set[str] = set()

    for product in Producto.objects.exclude(imagen_principal="").exclude(
        imagen_principal=None
    ):
        referenced.add(normalized(product.imagen_principal.name))
        for key in (product.imagen_principal_variantes or {}).values():
            referenced.add(normalized(key))

    for attachment in ArchivoAdjunto.objects.exclude(ruta_storage=""):
        original = normalized(attachment.ruta_storage)
        referenced.add(original)
        parent = PurePosixPath(original).parent
        for variant in ALLOWED_VARIANTS:
            candidate = root / parent / variant
            if candidate.is_file():
                referenced.add(str(parent / variant))

    present: set[str] = set()
    unsafe: list[str] = []
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_symlink():
                unsafe.append(path.relative_to(root).as_posix())
            elif path.is_file():
                present.add(path.relative_to(root).as_posix())

    result = {
        "referenced": len(referenced),
        "present": len(present),
        "missing": sorted(referenced - present),
        "unreferenced": sorted(present - referenced),
        "unsafe": sorted(unsafe),
    }
    print(json.dumps(result, sort_keys=True))
    if result["missing"] or result["unreferenced"] or result["unsafe"]:
        raise SystemExit(1)
    print("db-media-integrity-ok")
    return result


if __name__ == "__main__":
    audit()
