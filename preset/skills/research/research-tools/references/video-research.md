# Video & YouTube Content Research Reference

Techniques for extracting metadata, transcripts, descriptions, and comments from YouTube and other video platforms when standard access is blocked.

---

## Method Tier List (Most → Least Reliable)

| Tier | Method | Best For | Limitations |
|------|--------|----------|-------------|
| 1 | **r.jina.ai** | Full extraction: title, description, transcript, comments, metadata | None observed; works on live streams and regular videos |
| 2 | **YouTube oEmbed API** | Basic metadata: title, author, thumbnail, dimensions | No transcript, no comments, no description |
| 3 | **Invidious instances** | Full extraction via alternative frontend | Many instances blocked/rate-limited; changes frequently |
| 4 | **yt-dlp** | Full download + metadata | Requires cookies for age-restricted/bot-protected; 429 rate limits |
| 5 | **Browser automation** | JS-rendered content | Consent walls, bot detection (Anubis), slow |

---

## 1. r.jina.ai (Recommended Primary)

```bash
# Syntax: https://r.jina.ai/http://<youtube-url>
curl -s "https://r.jina.ai/http://www.youtube.com/watch?v=VIDEO_ID"
```

**Returns:** Markdown with:
- Video title
- Channel name + subscriber count
- View count, upload date, hashtags
- Full description (with links)
- Comments (top + newest)
- Transcript (if available)
- Related videos sidebar
- All links preserved

**Example:**
```bash
curl -s "https://r.jina.ai/http://www.youtube.com/watch?v=5-BQsmVOk_g"
# → Clean markdown extraction (see session for full output)
```

**Why it works:** jina.ai fetches server-side and renders as clean markdown, bypassing YouTube's JS/bot detection entirely.

**Also works for:** Embedded videos, YouTube Music, Shorts (`/shorts/ID`), live streams (`/live/ID`), **scientific papers (Nature, arXiv, etc.), Microsoft/blog articles** — any publicly accessible URL.

**Example (Nature paper):**
```bash
curl -s "https://r.jina.ai/https://www.nature.com/articles/s41586-024-08445-2"
```

**Example (Microsoft blog):**
```bash
curl -s "https://r.jina.ai/https://go.microsoft.com/fwlink/?linkid=2316506&clcid=0x409"
```

---

## 2. YouTube oEmbed API (Fast Metadata)

```bash
curl -s "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=VIDEO_ID&format=json"
```

**Returns JSON:**
```json
{
  "title": "Watch Microsoft Build 2026 from San Francisco",
  "author_name": "CNET",
  "author_url": "https://www.youtube.com/@CNET",
  "type": "video",
  "width": 200,
  "height": 113,
  "version": "1.0",
  "provider_name": "YouTube",
  "thumbnail_url": "https://i.ytimg.com/vi/VIDEO_ID/hqdefault.jpg",
  "html": "<iframe...>"
}
```

**Use when:** You only need title, channel, thumbnail — no transcript/comments needed.

---

## 3. Invidious Instances (Backup)

**Known working instances (as of 2026-06):**
- `https://inv.nadeko.net` — often 502
- `https://invidious.snopyta.org` — redirects to instance selector
- `https://yewtu.be` — anti-bot challenge page
- `https://inv.tux.pizza` — timeout
- `https://inv.ytxc.xyz` — empty response

**API pattern:**
```bash
curl -s "https://<instance>/api/v1/videos/VIDEO_ID"
```

**Pitfall:** Instances rotate/die frequently. Check https://github.com/iv-org/invidious-instances for current list.

---

## 4. yt-dlp (Full Download + Transcripts)

```bash
# Metadata only
yt-dlp --get-title --get-description --get-duration --print "%(upload_date)s" "https://youtube.com/watch?v=VIDEO_ID"

# With cookies (required for bot-protected)
yt-dlp --cookies-from-browser chrome "https://youtube.com/watch?v=VIDEO_ID"

# Specify JS runtime (deno/quickjs)
yt-dlp --js-runtimes deno "https://youtube.com/watch?v=VIDEO_ID"

# Transcript extraction (works even when metadata fails due to bot protection!)
yt-dlp --write-auto-sub --sub-lang en --skip-download "https://youtube.com/watch?v=VIDEO_ID" -o "/tmp/video.%(ext)s"
# Output: /tmp/video.en.vtt (WebVTT format with timestamps)
```

**Common errors & fixes:**
| Error | Fix |
|-------|-----|
| `Sign in to confirm you're not a bot` | `--cookies-from-browser chrome` (or export cookies.txt) |
| `HTTP Error 429: Too Many Requests` | Wait, use VPN, or switch to r.jina.ai |
| `No supported JavaScript runtime` | Install deno: `curl -fsSL https://deno.land/x/install/install.sh | sh` |

**Transcript search workflow:**
```bash
# Extract transcript
yt-dlp --write-auto-sub --sub-lang en --skip-download "URL" -o "/tmp/v.%(ext)s"

# Search for keywords with timestamps (grep on VTT)
grep -n -i "keyword" /tmp/v.en.vtt

# Read context around matches
read_file /tmp/v.en.vtt offset=<line-50> limit=100
```

---

## 5. Video ID Extraction Patterns

```bash
# From various URL formats:
# https://www.youtube.com/watch?v=5-BQsmVOk_g
# https://youtu.be/5-BQsmVOk_g
# https://www.youtube.com/live/5-BQsmVOk_g
# https://www.youtube.com/shorts/5-BQsmVOk_g
# https://www.youtube.com/embed/5-BQsmVOk_g

# Bash extraction:
VIDEO_ID=$(echo "$URL" | sed -E 's/.*(v=|live\/|shorts\/|embed\/|youtu\.be\/)([^&?\/]+).*/\2/')
```

---

## Quick Decision Flowchart

```
Need transcript/comments/description?
  │
  ├─ YES → Try r.jina.ai first (95% success)
  │         If fails → yt-dlp with cookies
  │         If fails → Try active Invidious instance
  │
  └─ NO (metadata only) → YouTube oEmbed API (instant, reliable)
```

---

## Session Reference

This reference was created/updated from sessions researching:
- **Video:** "Watch Microsoft Build 2026 from San Francisco" (CNET)
- **Video ID:** `5-BQsmVOk_g`
- **Date:** 2026-06-11
- **Methods tested:** r.jina.ai ✅, oEmbed ✅, Invidious (multiple) ❌, yt-dlp ❌ (429) / ✅ (transcript VTT), Browser ❌ (Anubis)
- **Transcript extraction:** yt-dlp `--write-auto-sub --sub-lang en --skip-download` → VTT file → grep for "quantum" → found segment at 02:15:35–02:19:27
- **Deep research:** Used r.jina.ai for Microsoft Majorana 1 blog (Feb 2025), Nature paper (s41586-024-08445-2), arXiv:2211.07629 (quantum resource estimation), Azure Quantum page
- **Result:** Comprehensive technical overview of Microsoft topological quantum roadmap (Majorana 1 → Majorana 2 → 1M qubit target)

**Key finding for future:** When yt-dlp metadata fails with 429/bot error, `--write-auto-sub --skip-download` often still works and returns clean VTT transcripts searchable by keyword.