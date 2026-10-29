# Cron-Based Autoresume for Long-Running Tasks

## Problem

When the LLM provider fails mid-session (e.g., "The model provider failed after retries"), all work stops. The user must manually check and restart. For long-running tasks (video rendering, multi-step pipelines), this is unacceptable.

## Solution: State File + Cron Job

### 1. Create a State Marker Script

```bash
#!/bin/bash
# task_state.sh — update task state
STATE_FILE="/tmp/task_state"
LOG_FILE="/tmp/task_log"
STATUS="$1"
DETAILS="$2"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "$TIMESTAMP | $STATUS | $DETAILS" >> "$LOG_FILE"
echo -e "$STATUS\n$TIMESTAMP\n$DETAILS" > "$STATE_FILE"
```

### 2. Update State Throughout the Task

```bash
/tmp/task_state.sh "INIT" "Task started"
/tmp/task_state.sh "RENDERING" "Rendering scene 1/5"
/tmp/task_state.sh "AUDIO" "Generating TTS clips"
/tmp/task_state.sh "MERGING" "Merging video + audio"
/tmp/task_state.sh "DONE" "Task complete"
```

### 3. Create Cron Autoresume Job

```
cronjob action=create
  schedule: every 5m
  prompt: |
    Read /tmp/rainbow_task_state. If DONE/DELIVERED, exit.
    Otherwise, check /tmp/rainbow_task_log for where it stopped.
    Resume work from that point.
    Update state file after each step.
```

### 4. Detect and Resume

The cron job checks:
- `cat /tmp/rainbow_task_state` — current status
- `tail -30 /tmp/rainbow_task_log` — what was happening
- `ls -la /tmp/*.mp4 /tmp/*.ogg` — what files exist

Then resumes from the INIT/RENDERING/AUDIO/MERGING state.

## State File Format

```
STATUS
TIMESTAMP
DETAILS
```

Example:
```
RENDERING
2026-05-28 21:15:30
Rendering Scene 3 of 5
```

## When to Use

Any task that:
- Takes > 5 minutes
- Has multiple sequential steps
- Could be interrupted by provider errors
- Produces files on disk (can verify progress)

## Important

- Set `deliver: origin` on the cron job so results come back to the same chat
- The cron prompt must be self-contained (no parent context)
- State file must be on persistent filesystem (not `/dev/shm`)
