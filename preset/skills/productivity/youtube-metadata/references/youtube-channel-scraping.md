# Full subscription-list harvest and watch-history extraction through the live browser

Selectors, endpoints and corruption traps for YouTube account pages. Driven through the
browser session described in `web-automation-auth` → `references/live-browser-cdp-marionette.md`;
triage logic (what to keep) is in `references/subscriptions-triage.md`.

## Which page gives which list

| Page | Yields |
|---|---|
| `/feed/subscriptions` | only channels with new videos — tens of thousands missing |
| `/feed/channels` | the FULL subscription list, A-Z, with subscriber counts |
| `/feed/history` | watch history |

The "All subscriptions" header button leads to `/feed/channels`.

Standing rule: the user expects the complete result, not the first partial list with a
disclaimer. If the obvious source is partial, find the full source silently and report from it.

## Harvest `/feed/channels`

Selectors (new UI): name → `ytd-grid-channel-renderer` → `#channel-title #text` (fallbacks
`#channel-title`, `h3 a`, `a#main-link`); subscribers → `#subscribers` (fallback
`#video-count`); handle → regex `@[\w.\-]{3,}` over the card text.

Scroll loop: `window.scrollTo(0, document.documentElement.scrollHeight)` + 2–3 s pause.
**End condition:** the continuation item is gone AND `scrollHeight` stopped growing — never
count DOM nodes (the count can stall during load).

Write JSON after every iteration: at ~1400 cards the socket dies mid-loop and a single
end-of-run write loses everything.

## Watch history: one HTTP page beats pagination

The first page of `/feed/history` carries ~200 `videoRenderer` objects to a plain HTTP
request — enough for an interest profile. Do not chase InnerTube pagination: it returns
`logged_in: 0` and empty payloads with `Authorization: SAPISIDHASH`, with
`credentials:'include'`, with `browseId: FEhistory`, and with `visitorData`; the continuation
token is not in `ytInitialData`; and scroll-harvest stalls at ~39 unique videos
(virtualization).

Requirements: cookies from `cookies.sqlite` for the `.youtube.com` domain, **one value per
name** (duplicates break SAPISIDHASH), `INNERTUBE_API_KEY` + `INNERTUBE_CLIENT_VERSION`
regexed from the HTML, and DoH in the profile when the host does not resolve locally.

Parse nested JSON from the response string with a brace-matching `grab(txt, key)` helper
searching for `'"videoRenderer":'` — template strings `"videoRenderer": null` are numerous.
Fields: `title` (simpleText | runs[].text), `ownerText`, `publishedTimeText`,
`viewCountText`.

## Retention on a long harvest

Write one JSONL record per page so a socket break costs one row, and progress is always
visible on disk. Keep per-item budgets honest: a full pass written only at the end leaves
neither file nor pace.

## Mass-subscription fingerprint

A handle ending in 3+ digits (`@name777`, `@user-4k9x2`, `@10002017`) is a batch-created
channel: 202 of ~1400 on this account, one overlapping the watch history. Safe, free signal
for unsubscribing without semantic analysis — check the overlap count first.
