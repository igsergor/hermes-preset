#!/usr/bin/env python3
"""Fetch YouTube data (subs/metadata) on hosts where YouTube DNS is blocked/poisoned.

Resolves real YouTube IPs via DoH (cloudflare-dns.com JSON API), monkey-patches
socket.getaddrinfo so yt-dlp connects to those IPs directly, then delegates all
arguments to yt-dlp. TLS SNI / Host header keep the real hostname, so Google
serves the normal responses.

Usage:
    python3 yt_fetch.py <youtube-url> [yt-dlp args...]

Examples:
    # Russian auto-subs:
    python3 yt_fetch.py "https://www.youtube.com/watch?v=ID" --no-warnings \
        --skip-download --write-auto-subs --sub-langs ru --sub-format vtt -o "vid.%(ext)s"
    # Description:
    python3 yt_fetch.py "<URL>" --skip-download --print "%(description)s"

Requires yt-dlp importable in the active interpreter (PEP 668 systems:\n`uv venv --clear && uv pip install yt-dlp`, then run with .venv/bin/python).\nIf the venv already exists but packages are missing, `--clear` replaces it safely —\n`uv venv` without --clear fails with \"already exists\".
"""
import json
import socket
import sys
import urllib.request

YT_DOMAINS = (
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
)


def doh_resolve(host):
    """Return list of A-record IPs for host via Cloudflare DoH."""
    url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: yt_fetch.py <youtube-url> [yt-dlp args]")

    ip_map = {}
    for domain in YT_DOMAINS:
        try:
            ips = doh_resolve(domain)
            if ips:
                ip_map[domain] = ips
        except Exception as exc:  # noqa: BLE001 - best-effort per domain
            print(f"[warn] DoH resolve failed for {domain}: {exc}", file=sys.stderr)

    if not ip_map:
        sys.exit("error: could not resolve any YouTube domain via DoH")

    real_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host, *args, **kwargs):
        if isinstance(host, str) and host in ip_map:
            last_err = None
            for ip in ip_map[host]:
                try:
                    return real_getaddrinfo(ip, *args, **kwargs)
                except OSError as err:
                    last_err = err
            raise last_err
        return real_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = patched_getaddrinfo

    from yt_dlp import main as ytdlp_main

    ytdlp_main(sys.argv[1:])


if __name__ == "__main__":
    main()
