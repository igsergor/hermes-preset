# Vision Model Roster — Cross-Provider (user's configured providers)

**Rule: a model name containing "VL" or a `capabilities.vision: true` flag is NOT proof of vision.** Verify via models.dev major-provider entries, and for free/local models verify with a real image request (hallucinated fluent descriptions happen). Full free-vision test recipe lives in `openrouter-free-models.md`.

**Last verified: 2026-10-22** (models.dev cache `~/.hermes/models_dev_cache.json`, major providers: openrouter, anthropic, openai, google, mistral, nvidia, deepseek, xiaomi, opencode, opencode-go, ollama-cloud, moonshotai, zai, zhipuai, minimax, xai, meta, cline-pass; false-positive bases removed).

## Counts (vision / total configured)

| Provider | Vision | Total | Notes |
|----------|--------|-------|-------|
| OmniRoute (aggregator) | 437 | 1085 | openrouter 284, th 46, ocgo 17, opencode-go 20, no-think 18, cxa 7, antigravity 4, nvidia 4, oc 2, cfp 4, mimotp 3, xiaomi-mimo-token-plan 3, zc 3, dva 1, ollamacloud 1 |
| TokenHarbor | 27 | 34 | aggregator; vision inherited from base model |
| ClinePass | 9 | 14 | subscription; gated `cline-pass/` ids |
| Mistral (direct) | 5 | 8 | ministral-3b/8b, mistral-small/medium/large latest |
| NVIDIA NIM | 5 | 13 | llama-3.2-11b-vision, muse-glimmer-30b, kimi-k3, nemotron-nano-omni, glm-5.3-flash |
| Xiaomi MiMo | 3 | 8 | mimo-v2.5, mimo-v2.6-flash, mimo-v2.6-pro |
| OpenCode Go Direct | 8 | 10 | glm-5.3-flash, space-bunny, muse-spark-1.3-contributor, mimo-v2.6-flash/pro, kimi-k3, qwen3.8-max, deepseek-v4-flash |
| Antigravity Local (.114) | 8 | 8 | all Gemini (3.5/3.6/3.7/3.8 flash, flash-latest, flash-lite-latest, pro-latest, 3.1-flash-lite) |
| Google AI Studio | 2 | 2 | gemini-1.5-flash, gemini-1.5-pro (legacy, vision-capable) |
| win-host LLM (.134:8092) | 2 | 2 | qwen35v4, qwen35v4-vision (Qwen3.5) |
| Bonsai128k (.134:8093) | 2 | 2 | bonsai, bonsai/bonsai (ternary-bonsai-2-27b) |
| Bonsai2 256k RPC (.134:8099) | 1 | 1 | bonsai2-256k |
| Ornith35B 256k RPC (.134:8095) | 1 | 1 | ornith35b-256k |
| Ollama Cloud | 14 | 29 | deepseek-v4.1-flash (+:1017), gemma4:31b, glm-5.3-flash, kimi-k2.5/2.6/2.7-code/k3, minimax-m3/3.1-flash, mistral-large-3:675b/4, muse-spark-open, qwen3.5:397b |
| OpenCode Beam Proxy | 0 | 1 | beam-free (text) |

## Text-only (no vision) — key configured models

- ClinePass: deepseek-v4-pro, glm-5.2, glm-5.3, mimo-v2.5-pro, qwen3.7-max
- TokenHarbor: deepseek-v3.2, deepseek-v4-pro, glm-5.2, glm-5.3, mimo-v2.5-pro, qwen3.7-max, th-orchestra
- Mistral: codestral-latest, labs-leanstral-1-5, ministral-14b-latest
- NVIDIA: deepseek-v4-flash-0731, mistral-nemotron, nemotron-3-super/ultra/lightning, gpt-oss-20b, laguna-xs-2.1, glm-5.3
- Xiaomi: mimo-v2.5-asr, mimo-v2.5-pro, mimo-v2.5-tts*
- OpenCode Go Direct: glm-5.3, glm-5.2
- Ollama Cloud: gpt-oss:120b/20b, nemotron-3-nano/super/ultra, nemotron-3-nano:30b

## OmniRoute vision IDs (437) — full list

See `/tmp/omni_vision.txt` (generated 2026-10-22) or recompute with:

```python
import json, yaml
md = json.load(open('~/.hermes/models_dev_cache.json'.replace('~','~')))
cfg = yaml.safe_load(open('~/.hermes/config.yaml'))
omni = [p for p in cfg['custom_providers'] if p['name']=='OmniRoute'][0]
ids = [m['id'] for m in omni['models']]
major = {'openrouter','anthropic','openai','google','mistral','nvidia','deepseek','xiaomi','opencode','opencode-go','ollama-cloud','moonshotai','moonshotai-cn','zai','zhipuai','minimax','xai','meta','cline-pass'}
vb = set()
for prov,pd in md.items():
    if prov not in major: continue
    for k,v in pd.get('models',{}).items():
        if 'image' in v.get('modalities',{}).get('input',[]):
            vb.add(k.split('/')[-1].split(':')[0])
# remove known false positives
fp = {'gpt-oss-120b','gpt-3.5-turbo','gpt-3.5-turbo-instruct','o3-mini','o3-mini-high','gpt-5.3-codex-spark','o4-mini-high','gpt-image-1-mini','gpt-realtime-2.1','grok-imagine-image','grok-imagine-image-2.0','grok-imagine-video-1.5','grok-imagine-video-1.5-lite','gpt-oss','gpt-oss-20b','fusion','free','auto','fast','cheap','small','nova-micro-v1','ministral-3b','mistral-large','magistral-medium-latest','minimax-01','minimax-latest','nemotron-3-ultra-550b','nemotron-3-nano-omni','qwen3.8-2.4t-a95b','qwen3.5-2b','qwen3.5-4b','qwen3-6-35b-a3b','qwen3.6-35b','deepseek-v4-flash-latest','deepseek-v3.2','gemini-embedding-2','gemma-4-12b-it','glm-5.2','glm-5.3','gpt-5.6-luna-fast','gpt-5.6-sol-fast','gpt-5.6-terra-fast','gpt-6-astra-fast','gpt-6-luna-fast','gpt-6-sol-fast','gpt-6.1-sol-fast','deepseek-v4.1-flash-1017-fast','glm-5.3-fast'}
vb -= fp
vb.add('gemini-3-flash'); vb.add('gemma4:31b')
res = sorted(i for i in ids if i.split('/')[-1].split(':')[0] in vb and i.split('/')[-1].split(':')[0] not in {'auto','cheap','fast','free','fusion'})
print(len(res))
```

## Cross-provider vision IDs (highlights)

- **Best free vision (verified with real image):** Google AI Studio `gemini-flash-lite-latest` / `gemini-2.5-flash-lite` (1–2s, reads text+colors), `gemini-2.5-flash`, `gemma-4-26b-a4b-it`; NVIDIA NIM `meta/llama-3.2-11b-vision-instruct` (~20s); see `openrouter-free-models.md`.
- **Local (offline, slow):** Ornith35B 256k RPC (~10 min/min video), Bonsai2 256k, Win11 qwen35v4 — vision works but prompt-eval ~12 t/s on GPU; suitable for batch, not interactive.
- **ClinePass vision (subscription):** deepseek-v4-flash, glm-5.3-flash, kimi-k2.6/2.7-code/k3, mimo-v2.5, minimax-m3, qwen3.7-plus, qwen3.8-max.
- **TokenHarbor vision (subscription, balance-dependent — currently $0):** claude-fable-5/5.1, claude-opus-4.8/5, claude-sonnet-4.6/5, deepseek-v4-flash (free variant works), deepseek-v4.1-flash, gemini-3.7/3.8-flash, glm-5.3-flash, gpt-5.5, gpt-5.6-luna/sol/terra, gpt-6-astra, grok-4.5/4.6, kimi-k2.6/k3, mimo-v2.5, qwen3.8-27b/flash/max.

## How to verdict a vision probe (a 200 is not proof)

- **HTTP 200 does not mean the model saw the image.** Some models accept the
  `image_url` part and reply «я не могу видеть изображения / вы не приложили
  фото» — they ignore the image entirely. Verdict by CONTENT: pass only when
  the answer names specifics from the picture (on-screen text, app name,
  objects). A blind refusal is definitive; a 503/504 is transport noise —
  retry, never score it.
- **Empty `content` + correct `reasoning_content` + `finish_reason: "length"`**
  means vision WORKS and the budget went to reasoning — raise `max_tokens`
  (300-500) or read `reasoning_content`; never score it blind.
- Ground-truth the test photo yourself first (`vision_analyze`) and confirm a
  positive on a SECOND, different photo; one fluent answer can be a lucky
  hallucination.
- Use a real JPEG from `~/tmp_uploads/*.jpg` as a base64 data URL, and run
  rounds of 3 attempts spaced minutes apart while the provider is overloaded.

### iishko node (verified with two real photos)

| Model | Vision | Notes |
|---|---|---|
| `qwen3-vl-plus` | YES | fastest and most precise (6-7 s, reads captions and on-screen text) |
| `deepseek-v4.1-flash-1017` | YES | reasoning-heavy: empty `content` at `max_tokens: 200` — raise the budget |
| `qwen3.8-flash` | YES | 7-11 s, accurate on both photos |
| `qwen-plus` | NO | 200 + «не могу видеть изображения» |
| `qwen-max` | NO | 200 + «мне недоступен прямой просмотр изображений» |

`deepseek-v4.1-flash` (bare) is retired upstream: absent from `/v1/models` and
403 `model_access_denied` — `-1017` replaces it.

## Pitfalls

- `openrouter/` prefix in OmniRoute is a router namespace, not a separate provider — the same base model may appear under `th/`, `ocgo/`, `opencode-go/` too; pick by price/latency, not by name.
- OmniRoute's `/v1/models` aggregates many upstreams; a model listed there may still 404 on `/chat/completions` (catalog ≠ routable). Probe before relying.
- Antigravity Local (`.114:8000`) only serves Gemini variants; all are vision-capable.
- Google AI Studio `gemini-1.5-*` entries in config are retired from the API (404); enumerate live roster via `/v1beta/models` before use.
- NVIDIA NIM IDs in config carry an `nvidia/` veneer prefix; strip it (`meta/...`, not `nvidia/meta/...`) before calling NIM directly, or get a 404 wall.
- Free `:free` vision models must be image-verified (not just catalog-flagged) — see `openrouter-free-models.md`.
