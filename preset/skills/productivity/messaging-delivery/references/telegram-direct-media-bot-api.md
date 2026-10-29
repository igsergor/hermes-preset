# Telegram Direct Media via Bot API

Sending photos, videos, and documents as **standalone clickable/previewable media messages** via raw Telegram Bot API calls using Python urllib. This bypasses the `send_message` tool's `MEDIA:` tag which doesn't produce clickable/previewable media.

**Use this approach when:**
- User asks to send a photo/video/file as a standalone message
- `send_message` with `MEDIA:` produces non-clickable results
- You need the media to open in full screen when tapped

## Read the bot token

```python
token = None
with open("~/.hermes/.env") as f:
    for line in f:
        line = line.strip()
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip()
            break
```

## Send Photo

```python
import urllib.request, json, io

def send_photo(token, chat_id, photo_path, thread_id=None, caption=None):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'.encode())
    body.write(f"{chat_id}\r\n".encode())
    
    if thread_id:
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="message_thread_id"\r\n\r\n'.encode())
        body.write(f"{thread_id}\r\n".encode())
    
    if caption:
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="caption"\r\n\r\n'.encode())
        body.write(f"{caption}\r\n".encode())
    
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="photo"; filename="photo.png"\r\n'.encode())
    body.write(b"Content-Type: image/png\r\n\r\n")
    with open(photo_path, "rb") as f:
        body.write(f.read())
    body.write(f"\r\n--{boundary}--\r\n".encode())
    
    body.seek(0)
    req = urllib.request.Request(url, data=body.read())
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())
```

## Send Document / Video / Audio

Same pattern with the appropriate endpoint and form field:

| Type | Endpoint | Form field |
|------|----------|------------|
| Photo | `/sendPhoto` | `photo` |
| Document | `/sendDocument` | `document` |
| Video | `/sendVideo` | `video` |
| Audio | `/sendAudio` | `audio` |

## Key Notes

- Always include `message_thread_id` for forum supergroups
- File paths must be absolute and readable
- Token is in `~/.hermes/.env` as `TELEGRAM_BOT_TOKEN`
- No external dependencies needed, uses stdlib urllib only
- Path MUST be under `~/` (trusted dir) — `/tmp/` is rejected by gateway
