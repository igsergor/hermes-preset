# Process Health Verification Pattern

When monitoring long-running background processes (whisper, TTS generation, ffmpeg encoding),
don't just poll for exit status. Proactively verify the process is making progress.

## Finding the Real Process

When using `terminal(background=true)` with Python one-liners, the process tree is:
```
bash (PID from terminal) → python3 (actual worker) → {python3} threads
```

Always find the Python child:
```bash
pstree -p <bash_pid>
# or
ps --ppid <bash_pid>
```

The bash wrapper will show VmRSS ~5MB and State S. The Python process shows actual memory usage.

## Checking Process Health

```bash
# 1. Memory usage (should be growing, not stuck)
cat /proc/<python_pid>/status | grep -E "VmRSS|VmSwap|Threads|State"

# Expected for whisper medium: VmRSS ~1500-2000 MB, Threads 16+
# Expected for idle/stuck: VmRSS < 100 MB (just the wrapper)

# 2. What's it waiting on?
cat /proc/<python_pid>/wchan
# futex = normal (waiting for thread)
# pipe_wait = waiting for I/O
# perf_event_read = possible hang

# 3. Is it making syscalls?
timeout 5 strace -p <python_pid> -c -f 2>&1 | tail -10
# Should show active syscalls (read, write, mmap, etc.)
# If empty or all futex — may be stuck

# 4. CPU usage
top -bn1 -p <python_pid> | tail -2
# Should show >30% CPU for compute-bound tasks
# 0% for extended period = possible hang

# 5. Log tail
tail -5 <logfile>
# Check for progress indicators
```

## Whisper-Specific Checks

```bash
# Log for whisper shows:
# Line 1: "Loading medium model..." (takes 1-2 min)
# Line 2: "Transcribing..." (then nothing until done)
# If only 2 lines after 10+ min → still working OR stuck

# Check Python process memory:
# Loading: VmRSS growing from 0 → ~2GB
# Transcribing: VmRSS stable at ~2GB, threads active
# If VmRSS < 500MB after "Transcribing..." → may be stuck or crashing
```

## When to Kill vs Wait

- **VMRSS growing** → wait, it's loading
- **VMRSS stable at expected level + threads active** → wait, it's working
- **VMRSS = 0 or <100MB after loading phase** → Python may have crashed
- **CPU = 0% for >5 minutes after "Transcribing..."** → may be stuck, investigate
- **Log shows error** → kill and fix

## Whisper Timing Benchmarks (8GB RAM, CPU-only)

| Model | Audio Length | Expected Time | VmRSS |
|-------|-------------|---------------|-------|
| medium | 7 min | ~14 min | ~2GB |
| medium | 1 hour | ~2-3 hours | ~2GB |
| base | 7 min | ~2-3 min | ~500MB |

Source: Igor's machine, 2026-05-31. Whisper medium on 7min audio took exactly 14 minutes from start to output. Process showed VmRSS=1946MB, 17 threads, State=S (sleeping on futex) — all normal. Do NOT kill it prematurely.

## User Preferences (Igor, 2026-05-31)

- "дождись medium, качество важнее скорости" — Don't downgrade from medium to base for whisper
- "мы не спешим никуда" — Quality > Speed
- "почему я тебе должен высказывать эти идеи, а не ты сам об этом думать?" — Be proactive about verification
- "сначала сам проверь внимательно, а потом отправляй" — Verify everything before delivery
