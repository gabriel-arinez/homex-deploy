#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
env_file=${D02_ENV_FILE:-.env.example}
project=${D02_COMPOSE_PROJECT:-homex-d02-gate}
base_url=${D02_BASE_URL:-http://localhost:${STAGING_HTTP_PORT:-8080}}
backend_url=${D02_BACKEND_URL:-http://localhost:${BACKEND_PORT:-8000}}

case "$project" in
  homex-d02-*) ;;
  *)
    echo "D02_COMPOSE_PROJECT debe comenzar con homex-d02- para proteger otros volúmenes" >&2
    exit 2
    ;;
esac

run_compose() {
  $compose --project-name "$project" --env-file "$env_file" "$@"
}

wait_url() {
  url=$1
  attempts=0
  until curl --fail --silent --show-error "$url" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "No quedó disponible: $url" >&2
      return 1
    fi
    sleep 1
  done
}

status_and_body() {
  url=$1
  body=$2
  shift 2
  curl --silent --show-error --output "$body" --write-out '%{http_code}' "$@" "$url"
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  run_compose down --volumes --remove-orphans || true
  rm -rf /tmp/homex-d02-gate
  exit "$status"
}
trap cleanup EXIT INT TERM
mkdir -p /tmp/homex-d02-gate

if [ "${D02_SKIP_BUILD:-0}" != "1" ]; then
  run_compose build --no-cache backend frontend-proxy
fi
run_compose up -d postgres redis
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose up -d api frontend-proxy
wait_url "$base_url/"
wait_url "$base_url/api/v1/health/"

# El proxy conserva exactamente la respuesta 401 producida por Django.
proxy_401=$(status_and_body "$base_url/api/v1/auth/me/" /tmp/homex-d02-gate/proxy-401.json)
direct_401=$(status_and_body "$backend_url/api/v1/auth/me/" /tmp/homex-d02-gate/direct-401.json)
test "$proxy_401" = 401
test "$direct_401" = 401
cmp /tmp/homex-d02-gate/proxy-401.json /tmp/homex-d02-gate/direct-401.json

echo d02-auth-status-preservation-ok

# Datos deterministas: un administrador para multipart y un usuario sin capacidad para 403.
run_compose exec -T api python scripts/preparar_integracion_frontend_f09.py
run_compose exec -T api python manage.py shell -c \
  "from django.contrib.auth import get_user_model; u,_=get_user_model().objects.get_or_create(username='d02-sin-capacidad'); u.set_password('d02-integration-only'); u.save()"

curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -d '{"username":"fe08-admin","password":"fe08-integration-only"}' \
  "$base_url/api/v1/auth/token/" > /tmp/homex-d02-gate/admin-token.json
curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -d '{"username":"d02-sin-capacidad","password":"d02-integration-only"}' \
  "$base_url/api/v1/auth/token/" > /tmp/homex-d02-gate/limited-token.json
admin_token=$(python3 -c "import json; print(json.load(open('/tmp/homex-d02-gate/admin-token.json'))['access'])")
limited_token=$(python3 -c "import json; print(json.load(open('/tmp/homex-d02-gate/limited-token.json'))['access'])")
proxy_403=$(status_and_body "$base_url/api/v1/clientes/" /tmp/homex-d02-gate/proxy-403.json -H "Authorization: Bearer $limited_token")
direct_403=$(status_and_body "$backend_url/api/v1/clientes/" /tmp/homex-d02-gate/direct-403.json -H "Authorization: Bearer $limited_token")
test "$proxy_403" = 403
test "$direct_403" = 403
cmp /tmp/homex-d02-gate/proxy-403.json /tmp/homex-d02-gate/direct-403.json

echo d02-permissions-preservation-ok

# Genera una PNG real 640x400 sin dependencias del host y la sube por multipart a través de Nginx.
python3 - <<'PY'
import struct, zlib
from pathlib import Path
w, h = 640, 400
raw = b''.join(b'\x00' + b'\x35\x73\x9b' * w for _ in range(h))
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
Path('/tmp/homex-d02-gate/upload.png').write_bytes(
    b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
)
PY
curl --fail --silent --show-error -H "Authorization: Bearer $admin_token" \
  "$base_url/api/v1/catalogo/productos/?search=FE08-SILLA-001" > /tmp/homex-d02-gate/products.json
product_id=$(python3 -c "import json; d=json.load(open('/tmp/homex-d02-gate/products.json')); print(d['results'][0]['id'])")
upload_status=$(status_and_body "$base_url/api/v1/catalogo/productos/$product_id/imagen-principal/" /tmp/homex-d02-gate/upload.json \
  -X POST -H "Authorization: Bearer $admin_token" -F 'archivo=@/tmp/homex-d02-gate/upload.png;type=image/png')
test "$upload_status" = 201
media_path=$(python3 - <<'PY'
import json
value=json.load(open('/tmp/homex-d02-gate/upload.json'))
def visit(node):
    if isinstance(node, str) and '/media/' in node: return '/media/' + node.split('/media/', 1)[1]
    if isinstance(node, dict):
        for item in node.values():
            found=visit(item)
            if found: return found
    if isinstance(node, list):
        for item in node:
            found=visit(item)
            if found: return found
print(visit(value) or '')
PY
)
test -n "$media_path"
curl --fail --silent --show-error "$base_url$media_path" >/dev/null

echo d02-multipart-media-ok

# Vue recibe index en rutas profundas; index no se cachea y sólo /assets usa immutable.
curl --fail --silent --show-error -D /tmp/homex-d02-gate/route.headers "$base_url/proformas/123" -o /tmp/homex-d02-gate/route.html
grep -q '<div id="app"></div>' /tmp/homex-d02-gate/route.html
grep -qi 'cache-control:.*no-store' /tmp/homex-d02-gate/route.headers
asset=$(sed -n 's/.*src="\([^\"]*\/assets\/[^\"]*\.js\)".*/\1/p' /tmp/homex-d02-gate/route.html | head -1)
test -n "$asset"
curl --fail --silent --show-error --compressed -H 'Accept-Encoding: gzip' -D /tmp/homex-d02-gate/asset.headers "$base_url$asset" -o /dev/null
grep -qi 'cache-control:.*immutable' /tmp/homex-d02-gate/asset.headers
grep -qi 'content-encoding: gzip' /tmp/homex-d02-gate/asset.headers
grep -qi 'x-content-type-options: nosniff' /tmp/homex-d02-gate/route.headers

echo d02-spa-cache-compression-ok

# Mismo origen no necesita relajar CORS; un origen ajeno no recibe autorización.
curl --silent --show-error -H 'Origin: https://evil.example' -D /tmp/homex-d02-gate/cors.headers \
  "$base_url/api/v1/health/" -o /dev/null
if grep -Eqi '^access-control-allow-origin: *(\*|https://evil\.example)' /tmp/homex-d02-gate/cors.headers; then
  echo 'CORS fue relajado para un origen no autorizado' >&2
  exit 1
fi

echo d02-cors-ok

# El artefacto público contiene sólo la URL Vite permitida, nunca secretos del runtime.
run_compose exec -T frontend-proxy sh -c \
  "! grep -R -E 'DJANGO_SECRET_KEY|R2_SECRET_ACCESS_KEY|replace-with-|postgresql://' /usr/share/nginx/html"
run_compose exec -T api gunicorn --version | grep -q '23.0.0'

if [ "${D02_BROWSER_SMOKE:-1}" = "1" ]; then
  NODE_PATH="${FRONTEND_CONTEXT:-../homex-frontend}/node_modules" \
    D02_BASE_URL="$base_url" node scripts/smoke_d02_browser.cjs
fi

echo d02-http-api-smoke-ok
