#!/usr/bin/env python3
"""
Hermes Session Snapshot Analyzer — state.db edition
Reads real token/cost data from ~/.hermes/state.db (NOT file estimation).

Usage:
    python3 analyze_snapshots.py [--week-start YYYY-MM-DD] [--output-dir ~/.hermes/cron/output]

IMPORTANT: This uses SQLite state.db for accurate token data.
Cache read cost is the #1 source of error. See PRICING_RETAIL dict below — update when prices change.

CRITICAL: Run via `terminal` with python3 heredoc — execute_code is BLOCKED in cron mode.
"""

import os
import json
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

STATE_DB = os.path.expanduser("~/.hermes/state.db")
OUTPUT_DIR = os.path.expanduser("~/.hermes/cron/output")
BASELINE_FILE = os.path.join(OUTPUT_DIR, "snapshot_baseline.json")
# User's week = Mon-Sun in UTC+7 (referred to as "MSK+4" by user)
WEEK_TZ = timezone(timedelta(hours=7))

# OpenRouter RETAIL pricing per 1M tokens — UPDATE THESE when prices change
# Retail = what OpenRouter dashboard shows (no cache discount, coefficient ~1.6x vs wholesale)
PRICING_RETAIL = {
    "deepseek/deepseek-v4-pro":                {"in": 0.692, "out": 1.383, "cache_read": 0.692},
    "openrouter/owl-alpha":                    {"in": 0.0,   "out": 0.0,   "cache_read": 0.0},  # FREE
    "nvidia/nemotron-3-ultra:free":            {"in": 0.0,   "out": 0.0,   "cache_read": 0.0},
    "nvidia/nemotron-3-super-120b-a12b:free":  {"in": 0.0,   "out": 0.0,   "cache_read": 0.0},
}


def get_model_pricing(model):
    if model in PRICING_RETAIL:
        return PRICING_RETAIL[model]
    for key, val in PRICING_RETAIL.items():
        if model and (key in model or model in key):
            return val
    return {"in": 0.0, "out": 0.0, "cache_read": 0.0}


def calculate_cost(model, in_tok, out_tok, cache_r):
    """Calculate cost using RETAIL pricing. No token scaling needed — use raw DB counts."""
    pricing = get_model_pricing(model or "")
    in_tok = in_tok or 0
    out_tok = out_tok or 0
    cache_r = cache_r or 0
    # Retail: cache_read priced at input rate (no discount)
    io_cost = (in_tok * pricing["in"] + out_tok * pricing["out"]) / 1_000_000
    cache_cost = cache_r * pricing["cache_read"] / 1_000_000
    return io_cost, cache_cost, io_cost + cache_cost


def query_sessions(cursor, week_start_ts, week_end_ts):
    cursor.execute("""
        SELECT id, source, model, started_at, message_count, tool_call_count,
               input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
               reasoning_tokens, estimated_cost_usd, actual_cost_usd, title
        FROM sessions
        WHERE started_at >= ? AND started_at < ?
        ORDER BY (COALESCE(input_tokens,0) + COALESCE(output_tokens,0) + COALESCE(cache_read_tokens,0)) DESC
    """, (week_start_ts, week_end_ts))
    return cursor.fetchall()


def fmt(n):
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000:    return f"{n//1_000}K"
    return str(n)


def build_report(rows):
    by_source = defaultdict(lambda: {"count": 0, "in": 0, "out": 0, "cache": 0, "cost": 0.0})
    by_model  = defaultdict(lambda: {"count": 0, "in": 0, "out": 0, "cache": 0, "msgs": 0, "cost": 0.0, "io_cost": 0.0, "cache_cost": 0.0})
    tot_in = tot_out = tot_cache = tot_io_cost = tot_cache_cost = 0
    with_tokens = 0
    top10 = []

    for (sid, source, model, started, msgs, tc, in_tok, out_tok,
         cache_r, cache_w, rtok, cost_est, cost_actual, title) in rows:
        in_tok = in_tok or 0; out_tok = out_tok or 0; cache_r = cache_r or 0
        source = source or "unknown"; model = model or "(no model)"
        io_cost, cache_cost, full_cost = calculate_cost(model, in_tok, out_tok, cache_r)

        tot_in += in_tok; tot_out += out_tok; tot_cache += cache_r
        tot_io_cost += io_cost; tot_cache_cost += cache_cost
        if in_tok > 0 or out_tok > 0: with_tokens += 1

        by_source[source]["count"] += 1; by_source[source]["in"] += in_tok
        by_source[source]["out"] += out_tok; by_source[source]["cache"] += cache_r
        by_source[source]["cost"] += full_cost

        by_model[model]["count"] += 1; by_model[model]["in"] += in_tok
        by_model[model]["out"] += out_tok; by_model[model]["cache"] += cache_r
        by_model[model]["msgs"] += (msgs or 0); by_model[model]["cost"] += full_cost
        by_model[model]["io_cost"] += io_cost; by_model[model]["cache_cost"] += cache_cost

        top10.append({"id": sid, "source": source, "model": model,
                       "in": in_tok, "out": out_tok, "cache": cache_r,
                       "total": in_tok + out_tok + cache_r, "msgs": msgs or 0, "started": started})

    n = len(rows)
    top10.sort(key=lambda x: x["total"], reverse=True)
    total_cost = tot_io_cost + tot_cache_cost
    total_tok = tot_in + tot_out
    return {
        "total_sessions": n, "sessions_with_tokens": with_tokens,
        "total_in": tot_in, "total_out": tot_out, "total_tokens": total_tok,
        "total_cache": tot_cache, "avg": total_tok // n if n else 0,
        "io_cost": tot_io_cost, "cache_cost": tot_cache_cost, "total_cost": total_cost,
        "by_source": dict(by_source), "by_model": dict(by_model), "top10": top10[:10],
    }


def save_baseline(report, ws, we):
    bl = {
        "week": f"{ws.strftime('%d.%m')}-{we.strftime('%d.%m')}",
        "date": datetime.now(MSK4).strftime("%Y-%m-%d"),
        "total_sessions": report["total_sessions"],
        "total_io_tokens": report["total_tokens"],
        "total_cache_tokens": report["total_cache"],
        "total_cost_usd": round(report["total_cost"], 2),
        "by_source": {s: {"count": d["count"], "tokens": d["in"]+d["out"], "cost": round(d["cost"], 2)} for s, d in report["by_source"].items()},
        "by_model":  {m: {"count": d["count"], "tokens": d["in"]+d["out"], "cache": d["cache"], "cost": round(d["cost"], 2)} for m, d in report["by_model"].items()},
    }
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(BASELINE_FILE, "w") as f: json.dump(bl, f, indent=2, ensure_ascii=False)
    return bl


def format_report(report, ws, we, prev):
    L = []; w = f"{ws.strftime('%d.%m')}-{we.strftime('%d.%m')}"
    L.append(f"📊 Снапшоты — неделя {w} (UTC+7)\n")
    L.append("📁 Сессии:")
    L.append(f"• Всего: {report['total_sessions']} сессий ({report['sessions_with_tokens']} с данными)")
    for src, d in sorted(report["by_source"].items(), key=lambda x: x[1]["in"]+x[1]["out"], reverse=True):
        L.append(f"  • {src.capitalize()} — {d['count']} сессий, {fmt(d['in']+d['out'])} токенов, ${d['cost']:.2f}")
    L.append("\n🤖 Модели (sessions/in/out/cache):")
    for model, d in sorted(report["by_model"].items(), key=lambda x: x[1]["in"]+x[1]["out"], reverse=True):
        L.append(f"• {model} — sess={d['count']}, in={fmt(d['in'])}, out={fmt(d['out'])}, cache={fmt(d['cache'])}")
    L.append("\n🔢 Токены за неделю:")
    L.append(f"• Input: {report['total_in']:,}")
    L.append(f"• Output: {report['total_out']:,}")
    L.append(f"• Cache read: {report['total_cache']:,}")
    L.append(f"• Среднее на сессию: {report['avg']:,}")
    L.append("\n💰 Стоимость (retail):")
    L.append(f"• Input/Output: ${report['io_cost']:.2f}")
    L.append(f"• Cache read: ${report['cache_cost']:.2f}")
    L.append(f"• ИТОГО: ${report['total_cost']:.2f}")
    L.append("\n🏆 Топ-10 сессий по токенам:")
    for i, s in enumerate(report["top10"], 1):
        started = datetime.fromtimestamp(s['started'], tz=WEEK_TZ).strftime('%d.%m %H:%M')
        L.append(f"{i:2}. [{started}] {s['source']:8} | {s['model']:35}")
        L.append(f"    in={fmt(s['in']):>8} out={fmt(s['out']):>6} cache={fmt(s['cache']):>8} total={fmt(s['total']):>10}")
    if prev:
        ds = report["total_sessions"] - prev.get("total_sessions", 0)
        dt = report["total_tokens"] - prev.get("total_io_tokens", 0)
        dc = report["total_cost"] - prev.get("total_cost_usd", 0)
        L.append(f"\n📈 Сравнение с ({prev.get('week','?')}):")
        L.append(f"• Сессии: {'+' if ds>=0 else ''}{ds}")
        L.append(f"• Токены: {'+' if dt>=0 else ''}{fmt(dt)}")
        L.append(f"• Стоимость: {'+' if dc>=0 else ''}${dc:.2f}")
    L.append("\nBaseline обновлён.")
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week-start", type=str)
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR)
    args = parser.parse_args()

    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if args.week_start:
        ws = datetime.strptime(args.week_start, "%Y-%m-%d").replace(tzinfo=WEEK_TZ)
    else:
        today = datetime.now(WEEK_TZ)
        # Last full week (Mon-Sun): go back to last Monday, then back one more week
        days_since_monday = today.weekday()
        last_mon = today - timedelta(days=days_since_monday + 7)
        ws = last_mon.replace(hour=0, minute=0, second=0, microsecond=0)
    we = ws + timedelta(days=7)  # exclusive end

    conn = sqlite3.connect(STATE_DB)
    rows = query_sessions(conn.cursor(), ws.timestamp(), we.timestamp())
    conn.close()

    if not rows:
        print(f"No sessions for week {ws.strftime('%d.%m')}-{we.strftime('%d.%m')}")
        return

    report = build_report(rows)
    prev = json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else None
    save_baseline(report, ws, we)

    text = format_report(report, ws, we, prev)
    print(text)

    rf = os.path.join(output_dir, f"snapshot_report_{ws.strftime('%d.%m')}-{we.strftime('%d.%m')}.txt")
    with open(rf, "w") as f: f.write(text)
    print(f"\nSaved: {rf}")


if __name__ == "__main__":
    main()
