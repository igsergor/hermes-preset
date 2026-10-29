# FFmpeg Audio Conversion Gotchas for Video Dubbing

## Problem: `-c:a aac` with MKV/Opus source produces empty audio

When remuxing MKV (Opus audio) to MP4 (AAC), ffmpeg may silently produce an empty AAC track:

```bash
# This CAN fail silently:
ffmpeg -i input.mkv -c:v copy -c:a aac -b:a 128k output.mp4
# Result: video plays, audio track exists, n_samples=0 (silence)
```

### How to detect

```bash
ffmpeg -ss 60 -t 5 -i output.mp4 -vn -acodec pcm_s16le -f wav /tmp/check.wav 2>/dev/null
ffmpeg -i /tmp/check.wav -af "volumedetect" -f null /dev/null 2>&1 | grep "n_samples"
# n_samples: 0 → EMPTY, conversion failed
# n_samples: 240000+ → OK, audio present
```

### Workaround: WAV intermediate

```bash
# Step 1: Extract audio to WAV
ffmpeg -i input.mkv -vn -acodec pcm_s16le temp_audio.wav

# Step 2: Mux with AAC encoding
ffmpeg -i input.mkv -i temp_audio.wav \
  -c:v copy -c:a aac -b:a 128k \
  -map 0:v:0 -map 1:a:0 \
  output.mp4
```

### Resolution: per-part assembly

The window-based approach that produced -91 dB silence has been replaced with the **per-part assembly** approach (600s parts, ~54 parts for 9 hours). This approach:
- Outputs WAV per-part (no codec issues during assembly)
- Makes per-part verification easy and reliable
- Allows per-part failure recovery (re-run just the bad part)

See `references/ffmpeg_mixing_per_part.md` for the complete approach.

## ⚠️ CRITICAL: TTS assembly can produce SILENT output even when source files are normal

**This is the #1 dubbing pitfall.** When assembling 14,000+ TTS segments into a single audio track using ffmpeg window-based mixing, the output can be completely silent (mean_volume -91 dB) even though every source MP3 has normal volume (-20 to -22 dB).

### How it manifests

- `ffprobe` on final assembled audio: `mean_volume: -91.0 dB, max_volume: -91.0 dB` — total silence
- Source TTS MP3s: `mean_volume: -20.6 dB, max_volume: -3.2 dB` — normal speech
- The mixing/assembly step is where the signal is lost

### Root cause

The window-based mixing approach (60s windows, adelay + amix + concat) can silently fail:
- Some window ffmpeg commands fail and produce silence fallback
- The `-t WINDOW` truncation in window output cuts off audio
- Chunks with errors silently become digital zero

### Detection: ALWAYS verify after EVERY assembly step

```bash
# After assembly, BEFORE merging with video:
ffmpeg -i assembled_audio.opus -af "volumedetect" -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"

# -91 dB → SILENT. Do NOT proceed to merge with video.
# -20 to -30 dB → Normal TTS level (before loudnorm).
# -16 to -20 dB → Good, after loudnorm.
```

### Detection: spot-check intermediate chunks

```bash
for f in /tmp/achunk_0001.opus /tmp/achunk_0100.opus /tmp/achunk_0300.opus; do
    echo -n "$f: "
    ffmpeg -i "$f" -af "volumedetect" -f null /dev/null 2>&1 | grep "mean_volume"
done
# Chunks with content: mean_volume > -50 dB
# Silent chunks (-91 dB): investigate those windows
```

### Prevention: verify-first pipeline

```
TTS sources → spot-check MP3s → assemble per-window → verify EACH window →
concat → verify concat → loudnorm → verify → WAV intermediate → AAC → verify →
merge with video → verify final
```

NEVER skip verification. Each step can silently fail.

## Problem: edge-tts TTS audio level

Normal edge-tts output: **mean_volume -20 to -22 dB, max_volume -3 to -5 dB**.

If your TTS source files show -91 dB: TTS generation itself failed (not an assembly issue).

## Reliable loudnorm targeting

```bash
-af "loudnorm=I=-16:TP=-1.5:LRA=11"
# I=-16: target integrated loudness -16 LUFS
# TP=-1.5: max true peak -1.5 dB
# LRA=11: loudness range 11 LU
```

## Problem: volume filter has no effect

If `volume=XDB` doesn't change output level:
1. The source is already silent (-91 dB = digital zero). Cannot amplify silence.
2. Fix the upstream issue (TTS or assembly), not the gain.
3. `loudnorm` also cannot fix true silence — it needs nonzero input.

## Verification checklist before delivering

```bash
# 1. Verify TTS SOURCE (before assembly)
ffmpeg -i tts_segments/seg_000001.mp3 -af "volumedetect" -f null /dev/null 2>&1 | grep "mean_volume"
# Expect: ~-20 dB. If -91 dB: TTS failed.

# 2. Verify ASSEMBLED audio (before video merge)
ffmpeg -i assembled_audio.opus -af "volumedetect" -f null /dev/null 2>&1 | grep -E "mean_volume|n_samples"
# Expect: > -50 dB. If -91 dB: assembly broken.

# 3. Verify FINAL output
ffmpeg -ss 60 -t 5 -i final.mp4 -vn -acodec pcm_s16le -f wav /tmp/check.wav 2>/dev/null
ffmpeg -i /tmp/check.wav -af "volumedetect" -f null /dev/null 2>&1 | grep "n_samples"
# n_samples MUST be > 0

# 4. Spot-check multiple timestamps
for t in 60 300 1800 7200 14400; do
    ffmpeg -ss $t -t 3 -i final.mp4 -vn -acodec pcm_s16le -f wav /tmp/t.wav 2>/dev/null
    echo -n "t=${t}s: "
    ffmpeg -i /tmp/t.wav -af "volumedetect" -f null /dev/null 2>&1 | grep "mean_volume" | head -1
done
# ALL timestamps: mean_volume > -50 dB
```

**Golden rule: The user should NEVER be your QA tester. Verify BEFORE delivering.**
