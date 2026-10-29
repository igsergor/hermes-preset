---
name: youtube-metadata
description: Fetch YouTube metadata, transcripts, and account (subscriptions/likes) audits.
category: productivity
tags: [youtube, oembed, metadata, titles, links, subtitles, yt-dlp]
version: 1.2.0
---

# YouTube Metadata via oEmbed

Get a YouTube video's **title and channel/author** without scraping the heavy watch page. Needed whenever you save a YouTube link somewhere meaningful (Obsidian note, bookmark file, research log, message) and the plain URL isn't enough.

**Scope:** also covers pulling full video content for "study/summarize this video" tasks — subtitles and description. On Igor's server `www.youtube.com` is DNS-blocked: direct oEmbed and watch-page fetches return empty there. Go straight to [references/youtube-from-dns-blocked-server.md] for the probe order (noembed.com first) and workaround, and use `scripts/yt_fetch.py` (DoH-patched yt-dlp wrapper) for transcripts. If yt-dlp's subtitle download keeps failing with **HTTP 429** (per-IP timedtext rate limit — survives retries, `--retry-sleep`, and `player_client` switches; verified Aug 2026), switch transports instead of retrying: `scripts/yt_transcript.py` wraps `youtube-transcript-api` (`uv pip install youtube-transcript-api`) under the same DoH DNS patch — different transport, different rate-limit bucket. Run `--list` first: videos often have only some languages (e.g. only auto-generated `en`, no `ru`).

Transport throttling is not absence: `LOGIN_REQUIRED` / `Sign in to confirm you're not a bot`, HTTP 429 on every timedtext `fmt`, and `short_json3 len=0` mean throttled egress — retry once after a 40–45s pause or switch egress (proxy/relay); never record these as final «unavailable». Only `TranscriptsDisabled` / `NO_TRACKS` / an empty cue body in every `fmt` is a verified absence, and the fallback must carry that verified reason.

Never silently truncate: join ALL `segs` cues (taking only the first segment drops most of the text), and never apply a hard `len(txt)` cutoff that discards short but real transcripts — a 63-char transcript is data, not noise. When quality matters, prefer the raw VTT with real timestamps over a relay/proxy extract, which can be several times shorter.

Assembly must be idempotent: re-runs add only missing transcripts and never duplicate notes or overwrite non-empty cache entries; keep filename sanitizing (regex replace, length cap) stable so reruns converge. Idempotence must still allow an UPGRADE: a note written from metadata alone gets rewritten once its transcript and a authored gist both arrive — skip a note only when there is no new evidence for it, and never downgrade one that already carries transcript content.

**ASR transcripts need word-level re-chunking.** Auto-generated captions (no manual punctuation) arrive as ONE huge unbroken run of text — sentence-splitting (`(?<=[.!?…])\s+`) returns a single 10,000+ character paragraph that is unreadable in a note. Chunk by words instead: break at sentence boundaries when present, then fall back to word-boundary chunks of ~800 characters when a block exceeds that limit. Also filter out ASR noise markers (`[музыка]`, `[music]`, `[аплодисменты]`) before rendering. Never paste an auto-caption dump into a note without this pass — the raw text is a wall that defeats the purpose of the note.

**Linux filenames are limited to 255 BYTES, not 255 characters.** Cyrillic titles (2 bytes/char in UTF-8) overflow this limit at ~128 characters, triggering `OSError: [Errno 36] File name too long` even when the character count looks safe. When building the filename, calculate `len(fname.encode())` (bytes, not `len(fname)`) and truncate aggressively if it exceeds 240 bytes — keep the full title in frontmatter and H1, shorten only the filename stem. A 130-character Cyrillic title WILL fail if you only check character length.

**Working fetcher on this server: `/home/igor/hermes1/yt_fetch_jina.py`.** Verified Oct 2026, and it solves three failures the ladder above no longer does. (1) The InnerTube player endpoint needs an explicit API key in the query string AND a current client version — `youtubei.googleapis.com/youtubei/v1/player` with no `key=` returns HTTP 400 for every video, and a stale `clientVersion` fails the same way. Working combo: `?key=ВАШ_YOUTUBE_API_КЛЮЧ` + client `IOS` `20.10.4` + UA `com.google.ios.youtube/20.10.4 (iPhone16,2...)`. (2) Even with that, the signed `timedtext` baseUrl returns **HTTP 429 from every player client** (IOS, ANDROID) and every format (`fmt=json3`/`srv3`/`vtt`, also via `video.google.com`) — `youtube-transcript-api` fails with `IpBlocked` on the same videos. This is a hard per-IP block, not a transient 429, so no retry schedule helps. (3) The fix: fetch the signed timedtext URL **through `https://r.jina.ai/<url>`**, which proxies it from jina's own egress and returns the full json3 payload intact. Parse it by locating `Markdown Content:` then the first `{` — do **not** use `raw.rfind("{")` before `"events"`, which lands on a nested `wpWinPositions` brace and fails with `Extra data`. Budget ~30s per video, so batch it with one worker per chunk rather than serially; cache to `/tmp/vchunks/transcripts/<vid>.txt` and skip anything already >50 bytes. When even the relay path stalls because the *player* endpoint went `LOGIN_REQUIRED` for hours, the last-resort transport is the user's logged-in Chrome via CDP — see "InnerTube transcripts at scale" below.

When timedtext returns **429 on every `fmt`**, do NOT keep retrying (see pitfall above) — **switch to the read proxy**: `https://r.jina.ai/<timedtext-url>` has a different egress. The proxy's payload is NOT uniform — branch on what actually came back: (a) `Markdown Content:` prose (most common) — strip the header, `.replace("~~","")`, treat lines as captions WITHOUT timestamps, so never present it as timestamped cues and never fabricate a `[00:00]`/`00:00` label for text that has none (a `ts=-1` sentinel rendered as `[-1:59]` is the same lie); (b) raw json3 `{'events':...}` JSON (it sometimes DOES pass JSON through — do not assume prose) — parse it and keep the REAL cue timestamps instead of dumping the document; (c) WEBVTT with empty cue bodies — valid headers, no text: that is absence of content, not a parser bug. A FOURTH shape arrives via `&fmt=vtt` through the proxy: YouTube roll-up captions repeat the ENTIRE line-so-far as its own plain line inside every cue, plus 0.01s readability cues that are pure duplicates, with word-timing tags `<00:00:01.319><c>word</c>` on continuation lines. Dedup by EXACT LINE TEXT (a seen-lines set while walking the file, whitespace-normalized key) — a tail-window echo filter leaves those echoes in because each repeated line is longer than any word window, and cue-boundary tail-trimming fails too. `scripts/sub_to_paragraphs.py` applies this line-level dedup in `words_from_vtt`. Getting a caption URL needs one InnerTube `youtubei/v1/player` POST; the **ANDROID** client works where IOS returns `400 Precondition check failed` on every body shape. That endpoint IP-throttles hard after a burst (`IpBlocked`/`RequestBlocked`), so fetch one video at a time with ~25 s pacing and exponential backoff up to 10 min, resumable via a status file — a tight retry loop just deepens the block for every later video. Distinguish throttle from genuine absence: `TranscriptsDisabled`/`NO_TRACKS`/`NoTranscriptFound`/`VideoUnplayable` are the video's real state and must stay in the note as such; never rewrite them as a rate-limit excuse.

**Failure classification before writing "no transcript" into a note** — a failure code alone is not proof the video lacks captions:
1. **Throttle (retry, don't record):** 429 on every fmt, `LOGIN_REQUIRED`/"Sign in to confirm you're not a bot", `IpBlocked`, empty body. Do one paced retry (30–45 s pause, per-video): a batch reporting 6 `unplayable` recovered 4 this way, and the same IDs flip between FAIL and OK across passes. Recording a throttle-class code as the note's reason is a FALSE claim about the video.
2. **Your own threshold/parse rejection (fix the code):** a `len(txt) > N` gate drops short-but-real transcripts (a 63-char cue body is a genuine transcript); `except: continue` around timedtext swallows 429 into a fake "parse failed". Never classify from an error message you did not verify against the raw response.
3. **Genuine absence (final):** zero `captionTracks` or `TranscriptsDisabled` confirmed after a paced retry — only this goes into the note. `UNPLAYABLE` with a rights reason — «заблокировано из-за контента, на который заявил права пользователь SME/WMG» or «Запись этой трансляции недоступна» — is the same class: permanent. The video may still exist (oEmbed/noembed still answers), but captions will never be served; verify existence once, put the rights reason in the note, and stop retrying.
4. **Artifact-as-content (reject the text, not the video):** a parse can return TEXT that is not a transcript — the raw `WEBVTT`/`Kind: captions` header leaking through as the whole body, a 3-word ASR stub («oh n oh»), or foreign-language ASR output that is pure word salad. Length and non-emptiness checks all pass, so this class survives every gate that only asks "is there a string". Screen for it before caching: reject a body that starts like a container header (`WEBVTT`, `-->`), holds fewer than ~6 word tokens, or reads as unintelligible in the caption language — mark the video unusable, let the note fall back to the warning, and never paste the junk in. The inverse also fails the audit: a note whose gist bullet says «Транскрипт недоступен» while its transcript section carries text (or the reverse) is internally contradictory — final audit compares the two sections per note instead of counting warnings across the vault.

**Cache beats log output.** A run printing `TOTAL 60/80` while its cache holds 64 non-empty entries means the printed total counts its own thresholds — report coverage from the cache, not stdout. Prefer RAW VTT per video over parsed text: for the same video the raw VTT was 5–10× larger than an earlier parsed excerpt, so a parsed cache may reflect an old truncated/thresholded run. Write the cache after every video (a kill must not lose work), and never overwrite non-empty entries — that makes parallel runs over a shared output safe. Scan final notes for `~~`, `"events"`, `wireMagic`, `[--:--]` — all must be zero.

For the full "study this video and add it to Obsidian" workflow — note structure, transcript normalization, grounding claims in the upstream repo instead of the video, and the translate-garbled-names trap — go to [references/youtube-to-obsidian.md]. When Igor instead asks "what can we actually USE from this?" about a tool- or feature-showcase video — the deliverable is a triage verdict, not a summary: one line per claim, each verified against the shipped source and docs — go to [references/tool-video-triage.md]. `scripts/sub_to_paragraphs.py` turns a raw subtitle dump (WebVTT or the `[M:SS]` format) into readable timestamped paragraphs; raw auto-caption cues must never be pasted into a note as-is, because the rolling window repeats the same phrase every two seconds.

## Account audits: subscriptions, likes, watch history

The other half of this class is the user's own account: «разбери подписки», «почисти
YouTube», «разбери лайки». Deliverable is a verdict table with the ambiguous rows for his
decision plus a plain-text unsubscribe list, NOT silently unsubscribing anything.

- Full subscription list and watch history (endpoints, selectors, the virtualization and
  DOM-corruption traps): `references/youtube-channel-scraping.md`.
- Triage rules, signal ordering, the ambiguity-asymmetry rule, verification verdicts and the
  regex self-check habit: `references/subscriptions-triage.md`.
- Driving the browser to harvest those pages: `web-automation-auth` →
  `references/live-browser-cdp-marionette.md` and `references/bulk-action-verification.md`.

## The technique: oEmbed API

```bash
curl -s "https://www.youtube.com/oembed?url=https://youtu.be/<VIDEO_ID>&format=json"
```

Returns JSON:
```json
{ "title": "...", "author_name": "...", "author_url": "..." }
```

- `<VIDEO_ID>` comes from the URL forms:
  - `https://youtu.be/<ID>` (short link)
  - `https://www.youtube.com/watch?v=<ID>`
  - `https://youtube.com/shorts/<ID>`
- Requires **no API key** and no auth. Much lighter than parsing `watch?v=` HTML (which frequently returns no `<title>` because of the consent page / JS-rendered layout).
- Batch: loop over IDs with a small `for` shell loop.

- **`no_captions` ≠ «субтитров нет» без повторной попытки**: `LOGIN_REQUIRED: not a bot` —
  троттлинг, восстанавливается паузой 40-45с; порог `len(txt)>120` выбрасывает реальные
  короткие транскрипты. Лучший текст — `raw_vtt/*.vtt` (с таймкодами), в 5-10 раз полнее
  выжимок в кэше. Подробности: [references/transcript-absence-vs-throttle.md].

## Consistency gotcha: the `si` query param

Shared YouTube links often carry `?si=<tracking>` (e.g. `https://youtu.be/ABC123?si=xyz`). Drop `?si=...` when building the oembed URL; only the video ID matters.

## Researching what a channel actually recommends (transcript-first protocol)

When Igor asks what a creator recommends, whether a substance is part of their
protocol, or asks to «посмотри ролик» — the answer comes from the transcripts,
not from blog posts paraphrasing the videos. Blogs are a fast index; they drift
and they routinely omit cofactors and caveats the speaker states on camera.

1. **Enumerate the topic's videos cheaply first.** One playlist listing gives
   every candidate id to triage:
   `yt_fetch.py --flat-playlist --print "%(id)s | %(title)s" "<playlist-url>"`.
2. **`--list` before every fetch.** `NoTranscriptFound` = that language is
   absent. `VideoUnplayable … account associated with this video has been
   terminated` = the video is GONE; web search happily returns terminated videos,
   so skip it instead of retrying a fetch that cannot succeed.
3. **Fetch to files, then grep them AS A SET.** One
   `grep -inE 'term1|term2' d3_*.txt` over every transcript answers "is X in
   their protocol" across a whole topic in a single pass, and it is what surfaces
   items their own written protocol omits.
4. **An ABSENCE inside the videos you happened to fetch is NOT evidence of
   absence from the creator's position — never use it to strike an item from
   the user's own plan.** Zero hits across the topic playlist you opened means
   only "not in these N videos". Creators split one substance across many
   videos (a D-videos playlist says nothing about their iodine protocol), so
   before concluding anything about a substance, run the channel's own SEARCH
   for that substance and fetch those transcripts:
   ```bash
   yt_fetch.py --flat-playlist --print "%(id)s | %(title)s" \
     "https://www.youtube.com/@<handle>/search?query=<substance>"
   ```
   Only a zero across BOTH the topic videos and the substance's own videos
   supports "they don't cover this". Report a presence claim with the quoted
   sentence + timestamp; report an absence with its scope stated ("absent from
   all 8 D-videos; their iodine videos say X") so the limit is visible.
5. **When the user suspects the list is INCOMPLETE, enumerate the whole topic,
   not the item they named.** "Не только куркумин там упоминается?" means the
   right move is the full cofactor list from that segment, every member's
   status, and which of them the speaker actually sells — not a yes/no on
   curcumin. Grep every transcript for the sibling terms in one pass; a quoted
   enumeration ("resveratrol, curcumin, curcitin and sulphoraphane") is itself
   the finding. Expect the user's own written protocol to carry items their
   videos never mention — attribute each one to its real source.
5b. **Recount finished work from FINAL statuses before declaring a remainder.**
   When reopening a task that was already reported done, fold the progress file
   to the last record per unique video/channel and count the fold — counting
   intermediate retry rows (ERROR→FAILED→ok) on a completed job fabricates a
   backlog that does not exist, and telling the user their finished work is
   unfinished is worse than the original error.
6. **Read the video DESCRIPTION for the products he names on camera.** It
   carries his own affiliate/product links, which identify the exact SKU he
   recommends — stronger than any blog paraphrase, and often a formulation
   (e.g. a D3+K2 drop "with Zinc") that the blog pages don't surface:
   ```bash
   yt_fetch.py --skip-download --print "%(description)s" "<watch-url>" | grep -oE 'https?://[^ )]+'
   ```
7. **Check whether a recommended compound is ALREADY in the stack before
   adding a SKU.** Read the label of the products already on the list; a
   "recommended extra" whose substance is already dosed inside a capsule the
   user is buying is a duplicate purchase, and naming that saves the cost.
   Video alt-text/description ingredient lists plus the product image are the
   label source when the storefront text omits the panel.
8. **Verify the storefront with a transport ladder; the obvious ones get
   throttled or return nothing.** Extractor backends 503 out and Shopify's
   `products/<handle>.json` answers `{"error":"local_rate_limited"}` within a
   couple of requests, so neither is a reliable price/label source. Use the
   read proxy, which returns the rendered product page:
   ```bash
   curl -s "https://r.jina.ai/https://<store>/products/<handle>" --max-time 60 \
     | grep -iE "new price|backordered|Add to cart|Sold out|Servings per"
   ```
   Space calls a few seconds apart. `is backordered and will ship` is the
   string to quote when an item is unavailable — it changes whether the user
   should order now or wait. Same "switch transport, don't retry" rule as the
   timedtext 429 above.
9. **Enumerate the whole catalog from the sitemap when web search misses a
   SKU.** Brand sites bury compounds in products no search engine indexed:
   grep the sitemap rather than trusting `web_search` or the site's own `?q=`
   (storefront search typically returns a fixed result count for ANY query,
   including nonsense — useless as a filter, and easy to misread as "no such
   product").
   ```bash
   curl -s -A "Mozilla/5.0" "https://<store>/sitemap_products_1.xml" \
     | grep -oE '<loc>[^<]+</loc>' | sed 's/<[^>]*>//g' > /tmp/catalog.txt
   grep -iE "<substance>|<mineral>" /tmp/catalog.txt | sed 's|.*/products/||;s|\.html||'
   ```
   This is how a multi-nutrient compound turns up after transcript mentions of
   a bare mineral — and it is how you find the combination product that makes
   a single-mineral SKU unnecessary.

Blog-style supplement pages are useful as a price/size index but never as
evidence for a dosage or cofactor claim — the label dose and the speaker's
recommended dose differ constantly.

## Delivering a protocol/pl regimen Igor asked to reconstruct

When the task is «посмотри ролик и скажи что там» about a course, stack or
protocol, the deliverable is a PLAN, not a summary. Shape he expects:

- **Exact quantities, never ranges.** «2-3 флакона» is unusable at checkout —
  compute `days × dose × people` against the real capsule count per bottle and
  state one integer per SKU, with the arithmetic visible. Reuse the previous
  answer's numbers as the base when he iterates ("на 2 человек", "пересчитай по
  150"), and re-derive only the affected rows.
- **A link per product**, on the line where it is bought, not a link dump at
  the end.
- **Flag stock status with the string that proves it** — «backordered, отгрузка
  при поступлении» changes whether he orders now or waits, so it belongs next
  to the price, not in a footnote.
- **His regimen is the deliverable, not your opinion of it.** Report what the
  creator recommends at full strength and note that it exceeds guideline
  ceilings once, at the end, with the specific number for each substance
  (e.g. 10 000 IU where the official ceiling is 2000-4000; 600 mcg iodine vs a
  150 mcg ceiling). Repeating the caveat on every row reads as arguing with
  the plan he asked for.
- **Keep source attribution per item.** A plan handed to him mixes items from
  the creator's videos, items from his own written PDF, and items you inferred.
  Say which is which — he acts on the difference (this is how a supplement in
  his PDF turns out to come from somewhere his videos never mention).
- **Say plainly when you were wrong and correct it in place.** Reversing an
  earlier recommendation (keeping vs dropping an item) is expected; state the
  correction and the new protocol without re-litigating the old reasoning.

## InnerTube transcripts at scale, when every transport is throttled

For bulk jobs (dozens+ videos) the InnerTube `player` endpoint with the **IOS client**
(`clientVersion 20.10.4`, UA `com.google.ios.youtube/20.10.4 (iPhone16,2; U; CPU iOS 18_3 like Mac OS X)`)
is the one that reliably returns `captions.playerCaptionsTracklistRenderer.captionTracks`.
ANDROID returns `tracks-but-empty`; MWEB/WEB return `UNPLAYABLE`.

The caption **tracklist** and the caption **text** are separate rate-limit buckets, and they throttle independently:

1. **Tracklist works, timedtext text 429s.** `POST /youtubei/v1/player` succeeds and gives a `baseUrl`, but `GET baseUrl&fmt=json3` returns `HTTP 429 Too Many Requests` from the direct IP — the known per-IP timedtext limit. yt-dlp fails identically, and so does `youtube-transcript-api` (`IpBlocked`).
   **Fix that works: fetch the timedtext URL through a read proxy.**
   `GET https://r.jina.ai/<baseUrl>&fmt=json3` returns the full json3 body, with a
   `Title:/URL Source:/Markdown Content:` header wrapped around it — parse from the first `{`.
   Pace ~1-2 s between videos and the whole batch succeeds.
2. **Tracklist itself returns `LOGIN_REQUIRED` / "Sign in to confirm you're not a bot".** This is
   the IP being rate-limited after a burst, and it also makes `andnroid_vr` and every yt-dlp
   client fail. Retrying does not help — it makes the block longer. Stop, wait, then resume with the single working client and slow pacing instead of cycling through clients; verified: the player-endpoint `LOGIN_REQUIRED` block can persist for HOURS even with fully paced retry rounds, so schedule the next round hours later rather than every few minutes, and use the wait productively — oEmbed/noembed metadata and r.jina.ai proxy traffic keep answering throughout, so classify outcomes, assemble the notes you can, and only the caption-text fetch waits. The reverse also holds: InnerTube **`browse`** (likes playlist, WEB client + cookies) keeps answering while `player` is bot-walled — separate buckets — so run likes/metadata collection during a player block.
3. **`status: OK` with no `captions` key at all** means the video genuinely has no subtitle track.
   That is a dead end, not a fetch failure — stop retrying it and mark the transcript unavailable.
   Don't burn the whole retry budget distinguishing "no track" from "blocked".

Batch shape that works: one script, per video → one `player` POST via IOS, best-language track
(russian, then english, then ukrainian/belarusian), `fmt=json3` via `r.jina.ai`, checkpoint the
results to JSON after every video so a kill/resume never loses work.

**Last-resort transport: the logged-in browser via CDP.** Before escalating here, try yt-dlp with
the user's Firefox-profile cookies — see `youtube-transcript-fetch` skill, recipe section: one
command per video with `--js-runtimes deno --remote-components ejs:github`, no browser session to
keep alive, and it downloads subtitle files for video IDs whose CDP transcript panel loads nothing
(different rate-limit bucket via the cookie jar). Preconditions: Chrome running with remote debugging — Igor opens
youtube.com in it on request (`ss -ltnp | grep 9222`). Procedure per video (verified working):
connect WS to the page's `webSocketDebuggerUrl`, `Network.enable`, `Page.navigate` to the watch
URL, wait ~14 s, click the "Show transcript" button (`aria-label` contains "transcript"; retry up
to 4×5 s — the panel and its button load late), then intercept the player's OWN `timedtext`
request via `Network.responseReceived` → `Network.getResponseBody`. Do NOT hand-build the fetch:
calling `fetch(baseUrl)` or `get_transcript` from page context returns `len=0` / `400 Precondition
check failed` — only the transcript panel's own request carries the signed params the server
accepts. The response arrives as srv3 JSON (`wireMagic:"pb3"`, `events[].segs[].utf8`) when no
`&fmt` was appended — parse `events`/`segs`, not WEBVTT. Reconnect the WS per video: a long-lived
socket times out after a few navigations, and `Network.enable` must be re-sent on the fresh
connection.

CDP outcome classes: «clicked=1, capture empty» = the panel loaded but its data did not arrive
inside the drain window — collect the empties and rerun them in later rounds (some convert).
A video whose transcript button never appears (clicked=0 after the 4 retries) has no transcript
panel — that is verified absence, not a fetch failure. The panel's request bypasses a
monkey-patched `window.fetch` (hooking it captures nothing); only CDP `Network` interception
sees it. And clicking the button while the panel is already open CLOSES it — never double-click
to force a reload; navigate the page again instead.

Two more panel states read as «clicked=1, capture empty» but have distinct fixes — check both
before declaring a video panel-absent:
- **Panel hidden with `visibility=ENGAGEMENT_PANEL_VISIBILITY_HIDDEN`** — the button clicks,
  the panel exists in DOM, but its content never loads; the toggle click just hides the
  already-hidden panel. Remove the `visibility` attribute from the panel element BEFORE
  clicking (`p.removeAttribute('visibility')`), then click Show transcript once; that sequence
  converted a stuck video to 189 segments in one shot.
- **Freshly navigated page: no transcript button exists at all** until the description is
  expanded — click `ytd-text-inline-expander #expand` first, then the button appears. A page
  that never yields the button after the expand click is the real panel-absent case.

Even with the button found and clicked, the panel can stay at zero segments with NO
`get_transcript` request on the network — the caption `baseUrl` in `ytInitialPlayerResponse`
serves page-context `fetch` (with or without credentials) as HTTP 200 + zero bytes, so
hand-building the request is a dead end; only the panel's own signed request carries the
params the server accepts, and when that request never fires, run the video through yt-dlp
with Firefox cookies instead (see `youtube-transcript-fetch` recipe) rather than debugging
the panel further.
(And never debug this against a tab another
fetcher is navigating concurrently — verify `location.href` matches your target video before
evaluating anything, or you diagnose the wrong page.)

**Captionless videos: study via local download + multimodal model — CDP screenshots are the last resort.**
A video with no caption track (verified cross-transport) often carries its meaning on screen and in audio. The approved pipeline (Igor's choice): download the video with the cookie'd yt-dlp recipe (same flags, a video format, no `--skip-download`), chop 10-minute chunks with ffmpeg (480p/15fps/crf30), feed each chunk to the multimodal model with audio+vision (muse-spark-1.3-contributor via opencode-go responses API), chain chunk summaries into the note's study section, then DELETE the local copy before the next video. Full recipe and API gotchas: [references/video-study-multimodal.md]; runnable queue script: `scripts/study_captionless.py`. Ground the gist in what the model actually reports seeing/hearing plus the author's description — never from the title alone.

The method lesson stands: answer Igor's method probes directly (frame frequency, loss between frames) and TEST his alternative before defending yours — here the download path (yt-dlp + cookies) turned out to be the working transport that made both screenshots and frame-sampling unnecessary. Do NOT try to download the media file through CDP instead: `streamingData` format URLs from `ytInitialPlayerResponse` 403 via direct curl and give 204/31-byte stubs via page `fetch` (the player's own googlevideo requests carry signed headers and range params `fetch` cannot replicate) — the download works through yt-dlp's own transport with the cookie jar, which is exactly why the study pipeline starts there. CDP screenshots of the playing player remain the fallback only when yt-dlp cannot download the video (no formats, member-only).

Two additions that make bulk jobs cheaper and survivable:

1. **The player response IS the note metadata.** The same POST that returns `captionTracks`
   carries `videoDetails` (`title`, `author`, `shortDescription`, `lengthSeconds`,
   `viewCount`, `uploadDate`) — take title/description/views/duration from there for batch
   note assembly instead of a separate oEmbed + description fetch per video (one request
   per video total). Keep the oEmbed ladder only for single ad-hoc links.
2. **Expect throttling at the TAIL of a batch and finish the pass anyway.** The first half
   of a run succeeds and the failures accumulate toward the end as the IP heats up
   (`timedtext_429`, `LOGIN_REQUIRED` bot-walls) — do not abort mid-batch or retry in place,
   that deepens the block for the remaining items. Finish the pass classifying every outcome
   into **terminal** (`no_captions` / `status OK` without `captions`, a real `unplayable`
   reason) vs **retryable** (429 / bot-wall), then run paced retry ROUNDS over ONLY the
   retryables — ~45 s pause per video, repeat until a round recovers nothing. Verified:
   the retry round recovered roughly half of a 48-video 429 tail that the main pass lost.

**Absence is not completion for the vault (Igor's standing rule): every liked/queued video
must end up studied and in Obsidian — a warning stub is open work, not done. When captions
are terminal-absent, the approved fallback is the video-study pipeline: download with cookie'd yt-dlp → 2-min chunks → multimodal model study (muse-spark-1.3-contributor) → summary into the note → delete the local copy ([references/video-study-multimodal.md]; CDP screenshots only when the download fails); when they are merely
throttled, keep paced rounds going instead of closing the task.
task. Liked-videos monitoring is a standing DAILY duty: `scripts/likes_daily_inner_tube.py`
collects the LL playlist WITHOUT Firefox/Marionette — cookies read straight from the snap
Firefox profile `cookies.sqlite`, SAPISIDHASH built in Python, InnerTube `browse` with
`browseId: VL+LL`. The new layout serves `lockupViewModel` items (`contentId` +
`metadata.lockupMetadataViewModel.title.content`), ~100 per response with NO continuation
token on the first page — enough for a daily diff, because fresh likes sort to the top. The
`Недоступные видео скрыты` alert in the response is normal, not an error. Deployed copy +
daily cron live at `/home/igor/likes_daily.py`; the daily agent job creates notes for new
likes, reruns the transcript backfill over them, AND studies every new like through the
multimodal pipeline (`~/.hermes/scripts/yt_like_study.py`: download → 2-min chunks →
muse-spark-1.3-contributor recap → inject into the note, idempotent). Metadata-only notes are open
work, not done — collecting without studying is pointless. The study script also reconciles:
each run diffs `latest.json` (full likes snapshot) against the vault (`watch?v=<vid>` search)
and backfills up to 5 stub-or-missing notes per run (`[backfill]` in the log) — this covers
relikes that never enter `new_likes.json` and past-run failures. Never create a second note for
a reliked video; check the vault first.

**Study-script pitfall — missing notes cause permanent stuck failures.** `yt_like_study.py` calls `find_note(vid)` and, if it returns None (no vault note exists for that vid), prints "НЕТ ЗАМЕТКИ — пропускаю" and counts fail=1. The video stays in `new_likes.json` forever and fails on every subsequent run — the backlog never clears. The reconcile list does NOT cover this case because reconcile only processes videos in `latest.json` that are NOT in `new_likes.json`; new likes are processed only through the `new` list, where a missing note is fatal. Root cause is always a sequencing gap: the study step ran before note creation (step 4 of the cron job) or note creation failed. **FIXED Oct 2026 — option (b) is implemented:** `yt_like_study.py` now carries `create_note(vid, title)` (frontmatter + H1 + Video ID table + «Суть по названию» + `pending_backfill` stub, filename `YouTube — <sanitized title>.md`, channel/title from noembed) and calls it whenever `find_note()` returns None, for BOTH the new list and the backfill list — the log line reads «заметки не было — создана скриптом (self-heal)». A missing note therefore no longer becomes a permanent failure, and the cron job's manual step 4 is no longer required for the pipeline to work. Two details that matter if you touch this code: the self-heal never overwrites an existing file at the same path (on a name collision it appends `[<vid>]`), and `_cache[vid]` is updated on creation so the later `insert_summary` targets the new note.

**Second stuck-backlog class — a stale «Транскрипт недоступен» line inside a note that HAS a recap (fixed Oct 2026).** Notes built metadata-first and later upgraded by the study step kept BOTH the old warning «⚠️ Транскрипт недоступен … Ниже — только метаданные» in the header block AND the real recap in «## 🎬 Транскрипт». `has_real_content()` used to short-circuit on that string, so the video was re-queued as backlog on EVERY run — each run re-inserted the (cached) summary, logged «ИЗУЧЕН И ВРЕЗАН», and the backlog never cleared: false progress that reads as success. Two fixes, both required: (1) `has_real_content()` checks positive markers FIRST and treats the warning as a stub only when no marker and no `**[M:SS]**` recap timestamp is present (a bare `**[M:SS]**` regex avoids matching description timelines like `**00:00–03:15**`, which are NOT content); (2) `insert_summary()` deletes any line containing «Транскрипт недоступен» when it writes a recap, because after insertion that claim is false. A one-off sweep over the vault removed the contradictory line from 90 notes (all of which kept their recaps; audit confirmed 0 notes left with both, and the 23 notes that legitimately have no transcript kept their warning). Rule: whenever you make a detector idempotent, verify CONVERGENCE — run it twice and confirm the second pass has zero work, not just that it prints success.

Detect studied notes by positive content markers
(`Автопересказ`, `video-recap`, `Транскрипт:`, `📌 Суть`, timestamp cues) — never by mere
absence of the `pending_backfill` stub, or notes carrying subtitles in other formats get
misclassified as unstudied and re-queued.

**When the user's own browser is the only working window, the daily diff does not need it.**
The `browse` likes-collection path above works from cached profile cookies with no browser
session — Chrome with the user's logged-in YouTube tab is needed only for the CDP
transcript/screenshot transports. Conversely, while the user's Chrome is open with
remote debugging (`ss -ltnp | grep 9222`), it is the fastest available transport for both
transcripts and frame study — but it is a CONCURRENT-shared tab: any batch CDP fetcher will
navigate the same tab, so never hand-debug against it while a batch job runs, and re-verify
`location.href` before every evaluate.

**Cron job prompt overestimates study speed by 5-10×.** The prompt for job 583efdab1ed4 claims "5-10 мин per video". The script's own output shows 55 min for a 55-min video (28 chunks × 2 min each). The prompt's estimate is wrong by an order of magnitude. When creating or auditing a cron prompt, measure the real per-unit cost first (run the script once, read its own timing), then write the prompt. Never repeat a timed-out foreground call — change to background mode. The script is idempotent (skips studied videos, reuses cached chunks) so interruption is safe. One video per cron run is the safe default; `RECONCILE_MAX=5` × 55 min = 4.5 hours — beyond any single cron slot. For a daily job, 1-2 per run is plenty; the backlog reconciles over a week.

The `browse` likes-collection path above works from cached profile cookies with no browser
session — Chrome with the user's logged-in YouTube tab is needed only for the CDP
transcript/screenshot transports. Conversely, while the user's Chrome is open with
remote debugging (`ss -ltnp | grep 9222`), it is the fastest available transport for both
transcripts and frame study — but it is a CONCURRENT-shared tab: any batch CDP fetcher will
navigate the same tab, so never hand-debug against it while a batch job runs, and re-verify
`location.href` before every evaluate.

### Long-running multimodal study: runtime reality vs prompt claims

The prompt for `583efdab1ed4` claims "На ролик уходит 5-10 мин". The script's own output says "55 мин, 28 чанков" for a 55-min video. The prompt's estimate is off by 5-10×. Always trust the script's measured output over the prompt text.

Rules:
- **A 55-min video → 28 two-minute chunks → 28 sequential API calls at ~2 min each → ~55 min wall time.** The prompt's "5-10 мин" is wrong by an order of magnitude. When creating or auditing a cron prompt, measure the real per-unit cost first (run the script once, read its own timing), then write the prompt.
- **One video per cron run is the safe default.** `RECONCILE_MAX=5` × 55 min = 4.5 hours — beyond any single cron slot. For a daily job, 1-2 per run is plenty; the backlog reconciles over a week.
- **The script is idempotent and resumable.** It skips already-studied videos, reuses cached chunks, and deletes chunks after processing. Interrupting mid-run is safe — the worst case is re-running one chunk. This makes background execution (terminal background=True) the right mode, not a risk.
- **Chunk caching means re-running is cheap.** Stale chunks from a previous (failed) run are reused if `os.path.exists(cpath) and os.path.getsize(cpath) > 10000`. After a crash, leftover `chunk_*.mp4` files from the failed run are automatically picked up — no manual cleanup needed.
- **The `study_pipeline.py` shim wraps `study_captionless.py`** and overrides `sc.download` with a DNS-safe version using `yt-dlp-dns.py`. Both must be on `sys.path` — the shim handles this. Don't call `study_captionless.process()` directly; always go through the shim.
- **Summary files are the delivery artifact.** `study_pipeline.process(vid)` writes `/tmp/yt_study/summaries/<vid>.md`. `yt_like_study.insert_summary()` reads that file and injects it into the vault note. If the summary file is missing, insert fails — check the summaries dir before declaring success.
- **EVERY chunk returning empty = quota/model wall, NOT a dead video.** When the OpenCode Go weekly quota is exhausted the API answers HTTP 429 `{"type":"error","error":{"type":"GoUsageLimitError","message":"Go usage limit exceeded"},"metadata":{"limitName":"weekly"}}`. Each `summarize()` then burns all 5 curl retries (560s max-time + 30s sleep) returning None, `process()` prints `<vid> пусто` and returns False, and the run ends `STUDY ok=0 fail=1` with the misleading line «изучить не удалось (видео мёртво?)» — the video is fine, the quota is gone. Before starting a long backfill run, probe the key (`OPENCODE_GO_API_KEY` from `~/.hermes/.env`): POST `https://opencode.ai/zen/go/v1/responses` with `{"model":"muse-spark-1.3-contributor","max_output_tokens":16,"input":[{"role":"user","content":[{"type":"input_text","text":"ok"}]}]}` — `429` = quota exhausted, do not start; the note keeps its `pending_backfill` stub and self-retries via reconcile once the weekly limit resets. A leftover `/tmp/mimo_resp_*.json` carrying `invalid_request_error` instead means a payload-level problem, a different class from the quota 429.

- **Applies-to `author_name`**, not just title — capture it too so the note/resource has attribution.
- **Long-running study scripts in cron jobs must run in background, not foreground.** A 55-min script will hit the terminal tool's 600s ceiling. Use `terminal(background=True, notify=True)` with output to a log file, then poll with `process_manage`. The script is idempotent (skips studied videos, reuses cached chunks) so interruption is safe. Never repeat a timed-out foreground call — change the mode. A cron agent re-resolves its interpreter on every run and the managed tools-python tree gets refreshed, so a `pip install yt-dlp` there silently vanishes and the next run fails the whole backlog with `ModuleNotFoundError`. Keep yt-dlp in a long-lived venv and make the download wrapper re-exec into it on `ImportError` instead of failing.
- **Persistent DNS blocks vs transient outages.** On Igor's server `*.youtube.com` never resolves (verified Aug 2026) while general internet works — retrying direct fetches there is wasted effort; use [references/youtube-from-dns-blocked-server.md]. Elsewhere, an occasional failed fetch may still be a transient route blip: retry once before declaring failure.
- **Auto-subs garble brand names** («Salad» → «sellet», «Kryptex» → «Cryptex/Cryptol», «pool.kryptex.com» → «PullTтриpt»). Never assert an uncertain name in a note — verify externally or mark it as distorted. See reference for more.
- **Obsidian `Resources/` YouTube notes carry NO numeric prefix.** The filename is exactly
  `YouTube — <title> (<channel>).md` with an em-dash. A `NN_` prefix (as used in scratch staging
  dirs like `/tmp/vnotes/c026/`) does not belong in the vault — 500+ existing notes there are
  unprefixed. Keep `NN_` for staging, strip it when the note lands in the vault.
- For the Obsidian vault specifically, two output patterns exist:
  - **Quick capture** — group multiple incoming links into ONE Inbox note with title + author each (per the `obsidian-vault` skill catalog), and remove any bare-link draft created earlier.
  - **Rich Resource note** ("изучи и добавь в обсидиан") — full summary + description + transcription as structured notes in `Resources/`. See [references/youtube-to-obsidian.md](skill://youtube-metadata/references/youtube-to-obsidian.md) for the full workflow.