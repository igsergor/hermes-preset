# Hermes в изолированном контейнере рядом с другим Hermes

Сценарий: на одном Linux-хосте уже работает один Hermes, и нужно поднять второй —
так, чтобы он не видел ни файлы хоста, ни локальную сеть, имел доступ в интернет
и одну папку на сетевой шаре.

Проверено на Ubuntu 24.04, Docker 29.x, образ `ghcr.io/igsergor/hermes-preset:latest`.

## Что даёт изоляцию и что нет

| Уровень | Как | Результат |
|---|---|---|
| Файлы хоста | ничего не монтировать, кроме тома данных | `/home`, `/etc`, `/var` хоста недоступны |
| Docker-сокет | не монтировать `/var/run/docker.sock` | нет управления хостовым Docker |
| Права | `cap_drop: ALL` + минимум обратно, `no-new-privileges` | нет `SYS_ADMIN`, `NET_ADMIN`, `DAC_READ_SEARCH` |
| Ресурсы | `cpus`, `mem_limit`, `pids_limit` | второй экземпляр не съест хост |
| Локальная сеть | правила iptables (см. `firewall.sh`) | LAN и docker-сети недоступны, интернет работает |
| Шара | **bind-mount одной подпапки** | видна только она, соседние каталоги — нет |
| Интернет через VPN | WireGuard-клиент + policy routing | см. «Чего не хватает» ниже |

Важно: `cap_drop: ALL` в чистом виде **ломает** образ — s6-overlay внутри требует
`CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETGID`, `SETUID`, `KILL`, `MKNOD`.
Без них контейнер падает на `s6-applyuidgid: fatal: unable to set supplementary group list`.

## Запуск

```bash
export SHARE_DIR=/mnt/myfiles/igser/hermes-share   # папка на шаре, уже смонтированной на хосте
docker compose -f docker-compose.yml up -d
sudo ./firewall.sh apply                            # закрыть LAN и docker-сети для этого контейнера
```

Проверка:

```bash
docker exec hermes-iso /opt/hermes/.venv/bin/python3 - <<'EOF'
import socket
for h,p in [("192.168.1.1",80),("172.18.0.1",9119),("1.1.1.1",443)]:
    s=socket.socket(); s.settimeout(3)
    try: s.connect((h,p)); print(h,"OPEN")
    except Exception as e: print(h,type(e).__name__)
    finally: s.close()
EOF
```

Ожидаемо: LAN и `172.18.0.1:9119` — таймаут, `1.1.1.1:443` — OPEN.

## Правила iptables: зачем два набора

- `DOCKER-USER` (цепочка FORWARD) — трафик контейнера **наружу** в LAN.
- `INPUT` — трафик контейнера **на сам хост**: адреса `172.17.0.1`/`172.18.0.1`
  принадлежат хосту, поэтому в FORWARD они не попадают. Без этого правила контейнер
  достаёт, например, дашборд соседнего Hermes на `172.18.0.1:9119` и SSH на `:22`.

`firewall.sh` ставит оба набора и умеет `remove`. Правила живут до перезагрузки —
для постоянства добавь вызов в systemd-юнит после `docker.service`.

## Чего не хватает для «интернет только через VPN»

Сейчас контейнер выходит в интернет напрямую через NAT хоста. Чтобы весь его трафик
шёл в туннель, нужен WireGuard-клиент и policy routing **на хосте** (ядро поддерживает
модуль `wireguard`, пакет `wireguard-tools` надо поставить):

1. Поднять `wg0` с `AllowedIPs = 0.0.0.0/0`, `Table = off`.
2. Своя таблица маршрутизации: `default dev wg0` + `blackhole` на LAN.
3. `ip rule add from <IP контейнера> lookup <таблица>` — только этот контейнер идёт в туннель,
   остальной хост (и первый Hermes) — как раньше.
4. На стороне VPN-сервера (MikroTik) для этого peer'а запретить доступ к `192.168.1.0/24`
   и `10.10.10.0/24`, разрешить только интернет.

Такой схеме нужен свободный peer на роутере. Пока он не заведён, изоляция ограничивается
локальной сетью (то есть ровно тем, что делает `firewall.sh`).