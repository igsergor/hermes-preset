#!/usr/bin/env python3
"""Probe which NVIDIA NIM (integrate.api.nvidia.com) models actually work.

The public /v1/models catalog lists ~82 models, but most return 404
"Function not found" for a given free account, and some hang forever.
This script probes every catalog model with a 1-token request (parallel,
25s timeout) and RETRIES the timeouts once — then prints a triaged list.

Usage:
    NIM_API_KEY=nvapi-... python3 nim-probe-models.py [--catalog /tmp/nim_models.json]

Exit output: three sections — WORKING / 404 (not provisioned) / timeouts+errors.
Feed the WORKING list into the OmniRoute connection + Hermes picker (nv/ prefix).
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://integrate.api.nvidia.com/v1"


def get_catalog(key):
    req = urllib.request.Request(f"{BASE}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return [m["id"] for m in json.load(r)["data"]]


def probe(key, mid, timeout=25):
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=json.dumps({"model": mid, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=timeout).read()
        return mid, "OK"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:80]
        return mid, f"{e.code}" if e.code == 404 else f"{e.code} {body}"
    except Exception as e:
        return mid, f"timeout/{type(e).__name__}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", help="cached /v1/models JSON (skips the live fetch)")
    args = ap.parse_args()

    key = os.environ.get("NIM_API_KEY")
    if not key:
        sys.exit("set NIM_API_KEY")

    if args.catalog and os.path.exists(args.catalog):
        ids = [m["id"] for m in json.load(open(args.catalog))["data"]]
    else:
        ids = get_catalog(key)
    print(f"catalog: {len(ids)} models listed", file=sys.stderr)

    results = {}
    with cf.ThreadPoolExecutor(20) as ex:
        for mid, st in ex.map(lambda m: probe(key, m), ids):
            results[mid] = st

    # retry timeouts once (cold starts / busy workers) — use a LONG retry
    # timeout: session finding 2026-09-16 is that 25s→40s retries still killed
    # several working reasoning models (nemotron-ultra-550b, gpt-oss-20b);
    # they need ~120s. A timeout is NOT a 404 — retest generously before
    # writing a model off.
    retries = [m for m, s in results.items() if s.startswith("timeout")]
    if retries:
        print(f"retrying {len(retries)} timeouts...", file=sys.stderr)
        with cf.ThreadPoolExecutor(9) as ex:
            for mid, st in ex.map(lambda m: probe(key, m, timeout=120), retries):
                results[mid] = st

    ok = sorted(m for m, s in results.items() if s == "OK")
    n404 = sorted(m for m, s in results.items() if s == "404")
    other = {m: s for m, s in results.items() if s != "OK" and s != "404"}

    print(f"\nWORKING ({len(ok)}) — safe to add to picker:")
    for m in ok:
        print("  ", m)
    print(f"\n404 not provisioned on this account ({len(n404)}): do NOT add")
    print(f"\nOther errors ({len(other)}):")
    for m, s in sorted(other.items()):
        print(f"   {m} -> {s}")


if __name__ == "__main__":
    main()
