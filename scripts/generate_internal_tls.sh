#!/bin/sh
set -eu

hostname=${HOMEX_PRIVATE_HOSTNAME:-homex.internal}
tls_dir=${HOMEX_TLS_DIR:-/etc/homex/tls}
nginx_gid=${HOMEX_NGINX_GID:-101}
force=${HOMEX_TLS_FORCE:-0}

case "$hostname" in
  *.*) ;;
  *)
    echo "HOMEX_PRIVATE_HOSTNAME debe ser un hostname completo, por ejemplo homex.internal" >&2
    exit 2
    ;;
esac

command -v openssl >/dev/null 2>&1 || {
  echo "openssl es obligatorio" >&2
  exit 2
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM
umask 077

ca_key="$tls_dir/homex-root-ca.key"
ca_cert="$tls_dir/homex-root-ca.crt"
server_key="$tls_dir/$hostname.key"
server_cert="$tls_dir/$hostname.crt"

sudo install -d -o root -g root -m 0755 "$tls_dir"

if [ ! -s "$ca_key" ] || [ ! -s "$ca_cert" ]; then
  openssl genrsa -out "$tmp/ca.key" 3072
  openssl req -x509 -new -sha256 -days 3650 \
    -key "$tmp/ca.key" \
    -subj "/CN=HOMEX Local Root CA/O=HOMEX" \
    -out "$tmp/ca.crt"

  sudo install -o root -g root -m 0600 "$tmp/ca.key" "$ca_key"
  sudo install -o root -g root -m 0644 "$tmp/ca.crt" "$ca_cert"
  echo "CA local HOMEX creada."
else
  echo "CA local HOMEX existente: se reutiliza."
fi

if [ "$force" != "1" ] && [ -s "$server_key" ] && [ -s "$server_cert" ]; then
  echo "Certificado servidor existente: $server_cert"
else
  openssl genrsa -out "$tmp/server.key" 2048
  openssl req -new \
    -key "$tmp/server.key" \
    -subj "/CN=$hostname/O=HOMEX" \
    -out "$tmp/server.csr"

  cat > "$tmp/server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$hostname
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

  sudo openssl x509 -req -sha256 -days 365 \
    -in "$tmp/server.csr" \
    -CA "$ca_cert" \
    -CAkey "$ca_key" \
    -CAcreateserial \
    -extfile "$tmp/server.ext" \
    -out "$tmp/server.crt"

  sudo install -o root -g "$nginx_gid" -m 0640 "$tmp/server.key" "$server_key"
  sudo install -o root -g root -m 0644 "$tmp/server.crt" "$server_cert"
fi

openssl verify -CAfile "$ca_cert" "$server_cert"
openssl x509 -in "$server_cert" -noout -checkend 2592000 >/dev/null || {
  echo "El certificado de servidor vence en menos de 30 días." >&2
  exit 1
}

if ! openssl x509 -in "$server_cert" -noout -ext subjectAltName | grep -Fq "DNS:$hostname"; then
  echo "El certificado no contiene SAN DNS:$hostname" >&2
  exit 1
fi

echo
echo "TLS HOMEX listo:"
echo "  CA para instalar en dispositivos: $ca_cert"
echo "  Certificado servidor:             $server_cert"
echo "  Clave servidor:                   $server_key"
echo
echo "Huella SHA256 de la CA:"
openssl x509 -in "$ca_cert" -noout -fingerprint -sha256
