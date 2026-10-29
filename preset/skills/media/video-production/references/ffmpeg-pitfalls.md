# ffmpeg Pitfalls — Session-Learned

## 1. `volume=60dB` filter doesn't actually boost

**Symptom:** `ffmpeg -i in -c:a aac -af volume=60dB out.mp4` → mean_volume still -91 dB
**Cause:** The volume filter operates in the pipeline but may not apply when combined with codec conversion in certain scenarios
**Fix:** Use `loudnorm=I=-16:TP=-1.5:LRA=11` instead

## 2. `-c:a aac` produces empty track (n_samples: 0)

**Symptom:** `ffmpeg -i in.mkv -c:v copy -c:a aac out.mp4` → ffprobe shows nb_samples: 0
**Cause:** Likely related to source being mono low-sample-rate or Opus→AAC pipeline issue
**Fix:** Add `-af loudnorm` to force audio processing pipeline, or use two-pass: Opus→WAV→AAC

## 3. `-segment_time` with `-c copy` produces empty chunks

**Symptom:** `ffmpeg -i in.mp4 -c copy -segment_time 360 -f segment chunk_%03d.mp4` → chunks have `{}` (no streams)
**Cause:** Segment cutting with stream copy at non-keyframe boundaries can fail silently
**Fix:** Re-encode video when chunking, or use `-force_key_frames` before cutting

## 4. Opus in MKV doesn't play on Android

**Symptom:** MKV with VP9+Opus plays fine on PC but has no audio on Android/Telegram
**Cause:** Android's default player doesn't support Opus audio in MKV container
**Fix:** Convert to MP4 with AAC audio, or remux Opus into MP4 container (less compatible)

## 5. TTS segments via edge-tts subprocess (not asyncio)

**Symptom:** asyncio `communicate()` with edge-tts produces 0-byte files
**Cause:** edge-tts may not flush stdout properly in async mode
**Fix:** Use `subprocess.run()` with explicit args instead of asyncio

## 6. volumedetect timing

`ffmpeg -i in.9h.mkv -af volumedetect -f null /dev/null` takes ~5+ minutes for 9-hour video.
Run it in background, don't block on it.

## 7. TTS segment mapping off-by-one

**Symptom:** Double-voice effect — two TTS voices play simultaneously.
**Cause:** TTS segments named with 0-based index (seg_000000.mp3) but subtitle indices are 1-based. Build script maps sub #N → seg_N instead of seg_N-1.
**Fix:** When building the segment index, use `idx = sub['index'] - 1` to map 1-based subtitle index to 0-based segment filename.

## 8. Overlapping subtitles require speed adaptation

**Symptom:** Double-voice even with correct mapping.
**Cause:** Original subtitles overlap in time (next sub starts before current ends). When TTS plays each sub at natural speed, overlapping segments produce two voices.
**Fix:** Use ffmpeg `atempo` filter to compress TTS segments to fit non-overlapping time slots. See [tts-speed-adaptation.md](tts-speed-adaptation.md).
