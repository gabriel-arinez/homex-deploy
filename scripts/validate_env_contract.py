#!/usr/bin/env python3
"""Valida que deploy no reintroduzca variables inventadas o duplicadas."""

from pathlib import Path


EXPECTED = {
    "COMPOSE_PROJECT_NAME", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
    "POSTGRES_PORT", "REDIS_PORT", "DJANGO_SECRET_KEY", "DJANGO_SETTINGS_MODULE",
    "DATABASE_URL", "DJANGO_ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS", "CELERY_BROKER_URL",
    "HOMEX_AUDIO_TEMP_ROOT", "HOMEX_AUDIO_MAX_BYTES", "HOMEX_AUDIO_TTL_SECONDS",
    "HOMEX_OUTBOX_RECONCILE_SECONDS", "HOMEX_ASR_MODEL_PATH", "HOMEX_ASR_DEVICE",
    "HOMEX_ASR_COMPUTE_TYPE", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME", "HOMEX_MEDIA_PUBLIC_DOMAIN", "VITE_API_BASE_URL",
}


def main() -> None:
    names: list[str] = []
    for raw_line in Path(".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            names.append(line.split("=", 1)[0])

    duplicates = sorted({name for name in names if names.count(name) > 1})
    actual = set(names)
    if duplicates or actual != EXPECTED:
        raise SystemExit(
            f"Contrato env inválido; duplicadas={duplicates}, "
            f"faltantes={sorted(EXPECTED - actual)}, inesperadas={sorted(actual - EXPECTED)}"
        )
    print(f"env-contract-ok: {len(names)} variables únicas")


if __name__ == "__main__":
    main()
