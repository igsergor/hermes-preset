#!/usr/bin/env python3
"""Send ANY file (document) to any Telegram chat/topic via Bot API directly.

MEDIA: prefix only renders images/video/audio — documents (.txt/.conf/.pdf/.json)
are silently dropped. Use this script instead for clickable, downloadable documents
in ANY chat/topic of the connected Telegram account.

Generalized: no hardcoded chat. Targets come from:
  1. explicit --chat_id / --thread_id args (most reliable), or
  2. a friendly target name from --name, resolved via the targets registry
     (~/.hermes/skills/.../scripts/telegram_targets.json), or
  3. no target -> defaults to the group specified by --group (default home channel).

Usage:
    # send to explicit chat (and optional thread)
    python3 send_document.py /path/file.txt --chat_id -1001234567890 --thread_id 7265

    # send to a named/target/saved registry entry
    python3 send_document.py /path/file.txt --name work-notes

    # list all known chats/threads (from registry + state.db history)
    python3 send_document.py --list

Token read from ~/.hermes/.env (TELEGRAM_BOT_TOKEN=...)
"""
import sys, os, io, json, sqlite3, glob, argparse, urllib.request

_ENV = "~/.hermes/.env"
_REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_targets.json")
_HOME_GROUP = "-1003961189874"   # default group chat id

def _token():
    with open(_ENV) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    print("ERROR: TELEGRAM_BOT_TOKEN not found in %s" % _ENV); sys.exit(1)

def _load_registry():
    if os.path.exists(_REGISTRY):
        try:
            return json.load(open(_REGISTRY))
        except Exception:
            pass
    return {"targets": {}}

def _save_registry(reg):
    json.dump(reg, open(_REGISTRY, "w"), ensure_ascii=False, indent=2)

def _discover_from_state():
    """Return known (platform, chat_id, thread_id) tuples from hermes state.db history."""
    out = []
    for db in glob.glob(os.path.expanduser("~/.hermes/state.db")) + glob.glob(os.path.expanduser("~/.hermes/profiles/*/state.db")):
        try:
            conn = sqlite3.connect(db)
            rows = conn.execute(
                "SELECT DISTINCT source, chat_id, thread_id FROM sessions "
                "WHERE (source LIKE 'telegram%' OR chat_type LIKE '%group%') "
                "AND chat_id IS NOT NULL ORDER BY chat_id").fetchall()
            conn.close()
            for r in rows:
                out.append((db, r[1], r[2]))
        except Exception:
            continue
    return out

def send_document(file_path, chat_id, thread_id=None, caption=None, mime=None):
    token = _token()
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    boundary = "----Boundary7MA4YWxkTrZu0gW"
    body = io.BytesIO()
    def w(s): body.write(s.encode())
    w(f"--{boundary}\r\n")
    w(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n')
    if thread_id:
        w(f"--{boundary}\r\n")
        w(f'Content-Disposition: form-data; name="message_thread_id"\r\n\r\n{thread_id}\r\n')
    if caption:
        w(f"--{boundary}\r\n")
        w(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n')
    fname = file_path.split("/")[-1]
    if mime is None:
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "txt"
        mime = {"png":"image/png","jpg":"image/jpeg","pdf":"application/pdf",
                "json":"application/json","md":"text/markdown"}.get(ext, "application/octet-stream")
    w(f"--{boundary}\r\n")
    w(f'Content-Disposition: form-data; name="document"; filename="{fname}"\r\nContent-Type: {mime}\r\n\r\n')
    with open(file_path, "rb") as doc:
        body.write(doc.read())
    w(f"\r\n--{boundary}--\r\n")
    body.seek(0)
    req = urllib.request.Request(url, data=body.read())
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    resp = urllib.request.urlopen(req, timeout=300)  # большие PDF идут минутами
    result = json.loads(resp.read())
    if result.get("ok"):
        print(f"Sent: message_id={result['result']['message_id']} chat={chat_id} thread={thread_id}")
        return True
    print("FAILED:", json.dumps(result, ensure_ascii=False)); sys.exit(1)

def main():
    p = argparse.ArgumentParser("send_document.py")
    p.add_argument("file_path", nargs="?")
    p.add_argument("--chat_id", "-c")
    p.add_argument("--thread_id", "-t", type=int)
    p.add_argument("--name", "-n", help="Target name from registry")
    p.add_argument("--caption", "-m")
    p.add_argument("--mime", help="Override content type")
    p.add_argument("--save", help="Save the resolved target as <name> in registry")
    p.add_argument("--list", "-l", action="store_true", help="List known chats/threads")
    p.add_argument("--group", "-g", default=_HOME_GROUP, help="Default group chat id when no target")
    args = p.parse_args()

    if args.list or not args.file_path:
        reg = _load_registry()
        print("=== Registry targets ===")
        for k, v in reg.get("targets", {}).items():
            print(f"  {k}: chat={v.get('chat_id')} thread={v.get('thread_id')}")
        print("\n=== Known Telegram chats from state.db ===")
        seen = set()
        for _db, cid, tid in _discover_from_state():
            key = (cid, tid)
            if key not in seen:
                seen.add(key)
                print(f"  chat={cid} thread={tid}")
        if not args.file_path:
            return
    else:
        chat_id, thread_id = None, None
        if args.name:
            reg = _load_registry()
            t = reg.get("targets", {}).get(args.name)
            if not t:
                print(f"ERROR: target '{args.name}' not in registry"); sys.exit(1)
            chat_id, thread_id = t.get("chat_id"), t.get("thread_id")
        chat_id = args.chat_id or chat_id or args.group
        thread_id = args.thread_id if args.thread_id is not None else thread_id
        if args.save:
            reg = _load_registry()
            key = args.save
            reg.setdefault("targets", {})[key] = {"chat_id": chat_id, "thread_id": thread_id}
            _save_registry(reg)
            print(f"Saved target '{key}': chat={chat_id} thread={thread_id}")
        send_document(args.file_path, chat_id, thread_id, args.caption, args.mime)

if __name__ == "__main__":
    main()