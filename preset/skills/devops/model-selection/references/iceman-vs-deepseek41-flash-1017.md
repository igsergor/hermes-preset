# iceman-contributor-free vs deepseek-v4.1-flash-1017 (live comparison, 28.10.2026)

Measured, not remembered: every number below came from direct `/chat/completions`
calls on 28.10.2026. Sample size is 1–2 runs per test, so treat deltas under ~15%
as noise.

## Passports (models.dev + live catalogues)

| | iceman-contributor-free | deepseek-v4.1-flash-1017 |
|---|---|---|
| What it is | stealth model, Go only, lab unclaimed (self-reports MAI / Microsoft AI) | DeepSeek V4.1 Flash, 17.10 snapshot (bare `deepseek-v4.1-flash` is retired) |
| Context / output | 262,144 / 131,072 | ~1,048,576 / 384,000 |
| Modality | text in/out | text (+ vision per provider notes) |
| Reasoning + tool calls | yes / yes | yes / yes |
| Price | $0, no request cap, does NOT draw Go allowance | $0.15 / $0.60 per 1M (OpenCode Go) |
| Condition | requires Console → Settings › Privacy → *Allow paid endpoints that train on request data*; prompts+completions used for training, no zero-retention | normal paid terms |
| Route probed | `https://opencode.ai/zen/go/v1` with the Go key | `api.reformboss.com/v1` (iishko) |

## Measured

| Metric | iceman | ds41-1017 |
|---|---|---|
| TTFT | 15–23 s | 2–3 s |
| 8-paragraph Russian text | 42–45 s, 1.7k tok (≈47% reasoning), 3.2–3.9k chars | 24–33 s, 4–5.2k tok (78–93% reasoning), 3.9k chars |
| Generation speed | 66–78 tok/s | 157–185 tok/s |
| Needle @121k tok | 19 s, correct | 26 s, correct |
| Needle @243–251k tok | 22 s, correct | 40 s, correct |
| Failures in ~20 calls | 0 | ~5/15 (see below) |

Quality was a tie on everything checkable: `merge_intervals` (touching intervals +
no input mutation), the `top_k_frequent` off-by-reverse bug, the three-pipes math
problem (10 min), and a `TTLCache` LRU+TTL task with a fake clock and O(1)
requirements — both implementations passed the same test suite. Tool calling: both
emitted a correct `tool_calls` first turn; second turn iceman correctly refused
(no write tool available) while ds41 called `run_tests`.

## Two quirks worth remembering

- **ds41-1017 at reasoning=high can spend the whole `max_tokens` budget on
  `reasoning_content` and return empty `content`** (`finish_reason: length`).
  Seen at 1600 tok (0 chars, twice) and at 6000 tok (0 chars, 42 s). Keep
  `max_tokens` ≥ 8k for this model, or lower `reasoning_effort`.
- **iceman is only reachable with the Go key**; it is absent from OmniRoute's
  catalog, so a `custom:omniroute` fallback cannot serve it. In Hermes it needs
  the `opencode-go` provider entry and `agent.reasoning_overrides` if effort is
  to follow the beam-style settings.
- TokenHarbor's `th/deepseek-v4.1-flash-1017` route is dead while balance is $0
  (402 `balance_zero`) — not a model verdict.

## Verdict

Equal on the tasks tested. Take ds41 for >262k context and for latency; take
iceman as a free, zero-quota, very stable fallback for coding/agent work that
fits 262k — but never for private or client code, because the free tier trains
on requests.
