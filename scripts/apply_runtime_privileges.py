#!/usr/bin/env python3
"""Aplica el contrato SQL propiedad de backend con el rol migrador."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variable requerida: {name}")
    return value


def main() -> None:
    sql_path = Path("/app/docs/sql/privilegios_runtime.sql")
    if not sql_path.is_file():
        raise RuntimeError(f"No existe el contrato backend: {sql_path}")

    migrator = required("HOMEX_DB_MIGRATOR_USER")
    runtime = required("HOMEX_DB_RUNTIME_USER")
    with psycopg.connect(required("DATABASE_URL"), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('homex.migrator_role', %s, false)", (migrator,))
            cursor.execute("SELECT set_config('homex.runtime_role', %s, false)", (runtime,))
            cursor.execute(sql_path.read_text(encoding="utf-8"))
    print("runtime-privileges-ok")


if __name__ == "__main__":
    main()
