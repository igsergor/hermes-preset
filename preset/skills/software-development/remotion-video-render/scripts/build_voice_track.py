#!/usr/bin/env python3
"""Build a timed voice+music track for a Remotion render.

Usage:
  python3 build_voice_track.py cues.json out.m4a [--music] [--cache DIR]

cues.json is a list of:
  {"name": "look", "text": "Look! A rainbow!", "delay_ms": 9000, "speed": 1.0}

- "delay_ms" is when the clip starts in the final track (compute from the
  component's scene frames as frame/30*1000).
- "speed" > 1.0 compresses a clip (ffmpeg atempo) to fit a scene.
- Each text is fetched once via Google translate_tts and cached by name, so
  reruns only refetch new/changed lines.
- --music overlays three quiet sine beds (0-22s, 18-40s, 29-43s) that fade in
  and out under the voice; drop it for a voice-only track.
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def fetch_tts(name: str, text: str, cache_dir: str) -> str:
    out = os.path.join(cache_dir, name + ".mp3")
    if os.path.exists(out) and os.path.getsize(out) > 100:
        return out
    url = (
        "https://translate.google.com/translate_tts?ie=UTF-8&q="
        + urllib.parse.quote(text)
        + "&tl=en&client=tw-ob"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=30).read()
    with open(out, "wb") as fh:
        fh.write(data)
    return out


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def build(cues, out, music: bool, total: float) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for c in cues:
        cmd += ["-i", c["file"]]
    if music:
        beds = [
            "0.09*sin(2*PI*523.25*t)+0.07*sin(2*PI*659.25*t)+0.05*sin(2*PI*783.99*t)",
            "0.08*sin(2*PI*440*t)+0.06*sin(2*PI*554.37*t+0.3)+0.05*sin(2*PI*659.25*t+0.7)",
            "0.10*sin(2*PI*587.33*t)+0.08*sin(2*PI*698.46*t)+0.05*sin(2*PI*880*t)",
        ]
        for b in beds:
            cmd += ["-f", "lavfi", "-t", "22", "-i", "aevalsrc='%s:s=48000'" % b]
    n_base = len(cues)
    filt = []
    labels = []
    for i, c in enumerate(cues):
        chain = "[%d:a]" % i
        sp = float(c.get("speed", 1.0))
        if abs(sp - 1.0) > 1e-3:
            chain += "atempo=%g," % sp
        d = int(c["delay_ms"])
        chain += "adelay=%d|%d[l%d]" % (d, d, i)
        filt.append(chain + ";")
        labels.append("l%d" % i)
    if music:
        specs = [(0.0, 2.0, None), (18.0, 11.0, 3.0), (29.0, 8.5, 2.0)]
        for j, (start, dur, out_fade) in enumerate(specs):
            idx = n_base + j
            f = "[%d:a]volume=0.55,adelay=%d|%d,afade=t=in:st=0:d=%g" % (idx, int(start * 1000), int(start * 1000), 2.0)
            if out_fade is not None:
                f += ",afade=t=out:st=%g:d=%g" % (dur - out_fade, out_fade)
            filt.append(f + "[bg%d];" % j)
            labels.append("bg%d" % j)
    filt.append("%samix=inputs=%d:normalize=0:dropout_transition=0[m];" % (
        "".join("[%s]" % l for l in labels), len(labels)))
    filt.append("[m]alimiter=limit=0.92,loudnorm=I=-15:TP=-1.5:LRA=11,"
                 "atrim=0:%g,asetpts=N/SR/TB[aout]" % total)
    cmd += ["-filter_complex", "".join(filt), "-map", "[aout]",
            "-ar", "48000", "-c:a", "aac", "-b:a", "128k", out]
    subprocess.run(cmd, check=True)
    print("wrote", out, duration(out), "s")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    cues_path, out = args[0], args[1]
    cache_dir = os.environ.get("TTS_CACHE", "/tmp/voice_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cues = json.load(open(cues_path))
    for c in cues:
        c["file"] = fetch_tts(c["name"], c["text"], cache_dir)
    total = max(float(c["delay_ms"]) / 1000.0 + duration(c["file"]) for c in cues) + 1.0
    build(cues, out, "--music" in flags, total)


if __name__ == "__main__":
    main()
