# parser

Turns the `sources/documents/kriegstagebuch-YYYY.txt` files into structured JSON, maps each letter to its page in `sources/documents/kriegstagebuch.pdf` for OCR proofreading, and produces the per-chapter `letters.jsonl` files that the website reads.

## Pipeline

```
sources/documents/kriegstagebuch-YYYY.txt
                          →  parse.py                   →  out/kriegstagebuch-YYYY.json
sources/documents/kriegstagebuch.pdf
                          →  map_pdf.py                 →  out/pages/page-NNN.png,
                                                           out/ocr.jsonl (cached),
                                                           out/letter_pages.json,
                                                           + merges pdf_page / pdf_page_range
                                                             back into the per-year JSON
out/kriegstagebuch-YYYY.json + data/chapter-XX/chronology.jsonl
                          →  build_chapter_letters.py   →  data/chapter-XX/letters.jsonl

render_pages.py renders all PDF pages to PNG at 200 DPI (called separately, one-time).
```

`out/` is git-ignored intermediate state. The site reads from `data/`.

## Running

```sh
.venv/bin/python parse.py --all            # parse all years
.venv/bin/python render_pages.py           # render 167 pages to PNG (one-time)
.venv/bin/python map_pdf.py                # OCR + map letters to pages
.venv/bin/python build_chapter_letters.py  # bucket letters into data/chapter-XX/
```

The OCR cache (`out/ocr.jsonl`) is reused unless deleted.

## Updating the data after editing a `kriegstagebuch-*.txt`

The `.txt` files under `sources/documents/` are the source of truth. Anything in `data/chapter-XX/letters.jsonl` is derived from them and gets overwritten.

**Typo / wording fix inside one letter** (no change to letter count or boundaries):

```sh
./run.sh    # parse → map_pdf → build_chapter_letters → proofread server
```

`./run.sh` from this directory does the full refresh in one shot. Or run the three Python steps individually if you don't want the proofreading server.

**Splitting or merging a letter** (changes letter count, header lines change):

Same command — `./run.sh`. The pipeline re-numbers letter ids (`YYYY-NNNN`) by source order within the year, so renumbering ripples through `data/chapter-XX/letters.jsonl` automatically. Watch the `build_chapter_letters.py` summary at the end:

- `Per-chapter letter counts` should still total 515 (or whatever the current authoritative total is — the script asserts this).
- `All boundary checks: OK` confirms the chapter-cut letter ids still match `expected_boundaries` in `build_chapter_letters.py`.

If a split/merge straddles a chapter boundary, `expected_boundaries` and the `LETTER_CHAPTER_OVERRIDES` dict in `build_chapter_letters.py` may need updating.

**Chronology / location data** (`data/chapter-XX/chronology.jsonl`) is hand-curated, not generated. Edit those files directly. If you change `arrival_date` values you may rebucket which chapter a letter falls into — re-run `build_chapter_letters.py` to refresh.

**Markers in the `.txt` files** (preserve when editing):
- `>>>>>` marks how far manual proofreading has progressed; the parser captures it as a `proofread_marker` paragraph (the map page drops it from rendering).
- `#####` flags an ambiguous OCR reconstruction or unknown abbreviation; the parser captures it as an `ocr_note` paragraph.
- `&&&&&` flags a brief annotation that summarizes the broader historical context of events, places, or people referenced in the surrounding letter text. The parser captures it as a `historical_context` paragraph; the map page renders it in a distinct font alongside the letter prose. These annotations are derived content — short stubs that downstream tooling will later expand into linked, more detailed historical material — and not part of Wilhelm's original transcription.

**Per-letter ordering convention:** within a letter (i.e. between two `von …` headers), prose paragraphs come first, then any `#####` notes, then any `&&&&&` annotations. The hard rule is only that all of a letter's content sits between its header and the next letter's header; the parser preserves source order and downstream consumers must tolerate annotations appearing out of order. The convention is what we follow when authoring or auditing source files. If a `&&&&&` annotation depends on a `#####` ambiguity in the same letter, the annotation should hedge accordingly (e.g. „vermutlich …").

## Proofreading workflow

Each letter in the per-year JSON has either a `pdf_page` (exact) or a `pdf_page_range` (narrow range when OCR missed the date). Open the matching `out/pages/page-NNN.png` alongside the `.txt` to spot OCR errors.

For an interactive tool, run the local proofreading app:

```sh
.venv/bin/python proofread.py
# open http://localhost:8770
```

This serves **one page with two modes** — toggle between them with the tabs at the top, or `Alt+1` (Letters) / `Alt+2` (Audio):

- **Letters** — three-pane UI: year/letter nav on the left, editable text in the middle, scanned page on the right. Ctrl+S commits to the source `.txt`.
- **Audio** — clip + timestamped-block nav on the left, audio player + editable text on the right, scrollable map pane below. A full-width **waveform scrubber** under the transport controls shows the amplitude envelope of the current block's audio window; the lead-in/lead-out spans are dimmed and the block's logical start/end are marked, so it's clear which audio belongs to the block. Playback runs from 2s before the block start to 2s after its end. The block granularity matches Whisper's timestamp granularity — selecting a block seeks the audio to that timestamp. Plus Ctrl+Shift+Space to play from the block start and Ctrl+Shift+W to swap the speaker tag (`[Wilhelm]` ↔ `[Tilman]`) on the cursor's line.

Both modes share the `>>>>>` proofread-marker convention and the same core keybindings (Ctrl+S commit, Ctrl+Shift+M mark-as-proofread). Each mode keeps its full state — including **uncommitted edits** — while you switch to the other, so you can flip over to check something and flip back untouched; a dot on the tab flags a mode with pending changes.

`./run.sh` re-parses, re-maps pages, rebuilds the per-chapter letters and starts the combined server in one shot — use it after a session that changes letter structure.

### How it's wired

`proofread.py` is a thin shell (page: `proofread.html`): it imports `proofread_letters.py` (letters) and `proofread_audio.py` (audio) and reuses their `State` + request handlers unchanged, mounting each tool's page in its own `<iframe>` (`/tool/letters` → `proofread_letters.html`, `/tool/audio` → `proofread_audio.html`) so all in-page state survives a mode switch. Those two modules are implementation details of the combined tool; each can still be run on its own (`proofread_letters.py` → 8765, `proofread_audio.py` → 8766) but the combined `proofread.py` is the one to use. All of them share `proofread_shared.js` for diff/search rendering.

The audio waveform is served by `/api/audio/waveform`, which slices a precomputed peak file. `precompute_waveforms.py` decodes each clip once (via **`ffmpeg`**) into a sidecar `"<clip>.mp3.peaks"` next to the mp3 — int16 (min,max) peaks at 200/sec — so the endpoint just slices the requested window out of it (sub-millisecond) instead of decoding on every block. `run.sh` runs it before launching the server (idempotent — skips clips whose sidecar is current), and the server also builds any missing sidecar lazily in the background, falling back to a windowed `ffmpeg` decode until it's ready. `ffmpeg` must be on `PATH`; the `.peaks` sidecars are derived caches and are git-ignored.

See `schema.md` for the full output schema.
