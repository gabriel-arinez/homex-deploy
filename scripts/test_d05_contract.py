#!/usr/bin/env python3
"""Gate estático para el contrato operativo D05."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *fragments: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(f"Falta {fragment!r} en {path}")


def main() -> None:
    require(
        "scripts/backup.sh",
        "pg_dump --format=custom",
        "pg_restore --list",
        "media_inventory.py inventory",
        "media_inventory.py archive",
        "release-manifest.yaml",
        "audio-temporal",
        "sha256sum -c SHA256SUMS",
        "HOMEX_BACKUP_RETENTION_DAYS",
    )
    require(
        "scripts/restore.sh",
        "--confirm",
        "sha256sum -c SHA256SUMS",
        "pg_restore --list",
        'psql --username "$POSTGRES_USER" --dbname postgres',
        "pg_restore --exit-on-error",
        "media_inventory.py verify",
        "verify_media_integrity.py",
        "run_compose run --rm migrate",
        "run_compose run --rm grant-runtime",
    )
    restore_text = (ROOT / "scripts/restore.sh").read_text(encoding="utf-8")
    if restore_text.index("media_inventory.py verify") > restore_text.index("dropdb --force"):
        raise SystemExit(
            "restore.sh debe verificar completamente la media antes de destruir PostgreSQL"
        )

    require(
        "scripts/deploy.sh",
        "scripts/backup.sh",
        "run_compose run --rm migrate",
        "scripts/smoke.sh",
    )
    require(
        "scripts/smoke.sh",
        "migrate --check",
        "verify_media_integrity.py",
        "homex-smoke-ok",
    )
    require(
        ".github/workflows/ci.yml",
        "recovery:",
        "python3 scripts/test_media_inventory.py",
        "sh scripts/test_d05_recovery.sh",
    )
    require(
        "docs/implementacion/D05_RECOVERY.md",
        "PostgreSQL",
        "media",
        "rollback",
        "audio",
    )
    print("d05-recovery-contract-ok")


if __name__ == "__main__":
    main()
