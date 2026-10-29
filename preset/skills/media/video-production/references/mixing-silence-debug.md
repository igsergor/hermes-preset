# Audio Mixing Silence Bug — Session 2026-05-30

## Root Cause: -91 dB "Silent" Track

**Symptom**: TTS segments individually have normal volume (~-20 dB mean), but after mixing all segments into a single continuous track, the result has mean_volume = -91 dB and max_volume = -91 dB (digital silence — flat line).

**Root cause**: The window-based mixing approach using `amix=duration=first` produced output equal to the SHORTEST input window (5.9s instead of 60s), causing massive data loss. The truncated result had silence for 59/60 seconds of each window, yielding an almost entirely silent track.

**Key insight**: -91 dB is NOT "quiet audio" — it's digital silence. Any time you see mean_volume ≈ max_volume ≈ -91 dB, the track contains essentially no audio signal. Always compare mean and max: if they're nearly equal and below -80 dB, the track is broken.

## Correct Approach: Per-Part Assembly

1. Split timeline into ~600s (10 min) parts (~54 parts for 9 hours)
2. For each part:
   - Collect TTS segments overlapping that window
   - Build ONE ffmpeg command with all segment inputs + `adelay` per segment + `amix`
   - Output as WAV (or Opus for size)
   - **IMMEDIATELY verify**: `ffprobe` or `volumedetect` on the part output — mean_volume MUST be > -30 dB
3. Concatenate all verified parts → final audio
4. Apply `loudnorm` → AAC encode
5. Verify final output AGAIN

**Part verification is CRITICAL**: Verify each part IMMEDIATELY after creation, before concatenating. If any part is silent, fix before proceeding.

## Verification Trap — Multi-Stage Problem

The DANGEROUS pattern:
1. Verify TTS sources: ✓ (-20 dB, ~14,812 files)
2. Mix sources into single track: **NOT VERIFIED** → -91 dB silence
3. Convert silence to different format: -91 dB silence (preserved)
4. Merge silence with video: silent video
5. Deliver silent video to user

**Rule**: Verify at EVERY intermediate stage — TTS, mixing, concatenation, format conversion, final merge. Never assume a stage worked because no error was thrown.

## Volume Level Reference

| Level | Meaning |
|-------|---------|
| -91 dB | Digital silence (flat line or rounding noise) |
| -80 dB | Effectively silent on all devices |
| -30 dB | Quiet but audible on headphones |
| -20 dB | Normal speech (edge-tts output level) |
| -17 dB | Good target after loudnorm |
| -16 dB | EBU R128 broadcast standard target |
| 0 dB | Full scale, clipping |

## Correct Loudnorm Usage

```bash
# WAV → loudnorm → WAV (slow, 30+ min for 9 hours on slow disk)
ffmpeg -y -i input.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -acodec pcm_s16le output.wav

# WAV → loudnorm → AAC in one pass
ffmpeg -y -i input.wav -c:a aac -b:a 128k -af "loudnorm=I=-16:TP=-1.5:LRA=11" output.m4a
```

**TIME WARNING**: Both commands take 30-60+ minutes for 9-hour audio. NEVER use Python `subprocess.run(timeout=600)`. Use `timeout=None` or `timeout=7200`.

## Segment Index Mapping

Verify subtitle JSON index maps 1:1 to `seg_NNNNNN.mp3` filenames:
```python
# JSON entries start at index 1:
# {"index": 1, "start_sec": 0.08, ...}
# TTS file: seg_000001.mp3 ← must match
```

## yt-dlp Output Filename

Actual downloaded filename includes format ID (e.g., `n8n_course.f302.webm`). Always `ls *.webm *.mkv` to find actual names before referencing in commands.