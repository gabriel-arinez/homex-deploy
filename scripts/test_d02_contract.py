#!/usr/bin/env python3
"""Contrato estático del staging D02 y su frontera de seguridad."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(text: str, fragment: str, source: str) -> None:
    if fragment not in text:
        raise SystemExit(f"Falta {fragment!r} en {source}")


def reject(text: str, fragment: str, source: str) -> None:
    if fragment in text:
        raise SystemExit(f"Valor prohibido {fragment!r} en {source}")


def main() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    nginx = (ROOT / "nginx/default.conf").read_text()
    backend_image = (ROOT / "docker/backend.Dockerfile").read_text()
    frontend_image = (ROOT / "docker/frontend.Dockerfile").read_text()
    env = (ROOT / ".env.example").read_text()

    for fragment in (
        "gunicorn",
        "connection.ensure_connection()",
        "frontend-proxy:",
        "VITE_API_BASE_URL:",
        "media_persistente:/var/lib/homex/media:ro",
    ):
        require(compose, fragment, "docker-compose.yml")
    reject(compose, 'manage.py", "runserver', "docker-compose.yml")

    for fragment in (
        "location ^~ /api/",
        "proxy_intercept_errors off",
        "proxy_request_buffering off",
        "client_max_body_size 26m",
        "location @spa",
        "max-age=31536000, immutable",
        "no-store, no-cache, must-revalidate",
        "gzip on",
        "X-Content-Type-Options",
    ):
        require(nginx, fragment, "nginx/default.conf")
    reject(nginx, "add_header Access-Control-Allow-Origin", "nginx/default.conf")

    require(backend_image, "--require-hashes", "docker/backend.Dockerfile")
    require(backend_image, "USER 10001:10001", "docker/backend.Dockerfile")
    require(frontend_image, "npm ci --ignore-scripts", "docker/frontend.Dockerfile")
    require(frontend_image, "USER 101:101", "docker/frontend.Dockerfile")
    for image in ("node:", "nginxinc/nginx-unprivileged:"):
        line = next(line for line in frontend_image.splitlines() if line.startswith(f"FROM {image}"))
        require(line, "@sha256:", "docker/frontend.Dockerfile")

    require(env, "CORS_ALLOWED_ORIGINS=http://localhost:8080", ".env.example")
    reject(env, "CORS_ALLOWED_ORIGINS=*", ".env.example")
    reject(env, "CSRF_TRUSTED_ORIGINS=*", ".env.example")
    print("d02-contract-tests-ok")


if __name__ == "__main__":
    main()
