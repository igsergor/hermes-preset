#!/usr/bin/env python3
"""Unwrap-proxy for providers whose NON-STREAMING responses come wrapped in a
{"data": {"choices": [...]}} envelope (CLinePass / api.cline.bot does this).

Forward OpenAI-format requests to a target base URL and unwrap the
`data` envelope into `{"choices": [...]}` so the OpenAI SDK / Hermes auxiliary
clients (vision, compression, session_search title) parse it correctly.

Why needed: streaming responses (SSE `data: {...}` chunks) carry standard
`choices` at the top level, so the MAIN agent chat works. But Hermes's
auxiliary tasks (vision_analyze, etc.) send NON-streaming requests and receive
the `{"data": {...}}` wrapper, which the SDK rejects with:
    "Expected object with .choices[0].message"
    (ChatCompletion(id=None, choices=None, ...) — choices were under `data`).

Listen on a localhost port; point `auxiliary.vision.base_url` (and any other
broken auxiliary task) at it. stdlib only — no pip deps.

Requires env var holding the API key (auth is passed through unchanged).
:
  CLINE_API_KEY=... ./clinepass-unwrap-proxy.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# NOTE: no trailing /v1 here. The OpenAI client appends `/chat/completions` to
# the base_url it was given; to reach `<api>/api/v1/chat/completions` when the
# client base_url is `http://127.0.0.1:PORT/v1`, the target must be
# `https://<api>/api` (the `/v1` comes from the path). Set TARGET to your
# provider's API root WITHOUT the /v1 path segment.
TARGET = "https://api.cline.bot/api"
PORT = 8765
API_KEY = os.environ.get("CLINE_API_KEY", "")


class Handler(BaseHTTPRequestHandler):
    def _fwd(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        url = TARGET + self.path
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": self.headers.get("Authorization", ""),
                "Content-Type": "application/json",
            },
        )
        try:
            r = urllib.request.urlopen(req, timeout=120)
            raw = r.read()
            ctype = r.headers.get("Content-Type", "application/json")
            status = r.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            ctype = e.headers.get("Content-Type", "application/json")
            status = e.code

        # Unwrap only JSON objects carrying {"data": {"choices": ...}} where
        # `choices` is NOT already at the top level (idempotent pass-through).
        try:
            decoded = json.loads(raw.decode("utf-8"))
            if (
                isinstance(decoded, dict)
                and isinstance(decoded.get("data"), dict)
                and "choices" in decoded["data"]
                and "choices" not in decoded
            ):
                decoded = decoded["data"]
                raw = json.dumps(decoded).encode("utf-8")
        except Exception:
            pass
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_POST = _fwd
    do_GET = _fwd
    do_PUT = _fwd
    do_DELETE = _fwd

    def log_message(self, fmt, *args):
        sys.stderr.write("[unwrap-proxy] %s\n" % (fmt % args))


if __name__ == "__main__":
    if not API_KEY:
        print("CLINE_API_KEY env var missing", file=sys.stderr)
        sys.exit(1)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"unwrap-proxy listening on 127.0.0.1:{PORT}", file=sys.stderr)
    srv.serve_forever()