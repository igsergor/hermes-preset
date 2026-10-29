# TTS Speed Matching & Punctuation-Based Pauses — Detailed Reference

## Problem Evolution

### v1-v3: Naive mixing → double voice
Used adelay+amix. Overlapping subtitles → two voices simultaneously.

### v4-v8: atempo speed matching
Each TTS compressed to fit slot. Speed varied wildly → unnatural.

### v9-v14: Uniform speed + punctuation pauses
Better, but gaps between segments → noticeable pauses.

### v15-v19: Final working solution
- Uniform speed ~1.75x with smooth drift correction
- Batch adelay+amix (batches of 20-25)
- Pauses ONLY at punctuation (. = 250ms, , = 100ms)
- NO inter-segment gaps
- Duration: 478s (target 484s)

## Final Algorithm

For each subtitle i:
1. available_dur = en[i+1].start - en[i].start
2. Generate TTS at +0% rate, measure raw duration
3. atempo = raw_dur / available_dur
4. If atempo > 2.0: regenerate at +100%, recalculate
5. Apply smooth speed with drift correction
6. Place at timeline using batch adelay+amix
7. Add punctuation pauses WITHIN segment only

## Key Numbers
- RU/EN ratio: ~1.7-1.8x
- Uniform speed: ~1.75x
- Atempo precision: ±20ms per segment
- Max speed deviation: ±0.10x
- Max adjacent change: 0.02-0.03x
- Punctuation: . = 250ms, , = 100ms

## Placement Rules
- Between segments: NO gap, concat immediately
- At period: 250ms pause
- At comma: 100ms pause
- Overlap: OK, timing handles it

## What NOT To Do
- Add silence between segments
- Use amix for de-overlapping
- Use amerge for timeline mixing
- Let speed vary >0.10x between adjacent
