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
