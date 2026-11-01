#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
env_file=${HOMEX_LOCAL_ENV:-/home/gabriel/HOMEX/homex-deploy/.env.manual-demo}
export BACKEND_CONTEXT=${HOMEX_BACKEND_SOURCE:-$root/../homex-backend-asr-main}
export FRONTEND_CONTEXT=${HOMEX_FRONTEND_SOURCE:-$root/../homex-frontend-asr-main}
compose=(docker compose --project-directory "$root" --env-file "$env_file" --profile operations)

case ${1:-} in
  rebuild)
    "${compose[@]}" build backend frontend-proxy
    "${compose[@]}" up -d postgres redis
    "${compose[@]}" up -d --no-deps api worker beat frontend-proxy
    ;;
  start)
    "${compose[@]}" up -d postgres redis
    "${compose[@]}" up -d --no-deps api worker beat frontend-proxy
    ;;
  status) "${compose[@]}" ps ;;
  logs) "${compose[@]}" logs --tail=100 -f api worker beat frontend-proxy ;;
  *) echo 'Usage: run_asr_local.sh rebuild|start|status|logs' >&2; exit 2 ;;
esac
