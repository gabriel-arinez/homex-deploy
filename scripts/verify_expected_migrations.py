#!/usr/bin/env python3
"""Compara las migraciones hoja HOMEX con el manifiesto montado."""

from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0, "/app")

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.integration")
django.setup()

from django.db import connection  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402


def expected_from_manifest(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    in_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "  expected_migrations:":
            in_block = True
            continue
        if in_block and not line.startswith("    "):
            break
        if in_block and ": " in line:
            app, migration = line.strip().split(": ", 1)
            expected[app] = migration
    if not expected:
        raise RuntimeError("El manifiesto no contiene expected_migrations")
    return expected


def main() -> None:
    expected = expected_from_manifest(Path("/release/manifest.yaml"))
    loader = MigrationLoader(connection)
    all_leaves = dict(loader.graph.leaf_nodes())
    actual = {app: all_leaves.get(app) for app in expected}
    if actual != expected:
        raise SystemExit(f"Migraciones hoja distintas: expected={expected!r}, actual={actual!r}")

    applied = set(loader.applied_migrations)
    missing = sorted(
        (app, migration)
        for app, migration in expected.items()
        if (app, migration) not in applied
    )
    if missing:
        raise SystemExit(f"Migraciones hoja no aplicadas: {missing!r}")
    print(f"expected-migrations-ok: {len(expected)} apps HOMEX")


if __name__ == "__main__":
    main()
