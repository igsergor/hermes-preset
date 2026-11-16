#!/usr/bin/env bash
# Закрывает изолированному контейнеру локальную сеть и docker-сети, оставляя интернет.
#   ./firewall.sh apply
#   ./firewall.sh remove
set -euo pipefail

CONTAINER="${CONTAINER:-hermes-iso}"
CHAIN="HERMES-ISO"

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo $0 $*" >&2; exit 1; }

ip_of() {
  docker inspect "$CONTAINER" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \
    | tr ' ' '\n' | grep -E '^[0-9]+\.' | head -1
}

apply() {
  local ip; ip=$(ip_of)
  [ -n "$ip" ] || { echo "контейнер $CONTAINER не запущен" >&2; exit 1; }

  # Трафик наружу: LAN, VPN-подсеть, другие docker-сети
  iptables -I DOCKER-USER 1 -s "$ip" -d 192.168.0.0/16 -j DROP
  iptables -I DOCKER-USER 1 -s "$ip" -d 10.0.0.0/8     -j DROP
  iptables -I DOCKER-USER 1 -s "$ip" -d 172.16.0.0/12  -j DROP

  # Трафик на сам хост (адреса bridge принадлежат хосту -> INPUT, не FORWARD)
  iptables -N "$CHAIN" 2>/dev/null || true
  iptables -C INPUT -s "$ip" -j "$CHAIN" 2>/dev/null || iptables -I INPUT 1 -s "$ip" -j "$CHAIN"
  iptables -F "$CHAIN"
  iptables -A "$CHAIN" -d 172.16.0.0/12 -j DROP
  iptables -A "$CHAIN" -d 10.0.0.0/8    -j DROP
  iptables -A "$CHAIN" -d 127.0.0.0/8   -j DROP
  iptables -A "$CHAIN" -j RETURN

  echo "применено для $CONTAINER ($ip)"
}

remove() {
  local ip; ip=$(ip_of || true)
  if [ -n "${ip:-}" ]; then
    iptables -D DOCKER-USER -s "$ip" -d 192.168.0.0/16 -j DROP 2>/dev/null || true
    iptables -D DOCKER-USER -s "$ip" -d 10.0.0.0/8     -j DROP 2>/dev/null || true
    iptables -D DOCKER-USER -s "$ip" -d 172.16.0.0/12  -j DROP 2>/dev/null || true
    iptables -D INPUT -s "$ip" -j "$CHAIN" 2>/dev/null || true
  fi
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true
  echo "снято"
}

case "${1:-}" in
  apply)  apply ;;
  remove) remove ;;
  *) echo "usage: $0 {apply|remove}" >&2; exit 2 ;;
esac