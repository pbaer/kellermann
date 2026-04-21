# parser

Turns the `kriegstagebuch-YYYY.txt` files into structured JSON and maps each letter to its page in `kriegstagebuch.pdf` to aid OCR proofreading.

## Pipeline

```
kriegstagebuch-YYYY.txt   →  parse.py     →  out/kriegstagebuch-YYYY.json
kriegstagebuch.pdf        →  map_pdf.py   →  out/pages/page-NNN.png,
                                             out/ocr.jsonl (cached),
                                             out/letter_pages.json,
                                             + merges pdf_page / pdf_page_range
                                               back into the per-year JSON
render_pages.py renders all PDF pages to PNG at 200 DPI (called separately).
```

## Running

```sh
.venv/bin/python parse.py --all            # parse all years
.venv/bin/python render_pages.py           # render 167 pages to PNG (one-time)
.venv/bin/python map_pdf.py                # OCR + map letters to pages
```

Re-run `parse.py` whenever the `.txt` files change. Re-run `map_pdf.py` afterward to re-merge page info. The OCR cache (`out/ocr.jsonl`) is reused unless deleted.

## Proofreading workflow

Each letter in the per-year JSON has either a `pdf_page` (exact) or a `pdf_page_range` (narrow range when OCR missed the date). Open the matching `out/pages/page-NNN.png` alongside the `.txt` to spot OCR errors.

For an interactive tool, run the local proofreading app:

```sh
.venv/bin/python proofread.py
# open http://localhost:8765
```

After making structural changes to a `.txt` file (splitting or merging letters, or any edit that changes letter count), kill the server and run `./run.sh` — it re-parses, re-maps pages, and starts the server in one shot.

Three-pane UI: year/letter nav on the left, editable text in the middle, scanned page on the right. Ctrl+S commits to the source `.txt`; Ctrl+← / Ctrl+→ navigate (blocked when you have uncommitted changes). After a commit session, re-run `parse.py` and `map_pdf.py` to refresh the derived JSON.

See `schema.md` for the full output schema.
