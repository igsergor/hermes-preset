# Browser Rendering on Hermes — What Doesn't Work

## Empty Page Screenshots

The Hermes browser tool runs on a remote Linux server without display/GPU. Canvas-based rendering (p5.js, HTML5 Canvas) often results in **empty page snapshots** even when the DOM is correct. The canvas element exists but renders blank.

**Don't waste time trying:**
- p5.js sketches via `browser_navigate` + screenshot
- HTML5 Canvas animations rendered headless
- Any approach relying on browser GPU/compositing

**What works:**
- Static HTML/CSS rendering for text-based pages
- `browser_console` + `expression` for reading DOM state (JS evaluation works)
- `browser_click`, `browser_text`, `browser_press` for form interaction
- `browser_scroll` for scrolling

## Workaround for Animation/Video Generation

Use **Manim** instead of browser-based animation for Hermes server environments. Manim renders server-side using Cairo + ffmpeg with no display needed.
