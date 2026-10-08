#!/usr/bin/env python3
"""Contrato estático/Compose de D04 para release candidate privada HTTPS."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SHA = "9ce723048d98a3925be45d9c359a25e6be7b19f3"
FRONTEND_SHA = "deba1de244395dbdcb266f03026630b403768d71"
NLP_SHA = "8d1750b2d1d26f6d90da10603216b7926bdaf820"
PRIVATE_HOSTNAME = "homex.internal"
PRIVATE_ORIGIN = "https://homex.internal"


def require(text: str, fragment: str, source: str) -> None:
    if fragment not in text:
        raise SystemExit(f"Falta {fragment!r} en {source}")


def reject(text: str, fragment: str, source: str) -> None:
    if fragment in text:
        raise SystemExit(f"Valor prohibido {fragment!r} en {source}")


def mount_for(service: dict, target: str) -> dict:
    matches = [volume for volume in service.get("volumes", []) if volume.get("target") == target]
    if len(matches) != 1:
        raise SystemExit(f"Se esperaba un mount para {target}: {matches!r}")
    return matches[0]


def main() -> None:
    env = (ROOT / ".env.production.example").read_text()
    overlay = (ROOT / "compose.production.yml").read_text()
    nginx = (ROOT / "nginx/production.conf").read_text()
    unit = (ROOT / "systemd/homex-cloudflared.service").read_text()
    installer = (ROOT / "scripts/install_cloudflared.sh").read_text()
    private_endpoint = (ROOT / "scripts/setup_private_endpoint.sh").read_text()
    tls_generator = (ROOT / "scripts/generate_internal_tls.sh").read_text()
    prepare_asr = (ROOT / "scripts/prepare_asr_d04.py").read_text()
    frontend_image = (ROOT / "docker/frontend.Dockerfile").read_text()
    manifest = (ROOT / "releases/manifest.yaml").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    for fragment in (
        f"HOMEX_PRIVATE_HOSTNAME={PRIVATE_HOSTNAME}",
        f"HOMEX_PRIVATE_ORIGIN={PRIVATE_ORIGIN}",
        "HOMEX_PRIVATE_BIND=10.254.254.1",
        "HOMEX_PRIVATE_PORT=443",
        "HOMEX_TLS_CERT_HOST_PATH=/etc/homex/tls/homex.internal.crt",
        "HOMEX_TLS_KEY_HOST_PATH=/etc/homex/tls/homex.internal.key",
        "HOMEX_CA_CERT_HOST_PATH=/etc/homex/tls/homex-root-ca.crt",
        f"DJANGO_ALLOWED_HOSTS={PRIVATE_HOSTNAME},localhost,127.0.0.1,api",
        f"CORS_ALLOWED_ORIGINS={PRIVATE_ORIGIN}",
        f"VITE_API_BASE_URL={PRIVATE_ORIGIN}",
        "HOMEX_HTTPS_ENABLED=1",
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
        "HOMEX_TLS_CERT_HOST_PATH",
        "HOMEX_TLS_KEY_HOST_PATH",
        "target: /etc/nginx/tls/tls.crt",
        "target: /etc/nginx/tls/tls.key",
        "./nginx/production.conf:/etc/nginx/conf.d/default.conf:ro",
        "HOMEX_API_CPUS",
        "HOMEX_WORKER_CPUS",
        "HOMEX_POSTGRES_CPUS",
    ):
        require(overlay, fragment, "compose.production.yml")

    for fragment in (
        "listen 8443 ssl;",
        "server_name homex.internal;",
        "ssl_certificate /etc/nginx/tls/tls.crt;",
        "ssl_certificate_key /etc/nginx/tls/tls.key;",
        "ssl_protocols TLSv1.2 TLSv1.3;",
        "proxy_set_header X-Forwarded-Proto https;",
        "microphone=(self)",
    ):
        require(nginx, fragment, "nginx/production.conf")

    require(
        unit,
        "--no-autoupdate tunnel --protocol http2 run --token-file "
        "/etc/homex/cloudflared/tunnel-token",
        "systemd unit",
    )
    reject(unit, "--token ", "systemd unit")
    reject(unit, "TUNNEL_TOKEN=", "systemd unit")

    for fragment in (
        "type dummy",
        "homex0",
        "homex-private",
        "10.254.254.1/32",
        "connection.autoconnect yes",
    ):
        require(private_endpoint, fragment, "scripts/setup_private_endpoint.sh")

    for fragment in (
        "2026.9.2",
        "ea2c9bb2d5017a796b64bf36e605d727accf76a5500014bb12952ce11ae1f932",
        "39f23e7c55ce2c2e502a0b3e070b978bf69135b19246b5b7581dadb94cf2144d",
        "sha256sum --check --status",
    ):
        require(installer, fragment, "scripts/install_cloudflared.sh")

    for fragment in (
        "HOMEX Local Root CA",
        "subjectAltName=DNS:$hostname",
        "extendedKeyUsage=serverAuth",
        "-days 365",
        "openssl verify -CAfile",
    ):
        require(tls_generator, fragment, "scripts/generate_internal_tls.sh")

    require(frontend_image, "find dist -type f -name '*.map'", "docker/frontend.Dockerfile")

    for sha in (BACKEND_SHA, FRONTEND_SHA, NLP_SHA):
        require(manifest, sha, "releases/manifest.yaml")

    for fragment in (
        "Systran/faster-whisper-small",
        "536b0662742c02347bc0e980a01041f333bce120",
        "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
    ):
        require(prepare_asr, fragment, "scripts/prepare_asr_d04.py")
        require(manifest, fragment, "releases/manifest.yaml")

    for image in (
        "api: homex/backend:d04-9ce7230",
        "worker: homex/backend:d04-9ce7230",
        "frontend_proxy: homex/frontend-proxy:d04-deba1de",
    ):
        require(manifest, image, "releases/manifest.yaml")

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

    proxy = config["services"]["frontend-proxy"]
    proxy_ports = proxy.get("ports", [])
    if len(proxy_ports) != 1:
        raise SystemExit(f"frontend-proxy debe exponer un único listener local: {proxy_ports!r}")
    port = proxy_ports[0]
    assert str(port["target"]) == "8443"
    assert str(port["published"]) == "443"
    assert port.get("host_ip") == "10.254.254.1"

    cert_mount = mount_for(proxy, "/etc/nginx/tls/tls.crt")
    key_mount = mount_for(proxy, "/etc/nginx/tls/tls.key")
    assert cert_mount["read_only"] is True
    assert key_mount["read_only"] is True

    api_env = config["services"]["api"]["environment"]
    assert api_env["DJANGO_SETTINGS_MODULE"] == "config.settings.production"
    assert PRIVATE_HOSTNAME in api_env["DJANGO_ALLOWED_HOSTS"].split(",")
    assert api_env["CORS_ALLOWED_ORIGINS"] == PRIVATE_ORIGIN
    assert api_env["HOMEX_HTTPS_ENABLED"] == "1"

    build_args = proxy["build"]["args"]
    assert build_args["VITE_API_BASE_URL"] == PRIVATE_ORIGIN

    if "beat" not in config["services"]:
        raise SystemExit("Falta el scheduler Celery beat en el perfil productivo")

    for service_name in ("postgres", "redis", "api", "worker", "frontend-proxy"):
        service = config["services"][service_name]
        deploy = service.get("deploy", {})
        limits = deploy.get("resources", {}).get("limits", {})
        cpu = service.get("cpus") or limits.get("cpus")
        memory = service.get("mem_limit") or limits.get("memory")
        if not cpu or not memory:
            raise SystemExit(
                f"{service_name} no tiene límites CPU/RAM efectivos: "
                f"cpus={cpu!r}, memory={memory!r}"
            )

    print("d04-private-https-release-contract-ok")


if __name__ == "__main__":
    main()
