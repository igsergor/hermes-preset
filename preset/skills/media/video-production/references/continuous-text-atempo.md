# Continuous Text + atempo Approach — 2026-05-31

## User Request

After multiple iterations of per-segment timing (v8-v19) with issues:
- Overlapping voices from coincident subtitles
- Unnatural pauses between segments from different time slots
- Speed variations causing unpleasant listening

User suggested: "Synthesize the entire piece as-is — without timings — i.e. glue all replicas into one text and synthesize it whole, or by sentences, then fit the total dubbing to the original total timing."

## Algorithm Implemented

1. Take all 200 subtitles from chunk 000
2. Split into 278 sentences (re.split on [.!?])
3. TTS each sentence with edge-tts (ru-RU-DmitryNeural, +0%)
4. Concatenate with ffmpeg concat demuxer
5. Measure: 827.7s natural duration
6. Target: 483.7s
7. Apply atempo=1.711 → 483.79s
8. Apply loudnorm=I=-16 → 483.77s, -16 dB

## Result

- Duration match: 483.77s vs 483.7s (error 0.07s)
- Perfectly uniform speed
- No gaps, no overlaps
- Natural continuous speech flow

## Comparison with Per-Segment Approach

Per-segment: timing precision but overlapping voices, gaps, speed variation.
Continuous text: no timing precision but natural flow, uniform speed, no artifacts.

## edge-tts Text Length Limit

Edge-tts silently times out on texts >~5000-8000 characters. For chunk 000:
- Full text: 7576 chars → timeout
- Split into 278 sentences → each 20-100 chars → works fine

**Always split long texts into sentences before calling edge-tts.**

## When to Use Each Approach

Continuous text approach is better when:
- Natural speech flow is priority
- Subtitle overlap is severe (>50%)
- User prefers "audiobook" style over "dubbed video" style

Per-segment approach is better when:
- Lip-sync matters
- Original timing has meaningful pauses
- User wants dubbed-video feel

## Next Steps (if user approves)

1. Apply same approach to all 75 chunks
2. Each chunk: concatenate text → TTS by sentence → concat → atempo → loudnorm
3. Concatenate all chunks
4. Merge with video

## Telegram Media Delivery Issue — CRITICAL

`send_message(media=...)` ALWAYS routes to the configured home channel, NOT the current conversation. In this session, all audio files went to the wrong chat and the user couldn't find them. **Lesson**: Don't assume `send_message` delivers to the current conversation. Inform the user that media delivery via bot is unreliable.

## User Reaction

File was generated successfully (483.77s, -16 dB) but delivery failed — user couldn't find the audio. The approach itself needs user approval before scaling to full video.
