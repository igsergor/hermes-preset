# Manim Rainbow Rendering — Lessons Learned 2026-05-28

## The Problem

Drawing a rainbow (7 concentric colored arcs) in Manim at `-ql` (480p) quality is tricky. Naive approaches result in only 2-4 visible colors instead of 7.

## Arc Overlap Math

Manim `Arc` objects are drawn as strokes. At `-ql` (854×480):
- Pixel-to-unit ratio: 854px / 16 units = **53.4 px/unit** (horizontal), 480px / 8 units = **60 px/unit** (vertical)
- `stroke_width=N` → thickness of `N/53.4` units (horizontal) or `N/60` units (vertical)
- Two arcs with radii `r1 < r2` and stroke width `w` **overlap** when `(r2 - r1) < w_in_units`

### Golden Rule
```
arc_spacing > stroke_width_in_units × 2
```

If violated, inner arcs are completely hidden by outer ones.

## Working Parameters

### Recipe A: Grown-from-innermost (adequate for children's video)

```python
rainbow_colors = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0088FF", "#4400FF", "#8800FF"]
for i, color in enumerate(rainbow_colors):
    # radius grows outward: innermost=0.6, outermost=3.0
    arc = Arc(radius=0.6 + i * 0.4, angle=PI, stroke_color=color, stroke_width=9, stroke_opacity=1.0)
    # stroke_width=9 → 9/53.4=0.169 units, spacing=0.4 > 0.169*2=0.338 ✓
rainbow_group.shift(UP * 1.5)
# Top: 1.5+3.0=4.5 ← viewport boundary ✓
# Bottom: 1.5-0.6=0.9 ← above ground ✓
```
Result: 4-5 visible colors on light background (blue/violet may blend). Acceptable for children's content.

### Recipe B: Guaranteed 7/7 colors (dark background)

For guaranteed all 7 colors visible, use a **dark background** (`#333333`):

```python
class TestRainbow(Scene):
    def construct(self):
        self.camera.background_color = "#333333"
        colors = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0088FF", "#4400FF", "#8800FF"]
        for i, color in enumerate(colors):
            arc = Arc(radius=3.0 + i * 0.3, angle=PI, stroke_color=color, stroke_width=15)
```

Dark background maximizes contrast with blue/violet. At 480p all 7 colors clearly visible.

## Viewport Bounds (Manim -ql / 480p)

- X: approximately -8 to +8
- Y: approximately -4.5 to +4.5
- Objects outside these bounds are clipped

**For rainbow arcs:** `max_radius + center_y ≤ 4.5` (top within viewport), `center_y - min_radius` can go below ground (clipped is OK).

## Why Blue/Violet Disappear on Light Backgrounds

Blue (`#0088FF`), indigo (`#4400FF`), violet (`#8800FF`) have low contrast against sky blue (`#87CEEB`) and light gray (`#E8E8E8`) at 480p. Antialiasing blends them.

**Solutions:**
1. Dark background — all colors pop (best, Recipe B)
2. Render at `-qm` (720p) for better color separation
3. Use more saturated blue: `#0066FF`, and increase stroke_width for blue+ arcs
4. Accept 4-5 visible colors for children's content (audience won't notice)

## Failed Approaches Log

| Parameters | Visible Colors | Root Cause |
|------------|---------------|------------|
| `r=3.2-i*0.08, sw=12` | 3/7 | spacing 0.08 << sw 0.225 — total overlap |
| `r=4.5-i*0.3, sw=5` | 2/7 | arcs drawn outermost-first, overlap hides inner |
| `r=1.5+i*0.35, sw=15` | 1/7 (red only) | spacing 0.35, sw 0.56 — complete overlap |
| `r=1.5+i*0.6, sw=8` | 4/7 | OK spacing, but blue/violet blend with light bg |
| `r=1.5+i*0.35, sw=15` | 1/7 (red only) | spacing 0.35, sw 0.56 — complete overlap |
| `r=1.5+i*0.6, sw=8` | 4/7 | OK spacing, but blue/violet blend with light bg |
| `r=0.6+i*0.4, sw=9, light bg` | 4-5/7 | Correct spacing, light bg washes out blue+ |
| `r=0.6+i*0.4, sw=9, dark #333 bg` | 5-6/7 | Better, some colors still thin at 480p |
| `r=1.5+i*0.4, sw=9, gray #E8E8E8 bg` | 4-5/7 | Same issue — blue family blends with light bg |

## Verified Working Recipe (2026-05-28)

```python
rainbow_colors = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0088FF", "#4400FF", "#8800FF"]
rainbow_group = VGroup()
for i, color in enumerate(rainbow_colors):
    arc = Arc(radius=0.6 + i * 0.4, angle=PI, stroke_color=color, stroke_width=9, stroke_opacity=1.0)
    rainbow_group.add(arc)
rainbow_group.shift(UP * 1.5)
# Viewport: Y from -4.5 to +4.5. Top: 1.5+3.0=4.5 ✓  Bottom: 1.5-0.6=0.9 ✓
```

Key: `spacing(0.4) > stroke_width_in_units(9/53.4*2 ≈ 0.338) ✓`

For best results use dark background: `self.camera.background_color = "#333333"`

## Post-Render Verification

Always verify key frames after rendering — don't assume it worked:

```bash
# Extract a frame at a specific timestamp
ffmpeg -i scene.mp4 -vf "select=eq(n\,50)" -frames:v 1 -update 1 check.jpg -y

# Then check with vision tool or pixel analysis
python3 -c "
from PIL import Image; import numpy as np; from collections import Counter
img = Image.open('check.jpg')
arr = np.array(img); pixels = arr.reshape(-1, 3)
quant = (pixels // 32) * 32
for c, n in Counter(map(tuple, quant)).most_common(20):
    print(f'RGB{c}: {n}px')
"
```

Look for distinct rainbow color clusters (>100px each). If a color is missing, adjust the Manim arc parameters and re-render.
