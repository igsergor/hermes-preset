#!/usr/bin/env python3
"""
Еженедельный разбор Obsidian vault.
- No_agent скрипт: механическая работа без LLM, DeepSeek вызывается только
  для дистилляции новых сессий — по одной за раз, без перегрузки контекста.
- Обработанные сессии помечаются в state.json и не трогаются повторно.
- Вывод идёт в stdout → Telegram (через no_agent cron).
"""

import json, os, subprocess, sys, time, re

import provider_compat as pc
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    # PyYAML пропадал из tools-python после обновления (28.09.26: ModuleNotFoundError
    # ронял весь прогон крона). Системный python3.12 его имеет — переисполняемся им один раз.
    if os.environ.get("WEEKLY_YAML_FALLBACK") == "1" or not Path("/usr/bin/python3").exists():
        sys.exit("ModuleNotFoundError: No module named 'yaml'")
    os.environ["WEEKLY_YAML_FALLBACK"] = "1"
    os.execv("/usr/bin/python3", ["/usr/bin/python3"] + sys.argv)

HERMES_HOME_DIR = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
HERMES_CONFIG = Path(os.environ.get("HERMES_CONFIG", str(HERMES_HOME_DIR / "config.yaml"))).expanduser()
VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault")).expanduser()
STATE = Path(os.environ.get("OBSIDIAN_WEEKLY_STATE", str(HERMES_HOME_DIR / "scripts" / ".obsidian-weekly-state.json"))).expanduser()
CLI = Path(os.environ.get("OBSIDIAN_CLI", str(HERMES_HOME_DIR / "skills" / "productivity" / "obsidian-vault" / "scripts" / "obsidian-cli.py"))).expanduser()
UNWRAP_URL = "http://127.0.0.1:8765/chat/completions"

def get_model_config():
    """Прочитать модель по умолчанию из config.yaml и определить endpoint для API.

    Returns:
        (model_id: str, endpoint_url: str, api_key: str or None)
        - Для ClinePass: endpoint = unwrap proxy (:8765), api_key = None (прокси сам авторизует)
        - Для остальных: endpoint = base_url провайдера + /chat/completions, api_key = из config/key_env
    """
    try:
        with open(HERMES_CONFIG) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        log(f"  ⚠ Ошибка чтения config.yaml: {e}")
        return ("", "", None)

    model_id = cfg.get("model", {}).get("default", "")
    if not model_id:
        return ("", "", None)

    for _key, prov in pc.provider_entries(cfg):
        if model_id not in pc.model_ids(prov):
            continue  # этот провайдер не содержит нашу модель

        base_url = pc.provider_url(prov)

        # ClinePass — идёт через unwrap proxy
        if "cline-pass" in model_id or "127.0.0.1:8765" in base_url:
            return (model_id, f"{base_url}/chat/completions", None)

        # Остальные — напрямую
        return (model_id, f"{base_url}/chat/completions", pc.api_key(prov))

    # Если модель не найдена в providers/custom_providers — fallback на unwrap (старое поведение)
    log(f"  ⚠ Модель '{model_id}' не найдена в providers, fallback на unwrap proxy")
    return (model_id, UNWRAP_URL, None)

SESSIONS_DIR = VAULT / "Archives" / "Sessions"
INBOX_DIR = VAULT / "Inbox"
RESOURCES_DIR = VAULT / "Resources"
KNOWLEDGE_DIR = VAULT / "Resources" / "Knowledge"

# Маппинг тематических тегов LLM-дистилляции → подпапка Knowledge.
# Первый совпавший тег определяет папку; ничего не совпало → Misc.
TAG_SUBDIR = [
    ({"omniroute", "ai-gateway", "clinepass", "cline", "opencode-go",
      "muse-spark", "tokenharbor", "mem0", "ollama", "deepseek", "qwen",
      "llm-providers", "llm-routing", "vision", "vision-models", "openrouter",
      "model-sync", "model-catalog", "compression", "prompt-cache", "truncation",
      "max-tokens", "api", "providers"}, "AI-LLM"),
    ({"cron", "capture", "indexing", "knowledge-capture", "session-log",
      "automation", "sqlite", "python", "config", "config-management",
      "json", "filtering", "channels", "triage", "subscriptions",
      "classification", "content-filtering", "system-audit", "state-db",
      "session-report", "empty-session", "hermes", "hermes-agent",
      "hermes-gateway", "obsidian", "knowledge-management", "vault-setup",
      "telegram", "session-capture", "hooks", "streaming", "footer",
      "troubleshooting", "bug", "error-handling", "gateway", "configuration",
      "ai-gateway"}, "Hermes"),
    ({"exchange", "corpmail", "smtp", "imap", "email"}, "Mail"),
    ({"vpn", "shop", "firefox", "firefox-snap", "snap", "qurator", "qration",
      "remote-windows-admin", "pywinrm", "impacket", "smb",
      "reasoning-levels"}, "Infra-Shopping"),
    ({"pension", "personal-finance", "npf", "ipk"}, "Finance"),
]

def knowledge_subdir(tags):
    """Подпапка Knowledge по тегам LLM. Возвращает имя подпапки."""
    tset = {t.strip().lower() for t in (tags or [])}
    for tagset, sub in TAG_SUBDIR:
        if tset & tagset:
            return sub
    return "Misc"

# Те же запрещённые символы, что в auto-capture (слэш в заголовке ронял capture).
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(name, max_len=120):
    """Безопасное имя файла: режет запрещённые символы, схлопывает пробелы."""
    name = _UNSAFE_CHARS.sub(' - ', name or '')
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name[:max_len].rstrip() or 'untitled'

def log(msg):
    print(msg, flush=True)

def fail(msg):
    log(f"❌ {msg}")
    sys.exit(1)

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return f"[timeout {timeout}s]", -1

# ─── Состояние ──────────────────────────────────────────
def load_state():
    if STATE.exists():
        with open(STATE) as f:
            return json.load(f)
    return {"last_run": "", "processed_sessions": []}

def save_state(state):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ─── DeepSeek дистилляция одной сессии ──────────────────
# ─── Префильтр шума: не тратить LLM-вызовы на сервисные сессии ──────────
NOISE_TITLE_PATTERNS = [
    r'Проверка корпоративной почты',
    r'diadoc-watchdog',
    r'TokenHarbor',
    r'Daily Note в Obsidian',
    r'Еженедельн\w+ (разбор|отчёт|проверка)',
    r'Ответь одним словом',
    r'^ок$',
]

def is_noise_filename(name):
    """Filename like 'Session - 2026-09-18 - Проверка корпоративной почты NTS · Sep 18 15:22.md'"""
    stem = re.sub(r'^Session - \d{4}-\d{2}-\d{2} - ', '', Path(name).stem)
    t = stem.strip().lower()
    return any(re.search(p, t, re.IGNORECASE) for p in NOISE_TITLE_PATTERNS)

def extract_message_count(text):
    m = re.search(r'message_count:\s*(\d+)', text)
    return int(m.group(1)) if m else 0

def distill_session(content, session_id):
    """Отправить содержимое одной сессии в LLM для извлечения знаний.
    Возвращает: (status, text) — status: 'ok' | 'empty' | 'error'.
    'error' не должен помечать сессию обработанной (ретрай в следующий раз)."""
    prompt = (
        "Извлеки знания из этой сессии Hermes-агента. "
        "Ответ напиши на русском, кратко (3-8 строк), только суть: "
        "какие технические детали, настройки, команды, решения были найдены. "
        "Если полезного содержания нет — ответь одним словом: НЕТ\n"
        "В самом конце ответа добавь строку строго в формате:\n"
        "TAGS: тег1, тег2, тег3\n"
        "(2-4 тематических тега латиницей: технологии, системы, темы — например: omniroute, vpn, cron, obsidian)\n\n"
        f"Сессия:\n{content[:8000]}"
    )
    model_id, endpoint, api_key = get_model_config()
    if not model_id:
        log("  ⚠ Не удалось прочитать модель по умолчанию из config.yaml")
        return ("error", "нет модели в config.yaml")
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.3,
        "stream": False,
    })
    cmd = ["curl", "-s", "-X", "POST", endpoint,
           "-H", "Content-Type: application/json",
           "-d", payload,
           "--max-time", "300"]
    if api_key:
        cmd.insert(4, "-H")
        cmd.insert(5, f"Authorization: Bearer {api_key}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=310)
        body = r.stdout.strip()
        if not body:
            return ("error", "пустой ответ")
        # Некоторые провайдеры (ClinePass) заворачивают ответ в {"data": {...}}
        resp = json.loads(body)
        if isinstance(resp.get("data"), dict) and "choices" in resp["data"]:
            resp = resp["data"]
        if "choices" in resp:
            text = resp["choices"][0]["message"]["content"].strip()
            if text.upper() == "НЕТ":
                return ("empty", None)
            return ("ok", text)
        elif "error" in resp:
            err = resp["error"]
            if isinstance(err, dict): err = err.get("message", str(err))
            return ("error", str(err)[:120])
        else:
            return ("error", f"неожиданный формат ответа: {body[:80]}")
    except Exception as e:
        return ("error", str(e)[:120])

def parse_tags(knowledge_text):
    """Вытащить строку 'TAGS: a, b, c' из ответа LLM. Возвращает (body, tags)."""
    m = re.search(r'TAGS:\s*(.+)\s*$', knowledge_text.strip(), re.IGNORECASE | re.MULTILINE)
    if not m:
        return knowledge_text, []
    tags = [t.strip().lower() for t in m.group(1).split(',') if t.strip()]
    tags = [re.sub(r'[^\w-]', '', t) for t in tags]
    tags = [t for t in tags if t][:5]
    body = knowledge_text[:m.start()].rstrip()
    return body, tags

def find_related_by_tags(tags, exclude_fname):
    """Найти существующие Knowledge-заметки с пересечением тематических тегов.
    Ищем в frontmatter ('tags: [...]') и в теле ('#TAGS:' хранится в frontmatter
    заметки, который создаём). Возвращает список имён файлов."""
    if not tags:
        return []
    related = []
    for f in RESOURCES_DIR.rglob("Knowledge*.md"):
        if f.name == exclude_fname:
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        fm = re.search(r'tags:\s*\[(.*?)\]', text)
        if not fm:
            continue
        ftags = {t.strip().lower() for t in fm.group(1).split(',')}
        if ftags & set(tags):
            related.append(f)
    return related

def create_knowledge_note(title, body, session_id, tags=None):
    """Создать/обновить заметку знаний в Resources/Knowledge/<подпапка по тегам>."""
    tags = tags or []
    subdir = KNOWLEDGE_DIR / knowledge_subdir(tags)
    subdir.mkdir(parents=True, exist_ok=True)
    safe = sanitize_filename(re.sub(r'[^\w\s-]', '', title), max_len=60)
    fname = f"Knowledge - {safe}.md"
    fpath = subdir / fname
    # Проверить, есть ли уже заметка про этот session_id
    if fpath.exists():
        content = fpath.read_text()
        if f'session_ids: "{session_id}"' in content:
            return None  # уже есть
    frontmatter = (
        "---\n"
        "tags: [knowledge, entry, distilled" + (", " + ", ".join(tags) if tags else "") + "]\n"
        f"created: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"session_id: \"{session_id}\"\n"
        "status: active\n"
        "---\n\n"
    )
    body_text = f"# {title}\n\n{body}\n"
    # Связанные заметки по тегам (в обе стороны)
    links_section = ""
    if tags:
        related = find_related_by_tags(tags, fname)
        if related:
            lines = [f"- [[{r.stem}]]" for r in related]
            links_section = "\n## 🔗 Связанные знания\n" + "\n".join(lines) + "\n"
            # Обратная ссылка: дописать в найденные заметки ссылку на новую
            for r in related:
                try:
                    rtext = r.read_text(errors="ignore")
                    if f"[[{fname[:-3]}]]" not in rtext:
                        rtext = rtext.rstrip() + f"\n- 🔗 См. также: [[{fname[:-3]}]]\n"
                        r.write_text(rtext)
                except Exception:
                    pass
    # Если файл уже есть — дописать
    if fpath.exists():
        existing = fpath.read_text()
        existing += f"\n---\n## {title}\n{body}\n{links_section}"
        fpath.write_text(existing)
    else:
        fpath.write_text(frontmatter + body_text + links_section)
    return fname

# ─── Поиск session_id в файле заметки ──────────────────
def extract_session_id(text):
    m = re.search(r'session_id:\s*"([^"]+)"', text)
    return m.group(1) if m else None

# ─── Основная логика ────────────────────────────────────
def main():
    log("📋 **Еженедельный разбор Obsidian**\n")
    state = load_state()
    last_run = state.get("last_run", "")
    processed = set(state.get("processed_sessions", []))
    new_processed = set()

    # 1. Статистика vault
    out, code = run(["python3", str(CLI), "stats"], timeout=15)
    if code == 0:
        log(f"📊 Статистика vault:\n```\n{out}\n```\n")
    else:
        log(f"⚠ Статистика недоступна: {out}\n")

    # 2. Проверка Inbox
    inbox_files = list(INBOX_DIR.glob("*.md")) if INBOX_DIR.exists() else []
    if inbox_files:
        log(f"📥 **Inbox: {len(inbox_files)} заметок** — требуют ручного разбора:")
        for f in inbox_files[:5]:
            log(f"  • {f.name}")
        if len(inbox_files) > 5:
            log(f"  … и ещё {len(inbox_files)-5}")
        log()
    else:
        log("📥 Inbox: пусто ✅\n")

    # 3. Проверка новых сессий в Archives/Sessions
    if not SESSIONS_DIR.exists():
        log("📦 Archives/Sessions: нет файлов\n")
    else:
        session_files = sorted(SESSIONS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        new_sessions = []
        skipped_noise = []
        for f in session_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if not last_run or mtime.isoformat() > last_run:
                if is_noise_filename(f.name):
                    # Сервисные серии (почта, watchdog'и, Daily Note) — помечаем
                    # обработанными без LLM, знания из них не дистиллируются.
                    skipped_noise.append(f)
                    text = f.read_text(errors="ignore")
                    sid = extract_session_id(text)
                    if sid:
                        new_processed.add(sid)
                else:
                    new_sessions.append(f)

        if skipped_noise:
            log(f"  ⏭ Пропущено без LLM (сервисные серии): {len(skipped_noise)}")

        if not new_sessions:
            log("📦 Archives/Sessions: новых (не-сервисных) сессий за неделю нет ✅\n")
        else:
            log(f"📦 Archives/Sessions: {len(new_sessions)} новых сессий на дистилляцию")
            MAX_PER_RUN = 8
            if len(new_sessions) > MAX_PER_RUN:
                log(f"  (обрабатываю только {MAX_PER_RUN}, остальные в следующий раз)")
                new_sessions = new_sessions[:MAX_PER_RUN]

            for sf in new_sessions:
                text = sf.read_text()
                sid = extract_session_id(text)
                if sid and sid in processed:
                    log(f"  {sf.name} — уже обработана, пропуск")
                    continue

                # Дешёвый механический фильтр: совсем короткие сессии не стоят LLM-вызова
                if extract_message_count(text) <= 2:
                    log(f"  ⏭ {sf.name} — ≤2 сообщений, без LLM")
                    if sid:
                        new_processed.add(sid)
                    continue

                log(f"  🔄 Дистилляция: {sf.name}…")
                status, knowledge = distill_session(text, sid or sf.name)
                if status == "ok":
                    body, tags = parse_tags(knowledge)
                    fname = create_knowledge_note(sf.name.replace("Session - ", "").replace(".md", ""), body, sid or sf.name, tags)
                    if fname:
                        extra = f" (теги: {', '.join(tags)}, связи: {len(find_related_by_tags(tags, fname))})" if tags else ""
                        log(f"✅ → {fname}{extra}")
                    else:
                        log("✅ (уже есть)")
                    if sid:
                        new_processed.add(sid)
                elif status == "empty":
                    log("⏭ (нет ценных знаний)")
                    if sid:
                        new_processed.add(sid)
                else:
                    # Ошибка API — НЕ помечаем обработанной, ретрай в следующий раз
                    log(f"  ⚠ API error: {knowledge} — ретрай в следующий раз")
            log("")

    # 4. Проверка битых вики-ссылок в хабах
    hubs = ["Resources/Resources Hub.md", "Projects/Hermes Agent — Настройка и расширение.md",
            "Areas/Development & Tech.md", "🏠 Start Here.md"]
    broken = []
    for hp in hubs:
        fp = VAULT / hp
        if not fp.exists():
            continue
        text = fp.read_text()
        for m in re.finditer(r'\[\[([^\]|]+)', text):
            target = m.group(1).strip()
            # Пропустить внешние/URL
            if target.startswith("http"):
                continue
            # Искать файл по любому пути
            matches = list(VAULT.rglob(f"{target}.md"))
            if not matches:
                broken.append((hp, target))
    if broken:
        log(f"🔗 **Найдено {len(broken)} битых вики-ссылок:**")
        for hp, link in broken[:8]:
            log(f"  • {link} (в {hp})")
        if len(broken) > 8:
            log(f"  … и ещё {len(broken)-8}")
        log()
    else:
        log("🔗 Битых вики-ссылок нет ✅\n")

    # 5. Обновить состояние
    processed.update(new_processed)
    state["processed_sessions"] = sorted(processed)
    save_state(state)

    # 6. Резюме
    total = len(session_files) if SESSIONS_DIR.exists() else 0
    total_res = len(list(RESOURCES_DIR.rglob("Knowledge*.md"))) if RESOURCES_DIR.exists() else 0
    log(f"**Сводка:** Inbox={len(inbox_files)} | Сессий в архиве={total} | Knowledge заметок={total_res} | Новых дистилляций={len(new_processed)} | Битых ссылок={len(broken)}")

if __name__ == "__main__":
    main()