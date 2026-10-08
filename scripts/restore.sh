#!/bin/sh
set -eu

usage() {
  echo "Uso: scripts/restore.sh <directorio-backup> --confirm" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
backup_dir=$1
[ "$2" = "--confirm" ] || usage

compose=${COMPOSE_BIN:-docker compose}
compose_files=${HOMEX_COMPOSE_FILES:--f docker-compose.yml -f compose.production.yml}
env_file=${HOMEX_ENV_FILE:-.env.production}
project=${COMPOSE_PROJECT_NAME:-homex-prod}
media_dir=${HOMEX_MEDIA_HOST_PATH:?HOMEX_MEDIA_HOST_PATH is required}
media_uid=${HOMEX_MEDIA_UID:-10001}
media_gid=${HOMEX_MEDIA_GID:-10001}
restore_parent=$(dirname "$media_dir")
restore_name=$(basename "$media_dir")
staging=$restore_parent/.${restore_name}.restore.$$
previous=$restore_parent/.${restore_name}.pre-restore.$$
media_swapped=0

run_compose() {
  # shellcheck disable=SC2086
  $compose $compose_files --project-name "$project" --env-file "$env_file" "$@"
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [ "$status" -ne 0 ] && [ "$media_swapped" -eq 1 ] && [ -d "$previous" ]; then
    rm -rf -- "$media_dir"
    mv "$previous" "$media_dir"
    echo "Restore falló; se repuso la media anterior" >&2
  fi
  [ ! -d "$staging" ] || rm -rf -- "$staging"
  exit "$status"
}
trap cleanup EXIT INT TERM

for required in database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json SHA256SUMS; do
  [ -f "$backup_dir/$required" ] || { echo "Backup incompleto: falta $required" >&2; exit 1; }
done
(
  cd "$backup_dir"
  sha256sum -c SHA256SUMS
)

if ! cmp -s releases/manifest.yaml "$backup_dir/release-manifest.yaml" && \
  [ "${HOMEX_RESTORE_ALLOW_RELEASE_MISMATCH:-0}" != "1" ]; then
  echo "La release activa no coincide con el backup; restaure primero el checkout/manifiesto correcto" >&2
  exit 1
fi

python3 - "$backup_dir/recovery.json" <<'PY'
import json
import sys
metadata=json.load(open(sys.argv[1], encoding="utf-8"))
assert metadata["schema_version"] == "1.0"
assert metadata["database_format"] == "postgresql-custom"
assert "audio-temporal" in metadata["excludes"]
PY

# Prevalidar completamente la media antes de cualquier operación destructiva sobre PostgreSQL.
mkdir -p "$restore_parent"
python3 scripts/media_inventory.py extract "$backup_dir/media.tar.gz" "$staging"
python3 scripts/media_inventory.py verify "$staging" "$backup_dir/media-manifest.json"

run_compose stop api worker beat frontend-proxy publisher reconciler cleanup 2>/dev/null || true
run_compose up -d postgres
attempt=0
# Esperar una consulta SQL real; pg_isready por sí solo puede adelantarse al arranque completo.
# shellcheck disable=SC2016
until run_compose exec -T postgres sh -eu -c \
  'psql --username "$POSTGRES_USER" --dbname postgres --tuples-only --command "SELECT 1"' \
  >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 60 ] || { echo "PostgreSQL no quedó disponible" >&2; exit 1; }
  sleep 1
done

# Verificar que el dump sea legible antes de destruir la base objetivo.
run_compose exec -T postgres pg_restore --list < "$backup_dir/database.dump" >/dev/null

# shellcheck disable=SC2016
run_compose exec -T postgres sh -eu -c '
  dropdb --force --if-exists --username "$POSTGRES_USER" "$POSTGRES_DB"
  createdb --username "$POSTGRES_USER" --owner "$HOMEX_DB_MIGRATOR_USER" "$POSTGRES_DB"
'
# shellcheck disable=SC2016
run_compose exec -T postgres sh -eu -c '
  pg_restore --exit-on-error --no-owner --no-privileges \
    --username "$POSTGRES_USER" --role "$HOMEX_DB_MIGRATOR_USER" --dbname "$POSTGRES_DB"
' < "$backup_dir/database.dump"

if [ -e "$media_dir" ]; then
  mv "$media_dir" "$previous"
fi
mv "$staging" "$media_dir"
chown -R "$media_uid:$media_gid" "$media_dir"
media_swapped=1

run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose run --rm --no-deps api python /opt/homex-deploy/verify_media_integrity.py

if [ -d "$previous" ]; then
  rm -rf -- "$previous"
fi
media_swapped=0
echo homex-restore-ok
