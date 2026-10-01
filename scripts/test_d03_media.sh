#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
project=${D03_COMPOSE_PROJECT:-homex-d03-gate}
media_dir=${D03_MEDIA_HOST_PATH:-}
base_url=${D03_BASE_URL:-http://localhost:${STAGING_HTTP_PORT:-8080}}

case "$project" in
  homex-d03-*) ;;
  *)
    echo "D03_COMPOSE_PROJECT debe comenzar con homex-d03-" >&2
    exit 2
    ;;
esac

if [ -z "$media_dir" ]; then
  media_dir=$(mktemp -d /tmp/homex-d03-media.XXXXXX)
else
  mkdir -p "$media_dir"
fi
chmod 0777 "$media_dir"

export HOMEX_MEDIA_HOST_PATH="$media_dir"
export HOMEX_MEDIA_STORAGE=filesystem
export HOMEX_MEDIA_ROOT=/var/lib/homex/media
export HOMEX_MEDIA_URL=/media/
export HOMEX_HTTPS_ENABLED=0
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api,testserver
export BACKEND_CONTEXT=${BACKEND_CONTEXT:-../homex-backend}
export FRONTEND_CONTEXT=${FRONTEND_CONTEXT:-../homex-frontend}

state_file=/tmp/homex-d03-state.json
token_file=/tmp/homex-d03-token.json

run_compose() {
  $compose -f docker-compose.yml -f compose.production.yml \
    --project-name "$project" --env-file .env.example "$@"
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

cleanup() {
  status=$?
  trap - EXIT INT TERM
  run_compose down --volumes --remove-orphans || true
  echo "Directorio temporal D03: $media_dir"
  exit "$status"
}
trap cleanup EXIT INT TERM

python3 scripts/test_d03_contract.py

if [ "${D03_SKIP_BUILD:-0}" != "1" ]; then
  run_compose build --no-cache backend frontend-proxy
fi

run_compose up -d postgres redis
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose up -d api frontend-proxy
wait_url "$base_url/"
wait_url "$base_url/api/v1/health/"

run_compose run --rm --no-deps \
  -v "$(pwd)/scripts/test_d03_media_runtime.py:/opt/homex-deploy/test_d03_media_runtime.py:ro" \
  api python /opt/homex-deploy/test_d03_media_runtime.py \
  | tee "$state_file"

python3 - "$state_file" <<'PY'
import json
import sys
from pathlib import Path

state=json.loads(Path(sys.argv[1]).read_text())
assert state["resultado"] == "d03-media-local-created"
for path in state["product_paths"] + state["attachment_paths"]:
    assert str(path).startswith("/var/lib/homex/media/")
for key in state["product_keys"] + state["attachment_keys"]:
    assert not key.startswith(("/", "http://", "https://"))
print("d03-logical-keys-ok")
PY

python3 - "$state_file" "$media_dir" <<'PY'
import json
import sys
from pathlib import Path

state=json.loads(Path(sys.argv[1]).read_text())
root=Path(sys.argv[2])
for key in state["product_keys"] + state["attachment_keys"]:
    path=root / key
    assert path.is_file(), path
print("d03-host-files-ok")
PY

python3 - "$state_file" "$base_url" <<'PY'
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

state=json.loads(Path(sys.argv[1]).read_text())
base=sys.argv[2].rstrip("/")
for value in state["product_urls"] + [state["attachment_url"]]:
    parsed=urllib.parse.urlsplit(value)
    path=parsed.path if parsed.scheme else value
    with urllib.request.urlopen(base + path, timeout=10) as response:
        assert response.status == 200
print("d03-nginx-media-ok")
PY

run_compose up -d --force-recreate api frontend-proxy
wait_url "$base_url/"
wait_url "$base_url/api/v1/health/"

python3 - "$state_file" "$base_url" <<'PY'
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

state=json.loads(Path(sys.argv[1]).read_text())
base=sys.argv[2].rstrip("/")
for value in state["product_urls"] + [state["attachment_url"]]:
    parsed=urllib.parse.urlsplit(value)
    path=parsed.path if parsed.scheme else value
    with urllib.request.urlopen(base + path, timeout=10) as response:
        assert response.status == 200
print("d03-recreate-persistence-ok")
PY

curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -d '{"username":"d03-media-admin","password":"d03-media-only"}' \
  "$base_url/api/v1/auth/token/" > "$token_file"
token=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['access'])" "$token_file")

product_id=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['product_id'])" "$state_file")
proforma_id=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['proforma_id'])" "$state_file")
detail_id=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['detail_id'])" "$state_file")
attachment_id=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['attachment_id'])" "$state_file")

attachment_status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  -X DELETE -H "Authorization: Bearer $token" \
  "$base_url/api/v1/proformas/$proforma_id/detalles/$detail_id/archivos/$attachment_id/")
test "$attachment_status" = 204

product_status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  -X DELETE -H "Authorization: Bearer $token" \
  "$base_url/api/v1/catalogo/productos/$product_id/imagen-principal/")
test "$product_status" = 204

python3 - "$state_file" "$media_dir" <<'PY'
import json
import sys
from pathlib import Path

state=json.loads(Path(sys.argv[1]).read_text())
root=Path(sys.argv[2])
for key in state["product_keys"] + state["attachment_keys"]:
    assert not (root / key).exists(), key
print("d03-delete-no-orphans-ok")
PY

echo d03-media-local-gate-ok
