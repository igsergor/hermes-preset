#!/usr/bin/env python3
"""
Одноразовый бекфилл: проставить тематические теги старым Knowledge-заметкам
и связать их по пересечению тегов (механика, как в obsidian-weekly-review.py).

Использует те же функции, что еженедельный разбор: get_model_config,
find_related_by_tags. LLM вызывается ТОЛЬКО для тегирования (2-4 тега),
тело заметки не переписывается. Повторный запуск безопасен: заметки,
у которых уже есть тематические теги (больше базовых трёх), пропускаются.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Импорт функций из скрипта еженедельного разбора (main() под guard'ом — безопасно)
import importlib.util
spec = importlib.util.spec_from_file_location("wr", str(Path(__file__).resolve().parent / "obsidian-weekly-review.py"))
wr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wr)

VAULT_DIR = Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault")).expanduser()
RESOURCES = VAULT_DIR / "Resources"
# Служебные теги старого шаблона знаний: не считаются тематическими
BASE_TAGS = {"knowledge", "entry", "distilled", "project", "reference", "session", "capture", "hermes"}

def log(msg):
    print(msg, flush=True)

def llm_tags(content):
    """Короткий вызов LLM: только теги. Возвращает список тегов или []."""
    model_id, endpoint, api_key = wr.get_model_config()
    if not model_id:
        log("  ⚠ Нет модели в config.yaml")
        return []
    prompt = (
        "Дай 2-4 тематических тега (латиницей, слова через запятую) для этой заметки знаний. "
        "Технологии, системы, темы. Ничего кроме строки 'TAGS: тег1, тег2' не выводи.\n\n"
        f"{content[:3000]}"
    )
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 60,
        "temperature": 0.2,
        "stream": False,
    })
    cmd = ["curl", "-s", "-X", "POST", endpoint,
           "-H", "Content-Type: application/json",
           "-d", payload, "--max-time", "120"]
    if api_key:
        cmd.insert(4, "-H")
        cmd.insert(5, f"Authorization: Bearer {api_key}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=130)
        body = r.stdout.strip()
        if not body:
            return []
        resp = json.loads(body)
        if isinstance(resp.get("data"), dict) and "choices" in resp["data"]:
            resp = resp["data"]
        text = resp["choices"][0]["message"]["content"].strip()
        _, tags = wr.parse_tags("TAGS: " + text.split("TAGS:", 1)[-1])
        return tags
    except Exception as e:
        log(f"  ⚠ {str(e)[:80]}")
        return []

def add_tags_to_frontmatter(text, tags):
    m = re.search(r'tags:\s*\[([^\]]*)\]', text)
    if not m:
        return text
    existing = [t.strip() for t in m.group(1).split(',') if t.strip()]
    merged = existing + [t for t in tags if t not in existing]
    new_line = "tags: [" + ", ".join(merged) + "]"
    return text[:m.start()] + new_line + text[m.end():]

def add_links_section(text, related_names):
    """Вставить/дополнить секцию '🔗 Связанные знания' перед концом файла."""
    lines = [f"- [[{n}]]" for n in related_names]
    block = "\n## 🔗 Связанные знания\n" + "\n".join(lines) + "\n"
    if "## 🔗 Связанные знания" in text:
        # дополнить существующую секцию
        out = text.rstrip() + "\n" + "\n".join(l for l in lines if l not in text) + "\n"
        return out
    return text.rstrip() + "\n" + block

def main():
    files = sorted(RESOURCES.rglob("Knowledge*.md"))
    log(f"📚 Knowledge-заметок: {len(files)}")
    tagged = []
    for f in files:
        text = f.read_text(errors="ignore")
        m = re.search(r'tags:\s*\[([^\]]*)\]', text)
        cur = {t.strip().lower() for t in m.group(1).split(',')} if m else set()
        thematic = cur - BASE_TAGS
        if thematic:
            log(f"  ⏭ {f.stem[:60]} — теги уже есть: {', '.join(sorted(thematic))}")
            tagged.append((f, list(thematic)))
            continue
        body = re.sub(r'^---.*?---\s*', '', text, count=1, flags=re.S)
        tags = llm_tags(body)
        if not tags:
            log(f"  ⚠ {f.stem[:60]} — LLM не дал тегов, пропуск")
            continue
        text = add_tags_to_frontmatter(text, tags)
        f.write_text(text)
        log(f"  ✅ {f.stem[:60]} → теги: {', '.join(tags)}")
        tagged.append((f, tags))

    # Второй проход: расстановка связей по всем затронутым (включая ранее тегированные)
    log("\n🔗 Расстановка связей...")
    links_added = 0
    for f, tags in tagged:
        text = f.read_text(errors="ignore")
        related = wr.find_related_by_tags(tags, exclude_fname=f.name)
        related_names = [r.stem for r in related]
        # уже существующие ссылки из этого файла
        have = set(re.findall(r'\[\[([^\]|]+)', text))
        new_links = [n for n in related_names if n not in have]
        if not new_links:
            continue
        text = add_links_section(text, new_links)
        f.write_text(text)
        links_added += len(new_links)
        log(f"  {f.stem[:55]}: +{len(new_links)} → {', '.join(n[:40] for n in new_links)}")
        # обратные ссылки
        for r in related:
            rtext = r.read_text(errors="ignore")
            if f"[[{f.stem}]]" not in rtext:
                r.write_text(rtext.rstrip() + f"\n- 🔗 См. также: [[{f.stem}]]\n")
    log(f"\n**Итого:** заметок с тегами: {len(tagged)}/{len(files)}, новых ссылок: {links_added}")

if __name__ == "__main__":
    main()
