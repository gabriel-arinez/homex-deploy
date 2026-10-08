#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
compose_files=${HOMEX_COMPOSE_FILES:--f docker-compose.yml -f compose.production.yml}
env_file=${HOMEX_ENV_FILE:-.env.production}
project=${COMPOSE_PROJECT_NAME:-homex-prod}
base_url=${HOMEX_SMOKE_BASE_URL:-https://homex.internal}

run_compose() {
  # shellcheck disable=SC2086
  $compose $compose_files --project-name "$project" --env-file "$env_file" "$@"
}

run_compose exec -T api python manage.py check
run_compose exec -T api python manage.py migrate --check
run_compose exec -T api python -c \
  'from django.db import connection; connection.ensure_connection(); connection.cursor().execute("SELECT 1"); print("database-smoke-ok")'
run_compose exec -T \
  -e HOMEX_HTTPS_ENABLED=0 api python -c \
  'import urllib.request; r=urllib.request.Request("http://127.0.0.1:8000/api/v1/health/", headers={"Host":"homex.internal","X-Forwarded-Proto":"https"}); urllib.request.urlopen(r, timeout=5).read(); print("api-smoke-ok")'
run_compose exec -T api python /opt/homex-deploy/verify_media_integrity.py

if [ "${HOMEX_SMOKE_HTTP:-1}" = "1" ]; then
  if [ -n "${HOMEX_CA_CERT_HOST_PATH:-}" ]; then
    curl --fail --silent --show-error --cacert "$HOMEX_CA_CERT_HOST_PATH" "$base_url/api/v1/health/" >/dev/null
  else
    curl --fail --silent --show-error "$base_url/api/v1/health/" >/dev/null
  fi
fi
echo homex-smoke-ok
