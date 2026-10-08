#!/bin/sh
set -eu

connection=${HOMEX_PRIVATE_CONNECTION:-homex-private}
interface=${HOMEX_PRIVATE_INTERFACE:-homex0}
address=${HOMEX_PRIVATE_ADDRESS:-10.254.254.1/32}
hostname=${HOMEX_PRIVATE_HOSTNAME:-homex.internal}
host_ip=${address%/*}

if ! command -v nmcli >/dev/null 2>&1; then
  echo "NetworkManager/nmcli es obligatorio para preparar el endpoint privado HOMEX" >&2
  exit 2
fi

if nmcli -t -f NAME connection show | grep -Fxq "$connection"; then
  sudo nmcli connection modify \
    "$connection" \
    connection.interface-name "$interface" \
    ipv4.method manual \
    ipv4.addresses "$address" \
    ipv4.never-default yes \
    ipv6.method disabled \
    connection.autoconnect yes
else
  sudo nmcli connection add \
    type dummy \
    ifname "$interface" \
    con-name "$connection" \
    ipv4.method manual \
    ipv4.addresses "$address" \
    ipv4.never-default yes \
    ipv6.method disabled

  sudo nmcli connection modify \
    "$connection" \
    connection.autoconnect yes
fi

sudo nmcli connection up "$connection"

if ! ip -4 addr show "$interface" | grep -Fq "$host_ip/"; then
  echo "No quedó asignada $address a $interface" >&2
  exit 1
fi

if [ "$hostname" != "homex.internal" ]; then
  echo "HOMEX_PRIVATE_HOSTNAME debe ser homex.internal para D04" >&2
  exit 2
fi

if grep -qE '^[[:space:]]*[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[[:space:]]+homex\.internal[[:space:]]*$' /etc/hosts; then
  sudo sed -i \
    -E "s#^[[:space:]]*[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[[:space:]]+homex\.internal[[:space:]]*\$#$host_ip homex.internal#" \
    /etc/hosts
else
  printf '%s %s\n' "$host_ip" "$hostname" | sudo tee -a /etc/hosts >/dev/null
fi

echo "homex-private-endpoint-ok"
echo "$interface -> $address"
echo "$hostname -> $host_ip"
