#!/usr/bin/env python3
"""Resolve a `/model …` line offline, exactly as the CLI/gateway resolver does.

Usage:
    python3 probe_model_switch.py '/model minimaxai/minimax-m3.1-flash --provider nvidia'
    python3 probe_model_switch.py minimaxai/minimax-m3.1-flash --provider nvidia

Why: `/model --provider <name>` resolves built-in providers first, so a custom
provider is only reachable as `custom:<slug>`; a bare vendor name dies with
"not connected". This probe prints the parse, the picker slugs, and the
resolution result for the given provider plus every picker slug that could match
it — no TUI, no live API call, no token spend.

Exits 0 when the given provider resolves, 1 otherwise, so it can gate a reply.
"""
import glob
import os
import sys


def _workspace() -> str | None:
    home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    cands = glob.glob(os.path.join(home, "installs", "*", "environments", "*", "workspace"))
    cands += [home, os.path.join(home, "hermes-agent")]
    for c in cands:
        if os.path.isdir(os.path.join(c, "hermes_cli")):
            return c
    return None


ws = _workspace()
if not ws:
    sys.exit("hermes_cli workspace not found — set HERMES_HOME or edit _workspace()")
sys.path.insert(0, ws)

from hermes_cli.inventory import build_models_payload, load_picker_context  # noqa: E402
from hermes_cli.model_switch import parse_model_switch_args, switch_model  # noqa: E402

raw = " ".join(sys.argv[1:]).strip()
if raw.startswith("/model"):
    raw = raw[len("/model"):].strip()

ctx = load_picker_context()
rows = build_models_payload(ctx).get("providers", []) or []
slugs = [r.get("slug") for r in rows if r.get("slug")]

req = parse_model_switch_args(raw)
print("install      :", ws)
print("parsed       : target=%r explicit_provider=%r errors=%r"
      % (req.target, req.explicit_provider, req.errors))
print("current      : %s / %s" % (ctx.current_provider, ctx.current_model))
print("picker slugs : %s" % ", ".join(slugs))

cands: list[str] = []
if req.explicit_provider:
    cands.append(req.explicit_provider)
    want = req.explicit_provider.lower().split(":")[-1]
    cands += [s for s in slugs if s and s != req.explicit_provider and want in s.lower()]

rc = 0
for prov in cands:
    try:
        r = switch_model(raw_input=req.target, current_provider=ctx.current_provider,
                         current_model=ctx.current_model, current_base_url="",
                         current_api_key="", is_global=req.is_global,
                         explicit_provider=prov, user_providers=ctx.user_providers,
                         custom_providers=ctx.custom_providers)
    except Exception as exc:  # noqa: BLE001
        print("%-24s -> EXC %s %s" % (prov, type(exc).__name__, exc))
        rc = 1
        continue
    print("%-24s -> success=%s model=%r provider=%r base=%r\n%swarn=%r\n%serr=%r"
          % (prov, r.success, r.new_model, r.target_provider, r.base_url,
             " " * 24, (r.warning_message or "")[:160], " " * 24, (r.error_message or "")[:200]))
    if prov == req.explicit_provider and not r.success:
        rc = 1

if not cands:
    print("no --provider in the argument; resolved target only:")
    print("  target=%r" % req.target)

sys.exit(rc)
