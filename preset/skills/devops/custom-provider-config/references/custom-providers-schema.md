# Custom Providers Schema Reference

## Full YAML Structure

```yaml
model:
  provider: custom
  base_url: "https://api.example.com/v1"
  api_key: "sk-..."
  default: "provider/model-name"

custom_providers:
  - name: "Display Name"              # Required: shown in picker row label
    base_url: "https://api.example.com/v1"  # Required: API endpoint
    api_key: "sk-..."                 # Optional: inline key (or use key_env)
    key_env: "ENV_VAR_NAME"           # Optional: env var for key
    api_mode: "openai_chat"           # Optional: transport type
    discover_models: true             # Optional: probe /models endpoint (default: true)
    models:                           # Required for picker: explicit model list
      - id: "provider/model-name"     # Required: exact model ID for API
        name: "Display Label"         # Required: shown in picker
      - id: "provider/other-model"
        name: "Other Label"
    extra_headers:                    # Optional: custom headers
      X-Custom-Header: "value"
```

## Field Details

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name for picker row; prefix before " — " used for grouping |
| `base_url` | string | Yes | OpenAI-compatible API base URL |
| `api_key` | string | No | Inline API key (secret) |
| `key_env` | string | No | Environment variable name for API key |
| `api_mode` | string | No | Transport: `openai_chat`, `anthropic_messages`, etc. |
| `discover_models` | boolean | No | Auto-probe `/models` endpoint (default: true) |
| `models` | array | Yes* | Explicit model list for picker; each item has `id` and `name` |
| `extra_headers` | object | No | Additional headers sent with requests |

*Required for picker visibility. Without `models`, the provider row appears but shows no models until `/models` is probed.

## Grouping Logic

Hermes groups custom_providers by:
```
(api_url, credential_identity, api_mode, extra_headers_hash, display_prefix)
```

Where `display_prefix` = text before " — " or " - " in `name`.

**Same group = single picker row with merged models.**

## Gateway Restart Required

Changes to `custom_providers` only take effect after:
```bash
systemctl --user restart hermes-gateway
```

Scope nuance: the restart is only needed for the **active model** side of the change. The picker *listing* is rebuilt on every `/model` open with no restart.

The restart must be run from a **separate shell** (SSH), never from inside the gateway process — the terminal tool hard-blocks restart commands while the agent runs as a gateway child, and the guard also catches `hermes gateway restart` and background-wrapper variants.

## Example: Cline / ClinePass

```yaml
model:
  provider: custom
  base_url: https://api.cline.bot/api/v1
  api_key: sk_...
  default: cline-pass/minimax-m3

custom_providers:
  - name: ClinePass
    base_url: https://api.cline.bot/api/v1
    models:
      - id: cline-pass/glm-5.3
        name: cp/GLM-5.3
      - id: cline-pass/minimax-m3
        name: cp/MiniMax M3
      # ... etc
```