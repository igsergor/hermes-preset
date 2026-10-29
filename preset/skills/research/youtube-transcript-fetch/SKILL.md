---
name: youtube-transcript-fetch
description: Fetch real YouTube transcripts in bulk (IP-429 workaround).
---

# YouTube bulk transcript fetch

`timedtext` is **IP-blocked (HTTP 429)** from this host — cookieless transports (`youtube-transcript-api`, bare `yt-dlp --write-sub`, curl_cffi impersonation, hand-built page `fetch`, every InnerTube client) all hit the wall. Working ladder, cheapest first: (1) **yt-dlp with the user's Firefox-profile cookies + deno + remote-components** — recipe at the bottom of this file, downloads real subtitle files even while everything cookieless is throttled; (2) the two-hop split below; (3) logged-in Chrome via CDP.

1. **InnerTube `player` → caption track URL** (works directly)
2. **`https://r.jina.ai/<captionUrl>` → transcript body** (relay works)

When even the relay path stalls because the *player* endpoint itself went `LOGIN_REQUIRED` for
hours (paced retry rounds recover nothing), the last-resort transport is the user's logged-in
Chrome via CDP — procedure in `youtube-metadata` skill, "InnerTube transcripts at scale". For videos with **no caption track at all**, the same CDP session doubles as the study path: play the video and read vision-analyzed screenshots (youtube-metadata skill, "Captionless videos").
Transport priority order for this host: cookie'd yt-dlp (see recipe below) → InnerTube+jina relay →
logged-in browser CDP. Escalate in that order; do not jump to the browser while the cheaper tier still
answers.

## Client that works

```python
API = "https://www.youtube.com/youtubei/v1/player"   # no key needed
UA = "com.google.ios.youtube/20.10.4 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X)"
headers = {"Content-Type": "application/json", "User-Agent": UA,
           "X-YouTube-Client-Name": "5", "X-YouTube-Client-Version": "20.10.4"}
```

- `clientVersion` **20.10.4** works; 19.29.1 / 15.13.2 return `400 Precondition check failed`.
- ANDROID 20.10.38 (client name 3, UA `com.google.android.youtube/20.10.38`) is a good fallback.
- WEB / MWEB return UNPLAYABLE; TVHTML5 errors out.
- If you send an ANDROID payload you must send ANDROID headers — mismatched client name/version headers cause 400.
- Read `captions.playerCaptionsTracklistRenderer.captionTracks[].baseUrl`. Prefer `ru`, then `en`, and `kind != asr` over `asr`.

## Relay

```python
urllib.request.urlopen("https://r.jina.ai/" + baseUrl + "&fmt=vtt",
                        headers={"User-Agent": "Mozilla/5.0", "x-respond-with": "text"})
```

`&fmt=vtt` returns clean `WEBVTT`. Other proxies (allorigins, codetabs, corsproxy, cors.sh, proxy.cors.sh, r.jina.ai-on-watch-page) fail. `r.jina.ai` only works on the raw `timedtext` URL, not on `youtube.com/watch`.

## Caption cleanup (mandatory)

YouTube roll-up captions repeat the whole line-so-far in every cue, so raw output looks like
`"A B. A B. C C. C D."`. Modern formats (`&fmt=vtt` through the relay, or the srv3 JSON the
browser transcript panel emits) carry the repetition as FULL DUPLICATE LINES, not word tails —
dedup by exact line text with a seen-lines set (whitespace-normalized), not by tail-window or
prefix-trimming:
1. Within a cue, if the words are exactly `X X` (first half == second half), keep one half.
2. Across cues, drop any line already seen verbatim; keep only genuinely new lines.
3. Strip word-timing tags (`<00:00:01.319><c>word</c>`) before any comparison.

Without this, notes read as word salad. `/tmp/vchunks/clean2.py` and
`youtube-metadata/scripts/sub_to_paragraphs.py` hold working implementations.
A self-contained, stdlib-only implementation of exactly these three steps ships with
this skill as `scripts/vtt_cleanup.py` (stdin/file in, cleaned text out) — use it
instead of hunting for the referenced scripts, which may not exist on this host.

When a prefix/tail cleanup still leaves echoes in the output, the format's repetition is
line-level — switch to the exact-line dedup instead of tightening the prefix matcher.

## Practice notes

- ~75% of a random "liked videos" batch yields a transcript. Typical failures: no caption tracks at all, or subtitles so short they parse to nothing.
- Cache the **raw VTT to a file per video ID**, not the parsed text — if the cleanup algorithm needs fixing you can reparse without refetching (a refetch is ~3 s/video and hits the relay).
- Write the cache after **every** video, not at loop end; a timeout otherwise loses everything.
- Truncate transcripts to ~12k chars when writing note source JSON; long webinars get truncated anyway and workers must be told so they don't imply full coverage.
- Classify every outcome into a state file before building notes: `ok_vtt` / `cdp_ok` / `ytdlp_ok` (raw transcript cached — the tag records WHICH transport produced it, so reprocessing knows where the raw text lives: InnerTube relay cache, CDP srv3 JSON, or yt-dlp VTT), `no_tracks` (cookieless player OK, zero captionTracks — NOT yet permanent, see the cross-transport rule below), `unusable` (text that is ASR noise — fewer than ~12 real word tokens or under ~120 chars), `throttle:UNPLAYABLE` (rights-blocked — permanent, verified via the playability reason), `throttle` (retryable). Never fold throttle into no_tracks: that converts a retryable fetch failure into a false "the video has no subtitles" claim in the note.
- ASR transcripts of low-content videos (ASMR clips, single-word repeats) parse to a few dozen chars — screen BEFORE caching with a word-token count, not a length check, so the note's fallback warning matches reality instead of embedding word salad.
- Absence is final only as a CROSS-TRANSPORT double negative: the cookieless player returned zero captionTracks AND a cookie'd yt-dlp round over the same ID produced no subtitle files. The cookie jar changes what tracks YouTube serves — verified: roughly 8% of a no_tracks batch had ru/en subs retrievable ONLY through the cookie'd path. One transport's empty pass is not proof.
- Run batches through `scripts/ytdlp_sub_batch.sh` (file of IDs in, per-video `OK/ПУСТО` lines out, already-downloaded IDs skipped, resumable by rerun). Order the queue by state class — recoverable throttle first, hopeless candidates last — so the recoverable items never sit behind a doomed tail.

## yt-dlp with the user's Firefox cookies (works while every cookieless transport is throttled)

A logged-in cookie jar moves the request into a different rate-limit bucket: the same host that
429s every cookieless transport serves subtitles fine. Working invocation (verified: downloaded
`ru` + `en` VTT files for a video whose CDP transcript panel loaded zero segments):

```bash
export PATH="$HOME/.deno/bin:$PATH"   # deno: curl -fsSL https://deno.land/install.sh | sh -s -- -y
yt-dlp --js-runtimes deno --remote-components ejs:github \
  --cookies-from-browser 'firefox:~/snap/firefox/common/.mozilla/firefox/20wpd4km.default' \
  -f 'ba/b' --write-auto-sub --write-subs --sub-langs 'ru,en' --skip-download \
  -o '<outdir>/%(id)s' 'https://www.youtube.com/watch?v=<ID>'
```

- `--cookies-from-browser chrome` fails here: Chrome cookie decryption needs the desktop keyring,
  part of the jar comes back undecryptable, YouTube answers «Please sign in». The snap Firefox
  profile (`cookies.sqlite`) decrypts fully and works.
- `--js-runtimes deno` alone is NOT enough: without `--remote-components ejs:github` the
  n-challenge solver is skipped, format selection dies («Only images are available for download»
  / «Requested format is not available»), and subtitle files are NEVER written even though yt-dlp
  found them («Downloading subtitles: ru, en» proves the jar works). The remote-components flag
  is what makes the run succeed.
- Format selection must succeed for subtitle files to be written; `-f 'ba/b'` with
  `--skip-download` is fine.
- One command per video, no browser session to keep alive — run it on every `throttle`-classed
  video BEFORE escalating to CDP. The same video ID that the CDP panel fails on can succeed here;
  the cookie jar is what differs, not the video.
- The same invocation downloads the VIDEO itself when you drop `--skip-download` and select a
  video format (`-f 'mp4[height<=360]/b[height<=360]/b'`): verified 62 MB / 24 s for a 23-min
  360p video. That download is the source for the captionless-video study pipeline —
  youtube-metadata skill, `references/video-study-multimodal.md` (subtitles here, video study there).
