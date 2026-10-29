---
name: generative-visual
description: "Generative visual art: p5.js sketches, Manim math animations, and infographic generation. Browser-based creative coding, 3Blue1Brown-style explainers, and visual summaries."
version: 1.0.0
author: Hermes Agent (consolidated from p5js, manim-video, baoyu-infographic)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [generative-art, p5js, manim, infographic, creative-coding, animation, math-visualization]
---

# Generative Visual Art

Three distinct tools for programmatic visual generation: **p5.js** (interactive browser sketches), **Manim** (math/algorithm animations), and **Infographics** (visual summaries from content).

---

## Section 1: p5.js (Interactive Browser Sketches)

Use for creative coding, generative art, interactive visualizations, canvas animations, shader effects, 3D scenes, and audio-reactive visuals.

### Output formats
HTML, PNG, GIF, MP4, SVG — exported as self-contained browser-based sketches.

### Rendering modes
- 2D rendering with noise/particle systems/flow fields
- WebGL scenes with GLSL shaders
- Pixel manipulation and kinetic typography
- Audio analysis (mouse/keyboard interaction)
- Headless high-res export

### Creative Standard
- Browser canvas is the medium; algorithmic craft is the standard
- Visual complexity + interaction > static beauty
- Each sketch should have at least one interactive element or audio-reactive feature

---

## Section 2: Manim (Math/Algorithm Animations)

Use for 3Blue1Brown-style explainer videos, algorithm visualizations, equation derivations, architecture diagrams, and data stories.

### Prerequisites
- Python 3.10+, Manim Community Edition v0.20+ (`pip install manim`)
- LaTeX (texlive-full on Linux, mactex on macOS)
- ffmpeg

### Pipeline
```
PLAN → CODE → RENDER → STITCH → AUDIO (optional) → REVIEW
```

### Modes
| Mode | Input | Output |
|------|-------|--------|
| Concept explainer | Topic/concept | Animated explanation |
| Equation derivation | Math expressions | Step-by-step animated proof |
| Algorithm visualization | Algorithm description | Execution with data structures |
| Architecture diagram | System description | Components building up |
| 3D visualization | 3D concept | Rotating surfaces, spatial geometry |
| Paper explainer | Research paper | Key findings animated |

### Critical Rules
- **Raw strings for LaTeX**: `MathTex(r"\frac{1}{2}")` — never without `r` prefix
- **Subtitles on every animation**: `self.add_subcaption("text", duration=N)`
- **FadeOut before replacing text**: `ReplacementTransform(note1, note2)`
- **Clean exits**: FadeOut all mobjects at scene end

### Color Palettes
| Palette | Background | Primary | Use case |
|---------|-----------|---------|----------|
| Classic 3B1B | `#1C1C1C` | `#58C4DD` | General math/CS |
| Warm academic | `#2D2B55` | `#FF6B6B` | Approachable |
| Neon tech | `#0A0A0A` | `#00F5FF` | Systems, architecture |

### Typography
Use monospace fonts for all text (Pango renderer produces broken kerning with proportional fonts). Minimum font_size=18.

### Audio-Video Sync
ALWAYS adjust audio to match video duration, never use `setpts` to stretch video:
```bash
SPEED=$(echo "$AUDIO_DUR / $VIDEO_DUR" | bc -l)
ffmpeg -i scene_audio.ogg -filter:a "atempo=$SPEED" -y scene_audio_fast.ogg
```

### References
- `references/animations.md` — core animations, rate functions, composition
- `references/mobjects.md` — Text, shapes, VGroup, positioning
- `references/visual-design.md` — design principles, opacity, layout
- `references/equations.md` — LaTeX in Manim, derivation patterns
- `references/graphs-and-data.md` — Axes, plotting, algorithm visualization
- `references/camera-and-3d.md` — MovingCameraScene, ThreeDScene
- `references/scene-planning.md` — narrative arcs, planning template
- `references/rendering.md` — CLI reference, quality presets, voiceover
- `references/troubleshooting.md` — LaTeX errors, animation errors
- `scripts/setup.sh` — dependency verification

---

## Section 3: Infographics (Visual Summaries)

Use for creating infographics from content (text, files, URLs, topics). Two dimensions: **layout** (information structure) × **style** (visual aesthetics).

### Options
| Option | Values |
|--------|--------|
| Layout | 21 options (bento-grid default) |
| Style | 21 options (craft-handmade default) |
| Aspect | landscape (16:9), portrait (9:16), square (1:1), custom |
| Language | en, zh, ja, etc. |

### Workflow
1. **Analyze** content → save `analysis.md`
2. **Structure** content → save `structured-content.md` (verbatim, no summarization)
3. **Recommend** 3-5 layout×style combinations
4. **Confirm** options with user
5. **Generate** prompt → save `prompts/infographic.md`
6. **Generate** image via `image_generate` tool
7. **Report** summary

### Keyword Shortcuts
| Keyword | Layout | Style |
|---------|--------|-------|
| 信息图 / infographic | `bento-grid` | `craft-handmade` |
| 高密度信息大图 | `dense-modules` | `morandi-journal`, `pop-laboratory` |

### Data Integrity
NEVER summarize, paraphrase, or alter source statistics. "73% increase" must stay "73% increase".

### References
- `references/analysis-framework.md` — analysis methodology
- `references/structured-content-template.md` — content format
- `references/base-prompt.md` — prompt template
- `references/layouts/<layout>.md` — 21 layout definitions
- `references/styles/<style>.md` — 21 style definitions
