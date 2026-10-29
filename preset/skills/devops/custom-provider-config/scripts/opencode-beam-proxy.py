#!/usr/bin/env python3
"""Beam strip-proxy: OpenAI-compatible front for opencode-go/beam-free.

Why: Hermes/OmniRoute mixes Responses-transport members (muse-spark) and
chat-transport members in one combo. Muse's thinking blocks persist in
history as `reasoning` on assistant messages; the opencode-go gateway
executor replays reasoning for the WHOLE provider, so strict chat
upstreams 400 with `unsupported_parameter: messages[N].reasoning`.

This proxy sits between Hermes and https://opencode.ai/zen/go/v1 and
strips foreign reasoning fields from the request history before
forwarding. Response content is passed through untouched.

Deployed as systemd user unit `opencode-beam-proxy.service` (port 28777).
Auth is self-injected from OPENCODE_GO_API_KEY env (Hermes refuses to
send named-provider credentials to localhost, so the client header is
overridden, not trusted). Session header x-opencode-session is mandatory
upstream (400 MissingSessionID without it): forwarded when the client
sends one, synthesized otherwise.

Update-proof: lives in ~/.hermes/scripts/ (never pruned by hermes update),
stdlib only.
"""

import json
import os
import random
import string
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET = "https://opencode.ai/zen/go/v1"
PORT = 28777

STRIP_FIELDS = ("reasoning", "reasoning_content", "reasoning_details",
                "reasoning_text")
STRIP_BLOCK_TYPES = ("thinking", "redacted_thinking")


def join_target(path):
    # Client base_url ends in /v1, so OpenAI SDK sends /v1/chat/completions
    # and /v1/models — but TARGET already contains /v1. Strip it to avoid
    # the /v1/v1/... double that upstream 404s.
    if path.startswith("/v1/"):
        path = path[3:]
    return TARGET + path


def _new_session_id():
    # ses_ + 12 hex + 14 base62 (matches opencode-cli shape)
    hexpart = "".join(random.choice("0123456789abcdef") for _ in range(12))
    b62 = string.ascii_letters + string.digits
    tail = "".join(random.choice(b62) for _ in range(14))
    return "ses_" + hexpart + tail


def strip_reasoning(obj):
    """Remove foreign reasoning fields from chat messages (in place)."""
    if isinstance(obj, dict):
        msgs = obj.get("messages")
        if isinstance(msgs, list):
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                for f in STRIP_FIELDS:
                    m.pop(f, None)
                content = m.get("content")
                if isinstance(content, list):
                    m["content"] = [b for b in content
                                    if not (isinstance(b, dict)
                                            and b.get("type") in STRIP_BLOCK_TYPES)]
    return obj


def build_request(path, body, headers):
    url = join_target(path)
    api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
    out = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
        "User-Agent": "opencode/1.18.34",
    }
    if api_key:
        out["Authorization"] = "Bearer " + api_key
    # forward opencode session/project scoping headers when present
    for h in ("x-opencode-session", "x-opencode-client",
              "x-opencode-project", "x-opencode-request"):
        v = headers.get(h) or headers.get(h.title())
        if v:
            out[h] = v
    if "x-opencode-session" not in out:
        out["x-opencode-session"] = _new_session_id()
    return urllib.request.Request(url, data=body, headers=out, method="POST")


class Handler(BaseHTTPRequestHandler):
    server_version = "BeamStripProxy/1.0"

    def _send_upstream(self, req, stream):
        try:
            r = urllib.request.urlopen(req, timeout=300)
            raw = r.read() if not stream else None
            ctype = r.headers.get("Content-Type", "application/json")
            status = r.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            ctype = e.headers.get("Content-Type", "application/json")
            status = e.code
            r = None
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            err = json.dumps({"error": str(e)}).encode()
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        if stream:
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
        else:
            self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if stream and r is not None:
            try:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif not stream:
            self.wfile.write(raw)

    def _fwd(self, with_body):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if (with_body and length) else b""
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
                stream = payload.get("stream", False) is True
                # beam-free: no longer strip foreign reasoning fields (upstream
                # accepts them now); just force reasoning_effort=max.
                payload["reasoning_effort"] = "max"
                body = json.dumps(payload).encode("utf-8")
            except Exception:
                stream = b'"stream":true' in body or b'"stream": true' in body
        else:
            stream = False
        req = build_request(self.path, body if body else None, self.headers)
        self._send_upstream(req, stream)

    def do_POST(self):
        self._fwd(with_body=True)

    def do_GET(self):
        # /v1/models passthrough for picker discovery
        api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
        url = join_target(self.path)
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "opencode/1.18.34",
            "Authorization": "Bearer " + api_key,
            "x-opencode-session": (self.headers.get("x-opencode-session")
                                   or _new_session_id()),
        })
        try:
            r = urllib.request.urlopen(req, timeout=30)
            raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except Exception as e:
            raw = json.dumps({"error": str(e)}).encode()
            status = 502
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        sys.stderr.write("[beam-proxy] %s\n" % (fmt % args))


if __name__ == "__main__":
    if not os.environ.get("OPENCODE_GO_API_KEY"):
        print("OPENCODE_GO_API_KEY env var missing", file=sys.stderr)
        sys.exit(1)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"beam-proxy listening on 127.0.0.1:{PORT}", file=sys.stderr)
    srv.serve_forever()
