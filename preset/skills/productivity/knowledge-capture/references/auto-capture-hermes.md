# Auto-Capture Hermes Sessions to Obsidian

## Overview
Автоматический захват сессий Hermes Agent в Obsidian vault через парсинг `state.db`.

## Компоненты

### 1. Скрипт автозахвата
**Файл**: `~/.hermes/scripts/auto-capture-obsidian.py`

**Возможности**:
- Парсит `state.db` (SQLite) для извлечения сессий за последние N дней
- Создает структурированные заметки в Inbox/ из шаблона `Session Capture.md`
- Извлекает: цель сессии, ход работы, использованные skills, длительность, модель
- Создает Knowledge entries в Resources/ из шаблона `Knowledge Entry.md`
- Создает Weekly Review из шаблона `Weekly Review.md`

**CLI**:
```bash
# Автозахват сессий (дефолты argparse сейчас --days 3 --limit 40; для бекфилла — больше)
python3 ~/.hermes/scripts/auto-capture-obsidian.py --session
python3 ~/.hermes/scripts/auto-capture-obsidian.py --session --days 180 --limit 800  # разовый бекфилл

# Создать Knowledge entry
python3 ~/.hermes/scripts/auto-capture-obsidian.py --knowledge \
  --title "Название" \
  --project "Hermes Agent" \
  --category "automation" \
  --essence "Суть" \
  --details "Детали" \
  --tech "Команды" \
  --application "Применение" \
  --gotchas "Подводные камни"

# Создать Weekly Review
python3 ~/.hermes/scripts/auto-capture-obsidian.py --weekly
```

### 2. Cron Jobs

| Job | Schedule | Команда |
|-----|----------|---------|
| Auto-capture sessions | 0 2 * * * (ежедневно 02:00) | `auto-capture-obsidian.py --session --days 1 --limit 10` |
| Weekly Review template | 0 10 * * 1 (понедельник 10:00) | `auto-capture-obsidian.py --weekly` |

Оба job'а созданы с `no_agent=true`, `deliver=local` — результат пишется в файлы, не отправляется в Telegram.

### 3. Шаблоны (в Templates/)

| Шаблон | Переменные | Назначение |
|--------|------------|------------|
| `Session Capture.md` | `{{date}}`, `{{session_id}}`, `{{title}}`, `{{platform}}`, `{{thread}}`, `{{chat_id}}`, `{{model}}`, `{{duration}}`, `{{message_count}}`, `{{goal}}`, `{{work_log}}`, `{{skills_used}}`, `{{insights}}`, `{{problems}}`, `{{links}}`, `{{artifacts}}`, `{{next_steps}}` | Автозахват сессии |
| `Knowledge Entry.md` | `{{date}}`, `{{title}}`, `{{project}}`, `{{category}}`, `{{source}}`, `{{essence}}`, `{{details}}`, `{{tech_details}}`, `{{application}}`, `{{gotchas}}`, `{{sources}}` | База знаний |
| `Weekly Review.md` | `{{date}}`, `{{week}}` | Еженедельный обзор |

### 4. Workflow Weekly Review

1. **Понедельник 10:00** — cron создает Weekly Review в Daily/
2. **В течение дня** — разобрать Inbox:
   - Session captures → перенести в Projects/Resources/Archive
   - Knowledge entries → уже в Resources, проверить теги/ссылки
   - Inbox Capture → классифицировать по PARA
3. **Обновить проекты** — статус, прогресс, следующий шаг
4. **Проверить Areas** — регулярные действия
5. **Планирование** — приоритеты на неделю
6. **Hermes/Automation** — проверить cron jobs, VPN, backups

## Извлечение данных из state.db

### Таблица `sessions`
Ключевые поля: `id`, `started_at`, `ended_at`, `title`, `source`, `chat_id`, `thread_id`, `message_count`, `model`, `model_config`

### Таблица `messages`
Ключевые поля: `session_id`, `role`, `content`, `tool_name`, `tool_calls`, `timestamp`

### Определение использованных skills
Парсим `tool_calls` где `function.name == 'skill_view'` → извлекаем `arguments.name`

## Gotchas

- `state.db` схема может меняться при обновлении Hermes — проверять колонки
- Захватывать сессии всех источников (telegram/cron/cli/tui/subagent); шумовые сервисные титулы группируются в один файл на день (`is_noise_title`)
- `deliver=local` означает, что вывод cron job'а не приходит в Telegram — отчёт смотреть в `~/.hermes/cron/output/<job_id>/`
- АРГУМЕНТЫ в `script` крона не пишутся — только чистый путь (см. gotcha 4 в SKILL.md); параметры через дефолты argparse или .sh-обёртку
- При повторном запуске за ту же неделю создается файл с суффиксом `(1)`, `(2)` и т.д. (для Weekly Review; session-заметки дедупятся по водяному знаку и не дублируются)
- Полное описание актуальной логики (группировка шума, префильтры, теги, связи) — в Gotchas 1-22 SKILL.md; этот референс может отставать от cron-версии скрипта

## Связанные заметки в vault

- `Inbox/Session - YYYY-MM-DD - ...md` — автозахваченные сессии
- `Resources/Knowledge - ...md` — база знаний
- `Daily/Weekly Review - YYYY-WNN.md` — еженедельные обзоры
- `Projects/Hermes Agent — Настройка и расширение.md` — главный проект