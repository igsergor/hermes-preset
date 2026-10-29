# Video Analysis Workflow

## Downloading Videos from GoFile.io

See `android-apk-build/references/gofile-api.md` for the full GoFile API reference.

Key points:
- Page URL returns HTML, not the file
- Get direct URL from browser: `document.querySelector('video').currentSrc`
- Download with `accountToken` cookie from browser session

## Extracting Frames for Analysis

```bash
mkdir -p /tmp/frames

# Extract 1 frame every 3 seconds
ffmpeg -i video.mp4 -vf "fps=1/3" -q:v 2 /tmp/frames/frame_%03d.jpg

# Extract at specific intervals (e.g., every 2 seconds for short videos)
ffmpeg -i video.mp4 -vf "fps=1/2" -q:v 2 /tmp/frames/frame_%03d.jpg

# Extract every frame (for very short videos < 5 sec)
ffmpeg -i video.mp4 -vf "fps=1" -q:v 2 /tmp/frames/frame_%03d.jpg
```

## Analyzing Frames

Use `vision_analyze` on each frame:
```
vision_analyze(image_url="/tmp/frames/frame_001.jpg", question="Describe all objects, text, colors, and arrangement in detail")
```

## Video Info

```bash
ffprobe -v error -show_format -show_streams video.mp4
```

Returns: codec, resolution, fps, duration, bitrate, number of frames
