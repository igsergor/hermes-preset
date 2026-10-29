# Studying captionless videos with muse-spark-1.3-contributor (multimodal, Igor-approved pipeline)

When a video has NO caption track (verified cross-transport: cookieless player returns zero `captionTracks` AND a cookie'd yt-dlp round produced no subtitle files) but its meaning lives on screen/audio, do NOT write a title-only note and do not start with CDP screenshots. The approved pipeline: download locally → chop into 2-minute chunks → feed each chunk to the multimodal model → assemble the summary into the note → delete the local copy.

## Which models actually take video (verified live, Oct 2026)

Vendor docs claim video input for more models than the Zen proxy actually serves. Verified with a 10-s probe clip via `video_url` + base64 through `https://opencode.ai/zen/go/v1/chat/completions`:

**Work (verified live, Oct 2026):** `muse-spark-1.3-contributor` (responses API, `input_video`; 30-min clip OK: 79k input tokens, 25s). Older chat/completions probe results kept for fallback: `mimo-v2.6-flash`, `mimo-v2.6-pro`, `mimo-v2.5`, `minimax-m3`, `qwen3.7-plus`, `qwen3.8-flash`, `qwen3.8-max`, `kimi-k2.7-code`. Fallback order on spark trouble: mimo-v2.6-flash, then minimax-m3.

**Fail despite docs:** `kimi-k3` (400: `video_url` unsupported by upstream schema), `glm-5.3-flash` (400: only text+image_url), `deepseek-v4-flash-vision-exp` / `deepseek-v4.1-flash` (images only), gpt-luna + grok families (text+image only). Note: the sparks fail on the chat/completions path (`ModelProtocolUnsupported`) but take video fine on the responses path (`input_video`) — always match the model to its wire protocol before declaring it video-dead.

**Probe with production-size `max_tokens` (1600), never 300.** Below ~1200 the whole budget goes to `reasoning_tokens` and `content` comes back null — a healthy model reads as dead. Three mimo-family models false-negatived at 300 and passed at 1600.

## Pipeline

**Chunk size: 2 minutes, not 10.** This limit was measured on mimo-v2.6-flash: chunks longer than ~3 min intermittently hang it into multi-minute read-timeouts; a 2-min 480p chunk answers in ~30 s. Verified side by side: the same video's 2-min chunk returned in 28 s while its 3.7-min chunk timed out repeatedly. On muse-spark-1.3-contributor much larger single shots work (10-min and 30-min clips verified 200), so if the pipeline ever moves chunk size up, re-validate latency on the model actually in use — never inherit the 2-min cap as a universal law. Use `-t 120` and step the offset by 120 s.

1. **Download** — same cookie'd yt-dlp recipe as subtitles, but a video format and no `--skip-download`:
   ```bash
   export PATH="$HOME/.deno/bin:$PATH"
   yt-dlp --js-runtimes deno --remote-components ejs:github \
     --cookies-from-browser 'firefox:/home/igor/snap/firefox/common/.mozilla/firefox/20wpd4km.default' \
     -f 'mp4[height<=360]/b[height<=360]/b' --socket-timeout 30 \
     -o '/tmp/yt_study/%(id)s.mp4' 'https://www.youtube.com/watch?v=<ID>'
   ```
   Verified: 62 MB / 24 s for a 23-min video at 360p. `--cookies-from-browser chrome` fails (keyring decryption); use the snap Firefox profile. Rights-blocked (`UNPLAYABLE`) videos cannot be downloaded either — those stay with the rights reason in the note.
2. **Chunk** (≈30–60 s of ffmpeg per chunk on the server):
   ```bash
   ffmpeg -ss <start> -i in.mp4 -t 120 -vf scale=480:-2 -r 15 -c:v libx264 -preset fast -crf 30 -c:a aac -b:a 48k chunk.mp4
   ```
   **Delete stale chunk files before a rerun after changing CHUNK** (`rm workdir/chunk_*.mp4`): the pipeline reuses an existing `chunk_<vid>_<n>.mp4` if present and >10 KB, so chunks cut with the old chunk length keep poisoning reruns with exactly the size that hangs the model.
3. **Summarize each chunk** with the API below; chain context — pass the previous chunk's summary in the prompt («это продолжение видео, предыдущие фрагменты были о …, не пересказывай уже сказанное»), otherwise each chunk re-introduces the video from scratch.
4. **Assemble** chunk summaries (with `[M:SS]` chunk offsets) into the note's study section, then **delete the local mp4** before the next video — the deal is «скачал, посмотрел, записал, удалил». Injecting into an existing note: replace the whole `## 🎬 Транскрипт` section (its `> [!warning]` stub included) with an `> [!info]` block stating the video has no subtitles and the summary is a multimodal recap. Verify the note path from the IDs map still EXISTS on disk before writing — stale path maps (old spacing/collision fixes) turn the write into a silent no-op — and flip the state class to `recap_ok` in the same pass so reruns skip injected videos.

## muse-spark-1.3-contributor API (opencode-go subscription)

- Endpoint: `https://opencode.ai/zen/go/v1/responses`, Responses API.
- Headers: `Authorization: Bearer <KEY>` **and** `x-opencode-session: <any uuid>` — without the session header the API refuses with `MissingSessionID`.
- Key: `OPENCODE_GO_API_KEY` in `/home/igor/.hermes/.env`. NOT in `~/.config/opencode/opencode.jsonc` — there it is the literal placeholder `{env:OPENCODE_GO_API_KEY}`, not a key.
- Video input: `{'type':'input_video','video_url':'data:video/mp4;base64,...'}` with `reasoning: {'effort':'low'}` and `max_output_tokens: 4000`.
- **`max_output_tokens: 4000` + `reasoning.effort: low` validated for 2-min chunks.** Responses API, not chat/completions (chat path 400s on this model).
- **Video inference degrades under load/time of day: an exact request that answered in 28 s can later time out at 240 s+ while text-only requests keep answering in seconds.** That is server-side, not a payload bug — diagnose by re-running a KNOWN-GOOD request before rewriting working code. The retry ladder (5 attempts, 550 s read timeout, 30 s backoff) breaks through once the service recovers; leave a single pipeline running rather than debugging working code overnight.
- **Never run two video requests against this API at once** (pipeline + a manual diagnostic, or two pipelines): concurrent video calls on one subscription key deepen timeouts for both. Kill the pipeline before testing a payload manually, or wait for the current attempt to finish.
- HTTP client: `urllib` with its default UA gets Cloudflare `403 error code 1010` (UA fingerprinting). Use `curl` (subprocess) — verified end to end.
- Latency: 2-min chunk ≈ 30 s when the service is healthy. Retry 5× with 30-s pauses on empty/timeout responses.
- The model reads on-screen text and hears speech — verified: it recounts dictated narrator phrases and names shown on screen, so it replaces both screenshot study and ASR for this purpose.

Throughput budget: ~1 min per 2-min chunk (ffmpeg + summarize) → a 25-min video ≈ 15 min. 120+ videos ≈ 12–16 h machine time: run as a background job, make it idempotent (skip IDs with an existing summary; delete the mp4 after success so a rerun re-downloads only failures), and order the queue by expected yield (recoverable/short first, hopeless candidates last).

Script: `scripts/study_captionless.py` — file of video IDs in, per-video summaries out, local copies cleaned up.

## When NOT to use

- Subtitles exist → the transcript path is cheaper and higher fidelity; see the `youtube-transcript-fetch` skill.
- The video cannot be downloaded (no formats, member-only) → fall back to CDP screenshots of the playing player (youtube-metadata SKILL.md, CDP section).
- Rights-blocked (`UNPLAYABLE`) → download is impossible too; keep the rights reason as the note's fallback.

## Verifying UNPLAYABLE before writing the stub reason

An `UNPLAYABLE` classification from the player API is not yet the note's reason — the video may have been deleted outright since. Verify once with the cookie'd yt-dlp (same recipe as the download step, no download):

```bash
yt-dlp --js-runtimes deno --remote-components ejs:github --cookies-from-browser 'firefox:<profile>' \
  --skip-download --print '%(title)s|%(availability)s' 'https://www.youtube.com/watch?v=<ID>'
```

The error line is the note's reason, verbatim-classed: `Video unavailable` → «Видео недоступно (удалено/скрыто на YouTube)»; `This live stream recording is not available` → «Запись стрима удалена с YouTube». Both are permanent — record, mark the note's transcript section with the reason, and never retry. Do not run the multimodal pipeline on these: the download step fails with the same error, so there is nothing to study. Bulk check: loop the IDs through the one-liner, one per line of output; a right-holder block (`SME/WMG`) and a deleted video look identical in the player API but differ here — quote what yt-dlp actually says, not the older classification.
