# Recovering a failed slice

Fan-outs die in two ways: the provider refuses the request (capacity /
admission errors), or the owner exits before children record a result. Both
leave the same problem — a slice with no deliverable. Recover by shrinking the
slice, never by re-running it as-is.

## Diagnose before re-dispatching

Read the failing child's live transcript and classify:

- **Capacity refusal** (`503`, "overloaded", "admission capacity") — the
  request itself was too heavy. The work is fine; the packaging was not.
- **Interrupted / no summary** — the child was killed mid-run. Whatever it
  wrote to disk is still valid; the conversation is lost.
- **Context exhausted** — the goal asked for more breadth than one child can
  hold. Needs splitting by axis, not by retry.

## Rule: make slices smaller and local

A child that reads a 3900-line file over the network burns its budget on
fetching and dies before it reasons. When files are already on disk, say so in
the goal and forbid the network: *"read these local paths, the network is not
needed."* The re-dispatch is then minutes of work instead of an hour.

Pair that with a hard output cap in the goal ("700-1000 words", "answer these 6
numbered points"). Unbounded goals let a child wander into a fourth subsystem
and blow up on a request the provider will refuse.

## Rule: children must persist incrementally

Tell every child to write its findings to a file as it goes, and to return only
the path plus a short bullet summary. Two payoffs: work survives owner exit, and
a parent turn that needs the finding does not re-read the transcript. Without
this, a killed child leaves nothing but a log.

## Rule: harvest the survivors, never assume the batch is atomic

A completion batch can report a mix of completed, failed, and `unknown` slices.
Before re-dispatching anything, check the scratch dir for the output files each
child was told to write. Re-running research that already exists on disk wastes
minutes and, on metered APIs, money.

## Reporting progress mid-fan-out

When reporting status while children still run, write for a reader who has not
seen the findings. No issue numbers, no API names, no code paths in a progress
update — those belong in the final report. Say what is done, what is left, and
roughly how long. If the user signals they did not follow an update, the fix is
plain language, not more detail.
