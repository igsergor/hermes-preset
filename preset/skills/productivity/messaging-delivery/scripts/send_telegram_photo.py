#!/usr/bin/env python3
"""Send a photo to a Telegram chat/topic via Bot API directly.

Usage:
    python3 send_telegram_photo.py /path/to/image.png [-c CHAT_ID] [-t THREAD_ID]

Token is read from ~/.hermes/.env (TELEGRAM_BOT_TOKEN=...)
"""
import sys, io, json, urllib.request

def send_photo(photo_path, chat_id, thread_id=None):
    # Read token from .env
    token = None
    with open("~/.hermes/.env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN=***                token = line.split("=", 1)[1].strip()
                break
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in ~/.hermes/.env")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = "----Boundary7MA4YWxkTrZu0gW"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode())
    if thread_id:
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="message_thread_id"\r\n\r\n{thread_id}\r\n'.encode())
    body.write(f"--{boundary}\r\n".encode())
    fname = photo_path.split("/")[-1]
    ext = fname.rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
    body.write(f'Content-Disposition: form-data; name="photo"; filename="{fname}"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    with open(photo_path, "rb") as photo:
        body.write(photo.read())
    body.write(f"\r\n--{boundary}--\r\n".encode())
    body.seek(0)

    req = urllib.request.Request(url, data=body.read())
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    if result.get("ok"):
        print(f"Sent: message_id={result['result']['message_id']}")
    else:
        print(f"FAILED: {result}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("photo_path")
    parser.add_argument("-c", "--chat_id", default="-1003961189874")
    parser.add_argument("-t", "--thread_id", type=int, default=None)
    args = parser.parse_args()
    send_photo(args.photo_path, args.chat_id, args.thread_id)
