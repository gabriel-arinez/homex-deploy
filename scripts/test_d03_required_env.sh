#!/bin/sh
set -eu
compose=${COMPOSE_BIN:-docker compose}
tmp=/tmp/homex-d03-required.env
for variable in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT_URL R2_BUCKET_NAME HOMEX_MEDIA_PUBLIC_DOMAIN; do
  awk -v variable="$variable" 'index($0, variable "=") != 1' .env.example > "$tmp"
  if env -u "$variable" $compose -f docker-compose.yml -f compose.production.yml --env-file "$tmp" config --quiet >/tmp/d03-required.out 2>/tmp/d03-required.err; then
    echo "La composición productiva aceptó $variable ausente" >&2
    exit 1
  fi
  grep -q "$variable" /tmp/d03-required.err
done
rm -f "$tmp" /tmp/d03-required.out /tmp/d03-required.err
echo d03-required-env-ok
