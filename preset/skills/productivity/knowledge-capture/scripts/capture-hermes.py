#!/usr/bin/env python3
"""
Auto-capture Hermes sessions to Obsidian vault.
Extracts session data from Hermes state.db and creates structured notes.

Usage:
  python3 capture-hermes.py --session --days 1 --limit 10
  python3 capture-hermes.py --knowledge --title "Name" --project "Project" --category "cat" --essence "..." --details "..." --tech "..." --application "..." --gotchas "..."
  python3 capture-hermes.py --weekly
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Vault paths - configure as needed
VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault"))
INBOX_DIR = VAULT_PATH / "Inbox"
RESOURCES_DIR = VAULT_PATH / "Resources"
DAILY_DIR = VAULT_PATH / "Daily"
STATE_DB = Path(os.environ.get("HERMES_STATE_DB", "~/.hermes/state.db"))

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
    """Get recent sessions from the state database."""
    if not STATE_DB.exists():
        print(f"State DB not found: {STATE_DB}", file=sys.stderr)
        return []
    
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    since = datetime.now() - timedelta(days=days)
    since_ts = since.timestamp()
    
    cursor.execute('''
        SELECT id, started_at, ended_at, title, source, chat_id, thread_id, 
               message_count, model, model_config
        FROM sessions 
        WHERE started_at > ? 
        ORDER BY started_at DESC LIMIT ?
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
    
    # First user message often contains the goal
    goal = user_messages[0]['content'][:500] if user_messages else "Не указано"
    
    # Build work log from tool usage and assistant responses
    work_log_parts = []
    
    for msg in messages:
        if msg['tool_name']:
            work_log_parts.append(f"**{msg['tool_name']}** — выполнен")
        elif msg['role'] == 'assistant' and msg['content'] and len(msg['content']) > 50:
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

def create_session_note(session_data):
    """Create a session capture note from session data."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    
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
    
    # Get messages and extract content
    messages = get_session_messages(session_id)
    extracted = extract_key_content(messages)
    
    content = TEMPLATE_SESSION.replace("{{date}}", date_str)
    content = content.replace("{{session_id}}", session_id)
    content = content.replace("{{title}}", title)
    content = content.replace("{{platform}}", platform)
    content = content.replace("{{thread}}", thread)
    content = content.replace("{{chat_id}}", chat_id)
    content = content.replace("{{model}}", model)
    content = content.replace("{{duration}}", str(duration))
    content = content.replace("{{message_count}}", str(message_count))
    content = content.replace("{{goal}}", extracted['goal'])
    content = content.replace("{{work_log}}", extracted['work_log'])
    content = content.replace("{{skills_used}}", extracted['skills_used'])
    content = content.replace("{{insights}}", "- (добавить при обработке)")
    content = content.replace("{{problems}}", "- (добавить при обработке)")
    content = content.replace("{{links}}", "- [[Projects/]]\n- [[Resources/]]\n- [[Areas/]]")
    content = content.replace("{{artifacts}}", "- Файлы: \n- Скрипты: \n- Конфиги: ")
    content = content.replace("{{next_steps}}", "- [ ] ")
    
    filename = f"Session - {date_str} - {title}.md"
    filepath = INBOX_DIR / filename
    
    if filepath.exists():
        base = filepath.stem
        counter = 1
        while filepath.exists():
            filepath = INBOX_DIR / f"{base} ({counter}).md"
            counter += 1
    
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ Created session note: {filepath}")
    return filepath

def create_knowledge_entry(data):
    """Create a knowledge entry note."""
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = data.get('title', 'Knowledge Entry')
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
    filepath = RESOURCES_DIR / filename
    
    if filepath.exists():
        base = filepath.stem
        counter = 1
        while filepath.exists():
            filepath = RESOURCES_DIR / f"{base} ({counter}).md"
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
    parser.add_argument("--days", type=int, default=1, help="Days back to capture")
    parser.add_argument("--limit", type=int, default=10, help="Max sessions to process")
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