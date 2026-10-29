---
name: ascii-creative
description: "ASCII art and ASCII video: text banners, terminal art, animated ASCII video production. Covers pyfiglet, cowsay, boxes, image-to-ascii, and full ASCII video pipeline."
version: 1.0.0
author: Hermes Agent (consolidated from ascii-art, ascii-video)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ascii, art, video, terminal, text-art, pyfiglet, cowsay, boxes, animation]
---

# ASCII Creative: Art & Video

Two related creative domains: **ASCII art** (static text/terminal art) and **ASCII video** (animated ASCII video production).

---

## Part 1: ASCII Art Tools

Multiple tools for different ASCII art needs. All are local CLI programs or free REST APIs.

### Text Banners (pyfiglet)
```bash
pip install pyfiglet --break-system-packages -q
python3 -m pyfiglet "YOUR TEXT" -f slant
python3 -m pyfiglet --list_fonts  # 571 fonts
```

| Style | Font | Best for |
|-------|------|----------|
| Clean & modern | `slant` | Project names, headers |
| Bold & blocky | `doom` | Titles, logos |
| Big & readable | `big` | Banners |
| Cyberpunk | `cyberlarge` | Tech themes |

### Remote API Alternative (no install)
```bash
curl -s "https://asciified.thelicato.io/api/v2/ascii?text=Hello+World"
curl -s "https://asciified.thelicato.io/api/v2/ascii?text=Hello&font=Doom"
```

### Cowsay (Message Art)
```bash
sudo apt install cowsay -y
cowsay "Hello World"
cowsay -f tux "Linux rules"
cowthink "Hmm..."
cowsay -l  # list all characters
```

### Boxes (Decorative Borders)
```bash
sudo apt install boxes -y
echo "Hello World" | boxes -d stone
echo "Hello World" | boxes -d cat
boxes -l  # list all 70+ designs
```

### Combine Tools
```bash
python3 -m pyfiglet "HERMES" -f slant | boxes -d stone
curl -s "https://asciified.thelicato.io/api/v2/ascii?text=HERMES&font=Slant" | boxes -d stone
```

### Image to ASCII
```bash
# ascii-image-converter (recommended)
sudo snap install ascii-image-converter
ascii-image-converter image.png -C -d 60,30

# jp2a (lightweight, JPEG only)
sudo apt install jp2a -y
jp2a --width=80 image.jpg
```

### Search Pre-Made ASCII Art
```bash
curl -s 'https://ascii.co.uk/art/cat' -o /tmp/ascii_art.html
# Then extract from <pre> tags with Python
```

### Fun Utilities
```bash
curl -s "qrenco.de/Hello+World"     # QR code as ASCII
curl -s "wttr.in/London"            # Weather as ASCII art
curl -s https://api.github.com/octocat  # Random Octocat
```

### LLM-Generated Custom Art
When tools don't have what's needed, generate directly using Unicode box-drawing characters. Max 60 chars wide, 15 lines for banners.

---

## Part 2: ASCII Video Production

Production pipeline for converting video/audio/images into colored ASCII character video output (MP4, GIF).

### Modes
| Mode | Input | Output |
|------|-------|--------|
| Video-to-ASCII | Video file | ASCII recreation of source |
| Audio-reactive | Audio file | Generative visuals from audio |
| Generative | None | Procedural ASCII animation |
| Hybrid | Video + audio | ASCII video with audio overlays |

### Stack
Single self-contained Python script. No GPU required.
- **Core**: Python 3.10+, NumPy
- **Signal**: SciPy (FFT, peak detection)
- **Imaging**: Pillow (font rasterization, frame I/O)
- **Video I/O**: ffmpeg (decode input, encode output)

### Pipeline
```
INPUT → ANALYZE → SCENE_FN → TONEMAP → SHADE → ENCODE
```

### Critical: Brightness
Use adaptive tonemap, never linear multipliers:
```python
def tonemap(canvas, gamma=0.75):
    f = canvas.astype(np.float32)
    lo, hi = np.percentile(f[::4, ::4], [1, 99.5])
    if hi - lo < 10: hi = lo + 10
    f = np.clip((f - lo) / (hi - lo), 0, 1) ** gamma
    return (f * 255).astype(np.uint8)
```

### Creative Standard
- First-render excellence is non-negotiable
- Dense, layered, considered — every frame rewards viewing
- Cohesive aesthetic across all scenes
- Per-scene variation in effects, palettes, colors

### References (from ascii-video skill)
- `references/architecture.md` — grid system, palettes, color system
- `references/effects.md` — effect building blocks, particles, transforms
- `references/shaders.md` — ShaderChain, transitions, encoding
- `references/scenes.md` — scene protocol, rendering, parallel rendering
- `references/inputs.md` — audio analysis, video sampling, TTS
- `references/optimization.md` — hardware detection, quality profiles
- `references/composition.md` — blend modes, tonemap, feedback
- `references/troubleshooting.md` — common pitfalls
