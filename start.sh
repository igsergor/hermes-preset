#!/usr/bin/env bash
# Linux / macOS launcher
set -eu
IMAGE="${HERMES_IMAGE:-ghcr.io/igsergor/hermes-preset:latest}"
NAME="${HERMES_NAME:-hermes}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден. Linux: https://docs.docker.com/engine/install/  macOS: Docker Desktop"
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "Контейнер уже есть — запускаю."
  docker start "$NAME" >/dev/null
else
  docker run -d --name "$NAME" -p 127.0.0.1:9119:9119 -v hermes-data:/opt/data "$IMAGE" gateway run
fi

URL="http://localhost:9119"
echo "Жду дашборд..."
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null; then break; fi
  sleep 1
done
echo "Открываю $URL"
(command -v xdg-open >/dev/null && xdg-open "$URL") || (command -v open >/dev/null && open "$URL") || echo "Открой вручную: $URL"