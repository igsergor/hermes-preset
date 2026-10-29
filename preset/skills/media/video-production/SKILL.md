---
name: video-production
description: "Video/audio processing and dubbing pipeline: ffmpeg operations, TTS dubbing, subtitle translation, Telegram delivery. Use for any video/audio processing, dubbing, transcoding, or chunking task."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [video, audio, ffmpeg, dubbing, TTS, subtitles, Telegram, processing]
    related_skills: [video-production]
---

# Video Production

Complete video/audio processing pipeline: ffmpeg operations, TTS dubbing with timing, subtitle translation, and Telegram delivery.

## Quick Decision Guide

| Task | Section |
|------|---------|
| Dub video (EN→RU or any language) | → §1 Dubbing Pipeline |
| ffmpeg: convert, chunk, merge, normalize | → §2 ffmpeg Operations |
| Cut out a segment / trim a video to a time range | → §2 ffmpeg Operations |
| TTS segment assembly & speed matching | → §3 TTS & Audio Assembly |
| Subtitle translation at scale | → §4 Subtitle Translation |
| Deliver via Telegram | → §5 Telegram Delivery |

---

## §1 Dubbing Pipeline (EN→RU)

Full pipeline: download → extract subtitles → translate → TTS → assemble → merge → verify → deliver.

### Prerequisites

```bash
pip install yt-dlp deep-translator edge-tts
# ffmpeg must be installed
# OPENROUTER_API_KEY in ~/.hermes/.env
```

### Pipeline Overview

```
Video URL → yt-dlp download
         → Extract EN subtitles (SRT)
         → Parse → segments with timestamps
         → Translate to Russian (parallel LLM API)
         → TTS dubbing (edge-tts, speed-adjusted)
         → Per-part audio assembly
         → loudnorm → AAC encode
         → Merge video + dubbed audio
         → Verify → Chunk for Telegram → Deliver
```

### Step 1: Download

```bash
yt-dlp --write-auto-sub --sub-lang en --sub-format srt \
  -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
  -o "~/dub-workdir/video.%(ext)s" "YOUTUBE_URL"
```

**Note:** Actual output includes format ID (e.g., `video.f302.webm`). Always `ls *.webm *.mkv` to find the real filename.

### Step 2: Translate (Parallel LLM API)

- Split into chunks of ~200 segments
- Launch 8–12 parallel background processes via `terminal(background=true)`
- Model: `openrouter/owl-alpha` (free, ~30s per 50 lines)
- **Do NOT use `delegate_task`** — it times out at 600s

### Step 3: TTS Dubbing

- Voice: `ru-RU-DmitryNeural` (male) or `ru-RU-SvetlanaNeural` (female)
- Use `ThreadPoolExecutor` (20 workers), not asyncio
- **Speed matching**: Russian TTS ~1.75× longer than English. Use `atempo` filter per segment.
- **Overlapping subtitles**: 14719 of 14811 pairs overlap. Use speed-matching algorithm, NOT naive mixing.

### Step 4: Audio Assembly (CRITICAL)

**❌ WRONG (produces -91 dB silence):** 60-second window mixing with amix
**✅ CORRECT:** Per-part assembly (600s parts)

1. Build ~54 intermediate WAV/Opus files (600s each)
2. Each part: `adelay` each TTS segment → `amix=normalize=0`
3. Concatenate all parts → `loudnorm` → AAC encode

### Step 5: Merge & Verify

```bash
ffmpeg -y -i source_video.webm -i dubbed_audio.aac.m4a \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -movflags +faststart output.mp4
```

**Verify BEFORE delivery:**
- `mean_volume > -25 dB` (if ≈ -91 dB, track is SILENT)
- `n_samples > 0`
- Spot-check 3 timestamps (beginning, middle, end)

### Timing Realities (8+ hour video)

| Stage | Time |
|-------|------|
| yt-dlp download | 5-15 min |
| Translation | 25-40 min |
| TTS generation | 40-60 min |
| Concat + Loudnorm | 30-40 min |
| AAC re-encode | 60-90 min |
| **TOTAL** | **~3-4 hours** |

### Key Pitfalls

- **Verify at EVERY stage** — silence at any stage poisons all downstream output
- **ffmpeg timeout**: Foreground terminal calls are clamped (~420s) regardless of the requested timeout — any ffmpeg pass that may run longer (volume detect on 30min+ files, concat/loudnorm on 8h+ files, any full re-encode of a multi-minute clip) must run as `terminal(background=True, notify=True)`; a timeout kill leaves a truncated, unplayable output behind
- **yt-dlp invocation**: often absent from PATH — `pip install yt-dlp`, then call `python3 -m yt_dlp ...`
- **Shell `$var` in `python3 -c`**: Never inline shell variables. Use `sys.argv` or env vars.
- **OPENROUTER_API_KEY**: Skip commented lines and `***` masked values in `.env`
- **Telegram 50MB limit**: Re-encode at `-b:a 64k` with `-segment_time 900`

---

## §2 ffmpeg Operations

### Volume Analysis

```bash
ffmpeg -i input -af "volumedetect" -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"
```

For long files (>30min), sample at 3 timestamps instead:
```bash
ffmpeg -ss 00:00:30 -t 10 -i input.mp4 -af volumedetect -f null -y /dev/null 2>&1 | grep mean_volume
ffmpeg -ss 04:00:00 -t 10 -i input.mp4 -af volumedetect -f null -y /dev/null 2>&1 | grep mean_volume
ffmpeg -ss 08:00:00 -t 10 -i input.mp4 -af volumedetect -f null -y /dev/null 2>&1 | grep mean_volume
```

### Trimming / Cutting a Segment

To hand the user a standalone clip (e.g. "cut from 19:40 to the end"):

1. Download best quality: `python3 -m yt_dlp -f "bv*+ba/b" --merge-output-format mp4 -o "source.%(ext)s" URL`
2. Get duration first: `python3 -m yt_dlp -j URL | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['duration'])"` — never assume where "to the end" ends
3. Cut with `-ss` BEFORE `-i` plus re-encode — this is frame-accurate (seek then decode). `-c copy` cuts only at keyframes and drifts by seconds:

```bash
ffmpeg -y -ss 00:19:40 -i source.mp4 -t <SECONDS> \
  -c:v libx264 -threads 8 -preset veryfast -b:v 1200k -maxrate 1400k -bufsize 2800k \
  -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart clip.mp4
```

4. Bitrate target: compute from the §5 formula for the clip's true duration (`-t` seconds), not the source length
5. Verify: `ffprobe -v error -show_entries format=duration,size` — duration must equal the requested span
6. Budget the encode: 1080p60 (esp. AV1 sources) transcodes ~1-2× realtime on 8 cores, so even a 5-minute clip exceeds the foreground clamp — launch with `background=True, notify=True` from the start

### AAC Conversion

```bash
# CORRECT:
ffmpeg -i input.mkv -c:v copy -c:a aac -b:a 128k \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -movflags +faststart output.mp4
```

### Chunking for Telegram

```bash
ffmpeg -i input.mp4 -c:v libx264 -b:v 360k -preset fast \
  -c:a aac -b:a 48k -f segment -segment_time 600 \
  -reset_timestamps 1 -movflags +faststart chunk_%03d.mp4
```

**Verify every chunk is under 50MB**: `ls -lh chunk_*.mp4`

### Format Compatibility

| Container | Video | Audio | Android | Telegram |
|-----------|-------|-------|---------|----------|
| MP4 | H.264 | AAC | ✅ | ✅ |
| MP4 | VP9 | AAC | ✅ (most) | ✅ |
| MKV | VP9 | Opus | ❌ audio | ✅ |

### Frame Analysis (Object Inventory)

```bash
mkdir -p frames
ffmpeg -i input.mp4 -vf fps=1/10 frames/frame_%03d.png
# Then analyze each frame with vision_analyze
```

---

## §3 TTS & Audio Assembly

### Per-Part Assembly Algorithm

```python
# For each 600s part:
# 1. Collect all TTS MP3 segments in that time range
# 2. adelay each segment to its offset within the part
# 3. amix all delayed segments for that part
# 4. Concatenate all parts → loudnorm → AAC encode
```

### TTS Speed Adaptation

- Generate TTS at natural speed (+0% rate)
- Measure raw duration with ffprobe
- `atempo = raw_dur / available_dur`
- Max atempo: 2.0 (chain for higher: `atempo=2.0,atempo=R/2.0`)
- Smooth transitions: max ±0.04-0.08× change between adjacent segments

### Alternative: Continuous-Speech Dubbing

When per-segment timing produces artifacts:
1. Join all subtitle text into one string
2. Split into ~1800-char parts (edge-tts limit)
3. TTS each part, concat without gaps
4. Apply uniform `atempo` to match target duration

---

## §4 Subtitle Translation

For translating thousands of subtitle segments via OpenRouter API:

1. Parse yt-dlp JSON → clean `{start, end, text}` array
2. Split into 200-segment chunks
3. Translate 12 chunks in parallel via OpenRouter API
4. Merge and sort by timestamp
5. Expect ~97% translation rate (rate limits cause ~3% loss)

---

## §5 Telegram Delivery

### Three Methods

| Method | Size Limit | Use |
|--------|-----------|-----|
| `MEDIA:` prefix | Verified delivering 44MB mp4 on this install; stay under the 50MB bot cap | Small/medium single files in trusted dirs |
| python-telegram-bot | 50MB per file | Arbitrary files |
| External hosting (Gofile.io) | 10GB | Files >50MB |

### Chunking for Telegram Bot API (50MB Limit)

```bash
# Calculate safe bitrate:
# target_video_kbps = (target_MB * 8192 / duration_seconds) - audio_kbps
# For 45MB, 900s, 48k audio: (45*8192/900) - 48 ≈ 361k video

ffmpeg -y -i input.mp4 \
  -c:v libx264 -b:v 361k -preset fast \
  -c:a aac -b:a 48k -movflags +faststart output.mp4
```

### Audio Format

Telegram on Android does NOT play Opus in MKV. Always use AAC:
```bash
ffmpeg -i input.mkv -c:v copy -c:a aac -b:a 128k output_aac.mkv
```

---

## References

- `references/tts-assembly.md` — Per-part assembly pipeline
- `references/tts-speed-adaptation.md` — atempo-based speed adjustment
- `references/tts-continuous-speech.md` — Gapless continuous-speech dubbing
- `references/ffmpeg-pitfalls.md` — Session-learned pitfalls
- `references/subtitle-translation-workflow.md` — Batch translation via API
- `references/continuous-text-atempo.md` — Continuous text + atempo approach
- `references/parallel-translation.md` — Parallel LLM translation
- `references/audio-assembly-delivery.md` — Audio concat/loudnorm/AAC, ffmpeg timeouts
