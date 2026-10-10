#!/bin/sh
set -eu

usage() {
  echo "Uso: scripts/backup_offsite.sh <directorio-backup>" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
source_dir=$1
destination=${HOMEX_OFFSITE_DESTINATION:?HOMEX_OFFSITE_DESTINATION is required}
recipient=${HOMEX_OFFSITE_GPG_RECIPIENT:?HOMEX_OFFSITE_GPG_RECIPIENT is required}
gpg_home=${HOMEX_OFFSITE_GPG_HOME:-}

[ -d "$source_dir" ] || { echo "Backup inexistente: $source_dir" >&2; exit 1; }
for required in database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json SHA256SUMS; do
  [ -f "$source_dir/$required" ] || { echo "Backup incompleto: falta $required" >&2; exit 1; }
done
(
  cd "$source_dir"
  sha256sum -c SHA256SUMS >/dev/null
)

source_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$source_dir")
destination_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$destination")
case "$destination_real/" in
  "$source_real"/*) echo "El destino off-site no puede estar dentro del backup" >&2; exit 2 ;;
esac

mkdir -p "$destination"
chmod 0700 "$destination"
name=$(basename "$source_dir").tar.gz.gpg
final=$destination/$name
temporary=$destination/.$name.tmp.$$
checksum=$final.sha256
fifo=$destination/.$name.pipe.$$
[ ! -e "$final" ] || { echo "La copia off-site ya existe: $final" >&2; exit 1; }

cleanup() {
  status=$?
  trap - EXIT INT TERM
  rm -f -- "$temporary" "$temporary.sha256" "$fifo"
  exit "$status"
}
trap cleanup EXIT INT TERM

gpg_args=""
if [ -n "$gpg_home" ]; then
  gpg_args="--homedir $gpg_home"
fi
# FIFO evita una copia intermedia en claro y permite comprobar por separado tar y GPG.
mkfifo -m 0600 "$fifo"
# El fingerprint es público. Las claves privadas nunca son argumentos ni archivos de esta unidad.
# shellcheck disable=SC2086
gpg $gpg_args --batch --yes --trust-model always --recipient "$recipient" \
  --output "$temporary" --encrypt "$fifo" &
gpg_pid=$!
if ! tar -C "$(dirname "$source_dir")" -czf "$fifo" "$(basename "$source_dir")"; then
  kill "$gpg_pid" 2>/dev/null || true
  wait "$gpg_pid" 2>/dev/null || true
  echo "No se pudo serializar la unidad de backup" >&2
  exit 1
fi
if ! wait "$gpg_pid"; then
  echo "No se pudo cifrar la unidad de backup" >&2
  exit 1
fi
rm -f -- "$fifo"
[ -s "$temporary" ] || { echo "La copia cifrada quedó vacía" >&2; exit 1; }
sha256sum "$temporary" | sed "s#  $temporary#  $name#" > "$temporary.sha256"
mv "$temporary" "$final"
mv "$temporary.sha256" "$checksum"
(
  cd "$destination"
  sha256sum -c "$(basename "$checksum")" >/dev/null
)
trap - EXIT INT TERM
printf '%s\n' "$final"
echo homex-offsite-encrypted-ok
