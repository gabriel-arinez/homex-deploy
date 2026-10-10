#!/usr/bin/env python3
"""Perfil agregado del ASR real; no serializa audio, texto, paths ni secretos."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time


def rss_mib() -> float:
    # Linux ru_maxrss se expresa en KiB.
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.audio.is_file():
        raise SystemExit("Falta audio autorizado para el perfil D07")

    sys.path.insert(0, os.environ.get("HOMEX_BACKEND_ROOT", "/app"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
    import django

    django.setup()
    from apps.capturas.asr import construir_servicio_asr

    before = rss_mib()
    cpu_before = time.process_time()
    started = time.perf_counter()
    service = construir_servicio_asr()
    load_seconds = time.perf_counter() - started
    after_load = rss_mib()

    durations: list[float] = []
    with tempfile.TemporaryDirectory(prefix="homex-d07-asr-") as temp:
        root = Path(temp)
        for index in range(2):
            probe = root / f"probe-{index}.wav"
            shutil.copyfile(args.audio, probe)
            transcribe_started = time.perf_counter()
            service.transcribe(probe)
            durations.append(time.perf_counter() - transcribe_started)
            if probe.exists():
                raise SystemExit("El servicio ASR conservó un temporal del perfil")
        remaining_audio = sum(1 for item in root.rglob("*") if item.is_file())

    # El gate aislado crea este fixture efímero; nunca borrar audio del operador.
    if args.audio == Path("/evidence/profile.wav"):
        args.audio.unlink(missing_ok=True)
    evidence = {
        "schema_version": "1.0",
        "component": "homex-asr",
        "device": os.environ.get("HOMEX_ASR_DEVICE", "cpu"),
        "compute_type": os.environ.get("HOMEX_ASR_COMPUTE_TYPE", "int8"),
        "worker_concurrency": 1,
        "model_load_seconds": round(load_seconds, 6),
        "first_transcription_seconds": round(durations[0], 6),
        "warm_transcription_seconds": round(durations[1], 6),
        "process_cpu_seconds": round(time.process_time() - cpu_before, 6),
        "rss_before_mib": before,
        "rss_after_load_mib": after_load,
        "rss_peak_mib": rss_mib(),
        "audio_files_remaining": remaining_audio,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print("d07-asr-profile-ok")


if __name__ == "__main__":
    main()
