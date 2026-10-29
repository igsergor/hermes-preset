#!/usr/bin/env python3
"""
Obsidian Vault CLI - простая утилита для работы с vault из терминала.
Использование:
  obsidian daily                    # открыть/создать дневник сегодня
  obsidian new -t Project "Title"   # создать заметку из шаблона
  obsidian search "query"           # поиск по vault
  obsidian random                   # случайная заметка
  obsidian stats                    # статистика vault
"""

import os
import sys
import argparse
import subprocess
import re
from datetime import datetime
from pathlib import Path

VAULT_PATH = Path("~/obsidian-vault")
TEMPLATES_DIR = VAULT_PATH / "Templates"
DAILY_DIR = VAULT_PATH / "Daily"
INBOX_DIR = VAULT_PATH / "Inbox"
PROJECTS_DIR = VAULT_PATH / "Projects"
AREAS_DIR = VAULT_PATH / "Areas"
RESOURCES_DIR = VAULT_PATH / "Resources"
ARCHIVES_DIR = VAULT_PATH / "Archives"

TEMPLATES = {
    "daily": "Daily Note.md",
    "project": "Project.md",
    "meeting": "Meeting.md",
    "note": "Note.md",
    "inbox": "Inbox Capture.md",
    "session": "Session Capture.md",
    "knowledge": "Knowledge Entry.md",
    "weekly": "Weekly Review.md",
}

def get_today_daily():
    """Получить путь к ежедневной заметке на сегодня."""
    today = datetime.now().strftime("%Y-%m-%d")
    return DAILY_DIR / f"{today}.md"

def create_from_template(template_name: str, title: str, **kwargs) -> Path:
    """Создать заметку из шаблона."""
    template_file = TEMPLATES.get(template_name.lower())
    if not template_file:
        print(f"Неизвестный шаблон: {template_name}")
        print(f"Доступные: {list(TEMPLATES.keys())}")
        sys.exit(1)
    
    template_path = TEMPLATES_DIR / template_file
    if not template_path.exists():
        print(f"Шаблон не найден: {template_path}")
        sys.exit(1)
    
    content = template_path.read_text(encoding="utf-8")
    
    # Замены
    now = datetime.now()
    content = content.replace("{{date:YYYY-MM-DD}}", now.strftime("%Y-%m-%d"))
    content = content.replace("{{date:dddd}}", now.strftime("%A"))
    content = content.replace("{{time:HH:mm}}", now.strftime("%H:%M"))
    content = content.replace("{{title}}", title)
    
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    
    # Определить папку назначения
    if template_name.lower() == "daily":
        target_dir = DAILY_DIR
        filename = f"{now.strftime('%Y-%m-%d')}.md"
    elif template_name.lower() == "inbox":
        target_dir = INBOX_DIR
        filename = f"Inbox - {title}.md"
    elif template_name.lower() == "project":
        target_dir = PROJECTS_DIR
        filename = f"{title}.md"
    elif template_name.lower() == "session":
        target_dir = INBOX_DIR
        filename = f"Session - {now.strftime('%Y-%m-%d')} - {title}.md"
    elif template_name.lower() == "knowledge":
        target_dir = RESOURCES_DIR / "Knowledge" / "Misc"
        filename = f"Knowledge - {title}.md"
    elif template_name.lower() == "weekly":
        target_dir = VAULT_PATH / "Daily"
        # Weekly review filename with week number
        year, week, _ = now.isocalendar()
        filename = f"Weekly Review - {year}-W{week:02d}.md"
    else:
        target_dir = VAULT_PATH
        filename = f"{title}.md"
    
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    
    if target_path.exists():
        print(f"Файл уже существует: {target_path}")
        return target_path
    
    target_path.write_text(content, encoding="utf-8")
    print(f"Создано: {target_path}")
    return target_path

def daily_command(args):
    """Открыть/создать дневник на сегодня."""
    daily_path = get_today_daily()
    if not daily_path.exists():
        create_from_template("daily", datetime.now().strftime("%Y-%m-%d"))
    
    # Открыть в редакторе (или просто показать путь)
    if args.edit:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(daily_path)])
    else:
        print(daily_path)
        # Показать содержимое
        content = daily_path.read_text(encoding="utf-8")
        print(content)

def new_command(args):
    """Создать новую заметку из шаблона."""
    # Парсим дополнительные переменные
    kwargs = {}
    for var in args.variables:
        if '=' in var:
            key, value = var.split('=', 1)
            kwargs[key] = value
    create_from_template(args.template, args.title, **kwargs)

def search_command(args):
    """Поиск по vault."""
    query = args.query
    # Использовать ripgrep если доступен
    try:
        result = subprocess.run(
            ["rg", query, str(VAULT_PATH), "--type", "md", "-i"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout:
            print(result.stdout)
        else:
            print("Ничего не найдено")
    except FileNotFoundError:
        # Fallback на grep
        result = subprocess.run(
            ["grep", "-r", "-i", query, str(VAULT_PATH), "--include=*.md"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout:
            print(result.stdout)
        else:
            print("Ничего не найдено (rg не установлен, используется grep)")

def random_command(args):
    """Случайная заметка."""
    import random
    md_files = list(VAULT_PATH.rglob("*.md"))
    md_files = [f for f in md_files if ".obsidian" not in f.parts and "Templates" not in f.parts]
    if md_files:
        chosen = random.choice(md_files)
        print(chosen)
        if args.show:
            print(chosen.read_text(encoding="utf-8"))
    else:
        print("Заметок не найдено")

def stats_command(args):
    """Статистика vault."""
    md_files = list(VAULT_PATH.rglob("*.md"))
    md_files = [f for f in md_files if ".obsidian" not in f.parts]

    total = len(md_files)
    daily_count = len(list(DAILY_DIR.glob("*.md"))) if DAILY_DIR.exists() else 0
    project_count = len(list(PROJECTS_DIR.glob("*.md"))) if PROJECTS_DIR.exists() else 0
    area_count = len(list(AREAS_DIR.glob("*.md"))) if AREAS_DIR.exists() else 0
    resource_count = len(list(RESOURCES_DIR.glob("*.md"))) if RESOURCES_DIR.exists() else 0
    inbox_count = len(list(INBOX_DIR.glob("*.md"))) if INBOX_DIR.exists() else 0
    template_count = len(list(TEMPLATES_DIR.glob("*.md"))) if TEMPLATES_DIR.exists() else 0
    archives_sessions_count = len(list((ARCHIVES_DIR / "Sessions").glob("*.md"))) if (ARCHIVES_DIR / "Sessions").exists() else 0
    archives_other = len(list(ARCHIVES_DIR.glob("*.md"))) if ARCHIVES_DIR.exists() else 0

    print(f"📊 Статистика Vault: {VAULT_PATH}")
    print(f"  Всего заметок: {total}")
    print(f"  📅 Daily: {daily_count}")
    print(f"  🎯 Projects: {project_count}")
    print(f"  🏢 Areas: {area_count}")
    print(f"  📚 Resources: {resource_count}")
    print(f"  📥 Inbox: {inbox_count}")
    print(f"  📦 Archives/Sessions: {archives_sessions_count}")
    print(f"  📋 Templates: {template_count}")

    # Теги - парсим frontmatter через regex
    all_tags = set()
    frontmatter_pattern = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
    tags_pattern = re.compile(r'tags:\s*\[(.*?)\]|tags:\s*(.+)', re.MULTILINE)
    
    for f in md_files:
        try:
            content = f.read_text(encoding="utf-8")
            fm_match = frontmatter_pattern.match(content)
            if fm_match:
                fm_content = fm_match.group(1)
                tags_matches = tags_pattern.findall(fm_content)
                for match in tags_matches:
                    if match[0]:  # tags: [tag1, tag2]
                        tags_str = match[0]
                        tags = [t.strip().strip('"\'') for t in tags_str.split(',')]
                        all_tags.update(tags)
                    elif match[1]:  # tags: tag1
                        tag = match[1].strip().strip('"\'')
                        all_tags.add(tag)
        except:
            pass

    if all_tags:
        print(f"  🏷 Теги ({len(all_tags)}): {', '.join(sorted(all_tags)[:20])}{'...' if len(all_tags) > 20 else ''}")

def main():
    parser = argparse.ArgumentParser(description="Obsidian Vault CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # daily
    daily_parser = subparsers.add_parser("daily", help="Открыть/создать дневник сегодня")
    daily_parser.add_argument("-e", "--edit", action="store_true", help="Открыть в редакторе")
    
    # new
    new_parser = subparsers.add_parser("new", help="Создать заметку из шаблона")
    new_parser.add_argument("-t", "--template", required=True, choices=list(TEMPLATES.keys()), help="Шаблон")
    new_parser.add_argument("title", help="Заголовок заметки")
    new_parser.add_argument("variables", nargs="*", help="Дополнительные переменные в формате key=value")
    
    # search
    search_parser = subparsers.add_parser("search", help="Поиск по vault")
    search_parser.add_argument("query", help="Поисковый запрос")
    
    # random
    random_parser = subparsers.add_parser("random", help="Случайная заметка")
    random_parser.add_argument("-s", "--show", action="store_true", help="Показать содержимое")
    
    # stats
    subparsers.add_parser("stats", help="Статистика vault")
    
    args = parser.parse_args()
    
    commands = {
        "daily": daily_command,
        "new": new_command,
        "search": search_command,
        "random": random_command,
        "stats": stats_command,
    }
    
    commands[args.command](args)

if __name__ == "__main__":
    main()