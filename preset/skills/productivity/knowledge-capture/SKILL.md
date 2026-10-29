---
name: knowledge-capture
description: "Capture AI agent sessions into PARA knowledge bases."
category: productivity
tags: [knowledge-capture, session-logging, obsidian, PARA, automation, hermes, ai-agents]
version: 1.2.0
---

# Knowledge Capture Skill

Класс-уровневый скилл для автоматического захвата сессий AI-агентов (Hermes, Claude Code, Codex, и др.) в структурированные базы знаний с PARA организацией.

## Когда использовать

- Настройка автозахвата сессий Hermes/другого агента в Obsidian/Notion/Logseq
- Создание базы знаний из диалогов с AI-агентами
- Автоматизация Weekly Review процесса
- Парсинг логов/БД агентов для извлечения инсайтов

## Архитектура

```
Knowledge Capture Pipeline
├── Source (Hermes state.db, Claude Code logs, Codex traces, etc.)
├── Parser (SQLite, JSONL, text logs)
├── Templates (Session Capture, Knowledge Entry, Weekly Review)
├── Vault (Obsidian PARA: Inbox → Projects/Areas/Resources/Archives)
├── Scheduler (cron: daily capture + weekly LLM review + weekly stats)
└── Review Loop (LLM-automated + human spot-checks)
```

## Компоненты

### 1. Источники данных

| Источник | Формат | Парсер |
|----------|--------|--------|
| Hermes Agent | SQLite (`state.db`: sessions + messages) | `auto-capture-obsidian.py` |
| Claude Code | JSONL transcripts | TBD |
| Codex CLI | JSONL transcripts | TBD |
| OpenCode | JSONL transcripts | TBD |
| Generic terminal | `.bash_history`, script output | TBD |

### 2. Шаблоны (Obsidian)

| Шаблон | Frontmatter | Куда кладется |
|--------|-------------|---------------|
| `Session Capture.md` | session_id, platform, thread, model, duration, skills_used | `Archives/Sessions/` |
| `Knowledge Entry.md` | project, category, source, status | `Resources/` |
| `Weekly Review.md` | week, tags: [weekly, review] | `Daily/` |

### 3. Автоматизация (Cron)

Два вида автоматизации: **механическая** (no_agent, предсказуемый скрипт) и **LLM-агентная** (c умным анализом, скиллами, пониманием контента).

| Job | Тип | Расписание | Что делает |
|-----|-----|------------|------------|
| Auto-capture | no_agent | 0 2 * * * | `auto-capture-obsidian.py` (аргументы — в дефолтах argparse: `--days 3 --limit 40`) — сырые сессии в `Archives/Sessions/`: дедуп по водяному знаку, отсев шума, ГРУППИРОВКА сервисных серий (почта, документы, API) |
| Еженедельный разбор Obsidian | ГИБРИД (no_agent=false + pre-run script) | 0 11 * * 1 | `obsidian-weekly-review.py` — механический разбор + per-session LLM дистилляция (макс 8 сессий). Префильтр шума: сервисные заголовки и сессии ≤2 сообщений — БЕЗ LLM. Модель динамически из `config.yaml`; `distill_session` → ('ok'/'empty'/'error', text): ошибки API не помечают сессию обработанной (ретрай), обязателен `stream:false`, unwrap `data{}` для ClinePass |
| Еженедельные снапшоты | LLM-агент | 0 10 * * 1 | Отчёт по токенам/сессиям из state.db |
| Еженедельные обновления | no_agent | 0 9 * * 1 | `daily-updates-check.sh` — apt check |
| Daily Note | no_agent | 0 20 * * * | скрипт `daily-note.py` (см. раздел ниже) |
| Vector index | no_agent | 30 3 * * * | `vault_vector_index.py` — инкрементальная векторизация vault (после capture). Бюджет прогона `--max-hours` / env `VAULT_INDEX_MAX_HOURS` (дефолт 3.5 при таймауте крона 4 ч) |

LLM-агентный cron требует **явной привязки провайдера/модели** в `jobs.json` (поля `model`, `provider`), иначе дрифт сессионной модели может заблокировать запуск (safety guard «unpinned drift»). Пример pinned конфига:
```json
"model": "nvidia/nemotron-3-ultra-550b-a55b:free",
"provider": "openrouter",
"provider_snapshot": "openrouter",
"model_snapshot": "nvidia/nemotron-3-ultra-550b-a55b:free",
"no_agent": false,
"script": null
```

### 4. Связи и поиск знаний

**Vault-first lookup (правило агента):** перед ответом по знакомой теме — grep по vault (подробно в скилле `obsidian-vault`), найденное — ссылкой [[...]]. Векторный prefetch (планируется: bge-m3 через OmniRoute, живой, dim 1024) — ДОПОЛНЕНИЕ к grep'у, не замена: вектор даёт «похожее», grep — «точное»; выдача топ-3-5, не обход графа.

**Связи между знаниями** — по пересечению тематических тегов, механически (gotcha 14). Что тегировать — gotcha 17. Требования к будущей векторной индексации vault: Sessions без шумовых групповых заметок, Daily/Templates не индексировать (фаза 2 для Daily), ключ индексации — хеш контента (не mtime: capture при resume перезаписывает файлы), в session-заметках фильтр по `thread:`/`chat_id:` из frontmatter — prefetch не должен поднимать контекст чужих TG-тредов.

### 5. Weekly Review Process

Два режима:

**A. Ручной (человек разбирает):**
1. Cron создает шаблон в `Daily/Weekly Review - YYYY-WNN.md`
2. Человек разбирает `Inbox/`:
   - Session captures → Projects/Resources/Archive
   - Knowledge entries → уже в Resources, проверка тегов
   - Quick captures → PARA классификация
3. Обновление проектов, Areas, планирование недели

**B. Гибридный (no_agent скрипт + per-session LLM дистилляция, пн 11:00):**\n1. **Механическая часть** (без LLM, ~0.1с): статистика vault (`obsidian stats --brief` — без длинного списка тегов), проверка Inbox на файлы, проверка битых вики-ссылок в хабах (regex).\n2. **Дистилляция знаний** — **не весь vault, а по одной сессии**: скрипт берёт новые сессии из `Archives/Sessions/` (не старше `last_run` из `state.json`), **макс 8 за раз**, и отправляет каждую по отдельности в LLM, выбранную из `model.default` в `config.yaml`. Модель определяется динамически: `get_model_config()` читает `config.yaml`, находит модель в `custom_providers`, и выбирает endpoint: ClinePass → unwrap proxy (`127.0.0.1:8765`), остальные провайдеры → напрямую на их `base_url` с Bearer auth. Сессии, где LLM ответила «нет знаний», помечаются `processed_sessions[]` в `state.json` и не трогаются повторно. Сессии с API-ошибкой НЕ помечаются — перепробуются в следующий раз. Префильтр шума ДО LLM (бесплатно): файлы с сервисными заголовками (почта, документы, Daily Note, «ответь одним словом») и сессии ≤2 сообщений помечаются обработанными без вызова LLM.\n3. **Обработанные сессии** не передистиллируются (проверка по `session_id` в `state.json`).\n4. **Результат:** знания создаются/дополняются в `Resources/Knowledge - *.md`, состояние сохраняется в `.obsidian-weekly-state.json`.\n   Теги и связи знаний: LLM добавляет в конец ответа строку `TAGS: тег1, тег2, тег3` (2-4 тематических тега латиницей), `parse_tags()` выделяет её, `create_knowledge_note()` вшивает теги в frontmatter и механически (regex, без LLM) линкует существующие Knowledge-заметки с пересечением тегов в обе стороны («🔗 Связанные знания» / «🔗 См. также»). Связи — локальные подсказки при чтении одной заметки, не приглашение обходить граф; шаблонные ссылки сессий на хабы (Resources Hub / Project / Area) — для человека в Obsidian, их не читать.\n5. Отправляет отчёт в Telegram со: статистикой, Inbox (если непусто), сколько сессий обработано/какие знания добавлены, битые ссылки (если есть).\n6. При пустом Inbox и отсутствии новых сессий — кратко сообщает что всё чисто.\n\n**Подробнее:** скрипт `~/.hermes/scripts/obsidian-weekly-review.py`, cron job `7fa6f2f77e31`, **`no_agent: false`** (гибрид): scheduler сам исполняет `script` pre-run и кладёт stdout в «Script Output», затем агент форматирует. Промпт агента ОБЯЗАН говорить «скрипт уже выполнен — НЕ запускай повторно, просто выдай Script Output полностью» — иначе двойной прогон: второй прогон видит обновлённый state.json и честно рапортует «новых сессий нет», а сводка агента противоречит факту (заметки созданы, отчёт — «0 дистилляций»).\n\n**Важно: no_agent скрипты и длина вывода** — no_agent cron доставляет stdout одной порцией в Telegram. Если вывод слишком длинный (строка тегов на 61 позицию), Telegram обрезает на середине. **Не обрезать вывод в скрипте** — вместо этого сократить источник данных. Для `obsidian-cli.py stats` добавлен флаг `--brief`: показывает количество тегов без списка имён. Использовать в автоматических отчётах: `obsidian stats --brief`. Если разбивка на сообщения необходима — переключить задачу на LLM-агентный cron (no_agent=false), где агент сам решит как отправлять.\n\n**Динамический роутинг провайдера (ключевой паттерн):**\n- `get_model_config()` читает `model.default` из `config.yaml`\n- Ищет модель в `custom_providers[]`, сопоставляя `models[].id`\n- Если провайдер ClinePass (base_url содержит `127.0.0.1:8765` или model_id содержит `cline-pass`): endpoint = `base_url + /chat/completions`, без Bearer (прокси сам авторизует)\n- Для остальных провайдеров: endpoint = `base_url + /chat/completions`, с `Authorization: Bearer {api_key}` (берётся из `prov.api_key` или `env[key_env]`)\n- Если модель не найдена в `custom_providers` — fallback на unwrap proxy (старое поведение)\n- Детали: см. `references/no-agent-dynamic-provider.md`\n\n**Какой режим выбрать:** гибридный — для поддержания чистоты с реальной дистилляцией знаний без перегрузки контекста. Ручной — для глубокого разбора и перепланирования проектов.

## Реализация для Hermes (референс)

### Скрипт: `~/.hermes/scripts/auto-capture-obsidian.py`

Рабочая реализация автозахвата (актуальный исполняемый файл в cron). Копия в `scripts/capture-hermes.py` (в этом скилле) — референс-версия, возможно отстаёт от cron-версии. При доработках править обе копии или объединить.

```bash
# Захват сессий (аргументы сейчас в дефолтах argparse: --days 3 --limit 40)
python3 ~/.hermes/scripts/auto-capture-obsidian.py --session
# Аудит/бекфилл покрытия: разовый прогон с большой глубиной (безопасен: дедуп по водяному знаку)
python3 ~/.hermes/scripts/auto-capture-obsidian.py --session --days 180 --limit 800

# Ручная Knowledge entry
python3 ~/.hermes/scripts/auto-capture-obsidian.py --knowledge \
  --title "Pattern Name" \
  --project "Project Name" \
  --category "setup|automation|debugging|research" \
  --essence "One-line summary" \
  --details "Full details" \
  --tech "Commands, configs, code" \
  --application "When/how to use" \
  --gotchas "Pitfalls"

# Weekly review template
python3 ~/.hermes/scripts/auto-capture-obsidian.py --weekly
```

### Шаблоны (добавлены в эту сессию)

Все 3 шаблона созданы в `Templates/` vault'а и зарегистрированы в `obsidian-cli.py`:

| Шаблон | Переменные | Папка назначения |
|--------|------------|------------------|
| `Session Capture.md` | `{{date}}`, `{{session_id}}`, `{{title}}`, `{{platform}}`, `{{thread}}`, `{{chat_id}}`, `{{model}}`, `{{duration}}`, `{{message_count}}`, `{{goal}}`, `{{work_log}}`, `{{skills_used}}`, `{{insights}}`, `{{problems}}`, `{{links}}`, `{{artifacts}}`, `{{next_steps}}` | `Inbox/` |
| `Knowledge Entry.md` | `{{date}}`, `{{title}}`, `{{project}}`, `{{category}}`, `{{source}}`, `{{essence}}`, `{{details}}`, `{{tech_details}}`, `{{application}}`, `{{gotchas}}`, `{{sources}}` | `Resources/` |
| `Weekly Review.md` | `{{date}}`, `{{week}}` | `Daily/` |

CLI команды для создания:
```bash
obsidian new -t session "Тема" session_id=xxx platform=telegram thread=yyy
obsidian new -t knowledge "Тема" project="Hermes Agent" category=automation essence="Суть"
obsidian new -t weekly
```

### Парсинг state.db

**Selection (по последней активности, а не старту):**
```sql
-- Сессии считаются «актуальными» если у них есть сообщение с timestamp в окне
-- Это ловит возобновлённые сессии (старый started_at, новая активность)
SELECT s.id, s.started_at, s.ended_at, s.title, s.source, s.chat_id,
       s.thread_id, s.message_count, s.model, s.model_config
FROM sessions s
JOIN messages m ON m.session_id = s.id
WHERE m.timestamp > ?
GROUP BY s.id
ORDER BY MAX(m.timestamp) DESC
LIMIT ?;
```

**Сообщения сессии (для парсинга):**
```sql
SELECT role, content, tool_name, tool_calls, timestamp
FROM messages WHERE session_id = ? ORDER BY id;
```

### Извлечение skills
Из `messages.tool_calls` где `function.name == 'skill_view'` → `arguments.name`

## Поддерживаемые Vault'ы

### Obsidian (основной)
- Путь: `~/obsidian-vault` (настраиваемый)
- Структура: PARA (Projects, Areas, Resources, Archives, Inbox, Templates, Daily)
- CLI: `obsidian` command (из obsidian-vault skill)

### Notion (планируется)
- API: notion-sdk
- Database per PARA category

### Logseq (планируется)
- Файловый формат .md в `pages/`, `journals/`

### Daily Note (cron, `8aa21e851f9c`, no_agent, скрипт `daily-note.py`)

Ежедневная заметка `Daily/YYYY-MM-DD.md` создаётся/дополняется скриптом `~/.hermes/scripts/daily-note.py` (переписан 30.09.26, только stdlib):
1. Дата считается в Python (`datetime.now(UTC+4)`), имя файла строго `YYYY-MM-DD.md` (шаблон `{{date:YYYY-MM-DD}}`/`{{date:dddd}}` подставляется; день недели на русский).
2. Источник секции «✅ Выполнено» — сессии state.db за окно дня (UTC+4), выборка по `MAX(messages.timestamp)`, до 7 уникальных заголовков, cron-сессии помечаются `(cron)`.
3. Если файл есть — строки вставляются сразу под `## ✅ Выполнено` (повторный прогон идемпотентен: уже встретившиеся строки не дублируются); пустые секции не трогаются; «📊 Метрики» остаётся под пользователь.
4. Бекфилл пропущенных дней: `python3 daily-note.py 2026-09-27` (аргумент — дата).
5. При пустом дне пишется ровно «Активности не было».

Ранее (до 30.09.26) скрипт был сломан тремя багами и 5 дней подряд не создавал заметки: `subprocess.check_output(['TZ=UTC+4','+%Y-%m-%d'], shell=True)` на POSIX отдаёт sh только первый элемент списка → пустая дата → файл `().md`; `f.write(x, encoding='utf-8')` (TypeError — у TextIOWrapper нет kwargs); запрос `WHERE s.status = 0` — колонки `status` в таблице `sessions` нет (schema drift) → всегда «Активности не было». Урок: дату/таймзону считать в Python, а не через shell; после правок гонять скрипт руками на одной дате и читать файл, а не только exit-код (крон помечал прогон `ok`).

## Gotchas / Pitfalls

0. **Валидация no_agent-скрипта = запустить и ПРОЧЕСТЬ результат, а не только exit-код** — cron помечает прогон `ok`, даже если скрипт записал не то (реальный случай: daily-note 5 дней подряд «успешно» писал файл `().md` вместо заметки). После правок: прогнать руками, прочитать созданный/изменённый файл, сверить содержимое с ожидаемым (секции на месте, дата правильная, «Активности не было» только при реально пустом дне).
1. **Schema drift** — `state.db` схема меняется при обновлении Hermes; проверять колонки перед парсингом
2. **Source filtering** — захватывать только `source == 'telegram'` (пропускать cron jobs)
3. **Delivery mode** — `deliver=local` (при `no_agent=true`) означает: результат пишется локально в файл, Telegram НЕ получает ничего. LLM-агентные cron задачи (`no_agent=false`) используют `deliver=origin`, и их финальный ответ автоматически доставляется в чат. Не путать.
4. **Аргументы в `script` крона не пишутся** — no_agent крон исполняет `script` как ЧИСТЫЙ путь: `_resolve_script_path` резолвит всю строку как имя файла, «script.py --args» → «Script not found», job падает каждый тик. Параметры — только через дефолты argparse в самом скрипте или обёртку .sh. Поле `prompt` у no_agent игнорируется (но синхронизировать для читабельности).\n5. **Skill ownership** — user-created skills (created_by=None) нельзя патчить автономно; нужно `hermes curator adopt <skill>`
6. **Inbox flood** — см. `references/inbox-flood-prevention.md`: сессии должны писать в `Archives/Sessions/` (не Inbox), один файл на сессию с автообновлением по водяному знаку `captured_msg_id` (= `MAX(messages.id)`, монотонный и при resume, и при сжатии) — НЕ просто «пропустить если session_id есть» (это теряет новые сообщения возобновляемых/сжатых сессий). Выборка сессий по `MAX(messages.timestamp)` (JOIN messages), а не `started_at`. Отсев пустых/приветственных срезом префикса `[пользователь] ` и пунктуации у первого слова, проверка `all(...)` (а не `len<=1`) т.к. в `state.db` бывают дубли одного user-сообщения.\n7. **Pinned provider/model для LLM-агентных cron** — cron-задачи с `no_agent=false` наследуют провайдер и модель из сессии создания. При дрифте конфига (смена модели/провайдера в основной сессии) задача блокируется safety guard'ом «unpinned drift». Лечится явной привязкой в `jobs.json`: установить поля `model`, `provider` (идентичные `model_snapshot`, `provider_snapshot`) на уровне job-объекта. Выполнить `cronjob action=update job_id=xxx provider=openrouter model=nvidia/nemotron-3-ultra-550b-a55b:free` (или руками поправить jobs.json).\n8. **Валидация после правок** — прогнать `auto-capture-obsidian.py --days 3` дважды: первый раз может обновить существующие заметки (backfill `captured_msg_id`), второй раз ожидать для законченных сессий `⏭ No new messages since last capture`, для приветствий `⏭ Trivial/empty session skipped`, новых файлов в `Inbox/` быть не должно. Активная (текущая) сессия честно `🔄 Updated session note (resumed)` — это норм, не баг.
9. **OmniRoute/SSE и ClinePass data-wrap при прямых curl-вызовах** — дистиллятор шлёт `stream: false`, но OmniRoute может вернуть SSE-строку, а ClinePass заворачивает ответ в `{"data": {...}}`. Разбор в `distill_session()`: unwrap `data{}`, иначе `json.loads` падает («Expecting value») и дистилляция молча деградирует. Диагностика: `curl -m 60 ... -d '{"stream":false}'`, смотреть сырой ответ.
10. **Bearer-ключ в скриптах не должен быть звёздочками** — был баг `Authorization: Bearer ***` (ключ подменён при защитном редактировании): у всех провайдеров кроме ClinePass авторизация молча не работала. После правок проверять, что подставляется реальный ключ из config.
11. **Ошибки API ≠ «нет знаний»** — при ошибке API сессия НЕ помечается в `processed_sessions` (ретрай в следующий раз); помечаются только 'ok' и 'empty'. Если сбойный прогон успел пометить — вычистить sids из `.obsidian-weekly-state.json` и откатить `last_run`.
12. **Vault структура (после чистки 20.09.26)** — корень vault содержит только `🏠 Start Here.md`; заметки по сервисам и export_*.json/csv — в `Resources/`;Weekly Review архивы — в `Archives/Reviews/`; session-captures случайно попавшие в Resources как "Knowledge - ..." перенесены в `Archives/Sessions/` (файлы Knowledge в Resources — только настоящие дистилляты с `tags: [knowledge, entry, distilled]`).
13. **find_session_note ищет ТОЛЬКО в Archives/Sessions** — Knowledge-дистилляты в Resources тоже содержат session_id в frontmatter; если дать авто-захвату rglob по всему vault, он найдёт Knowledge по session_id и ЗАТРЁТ его шаблоном сессии (реальный инцидент 20.09.26: 5 дистиллятов уничтожено, восстановлены передистилляцией). Сессии в state.db не удаляются — восстановление = удалить испорченный файл, вычистить sid из processed_sessions, откатить last_run, перегнать weekly.
14. **Тегирование Knowledge и связи** — LLM при дистилляции выдаёт строку `TAGS: ...` (2-4 тематических тега), скрипт механически вшивает секцию «🔗 Связанные знания» и обратные ссылки по пересечению тегов (parse_tags/find_related_by_tags/create_knowledge_note). Бекфилл старых заметок: `backfill-knowledge-tags.py` (идемпотентен: пропускает уже тегированные). Служебные теги, НЕ считающиеся тематическими: knowledge, entry, distilled, project, reference, session, capture, hermes (иначе мёртвые теги связывают несвязное). Связи — подсказки агенту при vault-first lookup, НЕ обход графа.
15. **Прогон weekly-review руками = прогон cron'а** — скрипт кладёт `last_run` в state.json и помечает сессии обработанными; после ручного теста свежие сессии крон уже не дистиллирует. Тестировать правки на старых сессиях (--days 3+) или после сбойного теста откатить `last_run`/вычистить sids.
16. **Старые Knowledge без тегов — бекфилл** — заметки, созданные до введения тегов, связей не имеют. Разовая/повторная догенерация: `python3 ~/.hermes/scripts/backfill-knowledge-tags.py` — тегирует LLM-вызовом только заметки без тематических тегов, связи расставляет механически. Первый прогон сделан 20.09.26 (15/15).
17. **Принцип отбора для тегирования/связей** — тегируем ТОЛЬКО Knowledge-дистилляты (машина-для-машины, заголовок не самоописателен). Sessions — сырой архив, навигация там не нужна (grep/session_id), тегировать все = сотни LLM-вызовов в никуда. Ресурсы-заметки Resources (сервисы, YouTube, API-ключи) — заголовки самоописательны + индексирует Resources Hub руками; связывать не нужно. Daily/Templates — журналы и шаблоны, вне графа. Пересматривать только если Resources разрастётся (50+) и заголовки перестанут говорить сами за себя — тогда расширить бекфилл с `Knowledge*` на весь Resources.
18. **Окно и лимит авто-захвата** — до 20.09.26 было `--days 1 --limit 10`: при 18-35 активных сессий в день содержательные сессии вылетали за окно навсегда (лимит тратился на шум/тривиальные, которые отсекаются только при записи, ПОСЛЕ выборки). Теперь ДЕФОЛТЫ argparse в `auto-capture-obsidian.py` = `--days 3 --limit 40` + разовый бекфилл `--days 180 --limit 800` (20.09.26), закрывший все 114 пропущенных. ⚠️ **Крон no_agent исполняет ТОЛЬКО чистый путь в `script`** — аргументы там писать НЕЛЬЗЯ: `_resolve_script_path` ищет файл с именем целиком («auto-capture-obsidian.py --session ...») → «Script not found», job падает каждый тик (тот же механизм, что сломал `--weekly` в gotcha 4). Аргументы = только через дефолты в argparse или обёртку .sh. Поле `prompt` у no_agent игнорируется (но лучше синхронизировать для читабельности). Если снова появится отставание — разовый прогон с большим окном/лимитом, дедуп по водяному знаку делает его безопасным.
19. **Проверка покрытия захвата** — сверка state.db ↔ frontmatter vault: содержательные (≥8 msg, не-шумовые) сессии, чей session_id отсутствует в Archives/Sessions (`session_id:` frontmatter + `` `id` `` в секциях групповых заметок), = дыра захвата. Шумовые без своего sid в групповых заметках — НОРМА (файл групповой, sid только у первого запуска); при желании писать все sid — улучшение, не баг.
20. **Заглушки в шаблонах = шум для векторного поиска** — одинаковый boilerplate («(добавить при обработке)», «Обработать при еженедельном обзоре») в сотнях файлов портит векторы/поиск. В шаблонах писать пусто («-»), существующие файлы чистить массово при появлении новых заглушек.
21. **Бекпорт инсайтов в session-заметки** (фаза 2) — при дистилляции weekly-крон может дописывать найденные инсайты в исходную session-заметку вместо заглушек: архив полнее, векторы по Sessions осмысленнее. Не блокер.
22. **Бекфилл coverage — разовый прогон с большим окном** — если аудит показал пропущенные сессии, `--session --days <глубина> --limit <много>` прогоняет всё разом; дедуп по водяному знаку делает прогон безопасным и идемпотентным. Не плодить отдельные скрипты для бекфилла.
23. **PyYAML пропадает из tools-python после обновления** — 28.09.26 викли-крон упал с `ModuleNotFoundError: No module named 'yaml'` (у `obsidian-weekly-review.py`); модуль появился обратно только 29.09. В скрипте теперь guard: `try: import yaml except ImportError:` → однократный `os.execv('/usr/bin/python3', ...)` (системный python3.12 имеет PyYAML), с защитой от зацикливания по env-флагу. Аналогично поступать с любым no_agent скриптом, зависящим от сторонних пакетов.
24. **Сбой крона может не перезапускаться: watchdog-job пропал из jobs.json** — cron-retry-watchdog (старый id `7a8a634df64f`) исчез ~17.09.26, и упавший 28.09 недельный разбор не был refire'нут ни разу (executions.db: последний запуск 17.09). Пересоздан 30.09.26 как `84550fce3c31` (`*/15 * * * *`, no_agent, deliver origin). Проверять наличие watchdog в `cronjob action=list`, а не только وجود скрипта на диске.

## Расширение для других агентов

Для добавления нового источника:
1. Создать парсер в `scripts/capture-<source>.py`
2. Добавить template mapping в `templates/` 
3. Настроить cron job: **no_agent=true** для механической вставки (сырые дампы/логи) или **no_agent=false** с LLM-агентной обработкой (умный разбор, дистилляция). Для LLM-агента привязать модель/провайдер явно (см. Gotcha #7).
4. Документировать в `references/<source>.md`

## Векторный индекс: бюджет прогона вместо убийства таймаутом

Ночной `vault_vector_index.py` не должен упираться в жёсткий `script_timeout_seconds` крона: прогон, убитый на 4-м часу, пишет `script failed` и теряет ETA/итог, хотя работа шла и БД писалась (проверяется по `files.indexed_at` в `vault_vectors.db`, не по логу).

Правило: скрипт сам останавливается за ~30 мин до лимита (`--max-hours`, дефолт 3.5 при таймауте 4 ч), проверяя бюджет **перед каждым файлом** (не внутри `embed_batch` — иначе рвётся транзакция). Всё уже закоммичено пофайлово; недоделанное остаётся в `todo` по SHA-256 и подхватывается следующей ночью — resume бесплатный.

Диагностика «индекс не работает N ночей» — считать не статус крона, а `files.indexed_at`:

```sql
SELECT strftime('%Y-%m-%d',indexed_at,'unixepoch','localtime') d, count(*)
FROM files WHERE strftime('%H',indexed_at,'unixepoch','localtime') BETWEEN '03' AND '09'
GROUP BY d ORDER BY d;
```

`failed`-статус при растущем `count(*)` = «не успевает», а не «сломался». Сравнивать приток (capture ~40 файлов/ночь) с темпом индекса: пока темп выше, долг рассасывается сам.

**Медленные ночи (60→165с на чанк) — это обычно не Ollama, а десктоп.** На этой VM (QXL paravirtual, софтверный рендер) `gnome-shell` уходит в 300–400% CPU + Xorg 30–46% + `sys` до 99%; в ядре при этом `workqueue: psi_avgs_work hogged CPU`. Ловится по `~/.hermes/logs/desktop_cpu.log` (колонки ts/load1/xorg%/gshell%/sys%). Эпизод 03:12–07:42 25.10 дал медиану 142с/чанк и 95 из 125 запросов >120с; в ночи с gshell ~0.1% та же модель даёт 51–82с.

## Связанные навыки

- `obsidian-vault` — управление vault, CLI, шаблоны, привычка vault-first lookup
- `hermes-agent` — настройка Hermes, конфигурация cron/skills
- Планируемая векторная память (bge-m3 через OmniRoute + sqlite-vec + плагин prefetch) — требования к индексации в разделе «Связи и поиск знаний» и gotcha 19-20

## Референсы

- `references/auto-capture-hermes.md` — детальная реализация для Hermes
- `references/network-access.md` — настройка Samba/Syncthing для сетевого доступа к vault
- `references/inbox-flood-prevention.md` — фикс копления Inbox от автозахвата (дедуп, отсев шума, вывод в Archives/Sessions)
- `references/PARA.md` — методология организации
- `references/no-agent-dynamic-provider.md` — паттерн: no_agent скрипт сам читает model.default из config.yaml, определяет endpoint/auth из custom_providers
- `references/templates.md` — каталог шаблонов

## Шаблоны конфигурации

- `templates/smb.conf.obsidian` — готовый Samba конфиг для шаринга vault