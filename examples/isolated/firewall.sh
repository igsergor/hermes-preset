#!/usr/bin/env bash
# Закрывает изолированному контейнеру локальную сеть и docker-сети, оставляя интернет.
#   ./firewall.sh apply
#   ./firewall.sh remove
#
# Правила привязаны к ПОДСЕТИ docker-сети (172.28.0.0/24 из compose), а не к IP
# контейнера: пересоздание контейнера и смена его адреса внутри подсети их не ломают.
set -euo pipefail

SUBNET="${SUBNET:-172.28.0.0/24}"
CHAIN="HERMES-ISO"

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo $0 $*" >&2; exit 1; }

apply() {
  # Трафик наружу: LAN, VPN-подсети, любые другие docker-сети
  for d in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
    iptables -C DOCKER-USER -s "$SUBNET" -d "$d" -j DROP 2>/dev/null \
      || iptables -I DOCKER-USER 1 -s "$SUBNET" -d "$d" -j DROP
  done

  # Трафик на сам хост. Адреса bridge (172.17.0.1/172.28.0.1) и LAN-адрес хоста
  # (192.168.1.130) принадлежат хосту, поэтому в FORWARD не попадают — нужен INPUT.
  # Без этих правил контейнер достаёт дашборд соседнего Hermes (:9119) и SSH (:22).
  iptables -N "$CHAIN" 2>/dev/null || true
  iptables -C INPUT -s "$SUBNET" -j "$CHAIN" 2>/dev/null || iptables -I INPUT 1 -s "$SUBNET" -j "$CHAIN"
  iptables -F "$CHAIN"
  # Ответы на собственные исходящие соединения контейнера пропускаем, всё прочее — DROP
  iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  iptables -A "$CHAIN" -j DROP

  echo "применено для подсети $SUBNET"
}

remove() {
  for d in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
    iptables -D DOCKER-USER -s "$SUBNET" -d "$d" -j DROP 2>/dev/null || true
  done
  iptables -D INPUT -s "$SUBNET" -j "$CHAIN" 2>/dev/null || true
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true
  echo "снято"
}

case "${1:-}" in
  apply)  apply ;;
  remove) remove ;;
  *) echo "usage: $0 {apply|remove}" >&2; exit 2 ;;
esac