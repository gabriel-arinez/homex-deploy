#!/bin/sh
set -eu

if [ -z "${RESTIC_REPOSITORY:-}" ]; then
  config=${HOMEX_RESTIC_CONFIG:-"${HOME:?}/.config/homex/restic-r2.env"}
  [ -r "$config" ] || { echo "Configuración privada Restic inaccesible" >&2; exit 1; }
  . "$config"
fi
export RESTIC_PASSWORD_FILE=${RESTIC_PASSWORD_FILE:-"${HOME:?}/.config/homex/restic-password"}
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY obligatorio}"

# Preflight remoto antes de interrumpir escritores para backup D05.
restic snapshots --json >/dev/null
output=$(sh scripts/backup.sh)
printf '%s\n' "$output"
backup_dir=$(printf '%s\n' "$output" | grep -E '^/[^[:space:]]*/homex-[0-9]{8}T[0-9]{6}Z$' | tail -n 1)
[ -d "$backup_dir" ] || { echo "backup.sh no devolvió una unidad válida" >&2; exit 1; }
sh scripts/backup_restic.sh "$backup_dir"
echo homex-backup-and-offsite-ok
