#!/usr/bin/env python3
"""Daily Note в Obsidian — служебный скрипт гибридного cron-job.

Два режима:

1) РЕЖИМ КОНТЕКСТА (по умолчанию) — для агента. Создаёт/находит файл daily note и
   печатает разобранный материал дня: значимые сессии из state.db, текущий блок
   «✅ Выполнено», содержательные cron-отчёты. Резюмирует агент.

2) РЕЖИМ ОТЧЁТА (--report) — БЕЗ агента, полностью детерминированный отчёт для
   Telegram. Используется фолбэк-воркроджем, когда агент упал: собирает отчёт из
   тех же источников, что и контекст, но сам решает, что показать.

Аргументы: [--report] [YYYY-MM-DD] — дата (для бекфилла); по умолчанию сегодня (UTC+4).
"""
import datetime
import os
import pathlib
import re
import sqlite3
import sys

TZ = datetime.timezone(datetime.timedelta(hours=4))
HERMES = pathlib.Path.home() / ".hermes"
VAULT = pathlib.Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault")).expanduser()
CRON_OUT = HERMES / "cron" / "output"

MAX_CANDIDATES = 40
MAX_REPORTS_CONTEXT = 12
MAX_REPORTS_REPORT = 8

RU_WEEKDAY = {
    "Monday": "понедельник", "Tuesday": "вторник", "Wednesday": "среда",
    "Thursday": "четверг", "Friday": "пятница", "Saturday": "суббота",
    "Sunday": "воскресенье",
}

# Служебные источники: субагенты и one-shot'ы не являются событиями дня.
NOISE_SOURCES = {"subagent", "oneshot"}
# Шаблоны cron-задач, которые повторяются десятки раз в день и не несут смысла.
NOISE_TITLE_RE = re.compile(
    r"^(Проверка корпоративной почты NTS|Ежедневный отчёт по снапшотам|"
    r"Ежедневная проверка обновлённой системы|Ежедневная статистика работы памяти|"
    r"магазин: проверка разблокировок|TokenHarbor Office Pass|cron-retry-watchdog|"
    r"desktop-cpu-sampler|Инкрементальная векторная индексация vault)",
    re.IGNORECASE,
)

SELF_JOB_DIR = "8aa21e851f9c"  # собственный отчёт job'а — не источник событий

# Строки, которые в отчётах почти всегда означают «нужно внимание Игоря».
ATTENTION_RE = re.compile(
    r"(требуют? ответа|требует? внимания|ждут? ответа|ожидают? ответа|"
    r"нужно подписать|требует? подписи|требует? действия|тред без ответа|"
    r"ответа нет|новых? документов? найден|найден новый|сломал|просит помочь)",
    re.IGNORECASE,
)


def day_sessions(d: datetime.date):
    """Сессии за день d (UTC+4).

    Возвращает (список[(время, источник, заголовок, msgs)], шум, ошибка|None).
    """
    lo = datetime.datetime(d.year, d.month, d.day, tzinfo=TZ).timestamp()
    hi = lo + 86400
    try:
        con = sqlite3.connect(f"file:{HERMES / 'state.db'}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT s.title, s.source, MAX(m.timestamp), COUNT(*) "
            "FROM sessions s JOIN messages m ON m.session_id = s.id "
            "WHERE m.timestamp >= ? AND m.timestamp < ? "
            "GROUP BY s.id ORDER BY MAX(m.timestamp) ASC",
            (lo, hi),
        ).fetchall()
        con.close()
    except Exception as e:
        return [], 0, f"{type(e).__name__}: {e}"

    out, seen = [], set()
    noise = 0
    for title, source, ts, msgs in rows:
        t = (title or "").strip()
        if source in NOISE_SOURCES:
            noise += 1
            continue
        if not t or t == "(без названия)":
            t = "(служебная сессия без названия)"
            noise += 1
        if NOISE_TITLE_RE.match(t):
            t = NOISE_TITLE_RE.sub("", t).strip(" ·-—") or t
        key = re.sub(r"\s+", " ", t.lower())
        if key in seen:
            noise += 1
            continue
        seen.add(key)
        hh = datetime.datetime.fromtimestamp(ts, TZ).strftime("%H:%M")
        out.append((hh, source or "?", t, msgs))
    return out, noise, None


def cron_outputs(d: datetime.date, limit: int, chars: int, skip_dir: str = ""):
    """Отчёты cron-задач за день d: [(stamp, размер, текст ответа)]."""
    if not CRON_OUT.is_dir():
        return []
    day = d.strftime("%Y-%m-%d")
    found = []
    for job_dir in CRON_OUT.iterdir():
        if not job_dir.is_dir() or (skip_dir and job_dir.name == skip_dir):
            continue
        for f in sorted(job_dir.glob("*.md")):
            if not f.name.startswith(day):
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            if "## Response" not in text:
                continue
            resp = text.split("## Response", 1)[-1]
            resp = resp.split("## Error", 1)[0].strip()
            resp = NOISE_TITLE_RE.sub("", resp).strip()
            if not resp or len(resp) < 40 or "Cronjob Response:" in resp:
                continue
            found.append((f.name[:16], f.stat().st_size, resp[:chars]))
    # свежие сверху (имя файла = время прогона)
    found.sort(key=lambda x: x[0], reverse=True)
    return found[:limit]


def current_done(path: pathlib.Path):
    """Текущее содержимое секции «✅ Выполнено» (пустая строка, если её нет)."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"(?ms)^##\s*✅ Выполнено\s*\n(.*?)(?=^##\s|\Z)", text)
    return m.group(1).strip() if m else ""


def ensure_note(d: datetime.date):
    """Создать daily note из шаблона, если нет. Возвращает (путь, действие)."""
    weekday_ru = RU_WEEKDAY[d.strftime("%A")]
    path = VAULT / "Daily" / f"{d.isoformat()}.md"
    if path.exists():
        return path, "уже существует — дополни секцию «✅ Выполнено»"
    tpl = (VAULT / "Templates" / "Daily Note.md").read_text(encoding="utf-8")
    tpl = tpl.replace("{{date:YYYY-MM-DD}}", d.isoformat())
    tpl = tpl.replace("{{date:dddd}}", weekday_ru)
    tpl = re.sub(r"(?m)^## ✅ Выполнено\n-.*$", "## ✅ Выполнено\n", tpl)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tpl, encoding="utf-8")
    return path, "создана из шаблона, «✅ Выполнено» пустое — заполни"


# --- Режим контекста (для агента) ---

def print_context(d: datetime.date):
    weekday_ru = RU_WEEKDAY[d.strftime("%A")]
    path, action = ensure_note(d)
    sessions, noise, err = day_sessions(d)

    print(f"ДАТА: {d.isoformat()} ({weekday_ru})")
    print(f"ФАЙЛ: {path}")
    print(f"ДЕЙСТВИЕ: {action}")
    print()

    if err:
        print(f"state.db НЕДОСТУПЕН ({err}) — собери сводку из cron-отчётов ниже.")
    elif not sessions:
        print("СЕССИИ: значимых нет (все служебные/повторяющиеся).")
    else:
        print(f"СЕССИИ ЗА ДЕНЬ (значимые: {len(sessions)}, отброшено шума: {noise}):")
        for hh, src, t, msgs in sessions[:MAX_CANDIDATES]:
            print(f"  {hh} [{src}] msgs={msgs} — {t}")

    done = current_done(path)
    print()
    print("ТЕКУЩИЙ БЛОК «✅ Выполнено» В ФАЙЛЕ:")
    print(done if done else "  (пусто)")

    reps = cron_outputs(d, MAX_REPORTS_CONTEXT, 600)
    print()
    if not reps:
        print("CRON-ОТЧЁТЫ ЗА ДЕНЬ: не найдено.")
    else:
        print(f"CRON-ОТЧЁТЫ ЗА ДЕНЬ ({len(reps)}), свежие и содержательные:")
        for stamp, size, resp in reps:
            print(f"  --- {stamp} ({size} B) ---\n{resp}\n")


# --- Режим отчёта (без агента, фолбэк) ---

def clean_topic(t: str) -> str:
    t = re.sub(r"\s*\[Replying to:.*$", "", t).strip()
    t = re.sub(r"^(\[[^\]]{1,20}\]\s*)", "", t).strip()
    return t


def _clean_lines(text: str):
    out = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", re.sub(r"[*#>`]", "", raw)).strip()
        line = re.sub(r"^[-–—•\d.)\s]+", "", line).strip()
        line = re.sub(r"^[^\w«\"(\[]+", "", line).strip()  # ведущие эмодзи/символы
        if len(line) >= 8:
            out.append(line)
    return out


def _topic_of(lines):
    """Тема письма/треда: сначала «Re: X» из заголовка, потом текст в кавычках.

    Порядок важен: в теле блока кавычками часто цитируется реплика собеседника,
    а не тема, и дедуп по ней схлопывает разные пункты.
    """
    head = lines[0]
    joined3 = " ".join(lines[:3])
    m = re.search(r"\bRe:\s*([^,«»\"]{3,40})", head)
    if m:
        return m.group(1)
    m = re.search(r"[«\"]([^»\"]{3,40})[»\"]", head)
    if m:
        return m.group(1)
    m = re.search(r"[«\"]([^»\"]{3,40})[»\"]", joined3)
    if m:
        return m.group(1)
    return head[12:44]


def attention_lines(reps):
    """Детерминированная выборка «требует внимания» из cron-отчётов.

    Отчёты пишутся блоками (пустая строка = новый пункт), поэтому триггер
    («требуют ответа») и суть пункта лежат в одном блоке. Берём блок целиком и
    отсекаем служебные подзаголовки вроде «Требуют ответа (ответа от вас нет)».
    """
    NEGATIVE_RE = re.compile(
        r"(не требует|не требуют|ответ отправлен|ответили|ответ есть|"
        r"ответа больше не нужно|закрыт[ао]? тред|требуют? ответа/действий:?$|"
        r"требуют? ответа \(|ждут ответа:?$|требует? внимания:?$|"
        r"^требует? внимания\b|^требуют? ответа\b)",
        re.IGNORECASE,
    )
    picked, seen = [], set()
    for stamp, _size, resp in reps:
        hm = re.match(r"\d{4}-\d{2}-\d{2}_(\d{2})-(\d{2})", stamp)
        tstr = f"{hm.group(1)}:{hm.group(2)}" if hm else stamp
        for block in re.split(r"\n\s*\n", resp):
            lines = _clean_lines(block)
            if not lines:
                continue
            hit = next((l for l in lines if ATTENTION_RE.search(l) and not NEGATIVE_RE.search(l)), None)
            if not hit:
                continue
            # суть = первые содержательные строки блока, где нет служебных подзаголовков
            useful = [l for l in lines[:3] if not NEGATIVE_RE.search(l)] or [hit]
            detail = " — ".join(useful)[:165]
            # дедуп по «кому + тема»: отчёты разных прогонов почты описывают один пункт
            # разными словами, но имя и тема стабильны
            head = lines[0]
            who = re.sub(r"\W+", "", head.split()[0].lower()) if head.split() else ""
            topic = re.sub(r"\W+", "", _topic_of(lines).lower())[:20].removeprefix("re")
            key = who + "|" + topic
            if key in seen:
                continue
            seen.add(key)
            picked.append((tstr, detail))
            if len(picked) >= 6:
                return picked
    return picked


def insert_done(path: pathlib.Path, lines):
    """Заполнить «✅ Выполнено» детерминированными строками (только если пусто)."""
    if current_done(path) or not lines:
        return 0
    block = "\n".join(lines)
    text = path.read_text(encoding="utf-8")
    m = re.search(r"(?m)^##\s*✅ Выполнено\s*\n(?:\n)*", text)
    if m:
        text = text[:m.start()] + "## ✅ Выполнено\n" + block + "\n" + text[m.end():]
    else:
        text = text.rstrip() + "\n\n## ✅ Выполнено\n" + block + "\n"
    path.write_text(text, encoding="utf-8")
    return len(lines)


def fill_done_from_sessions(path, sessions, limit: int = 7):
    """Агент недоступен — заполняем «✅ Выполнено» темами дня (хронологически).

    Отсекаем болтовню (короткие сессии) и cron-прогоны, у которых после снятия
    шаблона не осталось темы — иначе в заметку попадёт «Умение рисовать в чате».
    """
    rows, msgs_by_row = [], []
    for hh, _src, t, msgs in sessions:
        topic = clean_topic(t)
        bare = bool(re.match(r"^\d{1,2}:\d{2}(\s+·\s+\d{2}:\d{2})?$", topic))
        if not topic or topic.startswith("(служебная") or bare:
            continue
        if msgs < 20:
            continue
        rows.append(f"- [{hh}] {topic}")
        msgs_by_row.append(msgs)
    if not rows:  # всё отсеяно — лучше пусто, чем мусор
        return 0
    if len(rows) > limit:
        # оставить самую «объёмную» работу, но в хронологическом порядке
        big = sorted(range(len(rows)), key=lambda i: -msgs_by_row[i])[:limit]
        rows = [rows[i] for i in sorted(big)]
    return insert_done(path, rows)


def print_report(d: datetime.date):
    path, action = ensure_note(d)
    sessions, noise, err = day_sessions(d)
    done_before = current_done(path)
    reps = cron_outputs(d, MAX_REPORTS_REPORT, 2500, skip_dir=SELF_JOB_DIR)

    head = "создана" if action.startswith("создана") else "была"
    print(f"📓 Daily note {path.name} — {head}")
    print("⛔ Отчёт БЕЗ агента: модель была недоступна, ретраи не помогли. "
          "Файл заметки гарантированно создан, содержимое — автоматическое.")
    print()

    filled = 0
    if sessions and not done_before:
        filled = fill_done_from_sessions(path, sessions)

    if sessions:
        topics = [(hh, clean_topic(t), msgs) for hh, _src, t, msgs in sessions if msgs >= 5]
        topics = [(hh, t, m) for hh, t, m in topics if t]
        topics.sort(key=lambda x: -x[2])
        if topics:
            print(f"Ключевые темы дня ({len(sessions)} значимых сессий, шума отброшено {noise}):")
            for hh, t, msgs in topics[:6]:
                print(f"• {hh} {t[:95]} ({msgs} сообщ.)")
            print()
    elif err:
        print(f"⚠️ Сессии за день не прочитать: {err}")
        print()
    else:
        print("Значимых сессий за день не было.")
        print()

    att = attention_lines(reps)
    if att:
        print("Ждут внимания (по cron-отчётам дня):")
        for stamp, line in att:
            print(f"• [{stamp}] {line[:150]}")
        print()

    done_now = current_done(path)
    if filled:
        print(f"📝 Секция «Выполнено» заполнена автоматически ({filled} строк) из тем дня — "
              "можно поправить вручную в Obsidian.")
    elif done_now:
        print(f"✅ Секция «Выполнено» в заметке заполнена ({len(done_now.splitlines())} строк) — "
              "агент отработал частично, дубли не создавались.")
    else:
        print("📝 Секция «Выполнено» осталась пустой — её можно заполнить вручную в Obsidian.")

    if reps:
        print(f"Источник сводки: {len(reps)} cron-отчётов за день.")


def main():
    argv = list(sys.argv[1:])
    report_mode = "--report" in argv
    argv = [a for a in argv if not a.startswith("--")]
    if argv:
        d = datetime.date.fromisoformat(argv[0])
    else:
        d = datetime.datetime.now(TZ).date()
    if report_mode:
        print_report(d)
    else:
        print_context(d)


if __name__ == "__main__":
    main()