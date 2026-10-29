# Reformboss aggregator (api.reformboss.com/v1)

OpenAI-compatible gateway. Key from Telegram bot `@iishkogatewaybot` or the reformboss.com cabinet. Standard `Authorization: Bearer <key>`.

## Catalog (authed `/v1/models`, 10 ids)

- deepseek-v4-flash, deepseek-v4.1-flash, glm-5.3, glm-5.3-flash, kimi-k3,
  qwen-max, qwen-plus, qwen3.8-27b, qwen3.8-flash, qwen3.8-max

A wider candidate list (24 names incl. deepseek-v4.1-flash-1017, qwen3.8-max-0902,
image/video models) circulates from the Mini App and older probes — those extra
names are NOT in `/v1/models` and fail with `model_access_denied`.

## Working chat models (streaming ping, 2-of-3 rule)

deepseek-v4-flash, deepseek-v4.1-flash, glm-5.3, kimi-k3, qwen-max, qwen-plus,
qwen3.8-27b, qwen3.8-flash, qwen3.8-max.

**deepseek-v4.1-flash sees images** — proven 25.10.26 by posting user's own
screenshot as base64 `image_url` and getting the exact `Provider: iishko` line
back (finish: stop + a `reasoning_content` trace describing the image). Full
reliability data below (headline: it hallucinates page numbers ~7/8 of the
time, so route Hermes vision through `combo/hermesvision`, not any bare member).

## Vision by model — matrix (2026-10-26, real book photo 3840×2160 → 1600px, pages 66/67)

"Can it see at all" and "is it reliable" are different questions here:

- deepseek-v4-flash, deepseek-v4.1-flash: sometimes fully correct end-to-end
  (`Provider: iishko`, all captions), sometimes `finish_reason: length` with
  EMPTY content (the thinking trace eats the whole window), sometimes OCR-
  style digression (random body text instead of an answer), sometimes half-
  invented captions. Zero-vision it is NOT, stable it is NOT.
- glm-5.3: TEXT-ONLY on this gateway — `max_tokens` high or not, image is
  ignored. Never point image turns at it.
- kimi-k3 (direct + via OmniRoute): also `length`-loops with empty content on
  images. Documented in the catalog as `attachment: false` on one provider and
  `true` on another — upstream is unstable, not reliably vision here.
- max_tokens does NOT fix the loop: 400/600/1500/2000/3000/4000/8000 all hit
  `length`-empty at roughly the same rate. Do not "raise the budget and retry"
  as a cure.

Excluded: glm-5.3-flash is listed in `/v1/models` but fails streaming chat with
`invalid_request` — keep it out of `models:` until a probe passes it.

## Probe rules (all verified against this endpoint)

- Probe with `"stream": true` only — non-streaming curl gives false negatives
  on this gateway; a model is WORKING only if it answers via streaming in
  >=2 of 3 attempts. Single-ping failure (`upstream_unavailable`,
  e.g. deepseek-v4-flash flapping) is transient — never drop a model from
  `models:` on one failure.
- Never test with the key as shown in tool output — Hermes redacts secrets
  (`api_key: «redacted:sk-…»`, Bearer `***`), and the masked string yields a
  false `invalid_api_key`. Read the real key from config.yaml in-process and
  use it without printing (print only error code/message, never key material).
- HTTP 403 `model_access_denied` naming the Mini App / `@iishkogatewaybot`
  `/profile` sync is a key-rank restriction, not a config error — the fix is
  on the key side. Hermes marks the pool exhausted and falls back (beam-free);
  a stale `exhausted` in auth.json after such an episode is history, not state.
- Provider display name is `iishko`; slug `custom:iishko`; model label prefix
  `iishko/`. The bare name `Reformboss` in `auth.json` (`custom:reformboss`,
  empty pool) is a leftover from before the rename — not a second provider.

## Wrong endpoint for chat

model_endpoint_mismatch: wan2.2-t2i-flash, wanx2.1-t2i-turbo (image models).

## Reasoning-model quirk

glm-5.3, glm-5.3-flash, deepseek-v4.1-flash, qwen3.8-max return `content: null` until `max_tokens` is high enough (≈500–2000) — the first 200 tokens are reasoning. Hermes' default budget can yield empty replies and trigger fallback. Raise max_tokens or avoid these for short-turn use.

## Context windows

`/v1/models` reports no context field (all `created: 1626777600`). Set `context_length` per model manually; fall back to 256,000 otherwise (compresses early). Authoritative source: OpenRouter catalog for the base model.

## Probe script (`~/.hermes/scripts/iishko_probe.py`) — config writer MUST be indent-aware

The daily probe (cron `iishko_probe.py`, 09:00 +04) rewrites `models:` in config.yaml
from its probe results. The FIRST version used raw substring surgery and silently
corrupted the config twice:

- It searched `raw.find("\n- name:", models_idx)` for the next provider — but every
  provider row is indented (`  - name:`), so the search never matched, `end` fell back
  to `len(raw)`, and everything after the iishko block (the whole `telemetry:` section)
  was deleted.
- Its replacement block wrote model items at 2-space indent instead of 6, so the items
  escaped the provider mapping and YAML parsed them as **9 separate top-level providers**
  named `iishko/<model>`, each with 0 models. The picker then showed the `iishko` row with
  a single/zero model even though the config "parsed".

Rule: a script that edits config.yaml must (a) locate the provider block by LINE and
indent (`  - name: iishko` → `    models:` → items at `      `), (b) end the block at the
first non-blank line indented less than the items, (c) re-parse the result with
`yaml.safe_load`, (d) assert the provider's model ids equal the intended list and that
provider names are unique, and (e) only then write, after a timestamped backup. Any
check failing ⇒ refuse to write. Fix applied 2026-10-25; the pathological signature to
re-check after any future edit is `custom_providers` = 15 and `verify-picker-providers.py`
reporting `provider rows: 19` with zero entries named `iishko/<model>` (the broken state
read `provider rows: 24`).

### Repair recipe when the config is already corrupted

Restore from the last good backup (`~/.hermes/backups/config/config.yaml.good.*`) or
re-splice by line: keep everything up to `    models:`, emit items at 6-space indent,
then splice back the real following block (usually `telemetry:`) that was eaten. Verify
with `yaml.safe_load`, then `scripts/verify-picker-providers.py iishko` must show 9 models
and zero `iishko/<model>` provider names (bogus rows).

### Symptom seen by the user

The Telegram `/model` picker showed `Provider: iishko` with ONLY the currently active
model (`deepseek-v4.1-flash`) as a button. Cause: the corrupted config left the iishko row
with `models: []`, and a provider row with no models renders just the current selection.
No restart is needed to fix the listing — the picker rebuilds from config on every
`/model` open and the in-process config cache is keyed on the file's mtime/size, so an
on-disk edit invalidates it.

## Also registered INSIDE OmniRoute (2026-10-26)

iishko exists twice on purpose: as a **direct** Hermes custom provider
(`custom:iishko`, its own picker row) and as an **OmniRoute node** so combos can
route to it. Do not "dedupe" either one.

- node `openai-compatible-chat-cb3be958-ce71-4dec-ba8a-986ec9cb2782`, name
  `iishko`, prefix `iishko`, apiType `chat`, baseUrl `https://api.reformboss.com/v1`
- connection `e12f360e-a5c6-4b2c-9213-13352c728215` (authType apikey, autoSync on)
- after `POST /api/providers/<connId>/sync-models` the OmniRoute catalog carries
  all 10 ids as `iishko/<model>`
- combo `OpenCodeGo1` (`742a54fb-bd44-4f8e-a8b4-54fea6bdd2c1`) now starts with
  `iishko/deepseek-v4.1-flash`; the `beam` member was removed on request.
  combo `hermesvision` (`8a4e7b69-74b1-4d82-9fa6-6751a9679bd6`, ORDER MATTERS):
  currently `iishko/deepseek-v4.1-flash` → `combo/myvisionfree` →
  `ocgo/muse-spark-1.3-contributor`. Do NOT reorder to
  iishko → muse-spark → myvisionfree: the auto-promote ratchet (one-way,
  promote-on-success, NO demotion — the 2026-09-16 lesson documented in
  omniroute-routing.md) would pin the wrong member; myvisionfree must stay
  between iishko and muse-spark as the fallback ladder.
  Verify by routing + `call_logs.summary.comboStepId`, not by response model name.
- hermesvision + Vision Bridge behaviour (measured, do not guess): the bridge
  reroutes ONLY when the combo's first-step decision is `no-vision`; a nested
  `combo/myvisionfree` step counts via `resolveComboRefVisionCapability`, but
  some steps may parse as bare ids (`myvisionfree-model-N`) whose capability
  resolves NULL — `evaluateModelStepCapability` then marks them
  `"non-vision"` explicitly. With the current order the combo still reaches
  the free rung reliably; the observed failure (all-502) came from a high
  `max_tokens` (700) on the image turn of a reasoning model whose thinking
  trace ate the window — not from the bridge — and disappeared at 400/600.
- Vision-capability wiring (2026-10-25, non-obvious): reformboss's `/v1/models`
  exposes NO modality info, so OmniRoute's catalog says
  `capabilities: {tool_calling, reasoning}` with no `vision` — the Vision Bridge
  guardrail then evaluates every hermesvision step as non-vision and reroutes
  image requests to `antigravity/gemini-3.1-flash-lite` (the fastest synced
  vision model with usable credentials) even though the first combo member IS
  vision-capable. The static spec table (`modelSpecs.ts`) knows glm-5.3-flash
  (`supportsVision: true`) but NOT deepseek-v4.1-flash — which is why
  `iishko/glm-5.3` advertised `vision: true` while `iishko/deepseek-v4.1-flash`
  did not. Fix: `customModels` key_value row for the iishko node id with
  `{id: deepseek-v4.1-flash, supportsVision: true, apiFormat, supportedEndpoints}`
  (the dashboard's "Vision capable" toggle writes exactly this; functions
  `getCustomModelVisionOverride`/`addCustomModel` are not reachable via any
  REST route, so this was a direct sqlite INSERT — official-path gap, approved
  workaround). Restart required for it to take effect (guardrail reads DB at
  boot); verified after restart: `/v1/models` shows `capabilities.vision: true`
  for the model and a photo sent to `combo/hermesvision` was served by
  `hermesvision-model-1-…-deepseek-v4-1-flash` with a fully correct answer.
  NOTE: currently only `deepseek-v4.1-flash` carries this flag among the iishko
  ids — the rest still rely on the static spec table.
- Both representations are wanted, and this is a standing rule (user, 25.10.26):
  models mirrored from OmniRoute stay in the **OmniRoute** picker row, the
  **direct** provider rows stay direct — the same model existing in both places
  is by design, NOT duplication to clean up. So do NOT add `iishko/` (or any
  other live prefix) to `omniroute_model_sync.py`'s drop rules.
- Sync applied 25.10.26: OmniRoute row 1087 → 1129 (`+10 iishko/*`, `+36 beam/*`,
  plus nvidia/opencode-go/th churn), `--check` then reports no drift, and the
  direct `custom:iishko` row still carries its 9 models.

## Verification

```bash
curl -s https://api.reformboss.com/v1/models -H "Authorization: Bearer $KEY"
curl -s https://api.reformboss.com/v1/chat/completions -X POST \
  -H "Content-Type: application/json" -H "Authorization: Bearer $KEY" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"ping"}],"max_tokens":8,"stream":true}'
```

Gateway restart required after editing: `systemctl --user restart hermes-gateway`.
