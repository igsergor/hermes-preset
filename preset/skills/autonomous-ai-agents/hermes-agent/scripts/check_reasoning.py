#!/usr/bin/env python3
"""Print the EFFECTIVE reasoning config Hermes will use, per model.

Run with the checkout's interpreter so `hermes_constants` imports cleanly:

    <hermes-home>/hermes-agent/venv/bin/python scripts/check_reasoning.py [model-id ...]

Always reports `model.default`; extra ids on the command line are resolved too, so a
per-model `agent.reasoning_overrides` entry can be proven to win (and neighbours proven
unaffected) before telling the user it is set.
"""

from __future__ import annotations

import glob
import os
import sys


def hermes_home() -> str:
    return os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")


def find_checkout() -> str:
    candidates = [
        os.environ.get("HERMES_AGENT_DIR") or "",
        os.path.join(hermes_home(), "hermes-agent"),
    ]
    candidates += sorted(glob.glob(os.path.join(os.path.expanduser("~"), "hermes*", "hermes_constants.py")))
    for cand in candidates:
        if not cand:
            continue
        if cand.endswith("hermes_constants.py"):
            return os.path.dirname(cand)
        if os.path.isfile(os.path.join(cand, "hermes_constants.py")):
            return cand
    sys.exit("could not locate the hermes-agent checkout; set HERMES_AGENT_DIR")


REPO = find_checkout()
sys.path.insert(0, REPO)

from hermes_constants import resolve_reasoning_config  # noqa: E402


def load_config() -> dict:
    try:
        from hermes_cli.config import load_config as _load  # merged config, same as the runtime

        return _load() or {}
    except Exception:
        import yaml

        with open(os.path.join(hermes_home(), "config.yaml")) as fh:
            return yaml.safe_load(fh) or {}


def main() -> int:
    cfg = load_config()
    model_cfg = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    default_model = str(model_cfg.get("default") or "").strip()
    agent_cfg = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}

    print(f"repo:              {REPO}")
    print(f"default model:     {default_model} ({model_cfg.get('provider') or 'provider?'})")
    print(f"global effort:     {agent_cfg.get('reasoning_effort')!r}")
    print(f"per-model map:     {agent_cfg.get('reasoning_overrides') or {}}")
    print()

    ids = [default_model] + [a for a in sys.argv[1:] if a.strip()]
    seen: set[str] = set()
    for model in ids:
        if not model or model in seen:
            continue
        seen.add(model)
        print(f"{model:45} -> {resolve_reasoning_config(cfg, model)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
