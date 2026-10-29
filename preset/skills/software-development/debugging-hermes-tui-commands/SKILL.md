---
name: debugging-hermes-tui-commands
description: "Debug Hermes TUI slash commands: Python, gateway, Ink UI."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, hermes-agent, tui, slash-commands, typescript, python]
    related_skills: [python-debugpy, node-inspect-debugger, systematic-debugging]
---

# Debugging Hermes TUI Slash Commands

## Overview

Hermes slash commands span three layers — Python command registry, tui_gateway JSON-RPC bridge, and the Ink/TypeScript frontend. When a command misbehaves (missing from autocomplete, works in CLI but not TUI, config persists but UI doesn't update), the bug is almost always one layer being out of sync with another.

Use this skill when you encounter issues with slash commands in the Hermes TUI, particularly when commands aren't showing in autocomplete, aren't working properly in the TUI, or need to be added/updated.

## When to Use

- A slash command exists in one part of the codebase but doesn't work fully
- A command needs to be added to both backend and frontend
- Command autocomplete isn't working for specific commands
- Command behavior is inconsistent between CLI and TUI
- A command persists config but doesn't apply live in the TUI

## Architecture Overview

```
Python backend (hermes_cli/commands.py)     <- canonical COMMAND_REGISTRY
       │
       ▼
TUI gateway (tui_gateway/server.py)         <- slash.exec / command.dispatch
       │
       ▼
TUI frontend (ui-tui/src/app/slash/)        <- local handlers + fallthrough
```

Command definitions must be registered consistently across Python and TypeScript to work properly. The Python `COMMAND_REGISTRY` is the source of truth for: CLI dispatch, gateway help, Telegram BotCommand menu, Slack subcommand map, and autocomplete data shipped to Ink.

## Investigation Steps

1. **Check if the command exists in the TUI frontend:**
   ```bash
   search_files --pattern "/commandname" --file_glob "*.ts" --path ui-tui/
   search_files --pattern "/commandname" --file_glob "*.tsx" --path ui-tui/
   ```

2. **Examine the TUI command definition:**
   ```bash
   read_file ui-tui/src/app/slash/commands/core.ts
   # If not there:
   search_files --pattern "commandname" --path ui-tui/src/app/slash/commands --target files
   ```

3. **Check if the command exists in the Python backend:**
   ```bash
   search_files --pattern "CommandDef" --file_glob "*.py" --path hermes_cli/
   search_files --pattern "commandname" --path hermes_cli/commands.py --context 3
   ```

4. **Examine the gateway implementation:**
   ```bash
   search_files --pattern "complete.slash|slash.exec" --path tui_gateway/
   ```

## Fix: Missing Command Autocomplete

If a command exists in the TUI but doesn't show in autocomplete:

1. Add a `CommandDef` entry to `COMMAND_REGISTRY` in `hermes_cli/commands.py`:
   ```python
   CommandDef("commandname", "Description of the command", "Session",
              cli_only=True, aliases=("alias",),
              args_hint="[arg1|arg2|arg3]",
              subcommands=("arg1", "arg2", "arg3")),
   ```

2. Pick `cli_only` vs gateway availability carefully:
   - `cli_only=True` — only in the interactive CLI/TUI
   - `gateway_only=True` — only in messaging platforms
   - neither — available everywhere
   - `gateway_config_gate="display.foo"` — config-gated availability in the gateway

3. Ensure `subcommands` matches the expected tab-completion options shown by the TUI.

4. If the command runs server-side, add a handler in `HermesCLI.process_command()` in `cli.py`:
   ```python
   elif canonical == "commandname":
       self._handle_commandname(cmd_original)
   ```

5. For gateway-available commands, add a handler in `gateway/run.py`:
   ```python
   if canonical == "commandname":
       return await self._handle_commandname(event)
   ```

## Common Issues

1. **Command shows in TUI but not in autocomplete.** The command is defined in the TUI codebase but missing from `COMMAND_REGISTRY` in `hermes_cli/commands.py`. Autocomplete data ships from Python.

2. **Command shows in autocomplete but doesn't work.** Check the command handler in `tui_gateway/server.py` and the frontend handler in `ui-tui/src/app/createSlashHandler.ts`. If the command is local-only in Ink, it must be handled in `app.tsx` built-in branch; otherwise it falls through to `slash.exec` and must have a Python handler.

3. **Command behavior differs between CLI and TUI.** The command might have different implementations. Check both `cli.py::process_command` and the TUI's local handler. Local TUI handlers take precedence over gateway dispatch.

4. **Command persists config but doesn't apply live.** For TUI-local commands, updating `config.set` is not enough. Also patch the relevant nanostore state immediately (usually `patchUiState(...)`) and pass any new state through rendering components. Example: `/details collapsed` must update live detail visibility, not just save `details_mode`; in-session global `/details <mode>` may need a separate command-override flag so live commands can override built-in section defaults while startup/config sync preserves default-expanded thinking/tools behavior.

5. **Gateway dispatch silently ignores the command.** The gateway only dispatches commands it knows about. Check `GATEWAY_KNOWN_COMMANDS` (derived from `COMMAND_REGISTRY` automatically) includes the canonical name. If the command is `cli_only` with a `gateway_config_gate`, verify the gated config value is truthy.

## The `/model` Picker — Model Sourcing Path (OpenRouter & aggregators)

`/model` is a slash command whose picker list is built in Python, NOT in the
Ink frontend. When you need to change *which models appear* (e.g. add free
OpenRouter models, fix a missing model), the relevant code is:

```
cli.py::_handle_model_switch            # parses /model, opens picker or switches
  -> hermes_cli/inventory.build_models_payload
       -> hermes_cli/model_switch.list_authenticated_providers
            -> cached_provider_model_ids(slug)        # disk-cached
                 -> provider_model_ids(slug)
                      -> (openrouter) model_ids() -> fetch_openrouter_models()
                           hermes_cli/models.py  <-- EDIT HERE for the model list
```

Key facts (verified against hermes-agent 0.18.0):

- The **canonical model catalog for OpenRouter lives in `hermes_cli/models.py`**
  in two places: `OPENROUTER_MODELS` (curated `list[tuple[id, desc]]` fallback)
  and `fetch_openrouter_models()` (live-refreshed; merges curated against the
  live OpenRouter `/v1/models` catalog, drops models lacking tool-calling
  support via `_openrouter_model_supports_tools`, tags `free` when
  `_openrouter_model_is_free(pricing)` -> prompt+completion price == 0).
- **`provider_model_ids("openrouter")` calls `model_ids()` -> `fetch_openrouter_models()`.**
  So editing `fetch_openrouter_models` DOES affect the picker.
- **Dead-code trap:** `hermes_cli/model_switch.postprocess_providers_for_picker`
  also calls `fetch_openrouter_models`, but it is **never invoked anywhere**
  (grep confirms zero callers). Do not rely on it - patch `fetch_openrouter_models`
  directly.
- **Disk-cache TTL trap:** `cached_provider_model_ids` reads
  `$HERMES_HOME/provider_models_cache.json` and serves it while fresh (TTL).
  After editing the source, the picker STILL shows the old list until the cache
  is invalidated. Force a rebuild with `cached_provider_model_ids(slug,
  force_refresh=True)` or tell the user to run `/model --refresh`.
- OpenRouter is treated as a **routing aggregator**: its model list is NOT
  capped by `max_models` (see `list_authenticated_providers` - "Aggregator:
  show full catalog regardless of max_models"). Appending free models is safe;
  they won't be truncated.
- `:free` variant tags are preserved through `switch_model` (a slash means a
  variant tag, not vendor:model - conversion to slash only happens when there's
  NO slash already). So `tencent/hy3:free` resolves correctly.
- To surface ALL currently-callable free models (not just curated), append live
  free models inside `fetch_openrouter_models` after the curated pass:
  iterate `live_items`, skip already-present ids, require
  `_openrouter_model_is_free(pricing)` AND `_openrouter_model_supports_tools`,
  then `curated.append((mid, "free"))`. See `references/model_picker_openrouter.md`.

## `/model --provider` — built-in names vs custom providers

`--provider <name>` resolves against Hermes' **built-in** provider registry
first. A provider defined under `custom_providers:` in `config.yaml` is
addressed by its picker **slug** `custom:<lowercased name>`. So
`--provider NVIDIA` for a custom entry literally named `NVIDIA` resolves to the
built-in `nvidia` and dies on credentials (`Nvidia is not connected: no API key
or login was found for it … Set NVIDIA_API_KEY`) even though the custom entry
holds a working key. Any name that collides with a built-in behaves the same
(`nvidia`, `openai`, `mistral`, `deepseek`, …) — case does not disambiguate.
Correct form: `/model <model-id> --provider custom:<slug>`.

- **Unicode dashes are a red herring.** `parse_model_flags_detailed`
  deliberately normalizes the Unicode dash range U+2012-U+2015 before a flag
  keyword to `--` (Telegram/iOS autocorrect), so a pasted `—provider nvidia`
  parses identically to `--provider`. Diagnose the provider name, not the dash.
- **A model missing from the provider's `models:` list still switches.** The
  switch succeeds with the provider's real id; a display alias instead gets
  `Note: … was not found in this custom endpoint's model listing`, and with
  `discover_models: false` the model never appears in the picker even though the
  upstream `/v1/models` exposes it.

### Offline resolution probe (no TUI, no live API)

Resolve a `/model` line against the real context before answering the user:

```python
import sys; sys.path.insert(0, "<hermes install>/workspace")   # dir holding hermes_cli/
from hermes_cli.inventory import load_picker_context, build_models_payload
from hermes_cli.model_switch import parse_model_switch_args, switch_model
ctx = load_picker_context()                    # real custom_providers + user_providers + current model
rows = build_models_payload(ctx)["providers"]  # each row carries the picker slug, e.g. "custom:nvidia"
req = parse_model_switch_args("minimaxai/minimax-m3.1-flash —provider nvidia")
r = switch_model(raw_input=req.target, current_provider=ctx.current_provider,
                 current_model=ctx.current_model, current_base_url="", current_api_key="",
                 is_global=req.is_global, explicit_provider=req.explicit_provider,
                 user_providers=ctx.user_providers, custom_providers=ctx.custom_providers)
```

**Pass `user_providers`/`custom_providers` from `load_picker_context()`.** With
the defaults (`None`) custom providers are invisible to resolution and *every*
custom name fails with the credential error — a misleading result that reads as
the user's mistake. Ready-made runner: `scripts/probe_model_switch.py`.

## Debugging Tactics

When surface-level inspection doesn't reveal the bug:

- **Python side hangs or misbehaves:** use the `python-debugpy` skill to break inside `_SlashWorker.exec` or the command handler. `remote-pdb` set at the handler entry is the fastest path.
- **Ink side not reacting:** use the `node-inspect-debugger` skill to break in `app.tsx`'s slash dispatch or the local command branch. `sb('dist/app.js', <line>)` after `npm run build`.
- **Registry mismatch / unclear which side is wrong:** compare the canonical `COMMAND_REGISTRY` entry against the TUI's local command list side-by-side.

## Pitfalls

- Don't forget to set the appropriate category for the command in `CommandDef` (e.g., "Session", "Configuration", "Tools & Skills", "Info", "Exit")
- Make sure any aliases are properly registered in the `aliases` tuple — no other file changes are needed, everything downstream (Telegram menu, Slack mapping, autocomplete, help) derives from it
- For commands with subcommands, ensure the `subcommands` tuple in `CommandDef` matches what's in the TUI code
- `cli_only=True` commands won't work in gateway/messaging platforms — unless you add a `gateway_config_gate` and the gate is truthy
- After adding live UI state, search every consumer of the old prop/helper and thread the new state through all render paths, not just the active streaming path. TUI detail rendering has at least two important paths: live `StreamingAssistant`/`ToolTrail` and transcript/pending `MessageLine` rows. A `/clean` pass should explicitly check both.
- Rebuild the TUI (`npm --prefix ui-tui run build`) before testing — tsx watch mode may lag on first launch
- **`/model` picker edits need cache invalidation.** Editing `hermes_cli/models.py`
  (e.g. `fetch_openrouter_models` / `OPENROUTER_MODELS`) will NOT show up in the
  picker until `$HERMES_HOME/provider_models_cache.json` is rebuilt. The TTL is
  long enough that a plain `/model` open reads the stale list. Rebuild with
  `cached_provider_model_ids("openrouter", force_refresh=True)` or instruct the
  user to run `/model --refresh`.
- **Don't patch `postprocess_providers_for_picker`.** It calls
  `fetch_openrouter_models` but has zero callers (dead code). Changes there are
  invisible to the picker.
- **Curated `OPENROUTER_MODELS` lags the live catalog.** Free models get retired
  (e.g. `tencent/hy3-preview:free` -> `tencent/hy3:free`) without warning. Prefer
  deriving the free list live from the OpenRouter `/v1/models` endpoint over
  hardcoding, so the picker reflects what's actually callable.

## Verification

After fixing:

1. Rebuild the TUI:
   ```bash
   cd /home/bb/hermes-agent && npm --prefix ui-tui run build
   ```

2. Run the TUI and test the command:
   ```bash
   hermes --tui
   ```

3. Type `/` and verify the command appears in autocomplete suggestions with the expected description and args hint.

4. Execute the command and confirm:
   - Expected behavior fires
   - Any persisted config updates correctly (`read_file ~/.hermes/config.yaml`)
   - Live UI state reflects the change immediately (not just after restart)

5. If the command is also gateway-available, test it from at least one messaging platform (or run the gateway tests: `scripts/run_tests.sh tests/gateway/`).

## Verifying `/model` Picker Model-List Changes

After editing `hermes_cli/models.py` for the OpenRouter catalog:

```python
# Reproduce in the hermes-agent venv (cd ~/.hermes/hermes-agent && source venv/bin/activate)
from hermes_cli.models import fetch_openrouter_models, cached_provider_model_ids, clear_provider_models_cache
# 1) Live function returns the new set (force_refresh bypasses memory cache):
res = fetch_openrouter_models(force_refresh=True)
free = [m for m, d in res if "free" in d.lower()]
assert "tencent/hy3:free" in [m for m, _ in res]   # your target model present
# 2) Invalidate the on-disk picker cache, then the real picker path:
clear_provider_models_cache("openrouter")
ids = cached_provider_model_ids("openrouter", force_refresh=True)
assert "tencent/hy3:free" in ids
# 3) Confirm switch_model resolves it (no live API call needed):
from hermes_cli.model_switch import switch_model
r = switch_model(raw_input="tencent/hy3:free", current_provider="openrouter",
                 current_model="anthropic/claude-sonnet-4.6",
                 current_base_url="https://openrouter.ai/api/v1",
                 current_api_key="", is_global=False, explicit_provider="openrouter")
assert r.success and r.new_model == "tencent/hy3:free"
```
Direct live-catalog probe (to enumerate all currently-free models):
`curl -s https://openrouter.ai/api/v1/models | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data'] if m.get('pricing',{}).get('prompt')=='0' and m.get('pricing',{}).get('completion')=='0' and 'tools' in (m.get('supported_parameters') or [])]"`
See `references/model_picker_openrouter.md` for the full reproduction recipe and gotchas.
