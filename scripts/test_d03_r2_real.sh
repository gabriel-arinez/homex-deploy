#!/bin/sh
set -eu
if [ "${D03_REAL_R2_CONFIRM:-}" != "YES-DISPOSABLE-DATABASE" ]; then
  echo 'D03_REAL_R2_CONFIRM=YES-DISPOSABLE-DATABASE es obligatorio: el gate crea datos comerciales de prueba.' >&2
  exit 2
fi
for name in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT_URL R2_BUCKET_NAME HOMEX_MEDIA_PUBLIC_DOMAIN; do
  eval "value=\${$name:-}"
  case "$value" in ''|replace-*|*example.com|*invalid*) echo "$name no contiene una configuración R2 real" >&2; exit 2;; esac
done
[ "$R2_BUCKET_NAME" = homex-public-media ] || { echo 'R2_BUCKET_NAME debe ser homex-public-media' >&2; exit 2; }
case "$HOMEX_MEDIA_PUBLIC_DOMAIN" in http://*|https://*|*/*) echo 'HOMEX_MEDIA_PUBLIC_DOMAIN debe contener sólo el hostname' >&2; exit 2;; esac
compose=${COMPOSE_BIN:-docker compose}
project=${D03_COMPOSE_PROJECT:-homex-d03-real}
case "$project" in homex-d03-*) ;; *) echo 'D03_COMPOSE_PROJECT debe comenzar con homex-d03-' >&2; exit 2;; esac
$compose -f docker-compose.yml -f compose.production.yml --project-name "$project" --env-file .env run --rm \
  -e R2_PUBLIC_TEST_BASE_URL="https://$HOMEX_MEDIA_PUBLIC_DOMAIN" \
  -v "$(pwd)/scripts/test_r2_media_runtime.py:/opt/homex-deploy/test_r2_media_runtime.py:ro" \
  api python /opt/homex-deploy/test_r2_media_runtime.py | tee /tmp/homex-d03-r2-real-result.log
grep -q '"resultado": "d03-r2-media-ok"' /tmp/homex-d03-r2-real-result.log
echo d03-r2-real-ok
