# Artificial Analysis — bulk benchmark lookup (ranking N models)

Use when the ask is **"rank these N models by intelligence / capability"** or
"compare them on a neutral benchmark". Single-model spec questions still go to
the OpenRouter API first (see SKILL.md protocol).

Source of truth: the **Artificial Analysis Intelligence Index** published on
`artificialanalysis.ai`. It is a composite of several evaluations, and the
version number changes over time — always quote the version string you read,
never a remembered one:

```
Artificial Analysis Intelligence Index v<X.Y.Z> incorporates N evaluations: AA-Briefcase, GDPval-AA, AutomationBench-AA, Terminal-Bench, SciCode, Humanity's Last Exam, GDP.pdf, CritPt, AA-Omniscience, AA-LCR
```

## Procedure

**1. Resolve slugs from the sitemap — never guess them.** Display names do not
map to URLs (`MiMo-V2.5` → `mimo-v2-5-0424`, `Qwen3.7 Plus` → `qwen3-7-plus`,
`GLM-5.3-Flash` → `glm-5-3-flash`), and a guessed slug silently returns a
page for a different model or a 404 shell.

```bash
curl -s 'https://artificialanalysis.ai/sitemap.xml' -o /tmp/aa_sitemap.xml
grep -o -E 'https://artificialanalysis.ai/models/[a-z0-9-]+' /tmp/aa_sitemap.xml | sort -u > /tmp/aa_slugs.txt
grep -i -E 'deepseek|glm-5|kimi|qwen|mimo|minimax|longcat|muse|hy3' /tmp/aa_slugs.txt
```

The sitemap also tells you which models are **not** measured (free, preview and
limited-time offers are frequently absent) — that is a finding to report, not
an error to work around.

**2. Fetch the pages with `curl` in parallel, not with browser navigation.**
Each page is ~4 MB of server-rendered Next.js HTML, so N models ≈ N curl calls
instead of N browser round trips:

```bash
mkdir -p /tmp/aa
printf '%s\n' <slug> <slug> ... | xargs -P 5 -I{} sh -c \
  'curl -s -m 60 "https://artificialanalysis.ai/models/{}" -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64)" -o /tmp/aa/{}.html'
```

Drop any file that did not appear in the listing before parsing — a failed
fetch otherwise parses as "no score".

**3. Extract the number from the head of the file.** The score is stated
verbatim in the meta description:

```
<Model name> scores <N> on the Artificial Analysis Intelligence Index, placing it ... (median: <M>).
```

```python
import re
text = open(path, encoding='utf-8', errors='replace').read(600_000)  # head only
score = re.search(r'scores ([0-9.]+) on the Artificial Analysis Intelligence Index', text)
title = re.search(r'<title>(.*?)</title>', text, re.S)  # always confirm identity
```

Read a bounded head, not the whole file: these pages are effectively
single-line HTML, and an unbounded `grep` over 4 MB of them takes minutes
while returning the same first match.

**3b. Pull per-evaluation sub-scores out of the same page — no second fetch.**
The headline index is a composite, so an "agentic intelligence" ranking needs
the agentic component named explicitly. The same ~4 MB page embeds one JSON
record per model with the individual evaluations, including
`terminalBench40` (Terminal-Bench 4.0, labelled "Agentic coding & terminal
use" — the metric that matches a coding agent's actual job), plus
`terminalbenchHard`, `scicode`, `hle`, `lcr`, `intelligenceIndex` and the
`price1m*` fields:

```python
import re
text = open(path, encoding='utf-8', errors='replace').read()
m = re.search(r'\\"terminalBench40\\":\s*([0-9.]+|null)', text)
idx = re.search(r'\\"intelligenceIndex\\":([0-9.]+)', text)
```

The escaping in the embedded JSON is inconsistent (`\"` and `\\"` both occur),
so match the permissive `\\"key\\":` form. This is the only bulk route to
Terminal-Bench numbers per model — the `/evaluations/terminalbench-4-0`
leaderboard page carries its series in client-rendered chart divs and does not
yield model→score pairs to `curl`.

**3c. Anchor every sub-score to a slug, or you will report a neighbour's
number.** One page carries records for every model the site compares against,
so the *first* `terminalBench40` is yours and later ones belong to other
models. Read the `\\"slug\\":\\"...\\"` immediately preceding each match and keep
only the record whose slug equals the page you fetched; print slug + score
together so a mismatch is visible rather than silent.

**4. Report the variant the number belongs to.** Reasoning models have one page
per effort level — the default slug's `<title>` carries the effort as a suffix
(`GLM-5.3 (max)`, `Muse Spark 1.2 (xhigh)`, `DeepSeek V4.1 Flash (max)`), and
sibling slugs exist for `-non-reasoning` and other efforts. The headline score
is for the effort on the default page; state it in the output so a reader can
compare like with like.

**5. Sort, and be explicit about gaps.** Deliver a numbered table ordered by the
index, ties on adjacent rows, one clickable link per model. Models the source
doesn't measure get a line saying so rather than disappearing from the answer.

## Pitfalls

- **`/api/v2/models` is not public JSON** — it returns the HTML app shell
  (auth-gated). Scrape the HTML pages instead of hunting for an API key.
- **The interactive chart is the slow path.** Its "Download data" button emits a
  CSV, but only for the preselected series; use it when you need the whole
  leaderboard, not for a named shortlist.
- **Tabbed charts are already in the DOM.** Price/limit tables behind Go/Go
  Plus-style tabs can be read in one shot without clicking through them:
  `document.querySelectorAll('table')` plus a hidden-state check (`offsetParent`
  or the `hidden` attribute) returns every panel at once.
- **A near-zero sub-score next to a mid-range index is a data-quality signal,
  not a verdict.** Partial Terminal-Bench coverage shows up as implausibly low
  passes (single-digit fractions) for models that index fine. Report the number
  as the source states it, then say plainly that it looks under-measured and
  base the recommendation on the index plus price — never silently drop the row
  or quietly promote the metric to a decision criterion.
- **Index ≠ speed ≠ price.** A model can rank high on the index and still be
  the wrong pick (region locks, context limits, peak-hour pricing). Rank first,
  then filter on the user's actual constraints — see
  `references/opencode-go.md` for that filtering pattern.
