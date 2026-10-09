#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
compose_files=${HOMEX_COMPOSE_FILES:--f docker-compose.yml -f compose.production.yml}
env_file=${HOMEX_ENV_FILE:-.env.production}
project=${COMPOSE_PROJECT_NAME:-homex-prod}
media_dir=${HOMEX_MEDIA_HOST_PATH:?HOMEX_MEDIA_HOST_PATH is required}
backup_root=${HOMEX_BACKUP_ROOT:-/srv/homex/backups}
retention_days=${HOMEX_BACKUP_RETENTION_DAYS:-14}
timestamp=${HOMEX_BACKUP_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
target=$backup_root/homex-$timestamp
staging=$backup_root/.homex-$timestamp.tmp
lock=$backup_root/.backup.lock
stopped_services=
completed=0

run_compose() {
  # La separación de palabras permite COMPOSE_BIN="docker compose" y la lista -f controlada.
  # shellcheck disable=SC2086
  $compose $compose_files --project-name "$project" --env-file "$env_file" "$@"
}

restart_writers() {
  if [ -n "$stopped_services" ]; then
    # shellcheck disable=SC2086
    run_compose start $stopped_services >/dev/null
  fi
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  restart_writers || true
  if [ "$completed" -ne 1 ] && [ -d "$staging" ]; then
    rm -rf -- "$staging"
  fi
  rmdir "$lock" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT INT TERM

case "$timestamp" in
  *[!0-9TZ]*) echo "HOMEX_BACKUP_TIMESTAMP contiene caracteres no permitidos" >&2; exit 2 ;;
esac
case "$retention_days" in
  ''|*[!0-9]*) echo "HOMEX_BACKUP_RETENTION_DAYS debe ser entero" >&2; exit 2 ;;
esac

mkdir -p "$backup_root"
if ! mkdir "$lock" 2>/dev/null; then
  echo "Ya existe una operación de backup en $lock" >&2
  exit 1
fi
if [ -e "$target" ] || [ -e "$staging" ]; then
  echo "El destino de backup ya existe: $target" >&2
  exit 1
fi
mkdir -m 0700 "$staging"

media_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$media_dir")
backup_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$backup_root")
case "$backup_real/" in
  "$media_real"/*) echo "HOMEX_BACKUP_ROOT no puede estar dentro de media" >&2; exit 2 ;;
esac

running=$(run_compose ps --status running --services 2>/dev/null || true)
for service in api worker beat publisher reconciler cleanup; do
  if printf '%s\n' "$running" | grep -qx "$service"; then
    stopped_services="$stopped_services $service"
  fi
done
if [ -n "$stopped_services" ]; then
  # shellcheck disable=SC2086
  run_compose stop $stopped_services >/dev/null
fi

# shellcheck disable=SC2016
run_compose exec -T postgres sh -eu -c \
  'pg_dump --format=custom --compress=9 --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
  > "$staging/database.dump"
run_compose exec -T postgres pg_restore --list < "$staging/database.dump" >/dev/null

python3 scripts/media_inventory.py inventory "$media_dir" "$staging/media-manifest.json"
python3 scripts/media_inventory.py archive "$media_dir" "$staging/media.tar.gz"
cp releases/manifest.yaml "$staging/release-manifest.yaml"

python3 - "$staging/recovery.json" "$timestamp" "$project" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": "1.0",
    "created_at_utc": sys.argv[2],
    "compose_project": sys.argv[3],
    "database_format": "postgresql-custom",
    "media_format": "tar.gz",
    "includes": ["postgresql", "media", "release-manifest"],
    "excludes": ["redis", "audio-temporal", "asr-model", "tls-private-keys", "secrets"],
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

(
  cd "$staging"
  sha256sum database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json \
    > SHA256SUMS
  sha256sum -c SHA256SUMS
)

mv "$staging" "$target"
completed=1
restart_writers
stopped_services=

if [ "$retention_days" -gt 0 ]; then
  find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name 'homex-????????T??????Z' \
    -mtime "+$retention_days" -exec rm -rf -- {} +
fi

printf '%s\n' "$target"
echo homex-backup-ok
