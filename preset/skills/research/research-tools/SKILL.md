---
name: research-tools
description: "Research tools: arXiv search, blog/RSS monitoring, prediction markets, web research, and knowledge base management. Use when searching academic papers, monitoring blogs, querying Polymarket, doing web research, or building a knowledge base."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, arxiv, blogwatcher, polymarket, web-research, knowledge-base, rss]
    related_skills: [research-tools]
---

# Research Tools

Academic research, blog monitoring, prediction markets, web research, and knowledge base management.

## Quick Decision Guide

| Task | Section |
|------|---------|
| Search academic papers | → §1 arXiv |
| Monitor blogs/RSS feeds | → §2 Blogwatcher |
| Query prediction markets | → §3 Polymarket |
| General web research | → §4 Web Research |
| Build/query knowledge base | → §5 LLM Wiki |

---

## §1 arXiv

Search and retrieve academic papers via arXiv's free REST API.

### Search

```bash
curl -s "https://export.arxiv.org/api/query?search_query=all:transformer+attention&max_results=5&sortBy=submittedDate&sortOrder=descending"
```

Parse with Python:
```python
import xml.etree.ElementTree as ET
ns = {'a': 'http://www.w3.org/2005/Atom'}
root = ET.parse(sys.stdin).getroot()
for entry in root.findall('a:entry', ns):
    title = entry.find('a:title', ns).text.strip()
    arxiv_id = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
    print(f"[{arxiv_id}] {title}")
```

### Query Syntax

| Prefix | Searches | Example |
|--------|----------|---------|
| `all:` | All fields | `all:transformer+attention` |
| `ti:` | Title | `ti:large+language+models` |
| `au:` | Author | `au:vaswani` |
| `cat:` | Category | `cat:cs.AI` |

Boolean: `AND` (default), `OR`, `ANDNOT`. Exact phrase: `ti:"chain+of+thought"`.

### Semantic Scholar (Citations & Recommendations)

```bash
# Paper details + citations
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.03300?fields=title,authors,citationCount"

# Who cited this paper
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.03300/citations?fields=title,year&limit=10"

# Recommendations
curl -s -X POST "https://api.semanticscholar.org/recommendations/v1/papers/" \
  -H "Content-Type: application/json" \
  -d '{"positivePaperIds": ["arXiv:2402.03300"], "negativePaperIds": []}'
```

### Reading Papers

```
# Abstract (fast)
web_extract(urls=["https://arxiv.org/abs/2402.03300"])

# Full paper
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])
```

### Common Categories

`cs.AI` (AI), `cs.CL` (NLP), `cs.CV` (Vision), `cs.LG` (ML), `cs.CR` (Security)

---

## §2 Blogwatcher

Monitor blogs and RSS/Atom feeds.

### Installation

```bash
go install github.com/JulienTant/blogwatcher-cli/cmd/blogwatcher-cli@latest
# or
curl -sL https://github.com/JulienTant/blogwatcher-cli/releases/latest/download/blogwatcher-cli_linux_amd64.tar.gz | tar xz -C /usr/local/bin blogwatcher-cli
```

### Commands

```bash
blogwatcher-cli add "Blog Name" https://example.com
blogwatcher-cli add "Blog" https://example.com --feed-url https://example.com/feed.xml
blogwatcher-cli scan
blogwatcher-cli articles
blogwatcher-cli read 1
blogwatcher-cli import subscriptions.opml
```

Database: `~/.blogwatcher-cli/blogwatcher-cli.db`

---

## §3 Polymarket

Query prediction market data from Polymarket's public REST APIs.

### Three APIs

1. **Gamma API** (`gamma-api.polymarket.com`) — Discovery, search
2. **CLOB API** (`clob.polymarket.com`) — Real-time prices, orderbooks
3. **Data API** (`data-api.polymarket.com`) — Trades, open interest

### Search

```bash
curl -s "https://gamma-api.polymarket.com/public-search?query=bitcoin&limit=10"
```

### Parse Results

Prices ARE probabilities: `0.65` = 65% likely. Fields `outcomePrices` and `clobTokenIds` are double-encoded JSON — parse with `json.loads()`.

### Limitations

- Read-only (no trading)
- Trading requires wallet-based crypto auth

---

## §4 Web Research

General-purpose web research with plan-first workflow.

### Workflow

1. **Draft research plan** — phases, sources, criteria
2. **Present for approval** — user reviews scope
3. **Execute only after approval**

### Search Engines

`web_search` and `web_extract` both work; they just need a configured backend.
Resolve order is `web.search_backend` / `web.extract_backend` (strict) →
`web.backend` → autodetect. A **stored value is taken as-is with no probe**, so a
stale name fails every call instead of falling back — that is exactly how
`web.backend: local` broke both tools (no such provider exists).

Current config (2026-10, verified live):

```yaml
web:
  backend: ''
  search_backend: 'brave-free'   # key in ~/.hermes/.env: BRAVE_SEARCH_API_KEY
  extract_backend: 'exa'         # keyless, no key required
```

Pitfalls:

- **`brave-free` is search-only** (`supports_extract=False`) — pointing
  `extract_backend` at it yields "is a search-only backend". Brave = search,
  Exa/Firecrawl/Parallel/Keenable/Tavily = extract; DDGS = search only.
- `provider_env()` reads `os.environ` **then** `~/.hermes/.env`, so a key added to
  `.env` is picked up without restarting the gateway.
- Edit `config.yaml` **textually** (`patch`, or diff against a backup). A full
  `yaml.safe_dump` rewrite produces a multi-thousand-line diff.
- Backend → provider class: `plugins/web/<name>/{plugin.yaml,provider.py}`;
  registry: `agent/web_search_registry.py`. `plugin.yaml` lists the exact
  `provides_web_providers` name (`brave_free` dir → `brave-free` id).
- Diagnose by resolving the backend rather than guessing:
  `_get_search_backend()`, `_get_extract_backend()` from `tools/web_tools.py`.

### When search engines block (403/429, CAPTCHA)

| Tier | Method |

| Tier | Method |
|------|--------|
| 1 | Direct URLs to known sites |
| 2 | Telegram previews (`t.me/s/<channel>`) |
| 3 | Browser for JS-rendered sites |
| 4 | `execute_code` with Python parsing |

### Video/YouTube Content Extraction

For video metadata, transcripts, descriptions, and comments — see **[references/video-research.md](references/video-research.md)**.

Quick tier list:
1. **r.jina.ai** — `curl "https://r.jina.ai/http://youtube.com/watch?v=ID"` (full markdown extraction)
2. **YouTube oEmbed API** — `curl "https://www.youtube.com/oembed?url=...&format=json"` (basic metadata only)
3. **Invidious instances** — unreliable, check current list
4. **yt-dlp** — needs cookies for bot-protected content, rate-limited
5. **Browser** — consent walls, Anubis challenges, slow

### Pitfalls

- Avoid complex shell regex in `terminal()` — use `execute_code` with Python `re`
- Subagents for web research often time out (600s limit)
- `web_extract` caps output and writes the full page to
  `~/.hermes/cache/web/<host>-<hash>.md` — page it with `read_file` instead of re-fetching.
- **Never conclude 'not on the page' from a truncated extract.** An extract
  ending mid-sentence or mid-word means content was cut, not absent.
  Re-fetch with a higher `char_limit`; if it still truncates, `curl` the HTML
  and strip `script`/`style`/tags locally into a scratch text file, then read
  that. Absence is established only from a complete fetch.

---

## §5 LLM Wiki (Karpathy's Pattern)

Build and maintain a persistent, compounding knowledge base as interlinked markdown files.

### Location

Set via `WIKI_PATH` env var (defaults to `~/wiki`).

### Architecture

```
wiki/
├── SCHEMA.md          # Conventions, structure rules
├── index.md           # Sectioned content catalog
├── log.md             # Chronological action log
├── raw/               # Layer 1: Immutable sources
│   ├── articles/
│   ├── papers/
│   └── transcripts/
├── entities/          # Layer 2: Entity pages
├── concepts/          # Layer 2: Concept pages
├── comparisons/       # Layer 2: Side-by-side analyses
└── queries/           # Layer 2: Filed query results
```

### Core Operations

1. **Ingest**: Capture raw source → extract entities/concepts → create/update wiki pages → cross-reference
2. **Query**: Read index → search pages → synthesize answer → file valuable answers back
3. **Lint**: Check orphans, broken links, frontmatter, stale content, contradictions

### Conventions

- File names: lowercase, hyphens
- Every page starts with YAML frontmatter (title, created, updated, type, tags, sources)
- Use `[[wikilinks]]` for cross-references (min 2 outbound links per page)
- Never modify files in `raw/` — sources are immutable

### Obsidian Integration

The wiki directory works as an Obsidian vault. For headless servers, use `obsidian-headless` to sync via Obsidian Sync.
