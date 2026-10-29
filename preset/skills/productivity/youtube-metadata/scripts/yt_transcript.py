#!/usr/bin/env python3
"""Fallback transcript fetcher for YouTube when yt-dlp subtitle download 429s.

Same DoH trick as yt_fetch.py (monkey-patch socket.getaddrinfo with Cloudflare
DoH results), but wraps youtube-transcript-api instead of yt-dlp — different
transport, different rate-limit bucket, so it succeeds when yt-dlp's timedtext
downloads keep failing with HTTP 429 (verified Aug 2026).

Setup (PEP 668 systems): uv pip install youtube-transcript-api

Usage:
    python3 yt_transcript.py <youtube-url-or-id> --list
    python3 yt_transcript.py <youtube-url-or-id> [--langs ru,en] [-o out.txt]

Tries each requested language in order; writes timestamped plain text
"<video_id>.<lang>.txt" unless -o given. Run --list FIRST: videos often have
only some languages (e.g. only auto-generated en, no ru).
"""
import argparse
import json
import re
import socket
import sys
import urllib.request

YT_DOMAINS = ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be")


def doh_resolve(host):
    """Return A-record IPs for host via Cloudflare DoH JSON API."""
    url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]


def patch_dns():
    ipmap = {}
    for domain in YT_DOMAINS:
        try:
            ips = doh_resolve(domain)
            if ips:
                ipmap[domain] = ips
        except Exception as exc:  # noqa: BLE001 - best-effort per domain
            print(f"[warn] DoH resolve failed for {domain}: {exc}", file=sys.stderr)
    if not ipmap:
        sys.exit("error: could not resolve any YouTube domain via DoH")

    real_getaddrinfo = socket.getaddrinfo

    def patched(host, *args, **kwargs):
        if isinstance(host, str) and host in ipmap:
            last_err = None
            for ip in ipmap[host]:
                try:
                    return real_getaddrinfo(ip, *args, **kwargs)
                except OSError as err:
                    last_err = err
            raise last_err
        return real_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = patched


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    return m.group(1) if m else url.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url", help="YouTube URL or 11-char video id")
    ap.add_argument("--langs", default="ru,en", help="comma-separated priority list")
    ap.add_argument("--list", action="store_true", help="list available transcripts")
    ap.add_argument("-o", "--out", help="output file (default <id>.<lang>.txt)")
    args = ap.parse_args()

    vid = video_id(args.url)
    patch_dns()

    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()

    if args.list:
        for t in api.list(vid):
            print(f"{t.language_code} | generated: {t.is_generated}")
        return

    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    last_err = None
    for lang in langs:
        try:
            tr = api.fetch(vid, languages=[lang])
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {lang}: {type(exc).__name__}", file=sys.stderr)
            last_err = exc
            continue
        lines = [f"[{int(s.start)//60}:{int(s.start)%60:02d}] {s.text}" for s in tr]
        text = "\n".join(lines)
        out = args.out or f"{vid}.{lang}.txt"
        with open(out, "w") as fh:
            fh.write(text)
        print(f"OK {lang}: {len(text)} chars, {len(lines)} segments -> {out}")
        return

    sys.exit(f"error: none of {langs} available ({last_err}); try --list")


if __name__ == "__main__":
    main()
