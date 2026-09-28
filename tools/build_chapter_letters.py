#!/usr/bin/env python3
"""
Build per-chapter letters.jsonl files for the map page from parse.py output.

Reads:
- tools/out/kriegstagebuch-YYYY.json  (1939..1945)
- data/chapter-XX/chronology.jsonl  (chapters 01..07; language-agnostic layout)

Writes:
- data/chapter-XX/letters.jsonl  (one letter per line)
- data/chapter-XX/chronology.jsonl  (only the `source_letters` id references,
  and only when a split/merge renumbered letters — see below)

Localizable text fields (header_raw, location_raw, body[].text,
body[].parentheticals[].text) are emitted as { "de-DE": "..." } objects so the
on-disk schema is consistent with the rest of the localized data. Translations
into "en-US" can be added later without changing the file shape.

Letter -> chapter assignment: each letter is bucketed into the chapter whose
chronology contains the latest entry with arrival_date <= letter.date.iso.
This makes the chapter-cut points (last/first letter of each chapter) emergent
from the chronology rebucketing already done in Phase A. Letters with a null
date.iso fall back to line-order proximity to the surrounding dated letters.

Letter ids (YYYY-NNNN) are sequence numbers within a year, so an OCR fix that
splits or merges a letter renumbers everything after it in that year. To keep
the hand-curated chronology's `source_letters` references pointing at the same
letters, the previous letters.jsonl files are read before being overwritten,
old and new ids are matched by header (plus occurrence index, since a few
headers repeat), and changed ids are rewritten in chronology.jsonl. References
to a letter whose header disappeared (merged away) can't be resolved
automatically; they are reported, nothing under data/ is written (so the
problem persists until fixed), and the script exits non-zero.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from bisect import bisect_right

ROOT = Path(__file__).resolve().parent.parent
PARSER_OUT = ROOT / 'tools' / 'out'
DATA_DIR = ROOT / 'data'
SOURCE_LOCALE = 'de-DE'
YEARS = range(1939, 1946)

# Letters below are identified by (author, date.iso) rather than by id, since
# ids shift when letters are split or merged.

# Narrative overrides where date-based bucketing places a letter in the wrong
# chapter. Each entry pins a letter to a specific chapter regardless of date.
#
# Wilhelm, 1945-03-26, "Den Haag" — courier letter sent as the V-2 division was
# being pulled out of Holland (Mar 24 night). Its date is past the Ch7
# chronology entry "Rückmarsch 1945-03-24", but narratively it closes the V-2
# chapter (Ch6) rather than opening the retreat (Ch7). The retreat opens with
# Wilhelm's letter of 1945-04-02 ("auf dem Rückmarsch").
LETTER_CHAPTER_OVERRIDES: dict[tuple[str, str], int] = {
    ('Wilhelm', '1945-03-26'): 6,
}

# Sanity check: the first/last letter of each chapter, as the plan says.
EXPECTED_BOUNDARIES: list[tuple[int, str, tuple[str, str]]] = [
    (1, 'last',  ('Wilhelm',  '1940-05-09')),
    (2, 'first', ('Wilhelm',  '1940-05-12')),
    (2, 'last',  ('Marianne', '1941-01-21')),
    (3, 'first', ('Wilhelm',  '1941-01-23')),
    (3, 'last',  ('Wilhelm',  '1941-06-10')),
    (4, 'first', ('Wilhelm',  '1941-06-12')),
    (4, 'last',  ('Marianne', '1943-02-04')),
    (5, 'first', ('Wilhelm',  '1943-02-08')),
    (5, 'last',  ('Wilhelm',  '1943-07-04')),
    (6, 'first', ('Wilhelm',  '1943-10-15')),
    (6, 'last',  ('Wilhelm',  '1945-03-26')),
    (7, 'first', ('Wilhelm',  '1945-04-02')),
]

SOURCE_LETTERS_RE = re.compile(r'"source_letters": (\[[^\]]*\])')


def load_chronology() -> list[tuple[str, int]]:
    """Return [(arrival_date, chapter_number), ...] sorted by date."""
    items: list[tuple[str, int]] = []
    for ch in range(1, 8):
        p = DATA_DIR / f'chapter-{ch:02d}' / 'chronology.jsonl'
        with p.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                items.append((e['arrival_date'], ch))
    items.sort(key=lambda t: t[0])
    return items


def chapter_for_date(iso: str, chrono_dates: list[str], chrono_chapters: list[int]) -> int:
    """Find the chapter of the latest chronology entry with arrival_date <= iso."""
    idx = bisect_right(chrono_dates, iso) - 1
    if idx < 0:
        return chrono_chapters[0]  # before any entry → first chapter
    return chrono_chapters[idx]


def localize(text: str | None) -> dict | None:
    """Wrap source-locale text into the on-disk localized shape.

    Returns None for empty / None inputs so the caller can omit the field.
    """
    if text is None or text == '':
        return None
    return {SOURCE_LOCALE: text}


def localize_body(body: list[dict]) -> list[dict]:
    out = []
    for p in body:
        new_p: dict = {}
        for k, v in p.items():
            if k == 'text':
                wrapped = localize(v)
                if wrapped is not None:
                    new_p[k] = wrapped
            elif k == 'parentheticals':
                new_pars = []
                for par in v:
                    new_par: dict = {}
                    for pk, pv in par.items():
                        if pk == 'text':
                            wrapped = localize(pv)
                            if wrapped is not None:
                                new_par[pk] = wrapped
                        else:
                            new_par[pk] = pv
                    new_pars.append(new_par)
                new_p[k] = new_pars
            else:
                new_p[k] = v
        out.append(new_p)
    return out


def ids_by_header_key(records: list[tuple[str, str]]) -> dict[tuple[str, int], str]:
    """Map (header, occurrence index) -> id for [(id, header), ...] in source order."""
    seen: dict[str, int] = {}
    out: dict[tuple[str, int], str] = {}
    for lid, header in records:
        n = seen.get(header, 0)
        seen[header] = n + 1
        out[(header, n)] = lid
    return out


def load_previous_letters() -> list[tuple[str, str]]:
    """[(id, header), ...] from the letters.jsonl files about to be overwritten."""
    records = []
    for ch in range(1, 8):
        p = DATA_DIR / f'chapter-{ch:02d}' / 'letters.jsonl'
        if not p.exists():
            continue
        with p.open() as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    records.append((r['id'], r['header_raw'][SOURCE_LOCALE]))
    records.sort(key=lambda t: t[0])  # YYYY-NNNN sorts in source order
    return records


def update_chronology_refs(previous: list[tuple[str, str]],
                           current: list[tuple[str, str]],
                           write: bool) -> list[str]:
    """Rewrite chronology `source_letters` ids renumbered by a split/merge.

    Returns a list of problems (references that don't resolve to a letter).
    With write=False, only checks. Call once to check, then again to write
    only if there were no problems.
    """
    header_by_old_id = dict(previous)
    old_by_key = ids_by_header_key(previous)
    new_by_key = ids_by_header_key(current)
    remap = {old: new_by_key[k] for k, old in old_by_key.items()
             if k in new_by_key and new_by_key[k] != old}
    # Old ids whose letter no longer exists. Check these explicitly: after a
    # merge the id string itself is typically reused by the following letter.
    vanished = {old for k, old in old_by_key.items() if k not in new_by_key}
    current_ids = {lid for lid, _ in current}
    problems: list[str] = []

    for ch in range(1, 8):
        p = DATA_DIR / f'chapter-{ch:02d}' / 'chronology.jsonl'
        text = p.read_text(encoding='utf-8')

        def fix(m: re.Match) -> str:
            ids = json.loads(m.group(1))
            new_ids = [remap.get(i, i) for i in ids]
            for old, new in zip(ids, new_ids):
                if old in vanished or (old == new and new not in current_ids):
                    header = header_by_old_id.get(old, '?')
                    problems.append(f'chapter-{ch:02d}/chronology.jsonl references {old} '
                                    f'("{header}"), which no longer exists '
                                    f'(merged away?) — fix by hand')
                elif old != new and write:
                    print(f'  [renumber] chapter-{ch:02d}/chronology.jsonl: {old} -> {new}')
            return f'"source_letters": {json.dumps(new_ids, ensure_ascii=False)}'

        new_text = SOURCE_LETTERS_RE.sub(fix, text)
        if write and new_text != text:
            p.write_text(new_text, encoding='utf-8')
    return problems


def build_letter_record(entry: dict) -> dict:
    """Project a parser letter entry to the fields the map needs.

    Localizable text fields are wrapped as { "de-DE": "..." } so the file is
    ready to grow EN translations without a schema change.
    """
    out: dict = {
        'id': entry['id'],
        'author': entry['author'],
        'date_iso': entry['date'].get('iso'),
    }
    location_raw = localize(entry['location'].get('raw'))
    if location_raw is not None:
        out['location_raw'] = location_raw
    header_raw = localize(entry.get('header_raw'))
    if header_raw is not None:
        out['header_raw'] = header_raw
    out['body'] = localize_body(entry.get('body', []))
    if 'pdf_page' in entry:
        out['pdf_page'] = entry['pdf_page']
    elif 'pdf_page_range' in entry:
        out['pdf_page_range'] = entry['pdf_page_range']
    return out


def main() -> int:
    chrono = load_chronology()
    chrono_dates = [d for d, _ in chrono]
    chrono_chapters = [c for _, c in chrono]

    # Group letters by chapter, preserving (year, line_start) order so that the
    # narrative ordering in the .txt source is preserved within each chapter.
    by_chapter: dict[int, list[tuple[int, int, dict]]] = {ch: [] for ch in range(1, 8)}

    null_date_count = 0
    total_letters = 0
    current: list[tuple[str, str]] = []  # (id, header) in source order

    for year in YEARS:
        path = PARSER_OUT / f'kriegstagebuch-{year}.json'
        with path.open() as f:
            doc = json.load(f)
        letters = [e for e in doc['entries'] if e.get('type') == 'letter']

        # First pass: chapter assignment for letters with a real date.iso.
        per_letter_chapter: list[int | None] = [None] * len(letters)
        for i, e in enumerate(letters):
            iso = e['date'].get('iso')
            if iso:
                per_letter_chapter[i] = chapter_for_date(iso, chrono_dates, chrono_chapters)

        # Second pass: fill nulls by inheriting from the nearest dated neighbour
        # in line order (look backward first, then forward).
        for i in range(len(letters)):
            if per_letter_chapter[i] is not None:
                continue
            null_date_count += 1
            # backward
            j = i - 1
            while j >= 0 and per_letter_chapter[j] is None:
                j -= 1
            # forward
            k = i + 1
            while k < len(letters) and per_letter_chapter[k] is None:
                k += 1
            if j >= 0:
                per_letter_chapter[i] = per_letter_chapter[j]
            elif k < len(letters):
                per_letter_chapter[i] = per_letter_chapter[k]
            else:
                per_letter_chapter[i] = 1
            print(f'  [info] {letters[i]["id"]}: null date.iso → chapter {per_letter_chapter[i]} (inherited from neighbour)',
                  file=sys.stderr)

        for i, e in enumerate(letters):
            key = (e['author'], e['date'].get('iso'))
            ch = LETTER_CHAPTER_OVERRIDES.get(key, per_letter_chapter[i])
            by_chapter[ch].append((year, e['line_start'], e))
            current.append((e['id'], e['header_raw']))
            total_letters += 1

    # Sort within each chapter by source order (year, line_start).
    for ch in by_chapter:
        by_chapter[ch].sort(key=lambda t: (t[0], t[1]))

    # Sanity-check: verify the chapter boundary letters land where the plan says.
    def key(e: dict) -> tuple[str, str]:
        return (e['author'], e['date'].get('iso'))
    last_key = {ch: key(items[-1][2]) for ch, items in by_chapter.items() if items}
    first_key = {ch: key(items[0][2]) for ch, items in by_chapter.items() if items}
    boundary_ok = True
    for ch, which, expected in EXPECTED_BOUNDARIES:
        got = (last_key if which == 'last' else first_key).get(ch)
        if got != expected:
            boundary_ok = False
            print(f'  MISMATCH ch{ch} {which}: expected {expected}, got {got}')

    # Keep chronology references stable across renumbering (must run before
    # the old letters.jsonl files are overwritten).
    previous = load_previous_letters()
    ref_problems = update_chronology_refs(previous, current, write=False)
    if ref_problems:
        for msg in ref_problems:
            print(f'  REF ERROR {msg}')
        print('Not writing data/ until these references are fixed.')
        return 1
    update_chronology_refs(previous, current, write=True)

    # Write out files.
    for ch in range(1, 8):
        out_path = DATA_DIR / f'chapter-{ch:02d}' / 'letters.jsonl'
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open('w') as f:
            for _, _, entry in by_chapter[ch]:
                rec = build_letter_record(entry)
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    # Summary.
    print()
    print('Per-chapter letter counts:')
    for ch in range(1, 8):
        items = by_chapter[ch]
        if items:
            first = items[0][2]
            last = items[-1][2]
            print(f'  ch{ch}: {len(items):4d} letters  '
                  f'first={first["id"]} ({first["date"].get("iso")})  '
                  f'last={last["id"]} ({last["date"].get("iso")})')
        else:
            print(f'  ch{ch}: 0 letters')
    print(f'Total letters written: {total_letters}')
    print(f'Letters with null date.iso (chapter inherited from neighbour): {null_date_count}')

    print()
    print(f'All boundary checks: {"OK" if boundary_ok else "FAILED"}')

    return 0 if boundary_ok else 1


if __name__ == '__main__':
    sys.exit(main())
