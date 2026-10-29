# Obsidian Memory Provider for Hermes Agent

A pluggable [Hermes Agent](https://github.com/NousResearch/hermes-agent) memory provider that stores durable facts as plain Markdown files inside an Obsidian vault. No cloud, no API keys, no vector database service — the facts are files you can read, edit, and grep.

## What it actually does

- **Facts as Markdown.** Each fact is one `.md` file with YAML frontmatter under `Brain/facts/`. Readable, diffable, versionable by git.
- **Semantic recall over the whole vault.** A [sqlite-vec](https://github.com/asg017/sqlite-vec) index provides local vector search (bge-m3, 1024-dim, computed by a local Ollama). Combined with a keyword grep over Resources/Projects/Areas via reciprocal rank fusion.
- **Thread-scoped automatic recall.** Prefetch only injects chunks belonging to the current session thread; shared notes always pass. So automatic recall never leaks another conversation's noise.
- **Thread-agnostic conscious search.** `fact_store search` deliberately searches everything — if you ask "what did we decide about X", the answer includes other threads.
- **A `fact_store` tool.** `add` / `search` / `probe` / `list` / `update` / `remove`.

## Deliberate design decision: no auto-extraction

`auto_extract` is **off by default** and should stay off unless you know you want it.

There is already a nightly pipeline in my vault that extracts facts from session logs into the vault. A second per-turn extractor running inside the agent would duplicate every fact into two places with two slightly different wordings, and the agent would then recall the duplicate. Two extractors is worse than one slow extractor, because the agent cannot tell which copy is authoritative.

So by default the only writer is the explicit `fact_store add` call.

## Architecture

This is one product with three stages, not a plugin plus some loose scripts:

```
  CAPTURE                     INDEX                      SERVE
  ───────                     ─────                      ─────
  auto-capture-obsidian.py    vault_vector_index.py      obsidian_memory/  ← the plugin
  daily-note.py               reads vault .md            reads vault_vectors.db
  obsidian-weekly-review.py    writes $HERMES_HOME/       reads $HERMES_HOME/state.db
  backfill-knowledge-tags.py  vault_vectors.db           serves facts to the agent
        │                            │                          │
        └──── writes .md ────────────┘                          │
             into the Obsidian vault ───────────────────────────┘
```

The plugin never writes to the vault. Capture fills it, the indexer turns it into
vectors, the plugin serves it. `fact_store add` writes both — a markdown file in
`Brain/facts/` *and* the searchable store.

That is also why `auto_extract` is off by default: the capture stage is already the
single extractor for this system.

## Layout

| Path | What |
|---|---|
| `obsidian_memory/` (`__init__.py`, `store.py`, `vault_index.py`) | the memory provider plugin |
| `pipeline/` | the cron-driven capture stage — runs whether or not the agent does |
| `pipeline/vault_vector_index.py` | builds the vector index; **part of this product, not an external tool** |

## Requirements

| Requirement | Notes |
|---|---|
| Hermes Agent | plugin system + `memory.provider` support |
| `sqlite_vec` | vendored in `_vendor/sqlite_vec/` (v0.1.9, Apache-2.0) |
| Ollama with `bge-m3` | only for building the vector index; recall degrades to keyword-only if unavailable |

The vendored `vec0.so` is an x86-64 **Linux** shared object. On other platforms, install `sqlite-vec` from pip and delete `_vendor/` — the loader falls back to a normal import automatically.

No embeddings are ever sent to an API. There is no fallback path to a remote provider.

## Install

```bash
git clone <this-repo> ~/.hermes/plugins/obsidian_memory
```

Point it at your vault:

```bash
hermes config set plugins.obsidian-memory.vault_path ~/obsidian-vault
```

Then **activate it**. This is the part that surprises people: memory providers are
`kind: exclusive`, so `plugins.enabled` does *not* activate one. The switch is:

```bash
hermes config set memory.provider obsidian_memory
```

The value must equal the **directory name**, not the `name:` field in `plugin.yaml`.

Restart the gateway:

```bash
hermes gateway restart
```

## Recall: queue, not a timeout

Recall does not depend on the embedder winning the race. Each turn puts its query
into a queue and starts the calculation in the background; we wait `fresh_wait`
(5s) for it, and if the vector misses the budget the query **stays in the queue**
and is delivered later — turn 10 catches up turn 1, and when the machine drains,
everything queued goes out at once. Waiting is never removed: under light load the
vector still answers turn by turn.

Do not raise `prefetch_fresh_wait` past 5s. Hermes caps every external provider:

```python
# agent/memory_manager.py
_EXTERNAL_PREFETCH_TIMEOUT_S = 8.0
...
existing = self._external_prefetch_threads.get(provider.name)
if existing is not None and existing.is_alive():
    return ""   # provider skipped entirely until the stuck call returns
```

A longer wait leaves the thread alive and drops the provider from *all* subsequent
turns — raising the timeout makes recall worse, not better.

### Emergency keyword mode

Fires when this turn got **no fresh semantics** AND either the queue is **6 turns
deep**, the oldest stuck turn is **180s old**, or **6 turns in a row** delivered
nothing. It is not a per-turn fallback: with the queue working, waiting is
cheaper than paying for a degraded answer.

Two details that turned out to matter, both found by starving the real embedder
rather than by reasoning about it:

- **Starvation counts turns, not queue entries.** In a conversation where queries
  repeat ("да", "ок", "а в это самое") there is one queue entry, so depth never
  grows and a depth-only threshold is unreachable — while memory is silent.
  `_starved_turns` counts undelivered turns and is part of the trigger.
- **Keyword is recomputed per turn and never cached as context.** It used to land
  in the "previously delivered" ring, and every later turn got the *same* block:
  a question about video reports got the Carrier result. The ring now takes only
  real semantics, so each turn is answered for its own query.

A repeated query also waits for its in-flight computation instead of returning
empty instantly — that silent zero-cost miss was the same bug in another guise.

Each firing appends to `$HERMES_HOME/logs/obsidian-memory-emergency.jsonl` —
one record per incident, not per turn:

```json
{"ts": "...", "session": "...", "thread": "11003", "query": "...",
 "queue_depth": 5, "oldest_age_s": 30.0, "depth_limit": 6, "age_limit_s": 180.0,
 "starved_turns": 6, "swap_free_mb": 563}
```

`swap_free_mb` is there so incident analysis never guesses: on this host the
cause is almost always exhausted swap, which pushes bge-m3 (CPU, no VRAM) from
1s to 60-105s per embedding.

Deliberately a file, not `fact_store` and not a message: the incident happens in
*some other* thread, which must continue transparently and must not be told about
it. Read the log in the memory thread.

### Keyword ranking

`keyword_search` scores by IDF over all 718 vault notes, drops stopwords, ignores
query terms absent from the corpus, and returns real excerpts instead of
`(keyword hit)`. Without IDF a single shared word scored 0.50 and pulled in
unrelated notes; with it a top hit is the right note and junk queries score 0.

## Deploying the pipeline

Cron jobs reference these scripts by bare name (`vault_vector_index.py`) and the
scheduler's lifecycle guard **resolves the path and refuses anything that lands
outside `$HERMES_HOME/scripts/`**. A symlink pointing into `plugins/` resolves
outward and gets blocked:

```
Blocked: script path resolves outside the scripts directory
(/opt/data/scripts): 'vault_vector_index.py'
```

So the repo is the source of truth, but the deployed copies are real files:

```bash
python pipeline/deploy.py           # copy pipeline/ → $HERMES_HOME/scripts/
python pipeline/deploy.py --check   # read-only drift check, exit 1 on mismatch
```

Run `--check` after editing anything in `pipeline/`; cron uses the deployed copy,
not the repo.

## Building the vector index

The index is built out-of-band, not by the plugin at recall time:

```bash
python pipeline/vault_vector_index.py            # incremental run
python pipeline/vault_vector_index.py --full     # rebuild from scratch
python pipeline/vault_vector_index.py --search "your query"   # test recall
```

It writes `$HERMES_HOME/vault_vectors.db` (default `~/.hermes/vault_vectors.db`).
Indexes are incremental and keyed by **content hash, not mtime** — some capture
passes rewrite files in place, so an mtime-based check re-embeds unchanged content.

Chunking is ~2000 chars with 200 overlap, embedding is `bge-m3` (1024-dim) via a local
Ollama at `http://localhost:11434`. Batches are 4: a batch of 8 pushed past the 300s
embed timeout on an idle-old CPU and killed the whole run, so 4 plus retry-with-split
is the working setting.

Recall degrades gracefully — without the index, prefetch returns keyword hits only.

On this host (8 cores, bge-m3 on CPU, no VRAM) a warm embed is ~8s and the first one
after a keep_alive expiry is ~105s. `prefetch_fresh_wait` defaults to 5s, so a cold
model means prefetch returns empty and the result lands a turn later — that is the
designed fallback, not a broken index. Check `curl localhost:11434/api/ps` before
concluding that `0 chars` means a failed index.

## The capture pipeline

These run from cron, independently of whether the agent is up:

| Script | Job |
|---|---|
| `auto-capture-obsidian.py` | pulls recent Hermes sessions into `Archives/Sessions`, daily notes into `Daily` |
| `daily-note.py` | assembles the daily note from cron output |
| `daily-note-fallback.py` | worker-rodzhem: if the daily-note agent job failed, produce a deterministic report instead |
| `obsidian-weekly-review.py` | weekly vault review |
| `backfill-knowledge-tags.py` | backfills tags on existing Knowledge notes |

All paths come from the environment, with defaults that resolve on any host:

| Variable | Default |
|---|---|
| `OBSIDIAN_VAULT` | `~/obsidian-vault` |
| `HERMES_HOME` | `~/.hermes` |
| `VAULT_VECTORS_DB` | `$HERMES_HOME/vault_vectors.db` |
| `HERMES_STATE_DB` | `$HERMES_HOME/state.db` |
| `HERMES_CONFIG` | `$HERMES_HOME/config.yaml` |
| `OBSIDIAN_WEEKLY_STATE` | `$HERMES_HOME/scripts/.obsidian-weekly-state.json` |
| `OBSIDIAN_CLI` | `$HERMES_HOME/skills/productivity/obsidian-vault/scripts/obsidian-cli.py` |

`pipeline/daily-note-fallback.py` locates `daily-note.py` relative to its own file, and
`backfill-knowledge-tags.py` imports `obsidian-weekly-review.py` the same way — so the
`pipeline/` directory works as a unit from any checkout location.

## Configuration

Under `plugins.obsidian-memory` in `config.yaml`:

| Key | Default | Meaning |
|---|---|---|
| `vault_path` | `~/obsidian-vault` | Path to the Obsidian vault |
| `auto_extract` | `false` | Per-turn fact extraction. See above before enabling. |
| `prefetch_top` | `5` | How many chunks to inject per turn |
| `prefetch_fresh_wait` | `5.0` | Seconds to wait for a fresh result before falling back to the previous turn's recall. Must stay under the manager's ~8s budget. |
| `dedup_threshold` | `0.5` | Jaccard threshold for short-fact dedup |

`$HERMES_HOME` (default `~/.hermes`) locates `state.db` and `vault_vectors.db`.

## Telemetry

None. The plugin makes no outbound requests except to your local Ollama.

## License

The plugin code is mine; do what you want with it. The vendored
`sqlite_vec/vec0.so` is [sqlite-vec](https://github.com/asg017/sqlite-vec) v0.1.9,
Apache-2.0, © asg017 — see `_vendor/sqlite_vec/`.
