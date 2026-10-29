---
name: research-fanout
description: "Use when splitting research across parallel subagents."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [research, delegation, subagents, verification, synthesis, obsidian]
    category: research
---

# Research Fan-Out

Split one research question into N category slices, dispatch one subagent per
slice, then compile the slices into a single verified, cited deliverable
(report or Obsidian note). Citation mechanics (ledger, `sources.py`) belong to
`grounded-citations`; source-API and page-recovery ladders belong to
`research-tools` and `blocked-page-recovery`. This skill owns the
dispatch / verification / compile protocol — which is where fan-outs fail.

See `references/failed-slice-recovery.md` when a dispatched slice fails or comes
back with no summary — recover by shrinking the slice and reading from disk, not
by re-running it.

## When to Use

Use this skill when:

- one question needs breadth: an option/market survey, "every X with property
  Y", a comparison across categories — too wide for a single context window
- the result is meant to outlive the session (Obsidian note, report file), so
  its evidence must stay verifiable afterwards
- the deliverable will be compiled from several independent collections

Skip it for narrow lookups (one page, one API) — fetch directly. Any grounded
output still follows `grounded-citations` for citation mechanics.

## Procedure

### 1. Probe retrieval routes before dispatching (one cheap round)

Run 3-5 `curl` probes (source APIs, one search route, two target sites) so the
goals can tell children which routes work here. Otherwise every child burns
its budget rediscovering the same walls.

Write into every goal, explicitly:

- which routes work (direct `curl`, GitHub / HuggingFace / CivitAI / Wikipedia
  APIs, Wayback)
- which are captcha- or 403-walled from this host — and **never solve a
  CAPTCHA**
- the exact deliverable format (one table row per item, fixed columns)
- a machine-readable `output_schema` so the summary is parseable

### 2. Make each child's work refusal-proof

A child's final message is the only part that survives, and it is the part a
provider safety filter may reject. Mandate in the goal:

- **append each verified item to its own file as it is verified**
  (`open(path,'a')`) — never batch everything into the final answer
- **terse final message**: file path + row count + two-sentence summary
- **factual phrasing**: a catalogue of prices / rules / quotes, not "how to
  bypass X"
- **reuse what siblings already downloaded** (the shared scratch cache)
  instead of refetching — name the cached files in the goal
- `verified: true/false` per item; anything unreadable gets `[не проверено]`

### 3. Dispatch in parallel, then read failures as data

Fan out 3-5 children in one `delegate_task` call. On a failed or
unknown-status child: read its live transcript tail and the files it wrote
**before** re-dispatching — partial results are usually salvageable, and the
failure mode (refused answer vs. timeout vs. crash) dictates the re-dispatch
wording.

### 4. Compile in the parent

1. Structural validation first: count table rows per file, check column
   counts, spot-check the verdict columns — never trust a child's reported
   row count.
2. Register every cited URL in the citation ledger **centrally**, then write
   the report with `[n]` ids, render the Sources block, run `verify` (all per
   `grounded-citations`).
3. Assemble the note programmatically (concatenate child files + authored
   synthesis) instead of retyping their content — transcription is where
   numbers drift.
4. State method limits inside the deliverable: which routes were blocked,
   which rows are `[не проверено]`, the verification date.

## Pitfalls

- **Parallel children writing one shared file or ledger** — uncoordinated
  appends lose entries; keep the writer single (the parent) and have children
  return paths and URLs instead.
- **Trusting a child's self-report** — "completed, 23 rows" is a claim, not a
  measurement; recount from the file on disk.
- **Assuming a failed delegation lost everything** — children stream to live
  transcript logs and, with step 2, to their own output files; salvage before
  redoing the work.
- **Dispatching before probing routes** — each child then rediscovers the same
  captcha wall, multiplying the wasted budget on one dead end.
- **Retyping child findings into the report** — copy their file content
  programmatically; hand-retyping is how prices and counts get corrupted.
- **Omitting the method caveats** — a reference document that hides blocked
  routes or unverified rows reads more certain than the collection was.
