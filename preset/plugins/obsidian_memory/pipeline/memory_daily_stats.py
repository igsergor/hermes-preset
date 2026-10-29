#!/usr/bin/env python3
"""Ежедневная статистика работы памяти obsidian_memory (для крона, no_agent).

Парсит log-ротацию logs/agent.log[.1-.3] за последние 24ч — не tail -n 20000,
иначе день просто не помещается в окно (16026 строк за сутки против лимита
в 20000 строк файла, из них prefetch только ~10%).

Показывает:
- prefetch-обращения (obsidian-memory: prefetch ...) с hits>0 и hits=0
- записи фактов (obsidian-memory: fact added)
- срабатывания аварийного keyword (obsidian-memory EMERGENCY keyword fallback)
- пропуски из-за зависшего провайдера (prefetch timed out / skipping this turn)
- сколько ходов не дали вызова памяти (trivial-фильтр)

Тихо (пустой stdout), если активности не было.
"""
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path('/opt/data/logs')
CUTOFF = datetime.now() - timedelta(hours=24)

prefetch_re = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*obsidian-memory: prefetch query=(?P<q>.*) thread=(?P<t>\S*) hits=(?P<h>\d+) top_dist=(?P<d>\S+)$'
)
fact_re = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*obsidian-memory: fact added id=(?P<id>\S+) cat=(?P<c>\S+) len=(?P<l>\d+)$'
)
emerg_re = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*obsidian-memory EMERGENCY keyword fallback'
)
skip_re = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Memory provider .* prefetch (timed out|is still running)'
)
turn_re = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*agent\.turn_context: conversation turn'
)

# --- читаем ВСЕ ротированные файлы, фильтруем по дате внутри python ---
prefetches, facts, emerg, skips, turns = [], [], [], [], []
files = sorted(LOG_DIR.glob('agent.log*'), key=lambda p: p.name)
for path in files:
    if not path.is_file():
        continue
    try:
        out = subprocess.run(['cat', str(path)], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        continue
    for line in out.splitlines():
        if not line[:4].isdigit():
            continue
        try:
            ts = datetime.strptime(line[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if ts < CUTOFF:
            continue
        m = prefetch_re.match(line)
        if m:
            prefetches.append(m.groupdict())
            continue
        m = fact_re.match(line)
        if m:
            facts.append(m.groupdict())
            continue
        if emerg_re.match(line):
            emerg.append(ts)
            continue
        if skip_re.match(line):
            skips.append(line[:19] + ' ' + line.split('Memory provider')[-1][:60])
            continue
        if turn_re.match(line):
            turns.append(ts)

# --- инкремент векторной индексации из vault_vectors.db ---
idx = {'files': 0, 'chunks': 0, 'chars': 0, 'total_files': 0, 'total_chunks': 0}
try:
    import sqlite3
    c = sqlite3.connect('file:/opt/data/vault_vectors.db?mode=ro', uri=True, timeout=10)
    cutoff_ts = CUTOFF.timestamp()
    idx['files'] = c.execute("select count(*) from files where indexed_at > ?", (cutoff_ts,)).fetchone()[0]
    idx['chunks'], idx['chars'] = c.execute(
        "select count(*), coalesce(sum(length(ch.text)),0) from chunks ch join files f on f.path=ch.file_path "
        "where f.indexed_at > ?", (cutoff_ts,)).fetchone()
    idx['total_files'], idx['total_chunks'] = c.execute(
        "select (select count(*) from files), (select count(*) from chunks)").fetchone()
    c.close()
except Exception:
    pass

if not prefetches and not facts and not idx['files'] and not emerg:
    raise SystemExit(0)  # тихая ночь — ничего не отправляем

total = len(prefetches)
hits = sum(1 for p in prefetches if int(p['h']) > 0)
zero = total - hits
dists = [float(p['d']) for p in prefetches if p['d'] not in ('kw', 'None', 'nan')]
qcounts = Counter(p['q'].strip("'\"")[:50] for p in prefetches)

lines = [f'🧠 Память за сутки ({datetime.now():%d.%m %H:%M})']
if idx['files']:
    kb = idx['chars'] / 1024
    lines.append(f'📚 Индекс: +{idx["files"]} файлов, +{idx["chunks"]} чанков (~{kb:.0f} КБ текста); всего в базе {idx["total_files"]} файлов / {idx["total_chunks"]} чанков')
elif idx['total_files']:
    lines.append(f'📚 Индекс: файлов не менялось; всего в базе {idx["total_files"]} файлов / {idx["total_chunks"]} чанков')

# --- prefetch: вызовы и покрытие ---
lines.append(f'📥 Prefetch: {total} вызовов, с попаданиями {hits} ({hits * 100 // total if total else 0}%)')
if zero:
    lines.append(f'   без попаданий: {zero} (запрос не прошёл по индексу)')
if dists:
    lines.append(f'🎯 Средняя релевантность top-1: {sum(dists)/len(dists):.1f} (точные 19-23, шум 24-26)')

# --- сколько ходов было вообще (покрытие памятью) ---
if turns:
    n_turns = len(turns)
    cov = total * 100 // n_turns if n_turns else 0
    lines.append(f'🔄 Ходов: {n_turns} | вызовов памяти: {total} ({cov}%)')
    missing = n_turns - total
    if missing > 0:
        lines.append(f'   без вызова памяти: {missing} (trivial-фильтр: «ок», «привет», слэш-команды)')

# --- пропуски и аварии ---
if skips:
    lines.append(f'⚠️ Пропуски провайдера: {len(skips)}')
    for s in skips[:3]:
        lines.append(f'   • {s}')
if emerg:
    lines.append(f'🚨 Аварийный keyword: {len(emerg)} срабатываний')
    lines.append(f'   (очередь копилась 6 ходов или 180с без отдачи — лог: logs/obsidian-memory-emergency.jsonl)')

if total:
    top3 = ', '.join(f'«{q}»×{n}' for q, n in qcounts.most_common(3))
    lines.append(f'💬 Запросы: {top3}')

lines.append(f'✍️ Факты записано: {len(facts)}')
for f in facts[-5:]:
    lines.append(f'  • [{f["c"]}] id={f["id"]} ({f["l"]} симв.)')
if not facts:
    lines.append('  (ручных записей не было)')
print('\n'.join(lines))
