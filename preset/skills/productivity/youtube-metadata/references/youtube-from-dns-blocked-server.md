# Accessing YouTube from a DNS-blocked network (server playbook)

Verified on Igor's server (192.168.1.10), Aug 2026: `www.youtube.com` fails to resolve
through the router while general internet works fine. Cause is
upstream DNS filtering (RU-carrier YouTube degradation or router adlist — symptom
identical). All workarounds below work for either cause.

Determined Oct 2026: the failure is deterministic per transport, not flaky. UDP
queries to `192.168.1.10` for `www`/`youtube.com` apex/`music` return NXDOMAIN every
time (12/12 in series), while the SAME query over TCP (`+tcp`) returns NOERROR with
addresses every time (6/6) — because the router NAT rule redirecting VPN-client
UDP/53 to 8.8.8.8 is UDP-only, so TCP bypasses it. The UDP path travels inside the
VPN tunnel (egress Frankfurt via Syncedge `tun1`), where the upstream answers NXDOMAIN
in ~2 ms — a spoofed answer, not a timeout — specifically for storefront YouTube
domains; control domains over the same UDP path resolve fine, and sing-box logs show
zero DNS errors (silent spoof, not an outage). The gateway host itself reproduces it:
`getent www.youtube.com` fails while `youtubei.googleapis.com` resolves. The earlier
"flakiness" was systemd-resolved rotating upstreams (1.1.1.1, 8.8.8.8, 192.168.1.10)
and caching negative answers — a batch passes while a direct upstream answers and dies
when the router path answers. Diagnose per-transport (UDP series vs TCP series), never
with a single query.

Durable app-side fix (touches neither router nor gateway): an explicit-DNS module
that sends hand-built A queries over UDP straight to 1.1.1.1/8.8.8.8 with stdlib
sockets, caches by TTL, and installs a `socket.getaddrinfo` fallback on `gaierror`
— one import line per pipeline script. Subprocess downloaders need a wrapper script
that patches `socket` in-process before invoking yt-dlp, with fallback to the bare
binary when the wrapper is absent; verify with a metadata fetch of a previously
failing ID before declaring it working.

Refined Oct 2026: the failure is A-record-specific and flaky, not a steady block. Only
apex/`www`/`m`/`music`/`accounts` youtube.com A-queries return NXDOMAIN through
`192.168.1.10`, while AAAA answers, sibling hosts (`youtu.be`, `googlevideo.com`,
`youtubei.googleapis.com`) resolve, and direct `dig @1.1.1.1`/`@8.8.8.8` answers every time.
TTL is ~2 min and systemd-resolved caches the negative answer, so a batch passes while
the record is good and dies mid-run when the window flips — the same video ID succeeds
or fails depending on the minute, not on the video. Diagnose per-record-type before
touching anything: `dig @192.168.1.10 <host> A` vs `AAAA` vs the same pair at `@1.1.1.1`;
a direct hit with a router miss localizes the fault to the router/upstream path, and the
fix discussion belongs there — not in retry loops around the fetcher.

## Fast probes (what still works)
```bash
# Google video CDN reachable? (200 = DNS-only block on www.youtube.com)
curl -s -o /dev/null -w "%{http_code}\n" https://i.ytimg.com/vi/<VIDEO_ID>/hqdefault.jpg
# General sanity:
curl -s -o /dev/null -w "%{http_code}\n" https://example.com
```

## Metadata (title/channel) — try in this order
1. **noembed.com** (verified working, no key):
   `curl -s "https://noembed.com/embed?url=https://www.youtube.com/watch?v=<ID>"`
   → JSON with `title`, `author_name`, `thumbnail_url`.
2. **r.jina.ai** (verified working): `curl -s "https://r.jina.ai/https://www.youtube.com/watch?v=<ID>"`
   → markdown dump incl. title, view count, publish recency. Good second probe.
3. Direct `www.youtube.com/oembed` from the server — FAILS (same DNS block).
4. Public Invidious/Piped mirrors — unreliable (bot-wall garbage pages, 401s, dead
   hosts). Don't burn time enumerating them.

## Full transcripts / description — DoH + patched resolver + yt-dlp
The block is DNS-only, so resolve real IPs out-of-band and pin them:

```bash
# 1. Real IPs (JSON API):
curl -s -H "accept: application/dns-json" \
  "https://cloudflare-dns.com/dns-query?name=www.youtube.com&type=A"

# 2. Environment (PEP 668 — no system pip):
uv venv && uv pip install yt-dlp

# 3. Wrapper (patches socket.getaddrinfo -> DoH IPs, then runs yt-dlp):
chmod +x scripts/yt_fetch.py
.venv/bin/python scripts/yt_fetch.py "https://www.youtube.com/watch?v=<ID>" \
  --no-warnings --skip-download --write-auto-subs --sub-langs ru --sub-format vtt \
  -o "vid.%(ext)s"
.venv/bin/python scripts/yt_fetch.py "<URL>" --skip-download --print "%(description)s"
```

Why it works: TLS SNI and the HTTP Host header keep the original hostname — only the
local address lookup is overridden — so Google serves normal responses to the real IPs.

## HTTP 429 on subtitles — switch transport, don't retry (verified Aug 2026)
Symptom: `ERROR: Unable to download video subtitles for 'ru': HTTP Error 429: Too Many
Requests` from yt-dlp, and it PERSISTS across: `--retries 10 --retry-sleep 15`,
different `-o` templates, and `--extractor-args "youtube:player_client=android"`.
Cause is a per-IP rate limit on the timedtext endpoint, not a transient blip.

The fix that worked same-session: different client library = different rate-limit
bucket. `youtube-transcript-api` fetched the transcript immediately while yt-dlp
still 429'd. Wrapper with the identical DoH patch:

```bash
uv pip install youtube-transcript-api
.venv/bin/python scripts/yt_transcript.py "<URL>" --list          # FIRST: see what exists
.venv/bin/python scripts/yt_transcript.py "<URL>" --langs ru,en   # priority order
# -> writes <ID>.<lang>.txt, lines like "[7:42] text ..."
```

Gotchas learned the hard way:
- **Always `--list` first.** A video may have NO ru track at all (e.g. only
  auto-generated `en`) — guessing language codes wastes attempts against a
  rate-limited endpoint. `NoTranscriptFound` for `ru` ≠ API broken.
- **`VideoUnplayable … account associated with this video has been
  terminated` is a DEAD video, not a fetch failure.** Web search and channel
  search index terminated uploads happily, so a whole triage list can be full
  of them. Skip and move on; never re-run the fetch.
- Plain `youtube-transcript_api` WITHOUT the DoH patch dies with
  `NameResolutionError` (same DNS block) — always run through the wrapper or
  replicate the `socket.getaddrinfo` monkey-patch.
- Metadata (`--print "%(description)s"`, title/duration/upload_date) keeps working
  via yt_fetch.py even while subtitle downloads 429 — different endpoints,
  independent limits.

## Pitfalls
- `write_file` drops scripts as mode 600 without exec bit → `chmod +x` first.
- Auto-sub downloads frequently stall mid-transfer; yt-dlp auto-retries — let it
  finish instead of restarting.
- **Auto-subs garble brand names.** Real examples from one video: Salad → «sellet»,
  Kryptex → «Cryptex»/«Cryptol»/«CrypTex», pool.kryptex.com → «PullTтриpt». Never
  assert an uncertain name in a note — mark it as distorted or verify externally.
- VTT → readable text dedup:
  `grep -v '^[0-9]*:' vid.ru.vtt | grep -v '^$' | awk '!seen[$0]++' > subs.txt`
- Cleanup commands like `rm -rf` may require interactive user confirmation on this
  setup — leave temp dirs and tell the user, don't wedge the session on deletion.
