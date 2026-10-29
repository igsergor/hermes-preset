#!/usr/bin/env python3
"""Convert a raw subtitle dump into readable timestamped paragraphs.

Handles the two shapes the fetchers produce:
  * WebVTT (.vtt from yt_fetch.py) — rolling cues that REPEAT the tail of the
    previous cue, so a naive line dump repeats whole phrases every 2 seconds.
    YouTube's fmt=vtt roll-up is harsher: every cue also carries the ENTIRE
    line-so-far as its own plain line (plus 0.01s readability cues that are pure
    duplicates), so words_from_vtt dedups by EXACT LINE TEXT first — the 8-word
    tail window alone leaves those echoes in.
  * youtube-transcript-api text (--out, via yt_transcript.py) — "[M:SS] word"
    one per line.

Usage:
    python3 sub_to_paragraphs.py <file.vtt|file.txt> [--out FILE] [--gap 3] [--max 50]

Why the dedup: auto-captions emit an overlapping window; skipping a word already
seen in the last N words removes the echo without losing real repeats (a word said
twice 2s apart in the same sentence still survives, because the 8-word tail has
moved on).
"""
import argparse
import re
import sys

OVERLAP_TAIL = 8
MIN_OVERLAP = 3


def words_from_vtt(text):
    """[(seconds, word)] from WebVTT, cue overlaps removed.

    Line-level dedup first: fmt=vtt roll-up repeats the WHOLE line-so-far as its
    own line in every cue (and adds 0.01s pure-duplicate cues), so exact-line
    filtering must run before the word-tail window — otherwise echoes survive."""
    words, cur, seen = [], [], set()
    for line in text.splitlines():
        m = re.match(r"(\d{2}):(\d{2}):(\d{2})\.\d{3} -->", line)
        if m:
            if cur:
                words.extend(_emit(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), cur))
            cur = []
            continue
        t = re.sub(r"<[^>]+>", "", line).strip()
        if not t or re.match(r"^(WEBVTT|Kind:|Language:|\d+$)", t):
            continue
        key = re.sub(r"\s+", " ", t)
        if key in seen:
            continue
        seen.add(key)
        cur.append(t)
    if cur:
        words.extend(_emit(0, cur))
    return words


def words_from_api(text):
    """[(seconds, word)] from yt_transcript.py --out format."""
    words, last = [], 0
    for line in text.splitlines():
        m = re.match(r"\[(\d+):(\d{2})\] (.*)", line)
        if not m:
            continue
        sec = int(m.group(1)) * 60 + int(m.group(2))
        ws = m.group(3).split()
        for i, w in enumerate(ws):
            words.append((sec if i == 0 else last, w))
        last = sec
    return words


def _emit(base, pieces):
    out = []
    for p in pieces:
        for w in p.split():
            out.append((base, w))
    return out


def dedup(words):
    """Drop words that merely echo the rolling caption overlap."""
    kept, tail = [], []
    for sec, w in words:
        n = re.sub(r"\W+", "", w.lower())
        if not n:
            continue
        norm = [re.sub(r"\W+", "", x.lower()) for x in tail]
        if len(norm) >= MIN_OVERLAP and n in norm[-OVERLAP_TAIL:]:
            continue
        kept.append((sec, w))
        tail.append(w)
        if len(tail) > OVERLAP_TAIL:
            tail.pop(0)
    return kept


def to_paragraphs(words, gap=3, max_words=50):
    chunks, start, cur, prev = [], None, [], None
    for sec, w in words:
        if start is None:
            start, cur, prev = sec, [w], sec
            continue
        if sec - prev > gap or len(cur) > max_words:
            chunks.append((start, cur))
            start, cur = sec, [w]
        else:
            cur.append(w)
        prev = sec
    if cur:
        chunks.append((start, cur))
    return chunks


def fmt(sec):
    return f"{int(sec // 60):02d}:{int(sec % 60):02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default="-")
    ap.add_argument("--gap", type=int, default=3)
    ap.add_argument("--max", type=int, default=50)
    a = ap.parse_args()

    text = open(a.src, encoding="utf-8").read()
    words = words_from_api(text) if text.lstrip().startswith("[") else words_from_vtt(text)
    chunks = to_paragraphs(dedup(words), a.gap, a.max)
    body = "\n\n".join(f"**[{fmt(s)}]** " + " ".join(ws) for s, ws in chunks)
    if a.out == "-":
        print(body)
    else:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(body)


if __name__ == "__main__":
    sys.exit(main())
