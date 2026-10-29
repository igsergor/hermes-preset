# FFmpeg Audio Assembly: Per-Part Approach (PREFERRED)

## Context

The window-based mixing approach (60s windows, 540 chunks) can silently produce -91 dB silence even when all source TTS files are normal (-20 dB). The failure mode is intermittent — some chunks fail silently and become digital zero.

## Preferred approach: Per-part assembly (600s parts)

Split the timeline into ~54 parts of 600 seconds (10 minutes) each. For each part:

1. Collect all TTS segments whose timestamps fall within that 10-minute window
2. Build a single ffmpeg command with `adelay` for each segment (offset relative to part start)
3. Mix delayed streams with `amix=inputs=N:normalize=0`  
4. Output as WAV (or Opus) — **verify immediately with volumedetect**
5. If part mean_volume ≈ max_volume < -80 dB → SILENT, debug before proceeding

**CRITICAL: Verify concatenation output too.** After concatenating all parts, immediately check the result. In production, 54 parts each at -20 dB concatenated to -91 dB (silent). Check that:
- Total duration = sum of part durations  
- Concat mean_volume is within ±3 dB of individual part volumes
- If concat is silent, re-mux parts: `ffmpeg -i part.wav -c copy part_fixed.wav` then re-concat

**Volume sanity check at each stage:**
```bash
ffmpeg -i part_00.wav -af volumedetect -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"
ffmpeg -i concat.wav -af volumedetect -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"
# Both should be ~-20 dB (TTS level) or ~-17 dB (after loudnorm)
# NEVER proceed if mean_volume ≈ max_volume < -80 dB
```

## Part verification checklist

```
[ ] Part builds successfully (ffmpeg exit code 0)
[ ] Part file size > 0
[ ] Part mean_volume > -30 dB
[ ] Part mean_volume NOT ≈ max_volume (if both < -80 dB → silent)
[ ] Part duration ≈ expected PART_SEC (600s)
[ ] AFTER ALL PARTS: concat mean_volume within ±3 dB of part mean_volume
```

## TTS segment index mapping

CRITICAL: Verify the index mapping between subtitles_parsed.json and TTS filenames.
JSON entries are 1-based (index: 1, 2, ...). TTS files are 0-padded (seg_000001.mp3, ...).
Verify seg_000001.mp3 corresponds to JSON index 1, not 0.

## loudnorm + AAC encoding (post-assembly)

```bash
# Step 1: loudnorm (30-60+ min for 9 hours — use timeout=None)
ffmpeg -y -i concatenated.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -acodec pcm_s16le normalized.wav

# Step 2: AAC encode (30-60+ min — use timeout=None)
ffmpeg -y -i normalized.wav -c:a aac -b:a 128k output.m4a

# Step 3: Verify AAC has audio
ffmpeg -i output.m4a -af volumedetect -f null /dev/null 2>&1 | grep mean_volume
# Expected: mean_volume ≈ -16 to -18 dB
```

**⚠️ WAV >4GB warning**: 9 hours PCM WAV = ~1.5GB. ffmpeg may warn "Filesize invalid for wav" — this is a header limitation, the audio data IS readable by ffmpeg. Do NOT panic. Proceed with AAC encoding.

**⚠️ Python subprocess timeout**: NEVER use `subprocess.run(timeout=600)` for audio processing of long files. Use `timeout=None` or at least `timeout=7200`.

## Complete pipeline timing (9-hour video, 14812 segments)

| Step | Time | Bottleneck |
|------|------|-----------|
| Per-part assembly (54 parts) | ~30 min | Forking ffmpeg per part |
| Part verification | ~5 min | volumedetect per part |
| Concatenation | ~2 min | Sequential write |
| Loudnorm | ~30 min | Single-pass filter |
| AAC encoding | ~60 min | Encoder on slow disk |
| **Total** | **~2 hours** | |

## Convergence with window-based approach

The old `ffmpeg_mixing_window_based.md` approach has the SAME per-part assembly idea but with smaller windows (60s instead of 600s). 60s windows mean 540 ffmpeg invocations vs 54, which is 10× slower for assembly AND makes it harder to isolate which window failed silently.

**Use 600s parts. Never 60s windows.**
