#!/usr/bin/env python3
"""Contrato estático/Compose de D04 para release candidate privada."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SHA = "9ce723048d98a3925be45d9c359a25e6be7b19f3"
FRONTEND_SHA = "deba1de244395dbdcb266f03026630b403768d71"
NLP_SHA = "8d1750b2d1d26f6d90da10603216b7926bdaf820"
PRIVATE_HOSTNAME = "homex.internal"
PRIVATE_ORIGIN = "http://homex.internal:8080"


def require(text: str, fragment: str, source: str) -> None:
    if fragment not in text:
        raise SystemExit(f"Falta {fragment!r} en {source}")


def reject(text: str, fragment: str, source: str) -> None:
    if fragment in text:
        raise SystemExit(f"Valor prohibido {fragment!r} en {source}")


def main() -> None:
    env = (ROOT / ".env.production.example").read_text()
    overlay = (ROOT / "compose.production.yml").read_text()
    unit = (ROOT / "systemd/homex-cloudflared.service").read_text()
    installer = (ROOT / "scripts/install_cloudflared.sh").read_text()
    frontend_image = (ROOT / "docker/frontend.Dockerfile").read_text()
    manifest = (ROOT / "releases/manifest.yaml").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    for fragment in (
        f"HOMEX_PRIVATE_HOSTNAME={PRIVATE_HOSTNAME}",
        f"HOMEX_PRIVATE_ORIGIN={PRIVATE_ORIGIN}",
        "HOMEX_PRIVATE_BIND=127.0.0.1",
        "HOMEX_PRIVATE_PORT=8080",
        f"DJANGO_ALLOWED_HOSTS={PRIVATE_HOSTNAME},localhost,127.0.0.1,api",
        f"CORS_ALLOWED_ORIGINS={PRIVATE_ORIGIN}",
        f"VITE_API_BASE_URL={PRIVATE_ORIGIN}",
        "HOMEX_HTTPS_ENABLED=0",
        "CLOUDFLARED_VERSION=2026.9.2",
    ):
        require(env, fragment, ".env.production.example")

    for forbidden in (
        "CLOUDFLARE_TUNNEL_TOKEN=",
        "R2_ACCESS_KEY_ID=",
        "R2_SECRET_ACCESS_KEY=",
    ):
        reject(env, forbidden, ".env.production.example")

    for fragment in (
        "ports: !reset []",
        "HOMEX_PRIVATE_BIND",
        "HOMEX_PRIVATE_PORT",
        "HOMEX_API_CPUS",
        "HOMEX_WORKER_CPUS",
        "HOMEX_POSTGRES_CPUS",
    ):
        require(overlay, fragment, "compose.production.yml")

    require(unit, "--token-file /etc/homex/cloudflared/tunnel-token", "systemd unit")
    reject(unit, "--token ", "systemd unit")
    reject(unit, "TUNNEL_TOKEN=", "systemd unit")

    for fragment in (
        "2026.9.2",
        "03f1f25d1cc93b9ad6c60569d44060bc4f17ed97075760ed8cfca4b12dcd68cc",
        "3d97437c71848bd8df68041e12436b484a661d95073ea1937f01a845ce88faa3",
        "sha256sum --check --status",
    ):
        require(installer, fragment, "scripts/install_cloudflared.sh")

    require(frontend_image, "find dist -type f -name '*.map'", "docker/frontend.Dockerfile")

    for sha in (BACKEND_SHA, FRONTEND_SHA, NLP_SHA):
        require(manifest, sha, "releases/manifest.yaml")
    for sha in (BACKEND_SHA, FRONTEND_SHA):
        require(workflow, sha, ".github/workflows/ci.yml")

    output = subprocess.check_output(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "compose.production.yml",
            "--env-file",
            ".env.production.example",
            "--profile",
            "operations",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        text=True,
    )
    config = json.loads(output)

    for service_name in ("postgres", "redis", "api"):
        if config["services"][service_name].get("ports"):
            raise SystemExit(f"{service_name} expone ports en producción privada")

    proxy_ports = config["services"]["frontend-proxy"].get("ports", [])
    if len(proxy_ports) != 1:
        raise SystemExit(f"frontend-proxy debe exponer un único listener local: {proxy_ports!r}")
    port = proxy_ports[0]
    assert str(port["target"]) == "8080"
    assert str(port["published"]) == "8080"
    assert port.get("host_ip") == "127.0.0.1"

    api_env = config["services"]["api"]["environment"]
    assert api_env["DJANGO_SETTINGS_MODULE"] == "config.settings.production"
    assert PRIVATE_HOSTNAME in api_env["DJANGO_ALLOWED_HOSTS"].split(",")
    assert api_env["CORS_ALLOWED_ORIGINS"] == PRIVATE_ORIGIN
    assert api_env["HOMEX_HTTPS_ENABLED"] == "0"

    build_args = config["services"]["frontend-proxy"]["build"]["args"]
    assert build_args["VITE_API_BASE_URL"] == PRIVATE_ORIGIN

    if "beat" not in config["services"]:
        raise SystemExit("Falta el scheduler Celery beat en el perfil productivo")

    for service_name in ("postgres", "redis", "api", "worker", "frontend-proxy"):
        service = config["services"][service_name]
        deploy = service.get("deploy", {})
        limits = deploy.get("resources", {}).get("limits", {})
        if not limits:
            raise SystemExit(f"{service_name} no tiene límites CPU/RAM efectivos")

    print("d04-private-release-contract-ok")


if __name__ == "__main__":
    main()
