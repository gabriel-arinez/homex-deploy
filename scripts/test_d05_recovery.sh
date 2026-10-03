#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
project=${D05_COMPOSE_PROJECT:-homex-d05-gate}
backend_context=${BACKEND_CONTEXT:-../homex-backend}
work_dir=${D05_WORK_DIR:-$(mktemp -d /tmp/homex-d05.XXXXXX)}
media_dir=$work_dir/media
backup_root=$work_dir/backups
state_file=$work_dir/state.json
env_file=${D05_ENV_FILE:-.env.production.example}
timestamp=20261003T120000Z
backup_dir=$backup_root/homex-$timestamp

case "$project" in
  homex-d05-*) ;;
  *) echo "D05_COMPOSE_PROJECT debe comenzar con homex-d05-" >&2; exit 2 ;;
esac

mkdir -p "$media_dir" "$backup_root" "$work_dir/asr" "$work_dir/tls"
chmod 0777 "$media_dir"
touch "$work_dir/asr/model.bin" "$work_dir/tls/tls.crt" "$work_dir/tls/tls.key"

export BACKEND_CONTEXT="$backend_context"
export HOMEX_MEDIA_HOST_PATH="$media_dir"
export ASR_MODEL_SOURCE="$work_dir/asr"
export HOMEX_TLS_CERT_HOST_PATH="$work_dir/tls/tls.crt"
export HOMEX_TLS_KEY_HOST_PATH="$work_dir/tls/tls.key"
export HOMEX_CA_CERT_HOST_PATH="$work_dir/tls/tls.crt"
export COMPOSE_PROJECT_NAME="$project"
export HOMEX_ENV_FILE="$env_file"
export HOMEX_COMPOSE_FILES="-f docker-compose.yml -f compose.production.yml"
export HOMEX_BACKUP_ROOT="$backup_root"
export HOMEX_BACKUP_RETENTION_DAYS=0
export COMPOSE_BIN="$compose"

run_compose() {
  $compose -f docker-compose.yml -f compose.production.yml \
    --project-name "$project" --env-file "$env_file" "$@"
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  run_compose run --rm --no-deps --user 0 api sh -c 'find /var/lib/homex/media -mindepth 1 -delete' || true
  run_compose down --volumes --remove-orphans || true
  rm -rf -- "$work_dir"
  exit "$status"
}
trap cleanup EXIT INT TERM

wait_api() {
  attempts=0
  until run_compose exec -T -e HOMEX_HTTPS_ENABLED=0 api python -c \
    'import urllib.request; r=urllib.request.Request("http://127.0.0.1:8000/api/v1/health/", headers={"Host":"homex.internal","X-Forwarded-Proto":"https"}); urllib.request.urlopen(r, timeout=2).read()' \
    >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    [ "$attempts" -lt 60 ] || { echo "API D05 no quedó disponible" >&2; return 1; }
    sleep 1
  done
}

python3 scripts/test_d05_contract.py
python3 scripts/test_media_inventory.py

if [ "${D05_SKIP_BUILD:-0}" != "1" ]; then
  run_compose build backend
fi
run_compose up -d postgres redis
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose up -d api
wait_api

run_compose run --rm --no-deps \
  -e DJANGO_ALLOWED_HOSTS=homex.internal,localhost,127.0.0.1,api,testserver \
  -e HOMEX_HTTPS_ENABLED=0 \
  -v "$(pwd)/scripts/test_d03_media_runtime.py:/opt/homex-deploy/test_d03_media_runtime.py:ro" \
  api python /opt/homex-deploy/test_d03_media_runtime.py | tee "$state_file"
run_compose exec -T api sh -eu -c \
  'printf asr-temporal-no-respaldar > /var/lib/homex/audio-temporal/d05-asr.wav'

HOMEX_BACKUP_TIMESTAMP="$timestamp" scripts/backup.sh
test -d "$backup_dir"
(
  cd "$backup_dir"
  sha256sum -c SHA256SUMS
  if tar -tzf media.tar.gz | grep -E 'd05-asr|audio|\.wav$'; then
    echo "El backup contiene audio temporal" >&2
    exit 1
  fi
  grep -q 'audio-temporal' recovery.json
)

# Ensayo destructivo: desaparecen volumen PostgreSQL, Redis/audio y media del host.
run_compose exec -T --user 0 api sh -c 'find /var/lib/homex/media -mindepth 1 -delete'
run_compose down --volumes --remove-orphans
find "$media_dir" -mindepth 1 -delete
test -z "$(find "$media_dir" -mindepth 1 -print -quit)"

HOMEX_MEDIA_UID=$(id -u) HOMEX_MEDIA_GID=$(id -g) \
  scripts/restore.sh "$backup_dir" --confirm
run_compose up -d redis api
wait_api
HOMEX_SMOKE_HTTP=0 scripts/smoke.sh

run_compose run --rm --no-deps \
  -v "$(pwd)/scripts/test_d05_restored_runtime.py:/opt/homex-deploy/test_d05_restored_runtime.py:ro" \
  -v "$state_file:/tmp/d05-state.json:ro" \
  api python /opt/homex-deploy/test_d05_restored_runtime.py /tmp/d05-state.json

echo d05-backup-restore-gate-ok
