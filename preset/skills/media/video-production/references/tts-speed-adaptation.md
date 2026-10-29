# TTS Speed Adaptation for Dubbing

## Problem

When dubbing from English to Russian, Russian TTS takes 1.3-1.8x more time than English speech in the same subtitle slots. This causes:

1. **Overlapping subtitles**: Original EN subs overlap (speaker starts next line before finishing current — 14719 of 14811 pairs). At natural speed, TTS overlaps = double voice.
2. **Off-by-one mapping bug**: TTS segments named `seg_000000.mp3` (0-based) but subtitle indices are 1-based. Sub #1 looks up `seg_files[1]` = `seg_000001.mp3` = actual TTS for sub #2. Every segment one subtitle early.
3. **Drift**: Accumulated timing differences cause audio to go out of sync.

## CRITICAL: Duration Accuracy Requirement

**The final dubbed video MUST match the original video duration within ~0.05-0.1s.** Fragments are concatenated later — any drift accumulates and causes visible desync at fragment boundaries.

```python
target_dur = chunk_en[-1]["end_sec"] - chunk_en[0]["start_sec"]
# Acceptable error: < 0.1s
```

## Approaches Tested (n8n Full Course, 9h, 14812 subs)

| Version | Approach | Speed Range | Result |
|---------|----------|-------------|--------|
| v4 | Hard compress all to fit 95% of slot | 1.3x+ | Double voice gone but chipmunk |
| v12 | Natural 1.0x + 150ms micro-gaps | 1.0x | **Approved by user. Natural voice** |
| v19 | Uniform global speed, per-sub atempo | 1.69-2.11x | Global speed too aggressive |
| v21 | 60s blocks + sentence boundaries | 1.67-2.11x | Speed changes too frequent |
| v22 | 180s blocks + sentence boundaries + amix+aevalsrc | 1.81-2.91x | Uncorrected amix truncation |
| v23 | Iterative overlap elimination | 1.3-2.5x | **DIVERGED — never use** |
| v24 | Continuous timeline, no punct pauses | 1.72-1.74x | Exact duration, no overlaps, 17s drift |

## RECOMMENDED: Option B — Per-Sub Snap-to-Original with Local Overlap Trim

When dubbed video must match original duration AND stay synced.

**Algorithm:**
```
1. Compute global speed: speed = sum(nat_dur) / (video_dur - N*GAP), GAP=0.05
2. For each sub i:
   ideal_dur = nat_dur[i] / speed
   max_dur = min(next_start - cur_start - GAP, end_sec - start_sec + 0.3)
   actual_dur = min(ideal_dur, max_dur)
   if actual_dur < ideal_dur: sub_speed[i] = nat_dur[i] / actual_dur  # local speedup
3. Redistribute unused time to non-clipped subs proportionally
4. Generate TTS at local speeds via atempo
5. Place at original start_sec via adelay from video_start
6. amix all + aevalsrc padding + duration=longest
```

Only ~10-20% of subs get clipped (where overlap > 30%). Most stay at original position = good sync.

**Speed constraints:** Min 1.3x, Max 3.0x (local), typical 1.7-2.0x.

## Option A: Natural Speed + Micro-Gaps (User-Approved v12)

When natural voice quality is priority and longer dub duration OK.

```python
SPEED = 1.0
MICRO_GAP = 0.15  # 150ms between segments
```

## Option C: Sentence-Block Variable Speed (v22)

When sentence-aligned speed variation desired. 180s blocks at .!? boundaries.

## Option D: Continuous Timeline (v24)

WARNING: accumulates 10-17s drift vs original timeline. Only for non-lip-sync content.

## CRITICAL: Do NOT Use Iterative Correction

Simple iterative speed correction (increase → smooth → repeat) **diverges** (v23: -70s → -150s error). Compute analytically + single global trim multiplier.

## CRITICAL: ffmpeg Amix Duration Fix

```python
ref = "".join(f"[d{j}]" for j in range(N))
filt.append(f"aevalsrc=0:d={video_dur+1.0}[pad]")
filt.append(f"{ref}[pad]amix=inputs={N+1}:duration=longest:normalize=0[mix]")
```
Use `-t {video_dur + 1.0}` on output.

## CRITICAL: One amix For All Segments — No Batches

Do NOT mix in batches of 25 and concat. Creates inter-batch delay gaps.

**Correct**: Single amix with all N segments (200 inputs works fine, ~2-3min).

## CRITICAL: Adelay From video_start

```python
# CORRECT
offset_ms = int(max(0, (chunk_en[i]["start_sec"] - video_start)) * 1000)
# WRONG (batch-local)
offset_ms = int(max(0, (chunk_en[i]["start_sec"] - batch_start_time)) * 1000)
```

## Punctuation Pauses: Minimal Only

Do NOT use 0.25s/0.10s per punctuation. Sums to 40+ sec wasted. Use fixed 0.05s gap.

## Atempo Chain

```python
def build_atempo(speed):
    fl = []; rem = speed
    while rem > 2.0: fl.append("atempo=2.0"); rem /= 2.0
    while rem < 0.5: fl.append("atempo=0.5"); rem /= 0.5
    fl.append(f"atempo={rem:.4f}")
    return fl
```

## Subprocess Pitfall

```python
subprocess.run(cmd, timeout=60)    # CORRECT
subprocess.run(cmd, duration=60)   # WRONG — TypeError
```

## Verification Checklist

1. `abs(dubbed_dur - original_dur) < 0.1s`
2. `mean_volume > -25 dB`
3. Speed range 1.3-3.0x, adjacent delta < 0.08x
4. No double voice at block boundaries
5. amix output length matches video duration

## Expected Properties (9h EN → RU)

| Metric | Value |
|--------|-------|
| Overlapping subtitle pairs | ~99% |
| Avg overlap | 2.16s |
| Natural RU/EN ratio | 1.3-1.8x |
| Working compressed speed | 1.7-2.1x |
