#!/usr/bin/env python3
"""Valida contratos de entorno staging y producción sin secretos reales."""

from pathlib import Path


STAGING_EXPECTED = {
    "COMPOSE_PROJECT_NAME",
    "BACKEND_CONTEXT",
    "FRONTEND_CONTEXT",
    "HOMEX_BACKEND_IMAGE_TAG",
    "HOMEX_FRONTEND_IMAGE_TAG",
    "BACKEND_PORT",
    "STAGING_HTTP_BIND",
    "STAGING_HTTP_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_PORT",
    "HOMEX_DB_MIGRATOR_USER",
    "HOMEX_DB_MIGRATOR_PASSWORD",
    "HOMEX_DB_RUNTIME_USER",
    "HOMEX_DB_RUNTIME_PASSWORD",
    "HOMEX_MIGRATOR_DATABASE_URL",
    "REDIS_PORT",
    "DJANGO_SECRET_KEY",
    "DJANGO_SETTINGS_MODULE",
    "ASR_MODEL_SOURCE",
    "DATABASE_URL",
    "DJANGO_ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CELERY_BROKER_URL",
    "HOMEX_AUDIO_TEMP_ROOT",
    "HOMEX_AUDIO_MAX_BYTES",
    "HOMEX_AUDIO_TTL_SECONDS",
    "HOMEX_OUTBOX_RECONCILE_SECONDS",
    "HOMEX_ASR_MODEL_PATH",
    "HOMEX_ASR_DEVICE",
    "HOMEX_ASR_COMPUTE_TYPE",
    "HOMEX_MEDIA_STORAGE",
    "HOMEX_MEDIA_HOST_PATH",
    "HOMEX_MEDIA_ROOT",
    "HOMEX_MEDIA_URL",
    "HOMEX_HTTPS_ENABLED",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
    "HOMEX_MEDIA_PUBLIC_DOMAIN",
    "VITE_API_BASE_URL",
    "GUNICORN_WORKERS",
    "GUNICORN_TIMEOUT",
}

PRODUCTION_EXPECTED = {
    "COMPOSE_PROJECT_NAME",
    "BACKEND_CONTEXT",
    "FRONTEND_CONTEXT",
    "HOMEX_BACKEND_IMAGE_TAG",
    "HOMEX_FRONTEND_IMAGE_TAG",
    "HOMEX_PRIVATE_HOSTNAME",
    "HOMEX_PRIVATE_ORIGIN",
    "HOMEX_PRIVATE_BIND",
    "HOMEX_PRIVATE_PORT",
    "HOMEX_TLS_CERT_HOST_PATH",
    "HOMEX_TLS_KEY_HOST_PATH",
    "HOMEX_CA_CERT_HOST_PATH",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "HOMEX_DB_MIGRATOR_USER",
    "HOMEX_DB_MIGRATOR_PASSWORD",
    "HOMEX_DB_RUNTIME_USER",
    "HOMEX_DB_RUNTIME_PASSWORD",
    "HOMEX_MIGRATOR_DATABASE_URL",
    "DATABASE_URL",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "GUNICORN_WORKERS",
    "GUNICORN_TIMEOUT",
    "CELERY_BROKER_URL",
    "HOMEX_MEDIA_STORAGE",
    "HOMEX_MEDIA_HOST_PATH",
    "HOMEX_MEDIA_ROOT",
    "HOMEX_MEDIA_URL",
    "HOMEX_HTTPS_ENABLED",
    "HOMEX_AUDIO_TEMP_ROOT",
    "HOMEX_AUDIO_MAX_BYTES",
    "HOMEX_AUDIO_TTL_SECONDS",
    "HOMEX_OUTBOX_RECONCILE_SECONDS",
    "ASR_MODEL_SOURCE",
    "HOMEX_ASR_MODEL_PATH",
    "HOMEX_ASR_DEVICE",
    "HOMEX_ASR_COMPUTE_TYPE",
    "VITE_API_BASE_URL",
    "HOMEX_POSTGRES_CPUS",
    "HOMEX_POSTGRES_MEMORY",
    "HOMEX_REDIS_CPUS",
    "HOMEX_REDIS_MEMORY",
    "HOMEX_API_CPUS",
    "HOMEX_API_MEMORY",
    "HOMEX_WORKER_CPUS",
    "HOMEX_WORKER_MEMORY",
    "HOMEX_PROXY_CPUS",
    "HOMEX_PROXY_MEMORY",
    "CLOUDFLARED_VERSION",
    "CLOUDFLARED_AMD64_SHA256",
    "CLOUDFLARED_ARM64_SHA256",
    "CLOUDFLARE_TUNNEL_TOKEN_FILE",
}


def names(path: str) -> list[str]:
    result: list[str] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            result.append(line.split("=", 1)[0])
    return result


def validate(path: str, expected: set[str]) -> None:
    found = names(path)
    duplicates = sorted({name for name in found if found.count(name) > 1})
    actual = set(found)
    if duplicates or actual != expected:
        raise SystemExit(
            f"{path}: contrato env inválido; duplicadas={duplicates}, "
            f"faltantes={sorted(expected - actual)}, inesperadas={sorted(actual - expected)}"
        )


def main() -> None:
    validate(".env.example", STAGING_EXPECTED)
    validate(".env.production.example", PRODUCTION_EXPECTED)

    production = Path(".env.production.example").read_text(encoding="utf-8")
    for forbidden in (
        "CLOUDFLARE_TUNNEL_TOKEN=",
        "R2_ACCESS_KEY_ID=",
        "R2_SECRET_ACCESS_KEY=",
        "HOMEX_MEDIA_PUBLIC_DOMAIN=",
    ):
        if forbidden in production:
            raise SystemExit(f".env.production.example contiene variable prohibida: {forbidden}")

    print(
        "env-contract-ok: "
        f"{len(STAGING_EXPECTED)} staging + {len(PRODUCTION_EXPECTED)} producción"
    )


if __name__ == "__main__":
    main()
