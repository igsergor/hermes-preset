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
| Интернет через VLESS | MikroTik заворачивает весь .130 | контейнер выходит через тот же шлюз, что и первый Hermes |

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

## Интернет через VLESS — уже работает, настраивать нечего

Хост .130 целиком завёрнут в VLESS-шлюз на уровне MikroTik (policy routing по адресу клиента),
поэтому контейнер через обычный NAT хоста получает тот же выход, что и первый Hermes.
Проверено: `curl 'http://ip-api.com/line/?fields=country,isp,query'` внутри контейнера даёт
тот же egress, что на хосте (Sweden, OC NETWORKS).

Отдельный WireGuard-клиент на хосте не нужен и не должен настраиваться: доступ к домашней
WG-сети контейнеру не даётся — наоборот, он её не видит (правила `firewall.sh` режут
`192.168.1.0/24` и `10.0.0.0/8`). Заворот трафика делает роутер, контейнер об этом ничего не знает.

Проверка после запуска:

```bash
docker exec hermes-iso curl -s 'http://ip-api.com/line/?fields=country,isp,query'
```
