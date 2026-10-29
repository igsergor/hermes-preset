#!/command/with-contenv bash
# Первый запуск: добавляем в профиль то, чего нет в базовом образе —
# плагин памяти, волт и кроны. Конфиг и скиллы приходят из самого образа
# (cli-config.yaml.example и /opt/hermes/skills), их не трогаем.
set -eu

DATA="${HERMES_HOME:-/opt/data}"
MARKER="$DATA/.preset-seeded"
DEFAULTS=/opt/defaults

if [ -e "$MARKER" ]; then
    exit 0
fi

echo "[preset] первый запуск: доразворачиваю пресет в $DATA"

# Plугин памяти — только если его ещё нет (не перезаписываем пользовательский).
mkdir -p "$DATA/plugins"
if [ -d "$DEFAULTS/plugins/obsidian_memory" ] && [ ! -d "$DATA/plugins/obsidian_memory" ]; then
    cp -a "$DEFAULTS/plugins/obsidian_memory" "$DATA/plugins/"
fi

# Волт-скелет.
if [ ! -d "$DATA/vault" ]; then
    cp -a "$DEFAULTS/vault" "$DATA/vault"
fi
mkdir -p "$DATA/vault/Brain/facts" "$DATA/vault/Knowledge" "$DATA/vault/Daily" "$DATA/vault/Resources"

# Кроны — только на пустом профиле.
mkdir -p "$DATA/cron"
if [ ! -f "$DATA/cron/jobs.json" ]; then
    cp -a "$DEFAULTS/cron/jobs.json" "$DATA/cron/jobs.json"
fi

printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$MARKER"

if id hermes >/dev/null 2>&1; then
    chown -R hermes:hermes "$DATA/plugins" "$DATA/vault" "$DATA/cron" 2>/dev/null || true
fi

echo "[preset] готово: $(find "$DATA"/skills -name SKILL.md 2>/dev/null | wc -l) скиллов, $(find "$DATA"/vault -name '*.md' 2>/dev/null | wc -l) заметок"
echo "[preset] открой http://localhost:9119 и вставь ключ провайдера"