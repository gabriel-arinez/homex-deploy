#!/usr/bin/env python3
"""Contrato estático D03 para media productiva local persistente."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(text: str, fragment: str, source: str) -> None:
    if fragment not in text:
        raise SystemExit(f"Falta {fragment!r} en {source}")


def reject(text: str, fragment: str, source: str) -> None:
    if fragment in text:
        raise SystemExit(f"Valor prohibido {fragment!r} en {source}")


def media_mount(service: dict) -> dict:
    matches = [
        volume
        for volume in service.get("volumes", [])
        if volume.get("target") == "/var/lib/homex/media"
    ]
    if len(matches) != 1:
        raise SystemExit(f"Se esperaba un único mount de media, se obtuvo {matches!r}")
    return matches[0]


def main() -> None:
    production = (ROOT / "compose.d03-media.yml").read_text()
    nginx = (ROOT / "nginx/default.conf").read_text()
    env_text = (ROOT / ".env.example").read_text()

    for fragment in (
        "DJANGO_SETTINGS_MODULE: config.settings.production",
        "HOMEX_MEDIA_STORAGE:",
        "HOMEX_MEDIA_HOST_PATH:",
        "target: /var/lib/homex/media",
        "read_only: true",
    ):
        require(production, fragment, "compose.d03-media.yml")

    reject(production, "R2_ACCESS_KEY_ID:", "compose.d03-media.yml")
    reject(production, "R2_SECRET_ACCESS_KEY:", "compose.d03-media.yml")
    require(nginx, "location ^~ /media/", "nginx/default.conf")
    require(nginx, "alias /var/lib/homex/media/;", "nginx/default.conf")

    for fragment in (
        "HOMEX_MEDIA_STORAGE=filesystem",
        "HOMEX_MEDIA_HOST_PATH=/srv/homex/media",
        "HOMEX_MEDIA_ROOT=/var/lib/homex/media",
        "HOMEX_MEDIA_URL=/media/",
        "HOMEX_HTTPS_ENABLED=0",
    ):
        require(env_text, fragment, ".env.example")

    compose = os.environ.get("COMPOSE_BIN", "docker compose").split()
    output = subprocess.check_output(
        [
            *compose,
            "-f",
            "docker-compose.yml",
            "-f",
            "compose.d03-media.yml",
            "--env-file",
            ".env.example",
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
    api = config["services"]["api"]
    proxy = config["services"]["frontend-proxy"]
    worker = config["services"]["worker"]

    assert api["environment"]["DJANGO_SETTINGS_MODULE"] == "config.settings.production"
    assert api["environment"]["HOMEX_MEDIA_STORAGE"] == "filesystem"
    assert api["environment"]["HOMEX_MEDIA_ROOT"] == "/var/lib/homex/media"
    assert api["environment"]["HOMEX_HTTPS_ENABLED"] == "0"

    api_media = media_mount(api)
    proxy_media = media_mount(proxy)

    expected_source = os.environ.get("HOMEX_MEDIA_HOST_PATH", "/srv/homex/media")

    assert api_media["type"] == "bind"
    assert api_media["source"] == expected_source
    assert not api_media.get("read_only", False)

    assert proxy_media["type"] == "bind"
    assert proxy_media["source"] == expected_source
    assert proxy_media.get("read_only") is True

    if any(
        volume.get("target") == "/var/lib/homex/media"
        for volume in worker.get("volumes", [])
    ):
        raise SystemExit("worker no debe montar media comercial persistente")

    for service_name in ("api", "worker", "migrate", "publisher", "reconciler", "cleanup"):
        environment = config["services"][service_name].get("environment", {})
        if any(name.startswith("R2_") for name in environment):
            raise SystemExit(f"{service_name} recibió credenciales R2 en modo filesystem")

    print("d03-media-contract-ok")


if __name__ == "__main__":
    main()
