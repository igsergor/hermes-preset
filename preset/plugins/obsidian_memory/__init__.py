"""Obsidian Memory Provider — vault-first memory over the real Obsidian vault.

Architecture (agreed 20-23.09.26):
- Vault = single source of truth (auto-capture + weekly distillation already write there)
- Vector layer: sqlite-vec index built by scripts/vault_vector_index.py (local bge-m3 ONLY,
  decision 20.09.26 — no API fallback)
- This plugin: prefetch = RRF fusion of vector + keyword search over the vault;
  fact_store = durable facts with Jaccard dedup;
  session-note prefetch is NOT thread-filtered since 25.09.26 (Igor's decision):
  all relevant chunks surface regardless of thread; thread/chat_id metadata kept
  for provenance only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider, spawn_context_thread
from tools.registry import tool_error
from utils import is_truthy_value
from .store import MarkdownFactStore
from .vault_index import VaultVectorIndex, keyword_search, rrf_fuse

logger = logging.getLogger(__name__)

PROVIDER_NAME = "obsidian_memory"
CONFIG_KEY = "plugins.obsidian-memory"

HERMES_HOME_DIR = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
STATE_DB = HERMES_HOME_DIR / "state.db"
DEFAULT_VAULT_PATH = str(Path("~/obsidian-vault").expanduser())

FACT_STORE_SCHEMA = {
    "name": "fact_store",
    "description": (
        "Durable facts about the user, stored as markdown in the Obsidian vault.\n\n"
        "ACTIONS:\n"
        "• add — Store a durable fact the user expects you to remember.\n"
        "• search — Lookup across the WHOLE vault (facts + Knowledge + sessions, all threads).\n"
        "• probe — All facts about a person/thing (entity).\n"
        "• list — Recent facts.\n"
        "• update — Edit a fact.\n"
        "• remove — Delete a fact by id.\n\n"
        "IMPORTANT: Before answering questions about the user, ALWAYS probe or search first.\n"
        "Note: search is thread-agnostic (searches everything) — use it when the user asks "
        "what was discussed/done before, even if it was in another chat thread."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "search", "probe", "list", "update", "remove"],
            },
            "content": {"type": "string", "description": "Fact content (required for 'add'/'update')."},
            "query": {"type": "string", "description": "Search query (required for 'search')."},
            "entity": {"type": "string", "description": "Entity name for 'probe'."},
            "category": {"type": "string", "enum": ["user_pref", "project", "tool", "general"]},
            "tags": {"type": "string", "description": "Comma-separated tags."},
            "trust_delta": {"type": "number", "description": "Trust adjustment for 'update'."},
            "limit": {"type": "integer", "description": "Max results (default: 10)."},
        },
        "required": ["action"],
    },
}


def _load_plugin_config() -> dict:
    try:
        from hermes_cli.config import load_config_readonly
        from hermes_cli.config import cfg_get as _cg
        cfg = load_config_readonly()
        # cfg_get принимает ключи ОТДЕЛЬНЫМИ аргументами и ищет буквальный ключ.
        # Раньше сюда передавался CONFIG_KEY ("plugins.obsidian-memory") одной
        # строкой — такого ключа нет на верхнем уровне, и конфиг плагина из
        # config.yaml не читался НИКОГДА: все значения молча брались из дефолтов.
        return _cg(cfg, *CONFIG_KEY.split("."), default={}) or {}
    except Exception as e:
        logger.debug("obsidian-memory config load failed: %s", e)
        return {}


def _swap_free_mb() -> Optional[int]:
    """Свободный своп в МБ (None, если не читается) — главная причина голода.

    Пишется в журнал инцидента, чтобы разбор не гадал: при голоде почти всегда
    забит именно своп, и bge-m3 на CPU уходит с 1с на 60-105с.
    """
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("SwapFree:"):
                    return int(line.split()[1]) // 1024
    except Exception:  # noqa: BLE001
        pass
    return None


def _lookup_session_thread(session_id: str) -> tuple:
    """Resolve (chat_id, thread_id) for a session id from state.db (read-only)."""
    if not session_id:
        return ('', '')
    try:
        conn = sqlite3.connect(f'file:{STATE_DB}?mode=ro', uri=True, timeout=5)
        row = conn.execute(
            'SELECT chat_id, thread_id FROM sessions WHERE id=?', (session_id,)).fetchone()
        conn.close()
        if row:
            return (str(row[0] or ''), str(row[1] or ''))
    except Exception as e:
        logger.debug('session thread lookup failed: %s', e)
    return ('', '')


# LLM extraction via OmniRoute combo (memory-extract: OR↔nv cascade, decision 21.09.26)
EXTRACT_SYSTEM = (
    "Ты — извлекатель стойких фактов о пользователе из диалога. Извлекай ТОЛЬКО durable "
    "факты, которые пользователь ожидал бы запомнить: предпочтения, инфраструктуру, "
    "принятые решения, проекты, личную информацию (тех. стек, сеть, устройства, привычки). "
    "НЕ извлекай разовые задачи, отладку, приветствия. НЕ выдумывай. Если фактов нет — "
    "верни пустой массив.\n"
    "Верни ТОЛЬКО JSON массив (без markdown-обёртки):\n"
    '[{"fact": "<текст факта>", "category": "user_pref|project|tool|general", '
    '"entities": ["<сущность>", ...], "tags": ["<тег>", ...]}]'
)


def _safe_json(text: Optional[str]) -> list:
    if not text:
        return []
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for k in ("facts", "result", "output"):
                if k in data and isinstance(data[k], list):
                    return data[k]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            if isinstance(d, list):
                return d
        except Exception:
            pass
    logger.debug("Unparseable LLM extract output: %.300s", text)
    return []


def _llm_extract(dialog: str) -> list:
    """Извлечение фактов через OpenAI-совместимый endpoint.

    По умолчанию выключено: в публичном пресете у пользователя нет локального
    шлюза, а молча стучаться в несуществующий порт — это спам в логах.
    Включается переменными окружения:
        OBSIDIAN_EXTRACT_BASE_URL=https://api.openai.com/v1
        OBSIDIAN_EXTRACT_MODEL=gpt-4o-mini
        OBSIDIAN_EXTRACT_API_KEY=...
    """
    base = os.environ.get("OBSIDIAN_EXTRACT_BASE_URL", "").rstrip("/")
    if not base:
        logger.debug("obsidian-memory: auto-extract отключён (нет OBSIDIAN_EXTRACT_BASE_URL)")
        return []
    try:
        import requests
        model = os.environ.get("OBSIDIAN_EXTRACT_MODEL", "memory-extract")
        api_key = os.environ.get("OBSIDIAN_EXTRACT_API_KEY", "")
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": EXTRACT_SYSTEM},
                    {"role": "user", "content": dialog},
                ],
                "temperature": 0.2,
                "max_tokens": 1500,
                "stream": False,
            },
            timeout=300,
        )
        resp.raise_for_status()
        return _safe_json(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        logger.warning("obsidian-memory LLM extract failed: %s", e)
        return []


class ObsidianMemoryProvider(MemoryProvider):
    """Vault-first memory: prefetch over vault index + fact store."""

    def __init__(self, config: Optional[dict] = None):
        self._config = config if config is not None else _load_plugin_config()
        self._store: Optional[MarkdownFactStore] = None
        self._index: Optional[VaultVectorIndex] = None
        self._session_id = ""
        self._session_thread = ""
        self._session_chat_id = ""
        self._auto_extract = is_truthy_value(self._config.get("auto_extract", False))
        self._sync_lock = threading.Lock()
        self._sync_thread: Optional[threading.Thread] = None
        self._last_prefetch: Optional[str] = None
        # --- hybrid prefetch state (29.09.26, решение Игоря) ---
        self._pf_lock = threading.Lock()
        # Очередь незакрытых ходов (04.10.26): каждый ход копит свой результат,
        # отдаём всё накопленное сразу. Раньше self._results[query] перезаписывался
        # по одному результату на запрос, и кольцо «прошлый доставленный» не
        # наполнялось: на холодной модели успешного prefetch не бывает вовсе.
        self._queue: List[Dict[str, Any]] = []
        # Пороги читаются из конфига в момент использования, а не в __init__:
        # иначе правка config.yaml не подхватывалась до пересоздания провайдера.
        self._emergency_active = False
        # Ходы подряд без отдачи (04.10.26): ловит голод в разговоре с повторами,
        # где глубина очереди не растёт.
        self._starved_turns = 0
        self._last_delivered = ""
        self._last_delivered_fresh = True

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def get_config_schema(self):
        return [
            {"key": "vault_path", "description": "Obsidian vault path", "default": DEFAULT_VAULT_PATH},
            {"key": "auto_extract", "description": "Auto-extract facts per turn (DISABLED by default: vault pipeline already extracts — decision 20.09.26). Only manual fact_store add is active.", "default": "false", "choices": ["false", "true"]},
            {"key": "prefetch_top", "description": "Prefetch result count (top-N)", "default": "5", "choices": ["3", "4", "5"]},
            {"key": "prefetch_fresh_wait", "description": "Seconds to wait for this turn's fresh result before falling back to the queue (must stay < 8s Hermes manager budget)", "default": "5.0"},
            {"key": "prefetch_queue_max", "description": "Max undelivered turns kept in the recall queue", "default": "24"},
            {"key": "prefetch_emergency_depth", "description": "Emergency keyword mode when this many turns are stuck undelivered", "default": "6"},
            {"key": "prefetch_emergency_age", "description": "Emergency keyword mode when the oldest stuck turn is this many seconds old", "default": "180.0"},
            {"key": "dedup_threshold", "description": "Jaccard dedup threshold", "default": "0.5"},
        ]

    def save_config(self, values, hermes_home):
        from hermes_cli.config import save_config
        clean = {k: v for k, v in values.items() if v not in (None, "")}
        save_config({"plugins": {"obsidian-memory": clean}}, merge_existing=True)

    def initialize(self, session_id: str, **kwargs) -> None:
        vault_path = self._config.get("vault_path") or DEFAULT_VAULT_PATH
        self._session_id = session_id
        try:
            self._session_chat_id, self._session_thread = _lookup_session_thread(session_id)
        except Exception:
            self._session_chat_id, self._session_thread = ("", "")

        self._store = MarkdownFactStore(
            vault_path=vault_path,
            default_trust=float(self._config.get("default_trust", 0.5)),
            min_trust=float(self._config.get("min_trust", 0.3)),
        )
        try:
            self._index = VaultVectorIndex()
        except Exception as e:
            logger.warning("vault index unavailable: %s", e)
            self._index = None

    def system_prompt_block(self) -> str:
        total = self._store.count_facts() if self._store else 0
        return (
            "## Obsidian Memory\n"
            f"Active. Vault indexed ({total} facts stored).\n"
            "fact_store gives durable facts + full-vault search (all threads)."
        )

    # ---------- Prefetch: RRF(vector + keyword), hybrid fresh/stale ----------

    def _compute(self, query: str, top: int) -> str:
        """Полный расчёт recall для запроса (без тред-фильтра, решение 25.09.26)."""
        vec = self._index.search(query, top=top) if self._index else []
        kw = keyword_search(query, limit=top)
        fused = rrf_fuse(vec, kw, top=top)
        if not fused:
            logger.info("obsidian-memory: prefetch query=%.60r thread=%s hits=0", query, self._session_thread)
            return ""
        lines = []
        for r in fused:
            src = "+".join(r["sources"])
            snippet = r["text"][:180].replace("\n", " ")
            lines.append(f"- [{src}] {r['name']}: {snippet}")
        logger.info("obsidian-memory: prefetch query=%.60r thread=%s hits=%d top_dist=%s",
                    query, self._session_thread, len(lines),
                    f"{fused[0]['distance']:.1f}" if fused[0].get('distance') is not None else "kw")
        return "## Vault recall\n" + "\n".join(lines)

    @staticmethod
    def _merge_recall(current: str, missed: str, cap: int) -> str:
        """Свежий recall + догон пропущенного хода: свежие строки первыми, без дублей, с cap."""
        cur = [l for l in current.splitlines() if l.startswith("- ")]
        old = [l for l in missed.splitlines() if l.startswith("- ")]
        seen, out = set(), []
        for l in cur + old:
            key = l.split(": ", 1)[-1][:60]
            if key in seen:
                continue
            seen.add(key)
            out.append(l)
            if len(out) >= cap:
                break
        if not out:
            return ""
        return "## Vault recall\n" + "\n".join(out)

    @classmethod
    def _merge_many(cls, blocks: List[str], cap: int) -> str:
        """Склейка нескольких блоков recall (очередь): свежие первыми, без дублей, с cap."""
        out = ""
        for b in blocks:
            if not b:
                continue
            out = cls._merge_recall(b, out, cap=cap) if out else b
        return out

    def _compute_keyword_only(self, query: str, top: int, min_score: float = 0.5) -> str:
        """Только keyword-ветка: ноль эмбеддингов, ~0.2с.

        Нужна как самодостаточный фолбэк: векторный путь на холодной модели занимает
        дольше всего бюджета prefetch, и тогда гибридный откат отдаёт пустоту —
        потому что наполнить его может только успешный prefetch, которого не бывает.
        Keyword идёт первым-делом и всегда успевает.

        09.10.26 (решение Игоря): аварийная выдача фильтруется по min_score —
        голод вектора доказывает только задержку, а не качество keyword-хитов.
        Технический мусор («background process exited») содержит настоящие слова
        и проходил с score 0.4-0.63 по случайным совпадениям («exit», «code»),
        попадая в контекст как мусорный блок. Легитимные темы дают >= 0.63,
        точные — 1.0. Ниже порога ход честно остаётся без памяти.
        """
        # 09.10.26: служебный лексикон системных сообщений Hermes (proc_..., exit code,
        # background process...) вычищается из запроса ДО keyword-поиска. Эти слова
        # повсюду в vault (сессии хранят те же системные сообщения), IDF их не гасит:
        # запрос "[IMPORTANT] background process exited code" давал score 0.91 на
        # заметке про Nous Portal по случайным совпадениям 3 служебных слов.
        junk_re = re.compile(
            r"\b(?:proc_[a-z0-9]{6,}|important|background|exit(?:ed)?|cronjob|"
            r"response|completed|failed|stderr|stdout|proc(?:ess)?|code)\b", re.I)
        cleaned = junk_re.sub(" ", query)
        if not cleaned.strip():
            return ""
        # min_overlap_words=2: аварийная выдача идёт прямо в контекст, одиночное
        # случайное совпадение по одному редкому слову туда не пускаем.
        kw = keyword_search(cleaned, limit=top, min_score=min_score, min_overlap_words=2)
        if not kw:
            return ""
        lines = []
        for r in kw:
            src = "+".join(r.get("sources") or ["keyword"])
            snippet = (r.get("text") or "")[:180].replace("\n", " ")
            lines.append(f"- [{src}] {r.get('name', '')}: {snippet}")
        if not lines:
            return ""
        return "## Vault recall\n" + "\n".join(lines)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Очередь recall (04.10.26, решение Игоря).

        Каждый ход кладёт свой запрос в очередь и запускает расчёт в фоне. Ждём
        fresh_wait (5с) — если вектор успел, отдаём его СРАЗУ, ход в ход. Если не
        успел, запрос остаётся в очереди и закрывается позже: как только он
        посчитан, отдаём всё накопленное разом (свежие строки первыми, без дублей).

        Аварийный keyword включается не каждый раз, а по порогу: когда очередь
        копит дольше emergency_age секунд ИЛИ глубже emergency_depth ходов и
        семантика не отдала ничего. Каждое срабатывание пишется в журнал инцидентов.
        """
        if not query:
            return ""
        try:
            top = int(self._config.get("prefetch_top", 5))
            queue_max = int(self._config.get("prefetch_queue_max", 24))
            emerg_depth = int(self._config.get("prefetch_emergency_depth", 6))
            emerg_age = float(self._config.get("prefetch_emergency_age", 180.0))

            def _compute_async(entry: Dict[str, Any]) -> None:
                try:
                    entry["result"] = self._compute(entry["query"], top)
                    entry["ok"] = True
                except Exception as e:  # noqa: BLE001
                    entry["result"] = ""
                    entry["ok"] = False
                    logger.debug("obsidian compute failed: %s", e)
                entry["done"] = True

            thread: Optional[threading.Thread] = None
            with self._pf_lock:
                entry = next((e for e in self._queue if e["query"] == query), None)
                if entry is None:
                    entry = {"query": query, "ts": time.time(), "result": "",
                             "done": False, "ok": False, "delivered": False}
                    self._queue.append(entry)
                    while len(self._queue) > queue_max:
                        self._queue.pop(0)
                    entry["thread"] = threading.Thread(
                        target=_compute_async, args=(entry,),
                        name="obsidian-prefetch", daemon=True)
                    thread = entry["thread"]
                    thread.start()
                else:
                    # Повторный ход с тем же запросом. Раньше он уходил за 0.00с,
                    # не дожидаясь уже летящего расчёта и не попадая в очередь:
                    # при голоде именно повторы («да», «ок», «а в это самое»)
                    # молча теряли память, а глубина очереди не росла — порог
                    # аварийного режима становился недостижимым.
                    th = entry.get("thread")
                    if not entry["done"] and th is not None and th.is_alive():
                        thread = th

            # Ждём только свежий результат ЭТОГО хода — bounded, 5с по умолчанию.
            if thread is not None:
                thread.join(float(self._config.get("prefetch_fresh_wait", 5.0)))

            # 09.10.26 (решение Игоря): различаем «вектор ЗАВИС» и «вектор ЧЕСТНО
            # ответил пусто». Если свежий расчёт ЭТОГО хода успел (done) — вектор
            # не перегружен, его пустой результат = в vault нет релевантного ходу.
            # Аварийный keyword тогда неуместен: он не вытащит то, чего нет, а
            # мусорный блок (совпадения по «process», «code») только засорит контекст.
            fresh_entry = None
            with self._pf_lock:
                fresh_entry = next((e for e in self._queue if e["query"] == query), None)
            fresh_computed = bool(fresh_entry and fresh_entry.get("done"))
            fresh_empty = fresh_computed and fresh_entry.get("ok") and not (fresh_entry.get("result") or "").strip()

            with self._pf_lock:
                # Достаём НЕПУСТЫЕ результаты — это догон.
                ready = [e for e in self._queue if e["done"] and not e["delivered"] and e["result"]]
                for e in ready:
                    e["delivered"] = True
                # 09.10.26 (по уму, решение Игоря): очередь = только то, что вектор
                # ЕЩЁ НЕ СКАЗАЛ. Посчитавшаяся пустая запись — это готовый ответ
                # «в vault нет релевантного», а не голод: она уходит из очереди,
                # иначе её возраст стареет впустую и включает аварию раньше срока
                # на последующих зависших ходах. Висят расчёты — глубина/возраст
                # растут сами (порог по-прежнему достижим); вектор работает и
                # отвечает пусто — голодать незачем. Упавшие (ok=False) остаются:
                # не смог ответить = не смог, это настоящий голод.
                self._queue = [e for e in self._queue if not e["delivered"]
                               and not (e["done"] and e.get("ok") and not (e["result"] or "").strip())]
                oldest_age = (time.time() - self._queue[0]["ts"]) if self._queue else 0.0
                depth = len(self._queue)
                if not self._queue:
                    self._emergency_active = False

            blocks = [e["result"] for e in ready if e["result"]]
            fresh = self._merge_many(blocks, cap=top * 2)
            out = fresh
            out_fresh = bool(out)

            # Голод считается по СВЕЖЕЙ семантике этого хода, а не по итоговому
            # out. Иначе аварийный keyword залипал в _last_delivered, и все
            # следующие ходы получали ОДИН И ТОТ ЖЕ блок вместо ответа на свой
            # запрос: ход про видео отдавал операторовскую выдачу.
            with self._pf_lock:
                # Честная пустота свежего вектора — НЕ голод: счётчик сбрасывается,
                # иначе пустые cron-ходы копили голод и включали аварию на живом месте.
                if fresh or fresh_empty:
                    self._starved_turns = 0
                    self._emergency_active = False
                else:
                    self._starved_turns += 1
                starved_turns = self._starved_turns

            too_deep = depth >= emerg_depth or starved_turns >= emerg_depth
            too_old = oldest_age >= emerg_age
            # Вектор ответил пусто на СВЕЖИЙ расчёт этого хода => в памяти нет
            # релевантного, ждать/аварийить нечего. Таймер может тикать сколько
            # угодно — это не голод, а честная пустота. Порог не срабатывает.
            starved = not fresh and not fresh_empty
            if starved and (too_deep or too_old):
                # Порог пройден, а кроме keyword нечего отдать. Keyword считается
                # на КАЖДЫЙ ход заново (0.2с) — он дешёвый и должен отвечать на
                # текущий запрос, а не повторять прошлый.
                try:
                    kw_block = self._compute_keyword_only(query, top)
                except Exception as e:  # noqa: BLE001
                    kw_block = ""
                    logger.debug("keyword emergency failed: %s", e)
                # 09.10.26 (решение Игоря): порог по возрасту/глубине доказывает
                # только голод ВЕКТОРА, а не то, что в vault есть что отдать.
                # Если качественных keyword-хитов нет (всё ниже min_score),
                # в памяти просто нет релевантного этому ходу — мусор не отдаём,
                # аварийное состояние НЕ включаем, журнал НЕ пишем. Голод
                # продолжается без аварии: вектор рано или поздно даст честный
                # «пусто», и это правильный ответ.
                if kw_block:
                    out = self._merge_recall(out, kw_block, cap=top * 2) if out else kw_block
                    if not self._emergency_active:
                        self._emergency_active = True
                        self._log_emergency(query, depth, oldest_age, emerg_depth, emerg_age,
                                            starved_turns)
                    out_fresh = False
            elif not out:
                # Ничего не готово и порог не пройден — отдаём прошлое
                # доставленное, чтобы контекст не вырождался в пустоту.
                out, out_fresh = self._last_delivered, False

            with self._pf_lock:
                # В кольцо «прошлый доставленный» идёт только настоящая семантика:
                # аварийный keyword — ответ на конкретный ход, а не контекст.
                if out and out_fresh:
                    self._last_delivered = out
                    self._last_delivered_fresh = out_fresh
            self._last_prefetch = out or None
            return out
        except Exception as e:
            logger.debug("obsidian prefetch failed: %s", e)
            return ""

    def _log_emergency(self, query: str, depth: int, age: float,
                       depth_limit: int, age_limit: float,
                       starved_turns: int = 0) -> None:
        """Каждое срабатывание аварийного keyword — запись в журнал инцидентов.

        Файл вне тредов: авария случается в чужом треде, и туда ничего не пишем
        (тред должен продолжиться прозрачно). Агент читает журнал в треде про память.
        """
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session": self._session_id,
            "thread": self._session_thread,
            "chat_id": self._session_chat_id,
            "query": query[:120],
            "queue_depth": depth,
            "oldest_age_s": round(age, 1),
            "depth_limit": depth_limit,
            "age_limit_s": age_limit,
            "starved_turns": starved_turns,
            "swap_free_mb": _swap_free_mb(),
        }
        logger.warning("obsidian-memory EMERGENCY keyword fallback: %s", rec)
        try:
            path = HERMES_HOME_DIR / "logs" / "obsidian-memory-emergency.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            logger.debug("emergency log write failed: %s", e)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        pass  # inline prefetch is fast enough (warm embed ~1s)

    def recall_status(self):
        from agent.memory_provider import RecallStatus
        if not self._last_prefetch:
            return None
        n = self._last_prefetch.count("\n- ")
        # RecallStatus — датакласс (provider_label, count, glyph). Раньше здесь был
        # RecallStatus(text=...), TypeError глотался memory_manager как non-fatal,
        # и индикатор recall не показывался никогда. Аварийный режим виден по
        # logs/obsidian-memory-emergency.jsonl, а не через этот индикатор.
        return RecallStatus(provider_label="Obsidian", count=n)

    # ---------- Turn sync: LLM fact extraction ----------

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "",
                  messages: Optional[List[Dict]] = None, turn_author: Optional[Dict] = None) -> None:
        if not self._store or not self._auto_extract:
            return
        if not user_content or not assistant_content:
            return
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                return

        def _run():
            try:
                dialog = f"User: {user_content}\nAssistant: {assistant_content}"
                items = _llm_extract(dialog)
                threshold = float(self._config.get("dedup_threshold", 0.5))
                for item in items:
                    fact_text = str(item.get("fact", "")).strip()
                    if not fact_text or len(fact_text) < 8:
                        continue
                    category = item.get("category", "general")
                    if category not in self._store.CATEGORY_DIRS:
                        category = "general"
                    entities = item.get("entities", []) or []
                    tags = item.get("tags", []) or []
                    existing = self._store.fact_exists_similar(fact_text, threshold=threshold)
                    if existing:
                        logger.info("Dedup: %.40s ~ %s", fact_text, existing.id)
                        continue
                    self._store.add_fact(
                        fact_text, category=category, entities=entities, tags=tags,
                        session_id=self._session_id,
                    )
            except Exception as e:
                logger.warning("obsidian sync_turn extraction failed: %s", e)

        with self._sync_lock:
            self._sync_thread = spawn_context_thread(_run, name="obsidian-sync")
            self._sync_thread.start()

    def on_memory_write(self, action: str, target: str, content: str, metadata: Optional[Dict] = None) -> None:
        if not self._store or action != "add" or not content:
            return
        try:
            category = "user_pref" if target == "user" else "general"
            self._store.add_fact(content, category=category)
        except Exception as e:
            logger.debug("obsidian memory_write mirror failed: %s", e)

    # ---------- fact_store tool ----------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [FACT_STORE_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != "fact_store":
            return tool_error(f"Unknown tool: {tool_name}")
        if not self._store:
            return tool_error("Obsidian memory backend not initialized")

        action = args.get("action")
        try:
            if action == "add":
                content = args.get("content", "")
                if not content:
                    return tool_error("Missing required parameter: content")
                cat = args.get("category", "general")
                threshold = float(self._config.get("dedup_threshold", 0.5))
                existing = self._store.fact_exists_similar(content, threshold=threshold)
                if existing:
                    return json.dumps({"fact_id": existing.id, "status": "duplicate_skipped",
                                       "existing": existing.content[:200]})
                fact = self._store.add_fact(
                    content, category=cat,
                    tags=[t.strip() for t in (args.get("tags") or "").split(",") if t.strip()],
                    session_id=self._session_id,
                )
                logger.info("obsidian-memory: fact added id=%s cat=%s len=%d", fact.id, cat, len(content))
                return json.dumps({"fact_id": fact.id, "status": "added"})

            if action == "search":
                query = args.get("query", "")
                if not query:
                    return tool_error("Missing required parameter: query")
                limit = min(int(args.get("limit", 10)), 50)
                # Conscious search: NO thread filter — whole vault, all threads.
                facts = self._store.search_facts(query, limit=limit)
                vec = self._index.search(query, top=limit) if self._index else []
                kw = keyword_search(query, limit=limit)
                fused = rrf_fuse(vec, kw, top=limit)
                results = []
                for f in facts:
                    results.append({"source": "fact_store", "content": f["content"],
                                    "category": f["category"], "trust": f["trust"]})
                for r in fused:
                    snippet = r["text"][:300].replace("\n", " ") if r["text"] != "(keyword hit)" else r["name"]
                    results.append({"source": "vault", "name": r["name"], "snippet": snippet,
                                    "file": r["file_path"]})
                if not results:
                    return json.dumps({"result": "No relevant facts found."})
                return json.dumps({"results": results[:limit], "count": len(results)})

            if action == "probe":
                entity = args.get("entity", "")
                if not entity:
                    return tool_error("Missing required parameter: entity")
                limit = min(int(args.get("limit", 10)), 50)
                results = self._store.probe_entity(entity, limit=limit)
                if not results:
                    return json.dumps({"result": f"No facts about '{entity}'."})
                return json.dumps({"results": results, "count": len(results)})

            if action == "list":
                limit = min(int(args.get("limit", 20)), 100)
                results = self._store.list_facts(category=args.get("category"), limit=limit)
                return json.dumps({"results": results, "count": len(results)})

            if action == "update":
                fid = args.get("fact_id") or args.get("id")
                if not fid:
                    return tool_error("Missing required parameter: fact_id")
                fact = self._store.update_fact(
                    str(fid),
                    content=args.get("content"),
                    trust_delta=float(args.get("trust_delta", 0.0)),
                    category=args.get("category"),
                )
                if not fact:
                    return tool_error(f"Fact not found: {fid}")
                return json.dumps({"fact_id": fact.id, "status": "updated"})

            if action == "remove":
                fid = args.get("fact_id") or args.get("id")
                if not fid:
                    return tool_error("Missing required parameter: fact_id")
                ok = self._store.delete_fact(str(fid))
                if not ok:
                    return tool_error(f"Fact not found: {fid}")
                return json.dumps({"status": "deleted"})

            return tool_error(f"Unknown action: {action}")
        except Exception as e:
            logger.warning("fact_store action %s failed: %s", action, e)
            return tool_error(f"fact_store failed: {e}")

    def shutdown(self) -> None:
        self._store = None
        self._index = None


def register(ctx) -> None:
    config = _load_plugin_config()
    provider = ObsidianMemoryProvider(config=config)
    ctx.register_memory_provider(provider)