# Manim on Hermes — Environment Setup & Pipeline

## Installation on Hermes Ubuntu Server

The Hermes agent runs in a venv at `~/.hermes/hermes-agent/venv/`. Manim requires system-level dependencies:

```bash
# 1. Fix dpkg if interrupted
sudo dpkg --configure -a

# 2. System dependencies (all required)
sudo apt-get install -y pkg-config libcairo2-dev libpango1.0-dev

# 3. Python dependencies
pip3 install pycairo   # needs pkg-config + libcairo2-dev
pip3 install manim     # needs pycairo + libpango1.0-dev
```

**Common pitfalls:**
- `pycairo` fails with "Pkg-config for machine host machine not found" → install `pkg-config`
- `pycairo` fails with "Run-time dependency cairo found: NO" → install `libcairo2-dev`
- `manim` fails with "pangocairo not found" → install `libpango1.0-dev`
- If `dpkg` was interrupted, run `sudo dpkg --configure -a` first

## LaTeX

Manim's `MathTex` requires LaTeX (`texlive-full`). For children's videos with only `Text()`, LaTeX is NOT needed. Avoid `MathTex` if possible to skip the heavy LaTeX install.

## Rendering

```bash
# Draft (fast, 480p)
manim -ql script.py Scene1 Scene2 Scene3

# Production (1080p, slow)
manim -qh script.py Scene1 Scene2 Scene3
```

## Stitching Scenes

```bash
# Use ABSOLUTE paths in concat.txt
cat > /tmp/concat.txt << 'EOF'
file '~/media/videos/script/480p15/Scene1.mp4'
file '~/media/videos/script/480p15/Scene2.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i /tmp/concat.txt -c copy /tmp/output.mp4
```

**Important:** ffmpeg concat requires absolute paths. Relative paths break.

## Font

Use `"DejaVu Sans Mono"` on Linux (pre-installed). `"Menlo"` is macOS-only.

## Children's Video Style Tips

- Bright, saturated colors
- Simple shapes (circles for heads, rectangles for bodies)
- Large text (font_size >= 24)
- `LaggedStart` for sequential reveals
- `GrowFromCenter` for character entrances
- Avoid `MathTex` — use `Text()` only
- Keep scenes short (5-15 seconds each)

## Audio-Video Sync (learned 2026-05-28)

When TTS audio duration doesn't match video duration, **adjust audio speed, NOT video**:

```bash
# Wrong approach — setpts clips frames with concat:
# ffmpeg -i video.mp4 -vf "setpts=PTS*k" output.mp4  # DON'T

# Right approach — speed up audio with atempo:
SPEED=$(echo "$AUD_DUR / $VID_DUR" | bc -l)
ffmpeg -i audio.ogg -filter:a "atempo=${SPEED}" -y audio_fast.ogg

# Then merge:
ffmpeg -i video_noaudio.mp4 -i audio_fast.ogg -c:v copy -c:a aac -shortest final.mp4
```

`atempo` range is 0.5–2.0. Chain if factor exceeds range: `atempo=2.0,atempo=X`.
Verify final duration with `ffprobe final.mp4 2>&1 | grep Duration`.
