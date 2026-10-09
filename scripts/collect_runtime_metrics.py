#!/usr/bin/env python3
"""Recolecta métricas operativas HOMEX sin exponer secretos ni datos comerciales."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from redis import Redis  # noqa: E402

METRICS_PATH = Path(os.environ.get("HOMEX_METRICS_PATH", "/var/lib/homex/metrics/homex.prom"))
MEDIA_PATH = Path(os.environ.get("HOMEX_MEDIA_ROOT", "/var/lib/homex/media"))
AUDIO_PATH = Path(os.environ.get("HOMEX_AUDIO_TEMP_ROOT", "/var/lib/homex/audio-temporal"))
WARN_PERCENT = float(os.environ.get("HOMEX_STORAGE_WARN_PERCENT", "80"))
CRITICAL_PERCENT = float(os.environ.get("HOMEX_STORAGE_CRITICAL_PERCENT", "90"))


def disk_metrics(label: str, path: Path) -> tuple[list[str], dict[str, object]]:
    total, used, free = shutil.disk_usage(path)
    percent = (used * 100 / total) if total else 100.0
    state = 2 if percent >= CRITICAL_PERCENT else 1 if percent >= WARN_PERCENT else 0
    lines = [
        f'homex_storage_bytes{{storage="{label}",kind="total"}} {total}',
        f'homex_storage_bytes{{storage="{label}",kind="used"}} {used}',
        f'homex_storage_bytes{{storage="{label}",kind="free"}} {free}',
        f'homex_storage_used_percent{{storage="{label}"}} {percent:.4f}',
        f'homex_storage_state{{storage="{label}"}} {state}',
    ]
    return lines, {"path": str(path), "used_percent": round(percent, 2), "state": state}


def collect() -> tuple[str, dict[str, object]]:
    started = time.monotonic()
    health: dict[str, object] = {"postgres": False, "redis": False, "api": False}
    lines = ["# HELP homex_dependency_up Dependencia operativa disponible (1/0).", "# TYPE homex_dependency_up gauge"]

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1, pg_database_size(current_database())")
            _, db_size = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM trabajos_outbox WHERE publicado_at IS NULL")
            outbox_pending = cursor.fetchone()[0]
        health["postgres"] = True
        lines.extend((f"homex_postgresql_database_bytes {db_size}", f"homex_outbox_pending {outbox_pending}"))
    except Exception as exc:  # la métrica conserva el tipo, nunca DSN/credenciales
        health["postgres_error"] = type(exc).__name__

    try:
        redis_client = Redis.from_url(os.environ["CELERY_BROKER_URL"], socket_timeout=2)
        health["redis"] = bool(redis_client.ping())
    except Exception as exc:
        health["redis_error"] = type(exc).__name__

    try:
        request = urllib.request.Request(
            "http://api:8000/api/v1/health/",
            headers={"Host": "homex.internal", "X-Forwarded-Proto": "https"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            health["api"] = response.status == 200
    except Exception as exc:
        health["api_error"] = type(exc).__name__

    for dependency in ("postgres", "redis", "api"):
        lines.append(f'homex_dependency_up{{dependency="{dependency}"}} {int(bool(health[dependency]))}')

    storage: dict[str, object] = {}
    for label, path in (("media", MEDIA_PATH), ("audio_temporal", AUDIO_PATH)):
        try:
            disk_lines, detail = disk_metrics(label, path)
            lines.extend(disk_lines)
            storage[label] = detail
        except Exception as exc:
            lines.append(f'homex_storage_state{{storage="{label}"}} 2')
            storage[label] = {"path": str(path), "state": 2, "error": type(exc).__name__}

    healthy = all(bool(health[name]) for name in ("postgres", "redis", "api")) and all(
        int(item.get("state", 2)) < 2 for item in storage.values() if isinstance(item, dict)
    )
    duration = time.monotonic() - started
    lines.extend(
        (
            f"homex_monitor_last_success_timestamp_seconds {int(time.time()) if healthy else 0}",
            f"homex_monitor_collection_duration_seconds {duration:.6f}",
            f"homex_monitor_collection_healthy {int(healthy)}",
        )
    )
    event = {
        "event": "homex_runtime_metrics",
        "healthy": healthy,
        "collector_alive": True,
        "dependencies": health,
        "storage": storage,
        "duration_ms": round(duration * 1000, 2),
    }
    return "\n".join(lines) + "\n", event


def write_atomic(content: str) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = METRICS_PATH.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(METRICS_PATH)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop-seconds", type=int, default=0)
    args = parser.parse_args()
    while True:
        metrics, event = collect()
        write_atomic(metrics)
        print(json.dumps(event, sort_keys=True), flush=True)
        if not args.loop_seconds:
            return 0 if event["healthy"] else 1
        time.sleep(max(args.loop_seconds, 10))


if __name__ == "__main__":
    raise SystemExit(main())
