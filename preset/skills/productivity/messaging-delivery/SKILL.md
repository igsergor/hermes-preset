---
name: messaging-delivery
description: "Messaging and media delivery: gateway setup (Telegram/Discord/Slack), file delivery via Telegram, and TTS voice responses. Use when configuring messaging platforms, sending files/media via Telegram, or delivering voice responses."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [messaging, telegram, discord, slack, gateway, tts, voice, file-delivery]
    related_skills: [messaging-delivery]
---

# Messaging & Media Delivery

Three domains: gateway messaging platform setup, Telegram file delivery, and TTS voice responses.

## Quick Decision Guide

| Task | Section |
|------|---------|
| Configure Telegram/Discord/Slack gateway | → §1 Gateway Setup |
| Send files/media via Telegram | → §2 Telegram File Delivery |
| Deliver voice responses via TTS | → §3 TTS Voice Responses |

---

## §1 Gateway Messaging Setup

Configure Hermes gateway messaging platform integrations.

### Configuration Files

- `~/.hermes/config.yaml` — main config (platform toggles, toolsets, timeouts)
- `~/.hermes/.env` — secrets (bot tokens, allowed user IDs, API keys)

### Telegram

**Required `.env` variables:**
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
TELEGRAM_ALLOWED_USERS=987654321  # Numeric IDs, comma-separated
```

**Getting your user ID:** Use `@userinfobot` or `@RawDataBot`

**Common Pitfalls:**

| Problem | Fix |
|---------|-----|
| Username instead of numeric ID | Must be numeric: `TELEGRAM_ALLOWED_USERS=252852450` |
| Tirith blocks commands | `hermes config set security.tirith_enabled false` |
| MEDIA: path rejected | Files must be under `~/`, not `/tmp/` |
| MEDIA: silent failure | Files in `~/hermes1/` or similar subdirs may be blocked - use `~/` or trusted dirs like `~/.hermes/media_cache/` |
| Bot can't read chat history | Bot API limitation — bots only receive new messages |
| Silent message drops | User not in `TELEGRAM_ALLOWED_USERS` — no log entry |

**Temporarily allow all users** (to discover IDs):
```bash
GATEWAY_ALLOW_ALL_USERS=true  # Add to .env, restart, then remove
```

### Discord

```bash
DISCORD_BOT_TOKEN=your_token_here
```
Must enable **Message Content Intent** in Discord Developer Portal.

### Slack

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...  # For Socket Mode
```
Must subscribe to `message.channels` event.

### General Troubleshooting
### Audio Format

Telegram on Android does NOT play Opus in MKV. Always use AAC:
```bash
ffmpeg -i input.mkv -c:v copy -c:a aac -b:a 128k output_aac.mkv
```

### Critical Rules

1. **Send ONCE** — never retry to multiple targets
2. **Verify target before sending** — use `send_message(action='list')`
3. **If delivery fails twice** — tell user and offer alternatives
4. **Don't send duplicates** — user gets frustrated
5. **Respect user's language** — if the user communicates in Russian, respond in Russian; if in another language, match that language.
6. **Do not send archives** unless explicitly requested; send each file separately with its transcription/text.
7. **When preparing audio from text transcripts**, strip all Markdown formatting (e.g., `**`, `*`, `__`, `_`, `` ` ``, `~~`) from the transcript before sending it to the TTS engine, to avoid speaking those symbols. Ensure the transcript language matches the user's language (e.g., Russian if the user communicated in Russian). Generate the audio file using the `text_to_speech` tool, then send it via Telegram with a single message containing the cleaned transcript followed by a newline and `MEDIA:<path_to_audio_file>`. Do not embed the transcript inside the audio file; send it as plain text in the same message.

### MEDIA: Prefix Troubleshooting

If you see "No deliverable text or media remained after processing MEDIA tags":

1. **Check file path** - Must be under trusted directories:
   - ✅ `~/.hermes/media_cache/file.ogg` (recommended)
   - ✅ `~/.hermes/cache/file.ogg`
   - ✅ `~/file.ogg` (home directory - sometimes works)
   - ❌ `~/hermes1/file.ogg` (subdirs of home may be blocked)
   - ❌ `/tmp/file.ogg` (explicitly blocked)

2. **Verify file type** - Only image/video/audio extensions work (photos, voice bubbles, inline video)

3. **Check target format** - For group topics, use `telegram:-1001234567890:THREAD_ID`
   - Get thread ID from `send_message(action='list')` output
   - DMs use just `telegram:` or `telegram:username`

4. **Test with known good location** - Copy file to `~/.hermes/media_cache/` and try again

---

### ⚠️ Critical Limitation: Documents (.conf, .txt, .pdf, .json, .zip) via `MEDIA:` DO NOT WORK

The `MEDIA:` prefix only renders **images, videos, audio** as native Telegram media (photos, voice bubbles, playable video). **Document files are silently dropped** — user receives nothing.

**Workaround: Use raw Telegram Bot API `sendDocument`** via Python urllib (stdlib only, no deps):

```python
import urllib.request, json, io, os

# Read token from ~/.hermes/.env
with open("~/.hermes/.env") as f:
    for line in f:
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip()
            break

chat_id = "-1003961189874"      # Group ID from config
thread_id = "4901"              # Topic/thread ID from send_message(action='list')
file_path = "~/.hermes/media_cache/your-file.conf"

url = f"https://api.telegram.org/bot{token}/sendDocument"
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

body = io.BytesIO()
body.write(f"--{boundary}\r\n".encode())
body.write(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'.encode())
body.write(f"{chat_id}\r\n".encode())

body.write(f"--{boundary}\r\n".encode())
body.write(f'Content-Disposition: form-data; name="message_thread_id"\r\n\r\n'.encode())
body.write(f"{thread_id}\r\n".encode())

body.write(f"--{boundary}\r\n".encode())
body.write(f'Content-Disposition: form-data; name="document"; filename="your-file.conf"\r\n'.encode())
body.write(b"Content-Type: text/plain\r\n\r\n")
with open(file_path, "rb") as f:
    body.write(f.read())
body.write(f"\r\n--{boundary}--\r\n".encode())

body.seek(0)
req = urllib.request.Request(url, data=body.read())
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
resp = urllib.request.urlopen(req, timeout=300)  # 300s: большие PDF идут минутами
print(json.loads(resp.read()))
```

**Key points:**
- Files MUST be in trusted dirs (`~/.hermes/media_cache/`, `~/.hermes/cache/`, `~/`)
- Include `message_thread_id` for forum supergroups (topics)
- Use `sendDocument` for .conf/.txt/.pdf/.json, `sendPhoto`/`sendVideo`/`sendAudio` for media
- This produces a **clickable, downloadable document message** — not a MEDIA render

### Большие файлы и проверка доставки

- **Таймаут = 300s для файлов > ~5 МБ.** На 30s загрузка 8–32 МБ обрывается по таймауту и выглядит как «файл не доставлен», хотя проблема только в клиенте. В `scripts/send_document.py` таймаут уже 300; в своих однострочниках не возвращай 30.
- **Проверка факта доставки (обязательна, если пользователь просит «проверь, что дошло»):** из ответа `sendDocument` взять `document.file_id` → `getFile` → скачать `https://api.telegram.org/file/bot<token>/<file_path>` → `sha256sum` скачанного и локального → сверить. Совпадение хеша = на сервере лежит именно твой файл, а не обрезанный.
- **Проверочную копию удалять.** Если для проверки отправлял второе сообщение (`disable_notification=true`), после сверки вызови `deleteMessage` с его `message_id`, иначе в треде останется дубль.
- **Если `getFile`/скачивание не проходят (с сервера `api.telegram.org` недоступен, `Network is unreachable`)** — не выдавать отправку за проверенную: писать прямо «файл отправлен (message_id N), хеш сверить не смог — при проблеме переотправлю». Отчёт «дошло, хеш совпал» без реального скачивания = ложное подтверждение, которое вскроется на первом же битом файле.
- **Сжатие вместо «не доставлено»:** `gs -dPDFSETTINGS=/ebook -dColorImageResolution=150 -dGrayImageResolution=170` ужимает тяжёлый PDF в 3–4 раза без потери векторного текста; отправляй сжатую версию, а полную держи на диске и предложи по запросу.

### Screenshots & tall/large images → send as DOCUMENT (предпочтение пользователь, 08.10.26)

Фото-отправка (MEDIA: с .png/.jpg) = Bot API sendPhoto → Telegram ужимает длинную сторону
до 1568px. Для вертикальных скриншотов (соотношение > ~1.5:1) текст после сжатия
становится нечитаемым (~7px) — пользователь такое дважды заворачивал.

ПРАВИЛО: любой скриншот выше ~2000px или с мелким текстом (UI, корзины, таблицы)
отправлять КАК ФАЙЛОМ через прямой Bot API sendDocument:

```
python3 ~/.hermes/skills/productivity/messaging-delivery/scripts/send_document.py \
  /path/to/shot.png --chat_id <chat> --thread_id <thread> --caption '...'
```

- chat/thread текущего треда: из context gateway message (`chat_id`, `thread_id`).
- Байты не трогаются; в пузыре превью, тап → просмотрщик с зумом/прокруткой — пользователь так
  удобнее, чем PDF («вот так и делай в будущем»).
- MEDIA:/photo оставлять только для компактных кадров (длинная сторона ≤ ~2000px, текст ≥ ~14px
  после сжатия) — тогда фото удобнее (открывается сразу, без превью-файла).
- Для «одним кадром + читаемо» альтернатива: разложить строки в две колонки → почти квадрат
  (см. shop-orders, раздел про склейку корзины).

## §3 TTS Voice Responsesutput
- **Long responses are fine** — user chose to listen

### Receiving Voice Messages

When user sends a voice message, display transcription first:
```
🎤 Расшифровка: «<transcribed text>»
```
Then respond (voiced + text).
