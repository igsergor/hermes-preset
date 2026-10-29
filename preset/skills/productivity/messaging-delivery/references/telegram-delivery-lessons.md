# Telegram Delivery — System-Level Lessons

## Hermes Gateway Media Delivery: What Actually Works

### MEDIA: Prefix (Gateway-Level)

- **Works for:** Small files (~10-15MB max)
- **Fails silently for:** Files >15MB — gateway drops without error
- **Path restriction:** Must be under `~/` — `/tmp/` rejected
- **Delivery context:** Goes to the current session's chat, BUT only if the gateway processes it correctly

### send_message() Tool

- **Text only** — does NOT support video/media attachment
- **Target routing:** `target='telegram'` goes to home channel, NOT current thread
- **MEDIA in text:** When MEDIA: is embedded in send_message text, behavior is unreliable
- **MEDIA: for local files via send_message DOES NOT WORK** — gateway passes literal string `MEDIA:/path/to/file`, no file attachment (verified Jun 2026)

### python-telegram-bot (The Only Reliable Video Method)

- **Works for:** Files up to 50MB (Telegram Bot API hard limit)
- **Thread support:** `message_thread_id` parameter delivers to specific group topic
- **Token source:** Read from `~/.hermes/.env` (`TELEGRAM_BOT_TOKEN=...`)
- **Target discovery:** Use `send_message(action='list')` to find chat/thread IDs

**Minimal working example for small files (configs, docs):**
```python
from telegram import Bot
from telegram.request import HTTPXRequest

bot = Bot(token=FULL_BOT_TOKEN, request=HTTPXRequest(read_timeout=30, write_timeout=30))
await bot.send_document(
    chat_id="-1003961189874",
    message_thread_id=4901,
    document=open("file.conf", "rb"),
    filename="file.conf"
)
```

**Note:** Full token required — `.env` stores masked `855038...tYu4`. Extract full from bot token variable in code or get from @BotFather.

### Hermes `send` Command

- **Text only** — `hermes send -f <file>` reads file as text, binary files fail with encoding error
- **Not suitable for media**

## Failure Mode Decision Tree

```
Need to send video?
├─ File < 10MB?
│  ├─ Yes → MEDIA:/path/in/home/dir in direct reply text
│  └─ No → python-telegram-bot
├─ File 10-50MB?
│  └─ python-telegram-bot (MUST use this)
├─ File > 50MB?
│  ├─ Can split? → python-telegram-bot with chunks
│  └─ Cannot split? → External hosting (gofile.io) + send link
└─ Need specific thread?
   └─ python-telegram-bot with message_thread_id (ONLY method)
```

## Key Lessons from N8N Course Project

1. **MEDIA: gateway silently drops >15MB** — spent hours debugging before discovering python-telegram-bot
2. **send_message() text ≠ MEDIA delivery** — even when MEDIA: is in the text body
3. **Group threads require message_thread_id** — without it, goes to main group
4. **Token in .env, not in config.yaml** — `TELEGRAM_BOT_TOKEN` is in `~/.hermes/.env`
5. **Verify chunk sizes BEFORE sending** — part_033 (60MB) and part_034 (56MB) caused `Request Entity Too Large`
6. **python-telegram-bot reads token from .env** — don't hardcode it in scripts
7. **36 parts × ~30MB each** — took ~10 minutes to send sequentially with 1s delay
