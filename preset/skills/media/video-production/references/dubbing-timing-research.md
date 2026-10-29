# Video Dubbing: Timing Problem Landscape

## Research Findings (June 2026)

### Open Source Solutions Surveyed

| Project | Stars | Approach to Timing |
|---------|-------|-------------------|
| SoniTranslate (R3gm) | 1.4k | pydub overlay + `avoid_overlap` (shift start forward 0.2-0.5s). No speed compression. |
| CreatorBox | 182 | CosyVoice/Index-TTS. Timing not documented. |
| Python-Autodub | 2 | F5-TTS + Demucs. Timing not documented. |
| VidLingo | new | "Retimed composition" — details not public. |

**Key insight**: No open-source project solves the fundamental TTS timing problem well. SoniTranslate's `avoid_overlap` simply shifts segment starts forward — it doesn't try to fit TTS within original time slots.

### Approaches That DONT Work

1. **Iterative speed correction** — diverges. Smoothing undoes correction. Error grows each iteration.
2. **Batched amix** (25 segments per batch, then concat) — creates inter-batch delay gaps.
3. **Continuous timeline with no pauses** — gapless but accumulates 10-17s drift because original subs overlap.
4. **Hard clip at next_start** — cuts off 40%+ of speech because overlaps are 2+ seconds.
5. **Punctuation-based pauses** (0.25s period, 0.10s comma) — wastes 40+ seconds that could be speech.

### Recommended Approach: Hybrid Per-Sub Snap-to-Original

1. Compute global speed analytically: `speed = sum(nat_dur) / (video_dur - N * 0.05)`
2. For each sub, check if TTS fits before next sub starts
3. If not: locally speed up just that sub (up to 3.0x)
4. Redistribute freed time to other subs proportionally
5. Place each TTS segment at original `start_sec` (not continuous positions)
6. Single amix call with all segments + aevalsrc padding

This keeps 80-90% of subs at original position (perfect sync) and only modifies the problematic overlapping ones.

## Tools That Could Help

- **WhisperX** — forced alignment to find exact speech timing in original audio. Could be used to generate better `start_tts` timestamps.
- **ffmpeg atempo** — pitch-preserving speed change (range 0.5-2.0, chain for wider range).
- **pydub** — SoniTranslate uses this for overlay-based mixing (Python-native, slower than ffmpeg).
