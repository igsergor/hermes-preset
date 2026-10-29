#!/bin/bash
# Batch subtitle fetch via yt-dlp with the user's Firefox-profile cookies.
# Usage: ytdlp_sub_batch.sh <ids-file> [outdir]
#   <ids-file>: one video ID per line
#   Skips IDs already downloaded; per-video "OK/ПУСТО <timestamp>" lines on stdout.
#   Resumable: rerun the same file — only missing IDs are fetched.
export PATH="$HOME/.deno/bin:$PATH"   # deno: curl -fsSL https://deno.land/install.sh | sh -s -- -y
FF=~/snap/firefox/common/.mozilla/firefox/20wpd4km.default
IDS="$1"; OUT="${2:-/tmp/yt_subs}"
mkdir -p "$OUT"
while read -r vid; do
  [ -z "$vid" ] && continue
  if ls "$OUT/${vid}".*.vtt >/dev/null 2>&1; then echo "$vid: уже есть"; continue; fi
  timeout 90 yt-dlp --js-runtimes deno --remote-components ejs:github \
    --cookies-from-browser "firefox:$FF" \
    --skip-download --write-auto-sub --write-subs --sub-langs 'ru,en' \
    -o "$OUT/%(id)s" "https://www.youtube.com/watch?v=$vid" >/dev/null 2>&1
  if ls "$OUT/${vid}".*.vtt >/dev/null 2>&1; then
    echo "$vid: OK $(date '+%H:%M:%S')"
  else
    echo "$vid: ПУСТО $(date '+%H:%M:%S')"
  fi
done < "$IDS"
echo "ГОТОВО: $(wc -l < "$IDS") id обработано $(date '+%H:%M:%S')"
