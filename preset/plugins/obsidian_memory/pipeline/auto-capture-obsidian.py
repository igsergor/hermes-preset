#!/usr/bin/env python3
"""
Auto-capture Hermes sessions to Obsidian vault.
Extracts session data from Hermes state.db and creates structured notes.
"""

import os
import sys
import json
import re
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault")).expanduser()
INBOX_DIR = VAULT_PATH / "Inbox"
RESOURCES_DIR = VAULT_PATH / "Resources"
KNOWLEDGE_DIR = VAULT_PATH / "Resources" / "Knowledge"
SESSIONS_DIR = VAULT_PATH / "Archives" / "Sessions"
DAILY_DIR = VAULT_PATH / "Daily"
STATE_DB = Path(os.environ.get("HERMES_STATE_DB", str(Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser() / "state.db"))).expanduser()

# Android/WebDAV и Linux не любят в именах: / \ : * ? " < > |
# (прошлый инцидент: слэш в заголовке сессии ронял весь ночной capture).
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(name, max_len=120):
    """Безопасное имя файла: режет запрещённые символы, схлопывает пробелы."""
    name = _UNSAFE_CHARS.sub(' - ', name or '')
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name[:max_len].rstrip() or 'untitled'

TEMPLATE_SESSION = """---
tags: [session, capture, knowledge, hermes]
created: {{date}}
source: "hermes"
session_id: "{{session_id}}"
platform: "{{platform}}"
thread: "{{thread}}"
chat_id: "{{chat_id}}"
model: "{{model}}"
duration_minutes: {{duration}}
message_count: {{message_count}}
captured_msg_id: {{captured_msg_id}}
captured_at: "{{captured_at}}"
---

# 📝 Session Capture: {{title}}

**Session**: `{{session_id}}` | **Date**: {{date}} | **Platform**: {{platform}} | **Thread**: {{thread}} | **Duration**: {{duration}} min | **Messages**: {{message_count}}

## 🎯 Цель сессии
{{goal}}

## 📋 Ход работы
{{work_log}}

## 🛠 Использованные навыки (skills)
{{skills_used}}

## 💡 Ключевые инсайты / Решения
{{insights}}

## ⚠️ Проблемы и как решены
{{problems}}

## 🔗 Связанные заметки
{{links}}

## 📎 Артефакты
{{artifacts}}

## 🔄 Следующие шаги
{{next_steps}}

---

*Автоматически захвачено из Hermes Agent (state.db). Обработать при еженедельном обзоре.*
"""

TEMPLATE_KNOWLEDGE = """---
tags: [knowledge, entry, project, reference]
created: {{date}}
project: "{{project}}"
category: "{{category}}"
source: "{{source}}"
status: "active"
---

# 📚 Knowledge: {{title}}

**Project**: `{{project}}` | **Category**: {{category}} | **Date**: {{date}}

## 📌 Суть
{{essence}}

## 📝 Детали
{{details}}

## 🔧 Технические детали
```bash
{{tech_details}}
```

## 💡 Применение
{{application}}

## ⚠️ Подводные камни / Gotchas
{{gotchas}}

## 🔗 Связи
- [[Projects/{{project}}]]
- [[Resources/]]
- #knowledge/{{category}}

## 📚 Источники
{{sources}}

---

*Добавлено в базу знаний. Актуальность проверять при использовании.*
"""

# Weekly review template (embedded for CLI use)
TEMPLATE_WEEKLY = """---
tags: [weekly, review, process, hermes]
created: {{date}}
week: "{{week}}"
---

# 🔄 Weekly Review: Week {{week}} ({{date}})

## 📊 Статистика за неделю
- Сессий Hermes: 
- Заметок создано в vault: 
- Проектов обновлено: 
- Задач закрыто: 

---

## 1. 📥 Inbox → PARA Processing
*Разобрать всё из Inbox (5-10 мин)*

### Session Captures (автозахваченные)
- [ ] 
- [ ] 

### Knowledge Entries (ручные)
- [ ] 

### Быстрые захваты (Inbox Capture)
- [ ] 

**Действие для каждого**: Project / Area / Resource / Archive / Delete

---

## 2. 🎯 Projects Review
*Обновить статус, перенести завершенные в Archives*

| Проект | Статус | Прогресс | Следующий шаг |
|--------|--------|----------|---------------|
|  |  |  |  |

---

## 3. 🏢 Areas Check
*Проверить регулярные действия по областям*

| Область | Регулярное действие | Сделано? | Примечание |
|---------|---------------------|----------|------------|
| Home & Family |  | [ ] |  |
| Development & Tech |  | [ ] |  |
| Health & Fitness |  | [ ] |  |
| Finances |  | [ ] |  |

---

## 4. 📅 Calendar & Planning
*Планировать следующую неделю*

### Приоритеты на следующую неделю:
1. 
2. 
3. 

### Блокеры / Зависимости:
- 

---

## 5. 📝 Daily Notes Review
*Просмотреть daily notes за неделю, вынести важное*

### Ключевые инсайты недели:
- 

### Паттерны / Тренды:
- 

---

## 6. 🧠 Knowledge Base Health
*Состояние базы знаний*

- [ ] Теги актуальны
- [ ] Ссылки между проектами/ресурсами работают
- [ ] Дубликаты объединены
- [ ] Старые заметки в Archives актуальны

---

## 7. 🤖 Hermes & Automation
*Проверка автоматизаций*

- [ ] Auto-capture cron job работает (проверить Inbox)
- [ ] Dashboard доступен
- [ ] VPN/доступ с телефона работает
- [ ] Backups vault в порядке

---

## 📋 Action Items на неделю
- [ ] 
- [ ] 
- [ ] 

---

*Шаблон: Weekly Review.md | Обрабатывать еженедельно (понедельник/воскресенье)*
"""

def get_sessions(days=1, limit=10):
    """Get sessions with ANY recent activity (message updated in last N days).
    Uses max message timestamp, so resumed/continued sessions (whose started_at
    may be old) are still picked up."""
    if not STATE_DB.exists():
        print(f"State DB not found: {STATE_DB}")
        return []
    
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    since = datetime.now() - timedelta(days=days)
    since_ts = since.timestamp()
    
    # A session is 'recent' if its last message is within the window — this
    # catches resumed sessions regardless of started_at.
    cursor.execute('''
        SELECT s.id, s.started_at, s.ended_at, s.title, s.source, s.chat_id,
               s.thread_id, s.message_count, s.model, s.model_config
        FROM sessions s
        JOIN messages m ON m.session_id = s.id
        WHERE m.timestamp > ?
        GROUP BY s.id
        ORDER BY MAX(m.timestamp) DESC
        LIMIT ?
    ''', (since_ts, limit))

    sessions = []
    for row in cursor.fetchall():
        sessions.append(dict(row))
    
    conn.close()
    return sessions

def get_session_messages(session_id):
    """Get all messages for a session."""
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT role, content, tool_name, tool_calls, timestamp
        FROM messages 
        WHERE session_id = ? 
        ORDER BY id
    ''', (session_id,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append(dict(row))
    
    conn.close()
    return messages

def extract_skills_used(messages):
    """Extract which skills were loaded during the session."""
    skills = set()
    for msg in messages:
        if msg['tool_calls']:
            try:
                calls = json.loads(msg['tool_calls']) if isinstance(msg['tool_calls'], str) else msg['tool_calls']
                for call in calls:
                    if call.get('function', {}).get('name') == 'skill_view':
                        args = json.loads(call['function']['arguments']) if isinstance(call['function']['arguments'], str) else call['function']['arguments']
                        skill_name = args.get('name', '')
                        if skill_name:
                            skills.add(skill_name)
            except:
                pass
    return sorted(list(skills))

def extract_key_content(messages):
    """Extract key content from session messages for the note."""
    user_messages = [m for m in messages if m['role'] == 'user']
    assistant_messages = [m for m in messages if m['role'] == 'assistant' and m['content']]
    tool_results = [m for m in messages if m['role'] == 'tool']
    
    # First user message often contains the goal
    goal = user_messages[0]['content'][:500] if user_messages else "Не указано"
    
    # Build work log from tool usage and assistant responses
    work_log_parts = []
    skills_loaded = []
    
    for msg in messages:
        if msg['tool_name']:
            work_log_parts.append(f"**{msg['tool_name']}** — выполнен")
        elif msg['role'] == 'assistant' and msg['content'] and len(msg['content']) > 50:
            # Significant assistant response
            snippet = msg['content'][:300]
            if not any(skip in snippet.lower() for skip in ['loading', 'skill_view', 'skill_manage', '{"success"']):
                work_log_parts.append(f"💬 {snippet}...")
    
    work_log = "\n".join(work_log_parts[:20]) if work_log_parts else "См. исходный диалог в Hermes"
    
    # Skills
    skills = extract_skills_used(messages)
    skills_text = "\n".join([f"- `{s}`" for s in skills]) if skills else "- (не загружались явно)"
    
    return {
        'goal': goal,
        'work_log': work_log,
        'skills_used': skills_text,
    }

def get_max_msg_id(session_id):
    """Highest message id in this session (monotonic; grows on resume & compression)."""
    if not session_id:
        return 0
    try:
        conn = sqlite3.connect(STATE_DB)
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM messages WHERE session_id=?", (session_id,))
        val = cur.fetchone()[0]
        conn.close()
        return val or 0
    except Exception:
        return 0

def find_session_note(session_id):
    """Return (path, captured_msg_id) for existing note of this session, or (None, 0).
    ВАЖНО: искать только в Archives/Sessions. Knowledge-дистилляты в Resources
    тоже содержат session_id в frontmatter — если их сюда впустить, авто-захват
    затрёт Knowledge-заметку шаблоном сессии (реальный инцидент 20.09.26)."""
    if not session_id:
        return None, 0
    token = f'session_id: "{session_id}"'
    if not SESSIONS_DIR.exists():
        return None, 0
    for p in SESSIONS_DIR.glob("*.md"):
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            if token in content:
                captured = 0
                for line in content.splitlines():
                    if line.startswith('captured_msg_id:'):
                        try:
                            captured = int(line.split(':', 1)[1].strip())
                        except Exception:
                            captured = 0
                return str(p), captured
        except Exception:
            pass
    return None, 0

# Recurring/noise session titles that add no knowledge value. Sessions with
# such titles are still CAPTURED (audit trail), but they don't go through LLM
# distillation (prefilter in obsidian-weekly-review.py) and repeating ones
# (same base title within the same day, e.g. periodic mailbox checks) are
# grouped into one note with per-run sections instead of one file per run.
NOISE_TITLE_PATTERNS = [
    r'Проверка корпоративной почты',
    r'diadoc-watchdog',
    r'TokenHarbor',
    r'Daily Note в Obsidian',
    r'Еженедельн\w+ (разбор|отчёт|проверка)',
    r'Ответь одним словом',
    r'^ок$',
]

def is_noise_title(title):
    t = (title or '').strip().lower()
    return any(re.search(p, t, re.IGNORECASE) for p in NOISE_TITLE_PATTERNS)

def noise_base_title(title):
    """Normalize a noise title for grouping: strip trailing time markers like
    '· Sep 18 15:22', '· 15:22', '(Sep 18)', timestamps, so that repeated runs
    of the same job share one note."""
    t = title or ''
    t = re.sub(r'\s*[·—-]\s*(Sep|Aug|Oct|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul)\w*\s+\d{1,2}\s+\d{1,2}:\d{2}\s*$', '', t)
    t = re.sub(r'\s*[·—-]\s*\d{1,2}:\d{2}\s*$', '', t)
    t = re.sub(r'\s*\(.*?\)\s*$', '', t)
    return t.strip()

def is_trivial_session(messages, session_data):
    """True if session should be skipped: empty, or a short greeting-only exchange."""
    if (session_data.get('message_count') or 0) == 0:
        return True
    # Short greeting-only sessions (e.g. "привет", "как дела") are noise — skip.
    user_msgs = [m for m in messages if m['role'] == 'user' and m.get('content')]
    if not user_msgs:
        return True
    # If total session is tiny AND every user msg is a short greeting → skip
    if (session_data.get('message_count') or 0) < 8:
        greetings = ('привет', 'здравствуй', 'hello', 'hi', 'hey', 'добрый',
                     'как дела', 'привет, как дела', 'вечер добрый', 'доброе утро',
                     'добрый день', 'добрый вечер', 'test', 'тест', 'привет как дела', 'да')
        def _is_greeting(raw):
            import re as _re
            t = (raw or '').strip().lower()
            if t.startswith('[') and ']' in t[:30]:
                t = t.split(']', 1)[1].strip()
            if not t:
                return True
            first_word = _re.sub(r'[\W_]+$', '', t.split()[0])
            return len(t) < 40 and (first_word in greetings or t in greetings)
        if user_msgs and all(_is_greeting(m['content']) for m in user_msgs):
            return True
    return False

def create_session_note(session_data):
    """Capture a session note: create, or update-in-place if the session gained
    new messages (resume / context-compression rewrite). One file per session."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    session_id = session_data['id']
    started = datetime.fromtimestamp(session_data['started_at'])
    date_str = started.strftime("%Y-%m-%d")
    platform = session_data['source'] or 'telegram'
    thread = str(session_data['thread_id']) if session_data['thread_id'] else 'unknown'
    chat_id = str(session_data['chat_id']) if session_data['chat_id'] else 'unknown'
    model = session_data['model'] or 'unknown'
    message_count = session_data['message_count'] or 0
    
    # Calculate duration
    if session_data['ended_at']:
        duration = int((session_data['ended_at'] - session_data['started_at']) / 60)
    else:
        duration = int((datetime.now().timestamp() - session_data['started_at']) / 60)
    
    title = session_data['title'] or f"Hermes Session {started.strftime('%H:%M')}"
    title = sanitize_filename(title)
    
    # Get messages and extract content
    messages = get_session_messages(session_id)
    
    current_max = get_max_msg_id(session_id)
    
    # Find existing note for this session (dedup + resume-aware)
    existing_path, captured_max = find_session_note(session_id)
    
    if is_trivial_session(messages, session_data):
        print(f"⏭ Trivial/empty session skipped: {session_id} ({title})")
        return None
    
    # Recurring service jobs (mailbox checks, watchdogs, daily notes) go into
    # one grouped note per day instead of one file per run.
    if is_noise_title(title):
        return create_or_append_grouped_noise_note(session_data)
    
    # If a note exists and no new messages since last capture → skip (no data loss)
    if existing_path and current_max <= captured_max:
        print(f"⏭ No new messages since last capture: {session_id} — skip")
        return None
    
    extracted = extract_key_content(messages)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = TEMPLATE_SESSION.replace("{{date}}", date_str)
    content = content.replace("{{session_id}}", session_id)
    content = content.replace("{{title}}", title)
    content = content.replace("{{platform}}", platform)
    content = content.replace("{{thread}}", thread)
    content = content.replace("{{chat_id}}", chat_id)
    content = content.replace("{{model}}", model)
    content = content.replace("{{duration}}", str(duration))
    content = content.replace("{{message_count}}", str(message_count))
    content = content.replace("{{captured_msg_id}}", str(current_max))
    content = content.replace("{{captured_at}}", now_str)
    content = content.replace("{{goal}}", extracted['goal'])
    content = content.replace("{{work_log}}", extracted['work_log'])
    content = content.replace("{{skills_used}}", extracted['skills_used'])
    content = content.replace("{{insights}}", "-")
    content = content.replace("{{problems}}", "-")
    content = content.replace("{{links}}", "- [[Projects/Hermes Agent — Настройка и расширение]]\n- [[Resources/Resources Hub]]\n- [[Areas/Development & Tech]]")
    content = content.replace("{{artifacts}}", "- Файлы: \n- Скрипты: \n- Конфиги: ")
    content = content.replace("{{next_steps}}", "- [ ] ")
    
    if existing_path:
        # Resume/update: overwrite the same file (fresh snapshot), keep single note
        try:
            Path(existing_path).write_text(content, encoding="utf-8")
            print(f"🔄 Updated session note (resumed): {existing_path}")
            return existing_path
        except Exception as e:
            print(f"⚠️ Could not update {existing_path}: {e}")
    
    filename = f"Session - {date_str} - {title}.md"
    filepath = SESSIONS_DIR / filename
    
    if filepath.exists():
        base = filepath.stem
        counter = 1
        while filepath.exists():
            filepath = SESSIONS_DIR / f"{base} ({counter}).md"
            counter += 1
    
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ Created session note: {filepath}")
    return filepath

def create_or_append_grouped_noise_note(session_data):
    """Grouped note for recurring noise sessions: one file per (day, base title),
    appended with a per-run section. Uses its own watermark captured_msg_id
    stored in the file, same dedup semantics as regular session notes."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    session_id = session_data['id']
    started = datetime.fromtimestamp(session_data['started_at'])
    date_str = started.strftime("%Y-%m-%d")
    time_str = started.strftime("%H:%M")
    base = sanitize_filename(noise_base_title(session_data['title'] or 'Hermes Session'))
    filename = f"Session - {date_str} - {base}.md"
    filepath = SESSIONS_DIR / filename
    
    current_max = get_max_msg_id(session_id)
    messages = get_session_messages(session_id)
    extracted = extract_key_content(messages)
    model = session_data['model'] or 'unknown'
    message_count = session_data['message_count'] or 0
    
    run_section = (
        f"\n### 🕒 {time_str} — `{session_id}`\n"
        f"- Модель: {model} | Сообщений: {message_count}\n"
        f"- Цель: {extracted['goal'][:300]}\n"
    )
    
    if filepath.exists():
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'captured_msg_id:\s*(\d+)', content)
        captured_max = int(m.group(1)) if m else 0
        if current_max <= captured_max:
            print(f"⏭ No new messages since last capture: {session_id} — skip (grouped)")
            return None
        content = content.replace('captured_msg_id: ', f'captured_msg_id: ', 1)
        content = re.sub(r'captured_msg_id:\s*\d+', f'captured_msg_id: {current_max}', content, count=1)
        m2 = re.search(r'captured_at:\s*"([^"]+)"', content)
        content = re.sub(r'captured_at:\s*"[^"]+"', f'captured_at: "{datetime.now().strftime("%Y-%m-%d %H:%M")}"', content, count=1)
        mc = re.search(r'message_count:\s*(\d+)', content)
        if mc:
            content = content.replace(f'message_count: {mc.group(1)}', f"message_count: {int(mc.group(1)) + message_count}", 1)
        content = content.rstrip() + "\n" + run_section
        filepath.write_text(content, encoding="utf-8")
        print(f"🔄 Appended to grouped noise note: {filepath}")
        return filepath
    
    content = TEMPLATE_SESSION
    content = content.replace("{{date}}", date_str)
    content = content.replace("{{session_id}}", session_id)
    content = content.replace("{{title}}", f"{base} (серия запусков)")
    content = content.replace("{{platform}}", session_data['source'] or 'telegram')
    content = content.replace("{{thread}}", str(session_data['thread_id']) if session_data['thread_id'] else 'unknown')
    content = content.replace("{{chat_id}}", str(session_data['chat_id']) if session_data['chat_id'] else 'unknown')
    content = content.replace("{{model}}", model)
    content = content.replace("{{duration}}", "0")
    content = content.replace("{{message_count}}", str(message_count))
    content = content.replace("{{captured_msg_id}}", str(current_max))
    content = content.replace("{{captured_at}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    content = content.replace("{{goal}}", f"Повторяющийся сервисный запуск ({base}) — см. секции по времени")
    content = content.replace("{{work_log}}", run_section.lstrip())
    content = content.replace("{{skills_used}}", "- (не загружались явно)")
    content = content.replace("{{insights}}", "- (сервисная серия — без инсайтов)")
    content = content.replace("{{problems}}", "- (—)")
    content = content.replace("{{links}}", "- [[Projects/Hermes Agent — Настройка и расширение]]\n- [[Resources/Resources Hub]]")
    content = content.replace("{{artifacts}}", "- Файлы: \n- Скрипты: \n- Конфиги: ")
    content = content.replace("{{next_steps}}", "- [ ] ")
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ Created grouped noise note: {filepath}")
    return filepath

def create_knowledge_entry(data):
    """Create a knowledge entry note (в Resources/Knowledge/Misc — ручные записи без тегов)."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    target = KNOWLEDGE_DIR / "Misc"
    target.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = sanitize_filename(data.get('title', 'Knowledge Entry'))
    project = data.get('project', 'General')
    category = data.get('category', 'general')
    source = data.get('source', 'hermes-auto')
    
    essence = data.get('essence', '(добавить суть)')
    details = data.get('details', '(добавить детали)')
    tech_details = data.get('tech_details', '# Команды, конфиги, код')
    application = data.get('application', '(как применять)')
    gotchas = data.get('gotchas', '- (подводные камни)')
    sources = data.get('sources', '- ')
    
    content = TEMPLATE_KNOWLEDGE.replace("{{date}}", date_str)
    content = content.replace("{{title}}", title)
    content = content.replace("{{project}}", project)
    content = content.replace("{{category}}", category)
    content = content.replace("{{source}}", source)
    content = content.replace("{{essence}}", essence)
    content = content.replace("{{details}}", details)
    content = content.replace("{{tech_details}}", tech_details)
    content = content.replace("{{application}}", application)
    content = content.replace("{{gotchas}}", gotchas)
    content = content.replace("{{sources}}", sources)
    
    filename = f"Knowledge - {title}.md"
    filepath = target / filename

    if filepath.exists():
        base = filepath.stem
        counter = 1
        while filepath.exists():
            filepath = target / f"{base} ({counter}).md"
            counter += 1
    
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ Created knowledge entry: {filepath}")
    return filepath

def create_weekly_review(data):
    """Create a weekly review note."""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    year, week, _ = now.isocalendar()
    week_str = f"{year}-W{week:02d}"
    
    title = data.get('title', f'Weekly Review {week_str}')
    
    content = TEMPLATE_WEEKLY.replace("{{date}}", date_str)
    content = content.replace("{{week}}", week_str)
    content = content.replace("{{title}}", title)
    
    filename = f"Weekly Review - {week_str}.md"
    filepath = DAILY_DIR / filename
    
    if filepath.exists():
        base = filepath.stem
        counter = 1
        while filepath.exists():
            filepath = DAILY_DIR / f"{base} ({counter}).md"
            counter += 1
    
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ Created weekly review: {filepath}")
    return filepath

def main():
    parser = argparse.ArgumentParser(description="Auto-capture Hermes sessions to Obsidian")
    parser.add_argument("--days", type=int, default=3, help="Days back to capture")
    parser.add_argument("--limit", type=int, default=40, help="Max sessions to process")
    parser.add_argument("--session", action="store_true", help="Create session captures")
    parser.add_argument("--knowledge", action="store_true", help="Create knowledge entry")
    parser.add_argument("--weekly", action="store_true", help="Create weekly review")
    parser.add_argument("--title", help="Title for the note")
    parser.add_argument("--project", default="General", help="Project name")
    parser.add_argument("--category", default="general", help="Category")
    parser.add_argument("--essence", help="Essence/summary")
    parser.add_argument("--details", help="Details")
    parser.add_argument("--tech", help="Technical details")
    parser.add_argument("--application", help="How to apply")
    parser.add_argument("--gotchas", help="Gotchas")
    
    args = parser.parse_args()
    
    if args.knowledge:
        create_knowledge_entry({
            'title': args.title or 'Knowledge Entry',
            'project': args.project,
            'category': args.category,
            'source': 'hermes-auto',
            'essence': args.essence or '(добавить суть)',
            'details': args.details or '(добавить детали)',
            'tech_details': args.tech or '# Команды, конфиги, код',
            'application': args.application or '(как применять)',
            'gotchas': args.gotchas or '- (подводные камни)',
        })
    elif args.weekly:
        create_weekly_review({
            'title': args.title or f'Weekly Review {datetime.now().strftime("%Y-W%W")}',
        })
    elif args.session or (not args.knowledge and not args.session and not args.weekly):
        # Default to session capture
        sessions = get_sessions(args.days, args.limit)
        if sessions:
            print(f"Found {len(sessions)} sessions in last {args.days} day(s)")
            for s in sessions:
                create_session_note(s)
        else:
            print("No recent sessions found")
    else:
        print("Use --session, --knowledge, or --weekly")

if __name__ == "__main__":
    main()