#!/usr/bin/env python3
"""Contrato estático D07: fuentes, promoción, privacidad y recuperación."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BACKEND="bc375894036d30cefbc8cdf7c512315aaf1ab971"
FRONTEND="479a092462b36a90006eb1c52f9570ea63084bab"
NLP="79efeaf6a8ca738eb3abce414850f973b1962fd8"

def need(path: str, *parts: str) -> str:
    text=(ROOT/path).read_text(encoding="utf-8")
    for part in parts:
        if part not in text: raise SystemExit(f"Falta {part!r} en {path}")
    return text

def main() -> None:
    manifest=need("releases/manifest.yaml",'version: "0.7.0-d07-rc1"','status: candidate',BACKEND,FRONTEND,NLP,'api: homex/backend:d07-bc37589','frontend_proxy: homex/frontend-proxy:d07-479a092')
    if "latest" in manifest: raise SystemExit("El manifiesto D07 usa latest")
    schema=json.loads((ROOT/"releases/manifest.schema.json").read_text())
    released=json.dumps(schema)
    for part in ('digested_image','@sha256'):
        if part not in released: raise SystemExit("El estado released no exige digest")
    compose=need("docker-compose.yml",'--concurrency=1',BACKEND,FRONTEND)
    need("docker/backend.Dockerfile",'org.opencontainers.image.revision','$HOMEX_BACKEND_REVISION')
    need("docker/frontend.Dockerfile",'org.opencontainers.image.revision','$HOMEX_FRONTEND_REVISION')
    need("scripts/deploy.sh",'verify_release_images.py','scripts/backup.sh','scripts/smoke.sh')
    need("scripts/backup_offsite.sh",'sha256sum -c SHA256SUMS','--recipient','$recipient','homex-offsite-encrypted-ok')
    need("scripts/backup_and_offsite.sh",'scripts/backup.sh','scripts/backup_offsite.sh','homex-backup-and-offsite-ok')
    need("systemd/homex-backup.timer",'Persistent=true','America/La_Paz')
    profile=need("scripts/profile_asr_runtime.py",'worker_concurrency','audio_files_remaining','rss_peak_mib')
    for forbidden in ('\"transcript\":', '\"text\":', '\"audio_path\":'):
        if forbidden in profile: raise SystemExit(f"Perfil ASR expone {forbidden}")
    if 'networks: [data]' not in compose or 'internal: true' not in compose:
        raise SystemExit("Worker ASR debe permanecer en red interna sin salida directa")
    workflow=need(".github/workflows/ci.yml",BACKEND,FRONTEND,'d07-release-contract:','test_d07_offsite.sh')
    if 'ref: main' in workflow: raise SystemExit("CI D07 consume una rama flotante")
    print("d07-release-contract-ok")
if __name__ == "__main__": main()
