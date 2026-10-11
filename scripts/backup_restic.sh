#!/bin/sh
# Publica una unidad D05 validada en un repositorio Restic cifrado.
set -eu

[ "$#" -eq 1 ] || { echo "Uso: scripts/backup_restic.sh <directorio-backup>" >&2; exit 2; }
source_dir=$1
[ -d "$source_dir" ] || { echo "Unidad de backup inexistente" >&2; exit 1; }
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY es obligatorio}"
: "${RESTIC_PASSWORD_FILE:?RESTIC_PASSWORD_FILE es obligatorio}"
[ -r "$RESTIC_PASSWORD_FILE" ] || { echo "Contraseña Restic inaccesible" >&2; exit 1; }
for filename in database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json SHA256SUMS; do
  [ -f "$source_dir/$filename" ] || { echo "Backup incompleto: $filename" >&2; exit 1; }
done
(
  cd "$source_dir"
  sha256sum -c SHA256SUMS >/dev/null
)
name=$(basename "$source_dir")
case "$name" in
  homex-????????T??????Z) ;;
  *) echo "Nombre de unidad D05 no válido: $name" >&2; exit 2 ;;
esac

# La salida JSON temporal no contiene credenciales ni datos de los archivos.
umask 077
evidence=$(mktemp)
trap 'rm -f -- "$evidence"' EXIT HUP INT TERM
restic backup --json --tag homex-d07-offsite --tag "$name" "$source_dir" > "$evidence"
snapshot=$(python3 - "$evidence" <<'PY'
import json
import sys
from pathlib import Path
ids = [
    line["snapshot_id"]
    for raw in Path(sys.argv[1]).read_text().splitlines()
    if (line := json.loads(raw)).get("message_type") == "summary"
    and line.get("snapshot_id")
]
if len(ids) != 1:
    raise SystemExit("No se pudo identificar un snapshot Restic único")
print(ids[0])
PY
)
# Consulta directa al remoto; no equivale a una restauración completa.
restic snapshots --json --tag "$name" | python3 -c '
import json, sys
expected = sys.argv[1]
data = json.load(sys.stdin)
if not any(item.get("id") == expected for item in data):
    raise SystemExit("El snapshot no aparece en el repositorio remoto")
' "$snapshot"
restic ls "$snapshot" >/dev/null
printf 'homex-restic-snapshot=%s\n' "$snapshot"
echo homex-offsite-restic-ok
