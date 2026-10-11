#!/bin/sh
set -eu
root=${D07_OFFSITE_WORK_DIR:-/tmp/homex-d07-offsite}
case "$root" in /tmp/homex-d07-*) ;; *) echo "Workdir D07 inválido" >&2; exit 2 ;; esac
[ ! -e "$root" ] || { echo "Workdir D07 ya existe: $root" >&2; exit 2; }
mkdir -m 0700 "$root"
mkdir -m 0700 "$root/gnupg" "$root/backup" "$root/offsite"
mkdir -m 0700 "$root/backup/homex-20261009T120000Z"
cleanup() { status=$?; trap - EXIT INT TERM; rm -rf -- "$root"; exit "$status"; }
trap cleanup EXIT INT TERM
chmod 0700 "$root/gnupg"
cat > "$root/key-params" <<'KEY'
Key-Type: RSA
Key-Length: 2048
Name-Real: HOMEX D07 Recovery Test
Name-Email: recovery-test@homex.invalid
Expire-Date: 0
%no-protection
%commit
KEY
gpg --homedir "$root/gnupg" --batch --generate-key "$root/key-params" >/dev/null 2>&1
fingerprint=$(gpg --homedir "$root/gnupg" --batch --with-colons --list-keys recovery-test@homex.invalid | awk -F: '$1=="fpr" {print $10; exit}')
backup=$root/backup/homex-20261009T120000Z
printf database > "$backup/database.dump"
printf media > "$backup/media.tar.gz"
printf '{}\n' > "$backup/media-manifest.json"
printf 'release: d07\n' > "$backup/release-manifest.yaml"
printf '{"excludes":["audio-temporal"]}\n' > "$backup/recovery.json"
(cd "$backup" && sha256sum database.dump media.tar.gz media-manifest.json release-manifest.yaml recovery.json > SHA256SUMS)
HOMEX_OFFSITE_DESTINATION="$root/offsite" HOMEX_OFFSITE_GPG_RECIPIENT="$fingerprint" \
HOMEX_OFFSITE_GPG_HOME="$root/gnupg" scripts/backup_offsite.sh "$backup"
archive=$root/offsite/$(basename "$backup").tar.gz.gpg
[ -s "$archive" ]
(cd "$root/offsite" && sha256sum -c "$(basename "$archive").sha256" >/dev/null)
gpg --homedir "$root/gnupg" --batch --quiet --output "$root/restored.tar.gz" --decrypt "$archive"
tar -tzf "$root/restored.tar.gz" | grep -q "$(basename "$backup")/SHA256SUMS"
! tar -tzf "$root/restored.tar.gz" | grep -E 'audio|\.wav$'
echo d07-offsite-encrypted-restore-ok
