#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
env_file=${D01_ENV_FILE:-.env.example}
project=${D01_COMPOSE_PROJECT:-homex-d01-gate}

case "$project" in
  homex-d01-*) ;;
  *)
    echo "D01_COMPOSE_PROJECT debe comenzar con homex-d01- para proteger otros volúmenes" >&2
    exit 2
    ;;
esac

run_compose() {
  $compose --project-name "$project" --env-file "$env_file" "$@"
}

wait_postgres() {
  attempts=0
  until run_compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      echo "PostgreSQL no quedó disponible tras reinicio" >&2
      return 1
    fi
    sleep 1
  done
}

wait_redis() {
  attempts=0
  until [ "$(run_compose exec -T redis redis-cli ping 2>/dev/null || true)" = "PONG" ]; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      echo "Redis no quedó disponible tras reinicio" >&2
      return 1
    fi
    sleep 1
  done
}

wait_worker() {
  attempts=0
  until run_compose exec -T worker celery -A config inspect ping -d worker@homex-worker --timeout 5 2>/dev/null | grep -q pong; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 20 ]; then
      echo "Worker no respondió ping" >&2
      return 1
    fi
    sleep 2
  done
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  run_compose down --volumes --remove-orphans || true
  exit "$status"
}
trap cleanup EXIT INT TERM

if [ "${D01_SKIP_BUILD:-0}" != "1" ]; then
  run_compose build --no-cache backend
fi
run_compose up -d postgres redis
wait_postgres
wait_redis
run_compose run --rm migrate
run_compose run --rm migrate | tee /tmp/homex-d01-second-migrate.log
grep -q "No migrations to apply" /tmp/homex-d01-second-migrate.log
run_compose run --rm grant-runtime
run_compose up -d api worker
wait_worker

run_compose exec -T api python /opt/homex-deploy/verify_expected_migrations.py
run_compose exec -T api python scripts/verificar_integracion_f084.py
run_compose exec -T api sh -c \
  'test "$(stat -c %a /var/lib/homex/audio-temporal)" = 700'
run_compose exec -T worker sh -c \
  'test -r /opt/homex/models/faster-whisper-small/model.bin && ! touch /opt/homex/models/faster-whisper-small/.write-test'

run_compose stop postgres
run_compose start postgres
wait_postgres
run_compose exec -T api python manage.py shell -c \
  "from apps.capturas.models import Captura; assert Captura.objects.exists(); print('postgres-persistence-ok')"

run_compose stop redis
run_compose exec -T api python manage.py shell -c \
  "from uuid import uuid4; from django.contrib.auth import get_user_model; from apps.proformas.services import crear_proforma; from apps.capturas.services import recibir_captura_texto; from apps.capturas.models import TrabajoOutbox; actor=get_user_model().objects.create_user(username=f'redis-down-{uuid4().hex}'); proforma=crear_proforma(actor=actor, prospecto_nombre='Redis caído'); intento=recibir_captura_texto(actor=actor, clave_idempotencia=uuid4(), proforma_id=proforma.id, texto='Dos escritorios, total cien bolivianos').intento; assert TrabajoOutbox.objects.filter(intento=intento, publicado_at__isnull=True).exists(); print('postgres-outbox-survives-redis-outage-ok')"
run_compose start redis
wait_redis
run_compose run --rm publisher
run_compose run --rm reconciler

run_compose stop worker
run_compose run --rm cleanup
run_compose start worker
wait_worker

wait_postgres
wait_redis
echo d01-runtime-ok
