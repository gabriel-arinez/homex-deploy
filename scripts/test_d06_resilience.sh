#!/bin/sh
set -eu
compose=${COMPOSE_BIN:-docker compose}
project=${D06_COMPOSE_PROJECT:-homex-d06-gate}
case "$project" in homex-d06-*) ;; *) echo 'D06_COMPOSE_PROJECT debe comenzar con homex-d06-' >&2; exit 2;; esac
# Sólo se admite el directorio descartable exacto del namespace D06; nunca borrar uno preexistente.
root=${D06_WORK_DIR:-/tmp/$project}
if [ "$root" != "/tmp/$project" ] || [ -e "$root" ] || [ -L "$root" ]; then
  echo "D06_WORK_DIR debe ser /tmp/$project y no debe existir previamente" >&2
  exit 2
fi
umask 077
mkdir "$root"
printf '%s\n' "$project" > "$root/.d06-owner"
media=$root/media; metrics=$root/metrics; model=$root/asr; tls=$root/tls; fault_audio=$root/audio-readonly
mkdir -p "$media" "$metrics" "$model" "$fault_audio"; chmod 0777 "$media" "$metrics" "$model"; touch "$model/model.bin"
export HOMEX_PRIVATE_BIND=127.0.0.1 HOMEX_PRIVATE_PORT=${D06_PRIVATE_PORT:-9443}
export HOMEX_MEDIA_HOST_PATH=$media HOMEX_METRICS_HOST_PATH=$metrics ASR_MODEL_SOURCE=$model
export HOMEX_TLS_CERT_HOST_PATH=$tls/homex.internal.crt HOMEX_TLS_KEY_HOST_PATH=$tls/homex.internal.key HOMEX_CA_CERT_HOST_PATH=$tls/homex-root-ca.crt
export BACKEND_CONTEXT=${BACKEND_CONTEXT:-../homex-backend} FRONTEND_CONTEXT=${FRONTEND_CONTEXT:-../homex-frontend}
HOMEX_PRIVATE_HOSTNAME=homex.internal HOMEX_TLS_DIR=$tls HOMEX_NGINX_GID=101 HOMEX_TLS_FORCE=1 HOMEX_TLS_UNPRIVILEGED=1 sh scripts/generate_internal_tls.sh
run_compose(){ $compose -f docker-compose.yml -f compose.production.yml --project-name "$project" --env-file .env.production.example --profile operations --profile observability --profile build "$@"; }
cleanup(){ status=$?; trap - EXIT INT TERM; chmod 0777 "$media" "$fault_audio" 2>/dev/null || true; run_compose down --volumes --remove-orphans || true; if [ -f "$root/.d06-owner" ] && [ "$(cat "$root/.d06-owner")" = "$project" ]; then rm -rf -- "$root"; fi; exit "$status"; }
trap cleanup EXIT INT TERM
wait_health(){ service=$1; expected=$2; attempts=0; id=$(run_compose ps -q "$service"); while :; do value=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id"); [ "$value" = "$expected" ] && return 0; attempts=$((attempts+1)); [ "$attempts" -lt 60 ] || { echo "$service no llegó a $expected (actual $value)" >&2; return 1; }; sleep 1; done; }
url=https://homex.internal:$HOMEX_PRIVATE_PORT
curl_homex(){ curl --silent --show-error --cacert "$HOMEX_CA_CERT_HOST_PATH" --resolve "homex.internal:$HOMEX_PRIVATE_PORT:127.0.0.1" "$@"; }
wait_url(){ attempts=0; until curl_homex --fail "$url/api/v1/health/" >/dev/null 2>&1; do attempts=$((attempts+1)); [ "$attempts" -lt 90 ] || return 1; sleep 1; done; }
python3 scripts/test_d06_contract.py
# Probar que una ruta de trabajo preexistente NO es borrada por el gate.
guard_dir="/tmp/${project}-guard"
if [ -e "$guard_dir" ] || [ -L "$guard_dir" ]; then
  echo "Guardia D06 preexistente, no se puede ejecutar prueba negativa" >&2
  exit 2
fi
mkdir "$guard_dir"
printf 'preservar\n' > "$guard_dir/sentinel"
if D06_WORK_DIR="$guard_dir" sh scripts/test_d06_resilience.sh >/dev/null 2>&1; then
  echo "D06 aceptó ruta de trabajo ajena" >&2; exit 1
fi
test "$(cat "$guard_dir/sentinel")" = preservar
rmdir "$guard_dir" 2>/dev/null || { rm -f "$guard_dir/sentinel"; rmdir "$guard_dir"; }
echo d06-workdir-isolation-ok
if [ "${D06_SKIP_BUILD:-0}" != 1 ]; then run_compose build backend frontend-proxy; fi
run_compose up -d postgres redis
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose up -d api worker frontend-proxy monitor
wait_url; wait_health worker healthy; wait_health monitor healthy
grep -q 'homex_dependency_up{dependency="postgres"} 1' "$metrics/homex.prom"
grep -q 'homex_monitor_collection_healthy 1' "$metrics/homex.prom"
grep -q 'homex_storage_used_percent{storage="media"}' "$metrics/homex.prom"
echo d06-metrics-health-ok
headers=$root/headers; curl_homex --fail -D "$headers" "$url/api/v1/health/" >/dev/null
request_id=$(awk 'BEGIN{IGNORECASE=1} /^X-Request-ID:/ {gsub("\r",""); print $2}' "$headers")
test -n "$request_id"; sleep 1
run_compose logs --no-color frontend-proxy | grep -F '"request_id":"'"$request_id"'"'
run_compose logs --no-color api | grep -F '"request_id":"'"$request_id"'"'
! run_compose logs --no-color | grep -E 'Authorization: Bearer|DJANGO_SECRET_KEY=|POSTGRES_PASSWORD=|CLOUDFLARE_TUNNEL_TOKEN'
echo d06-log-correlation-ok
status=$(curl_homex --output /dev/null --write-out '%{http_code}' "$url/api/v1/auth/me/"); test "$status" = 401
echo d06-unauthorized-access-ok
run_compose stop postgres
if run_compose exec -T api python -c "from django.db import connection; connection.cursor().execute('SELECT 1')" >/dev/null 2>&1; then
  echo 'API conservó readiness SQL con PostgreSQL detenido' >&2; exit 1
fi
if run_compose run --rm --no-deps monitor python /opt/homex-deploy/collect_runtime_metrics.py; then
  echo 'monitor aceptó PostgreSQL caído' >&2; exit 1
fi
grep -q 'homex_dependency_up{dependency="postgres"} 0' "$metrics/homex.prom"
grep -q 'homex_monitor_collection_healthy 0' "$metrics/homex.prom"
run_compose start postgres; wait_health postgres healthy
run_compose exec -T api python -c "from django.db import connection; connection.cursor().execute('SELECT 1')"
wait_health api healthy; wait_url
echo d06-postgresql-failure-recovery-ok
run_compose stop redis
if run_compose run --rm --no-deps monitor python /opt/homex-deploy/collect_runtime_metrics.py; then echo 'monitor aceptó Redis caído' >&2; exit 1; fi
grep -q 'homex_dependency_up{dependency="redis"} 0' "$metrics/homex.prom"
run_compose start redis; wait_health redis healthy
run_compose run --rm --no-deps monitor python /opt/homex-deploy/collect_runtime_metrics.py
wait_health worker healthy
echo d06-redis-degraded-recovery-ok
for service in api worker frontend-proxy; do run_compose restart "$service"; wait_health "$service" healthy; done
wait_url
echo d06-process-restarts-ok
run_compose stop frontend-proxy
if curl_homex --fail --max-time 3 "$url/" >/dev/null 2>&1; then echo 'Origen siguió accesible con proxy detenido' >&2; exit 1; fi
run_compose start frontend-proxy; wait_health frontend-proxy healthy; wait_url
echo d06-tunnel-origin-failure-recovery-ok
chmod 0555 "$media"
if run_compose exec -T api python -c "from pathlib import Path; Path('/var/lib/homex/media/d06-write-probe').write_text('x')" >/dev/null 2>&1; then echo 'Media read-only aceptó escritura' >&2; exit 1; fi
chmod 0777 "$media"
run_compose exec -T api python -c "from pathlib import Path; p=Path('/var/lib/homex/media/d06-write-probe'); p.write_text('x'); p.unlink()"
echo d06-media-readonly-recovery-ok
docker run --rm --tmpfs /full:rw,size=64k "homex/backend:${HOMEX_BACKEND_IMAGE_TAG:-d04-9ce7230}" python -c "import errno,pathlib; p=pathlib.Path('/full/fill'); caught=False
try:
 p.write_bytes(b'x'*1048576)
except OSError as e:
 caught=e.errno==errno.ENOSPC
assert caught; print('d06-disk-full-controlled-ok')"
touch "$fault_audio/huérfano.tmp"; touch -d '2 hours ago' "$fault_audio/huérfano.tmp"; chmod 0555 "$fault_audio"
if run_compose run --rm --no-deps -v "$fault_audio:/var/lib/homex/audio-temporal:ro" cleanup >/dev/null 2>&1; then echo 'Cleanup read-only no reportó fallo' >&2; exit 1; fi
chmod 0777 "$fault_audio"
echo d06-cleanup-failure-visible-ok
tmpenv=$root/incomplete.env; awk 'index($0,"DJANGO_SECRET_KEY=") != 1' .env.production.example > "$tmpenv"
if env -u DJANGO_SECRET_KEY $compose -f docker-compose.yml -f compose.production.yml --env-file "$tmpenv" config --quiet >/dev/null 2>&1; then echo 'Configuración incompleta fue aceptada' >&2; exit 1; fi
echo d06-incomplete-config-rejected-ok
run_compose run --rm --no-deps -v "$(pwd)/scripts/test_d06_concurrency.py:/opt/homex-deploy/test_d06_concurrency.py:ro" api python /opt/homex-deploy/test_d06_concurrency.py
run_compose exec -T worker celery -A config inspect ping -d worker@homex-worker --timeout 5 | grep -q pong
echo d06-worker-correlation-task-id-ok
echo d06-resilience-gate-ok
