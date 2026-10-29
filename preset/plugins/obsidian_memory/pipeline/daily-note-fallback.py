#!/usr/bin/env python3
"""Фолбэк-воркроджем для гибридного job'а «Daily Note в Obsidian» (8aa21e851f9c).

Задача агента в том job'е — наполнить daily note и написать развёрнутый отчёт.
Агент может упасть (провайдеры 403/451/451, дрейф конфига, таймаут). Этот
воркроджем страхует:

  1. Основной прогон агента не удался (last_status=error или last_delivery_error).
  2. Пробуем перезапустить агент — до MAX_REFIRES раз, с интервалом RETRY_GAP_MIN.
     Если агент ожил — придёт его нормальный отчёт (позже, но полноценный).
  3. Все ретраи исчерпаны (или повторных попыток нет) — выдаём ДЕТЕРМИНИРОВАННЫЙ
     отчёт без агента: `daily-note.py --report`. Он сам создаёт/дополняет заметку.

Пустой stdout = тишина (no_agent watchdog pattern). Cron-задача: раз в час.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERMES_BIN = os.environ.get("DN_FB_BIN") or os.path.expanduser("~/.local/bin/hermes")
# env-переопределения — только для тестов (прогон на фиктивном состоянии без правки jobs.json)
JOBS_FILE = os.environ.get("DN_FB_JOBS") or os.path.expanduser("~/.hermes/cron/jobs.json")
STATE_FILE = os.environ.get("DN_FB_STATE") or os.path.expanduser("~/.hermes/cron/daily-note-fallback-state.json")
NOTE_SCRIPT = os.environ.get("DN_FB_NOTE") or str(
    Path(__file__).resolve().parent / "daily-note.py"
)

TARGET_JOB_ID = "8aa21e851f9c"
RETRY_GAP_MIN = 60   # Igor: «ретраил прост раз в час»
MAX_REFIRES = 3      # Igor: «раза 3»
MIN_AGE_MIN = 15     # не хватаемся за прогон, который только что стартовал/упал


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def iso_local(s):
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def get_job(jobs, jid):
    for j in jobs:
        if j.get("id") == jid or j.get("job_id") == jid:
            return j
    return None


def main():
    now = datetime.now(timezone.utc)
    data = load_json(JOBS_FILE, {})
    jobs = data.get("jobs", data if isinstance(data, list) else [])
    job = get_job(jobs, TARGET_JOB_ID)
    if not job:
        return  # job удалён — молчим, чтобы не спамить вечно

    state = load_json(STATE_FILE, {})

    last_run_at = job.get("last_run_at")
    failing = job.get("last_status") == "error" or bool(job.get("last_delivery_error"))
    if not last_run_at or not failing:
        state.pop(TARGET_JOB_ID, None)  # успех/нет прогона — эпизод закрыт
        save(state)
        return  # тишина: всё хорошо (или рано)

    last = iso_local(last_run_at)
    if not last:
        return
    age_min = (now - last).total_seconds() / 60
    if age_min < MIN_AGE_MIN:
        return  # ещё свежий сбой, ждём

    # Новый эпизод сбоя = новый last_run_at.
    rec = state.get(TARGET_JOB_ID) or {}
    if rec.get("episode") != last_run_at:
        rec = {"episode": last_run_at, "refires": 0, "last_refire": None, "fallback_sent": False}

    refires = rec.get("refires", 0)

    # 1) Ещё есть попытки перезапустить агента.
    if refires < MAX_REFIRES:
        if rec.get("last_refire"):
            lr = iso_local(rec["last_refire"])
            if lr and (now - lr).total_seconds() / 60 < RETRY_GAP_MIN:
                return  # пауза между ретраями не вышла — тишина
        if job.get("fire_claim"):
            return  # задача уже выполняется — не мешаем
        try:
            r = subprocess.run(
                [HERMES_BIN, "cron", "run", TARGET_JOB_ID],
                capture_output=True, text=True, timeout=90,
            )
        except subprocess.TimeoutExpired:
            return  # не ответил — попробуем на следующем тике
        if r.returncode == 0:
            rec["refires"] = refires + 1
            rec["last_refire"] = now.isoformat()
            state[TARGET_JOB_ID] = rec
            save(state)
            n = rec["refires"]
            print(f"⏳ Daily Note: агент не отработал, перезапуск #{n}/{MAX_REFIRES}. "
                  "Если оживёт — придёт его полный отчёт. "
                  f"После {MAX_REFIRES} неудач выдам отчёт без агента.")
        # returncode != 0 — молчим, следующий тик попробует снова
        return

    # 2) Ретраи исчерпаны → детерминированный отчёт без агента (один раз за эпизод).
    if rec.get("fallback_sent"):
        return
    try:
        r = subprocess.run(
            [sys.executable, NOTE_SCRIPT, "--report"],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        return
    if r.returncode != 0 or not r.stdout.strip():
        return
    rec["fallback_sent"] = True
    state[TARGET_JOB_ID] = rec
    save(state)
    print(r.stdout.strip())


def save(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())