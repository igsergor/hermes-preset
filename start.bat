@echo off
setlocal
set IMAGE=ghcr.io/igsergor/hermes-preset:latest
set NAME=hermes

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker не найден. Установи Docker Desktop: https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)

docker ps -a --format "{{.Names}}" | findstr /x "%NAME%" >nul
if not errorlevel 1 (
  echo Контейнер уже создан — запускаю.
  docker start %NAME% >nul
) else (
  docker run -d --name %NAME% -p 127.0.0.1:9119:9119 -v hermes-data:/opt/data %IMAGE% gateway run
)

echo.
echo Жду, пока поднимется дашборд...
timeout /t 8 /nobreak >nul
start "" http://localhost:9119
echo Открыл http://localhost:9119 — вставь ключ провайдера.
pause