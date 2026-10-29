# Gateway reply footer: extending via `~/.hermes/hooks/`

The messaging footer (`alias → served · tok/s · …`) is built in exactly one place:
`GatewayTurnMixin._hmwa_runtime_footer_line` (gateway/run_turn.py) →
`gateway/runtime_footer.py:build_footer_line` (fields: model, served_model,
context_pct, latency, cwd; unknown fields are skipped silently).

## Procedure

1. Create `~/.hermes/hooks/<name>/` with `handler.py` + `HOOK.yaml` (events: `gateway:startup`).
2. In `handler.py`, wrap the seam with `functools.wraps`, guard every step with
   try/except that falls back to the original line — a footer nicety must never
   break a turn.
3. Mark each wrapper with an attribute flag and skip when already marked:
   `gateway:startup` re-runs handlers, and double-wrapping stacks segments.
4. Never modify Hermes source — bind module attributes in the running gateway
   only, so `hermes update` is safe.
5. Activate with a gateway restart: hook files are exec'd from disk at startup
   and there is no hot reload for hooks — the control-socket `reload-plugins`
   command reloads plugins only and leaves `~/.hermes/hooks/` untouched.
6. Unit-check pure logic (parse/derive functions) standalone before restarting.
   Full-wrapper check without a restart: stub the patched modules in `sys.modules`
   (`gateway.run_turn` with a stub `GatewayTurnMixin`, plus any `agent.*` imports the
   wrapper touches), import the handler with `importlib.util.spec_from_file_location`,
   then call the patched functions with fabricated payloads and assert the rendered
   line. This validates both seams and the fallback paths in one shot.

## Deriving the provider segment

- The turn result dict is rebuilt by `gateway/run_turn_runner.py` (`common = {...}`)
  and drops `requested_model`/`served_model` — key captures by `session_id`, which
  the rebuild preserves, and restore the fields inside the footer wrapper.
- For routed (combo) turns the served id carries the backend as prefix
  (`nvidia/…`, `z-ai/…`) — the prefix IS the provider. Render `via <prefix>` only
  when served differs from requested; direct models and slash-less ids
  (`space-bunny-free`) carry no provider at this seam — omit, never guess.
- Keep the separator consistent with the builder (` · `).

## Reading the `tok/s` figure

- The segment is a per-turn wall-time ratio: output tokens over the whole request duration, time-to-first-token and routing latency included. It is NOT sustained generation speed and matters mainly as a latency signal.
- Tool-call steps with tiny outputs (tens of tokens) behind a multi-second TTFT read as single-digit tok/s while the model itself is fast — never diagnose "the model is slow" from the footer on such a step.
- To verify real speed, bypass the footer: one direct streaming request to the provider, timestamps for TTFT and total, then compute decode-only tps (`completion_tokens / (total − ttft)`) and read `usage.tokens_per_second` from the response. Sanity-check with a long-generation prompt, not a tool step.
- Sample baseline on the OmniRoute → opencode-go routing: TTFT ~6 s, decode-only ~100–150 tok/s for a full-length answer.

## Decode-only speed (per-API-call seam)

When the user wants the honest generation rate instead of the per-turn ratio
(rendered as `· <turn latency> (<tps> tok/s gen)` — latency plus parenthesised
decode speed), the turn seam is not enough; take it from the per-call seam:

- Wrap `agent.turn_response_intake._fire_post_api_request_hook` — it fires once per
  API response with `api_duration`, `api_start_time`, and first-chunk epoch via
  `agent._last_api_first_chunk_at`. Patching the module attribute works even though
  `conversation_loop` imports `normalize_model_response` directly: the call to the
  fire function is a module-global lookup inside it.
- A `~/.hermes/hooks/` handler CANNOT subscribe to `post_api_request` via HOOK.yaml:
  that event belongs to the plugin-hook registry (`hermes_cli.lifecycle`), a
  different system from gateway hooks (`gateway/hooks.py`). Patch the fire function
  instead — same pattern as the footer seam.
- Token counts come from `agent.usage_pricing.normalize_usage`; the canonical
  dataclass field is `output_tokens` — reading `completion_tokens` from the asdict
  yields None and the segment silently disappears.
- decode_tps = `output_tokens / (api_duration − (first_chunk_at − started_at))`;
  when `first_chunk_at` is missing (non-streamed call) fall back to the full
  `api_duration`. Store the last value per `session_id` and render it in the
  footer wrapper; keep the per-turn ratio as the fallback when no call was recorded.

## Live hooks (this installation)

- `omniroute-served-model/` — restores served model lost in the rebuild, appends
  `via <provider>`; also honors `x-omniroute-model` on the non-streaming path.
- `turn-tps-footer/` — appends turn latency plus decode-only generation speed
  (`· 14s (146 tok/s gen)`) from the last API call of the turn, falling back to
  the per-turn output ratio when no per-call data was recorded.
