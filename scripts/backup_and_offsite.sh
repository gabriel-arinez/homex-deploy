#!/bin/sh
set -eu
output=$(scripts/backup.sh)
printf '%s\n' "$output"
backup_dir=$(printf '%s\n' "$output" | sed -n '1p')
[ -d "$backup_dir" ] || { echo "backup.sh no devolvió una unidad válida" >&2; exit 1; }
scripts/backup_offsite.sh "$backup_dir"
echo homex-backup-and-offsite-ok
