#!/usr/bin/env python3
"""Liked-videos (playlist LL) collector WITHOUT Firefox/Marionette.

Reads YouTube cookies straight from the snap Firefox profile's cookies.sqlite,
builds SAPISIDHASH authorization in Python, and calls InnerTube `browse` with
browseId "VL"+"LL" (= the liked-videos playlist). Runs from a cron with no
browser running.

Layout notes (verified):
  * Items come as `lockupViewModel`: video id in `contentId`, title in
    `metadata.lockupMetadataViewModel.title.content`.
  * ~100 items per response and NO continuation token on the first page —
    for a daily diff that is enough, because fresh likes sort to the top.
  * The alert «Недоступные видео скрыты» in the response is normal, not an error.

Usage: python3 likes_daily_inner_tube.py
Output: prints `NEW <N> | всего лайков: <total> | известных: <known>` then the
new items; state in ~/likes_daily_state (known.json / latest.json / new_likes.json).
"""
import glob
import hashlib
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
CK = f"{HOME}/snap/firefox/common/.mozilla/firefox/20wpd4km.default/cookies.sqlite"
if not os.path.exists(CK):
    hits = glob.glob(f"{HOME}/snap/firefox/common/.mozilla/firefox/*.default/cookies.sqlite")
    CK = hits[0] if hits else CK
ST = f"{HOME}/likes_daily_state"
os.makedirs(ST, exist_ok=True)
ORIGIN = "https://www.youtube.com"
KEY = "ВАШ_YOUTUBE_API_КЛЮЧ"  # public web key
VER = "2.20261010.00.00"


def cookies():
    db = sqlite3.connect(f"file:{CK}?immutable=1", uri=True)
    rows = db.execute("select name, value from moz_cookies where host like '%youtube.com'").fetchall()
    return {n: v for n, v in rows if v}


def sap_hash(cookies):
    ts = int(time.time())
    sap = cookies.get("SAPISID") or cookies.get("__Secure-3PAPISID") or ""
    h = hashlib.sha1(f"{ts} {sap} {ORIGIN}".encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"


def browse(cookies, continuation=None):
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": VER, "hl": "ru"}},
            "browseId": "VL" + "LL"}
    if continuation:
        body["continuation"] = continuation
    hdr = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        "Authorization": sap_hash(cookies),
        "X-Origin": ORIGIN,
        "X-Youtube-Client-Name": "1",
        "X-Youtube-Client-Version": VER,
        "Cookie": "; ".join(f"{n}={v}" for n, v in cookies.items()),
    }
    req = urllib.request.Request(f"https://www.youtube.com/youtubei/v1/browse?key={KEY}",
                                 data=json.dumps(body).encode(), headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def walk(d, out):
    """Collect lockupViewModel (new layout) and videoRenderer (old) from any depth."""
    if isinstance(d, dict):
        if "lockupViewModel" in d:
            l = d["lockupViewModel"]
            vid = l.get("contentId")
            title = (l.get("metadata", {}).get("lockupMetadataViewModel", {})
                     .get("title", {}).get("content", ""))
            if vid:
                out.append({"vid": vid, "title": title})
        elif "videoRenderer" in d:
            vr = d["videoRenderer"]
            vid = vr.get("videoId")
            title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
            out.append({"vid": vid, "title": title})
        for v in d.values():
            walk(v, out)
    elif isinstance(d, list):
        for v in d:
            walk(v, out)


def find_cont(d):
    if isinstance(d, dict):
        if "continuationItemRenderer" in d:
            return d["continuationItemRenderer"].get("continuationEndpoint", {}) \
                .get("continuationCommand", {}).get("token")
        for v in d.values():
            r = find_cont(v)
            if r:
                return r
    elif isinstance(d, list):
        for v in d:
            r = find_cont(v)
            if r:
                return r
    return None


def collect(cookies, max_pages=6):
    items, cont = [], None
    for _ in range(max_pages):
        d = browse(cookies, cont)
        out = []
        walk(d, out)
        if not out:
            break
        items.extend(out)
        cont = find_cont(d)
        if not cont:
            break
        time.sleep(2)
    return items


def main():
    ck = cookies()
    if not ck.get("SAPISID"):
        print("ERR нет SAPISID в cookies")
        return
    items = collect(ck)
    if not items:
        print("ERR пустой сбор (cookies протухли?)")
        return
    known_path = f"{ST}/known.json"
    known = json.load(open(known_path)) if os.path.exists(known_path) else {}
    new = [i for i in items if i["vid"] not in known]
    json.dump(items, open(f"{ST}/latest.json", "w"), ensure_ascii=False)
    for i in items:
        known.setdefault(i["vid"], {"title": i["title"],
                                    "first_seen": datetime.now(timezone.utc).isoformat()})
    json.dump(known, open(known_path, "w"), ensure_ascii=False)
    json.dump(new, open(f"{ST}/new_likes.json", "w"), ensure_ascii=False)
    print(f"NEW {len(new)} | всего лайков: {len(items)} | известных: {len(known)}")
    for i in new[:10]:
        print("  +", i["vid"], i["title"][:60])


if __name__ == "__main__":
    main()
