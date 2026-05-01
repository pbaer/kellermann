# Parser output schema (provisional)

One JSON file per source year: `parser/out/kriegstagebuch-YYYY.json`.

```
{
  "source_file": "kriegstagebuch-1940.txt",
  "year": 1940,
  "entries": [ Entry, ... ]
}
```

## Entry

Shared fields:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable within a file. Letters: `YYYY-NNNN` (zero-padded sequence). Front matter: `YYYY-frontmatter`. |
| `type` | enum | `letter` \| `front_matter` |
| `line_start` / `line_end` | int (1-based) | Source line range, inclusive. |

Letter-only fields:

| Field | Type | Notes |
| --- | --- | --- |
| `author` | `"Wilhelm"` \| `"Marianne"` | From the header. |
| `header_raw` | string | Full header as it appears, with multi-line headers joined by single spaces. |
| `location` | `{raw, uncertain, narrative}` | `uncertain=true` if `?` is present. `narrative=true` for phrases like `auf Fahrt`, `Angriff auf Jug.`. No normalization / gazetteer yet. |
| `date` | `{raw, iso, annotations, occasion}` | `iso` is `YYYY-MM-DD` or `null`. `occasion` captures `1. Ostertag`, `4. Advent`, etc. |
| `body` | `Paragraph[]` | Paragraphs are separated by blank lines in the source. Line breaks within a paragraph are collapsed: a trailing `-` on a line is removed and the next line is joined with no space (German word-break convention); otherwise lines are joined with a single space. |
| `pdf_page` | int \| absent | 1-indexed page in `kriegstagebuch.pdf`. Present only when `map_pdf.py` has been run AND the letter's OCR date anchored to a specific page. PDF page 1 is the cover; PDF page N corresponds to typewriter page N−1 (visible in the scan's top-right corner). |
| `pdf_page_range` | `[int, int]` \| absent | Present (instead of `pdf_page`) when the OCR missed this letter's date. The letter is guaranteed to be on one of the pages in the inclusive range, inferred from surrounding matched letters (since PDF order is identical to .txt order). |

Front-matter-only fields:

| Field | Type | Notes |
| --- | --- | --- |
| `text` | string | Raw content of the block. |

## Paragraph

```
{
  "kind": "prose" | "ocr_note" | "historical_context" | "proofread_marker",
  "text": "...",
  "parentheticals": [    // omitted when empty
    { "text": "...", "char_start": N, "char_end": N, "kind": "likely_retrospective" | "unclassified" }
  ]
}
```

`kind` disambiguates the kinds of paragraph that can appear inside a letter's body:

- `prose` — normal letter or editorial-bridge text.
- `ocr_note` — a paragraph beginning with `#####` (OCR ambiguity note).
- `historical_context` — a paragraph beginning with `&&&&&` (brief annotation summarizing the broader historical context of events, places, or people referenced in the surrounding letter text). The marker is preserved in `text`; consumers may strip the leading `&&&&&` when rendering.
- `proofread_marker` — a paragraph that is exactly `>>>>>` (manual-review boundary).

`parentheticals` is only present on `prose` paragraphs that actually contain parentheses; the field is omitted otherwise. `char_start` / `char_end` are offsets into the joined paragraph text. Classification is coarse:

- `likely_retrospective`: contains `Wilh.` / `Wilhelm`, a post-1945 year, or words like `später`, `jahrzehntelang`, `inzwischen`, `erinnert sich`.
- `unclassified`: everything else.

## Known simplifications

- Editorial bridges (Wilhelm's 1989 prose between letters) are currently attached to the preceding letter's body as trailing prose paragraphs. They are not a separate entry type yet.
- The 1945 epilogue (lines 168–295, the "Hier der Bericht…" narrative and march itinerary) is attached to the last letter's body. To be split in a later pass.
- Location normalization (`Chtz.` / `Chemnitz`, `Dneprop.` / `Dnjepropetrowsk`) is deferred — only `raw` is captured.
- No signature/closing extraction. The letter body ends at the next header or end-of-file, with trailing blank lines trimmed.
- The single non-canonical header `Marianne, Brief vom 01. 01. 1943` at 1943.txt:1–2 is captured as front matter, not a letter.
