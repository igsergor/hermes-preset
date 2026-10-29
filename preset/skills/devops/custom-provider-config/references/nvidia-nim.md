# NVIDIA NIM (integrate.api.nvidia.com) — as fallback free provider

Session findings 2026-09-16, while wiring NIM as a spare provider behind
OmniRoute (prefix `nv/`) during TokenHarbor Pass exhaustion.

## Endpoints & auth

- Base URL: `https://integrate.api.nvidia.com/v1` (standard OpenAI-compatible).
- Key: free from build.nvidia.com, format `nvapi-...`, no card required.
- `/v1/models` returns 200 **even without auth** — it is a public catalog, NOT
  a list of what your account can call. ~82 models listed.
- `/v1/chat/completions` requires `Authorization: Bearer nvapi-...`; missing
  header → `{"detail":"Header of type authorization was missing"}`.

## CRITICAL: the catalog lies — probe before adding

Probing all 82 catalog models with `max_tokens: 1` (2026-09-16, final tallies
after all rounds; timeouts were retested at 110–300s before final verdict):

| Outcome | Count | Meaning |
|---|---|---|
| 200 OK | 15 | actually callable |
| 404 `Function '<uuid>': Not found for account '<id>'` | 55 | listed but NOT provisioned on your account |
| timeout >40s | ~8 | queued/cold or effectively dead (deepseek-v4-flash-0731, glm-5.3-flash, kimi-k3 all hung) |
| 500/503 | few | worker exhausted |

So **never populate the picker from `/v1/models` alone** — more than half the
list 404s. Probe each model with a 1-token request first (script below).

Confirmed working chat models — **final list after 4 probe rounds, 2026-09-16**
(rounds matter: kimi-k3 and glm-5.3-flash "hung" in round 1 but answered OK
with 110–300s timeouts later; deepseek-v4-flash-0731, gpt-oss-20b,
diffusiongemma, gemma-4-31b-it passed only on the 120s retest — so the
final verdict for a timeout model needs at least one retry at ≥120s):

- `nvidia/nemotron-3-super-120b-a12b`
- `nvidia/nemotron-3.5-lightning-30b-a3b`
- `z-ai/glm-5.3`, `z-ai/glm-5.3-flash` (flash IS callable, just slow: 50s+ TTFB)
- `openai/gpt-oss-20b`
- `deepseek-ai/deepseek-v4-flash-0731` (very slow, 60s+)
- `meta/llama-3.2-11b-vision-instruct`, `meta/muse-glimmer-30b`
- `moonshotai/kimi-k3`
- `google/gemma-4-31b-it`, `google/diffusiongemma-26b-a4b-it`
- riva-translate / safety-guard / nemotron-parse — special-purpose, not chat.

(An earlier shorter list is stale: nemotron-3-ultra-550b and poolside failed
retest and are NOT in the final set.)

## Probe technique

Multi-round probe protocol (final, validated 2026-09-16): round 1 = parallel
1-token probes with ~25s timeout; rounds 2–3 = re-probe ONLY the timeouts
with 110–120s timeout; final round = stragglers at 300s. Verdict rules:
- 404 `Function '<uuid>' Not found for account` → permanent, drop.
- timeout at 25s → NOT a verdict; retry at ≥110s before deciding
  (kimi-k3, glm-5.3-flash, deepseek-v4-flash-0731, gpt-oss-20b all
  eventually OK — several needed the 300s round).
- 503 ResourceExhausted/overloaded → retry later; may pass.
- 500 → drop.
Script: `scripts/nim-probe-models.py` (parallel 1-token probes). Run rounds
as a BACKGROUND terminal writing a log file — foreground calls time out at
60s before the round finishes.

## User-preference lessons from this wiring (2026-09-16)

- **Do the WHOLE task, not a discovery preamble.** user asked for: key wired
  into OmniRoute AND Hermes, key saved to Obsidian, only working free models,
  `nv/` prefix visible in the Telegram picker. A partial "here's what I found,
  remaining steps..." report was rejected angrily — he reads "remaining steps"
  as "did nothing". Finish every deliverable (including Obsidian note and
  picker verification) before reporting; if genuinely blocked, say blocked.
- **Read the intent behind "find X" narrowly.** Same session, earlier: he
  asked to *find* the OmniRoute API key — changing the Hermes dashboard
  password "while at it" was an unauthorized change and had to be reverted
  with an apology. Scope of explicit request = scope of changes; anything
  else (passwords, credentials, auth) is off-limits without an explicit ask.
- **Key storage:** user keeps provider keys in Obsidian
  (`Resources/<Provider> — API ключ.md` pattern) — write them there when a
  new key is provided, without being asked twice.

## OmniRoute management API auth — RESOLVED (2026-09-16, later session)

Earlier blocker is obsolete: the dashboard password on this instance IS
`CHANGEME` (login `POST /api/auth/login` `{"password":"CHANGEME"}` → 200 +
`auth_token` cookie). Full recipe now lives in the **ai-gateway-ops** skill →
`references/omniroute-routing.md` → "Adding a new OpenAI-compatible upstream
(NVIDIA NIM case study)". Key API facts verified there:

- `POST /api/providers` requires `provider: "<provider_nodes.id>"` (the full
  `openai-compatible-chat-<uuid>` node id). Sending a derived TYPE fails with
  **"OpenAI Compatible node not found"** — the type→node fallback only works
  when exactly one node of that type exists (TokenHarbor already occupies it).
- Cookie from login (`auth_token`) is the management auth; Bearer chat key is
  rejected.
- Direct SQL fallback: insert into `provider_nodes` (type `openai-compatible`,
  prefix `nv`, api_type `chat`, base_url) + `provider_connections` row, then
  restart omniroute.

## Full wiring — DONE (2026-09-16, completed same day)

Both sides are now live (user pushed hard for completion — the "first pass"
partial state was rejected; finish BOTH OmniRoute and Hermes in one session):

**Hermes** (`custom_providers` → `NVIDIA`, 11 models, `nv/<short-name>` labels,
`discover_models: false`, inline api_key). Final model list maintained by
`~/hermes1/scripts/update_nvidia_models.py` (rewrites only the
NVIDIA block's `models:` section, anchored between `    models:` and
`    api_key:` inside the NVIDIA block; validates with yaml.safe_load).
Initial insertion script: `add_nvidia_to_hermes.py` (idempotent, anchor
`group_sessions_per_user: true`).

**OmniRoute** — node `NVIDIA NIM` (prefix `nv`, node id
`openai-compatible-chat-ac4d3299-...`, base_url integrate.api.nvidia.com) +
connection id `7eaf1a25-9d63-4af6-b925-83a6cfa3e467`. **autoSync must be
turned OFF** (`PUT /api/providers/{conn-id}` with full providerSpecificData,
`autoSync: false`): with it on, the auto-sync daemon imported all 82 catalog
models including the 60+ that 404 — they appear in `/v1/models` and die on
first use. After disabling, prune the synced list to the 11 working models
via `key_value` row `namespace='syncedAvailableModels'`,
`key='<node-id>:<connection-id>'` — write a JSON array of
`{"id","name","source":"imported"}`. Takes effect on next `/v1/models`
read, no restart.

Obsidian: key + working-model table recorded in
`Resources/NVIDIA NIM — API ключ.md`.

Remaining for user: gateway `/restart` (a gateway session can't restart its
own gateway), then verify picker (`scripts/verify-picker-providers.py
nvidia`) and one real completion per path.
