#!/bin/sh
# macOS launcher (двойной клик в Finder)
set -eu
IMAGE="${HERMES_IMAGE:-ghcr.io/igsergor/hermes-preset:latest}"
NAME="${HERMES_NAME:-hermes}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден. Поставь Docker Desktop: https://www.docker.com/products/docker-desktop/"
  read -r _ || true
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  docker start "$NAME" >/dev/null
else
  docker run -d --name "$NAME" -p 127.0.0.1:9119:9119 -v hermes-data:/opt/data "$IMAGE" gateway run
fi

echo "Жду дашборд..."
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null http://localhost:9119 2>/dev/null; then break; fi
  sleep 1
done
open http://localhost:9119
echo "Открыл http://localhost:9119 — вставь ключ провайдера."