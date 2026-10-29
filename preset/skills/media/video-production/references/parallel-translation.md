# Parallel Translation: Shell Scripts, Timing, and Pitfalls (2026-06-01)

Session: N8N FULL COURSE (9h video) — 14,812 subtitles, 75 chunks, 12 parallel workers.

## What Worked

### Translation Pipeline Architecture
- `translate_chunk.py` reads `subs.json`, translates a range, writes full array with only its range translated
- `run_all_translate.sh` launches 7 batches of 12 parallel workers
- `merge_chunks.py` merges all chunk JSONs into `subs_ru.json`
- Total time: ~24 minutes for 14,812 segments

### Parallel Launch Pattern
```bash
for batch in $(seq 0 6); do
    BATCH_START=$((batch * 12))
    BATCH_END=$((BATCH_START + 12))
    [ $BATCH_END -gt 75 ] && BATCH_END=75
    for i in $(seq $BATCH_START $((BATCH_END - 1))); do
        bash run_chunk.sh $i &
    done
    wait
done
```

### Shell Quoting Pattern for run_chunk.sh
```bash
read START END <<< $(python3 -c "
import json
total = len(json.load(open('/home/igor/dub-workdir/subs.json')))
start = $CHUNK * 200
end = min(start + 200, total)
print(start, end, total)
")
```

### Polling Strategy: Count Output Files
**DO NOT poll PIDs** — transitive bash→python chains make PID tracking unreliable. Count output files instead:
```bash
ls chunks/chunk_*.json | wc -l
```

## What Failed and Was Fixed

### 1. OPENROUTER_API_KEY Loading from .env

**Problem:** `~/.hermes/.env` has MULTIPLE `OPENROUTER_API_KEY=*** lines. The old loader read a commented example with `***`, tried to use it → 401 on every call.

**Fix:** Skip `#` comments, skip values containing `***`, validate length > 20:
```python
def load_api_key():
    env_path = os.path.expanduser('~/.hermes/.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'): continue
                if line.startswith('OPENROUTER_API_KEY=') and '***' not in line:
                    val = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if val and len(val) > 20: return val
    return os.environ.get('OPENROUTER_API_KEY', '')
```

### 2. Shell/Python Quoting in Shell Scripts

**Problem:** `python3 -c "print($VAR)"` — if $VAR is empty or has spaces, the command breaks silently. Always pass shell vars via sys.argv:
```python
python3 -c "import sys; print(int(sys.argv[1]) * 200)" "$CHUNK"
```

### 3. volumedetect Timeout

**Problem:** `subprocess.run(cmd, timeout=120)` for ffmpeg volumedetect on 9h file → TimeoutExpired.

**Fix:** Use `timeout=600` for files >30min, `timeout=3600` for >1h. Or sample at 3 timestamps instead.

### 4. TTS Script Killed by Terminal Timeout

**Problem:** `terminal(background=true, timeout=180)` killed TTS before completion (each 30min part takes 3-5 min).

**Fix:** Use `execute_code` with `subprocess.Popen` for long-running processes, or timeout >= 600s.

## Timing Benchmarks (9h video)

| Stage | Time | Notes |
|-------|------|-------|
| yt-dlp download (480p) | ~8 min | 830MB |
| Translation (75 chunks x 12 parallel) | ~24 min | OpenRouter API |
| TTS (18 parts x 6 parallel) | ~40 min | edge-tts bottleneck |
| Concat + Loudnorm | ~30 min | |
| AAC re-encode (64kbps) | ~15 min | For Telegram 50MB limit |
| Merge + Segment | ~5 min | |
| **TOTAL** | **~2.5 hours** | |

## Disk Usage Notes

75 chunk JSON files x 14812 segments each = ~500MB wasted. Optimization: make translate_chunk.py output ONLY its range, not the full array.
