#!/bin/sh
set -eu

version=${CLOUDFLARED_VERSION:-2026.9.2}
amd64_sha=${CLOUDFLARED_AMD64_SHA256:-ea2c9bb2d5017a796b64bf36e605d727accf76a5500014bb12952ce11ae1f932}
arm64_sha=${CLOUDFLARED_ARM64_SHA256:-39f23e7c55ce2c2e502a0b3e070b978bf69135b19246b5b7581dadb94cf2144d}
token_file=${CLOUDFLARE_TUNNEL_TOKEN_FILE:-/etc/homex/cloudflared/tunnel-token}

case "$(uname -m)" in
  x86_64|amd64)
    artifact=cloudflared-linux-amd64
    expected_sha=$amd64_sha
    ;;
  aarch64|arm64)
    artifact=cloudflared-linux-arm64
    expected_sha=$arm64_sha
    ;;
  *)
    echo "Arquitectura no soportada por este instalador: $(uname -m)" >&2
    exit 2
    ;;
esac

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT INT TERM

url="https://github.com/cloudflare/cloudflared/releases/download/${version}/${artifact}"

echo "Descargando cloudflared ${version} (${artifact})..."
curl --fail --location --silent --show-error "$url" --output "$tmp"
printf '%s  %s\n' "$expected_sha" "$tmp" | sha256sum --check --status

sudo install -m 0755 "$tmp" /usr/local/bin/cloudflared
sudo install -d -m 0700 /etc/homex/cloudflared
sudo install -m 0644 systemd/homex-cloudflared.service /etc/systemd/system/homex-cloudflared.service
sudo systemctl daemon-reload

installed=$(/usr/local/bin/cloudflared --version)
case "$installed" in
  *"$version"*) ;;
  *)
    echo "Versión instalada inesperada: $installed" >&2
    exit 1
    ;;
esac

echo "cloudflared $version instalado y fijado por SHA256."
if sudo test -s "$token_file"; then
  sudo chmod 0600 "$token_file"
  sudo systemctl enable --now homex-cloudflared.service
  sudo systemctl --no-pager --full status homex-cloudflared.service || true
else
  cat <<EOF
El servicio todavía NO se inició porque falta el token en:
  $token_file

Créelo sin dejar el token en el historial:
  sudo sh -c 'umask 077; cat > $token_file'
Pegue el token, presione Enter y luego Ctrl-D.

Después:
  sudo systemctl enable --now homex-cloudflared.service
EOF
fi
