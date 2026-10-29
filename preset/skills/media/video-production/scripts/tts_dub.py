#!/usr/bin/env python3
"""
Russian TTS dubbing with precise segment timing using edge-tts.
Uses ThreadPoolExecutor for parallelism and -f flag for text input (REQUIRED).
Idempotent: skips already-generated segments. Mixes in batches to avoid ffmpeg limits.

Usage: python3 tts_dub.py [subtitles_json] [output_audio]
"""
import json, pathlib, subprocess, sys, os, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

WORKDIR = pathlib.Path.home() / "n8n-dub"
VOICE = "ru-RU-DmitryNeural"
MAX_WORKERS = 20
BATCH_MIX = 100
SEG_DIR_NAME = "tts_segments"

def parse_srt_time(ts):
    ts = ts.replace(',', '.')
    parts = ts.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

def get_duration(filepath):
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(filepath)],
            capture_output=True, text=True, timeout=10).stdout.strip()
        return float(probe) if probe else None
    except Exception:
        return None

def estimate_rate(text, dur):
    words = len(text.split())
    natural = (words / 130) * 60
    if dur < 0.3:
        return "+0%"
    if natural > dur * 1.1:
        pct = int((natural / dur - 1) * 100) + 10
        return "+{}%".format(min(pct, 100))
    return "+0%"

def tts_generate(text, output, rate="+0%"):
    """Generate TTS via subprocess using -f flag (REQUIRED — stdin does NOT work)."""
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', suffix='.txt', delete=False
        ) as tmp:
            tmp.write(text)
            tmp_path = tmp.name
        result = subprocess.run(
            ["edge-tts", "--voice", VOICE, "--rate", rate,
             "--write-media", str(output), "-f", tmp_path],
            capture_output=True, timeout=60
        )
        os.unlink(tmp_path)
        return (
            result.returncode == 0
            and output.exists()
            and output.stat().st_size > 100
        )
    except Exception as e:
        print("  TTS error:", e)
        return False

def mix_batch(segments, output, total_duration):
    """Mix segments via ffmpeg adelay + amix."""
    if not segments:
        return False
    inputs = []
    filter_parts = []
    for i, (audio_file, start_sec, dur_sec) in enumerate(segments):
        inputs.extend(["-i", audio_file])
        delay_ms = int(start_sec * 1000)
        filter_parts.append(
            "[{0}]adelay={1}|{1},atrim=0:{2},asetpts=PTS-STARTPTS[s{0}];".format(
                i, delay_ms, dur_sec))
    n = len(segments)
    mix = "".join("[s{}]".format(i) for i in range(n))
    filter_parts.append(
        "{}amix=inputs={}:duration=first:dropout_transition=0[out]".format(mix, n))
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", "".join(filter_parts),
        "-map", "[out]",
        "-acodec", "libopus", "-b:a", "48k",
        "-t", str(total_duration + 10),
        str(output)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print("  ffmpeg err:", result.stderr[:200])
    return result.returncode == 0

def main():
    json_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORKDIR / "subtitles_ru_final.json"
    output_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else WORKDIR / "n8n_course.ru.audio.opus"

    with open(json_path) as f:
        entries = json.load(f)

    valid = []
    for e in entries:
        text = e.get("text_ru", "").strip()
        if not text:
            continue
        start_sec = parse_srt_time(e["start"])
        end_sec = parse_srt_time(e["end"])
        dur = end_sec - start_sec
        if dur >= 0.3:
            valid.append((text, start_sec, dur))

    total = len(valid)
    total_duration = parse_srt_time(entries[-1]["end"])
    print("Processing {} segments, total: {:.1f}h".format(total, total_duration / 3600))

    seg_dir = WORKDIR / SEG_DIR_NAME
    seg_dir.mkdir(exist_ok=True)

    lock = threading.Lock()
    generated = [0]
    skipped = [0]
    failed = [0]

    def process_one(idx):
        text, start_sec, dur = valid[idx]
        out = seg_dir / "seg_{:06d}.mp3".format(idx)

        # Idempotent: skip existing valid files
        if out.exists() and out.stat().st_size > 100:
            d = get_duration(out)
            if d and d > 0.1:
                with lock:
                    skipped[0] += 1
                return (idx, str(out), start_sec, dur)

        rate = estimate_rate(text, dur)
        ok = tts_generate(text, out, rate)
        if not ok:
            ok = tts_generate(text, out, "+0%")

        with lock:
            if ok:
                generated[0] += 1
            else:
                failed[0] += 1
                print("  FAILED seg {}".format(idx))
        return (idx, str(out) if ok else None, start_sec, dur)

    # Process in parallel with ThreadPoolExecutor
    print("Generating TTS with {} workers...".format(MAX_WORKERS))
    all_seg_info = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(process_one, i): i for i in range(total)}
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            result = future.result()
            all_seg_info.append(result)
            if done_count % 1000 == 0:
                pct = done_count / total * 100
                print("  Progress: {:.1f}% (gen={}, skip={}, fail={})".format(
                    pct, generated[0], skipped[0], failed[0]))

    # Collect valid segments for mixing
    segments_for_mix = [(f, s, d) for (_, f, s, d) in all_seg_info if f is not None]
    print("\nMixing {} segments ({} failed) into master audio...".format(
        len(segments_for_mix), failed[0]))

    if len(segments_for_mix) <= BATCH_MIX:
        ok = mix_batch(segments_for_mix, output_path, total_duration)
    else:
        group_files = []
        for g in range(0, len(segments_for_mix), BATCH_MIX):
            chunk = segments_for_mix[g:g + BATCH_MIX]
            g_out = seg_dir / "mix_group_{:03d}.opus".format(g)
            print("  Mixing group {}-{}...".format(g, g + len(chunk)))
            if mix_batch(chunk, g_out, total_duration):
                group_files.append(str(g_out))

        if group_files:
            print("Combining {} groups...".format(len(group_files)))
            cmd = ["ffmpeg", "-y"]
            for gf in group_files:
                cmd.extend(["-i", gf])
            n = len(group_files)
            inputs_str = "".join("[{}]".format(i) for i in range(n))
            filter_str = "{}amix=inputs={}:duration=first[out]".format(inputs_str, n)
            cmd.extend(["-filter_complex", filter_str, "-map", "[out]",
                        "-acodec", "libopus", "-b:a", "48k",
                        "-t", str(total_duration + 10), str(output_path)])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            ok = result.returncode == 0
        else:
            ok = False

    if ok and output_path.exists():
        size_mb = output_path.stat().st_size / 1e6
        print("Done! {} ({:.0f} MB)".format(output_path, size_mb))
    else:
        print("ERROR: Mixing failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
