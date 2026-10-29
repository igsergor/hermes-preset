# Auditing and pruning YouTube subscriptions

Task class: «разбери подписки — что оставить, от чего отписаться». Hundreds of channels, the
cost of an error is a subscription the user kept for years, and the permission the user
grants usually covers only a slice («201 — отписывайся») of the whole task.

## Two halves must stay open

The user states the task in full («разбери ВСЕ подписки») and authorizes a narrow action.
Narrow authorization limits the ACTION, not the task: the remaining buckets must still be
carried to a verdict, or he returns and points at the original formulation. Report
«пока готово M из N» rather than closing on a convenient slice.

## Build the interest profile from real history FIRST

Never invent interests from memory («AI, железо, православие») and then classify channels
against them — that is the main cause of bad verdicts. Extract the top 30–50 channels from
the actual watch history, look at what they are, and declare THAT the profile. This surfaces
topics nobody would guess (on this account: православие and SEO/AI-earnings far outweigh the
assumed tech focus).

A channel in history may not be in the subscription list at all, and part of what defines the
profile never enters the unsubscribe bucket — that is correct, not an omission.

## Signals, strongest first

1. **A like in the last ≤2 years** — a direct, decisive statement of interest. If a fresh like
   lands on a channel already unsubscribed, re-subscribe IMMEDIATELY, not at the final report.
   Likes are only given to what matters (older ones were partly automated). Old likes (5+ years)
   prove staleness, not interest.
2. **Titles of recent videos** — high weight: what the channel is about NOW.
3. **Watch history** — medium; often empty (not watched ≠ not wanted), so it corrects rather
   than decides.
4. **Name + description** — weak: marketing, not substance.
5. **Channel size** — NOT a signal either way. A 1.2M crypto channel can be junk and a 7M health
   channel can be essential; both look solid. Size never decides, including in ambiguous cases.

**Asymmetry rule: when in doubt, KEEP.** Extra junk is harmless; a lost subscription is not.
Ambiguous channels go to the user as a table, never into the unsubscribe list silently. A
channel not classified by a child agent → KEEP.

## Execution order

1. Export ALL subscriptions: `/feed/channels` (NOT `/feed/subscriptions`, which shows only
   channels with new videos), scroll to the end, dedup by `channelId` — never by name.
2. Collect likes WITH dates (the strongest signal, see below).
3. Collect ~6 recent video titles per candidate channel (`/@handle/videos`).
4. Collect watch history as a CORRECTION signal only.
5. Combine like-freshness + titles + history + name/description → verdict.
6. Split into keep / unsubscribe / ambiguous, and hand the ambiguous set to the user.

Unsubscribe execution mechanics live in `web-automation-auth` →
`references/bulk-action-verification.md`.

## Collecting likes (playlist LL)

- The official like list is `https://www.youtube.com/playlist?list=LL`, on web and InnerTube.
- The current UI renders cards as `yt-lockup-view-model`; the older
  `ytd-playlist-video-renderer` selector returns 0 and reads as "playlist empty".
- **The playlist renders in 15–20 s.** A script that declares "no new items for N iterations"
  at 10 s writes ZERO likes. Loop until the DOM is non-empty first.
- A like's date is in `3d ago` / `3w ago` / `1mo ago` — the moment the video entered the
  playlist, i.e. when «нравится» was pressed. The parser MUST handle abbreviations
  (`s m h d w mo y yr`): an abbreviation-blind parser silently dropped 700 of 807 dates.
  Collect the raw `ago` string and parse later — no re-harvest needed for a broken parser.
- A collector that returns 0 lines is almost never "playlist empty": check
  `document.title`, `location.href`, `body.innerText` (does "Liked videos" and the count show)
  and the count of BOTH selectors.

## Verdicts that must stay distinguishable

Before reporting «всё отписано», a verification pass reads the live button per channel, and
its outcomes must not collapse into two:

`STILL_SUB` (action failed — act) / `UNSUB_OK` / `LOGGED_OUT` (re-verify is possible, not proof
of failure) / `BLANK` (page unrendered) / `GONE_404`. The last two are "cannot verify" and are
re-queued, never counted as success. Restart the browser on a BLANK wave, not only on
exceptions.

Three ways the pass fakes «all good»:

1. The auth check looks for the text «Войти», so `login=True` means the button EXISTS = the
   session is BROKEN — the polarity is inverted. Name such flags for what they assert
   (`signin_button_visible`).
2. A blank page is not an empty state: no button + empty `body.innerText` is BLANK, never
   "not subscribed".
3. The wait must exceed what is plausible: channel pages take ~15 s, so wait 12×2 s, not
   9×2 s, before declaring "no button".

Report from the verification facts (how many `UNSUB_OK`, how many `STILL_SUB` — the latter is
a FINDING and must be said immediately — how many unverifiable), never from the run journal.

## The «ambiguous 10%» is a risk calculation, not a random sample

When asked for the 10% least suitable for unsubscribing, rank by risk: presence in watch
history, a fresh like, topic closeness to the profile. Match topics with word boundaries
(`\bавто` must not match «автор»; `\bсми` must not match «смит»; a bare «мото» grabs
«мотор»), and never treat as "close to the profile" something that contradicts it (music,
kids, beauty are never close).

Never declare «ошибочно отписаны» until every candidate has been checked individually.

## Data pitfalls that corrupt a triage

- **A truncated description is the main source of absurd verdicts.** Descriptions cut to ~200
  chars for context produce "politics in the Games category"; titles show the topic honestly.
  Either collect full text or use the stronger signal (recent titles).
- **Every interest regex is tested on two lines first**: zero matches on neutral text
  ("alpha beta gamma") and exact matches on a reference sentence. Silent bugs that follow
  from skipping this: `||` in a multi-line join (an empty alternative matches every position —
  the tell is a per-channel count in the hundreds), a capturing group in `findall` (returns the
  group, not the match), and a missing `\b` at the end.
- Live-signal false positives exist: "AI" in a mining-channel video means ASIC rigs, not neural
  nets; "автоматизация" in an MLM channel is not n8n. A filter only GENERATES candidates;
  the verdict is read by eye.
- Do not match likes to subscriptions by normalized name — normalization that strips digits
  glues `@inventor247` to a channel called "Inventor" and fills the report with zero-like
  channels. Check each candidate individually.
- The subscription DATE is unavailable (neither the channel page nor `/feed/channels` exposes
  it) — never build a criterion on it; use channel activity and the direct signals above.

## Reports

One table of verdicts with the ambiguous rows for the user's decision; a plain-text file of
channels to unsubscribe (he applies it by hand); a justification document per channel. Numbers
summary: total / keep / unsubscribe + top categories. Data limits go in ONE closing line,
never instead of a result.
