#!/usr/bin/env python3
"""Show exactly which provider rows + models the Hermes picker will render.

Why: a `custom_providers` entry can be correct in config.yaml yet invisible in
the Telegram/Discord /model picker (or vice-versa). Restarting the gateway and
eyeballing the client is slow and ambiguous. This script builds the picker
payload in-process from the on-disk config, so you can tell a *config* problem
from a *cache/restart* problem immediately.

Usage:
    ./venv/bin/python verify-picker-providers.py [NAME-FILTER]

    NAME-FILTER  optional case-insensitive substring; only matching rows are
                 printed in detail (all row names are always summarised).

Run it with the hermes-agent venv interpreter, e.g.
    cd ~/.hermes/hermes-agent && ./venv/bin/python \
        ~/.hermes/skills/devops/custom-provider-config/scripts/verify-picker-providers.py

If invoked with a different Python that lacks the deps, the script re-execs
itself with the venv interpreter when it can find one.
"""

from __future__ import annotations

import os
import subprocess
import sys

# ── locate the hermes-agent install ─────────────────────────────────────────
HERMES_AGENT_DIR = os.environ.get(
    "HERMES_AGENT_DIR", os.path.expanduser("~/.hermes/hermes-agent")
)
CONFIG_PATH = os.environ.get(
    "HERMES_CONFIG", os.path.expanduser("~/.hermes/config.yaml")
)


def _venv_python() -> str | None:
    for candidate in (
        os.path.join(HERMES_AGENT_DIR, "venv", "bin", "python"),
        os.path.join(HERMES_AGENT_DIR, ".venv", "bin", "python"),
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _maybe_reexec() -> None:
    """Re-exec under the venv interpreter if we are not already running it."""
    venv_py = _venv_python()
    if not venv_py:
        return
    # Same interpreter? nothing to do.
    try:
        if os.path.samefile(venv_py, sys.executable):
            return
    except OSError:
        pass
    # Already able to import the package? nothing to do.
    try:
        import hermes_cli  # noqa: F401

        return
    except Exception:
        pass
    os.execv(venv_py, [venv_py, os.path.abspath(__file__), *sys.argv[1:]])


def main() -> int:
    _maybe_reexec()

    if not os.path.isdir(HERMES_AGENT_DIR):
        print(f"hermes-agent dir not found: {HERMES_AGENT_DIR}", file=sys.stderr)
        return 2
    sys.path.insert(0, HERMES_AGENT_DIR)

    try:
        from hermes_cli.inventory import (  # noqa: E402
            build_models_payload,
            load_picker_context,
        )
    except Exception as exc:  # pragma: no cover - import surface drift
        print(f"could not import hermes_cli.inventory: {exc}", file=sys.stderr)
        print(
            "Run this with the hermes-agent venv interpreter "
            "(./venv/bin/python) or set HERMES_AGENT_DIR.",
            file=sys.stderr,
        )
        return 2

    needle = (sys.argv[1] if len(sys.argv) > 1 else "").lower()

    # `probe_custom_providers=False` keeps local/offline endpoints from
    # blocking the build — the configured model list still renders, which is
    # exactly what we want to inspect.
    ctx = load_picker_context()
    payload = build_models_payload(ctx, probe_custom_providers=False)
    rows = payload.get("providers") or []

    print(f"config      : {CONFIG_PATH}")
    print(f"provider rows: {len(rows)}\n")

    # Always summarise every row so a *missing* provider is obvious.
    names = []
    for row in rows:
        name = row.get("name") or row.get("id") or row.get("provider") or "?"
        count = len(row.get("models") or [])
        names.append(f"{name} ({count})")
    print("rows:", ", ".join(names) if names else "(none)")
    print()

    matched = 0
    for row in rows:
        name = row.get("name") or row.get("id") or row.get("provider") or "?"
        if needle and needle not in str(name).lower():
            continue
        matched += 1
        models = row.get("models") or []
        labels = [m if isinstance(m, str) else m.get("name") for m in models]
        print(f"--- {name}")
        print(f"    base_url : {row.get('base_url')}")
        print(f"    models   : {len(models)}")
        print(f"    labels   : {labels}")
        print()

    if needle and not matched:
        print(f"NO row matched {needle!r} — the provider is absent from the picker payload.")
        print("Check `custom_providers` in config.yaml (see the skill's")
        print('"provider vanished from the picker" section).')
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
