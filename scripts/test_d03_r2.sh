#!/bin/sh
set -eu
compose=${COMPOSE_BIN:-docker compose}
project=${D03_COMPOSE_PROJECT:-homex-d03-gate}
case "$project" in homex-d03-*) ;; *) echo 'D03_COMPOSE_PROJECT debe comenzar con homex-d03-' >&2; exit 2;; esac
run_compose() {
  $compose -f docker-compose.yml -f compose.production.yml -f compose.r2-test.yml \
    --project-name "$project" --env-file .env.example --profile r2-test "$@"
}
cleanup() {
  status=$?; trap - EXIT INT TERM
  run_compose down --volumes --remove-orphans || true
  exit "$status"
}
trap cleanup EXIT INT TERM
export R2_ACCESS_KEY_ID=d03-test-access
export R2_SECRET_ACCESS_KEY=d03-test-secret
export R2_ENDPOINT_URL=http://r2-test:5000
export R2_BUCKET_NAME=homex-public-media
export HOMEX_MEDIA_PUBLIC_DOMAIN=media.homex.test
export COMPOSE_BIN="$compose"
export BACKEND_CONTEXT=${BACKEND_CONTEXT:-../homex-backend}
export FRONTEND_CONTEXT=${FRONTEND_CONTEXT:-../homex-frontend}
python3 scripts/test_d03_contract.py
sh scripts/test_d03_required_env.sh
if [ "${D03_BUILD_BACKEND:-0}" = "1" ]; then run_compose build backend; fi
run_compose up -d postgres r2-test
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose run --rm r2-init
run_compose run --rm r2-media-test | tee /tmp/homex-d03-r2-result.log
grep -q '"resultado": "d03-r2-media-ok"' /tmp/homex-d03-r2-result.log
run_compose run --rm r2-init python -c "import boto3,os; c=boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT_URL']); assert c.list_objects_v2(Bucket=os.environ['R2_BUCKET_NAME']).get('KeyCount',0)==0; print('d03-r2-no-orphans-ok')"
if run_compose config --format json | python3 -c "import json,sys; c=json.load(sys.stdin); e=c['services']['frontend-proxy'].get('environment',{}); assert not any(k.startswith('R2_') for k in e)"; then :; else exit 1; fi
echo d03-r2-gate-ok
