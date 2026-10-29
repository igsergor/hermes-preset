# syntax=docker/dockerfile:1.7
#
# Hermes Agent — русский пресет «из коробки».
# База — официальный образ Nous Research. Мы добавляем только:
#   * Ollama + bge-m3 (локальные эмбеддинги, как в оригинальной сборке)
#   * преднастроенный профиль в /opt/defaults (скиллы, волт, кроны, конфиг)
#   * seed при первом старте и loopback-прокси для дашборда
#
# Ключей и личных данных внутри нет и быть не должно: публичный образ
# изучаем кем угодно, ключ вводится в дашборде уже после запуска.

FROM nousresearch/hermes-agent:stable

LABEL org.opencontainers.image.source="https://github.com/igsergor/hermes-preset" \
      org.opencontainers.image.description="Hermes Agent ru preset: skills, Obsidian memory, local embeddings"

ARG TARGETARCH
ENV TZ=UTC \
    OLLAMA_MODELS=/opt/ollama/models \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_KEEP_ALIVE=10m \
    OLLAMA_MAX_LOADED_MODELS=1 \
    OLLAMA_NUM_PARALLEL=1 \
    HERMES_DASHBOARD=1 \
    HERMES_DASHBOARD_HOST=127.0.0.1 \
    HERMES_DASHBOARD_PORT=9120

USER root

# --- socat: публикует дашборд на 0.0.0.0:9119 внутри контейнера, но сам
#     дашборд слушает loopback и потому не требует пароля. Хост-порт
#     публикуется только на 127.0.0.1, наружу ничего не торчит.
RUN apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends socat zstd && \
    rm -rf /var/lib/apt/lists/*

# --- Ollama (CPU). Модель тянется на этапе сборки: первый запуск у
#     пользователя не должен ничего докачивать.
RUN set -eux; \
    curl -fsSL --retry 3 --retry-all-errors https://ollama.com/install.sh | sh; \
    /usr/local/bin/ollama --version

RUN set -eux; \
    mkdir -p "$OLLAMA_MODELS"; \
    ollama serve >/tmp/ollama-build.log 2>&1 & \
    for i in $(seq 1 90); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull bge-m3; \
    ollama list; \
    pkill -f 'ollama serve' || true; sleep 1; \
    du -sh "$OLLAMA_MODELS"; \
    chown -R 10000:10000 /opt/ollama

# --- Python-зависимости плагина памяти: frontmatter (yaml), векторный
#     индекс (numpy + sqlite-vec) и локальный Qdrant-путь (qdrant-client).
RUN /opt/hermes/.venv/bin/python3 -m ensurepip --upgrade >/dev/null 2>&1 && \
    /opt/hermes/.venv/bin/python3 -m pip install --no-cache-dir --disable-pip-version-check \
        pyyaml numpy qdrant-client sqlite-vec && \
    rm -rf /root/.cache/pip

# --- Пресет: конфиг, скиллы, волт, кроны, плагин памяти.
# Конфиг и скиллы кладём туда, откуда базовый образ их разворачивает при
# первом старте: так профиль создаётся сразу правильным, без гонки с stage2.
COPY preset/ /opt/defaults/
RUN set -eux; \
    cp /opt/defaults/config.yaml /opt/hermes/cli-config.yaml.example; \
    rm -rf /opt/hermes/skills/*; \
    cp -a /opt/defaults/skills/. /opt/hermes/skills/; \
    chmod -R a+rX /opt/defaults /opt/hermes/skills; \
    find /opt/defaults /opt/hermes/skills -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

# --- Seed при первом старте (пустой том) и прокси дашборда.
COPY docker/seed-preset.sh /etc/cont-init.d/05-preset-seed
COPY docker/ollama-run.sh /etc/s6-overlay/s6-rc.d/ollama/run
COPY docker/dashboard-proxy.sh /etc/s6-overlay/s6-rc.d/dashboard-proxy/run
RUN chmod 0755 /etc/cont-init.d/05-preset-seed \
              /etc/s6-overlay/s6-rc.d/ollama/run \
              /etc/s6-overlay/s6-rc.d/dashboard-proxy/run && \
    printf 'longrun\n' > /etc/s6-overlay/s6-rc.d/ollama/type && \
    printf 'longrun\n' > /etc/s6-overlay/s6-rc.d/dashboard-proxy/type && \
    mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d && \
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/ollama \
          /etc/s6-overlay/s6-rc.d/user/contents.d/dashboard-proxy

EXPOSE 9119