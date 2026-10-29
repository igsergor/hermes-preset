# `/model` Picker — OpenRouter Model Sourcing (detail)

Condensed from a live session extending the picker to surface free OpenRouter
models (hermes-agent 0.18.0, July 2026).

## Real code path (where the picker gets its list)
```
cli.py::_handle_model_switch
  -> hermes_cli/inventory.build_models_payload
       -> hermes_cli/model_switch.list_authenticated_providers
            -> cached_provider_model_ids(slug)        # reads provider_models_cache.json (TTL)
                 -> provider_model_ids(slug)
                      -> (openrouter) model_ids() -> fetch_openrouter_models()   # hermes_cli/models.py
```

## Files to edit
- `hermes_cli/models.py`
  - `OPENROUTER_MODELS`: curated `list[tuple[id, desc]]`, offline fallback.
  - `fetch_openrouter_models()`: live-refreshed; THE function that drives the picker.
  - `_openrouter_model_is_free(pricing)`: True when prompt AND completion == 0.
  - `_openrouter_model_supports_tools(item)`: True when `supported_parameters` list contains `"tools"` (permissive if field absent).

## Pitfalls (cost real debugging time)
1. **Disk-cache TTL.** After editing source, `provider_models_cache.json` still
   serves the OLD list until invalidated. The picker reads the cache, not the
   source, while fresh. Fix: `clear_provider_model_ids` / `clear_provider_models_cache("openrouter")`
   then `cached_provider_model_ids("openrouter", force_refresh=True)`, OR tell user
   `/model --refresh`.
2. **Dead code.** `model_switch.postprocess_providers_for_picker` calls
   `fetch_openrouter_models` but has ZERO callers. Editing it is invisible.
3. **Curated list lags live.** `OPENROUTER_MODELS` had 4/7 free entries retired
   (not in live catalog) and was missing `tencent/hy3:free` (only had
   `tencent/hy3-preview:free`). Always derive the live free set from the API.
4. **Aggregator = no max_models cap.** OpenRouter model list is NOT truncated by
   `max_models` ("Aggregator: show full catalog regardless of max_models"). Safe
   to append many free models.
5. **`:free` survives switch.** `switch_model` preserves the `:free` variant tag
   (slash = variant, not vendor:model). `tencent/hy3:free` resolves fine.

## Patch pattern that worked
In `fetch_openrouter_models`, after the curated pass builds `curated` (and after
the `if not curated: return ...` guard), append any live free model not already
present:
```python
try:
    _curated_ids = {mid for mid, _ in curated}
    for live_item in live_items:
        if not isinstance(live_item, dict):
            continue
        mid = str(live_item.get("id") or "").strip()
        if not mid or mid in _curated_ids:
            continue
        if not _openrouter_model_is_free(live_item.get("pricing")):
            continue
        if not _openrouter_model_supports_tools(live_item):
            continue
        curated.append((mid, "free"))
        _curated_ids.add(mid)
except Exception:
    pass
```
This took the picker from 3 visible free models to 19 (all currently-callable,
tools-supported, price 0/0), including `tencent/hy3:free`.

## Verification recipe (run in hermes-agent venv)
```python
from hermes_cli.models import fetch_openrouter_models, cached_provider_model_ids, clear_provider_models_cache
res = fetch_openrouter_models(force_refresh=True)
assert "tencent/hy3:free" in [m for m, _ in res]
clear_provider_models_cache("openrouter")
ids = cached_provider_model_ids("openrouter", force_refresh=True)
assert "tencent/hy3:free" in ids and len([m for m in ids if m.endswith(":free")]) >= 19
from hermes_cli.model_switch import switch_model
r = switch_model(raw_input="tencent/hy3:free", current_provider="openrouter",
                 current_model="anthropic/claude-sonnet-4.6",
                 current_base_url="https://openrouter.ai/api/v1",
                 current_api_key="", is_global=False, explicit_provider="openrouter")
assert r.success and r.new_model == "tencent/hy3:free"
```

## Enumerate live free models directly
```
curl -s https://openrouter.ai/api/v1/models | python3 -c "
import sys,json
for m in json.load(sys.stdin)['data']:
    p=m.get('pricing',{})
    if p.get('prompt')=='0' and p.get('completion')=='0' and 'tools' in (m.get('supported_parameters') or []):
        print(m['id'])
"
```
