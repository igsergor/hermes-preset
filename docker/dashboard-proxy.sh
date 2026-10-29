#!/command/with-contenv bash
# Дашборд слушает только loopback (9120) — поэтому не требует пароля.
# Прокси публикует его на 0.0.0.0:9119 внутри контейнера; на хост порт
# пробрасывается как 127.0.0.1:9119, то есть наружу доступа нет.
set -u
PORT="${HERMES_DASHBOARD_PUBLIC_PORT:-9119}"
while true; do
    socat TCP-LISTEN:"$PORT",fork,reuseaddr TCP:127.0.0.1:9120
    sleep 1
done