#!/usr/bin/env python3
"""Clean a YouTube roll-up VTT transcript into readable lines.

YouTube's roll-up captions repeat the whole line-so-far in every cue, so the raw VTT
reads as word salad. Modern VTT carries the repetition as FULL DUPLICATE LINES (not
word tails), so cleanup is exact-line dedup with a seen-lines set, not prefix-trimming:

  1. Strip word-timing tags (<00:00:01.319><c>word</c>) before any comparison.
  2. Within a cue, if the text is exactly "X X" (first half == second half), keep one half.
  3. Across cues, drop any line already seen verbatim; keep only genuinely new lines.

Usage:
    python3 vtt_cleanup.py input.vtt            # prints cleaned text to stdout
    python3 vtt_cleanup.py input.vtt out.txt    # writes to out.txt
    cat input.vtt | python3 vtt_cleanup.py     # reads stdin

Stdlib only. Exit 0 on success.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s)


def norm(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def half_dedup(line: str) -> str:
    """If a line is exactly 'X X' (char halves equal), keep one half."""
    if len(line) < 4 or len(line) % 2:
        return line
    half = len(line) // 2
    left = line[:half].strip()
    right = line[half:].strip()
    if left and left == right:
        return left
    return line


def clean_vtt(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    # Split into cue blocks (blank-line separated).
    for block in re.split(r"\n\s*\n", text):
        if "-->" not in block:
            continue
        parts = block.splitlines()
        idx = next((i for i, l in enumerate(parts) if "-->" in l), None)
        if idx is None:
            continue
        body = strip_tags("\n".join(parts[idx + 1:]))
        for raw_line in body.splitlines():
            line = half_dedup(norm(raw_line))
            if not line or line in seen:
                continue
            seen.add(line)
            out.append(line)
    return "\n".join(out) + ("\n" if out else "")


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] not in ("-",):
        src = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        src = sys.stdin.read()
    cleaned = clean_vtt(src)
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(cleaned, encoding="utf-8")
    else:
        sys.stdout.write(cleaned)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
