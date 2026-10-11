#!/bin/sh
set -eu

# En el host se carga la configuración privada (nunca desde Git).
if [ -z "${RESTIC_REPOSITORY:-}" ]; then
  config=${HOMEX_RESTIC_CONFIG:-"${HOME:?}/.config/homex/restic-r2.env"}
  [ -r "$config" ] || { echo "Configuración privada Restic inaccesible" >&2; exit 1; }
  . "$config"
fi
export RESTIC_PASSWORD_FILE=${RESTIC_PASSWORD_FILE:-"${HOME:?}/.config/homex/restic-password"}
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY obligatorio}"

# No detener servicios ni generar backup si no hay credenciales válidas.
restic snapshots --json >/dev/null
output=$(scripts/backup.sh)
printf '%s\n' "$output"
backup_dir=$(printf '%s\n' "$output" | grep -E '^/[^[:space:]]*/homex-[0-9]{8}T[0-9]{6}Z
[ -d "$backup_dir" ] || { echo "backup.sh no devolvió una unidad válida" >&2; exit 1; }
sh scripts/backup_restic.sh "$backup_dir"
echo homex-backup-and-offsite-ok
 | tail -n 1)
[ -d "$backup_dir" ] || { echo "backup.sh no devolvió una unidad válida" >&2; exit 1; }
sh scripts/backup_restic.sh "$backup_dir"
echo homex-backup-and-offsite-ok
