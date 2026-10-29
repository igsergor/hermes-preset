# Reconstructing a Lost Procedure from Session History

Use when the user asks "восстанови как ты делал X" (rebuild the METHOD, not
the artifact) and the full history exceeds what fits in context (can be >1M
tokens). Do not read the history start-to-finish — window and filter it.

## The store

`~/.hermes/state.db` (SQLite):
- `sessions(id, started_at, ...)` — id like `20261014_121924_abb9205f`
- `messages(session_id, timestamp, role, content, tool_calls, tool_name, ...)`
  — `timestamp` is a Unix float; `tool_calls` is a JSON string of the
  assistant's calls (function name + arguments).

If session id unknown: `select id, started_at from sessions where started_at
between X and Y`.

## Procedure

1. **Scope by time first, then by keyword.** Ask (or infer from the summary)
   which day/part of the session produced the artifact, and pull only that
   window: `where session_id=? and timestamp between ? and ?`. A full session
   dump can be megabytes; a build window is usually tens of messages.
2. **Keyword pre-filter for wide windows**: `content like '%<name>%' or
tool_calls like '%<name>%'` where `<name>` is the artifact name (e.g. the
   PDF/script version) — 40–50 hits usually pinpoint the build.
3. **Dump to a scratch JSON/text file, not stdout** — then read it in chunks
   with `read_file`, or grep it. Never print raw tool_calls to the terminal
   output in bulk; it truncates and pollutes context.
4. **Two passes**: (a) the prep window BEFORE the artifact (image crops,
   inputs, one-off fixes), (b) the build window (assemble → render → compress
   → send). Extract assistant tool_calls in order; tool results only where
   numbers matter (byte sizes, dimensions, verification output).
5. **Reconstruct as a numbered methodology file** with exact commands, input
   paths, and acceptance checks — save it in the project's permanent archive
   next to PROJECT.md, then REPORT the steps to the user for review.
6. **Verify by re-execution, not by re-reading**: rebuild in an ISOLATED dir
   from the original inputs following only the recovered doc, then diff
   against the known-good artifact (byte size + pixel diff — see
   messaging-delivery references/bot-api-delivery.md for why SHA of
   gs/Chrome PDFs never matches). A mismatch per-page usually means one
   input asset was missed — bisect by page.

## Pitfalls

- **Do not paste 1.6MB JSON into context**: filter with python inside the
  tool call, print only counts/samples; read the dumped file in line ranges.
- **Session timestamps are Unix floats, not strings** — convert with
  `datetime.datetime(...).timestamp()` for the window bounds (mind local tz).
- **A truncated script in history is common** — a heredoc'd script may have
  been cut at N lines when it was written. Re-derive the tail (e.g. the final
  HTML write/render step) rather than assuming the dump is complete; verify
  by running.
- **The recovered doc must be re-tested end-to-end before it is called
  "recovered"** — a methodology that reproduces byte-identical output is the
  only acceptance bar the user accepts for this check.
