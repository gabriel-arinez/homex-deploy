#!/bin/sh
set -eu
root=$(mktemp -d /tmp/homex-d07-restic-XXXXXXXX)
cleanup() { status=$?; trap - EXIT HUP INT TERM; rm -rf -- "$root"; exit "$status"; }
trap cleanup EXIT HUP INT TERM
mkdir -p "$root/source/homex-20261009T120000Z" "$root/restored"
source_dir="$root/source/homex-20261009T120000Z"
for name in database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json; do
  printf 'HOMEX D07 fixture %s\n' "$name" > "$source_dir/$name"
done
(cd "$source_dir" && sha256sum database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json > SHA256SUMS)
export RESTIC_REPOSITORY="$root/repository"
export RESTIC_PASSWORD=homex-d07-isolated-test-only
printf '%s\n' "$RESTIC_PASSWORD" > "$root/password"
chmod 600 "$root/password"
export RESTIC_PASSWORD_FILE="$root/password"
unset RESTIC_PASSWORD
restic init >/dev/null
sh scripts/backup_restic.sh "$source_dir"
restic restore latest --tag homex-d07-offsite --target "$root/restored" >/dev/null
restored="$root/restored${source_dir}"
[ -d "$restored" ] || { echo "No se restauró la unidad D05" >&2; exit 1; }
(cd "$restored" && sha256sum -c SHA256SUMS >/dev/null)
cmp "$source_dir/database.dump" "$restored/database.dump"
cmp "$source_dir/media.tar.gz" "$restored/media.tar.gz"
if find "$restored" -type f | grep -Eq '\\.(wav|mp3|ogg)$'; then
  echo "Audio temporal incluido por error" >&2; exit 1
fi
printf 'corrupcion\n' >> "$source_dir/database.dump"
if sh scripts/backup_restic.sh "$source_dir" > "$root/expected-failure.log" 2>&1; then
  echo "La unidad corrupta fue aceptada" >&2; exit 1
fi
restic check >/dev/null
echo d07-restic-backup-restore-ok
