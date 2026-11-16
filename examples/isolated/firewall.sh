#!/usr/bin/env bash
# Изоляция контейнера от LAN и docker-сетей. Не полагается на заранее известную подсеть:
# читает ФАКТИЧЕСКУЮ конфигурацию контейнера в Docker и строит правила под неё.
#
#   ./firewall.sh apply    — перестроить правила по факту
#   ./firewall.sh check    — перестроить, если конфигурация изменилась (для таймера)
#   ./firewall.sh status   — показать состояние
#   ./firewall.sh remove   — снять все свои правила
#
# Fail-closed: если контейнер запущен в режиме, где правила бессильны
# (--network host и подобные), он ОСТАНАВЛИВАЕТСЯ, а не остаётся открытым.
set -euo pipefail

CONTAINER="${CONTAINER:-hermes-iso}"
CHAIN="HERMES-ISO"
TAG="hermes-iso"                      # метка всех наших правил
DESTS=(192.168.0.0/16 10.0.0.0/8 172.16.0.0/12)
STATE="/run/hermes-iso-firewall.state"

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo $0 $*" >&2; exit 1; }

inspect() {
  docker inspect -f '{{.State.Running}}|{{.HostConfig.NetworkMode}}|{{range .NetworkSettings.Networks}}{{.IPAddress}};{{end}}|{{range .NetworkSettings.Networks}}{{.GlobalIPv6Address}};{{end}}' "$CONTAINER" 2>/dev/null || true
}

# Удалить все наши правила и цепочку (v4 и v6)
purge() {
  local rule
  while rule=$(iptables -S DOCKER-USER 2>/dev/null | grep -F -- "--comment $TAG" | head -1 | sed 's/^-A DOCKER-USER //') && [ -n "$rule" ]; do
    # shellcheck disable=SC2086
    iptables -D DOCKER-USER $rule 2>/dev/null || break
  done
  while rule=$(iptables -S INPUT 2>/dev/null | grep -F -- "--comment $TAG" | head -1 | sed 's/^-A INPUT //') && [ -n "$rule" ]; do
    # shellcheck disable=SC2086
    iptables -D INPUT $rule 2>/dev/null || break
  done
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true

  if command -v ip6tables >/dev/null 2>&1; then
    while rule=$(ip6tables -S DOCKER-USER 2>/dev/null | grep -F -- "--comment $TAG" | head -1 | sed 's/^-A DOCKER-USER //') && [ -n "$rule" ]; do
      # shellcheck disable=SC2086
      ip6tables -D DOCKER-USER $rule 2>/dev/null || break
    done
    while rule=$(ip6tables -S INPUT 2>/dev/null | grep -F -- "--comment $TAG" | head -1 | sed 's/^-A INPUT //') && [ -n "$rule" ]; do
      # shellcheck disable=SC2086
      ip6tables -D INPUT $rule 2>/dev/null || break
    done
  fi
  rm -f "$STATE"
}

# Docker отдаёт строку "invalid IP" для пустых адресов — фильтруем
ip4_list() { printf '%s' "$1" | tr ';' '\n' | grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' || true; }
ip6_list() { printf '%s' "$1" | tr ';' '\n' | grep -E '^[0-9a-fA-F:]+:[0-9a-fA-F:]*$' || true; }

apply() {
  local info running mode v4 v6 ip
  info=$(inspect)
  if [ -z "$info" ]; then echo "контейнер $CONTAINER не создан"; purge; return 0; fi
  IFS='|' read -r running mode v4 v6 <<< "$info"

  if [ "$running" != "true" ]; then echo "контейнер не запущен"; purge; return 0; fi

  case "$mode" in
    host|container:*)
      echo "ОПАСНО: NetworkMode=$mode — правила не отсекают сеть контейнера, останавливаю $CONTAINER" >&2
      docker stop "$CONTAINER" >/dev/null 2>&1 || true
      purge; return 3 ;;
  esac

  # macvlan/ipvlan: контейнер получает адрес прямо в LAN, iptables его не фильтрует
  local net drv
  for net in $(docker inspect -f '{{range $n,$v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$CONTAINER" 2>/dev/null); do
    drv=$(docker network inspect -f '{{.Driver}}' "$net" 2>/dev/null || true)
    case "$drv" in
      macvlan|ipvlan)
        echo "ОПАСНО: сеть $net драйвера $drv — контейнер в LAN напрямую, останавливаю $CONTAINER" >&2
        docker stop "$CONTAINER" >/dev/null 2>&1 || true
        purge; return 3 ;;
    esac
  done

  purge
  iptables -N "$CHAIN"
  iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  iptables -A "$CHAIN" -j DROP

  local n=0
  for ip in $(ip4_list "$v4"); do
    for d in "${DESTS[@]}"; do
      iptables -I DOCKER-USER 1 -s "$ip" -d "$d" -m comment --comment "$TAG" -j DROP
    done
    # Трафик на сам хост (bridge-адрес и LAN-адрес хоста) идёт в INPUT, не в FORWARD
    iptables -I INPUT 1 -s "$ip" -m comment --comment "$TAG" -j "$CHAIN"
    n=$((n+1))
  done

  # IPv6: если Docker его включит — контейнеру закрыто всё, кроме ответов на свои соединения
  local n6=0
  if command -v ip6tables >/dev/null 2>&1; then
    for ip in $(ip6_list "$v6"); do
      ip6tables -I INPUT 1 -s "$ip" -m comment --comment "$TAG" -j DROP
      ip6tables -I DOCKER-USER 1 -s "$ip" -m comment --comment "$TAG" -j DROP
      n6=$((n6+1))
    done
  fi

  printf '%s|%s|%s\n' "$mode" "$v4" "$v6" > "$STATE"
  echo "применено: mode=$mode, IPv4-адресов $n, IPv6-адресов $n6"
}

status() {
  local info running mode v4 v6 ip n=0
  info=$(inspect); [ -n "$info" ] || { echo "контейнер не создан"; return 0; }
  IFS='|' read -r running mode v4 v6 <<< "$info"
  [ "$running" = "true" ] || { echo "контейнер не запущен — правил нет (норма)"; return 0; }
  for ip in $(ip4_list "$v4"); do
    for d in "${DESTS[@]}"; do
      iptables -C DOCKER-USER -s "$ip" -d "$d" -m comment --comment "$TAG" -j DROP 2>/dev/null && n=$((n+1))
    done
    iptables -C INPUT -s "$ip" -m comment --comment "$TAG" -j "$CHAIN" 2>/dev/null && n=$((n+1))
  done
  if [ "$n" -ge 4 ]; then echo "защищён: $n правил, mode=$mode"; else echo "НЕ ЗАЩИЩЁН: найдено $n правил, mode=$mode"; return 1; fi
}

case "${1:-}" in
  apply)  apply ;;
  check)
    info=$(inspect)
    if [ -z "$info" ]; then purge; exit 0; fi
    IFS='|' read -r running mode v4 v6 <<< "$info"
    cur="$mode|$v4|$v6"
    if [ "$running" != "true" ]; then purge; exit 0; fi
    if [ ! -f "$STATE" ] || [ "$(cat "$STATE")" != "$cur" ]; then apply; fi ;;
  status) status ;;
  remove) purge; echo "снято" ;;
  *) echo "usage: $0 {apply|check|status|remove}" >&2; exit 2 ;;
esac