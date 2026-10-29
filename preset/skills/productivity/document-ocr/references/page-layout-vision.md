# Reading a photographed book page precisely, and typesetting to match

> Rule of thumb: a vision reply is *one witness*. Dark-pixel band profiles on
> the original are the other. Where they disagree, implement the profiles and
> re-read the text with vision.

## 1. Get the vision route working first

`vision_analyze` answering «unavailable — no vision-capable provider» means
`auxiliary.vision` names a model that cannot read images — not that the box has
no vision.

1. `hermes config get auxiliary.vision` — check provider/model.
2. Test a candidate before committing it: POST to the OmniRoute proxy
   `http://localhost:20128/v1/chat/completions` with the working `sk-76d…`
   key from `~/.omniroute/storage.sqlite` (table `api_keys`, column `key`,
   `WHERE key_prefix LIKE 'sk-76d%'`) and a thumbnail image as
   `data:image/jpeg;base64` in a standard vision message.
3. Known image-capable routes on this box:
   - **OmniRoute + `ocgo/muse-spark-1.3-contributor`** — reads pages, covers
     and plates well; set it with
     `hermes config set auxiliary.vision.model "ocgo/muse-spark-1.3-contributor"`.
     Applies live — verify with one `vision_analyze` call, no restart needed.
   - The same model direct to `https://opencode.ai/zen/go/v1` →
     `ModelProtocolUnsupported`; `cline-pass/muse-spark-1.3-contributor` via
     the unwrap proxy on 127.0.0.1:8765 → region-forbidden; `cline-pass/qwen3.8-max`
     → entitlement error.
   - Local Ornith35B (`192.168.1.10:8095`, key `local-ornith`) works; slower
     and weaker — fallback only.
4. Never edit `~/.hermes/config.yaml` by hand from inside the gateway: the
   patch tool refuses it as security-sensitive and heredoc edits are refused
   by the command scanner. `hermes config set <key> <value>` is the sanctioned
   path.

### Vision reply stability (always-on)

- **Send a downscaled thumbnail (~1000–1200 px long side), not the raw
  original.** Large full-res page photos intermittently produce total
  hallucinations — the read comes back describing an unrelated image
  ("an English AI-assistant text block", a stock selfie) instead of the page.
- **Treat a reply describing something that is clearly not your page as a
  hallucinated read, never as data**: do not typeset from it, do not reason
  from it — rebuild the image at ~1000 px and re-ask.
- **Sanity-check the reader before a working session**: send a trivial probe
  (solid background + centered shape) and expect it described correctly;
  on timeouts repeat with a SMALLER crop of just the region needed (a
  clipped tail or portrait crop often gets through when the full page does
  not). Identical full-page retries are wasted turns.
- **Ask closed, countable questions — open transcription is where the
  hallucinations live.** «Есть ли подпись под портретом, ДА или НЕТ»,
  «сколько строк ниже портрета», «должность и фамилия — дословно» return
  single facts cross-checkable against the band profile; a free-form
  «опиши страницу» can invent whole content. Every answered count or
  yes/no must agree with the dark-pixel bands before it is used.
- **A reply stating it only has «текстовый блок» / «нет доступа к пикселям»
  and asking to send the image is a refusal signal, not a page observation
  and not proof the image is wrong.** It appears intermittently for the same
  file the same model reads correctly on the next retry — discard it, do not
  reason from it, re-send a FRESH downscaled copy (~1100 px) as a new file
  rather than re-evaluating the same attachment.

## 2. Verify geometry numerically; let vision read the text

Ask for positions as **fractions of the page**, not pixels:

```
Это одна страница (№N) книги. Ответь точно:
1) координаты заголовка, портрета и текстовых колонок в долях страницы
   (слева/справа/сверху/снизу);
2) есть ли подпись под портретом — дословно;
3) сколько строк текста и на каких долях высоты;
4) что в левом нижнем углу;
5) подпись автора внизу — дословно и её выравнивание;
6) где номер страницы.
```

A reply worth building on looks like: plate x .075–.37 / y .11–.405, twelve
text lines right of the plate, full-width lines below, signature right-aligned,
page number in the outer bottom corner.

**Cross-check every probed fraction against dark-pixel band profiles.** On
the half-page image (numpy): threshold <~130, sum dark pixels per row →
text-line bands; per column within a band → the plate's exact x-extent and
where the side column starts. Exact to the pixel, immune to hallucination;
when the vision reply and the profile disagree, **the profile wins**. This
catches a crop that cuts part of the plate, a line claimed "in the side
column" that actually spans full width, and a caption the model never saw.

**Decide column vs full-width by bands, not by feel.** The wrap-around side
column ends at the first band below the plate that spans outer margin to
outer margin; every earlier band beside the plate is side-column material.
Parking content in the column because it reads as a continuation displaces
every line after it — split the sentence exactly at the full-width band.

**A page that ends mid-sentence ships mid-sentence.** Transcribe only the
row bands actually present; never invent a trailing word or line to round
off the layout — the invented line belongs to the next page and drifting
pagination is exactly what «строка в строку» forbids.

**Never add a caption the bands don't show.** If no short centered/offset row
pairs sit between the plate's bottom edge and the next full-width band, the
page has no plaque caption — leave it out.

**Use the vision read for the verbatim text too.** On this book's small italic
serif, tesseract mangles words («Летотисъ», «Коллунор», «прееметвен») while the
vision model transcribes clean; let OCR only cross-check proper nouns and
numbers, and re-ask vision when a word looks garbled.

## 3. Typeset to the verified fractions

Skeleton (reportlab, A4 points):

```python
W, H = A4
plate_pw = CW * (frac_w / col_frac_w)          # plate width as page fraction
plate_ph = plate_pw * plate_h0 / plate_w0      # original pixel proportions —
#                                               never force a plate square
c.drawImage(plate, x, H - frac_y_top * H - plate_ph, plate_pw, plate_ph)
# lines right of the plate start at its top baseline; full-width lines
# start below the plate's bottom edge; signature drawRightString;
# page number drawn at its probed fraction, not centred by default
```

Full working example: str16-style page — heading centred at ~y .075, plate
left ~x .075–.37, 12 lines in the right column, 6 lines full width, 3-line
signature right-aligned at ~y .60–.665, page number at the lower-outer corner.

## 4. Pre-delivery fidelity checklist

Close the loop with a side-by-side render compare — the checklist below is
*what* to check, this is *how*: render the finished page
(`pdftoppm -png -r 150 -f N -l N out.pdf view`), montage source photo +
render at equal height (PIL, white gutter), and run `vision_analyze` on the
montage asking for visual differences only — plate size/gap, fonts, indents,
leading, signature/number placement — never content. Fix what it names,
re-render, repeat until it reports no critical diffs. Two passes closed a
representative page here; never ship the first render unchecked.

**For the page tail make a dedicated narrow side-by-side** of just the bottom
band (last lines + page number) — full-page montages hide whether the last
line, hyphen breaks and column depth actually coincide; these are the very
faults the user spots (an invented trailing line, a caption shifted into the
wrap column, a number in the wrong corner).

Typography faults the montage catches that OCR never will: body set upright
instead of the source's italic; DejaVu has no italic face, so register
`LiberationSerif-Italic.ttf` for body and signature. Keep the plate's pixel
proportions (never force square), trim the near-white halo ring off plate
crops and autocontrast before embedding, hold the photo–text gap minimal,
sit the signature (same size/italic as body, right-aligned) directly under
the text with no large gap, and draw the page number small italic gray at
its probed corner.

Run it against the source photo every time — the user compares the same way:

- [ ] plate position and proportions match the source (not square, not stretched);
- [ ] plate cut from the original full-res photo and sharpened
      (`book-scan-pipeline.md` §2);
- [ ] text verbatim from the vision read, remaining typos fixed against the source;
- [ ] page number at the source's position (outer bottom corner here, not centred);
- [ ] signature alignment matches the source;
- [ ] column/full-width boundaries match the band profile;
- [ ] blank leaves present at the count visible in the photos;
- [ ] cover portrait, desk background stripped, corner colour probes pass.
