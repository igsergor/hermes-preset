# Tool-Recommendation Video → Triage Verdict

When Igor asks «что из этого реально есть у нас / что можно использовать» about a
video that showcases a tool, the deliverable is a **verdict per claim**, not a
summary and not a feature list. Shape: one line per claim — what the video
asserts, what our install actually does, and the verdict (есть / нет / есть, но
иначе / это чужой продукт поверх нашего).

Ladder, per claim:
1. **Get the claim's own words from the transcript** — a claim is only as precise
   as the sentence that carries it; the title and thumbnail carry none.
2. **Match the exact name in the shipped source and docs.** Run
   `hermes <subcommand> --help` for CLI claims and grep the install's docs tree for
   the feature name. A name that matches nothing in either is a *marketing label*,
   not a feature — say so, then identify which real subsystem it maps to.
3. **Check the default, not the existence of a flag.** Many behaviors are
   opt-in (`continuity`, `context_from`, per-mode toggles). "Now it does X" is
   true only when the default does it; otherwise write "есть, но включается
   флагом".
4. **Check our surface, not the video's.** A feature that is on by default in a
   desktop/GUI surface may be unreachable on a headless install; gate claims
   against the install actually running here before promising them.
5. **Credit the upstream, not the reseller.** A bundled preset/pack the author
   distributes through a paid community is their product layered on top — verify
   it against upstream before counting it as a feature of the tool itself.
6. **Version-check the premise.** Compare `hermes --version` (or the checkout's
   HEAD) with the release the video claims to cover. When our install is already
   ahead, the "brand-new update" content is old news here and the verdict must
   be stated against what we actually run.

Pitfalls:
- **Never grade a claim by the video's enthusiasm.** The same sentence often
  bundles one real feature with one invented name; split them before judging.
- **Scope source greps to the docs and CLI/gateway directories with a timeout.**
  A recursive grep from a repo root that ships a `node_modules` tree exceeds the
  command timeout and returns nothing, which reads as "absent" when it is only
  "unsearched".
- **Release-name and contributor counts are unverifiable from our side.** Check
  whether the tag/branch exists; if it does not, label the numbers as the
  author's claim rather than either confirming or denying them.
- **"Nobody replies to every message" / "fires and forgets" style nuances are
  the difference between the claim and reality** — carry them into the verdict.
  A delivery model that is queued/fire-and-forget is not the same as the live
  two-way chat the video shows.
- **Do not turn the triage into a purchase recommendation.** Igor asks what is
  usable here; answer that, then note what would need setting up on our side.
