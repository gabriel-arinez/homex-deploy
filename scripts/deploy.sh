#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
compose_files=${HOMEX_COMPOSE_FILES:--f docker-compose.yml -f compose.production.yml}
env_file=${HOMEX_ENV_FILE:-.env.production}
project=${COMPOSE_PROJECT_NAME:-homex-prod}

run_compose() {
  # shellcheck disable=SC2086
  $compose $compose_files --project-name "$project" --env-file "$env_file" --profile operations --profile observability "$@"
}

run_compose config --quiet

# La promoción exige imágenes GHCR inmutables y verificadas antes de migrar.
if [ "${HOMEX_RELEASE_IMAGE_BUILD_MODE:-0}" = "1" ]; then
  echo "El modo de construcción CI está prohibido durante despliegue" >&2
  exit 1
fi

# Comprobar las referencias antes de cualquier descarga o modificación.
HOMEX_REQUIRE_COMPOSE_MATCH=1 HOMEX_ENV_FILE="$env_file" HOMEX_COMPOSE_FILES="$compose_files" \
  HOMEX_RELEASE_IMAGE_PRECHECK=1 python3 scripts/verify_release_images.py

run_compose pull --policy always api worker frontend-proxy monitor

HOMEX_REQUIRE_COMPOSE_MATCH=1 HOMEX_ENV_FILE="$env_file" HOMEX_COMPOSE_FILES="$compose_files" \
  python3 scripts/verify_release_images.py

run_compose up -d postgres redis

# shellcheck disable=SC2016
if [ "${HOMEX_DEPLOY_SKIP_BACKUP:-0}" != "1" ] && \
  run_compose exec -T postgres sh -eu -c \
    'psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --command "SELECT 1"' \
    >/dev/null 2>&1; then
  HOMEX_ENV_FILE="$env_file" HOMEX_COMPOSE_FILES="$compose_files" \
    COMPOSE_BIN="$compose" COMPOSE_PROJECT_NAME="$project" scripts/backup.sh
fi

# El backup D05 reanuda escritores para conservar su semántica operacional.
# Antes de migrar, detenerlos nuevamente y mantenerlos fuera hasta iniciar D07.
# Si la migración comienza, NO reactivar automáticamente procesos D04 ante un fallo:
# el esquema podría haber cambiado y exige recuperación según runbook.
migration_started=0
stopped_writers=
recover_before_migration() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$migration_started" -eq 0 ] && [ -n "$stopped_writers" ]; then
    # shellcheck disable=SC2086
    run_compose start $stopped_writers || true
  fi
  if [ "$status" -ne 0 ] && [ "$migration_started" -eq 1 ]; then
    echo "Despliegue interrumpido tras iniciar migraciones; NO reiniciar escritores D04. Seguir RECOVERY_RUNBOOK.md." >&2
  fi
  exit "$status"
}
trap recover_before_migration EXIT
running=$(run_compose ps --status running --services)
for writer in api worker beat publisher reconciler cleanup; do
  if printf '%s\n' "$running" | grep -qx "$writer"; then
    stopped_writers="$stopped_writers $writer"
  fi
done
if [ -n "$stopped_writers" ]; then
  # shellcheck disable=SC2086
  run_compose stop $stopped_writers
fi
migration_started=1
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose up -d api worker beat frontend-proxy monitor
HOMEX_ENV_FILE="$env_file" HOMEX_COMPOSE_FILES="$compose_files" \
  COMPOSE_BIN="$compose" COMPOSE_PROJECT_NAME="$project" scripts/smoke.sh
# El monitor debe producir métricas al menos una vez antes de promover el despliegue.
attempt=0
monitor_id=$(run_compose ps -q monitor)
[ -n "$monitor_id" ] || { echo "Monitor no fue creado" >&2; exit 1; }
while :; do
  monitor_status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$monitor_id")
  [ "$monitor_status" = healthy ] && break
  attempt=$((attempt + 1))
  [ "$attempt" -lt 60 ] || { echo "Monitor no disponible: $monitor_status" >&2; exit 1; }
  sleep 2
done
echo homex-deploy-ok
