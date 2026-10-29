# TTS Continuous-Speech Dubbing Approach

## When to Use This Approach

When the goal is natural-sounding dubbing **without per-segment timing**, and the overall chunk duration just needs to match the original. This works well when:
- Subtitle overlap is extreme (>95% of segments overlap)
- Per-segment double-voice artifacts are unacceptable
- User prefers one continuous speech flow without pauses between segments

## The Algorithm

```
1. Join ALL subtitle text in the chunk into ONE string (separated by space)
2. Split into edge-tts-friendly parts (~1800-2000 chars each, at sentence boundaries)
   - edge-tts has a ~3000-4000 char limit per call; stay well under
3. Generate TTS for each part (edge-tts, +0% rate = natural speed)
4. Concatenate parts with NO gaps between them
5. Compute atempo = sum(all_part_durations) / target_duration
6. Apply uniform atempo to the joined audio
7. Normalize (loudnorm=I=-16)
```

## Key Formulas

```
target_duration = last_sub_end - first_sub_start  (from subtitle timings)
atempo = sum(natural_tts_durations) / target_duration
# Result: pitch-preserving uniform speed change
```

## Critical Pitfalls

### MP3 encoding adds silence
Re-encoding MP3→MP3 adds encoder delay/padding (~50-100ms per file). For precise duration matching:
- Use WAV intermediate for atempo application
- Only encode to final MP3 at the last step
- Use `-ar 44100 -ac 1` for WAV to keep sizes manageable

### atempo precision
- Compute `atempo = sum_orig / target` using actual measured durations (ffprobe on each part)
- Do NOT estimate from character count — actual TTS speed varies by text content
- For chunk_000 (~8 min): atempo ~1.16-1.17 (mild speedup, sounds natural)

### Verify duration at EVERY stage
```bash
# After concat (before atempo)
ffprobe -v quiet -show_entries format=duration -of csv=p=0 joined.wav
# After atempo
ffprobe -v quiet -show_entries format=duration -of csv=p=0 joined_fast.wav
# After MP3 encode — this is what the user gets
ffprobe -v quiet -show_entries format=duration -of csv=p=0 final.mp3
# MP3 encoding can change duration by 0.1-0.5s — if off, adjust atempo and retry
```

### Duration miscalculation trap
The `target_duration` is NOT the sum of subtitle durations. It's:
```
target = sub[N-1].end - sub[0].start
```
i.e., from the start of the first subtitle to the end of the last subtitle in the chunk.

## Comparison with Per-Segment Approach

| Aspect | Per-Segment (old) | Continuous Speech (new) |
|--------|-------------------|------------------------|
| Pauses between segments | Yes (at punctuation) | No — one continuous flow |
| Speed | Variable per segment | Uniform across chunk |
| Double-voice risk | High with overlapping subs | None |
| Naturalness | Can sound choppy | More natural, audiobook-like |
| Duration matching | Per-segment drift correction | Global atempo |
| Computation | Complex (per-segment atempo, drift) | Simple (one atempo value) |

## Known Good Parameters (ru-RU-DmitryNeural, n8n course)

| Parameter | Value |
|-----------|-------|
| Chunk size (chars) | ~1800-2000 per edge-tts call |
| Target loudness | -16 LUFS (loudnorm=I=-16) |
| Sample rate | 44100 Hz |
| Channels | mono |
| atempo range | 1.1-1.3 (mild, sounds natural) |

## Example: chunk_000 (200 subs, ~483.7s)

```
200 subs → " ".join(texts) = 7576 chars
→ 5 parts × ~1600-1900 chars
→ TTS: 145+132+138+136+13 = 564.6s natural
→ atempo = 564.6/483.7 = 1.167
→ Concat 5 WAVs → apply atempo → encode MP3 → loudnorm
→ Final: 483.6s, -17.1dB, gapless
```
