# Audio Assembly and Telegram Delivery (2026-06-01)

Session: N8N FULL COURSE — 9h dubbed audio assembly and chunked delivery.

## Audio Assembly Pipeline (What Actually Ran)

### Stage 1: TTS Generation
- 18 parts × ~30min each
- Continuous text + atempo approach (not per-segment)
- Each part: concat TTS groups → measure natural duration → atempo to match target → verify
- Mean volume per part: -21.3 dB (natural edge-tts output)
- Each part MP3: ~6.9MB

### Stage 2: Concat + Loudnorm
```
ffmpeg -f concat -i concat_parts.txt -acodec libmp3lame -ar 22050 -ac 1 dubbed_raw.mp3
ffmpeg -i dubbed_raw.mp3 -af "loudnorm=I=-16:TP=-1.5:LRA=11" -acodec libmp3lame -ar 22050 -ac 1 dubbed_norm.mp3
```
- dubbed_raw.mp3: 124MB, 9.01h
- dubbed_norm.mp3: 124MB (loudnorm doesn't change file size much)
- **Took ~30 minutes** — ffmpeg must read entire 9h to compute loudnorm stats

### Stage 3: AAC Encode (for MP4 container)
```
ffmpeg -i dubbed_norm.mp3 -c:a aac -b:a 128k -ar 22050 -ac 1 dubbed_audio.aac
```
- dubbed_audio.aac: 369MB at 128kbps
- **Took ~15 minutes**

### Stage 4: Merge with Video
```
ffmpeg -y -i video.mp4 -i dubbed_audio.aac -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -movflags +faststart n8n_course_ru.mp4
```
- Final: 1.2GB, 9:00:19
- **Took ~2 minutes** (stream copy, no re-encode)

## The 50MB Telegram Problem

**Initial segmentation (1800s = 30min, `-c:a copy`):**
- Produced 18 parts, 57-92MB each
- 6 parts exceeded 50MB Telegram Bot API limit
- part_000: 61MB → "Request Entity Too Large"

**Fix: Re-encode audio at lower bitrate + shorter segments:**
```
ffmpeg -y -i n8n_course_ru.mp4 \
  -c:v copy -c:a aac -b:a 64k -ar 22050 -ac 1 \
  -f segment -segment_time 900 \
  -reset_timestamps 1 -movflags +faststart \
  output/part_%03d.mp4
```
- Produced 36 parts, 18-32MB each ✅ all under 50MB
- **Re-encoding took ~15 minutes** for 9h audio at 64kbps

## Key Lessons

1. **`-c:a copy` preserves original bitrate.** If the original AAC is 128kbps, segments WILL be large. You MUST re-encode to reduce size, which costs 15-90 minutes for long files.

2. **Test first with one segment before committing to full re-encode.** Check if `-c:a copy` segments happen to be under 50MB (depends on video complexity). If they are, skip the expensive re-encode.

3. **The 50MB limit is for Bot API only.** Telegram user clients accept up to 2GB. But since we send via bot, we're stuck at 50MB.

4. **Volume verification on long files:** Don't run full-file volumedetect. Sample at 3 timestamps (beginning, middle, end) using `-ss HH:MM:SS -t 10`.

5. **Re-encode strategy guideline:**
   - 64kbps AAC → ~28MB per 10min segment (safe)
   - 48kbps AAC → ~20MB per 10min segment (very safe, slightly degraded quality)
   - 128kbps AAC copy → ~60MB per 15min segment (exceeds limit)

## Verification Results

All 36 parts verified with spot-check volumedetect:
- part_000: -16.8 dB ✅
- part_017: -16.9 dB ✅  
- part_035: -16.8 dB ✅

All parts have audio (n_samples > 0).
