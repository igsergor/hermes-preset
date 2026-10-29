# Subtitle Translation Workflow (EN→RU via OpenRouter API)

## Overview

Translate thousands of subtitle segments to Russian using parallel OpenRouter API calls.

## Pipeline

### 1. Extract Subtitles

```bash
yt-dlp --write-auto-sub --sub-lang en --sub-format json \
  -o subs.json --skip-download "VIDEO_URL"
```

### 2. Parse to Clean Format

```python
import json

with open('subs.json') as f:
    data = json.load(f)

segments = []
for event in data.get('events', []):
    if 'segs' in event:
        text = ''.join(s.get('utf8', '') for s in event['segs']).strip()
        if text:
            start_sec = event['tStartMs'] / 1000.0
            dur_sec = (event.get('dDurationMs', 0)) / 1000.0
            end_sec = start_sec + dur_sec
            segments.append({
                'start': round(start_sec, 3),
                'end': round(end_sec, 3),
                'text': text
            })

with open('parsed_subs.json', 'w') as f:
    json.dump(segments, f, ensure_ascii=False, indent=2)
```

### 3. Chunk and Translate

- **Chunk size:** 200 segments
- **Parallelism:** 12 concurrent processes
- **Model:** `openrouter/auto`

**Prompt template:**
```
Переведи на русский язык следующие субтитры. Сохраняй нумерацию строк.
Каждый перевод на новой линии в формате: "НОМЕР: ТЕКСТ"

0: Hello everyone
1: Welcome to this course

Ответ только переводом, без пояснений.
```

**Response parsing:** Split by `\n`, parse `NUMBER: text`. Match back to original indices.

### 4. Merge Chunks

```python
import json, glob

all_translated = []
for f in sorted(glob.glob('translated/translated_*.json')):
    with open(f) as fh:
        all_translated.extend(json.load(fh))

all_translated.sort(key=lambda x: x['start'])

with open('translated_subs.json', 'w') as f:
    json.dump(all_translated, f, ensure_ascii=False, indent=2)
```

## Lessons Learned (N8N Course Project)

- **14,812 segments** — 75 chunks x 200 segs — 12 parallel — ~24 min
- **Result:** 14,337/14,812 = **96.8%** translated (475 untranslated from rate limits)
- Untranslated segments are short and scattered — negligible for 8h content
- **Key pitfall:** Rate limits cause empty responses. Cannot retry per-chunk in parallel — accept ~3% loss
- **Model:** `openrouter/auto` works well; no need for expensive models
