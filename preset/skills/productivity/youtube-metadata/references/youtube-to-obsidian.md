# YouTube → Obsidian: Rich Resource Note Workflow

When the user asks "изучи и добавь в обсидиан" (study this video and add to Obsidian), the expected output is a structured **Resource note** (not a quick Inbox capture). This workflow combines `youtube-metadata` fetching with `obsidian-vault` note creation.

## Workflow

**Before writing, resolve every `[[wikilink]]` you intend to use.** A guessed name produces a silent dead link in Obsidian that nothing ever flags. Check each target with `list(Path(vault).rglob(f"{name}.md"))`; if nothing comes back, link to the note that actually exists or drop the link and name the file in prose. Verify the whole file again after the final write — a patch can leave a mangled `]]+-` splice.

### Step 1: Get metadata (title + author)

```bash
curl -s "https://noembed.com/embed?url=https://www.youtube.com/watch?v=<ID>"
```

Extract: `title`, `author_name`, `author_url`, `thumbnail_url`.

### Step 2: Get description

```bash
cd ~/.hermes/skills/productivity/youtube-metadata
.venv/bin/python scripts/yt_fetch.py "<URL>" --skip-download --print "%(description)s"
```

If venv missing: `uv venv --clear && uv pip install yt-dlp`

### Step 3: List and fetch transcript

```bash
.venv/bin/python scripts/yt_transcript.py "<URL>" --list
.venv/bin/python scripts/yt_transcript.py "<URL>" --langs en[,ru] [--out FILE]
```

If `youtube-transcript-api` missing: `uv pip install youtube-transcript-api`.

**A 429 can hit a brand-new video on the first try** — the timedtext rate limit is per-IP and can be warm from earlier work. `--list` still works when downloads 429, so always run it first: it confirms the track exists and which languages you can get, and tells you whether to keep retrying yt-dlp or switch immediately to `yt_transcript.py`. Do not burn retries on yt-dlp first.

### Step 3b: Turn the raw dump into readable paragraphs

Never paste raw cues into a note — auto-captions roll a repeating window, so a verbatim dump repeats the same phrase every 2 seconds and is unreadable. Normalize first:

```bash
.venv/bin/python scripts/sub_to_paragraphs.py <file.vtt|file.txt> --out /tmp/body.md
```

Auto-detects the two input shapes (WebVTT, or the `[M:SS] word` format of `yt_transcript.py --out`) and emits `**[mm:ss]** paragraph` blocks. Inspect the result before wrapping it in a note; if a sentence is still garbled, the source is a machine translation, not a segmentation bug.

### Step 4: Create Obsidian Resource note

**Location:** `Resources/YouTube/<topic-subdir>/` (e.g. `Resources/YouTube/AI/`), filename exactly
`YouTube — <title> (<channel>).md` — no numeric prefix, Android-safe characters only.
**Structure:**

```yaml
---
title: "<video title>"
author: "<channel name>"
channel: "@<handle>"
url: "https://www.youtube.com/watch?v=<ID>"
tags: [resource, video, ...]
date: <YYYY-MM-DD>
type: resource
source: youtube
---
```

Body sections (in order):
1. **Metadata block** — title, author, link
2. **Summary** — condensed description in ~3-6 bullet points
3. **Technical details** — tables, step lists, key takeaways (tailored to content)
4. **Relevance note** — why this matters (from context/description)
5. **Transcript link** — wikilink `[[<Transcript Note Name>]]`

### Step 4b: Ground claims in the upstream source, not the video

For a tech/tooling video, the project's own repo/docs outrank both the video and its transcript. Fetch the README (raw, under the DoH patch if GitHub is blocked) and pull from it the model/feature tables, install commands, version numbers, and license the video only gestures at. A video review is a secondary source; a benchmark claim you did not verify upstream should not end up in the note as fact.

### Step 4c: Translate-garbled names get a correction table

Auto-translated captions render proper nouns phonetically and unrecoverably ("Oleа"→ollaya, "Джей"→Jev, "Leia"→laya, "Гликласс"→gliclass). Left alone, the transcript note teaches the wrong names to every future search. Add a warning callout near the top of the transcript note mapping the garbled forms to the real ones, sourced from the upstream repo — and use those real names in the resource note's tables and links.

### Step 4d: «Применимо у нас» — обязательная секция для технических роликов

When Igor asks «изучи … и подумай что полезного применить», the note must END with a
section mapping the video's findings to OUR current infrastructure — concrete rig, running
servers/ports/models, and per-item verdict (take it / already done / wrong fit), each
claim tied to our measured setup, not to the video's. Deliver the same mapping as the chat
reply in one message: note path + short applicability list. A generic summary without the
mapping is an incomplete answer for this user.

### Step 4e: Feature question inside a promo-heavy video — verify upstream, not the video

Creator videos often wrap one real product update in promo (free session, course,
community). When Igor asks «что там про <фичу>», answer the feature from the
transcript, tag the promo half in one line without elaborating, and verify every
product claim against the primary source — official announcement/docs or the
installed binary's own defaults (config-defaults grep, `--version`) — never the
video alone. State which parts came from the video vs the primary source.

### Step 5: Create companion transcript note (optional for longer videos)

**Location:** same folder as the note, name `<Title> Transcript.md`
**Structure:** Timestamped transcript blocks `[MM:SS] text ...`, cleaned and condensed.

### Variant: Quick Inbox capture

For when the user just shares a link without "изучи" — create a single Inbox note with title + author only, per SKILL.md pitfall guidance.

### Variant: Bulk assembly (a whole batch → many notes)

When dozens of videos must land as notes from a prepared source list (id, channel, like date), the pipeline is three scripts, each resumable, plus a split of the work by what evidence exists:

1. **Fetch** metadata + transcript per video into two JSON caches (`meta_<batch>.json`, `tr_<batch>.json`), written after EVERY video. Classify outcomes: terminal (`no_captions`, real `unplayable`) vs retryable (429/bot-wall) — retryables go to a paced second pass, never straight into a note.
2. **Split by evidence.** Videos WITH transcript text need an authored gist; build one digest file per video (metadata header + paragraphed transcript) and fan them out to subagents that emit `[{vid, gist, tags}]` JSON — with the standing rule that gist bullets come only from the digest, and an empty/short transcript means the gist is built from the description alone plus an explicit «⚠️ Транскрипт недоступен — только описание» bullet. Videos WITHOUT transcript get a deterministic note: metadata + description excerpt + the warning callout, no authoring pass.
3. **Assemble idempotently.** Skip a video if any existing note contains its `watch?v=<id>` (match on content, not filename — titles get edited/truncated), never overwrite a file that already carries the id, and append the id to the filename only when a same-title collision exists.

Pitfalls specific to bulk:
- **Validate a cached transcript before it becomes note content — the cache can hold parse junk, not speech.** Tell-tale shapes: text starting with a raw `WEBVTT` header, a few dozen characters of concatenated fragments ("oh n oh…"), or fluent nonsense in a different language than the track claimed. Cheap gate: < ~200 chars, or a high ratio of non-word tokens, or missing the expected language — demote to the `⚠️ Транскрипт недоступен` fallback and mark the cache entry unusable so the next pass doesn't re-promote it. A junk transcript embedded in a note is worse than the honest fallback.
- **Paragraphize plain-prose transcripts before they reach a note.** Timestamp-less text (proxy/json3 joins) has no punctuation in ASR, so a sentence splitter returns ONE paragraph of tens of KB; and `[музыка]`/`[music]`/`[--:--]` markers ride along as content. Split on sentence boundaries only as a first pass, then word-chunk any block over ~800 chars, and strip sound-effect markers — a note whose transcript section is a single wall of text is a defect, not a formatting quirk.
- **Verify subagent output as a SET DIFFERENCE, not per-task claims.** After an authoring fan-out, diff `need_vids − union(authored_json vids)` and confirm it is empty before assembling; a subagent that dies mid-run (model-overload 503) often still left a complete file behind, so re-dispatching on the failure notice alone duplicates work while the coverage check would show nothing missing. Roughly 18 digests / 200–400 KB per subagent task completes reliably; bigger slices are what runs into capacity failures.
- **The filesystem limit is 255 BYTES, not 255 chars** — Cyrillic doubles the byte count, so a sanitized `title(120) + channel(60)` name still dies with `OSError: File name too long`. Build the filename through a shrinking ladder (title 120→80→50, channel 60→40→30) until `len(fname.encode()) <= 240`, and re-check after appending a disambiguating id.
- A title can be empty in the source list (deleted/hidden metadata) — always prefer `videoDetails.title` from the fetch pass over the source row.
- Report coverage from the CACHE counts (written / terminal / retryable-pending), never from the run's printed `TOTAL`, which reflects the run's own thresholds.
- **Audit the whole batch against the NOTE CONTENT, not the state file.** After assembly, walk every id and classify its note: transcript/recap section with real content → covered; `> [!warning] Транскрипт недоступен` stub → open; section missing → open. The final claim «N/M с реальным содержанием» must come from this content audit, not from state-class counters — a stale path map (old spacing/quoting in the id→path file) or an earlier partial injection leaves state saying `ok` while the note still holds a stub. For each id whose state-map path does not exist on disk, locate the real note by grepping the vault for `watch?v=<id>` in the first 600 chars — titles get re-spaced, so filename-derived maps drift.
- **ASR-stub videos (music clips) are captionless for practical purposes.** A video whose every track yields < ~50 chars of word tokens after noise filtering ([музыка], single letters) is a music video where ASR cannot work — do not paste the 20-char stub, reclassify the id as captionless and route it to the video-study pipeline (mimo recap). An `ytdlp_ok`/`cdp_ok` class from an earlier wave can hide such a stub; the final audit above is what catches it.
- **Idempotent injection needs an expandable class gate.** When the injector only processes ids of one state class (`no_tracks`), later batches (e.g. `unusable` reclassified to recap) silently skip — widen the accepted-classes condition each time a new class enters the recap pipeline, or filter the run's id list to «ids with a summary file but no recap in the note» instead of by class.

## Pitfalls

- **yt-dlp stalls on description** — it needs JS runtime for modern YouTube extraction. `yt-dlp` may timeout on `--print` without deno/node. The wrapper runs a 45-60s timeout; if it hangs, skip the description and use transcript only.
- **noembed returns `author_name` as display name, not handle** — extract `author_url` to get the `@handle` portion for frontmatter.
- **Transcription is auto-generated** — brand names and technical terms are frequently garbled («Salad» → «sellet», «Kryptex» → «Cryptex»). Verify uncertain names before asserting in a note.
- **Transcript file lands in the skill's directory** — the yt_transcript.py writes `<ID>.<lang>.txt` to its CWD. Clean up after note creation: `rm -f /path/to/skill/<ID>.*.txt`.