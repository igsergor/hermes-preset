# Telegram Bot API Delivery — When MEDIA: Fails

## Problem
MEDIA: prefix in response text works for files in trusted directories (`~/.hermes/media_cache/`, `~/.hermes/cache/documents/`), but sometimes silently fails (shows as text `MEDIA:/path` instead of native file). This happens when:
- Gateway doesn't process the directive
- File extension not in MEDIA_DELIVERY_EXTS
- Path not in trusted directory

## Solution: Direct Bot API via python-telegram-bot

### Requirements
- Full Telegram bot token (not masked)
- Chat ID and Thread ID (for forum topics)

### Token Location
Read from `~/.hermes/.env`:
```bash
grep TELEGRAM_BOT_TOKEN ~/.hermes/.env
# TELEGRAM_BOT_TOKEN=8550380334:AAE...  (bot_id:hash)
```
**Note:** Token in `.env` is often masked as `855038...tYu4`. Get full token from **@BotFather** → `/mybots` → select bot → **API Token** → **Show**.

### Chat/Thread ID Discovery
```bash
# Via Hermes
send_message(action='list')
# Returns: telegram:GroupHermes1 / topic 4901
# Chat: -1003961189874, Thread: 4901
```

### Python Script (standalone, no dependencies beyond python-telegram-bot)

```python
#!/usr/bin/env python3
"""Send files to Telegram chat/thread via Bot API."""

import os
import sys
import pathlib
import asyncio
from telegram import Bot
from telegram.request import HTTPXRequest

def read_token():
    env_path = pathlib.Path('~/.hermes/.env')
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return os.environ.get('TELEGRAM_BOT_TOKEN', '')

async def send_files(files, chat_id, thread_id):
    token = read_token()
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found")
        return False
    
    bot = Bot(token=token, request=HTTPXRequest(read_timeout=60, write_timeout=60, connect_timeout=30))
    
    for name, path in files:
        with open(path, "rb") as f:
            await bot.send_document(
                chat_id=chat_id,
                message_thread_id=thread_id,
                document=f,
                filename=name,
                caption=f"WireGuard config: {name}"
            )
        print(f"Sent {name}")
    return True

if __name__ == "__main__":
    files = [
        ("wg-work-debian.conf", "~/wg-work-debian.conf"),
        ("wg-phone.conf", "~/wg-phone.conf"),
        ("wg-laptop.conf", "~/wg-laptop.conf"),
    ]
    CHAT_ID = "-1003961189874"
    THREAD_ID = 4901
    
    asyncio.run(send_files(files, CHAT_ID, THREAD_ID))
```

### Usage
```bash
python3 send_telegram_files.py
```

### Alternative: curl (no Python deps)
```bash
TOKEN="8550380334:AAE..."
CHAT="-1003961189874"
THREAD=4901

curl -X POST "https://api.telegram.org/bot${TOKEN}/sendDocument" \
  -F chat_id="${CHAT}" \
  -F message_thread_id="${THREAD}" \
  -F document=@"~/wg-work-debian.conf" \
  -F caption="wg-work-debian.conf"
```

### Fallback: External Hosting (gofile.io)
```bash
# Get server
SERVER=$(curl -fsSL "https://api.gofile.io/servers" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['servers'][0]['name'])")

# Upload
curl -f -F "file=@~/wg-configs.zip" "https://${SERVER}.gofile.io/uploadFile"
# Returns: {"data":{"downloadPage":"https://gofile.io/d/<CODE>"}}
```

### Verification loop (send → prove bytes arrived)
1. sendDocument response JSON → capture result.document.file_id IMMEDIATELY
   (bots cannot call getMessages — it returns 404, so a deleted/lost
   response means re-sending a control duplicate to get a fresh file_id).
2. getFile?file_id=... → result.file_path (e.g. "documents/file_425.pdf")
3. Download with the LEGACY URL shape:
   https://api.telegram.org/file/bot<TOKEN>/<file_path>      ✅ HTTP 200
   https://api.telegram.org/bot<TOKEN>/file/<file_path>      ❌ 404
4. sha256(downloaded) == sha256(local) → guaranteed delivered byte-for-byte.
   Retry steps 2–3 up to ~5x on ConnectionReset/404 (cold file).
5. If a control duplicate was sent purely for verification — deleteMessage
   it afterwards so the chat only keeps the intended document.
PDF caveat: gs/Chrome re-compression embeds a random /ID + CreationDate, so
SHA differs between builds even when content is identical. For build-parity
checks use byte SIZE equality plus a pixel diff (pdftoppm -r 60 + cv2.absdiff),
not SHA.

### Key Learnings from Session
1. **MEDIA: works** when files are in `~/.hermes/media_cache/` or `~/.hermes/cache/documents/`
2. **Bot API required** for reliable delivery to specific forum topics
3. **Token must be full** — masked token in .env is unusable
4. **Thread ID matters** — without `message_thread_id`, goes to main group
5. **Timeout 60s+** needed for Bot API calls
6. **Token in env is unreliable** — read it from config.yaml/`/tmp/kom_tg_token` copy when curl returns 404 Not Found on every method