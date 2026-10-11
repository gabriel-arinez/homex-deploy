#!/usr/bin/env python3
"""Contrato estático D07: fuentes, promoción, privacidad y recuperación."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BACKEND="3e05362ac49c170963a8dc1d32b4d612e491112f"
FRONTEND="479a092462b36a90006eb1c52f9570ea63084bab"
NLP="79efeaf6a8ca738eb3abce414850f973b1962fd8"

def need(path: str, *parts: str) -> str:
    text=(ROOT/path).read_text(encoding="utf-8")
    for part in parts:
        if part not in text: raise SystemExit(f"Falta {part!r} en {path}")
    return text

def main() -> None:
    manifest=need("releases/manifest.yaml",'version: "0.7.0-d07-rc2"','status: candidate',BACKEND,FRONTEND,NLP,'api: ghcr.io/gabriel-arinez/homex-backend:0.7.0-d07-rc2@sha256:0a9f7f0e7650304808fe8d99227648ef42b34507c11d3ed86adbd8176391166a','frontend_proxy: ghcr.io/gabriel-arinez/homex-frontend-proxy:0.7.0-d07-rc2@sha256:023cad7b1d64520e5e3d2d407d27ed6224c88ae1c2f4bcbd0b74c24b0bebe15c')
    if "latest" in manifest: raise SystemExit("El manifiesto D07 usa latest")
    schema=json.loads((ROOT/"releases/manifest.schema.json").read_text())
    released=json.dumps(schema)
    for part in ('digested_image','@sha256'):
        if part not in released: raise SystemExit("El estado released no exige digest")
    compose=need("docker-compose.yml",'--concurrency=1',BACKEND,FRONTEND)
    need("docker/backend.Dockerfile",'org.opencontainers.image.revision','$HOMEX_BACKEND_REVISION')
    need("docker/frontend.Dockerfile",'org.opencontainers.image.revision','$HOMEX_FRONTEND_REVISION')
    deploy=need("scripts/deploy.sh",'verify_release_images.py','scripts/backup.sh','scripts/smoke.sh',
                'migration_started=1','run_compose stop $stopped_writers',
                'run_compose run --rm migrate','run_compose run --rm grant-runtime',
                'NO reiniciar escritores D04')
    if not (deploy.index('scripts/backup.sh') < deploy.index('run_compose stop $stopped_writers')
            < deploy.index('migration_started=1') < deploy.index('run_compose run --rm migrate')
            < deploy.index('run_compose up -d api worker beat')):
        raise SystemExit("Orden inseguro de backup/parada/migración/arranque")
    need("scripts/backup_offsite.sh",'sha256sum -c SHA256SUMS','--recipient','$recipient','homex-offsite-encrypted-ok')
    need("scripts/backup_and_offsite.sh",'scripts/backup.sh','scripts/backup_restic.sh','homex-backup-and-offsite-ok')
    need("scripts/backup_restic.sh", "sha256sum -c SHA256SUMS", "restic backup", "restic snapshots", "restic ls", "homex-offsite-restic-ok")
    need("scripts/test_d07_restic.sh", "restic restore", "restic check", "d07-restic-backup-restore-ok")
    need("systemd/homex-backup.service", "HOMEX_RESTIC_CONFIG", "RESTIC_PASSWORD_FILE", "backup_and_offsite.sh")
    need("scripts/verify_release_images.py", "verify_compose(refs)", "services[name]", "HOMEX_ENV_FILE")
    need("scripts/backup_offsite.sh", "HOMEX_OFFSITE_REQUIRE_MOUNT", "mountpoint -q", "GNUPGHOME")
    need("systemd/homex-backup.timer",'Persistent=true','America/La_Paz')
    profile=need("scripts/profile_asr_runtime.py",'worker_concurrency','audio_files_remaining','rss_peak_mib')
    if "args.audio.unlink" in profile: raise SystemExit("Perfil destruye el audio original")
    for forbidden in ('\"transcript\":', '\"text\":', '\"audio_path\":'):
        if forbidden in profile: raise SystemExit(f"Perfil ASR expone {forbidden}")
    if 'networks: [data]' not in compose or 'internal: true' not in compose:
        raise SystemExit("Worker ASR debe permanecer en red interna sin salida directa")
    workflow=need(".github/workflows/ci.yml",BACKEND,FRONTEND,'d07-release-contract:','test_d07_offsite.sh')
    if 'ref: main' in workflow: raise SystemExit("CI D07 consume una rama flotante")
    print("d07-release-contract-ok")
if __name__ == "__main__": main()
