#!/usr/bin/env python3
"""
Инкрементальная векторная индексация Obsidian Vault → sqlite-vec.

ТЗ (согласовано 20-21.09.26):
- Эмбеддинги: ТОЛЬКО локально, Ollama bge-m3 на .130 (http://localhost:11434/api/embeddings, поле prompt!, dim 1024)
- Инкремент: SHA-256 контента (НЕ mtime — capture перезаписывает файлы при resume)
- Порядок: Resources → Knowledge (в Resources) → Archives/Sessions; Daily/Templates — фаза 2
- Шумовые групповые session-заметки (почта/watchdog/daily-note) — только первая строка заголовка (одна строка на день)
- Хранилище: sqlite-vec 0.1.9 (venv Hermes), одна БД $HERMES_HOME/vault_vectors.db
- Выдача при поиске: топ-3-5 (лимитирует вызывающий)
- Чанк ~500 токенов (≈2000 символов), перекрытие 200 символов
- Первый вызов после простоя Ollama ~20с → таймаут эмбеддинга 120с, батчи по 8

Использование:
  python3 vault_vector_index.py                 # инкрементальный прогон
  python3 vault_vector_index.py --full          # пересобрать всё (сносит таблицы)
  python3 vault_vector_index.py --search "запрос"  # тест поиска (top-5)
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.request
from pathlib import Path

VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "/opt/data/vault")).expanduser()
HERMES_HOME_DIR = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
DB_PATH = Path(os.environ.get("VAULT_VECTORS_DB", str(HERMES_HOME_DIR / "vault_vectors.db"))).expanduser()
OLLAMA_URL = 'http://localhost:11434/api/embeddings'
MODEL = 'bge-m3'
DIM = 1024
CHUNK_CHARS = 2000
CHUNK_OVERLAP = 200
EMBED_TIMEOUT = 300
BATCH = 4  # 01.10.26: было 8 — пачка из 8 чанков под нагрузкой упиралась в 300с и роняла весь прогон; 4 + ретраи с дроблением ниже
# 26.10.26: жёсткий кап входа эмбеддинга. llama-server у ollama собран с -b 2048:
# вход >2048 токенов даёт мгновенный HTTP 500 «increase the physical batch size»
# (наблюдалось 2361…8337 токенов на чанке ≤2000 символов: плотный код/base64/транскрипты
# дают до ~1.45 ток/сим). 1300 символов × 1.5 = 1950 < 2048 — безопасно с запасом.
# Режем ТОЛЬКО вход эмбеддинга; текст чанка в БД и хеш файла не меняются → без переиндексации.
MAX_EMBED_CHARS = 1300


def _truncate_embed_input(t: str) -> str:
    t = t.strip()
    return t[:MAX_EMBED_CHARS] if len(t) > MAX_EMBED_CHARS else t

# --- Фильтры по ТЗ ---

NOISE_SESSION_PATTERNS = [
    r'Проверка корпоративной почты',
    r'diadoc-watchdog',
    r'TokenHarbor',
    r'Daily Note в Obsidian',
    r'Еженедельн\w+ (разбор|отчёт|проверка)',
    r'hermes-update-monitor',
]

def is_noise_session(path: Path) -> bool:
    """Grouped noise session-заметки → только заголовок, без тела."""
    if 'Archives/Sessions' not in str(path):
        return False
    return any(re.search(p, path.stem, re.IGNORECASE) for p in NOISE_SESSION_PATTERNS)


# --- Сбор файлов по порядку полезности ---

def collect_files():
    """Resources → Knowledge (внутри Resources) → Archives/Sessions. Daily/Templates — фаза 2."""
    buckets = []
    res = sorted((VAULT / 'Resources').rglob('*.md')) if (VAULT / 'Resources').exists() else []
    sess = sorted((VAULT / 'Archives' / 'Sessions').glob('*.md')) if (VAULT / 'Archives' / 'Sessions').exists() else []
    # Projects/Areas тоже полезны (вручную ведём) — после Resources
    proj = sorted((VAULT / 'Projects').glob('*.md')) if (VAULT / 'Projects').exists() else []
    areas = sorted((VAULT / 'Areas').glob('*.md')) if (VAULT / 'Areas').exists() else []
    brain = sorted((VAULT / 'Brain' / 'facts').rglob('*.md')) if (VAULT / 'Brain' / 'facts').exists() else []
    knowledge = sorted((VAULT / 'Knowledge').rglob('*.md')) if (VAULT / 'Knowledge').exists() else []
    buckets = brain + knowledge + proj + areas + res + sess
    seen, out = set(), []
    for f in buckets:
        if f.is_file() and f.suffix == '.md' and str(f) not in seen:
            seen.add(str(f)); out.append(f)
    return out


# --- Чанкинг ---

def chunk_text(text: str):
    """Чанк ~2000 символов с перекрытием 200. Разрезаем по абзацам где можно."""
    if len(text) <= CHUNK_CHARS:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            # резать по последнему \n в окне
            nl = text.rfind('\n', start + CHUNK_CHARS - 400, end)
            if nl > start:
                end = nl
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


# --- sqlite-vec ---

def load_vec(conn):
    """Загружает sqlite_vec. ImportError здесь = не тот интерпретатор (крон гоняет .py
    через свой pm-venv без sqlite-vec — отсюда ночные ModuleNotFoundError).
    Тогда перезапускаемся тем питоном, где пакет точно есть: hermes-agent/venv
    (тот же, что в systemd-юните vault-vector-index). Синоним обёртки .sh."""
    try:
        import sqlite_vec  # noqa: F401
    except ImportError:
        import os, sys, subprocess
        fallback = os.environ.get(
            'HERMES_VEC_PYTHON',
            '/opt/hermes/.venv/bin/python3')
        if os.path.exists(fallback) and os.path.realpath(fallback) != os.path.realpath(sys.executable):
            os.execv(fallback, [fallback] + sys.argv)
        raise
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 60000")
    load_vec(conn)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            indexed_at REAL NOT NULL
        )
    ''')
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
            embedding float[1024]
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL,
            chunk_idx INTEGER NOT NULL,
            text TEXT NOT NULL,
            vec_rowid INTEGER,
            is_noise_header INTEGER DEFAULT 0,
            thread TEXT DEFAULT '',
            chat_id TEXT DEFAULT '',
            platform TEXT DEFAULT ''
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_path)')
    conn.commit()
    return conn


def serialize(v: list) -> bytes:
    return struct.pack(f'{len(v)}f', *v)


# --- Ollama ---

def embed_batch(texts: list, _depth: int = 0) -> list:
    """Эмбеддинг пачки по одному запросу. При сбое пачку дробим пополам и повторяем
    (01.10.26, решение Игоря: ретраи с дроблением вместо падения всего прогона).
    Одиночный текст — одна повторная попытка после паузы.
    06.10.26: сбой в ОДНОЙ половине дробления больше не роняет уже готовую вторую —
    каждая половина упакована в try/except, неудачный чанк падает последним и
    виден как отдельный RuntimeError, а не как TimeoutError спустя 300с."""
    if len(texts) > 1 and _depth < 4:
        mid = len(texts) // 2
        parts, errs = [], []
        for half in (texts[:mid], texts[mid:]):
            try:
                parts.append(embed_batch(half, _depth + 1))
            except Exception as e:
                parts.append(None)
                errs.append(f'{len(half)} chunks, depth {_depth + 1}: {e!r}')
        if errs:
            # имя ошибки и глубина — а не TimeoutError спустя 300с тишины
            raise RuntimeError('embed_batch half failed: ' + ' | '.join(errs))
        return parts[0] + parts[1]

    try:
        out = []
        for t in texts:
            t = _truncate_embed_input(t)
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps({'model': MODEL, 'prompt': t}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as r:
                d = json.load(r)
            emb = d.get('embedding')
            if not emb or len(emb) != DIM:
                raise RuntimeError(f'bad embedding: len={len(emb) if emb else None}')
            out.append(emb)
        return out
    except Exception:
        if len(texts) == 1 and _depth < 3:
            time.sleep(10)
            return embed_batch(texts, _depth + 1)
        raise


# --- Индексация ---

def file_body(path: Path):
    """Текст для индексации. Шумовые → только заголовок H1. Обычные → тело без frontmatter."""
    text = path.read_text(encoding='utf-8', errors='ignore')
    if is_noise_session(path):
        m = re.search(r'^#\s+(.+)$', text, re.M)
        return m.group(1) if m else path.stem
    # снять YAML frontmatter (в вектор не нужен, метаданные и так в заголовке)
    body = re.sub(r'^---\n.*?\n---\n', '', text, count=1, flags=re.S)
    return body


def file_meta(path: Path) -> dict:
    """Парсит frontmatter: thread, chat_id, platform. Для фильтра чужих тредов в плагине."""
    meta = {'thread': '', 'chat_id': '', 'platform': ''}
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')[:600]
        m = re.match(r'^---\n(.*?)\n---', text, re.S)
        if m:
            for line in m.group(1).splitlines():
                mm = re.match(r'^(thread|chat_id|platform):\s*"?([^"\n]*)"?', line.strip())
                if mm:
                    meta[mm.group(1)] = mm.group(2).strip()
    except Exception:
        pass
    return meta


def index_file(conn, path: Path, content_hash: str):
    # 09.10.26: имя файла печатается ДО эмбеддинга. Долгий embed_batch (50-300с на батч
    # под нагрузкой) оставлял лог без записей на 5-10 минут, и надзиратель по правилу
    # «лог молчит >25 мин» убивал живой процесс (exit 137). Теперь лог живёт весь прогон.
    print(f'→ {path.name} ({time.strftime("%H:%M:%S")})', flush=True)
    body = file_body(path)
    chunks = chunk_text(body)
    if not chunks:
        chunks = [path.stem]
    # удалить старые чанки файла
    old = conn.execute('SELECT vec_rowid FROM chunks WHERE file_path=?', (str(path),)).fetchall()
    for (rid,) in old:
        if rid:
            conn.execute('DELETE FROM vec_chunks WHERE rowid=?', (rid,))
    conn.execute('DELETE FROM chunks WHERE file_path=?', (str(path),))
    # эмбеддинг батчами
    rel = str(path)
    meta = file_meta(path)
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]
        embs = embed_batch(batch)
        for j, (txt, emb) in enumerate(zip(batch, embs)):
            cur = conn.execute('INSERT INTO vec_chunks(embedding) VALUES (?)', (serialize(emb),))
            rid = cur.lastrowid
            conn.execute('INSERT INTO chunks(file_path, chunk_idx, text, vec_rowid, is_noise_header, thread, chat_id, platform) VALUES (?,?,?,?,?,?,?,?)',
                         (rel, i + j, txt[:4000], rid, 1 if is_noise_session(path) else 0,
                          meta['thread'], meta['chat_id'], meta['platform']))
    conn.execute('INSERT OR REPLACE INTO files(path, content_hash, indexed_at) VALUES (?,?,?)',
                 (rel, content_hash, time.time()))
    conn.commit()
    return len(chunks)


def drop_file(conn, path: str):
    old = conn.execute('SELECT vec_rowid FROM chunks WHERE file_path=?', (path,)).fetchall()
    for (rid,) in old:
        if rid:
            conn.execute('DELETE FROM vec_chunks WHERE rowid=?', (rid,))
    conn.execute('DELETE FROM chunks WHERE file_path=?', (path,))
    conn.execute('DELETE FROM files WHERE path=?', (path,))
    conn.commit()


def run(full=False, verbose=True):
    # fcntl-блокировка на весь процесс индексации: два процесса одновременно
    # писали в один SQLite и второй падал с "database is locked" (busy_timeout
    # не спасает — транзакция открыта на время embed_batch, 50-105с на CPU).
    # Второй процесс уходит сразу, не трогая БД.
    lock_path = Path('/tmp/vault_vector_index.lock')
    lock_fd = open(lock_path, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if verbose:
            print('⚠️ Индексация уже запущена другим процессом — этот запуск пропущен')
        lock_fd.close()
        return
    try:
        _run_locked(full, verbose)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            lock_fd.close()


def _run_locked(full, verbose):
    conn = init_db()
    if full:
        conn.execute('DROP TABLE IF EXISTS vec_chunks')
        conn.execute('DROP TABLE IF EXISTS chunks')
        conn.execute('DROP TABLE IF EXISTS files')
        conn.commit()
        conn.close()
        conn = init_db()

    files = collect_files()
    known = {r[0]: r[1] for r in conn.execute('SELECT path, content_hash FROM files')}
    # существующие на диске файлы, которых нет в списке (удалены из vault) — чистить только в наших папках
    our_dirs = {'Resources', 'Projects', 'Areas', 'Archives'}
    stale = [p for p in known
             if not Path(p).exists() and any(f'/obsidian-vault/{d}/' in p for d in our_dirs)]

    todo, done, skipped, total_chunks = 0, 0, 0, 0
    failed = []
    t0 = time.time()
    for p in files:
        try:
            content = p.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            if verbose: print(f'⚠️ read fail {p.name}: {e}')
            continue
        h = hashlib.sha256(content.encode()).hexdigest()
        if known.get(str(p)) == h:
            skipped += 1
            continue
        try:
            n = index_file(conn, p, h)
        except Exception as e:
            # 06.10.26: один файл с таймаутом не роняет весь проход — остальные
            # файлы индексируются, список сбойных печатается в конце итога
            failed.append(f'{p.name}: {e}')
            continue
        done += 1
        total_chunks += n
        if verbose and (done % 10 == 0 or done < 5):
            # ETA по фактической скорости обработки файлов (30.09.26: старая формула
            # делила indexed-файлы на время ВСЕГО прохода, включая хеши skip'ов — врала в 10+ раз)
            scanned = done + skipped
            per_file = (time.time() - t0) / max(scanned, 1)
            eta = max(len(files) - scanned, 0) * per_file
            print(f'  … {done} переиндексировано ({total_chunks} чанков), ETA {eta/60:.0f} мин')
    for p in stale:
        drop_file(conn, p)
    dt = time.time() - t0
    print(f'✅ Готово: файлов всего {len(files)}, изменено {done} ({total_chunks} чанков), без изменений {skipped}, удалено {len(stale)}; {dt/60:.1f} мин')
    if failed:
        print(f'⚠️ Сбойные файлы: {len(failed)} — остались без индекса, повторятся на следующем проходе:')
        for f in failed:
            print(f'   - {f[:200]}')
    print(f'failed={len(failed)}')  # для задачи-надзирателя: 0 = всё ок
    conn.close()


# --- Поиск (для приёмки) ---

def search(query: str, top=5, thread: str = '', chat_id: str = ''):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 60000")
    load_vec(conn)
    q = embed_batch([query])[0]
    # k больше top — чтобы после thread-фильтрации осталось достаточно
    k = top * 4 if (thread or chat_id) else top
    rows = conn.execute('''
        SELECT c.file_path, c.chunk_idx, c.text, distance, c.thread, c.chat_id
        FROM (SELECT rowid, distance FROM vec_chunks WHERE embedding MATCH ? ORDER BY distance LIMIT ?) v
        JOIN chunks c ON c.vec_rowid = v.rowid
    ''', (serialize(q), k)).fetchall()
    conn.close()
    if thread or chat_id:
        rows = [r for r in rows if (not thread or r[4] == thread) and (not chat_id or r[5] == chat_id)][:top]
    for fp, idx, txt, dist, thr, chid in rows:
        name = Path(fp).stem
        print(f'\n[{dist:.3f}] {name} (чанк {idx}, thread={thr or "-"})')
        print('   ' + txt[:200].replace('\n', ' '))


def ensure_meta_columns(conn):
    """Миграция: добавить thread/chat_id/platform в существующую таблицу chunks."""
    cols = {r[1] for r in conn.execute('PRAGMA table_info(chunks)')}
    for col in ('thread', 'chat_id', 'platform'):
        if col not in cols:
            conn.execute(f'ALTER TABLE chunks ADD COLUMN {col} TEXT DEFAULT \'\'')
    conn.commit()


def rescan_meta(conn):
    """Перечитать frontmatter и обновить thread/chat_id/platform у существующих чанков (без переэмбеддинга)."""
    import json as _json
    n = 0
    for (path,) in conn.execute('SELECT DISTINCT file_path FROM chunks'):
        p = Path(path)
        if not p.exists():
            continue
        meta = file_meta(p)
        cur = conn.execute('UPDATE chunks SET thread=?, chat_id=?, platform=? WHERE file_path=?',
                           (meta['thread'], meta['chat_id'], meta['platform'], path))
        n += cur.rowcount
    conn.commit()
    print(f'✅ meta обновлена у {n} чанков')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--full', action='store_true', help='пересобрать всё')
    ap.add_argument('--search', type=str, help='тестовый поиск')
    ap.add_argument('--rescan-meta', action='store_true', help='обновить thread/chat_id у чанков без переэмбеддинга')
    ap.add_argument('--thread', type=str, default='', help='фильтр по thread (для --search)')
    ap.add_argument('--chat-id', type=str, default='', help='фильтр по chat_id (для --search)')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    if a.search:
        search(a.search, thread=a.thread, chat_id=getattr(a, 'chat_id', ''))
    elif a.rescan_meta:
        c = init_db()
        ensure_meta_columns(c)
        rescan_meta(c)
        c.close()
    else:
        run(verbose=not a.quiet)
