#!/bin/sh
set -eu

compose=${COMPOSE_BIN:-docker compose}
env_file=${D04_ENV_FILE:-.env.production.example}
project=${D04_COMPOSE_PROJECT:-homex-d04-gate}
base_url=${D04_BASE_URL:-https://homex.internal}
export HOMEX_PRIVATE_BIND=${D04_PRIVATE_BIND:-127.0.0.1}
backend_context=${BACKEND_CONTEXT:-../homex-backend}
frontend_context=${FRONTEND_CONTEXT:-../homex-frontend}
media_dir=${D04_MEDIA_HOST_PATH:-/tmp/homex-d04-media}
model_dir=${D04_ASR_MODEL_PATH:-/tmp/homex-d04-asr}
tls_dir=${D04_TLS_DIR:-/tmp/homex-d04-tls}
ca_cert="$tls_dir/homex-root-ca.crt"
server_cert="$tls_dir/homex.internal.crt"
server_key="$tls_dir/homex.internal.key"
audio_fixture=${D04_AUDIO_FIXTURE:-/tmp/homex-d04-cotizacion.wav}
evidence_dir=${D07_EVIDENCE_DIR:-/tmp/homex-d07-evidence}
profile_audio=$evidence_dir/profile.wav
playwright_config="$frontend_context/playwright.d04.config.ts"

case "$project" in
  homex-d04-*) ;;
  *)
    echo "D04_COMPOSE_PROJECT debe comenzar con homex-d04-" >&2
    exit 2
    ;;
esac

if [ "${D04_RESOLVE_LOOPBACK:-0}" != "1" ] && ! getent hosts homex.internal | awk -v expected="$HOMEX_PRIVATE_BIND" '$1 == expected {found=1} END {exit !found}'; then
  echo "El gate aislado requiere homex.internal -> $HOMEX_PRIVATE_BIND" >&2
  exit 2
fi

if ! command -v espeak-ng >/dev/null 2>&1; then
  echo "Falta espeak-ng para generar el audio determinista D04" >&2
  exit 2
fi

mkdir -p "$media_dir" "$model_dir" "$evidence_dir"
chmod 0777 "$media_dir" "$model_dir" "$evidence_dir"

HOMEX_PRIVATE_HOSTNAME=homex.internal HOMEX_TLS_DIR="$tls_dir" \
  HOMEX_NGINX_GID=101 HOMEX_TLS_FORCE=1 \
  sh scripts/generate_internal_tls.sh

export BACKEND_CONTEXT="$backend_context"
export FRONTEND_CONTEXT="$frontend_context"
export HOMEX_MEDIA_HOST_PATH="$media_dir"
export ASR_MODEL_SOURCE="$model_dir"
export HOMEX_TLS_CERT_HOST_PATH="$server_cert"
export HOMEX_TLS_KEY_HOST_PATH="$server_key"
export HOMEX_CA_CERT_HOST_PATH="$ca_cert"

run_compose() {
  $compose -f docker-compose.yml -f compose.production.yml \
    --project-name "$project" --env-file "$env_file" \
    --profile operations --profile build "$@"
}

wait_url() {
  url=$1
  attempts=0
  until curl --fail --silent --show-error --cacert "$ca_cert" --resolve "homex.internal:443:$HOMEX_PRIVATE_BIND" "$url" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 90 ]; then
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
  rm -f "$playwright_config" "$audio_fixture" "$profile_audio"
  exit "$status"
}
trap cleanup EXIT INT TERM

python3 scripts/test_d04_contract.py

if [ "${D04_SKIP_BUILD:-0}" != "1" ]; then
  run_compose build --no-cache backend frontend-proxy
fi

# El modelo ASR se prepara dentro de la misma imagen backend/worker fijada por la release,
# usando exactamente el snapshot y hash declarados por D04.
run_compose run --rm --no-deps \
  -v "$model_dir:/opt/homex-d04-asr" \
  -v "$(pwd)/scripts/prepare_asr_d04.py:/opt/homex-deploy/prepare_asr_d04.py:ro" \
  backend python /opt/homex-deploy/prepare_asr_d04.py /opt/homex-d04-asr

espeak-ng -v es-la -s 115 -g 10 -w "$audio_fixture" \
  "tres mesas, total cien bolivianos"

run_compose up -d postgres redis
run_compose run --rm migrate
run_compose run --rm grant-runtime
run_compose up -d api worker beat frontend-proxy

wait_url "$base_url/"
wait_url "$base_url/api/v1/health/"

run_compose exec -T api python scripts/preparar_integracion_frontend_f09.py

cp scripts/playwright.d04.config.ts "$playwright_config"

(
  cd "$frontend_context"
  D04_BASE_URL="$base_url" node <<'NODE'
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ headless: true, args: process.env.D04_RESOLVE_LOOPBACK === '1' ? ['--host-resolver-rules=MAP homex.internal 127.0.0.1'] : [] })
  const context = await browser.newContext({ ignoreHTTPSErrors: true })
  const page = await context.newPage()
  await page.goto(process.env.D04_BASE_URL + '/login', { waitUntil: 'networkidle' })
  const secure = await page.evaluate(() => ({
    secureContext: window.isSecureContext,
    randomUUID: typeof crypto.randomUUID === 'function',
  }))
  await browser.close()
  if (!secure.secureContext || !secure.randomUUID) {
    throw new Error(`Origen D04 no es contexto seguro: ${JSON.stringify(secure)}`)
  }
  console.log('d04-browser-secure-context-ok')
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
NODE
)

(
  cd "$frontend_context"
  D04_BASE_URL="$base_url" \
  FE08_AUDIO_FIXTURE="$audio_fixture" \
  npx playwright test src/tests/integration/fe08-real.spec.ts \
    --config playwright.d04.config.ts
)

run_compose exec -T api python scripts/verificar_integracion_frontend_f09.py

# Perfil real y agregado del mismo modelo local, dentro de la red interna sin descarga posible.
espeak-ng -v es-la -s 115 -g 10 -w "$profile_audio" "tres mesas, total cien bolivianos"
run_compose run --rm --no-deps \
  -v "$evidence_dir:/evidence" \
  worker python /opt/homex-deploy/profile_asr_runtime.py \
    /evidence/profile.wav --output /evidence/asr-runtime.json
test ! -e "$profile_audio"
python3 - "$evidence_dir/asr-runtime.json" <<'PYPROFILE'
import json,sys
data=json.load(open(sys.argv[1],encoding="utf-8"))
assert data["worker_concurrency"] == 1
assert data["audio_files_remaining"] == 0
assert data["rss_peak_mib"] >= data["rss_before_mib"] > 0
assert data["first_transcription_seconds"] > 0
assert "transcription" not in data and "text" not in data and "audio_path" not in data
print("d07-asr-runtime-evidence-ok")
PYPROFILE

# Este verificador usa DRF APIClient en el mismo proceso, no el listener HTTPS real.
# El transporte HTTPS ya quedó cubierto por Playwright; desactivar sólo el redirect
# en este proceso evita convertir una prueba de documentos/media en una prueba de middleware.
run_compose exec -T -e HOMEX_HTTPS_ENABLED=0 \
  api python scripts/verificar_superficies_frontend_f09.py

run_compose exec -T api python manage.py check
run_compose exec -T api python manage.py makemigrations --check --dry-run

# El frontend productivo no debe contener source maps ni secretos.
run_compose exec -T frontend-proxy sh -c \
  "! find /usr/share/nginx/html -type f -name '*.map' -print -quit | grep -q ."
run_compose exec -T frontend-proxy sh -c \
  "! grep -R -E 'DJANGO_SECRET_KEY|CLOUDFLARE_TUNNEL_TOKEN|R2_SECRET_ACCESS_KEY|postgresql://' /usr/share/nginx/html"

echo d04-private-release-candidate-ok
