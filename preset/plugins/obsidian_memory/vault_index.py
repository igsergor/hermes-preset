"""Vector index over the real Obsidian vault (sqlite-vec + local Ollama bge-m3).

Reads the index built by ~/.hermes/scripts/vault_vector_index.py:
DB /opt/data/vault_vectors.db (files + chunks + vec_chunks, 1024-dim bge-m3).
Embeddings are LOCAL ONLY (Ollama on .130) — decision 20.09.26, no API fallback here.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import struct
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HERMES_HOME_DIR = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
VEC_DB = HERMES_HOME_DIR / 'vault_vectors.db'
DEFAULT_VAULT_PATH = str(Path("~/obsidian-vault").expanduser())
OLLAMA_URL = 'http://localhost:11434/api/embeddings'
MODEL = 'bge-m3'
DIM = 1024
EMBED_TIMEOUT = 300
KEEP_ALIVE = '-1'  # 27.10.26 (Игорь): bge-m3 НИКОГДА не выгружается. Было '24h' —
            # сутки простоя выгружали модель и первый recall платил ~105с холодной загрузки.
            # Явный keep_alive в запросе ПЕРЕКРЫВАЕТ серверный OLLAMA_KEEP_ALIVE,
            # поэтому -1 надо держать и здесь, и в ollama.service.d/override.conf.
# 26.10.26: кап входа — llama-server у ollama собран с -b 2048, вход >2048 токенов
# даёт мгновенный HTTP 500 «increase the physical batch size» (длинные запросы recall).
# 1300 символов × 1.5 ток/сим = 1950 < 2048 — безопасно с запасом.
MAX_EMBED_CHARS = 1300


def serialize(v: List[float]) -> bytes:
    return struct.pack(f'{len(v)}f', *v)


class VaultVectorIndex:
    """Read-only semantic search over the vault vector index."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else VEC_DB
        self._lock = threading.Lock()
        self._last_embed = 0.0

    def available(self) -> bool:
        return self.db_path.exists()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True, timeout=10)
        try:
            import sqlite_vec
        except ModuleNotFoundError:
            # hermes_bootstrap герметизирует sys.path (site-packages вырезан) —
            # грузим вендор из _vendor/ (копия пакета внутри плагина, 176K)
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent / '_vendor'))
            import sqlite_vec
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception as e:
            conn.close()
            raise RuntimeError(f'sqlite-vec load failed: {e}')
        return conn

    def _embed(self, text: str) -> List[float]:
        # Warm-cache: skip re-embedding identical query within 30s
        text = text.strip()[:MAX_EMBED_CHARS]  # 26.10.26: кап под -b 2048 (см. выше)
        with self._lock:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps({'model': MODEL, 'prompt': text, 'keep_alive': KEEP_ALIVE}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as r:
                d = json.load(r)
            emb = d.get('embedding')
            if not emb or len(emb) != DIM:
                raise RuntimeError(f'bad embedding len={len(emb) if emb else None}')
            self._last_embed = time.time()
            return emb

    def search(
        self,
        query: str,
        *,
        top: int = 5,
        thread: str = '',
        chat_id: str = '',
        max_distance: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Semantic search. thread/chat_id filter: session-note chunks only —
        Resources/Knowledge (thread='') always pass through (общие знания)."""
        if not self.available():
            return []
        try:
            q = self._embed(query)
        except Exception as e:
            logger.warning('vault_vector embed failed: %s', e)
            return []
        k = top * 4 if (thread or chat_id) else top
        try:
            conn = self._connect()
            rows = conn.execute('''
                SELECT c.file_path, c.chunk_idx, c.text, v.distance, c.thread, c.chat_id, c.is_noise_header
                FROM (SELECT rowid, distance FROM vec_chunks WHERE embedding MATCH ?
                      ORDER BY distance LIMIT ?) v
                JOIN chunks c ON c.vec_rowid = v.rowid
            ''', (serialize(q), k)).fetchall()
            conn.close()
        except Exception as e:
            logger.warning('vault_vector search failed: %s', e)
            return []

        out = []
        for fp, idx, text, dist, thr, chid, is_noise in rows:
            if dist > max_distance:
                continue
            # Thread filter: only session-note chunks carry thread/chat_id; shared notes (thread='') pass.
            if thread or chat_id:
                if thr or chid:  # session-note chunk
                    if thread and thr and thr != thread:
                        continue
                    if chat_id and chid and chid != chat_id:
                        continue
            out.append({
                'file_path': fp,
                'name': Path(fp).stem,
                'chunk_idx': idx,
                'text': text,
                'distance': dist,
                'thread': thr,
                'is_noise_header': bool(is_noise),
            })
        return out[:top]


_TOKEN_RE = re.compile(r'[0-9a-zA-Zа-яёА-ЯЁ_]{2,}')
# Стоп-слова убираются из запроса ДО подсчёта: иначе «на/и/по/с» дают overlap
# всем файлам подряд и keyword возвращает шум (решение 04.10.26).
_STOPWORDS = frozenset("""
и в на по с не что как а то он она они мы вы это тот та те от до за из у о об при про
для же бы но или если так как уже еще ещё был была были быть есть нет можно надо
к от по на и из с со во ко да ли бы вот там тут где когда чем это тот та те все всё
the a an of to in for on and or is are was were be been it its this that with as at by
from not no but if then than so such we you they he she i my your our their
""".split())

# Порог: доля IDF-веса запроса, ниже которой совпадение считается шумом.
# 0.34 отсекает «3X-UI_KIT» на запросе про микротик (пересечение только по шуму).
_KEYWORD_MIN_SCORE = 0.34
# Слово, встречающееся в большинстве заметок vault, не различает ничего.
# Ниже этого порога IDF запрос отбрасывается целиком — иначе «это самое»
# набирает score 1.00 на первом попавшемся файле.
_KEYWORD_MIN_IDF = 0.15
_EXTRA_STOP = frozenset("""
самое самый самая самую ещё щас сейчас тогда потом теперь также либо какой какая
какие какое очень просто потом пока наконец наконец-то
""".split())


def _query_words(query: str) -> set:
    return {w for w in _TOKEN_RE.findall(query.lower())
            if w not in _STOPWORDS and w not in _EXTRA_STOP}


def _excerpt(body: str, words: set, limit: int = 300) -> str:
    """Ближайшая строка файла, где встречается слово запроса.

    Без этого keyword-хит отдавал только имя файла ('(keyword hit)') — в контекст
    попадало имя заметки без сути, что бесполезно агенту.
    """
    for line in body.splitlines():
        low = line.lower()
        if any(w in low for w in words):
            return line.strip().lstrip('#').strip()[:limit]
    return ''


def keyword_search(query: str, *, limit: int = 5, thread: str = '', chat_id: str = '',
                   min_score: float = _KEYWORD_MIN_SCORE,
                   min_overlap_words: int = 1) -> List[Dict[str, Any]]:
    """Keyword search over vault .md files (vault-first grep equivalent).

    Скандит Resources/Projects/Areas/Archives/Sessions; ранжирует по IDF.
    Thread filter applies ONLY to Archives/Sessions files (shared notes always pass).
    """
    vault = Path(DEFAULT_VAULT_PATH)
    if not vault.exists():
        return []
    q_words = _query_words(query)
    if not q_words:
        return []
    out = []
    df: Dict[str, int] = {}      # документная частота по ВСЕМ просканированным файлам
    n_docs = 0
    dirs = [vault / 'Resources', vault / 'Projects', vault / 'Areas', vault / 'Archives' / 'Sessions']
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob('*.md')):
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            # session file thread filter (frontmatter)
            thr, chid = '', ''
            m = re.match(r'^---\n(.*?)\n---', text[:600], re.S)
            if m:
                mm = re.search(r'^thread:\s*"?([^"\n]*)', m.group(1), re.M)
                thr = mm.group(1).strip() if mm else ''
                mm = re.search(r'^chat_id:\s*"?([^"\n]*)', m.group(1), re.M)
                chid = mm.group(1).strip() if mm else ''
            if (thread or chat_id) and 'Archives/Sessions' in str(p):
                if thread and thr and thr != thread:
                    continue
                if chat_id and chid and chid != chat_id:
                    continue
            body = text.lower()
            body_words = set(_TOKEN_RE.findall(body))
            for w in q_words:
                if w in body_words:
                    df[w] = df.get(w, 0) + 1
            n_docs += 1
            overlap = q_words & body_words
            if not overlap:
                continue
            out.append({'file_path': str(p), 'name': p.stem, 'overlap': overlap,
                        'text': _excerpt(body, overlap), 'thread': thr})

    if not out or not n_docs:
        return []
    # IDF по всем заметкам vault: слово в каждом файле весит ~0.
    # Слова, которых нет в корпусе вообще (df=0), из знаменателя убираем:
    # иначе запрос «векторная индексация vault» не находит ничего — 2 из 4 слов
    # не встречаются нигде и обнуляют оценку единственного реального совпадения.
    idf = {w: math.log((n_docs + 1) / (df[w] + 0.5)) for w in q_words if df.get(w)}
    if not idf:
        return []
    # Неинформативные слова (везде) выбрасываем — иначе запрос из общих слов
    # («это самое») даёт score 1.00 любому файлу.
    idf = {w: v for w, v in idf.items() if v > _KEYWORD_MIN_IDF}
    if not idf:
        return []
    total = sum(idf.values())
    for r in out:
        r['overlap'] = r['overlap'] & set(idf)
        got = sum(idf[w] for w in r['overlap'])
        r['score'] = got / total
    # min_overlap_words: одинокое совпадение даже по редкому слову — часто случайность
    # («exit» встретился один раз в файле про Nous Portal и дал score 0.63 запросу про
    # «background process exited»). Требование >=2 информативных слов отсекает такие
    # одиночные случайные совпадения, не трогая тематические (там совпадают 2+ слова).
    hits = [r for r in out if r['score'] >= min_score and len(r['overlap']) >= min_overlap_words]
    hits.sort(key=lambda x: (-x['score'], x['name']))
    return hits[:limit]


def rrf_fuse(vec_results: List[Dict], kw_results: List[Dict], k: int = 60, top: int = 5) -> List[Dict]:
    """Reciprocal Rank Fusion of vector + keyword results (by file)."""
    scores: Dict[str, float] = {}
    info: Dict[str, Dict] = {}
    for rank, r in enumerate(vec_results):
        key = r['file_path']
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        info.setdefault(key, {'name': r['name'], 'text': r['text'], 'distance': r['distance'],
                              'thread': r.get('thread', ''), 'sources': []})
        if 'vector' not in info[key]['sources']:
            info[key]['sources'].append('vector')
    for rank, r in enumerate(kw_results):
        key = r['file_path']
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key in info:
            if 'keyword' not in info[key]['sources']:
                info[key]['sources'].append('keyword')
        else:
            info[key] = {'name': r['name'], 'text': '(keyword hit)', 'distance': None,
                         'thread': r.get('thread', ''), 'sources': ['keyword']}
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top]
    out = []
    for key, s in ranked:
        d = dict(info[key])
        d['file_path'] = key
        d['rrf_score'] = round(s, 6)
        out.append(d)
    return out