# Google AI Studio (Gemini) — Custom Provider Reference

## Overview

Google AI Studio provides access to Gemini models via the Generative Language API.
Unlike ClinePass/Mistral, it uses a **query-parameter style API key** (`AQ.Ab8...`) rather than standard Bearer tokens.

## Configuration Pattern

```yaml
custom_providers:
  - name: "Google AI Studio"
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    api_key: "ВАШ_GOOGLE_AI_STUDIO_КЛЮЧ"
    models:
      - id: "googleai/gemini-1.5-flash"
        name: "cp/gemini-1.5-flash"
        context_length: 1048576
      - id: "googleai/gemini-1.5-pro"
        name: "cp/gemini-1.5-pro"
        context_length: 1048576
```

## Key Differences from Other Providers

| Aspect | Google AI Studio | ClinePass / Mistral |
|--------|------------------|---------------------|
| **Auth method** | Query parameter `?key=API_KEY` or inline `api_key` in config | Bearer token via `key_env` |
| **API key format** | `AQ.Ab8...` (starts with `AQ.`) | `sk-...` |
| **Base URL** | `https://generativelanguage.googleapis.com/v1beta` | Standard `/v1` paths |
| **Model ID prefix** | `googleai/` | `cline-pass/`, `ministral-*`, etc. |

## Why `api_key` instead of `key_env`?

Hermes' gateway reads credentials from the `custom_providers` entry. For standard OpenAI-compatible APIs, it expects a Bearer token via `key_env` (reads from `.env`). But Google AI Studio keys are passed as **query parameters** in the request URL (`?key=...`), not in the Authorization header. When you provide an inline `api_key` in the provider entry, Hermes detects the non-standard format and handles it correctly.

## Models & Context Windows

| Model ID | Display Name | Context Length |
|----------|--------------|----------------|
| `googleai/gemini-1.5-flash` | `cp/gemini-1.5-flash` | 1,048,576 (1M) |
| `googleai/gemini-1.5-pro` | `cp/gemini-1.5-pro` | 1,048,576 (1M) |

## Verification

Test the API key and a model:

```bash
curl -s -H "Content-Type: application/json" \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=ВАШ_GOOGLE_AI_STUDIO_КЛЮЧ" \
  -X POST -d '{"contents":[{"parts":[{"text":"hi"}]}]}' | python3 -m json.tool
```

List available models:

```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=ВАШ_GOOGLE_AI_STUDIO_КЛЮЧ" | python3 -m json.tool
```

## Gateway Restart Required

After adding/updating the provider:

```bash
systemctl --user restart hermes-gateway
```

**Must run from a separate shell** (not inside the gateway process) — SIGTERM propagates to child processes and kills the restart command.

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Models don't appear in picker | Used `key_env` instead of inline `api_key` | Use inline `api_key` in `custom_providers` entry |
| "Provider authentication failed" | Missing `api_key` in provider entry | Add `api_key: "AQ.Ab8..."` directly in the provider block |
| Wrong base URL | Used `/v1` instead of `/v1beta` | Use `https://generativelanguage.googleapis.com/v1beta` |