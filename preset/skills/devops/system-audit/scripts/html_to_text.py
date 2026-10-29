#!/usr/bin/env python3
"""Strip HTML docs pages to plain text for offline grepping.

Use when web_extract truncates a long release-notes/changelog page and you need
the sections you actually care about (e.g. 'Server', 'Kernel', 'Development').

Usage:
    python3 html_to_text.py <url> <outfile>
    grep -n "¶" outfile | head -40      # section index
    sed -n '427,500p' outfile            # one section

Why: many doc sites (documentation.ubuntu.com and friends) put all sections on
one page; character-budgeted extraction only ever returns the head, and raising
char_limit does not help.
"""
import sys, re, html, urllib.request

url, out = sys.argv[1], sys.argv[2]
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
t = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
t = re.sub(r'<script.*?</script>', '', t, flags=re.S)
t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
t = re.sub(r'<[^>]+>', ' ', t)
t = html.unescape(t)
t = re.sub(r'[ \t]+', ' ', t)
t = re.sub(r'\n\s*\n+', '\n', t)
open(out, 'w').write(t)
print(len(t), 'chars ->', out)
