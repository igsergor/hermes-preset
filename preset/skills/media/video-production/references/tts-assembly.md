# TTS Assembly from Segments — Detailed Reference

## Problem
Assemble thousands of short TTS MP3 segments (each 2-15 seconds) into a single continuous audio track with correct timing to match subtitle positions, then normalize and encode to AAC for mobile playback.

## Why 60-Second Window Mixing Fails

The initial approach mixed TTS segments in 60-second windows using `amix`. This **silently produced -91 dB (complete silence)** for 9+ hour audio. The failure was not an ffmpeg error -- the command succeeded, but the output contained complete silence.

**Never use 60-second window mixing for long-form TTS assembly.**

## Correct Approach: Per-Part Assembly (600s parts)

Split into ~54 parts of 600 seconds (10 minutes) each. For each part, collect all TTS segments overlapping that time range, delay each to its position within the part, mix, and output. Then concatenate all parts.

### Working Pipeline

```
1. Build per-part audio (600s each, ~54 parts)
   For each part: adelay each TTS segment -> amix -> Opus output
   
2. Concatenate all parts -> single Opus file

3. loudnorm (EBU R128) -> normalize to -16 LUFS
   timeout: 3600s minimum for 9h audio

4. AAC encode (128kbps) -> .m4a
   timeout: 3600s minimum for 9h audio

5. Merge with video -> MP4 (copy video + audio)
```

### Expected Timing (VDA/slow disk)
- Per-part assembly: ~30s x 54 = ~27 min
- Concatenation: ~2-5 min
- Loudnorm: ~30-60 min
- AAC encode: ~30-60 min
- Total: ~2-3 hours

## TTS Baseline Levels (edge-tts, ru-RU-DmitryNeural)
- Format: MP3 24kHz mono
- Mean volume: -20 to -22 dB
- Max volume: -3 to -5 dB
- After loudnorm: mean ~= -16 to -18 dB

## Verification After Each Stage

**If mean_volume ~=-91 dB at any stage, STOP and debug immediately. Do NOT proceed.**

| Stage | Expected mean_vol |
|-------|-------------------|
| Raw TTS MP3 | -20 to -22 dB |
| After part assembly | -18 to -22 dB |
| After concatenation | -18 to -22 dB |
| After loudnorm | -16 to -18 dB |
| After AAC encode | -16 to -18 dB |
| Final MP4 chunk | -16 to -18 dB |

## Key ffmpeg Parameters

- adelay=DELAY|DELAY: delay in ms (mono: repeat same value)
- amix=inputs=N:normalize=0: mix without normalization
- loudnorm=I=-16:TP=-1.5:LRA=11: EBU R128 to -16 LUFS
- -movflags +faststart: streaming-optimized MP4
- -reset_timestamps 1: reset timestamps when chunking
