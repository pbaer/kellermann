#!/usr/bin/env python3
"""Provisional parser for kriegstagebuch-YYYY.txt files.

Extracts letters (with author, location, date, body paragraphs, inline
parentheticals) plus front matter, OCR notes and proofread markers into JSON.

Usage:
    python parser/parse.py --all
    python parser/parse.py --year 1940
    python parser/parse.py --verify-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
YEARS = list(range(1939, 1946))

HEADER_RE = re.compile(r"^von (Wilhelm|Marianne),")
DATE_RE = re.compile(r"den\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")
DATE_RE_ALT = re.compile(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b")
PAREN_RE = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)")
OCC_RE = re.compile(
    r"(\d+\.\s*(?:Hochzeitstag|Advent|Ostertag|Osterfeiertag|Pfingsttag|"
    r"Weihnachtstag|Weihnachtsfeiertag))|Ostern|Karfreitag|Heiligabend"
)
OCR_NOTE_PREFIX = "#####"
PROOFREAD_MARKER = ">>>>>"

NARRATIVE_TRIGGERS = (
    "auf Fahrt", "Angriff auf", "Vormarsch", "unterwegs", ". Tag in",
    "wieder in Stellung", "auf dem Marsch", "auf Transport",
    "auf dem Rückmarsch", "wahrscheinlich", "auf der Fahrt",
)


@dataclass
class Entry:
    id: str
    type: str
    line_start: int
    line_end: int
    author: str | None = None
    location: dict | None = None
    date: dict | None = None
    header_raw: str | None = None
    body: list[dict] | None = None
    text: str | None = None


def classify_paren(inner: str) -> str:
    lower = inner.lower()
    if re.search(r"\bwilh\.?\b|\bwilhelm\b", lower):
        return "likely_retrospective"
    if re.search(r"\b19(4[6-9]|[5-9]\d)\b", inner):
        return "likely_retrospective"
    if any(w in lower for w in ("später", "jahrzehntelang", "inzwischen", "erinnert sich")):
        return "likely_retrospective"
    return "unclassified"


def extract_parentheticals(text: str) -> list[dict]:
    return [
        {
            "text": m.group(1),
            "char_start": m.start(),
            "char_end": m.end(),
            "kind": classify_paren(m.group(1)),
        }
        for m in PAREN_RE.finditer(text)
    ]


def extract_header_meta(header: str, file_year: int) -> dict:
    m = HEADER_RE.match(header)
    author = m.group(1) if m else None
    rest = header[m.end():].strip() if m else header

    date_match = DATE_RE.search(rest)
    if not date_match:
        date_match = DATE_RE_ALT.search(rest)

    if date_match:
        d, mo, y = date_match.group(1), date_match.group(2), date_match.group(3)
        try:
            iso = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            iso = None
        location_str = rest[:date_match.start()].rstrip(" ,.")
        annotations_str = rest[date_match.end():].strip(" ,.")
        date_raw = date_match.group(0).strip()
    else:
        iso = None
        location_str = rest
        annotations_str = ""
        date_raw = None

    occasion = None
    for blob in (annotations_str, location_str):
        om = OCC_RE.search(blob)
        if om:
            occasion = om.group(0)
            break

    is_narrative = any(t in location_str for t in NARRATIVE_TRIGGERS)
    is_uncertain = "?" in location_str

    return {
        "author": author,
        "location": {
            "raw": location_str,
            "uncertain": is_uncertain,
            "narrative": is_narrative,
        },
        "date": {
            "raw": date_raw,
            "iso": iso,
            "annotations": [annotations_str] if annotations_str else [],
            "occasion": occasion,
        },
    }


def join_paragraph_lines(lines: list[str]) -> str:
    """Merge lines of a paragraph into a single string.

    German transcription convention: a line ending in ``-`` marks a word
    broken across a line. Join those with no space and drop the hyphen.
    Other line breaks become a single space.
    """
    if not lines:
        return ""
    out = lines[0]
    for nxt in lines[1:]:
        if out.endswith("-"):
            out = out[:-1] + nxt.lstrip()
        else:
            out = out + " " + nxt.lstrip()
    return out


def parse_file(path: Path, year: int) -> list[Entry]:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    n = len(lines)
    entries: list[Entry] = []

    header_indices = [i for i, line in enumerate(lines) if HEADER_RE.match(line)]
    if not header_indices:
        return entries

    first_header = header_indices[0]
    if first_header > 0:
        fm_lines = lines[:first_header]
        while fm_lines and fm_lines[-1].strip() == "":
            fm_lines.pop()
        if fm_lines:
            entries.append(Entry(
                id=f"{year}-frontmatter",
                type="front_matter",
                line_start=1,
                line_end=len(fm_lines),
                text="\n".join(fm_lines),
            ))

    letter_counter = 0
    for idx, h in enumerate(header_indices):
        letter_counter += 1
        header_raw = lines[h]
        header_end = h

        if not (DATE_RE.search(header_raw) or DATE_RE_ALT.search(header_raw)):
            j = h + 1
            while j < n and lines[j].strip() != "" and not HEADER_RE.match(lines[j]):
                header_raw += " " + lines[j].strip()
                header_end = j
                if DATE_RE.search(header_raw) or DATE_RE_ALT.search(header_raw):
                    break
                j += 1

        if idx + 1 < len(header_indices):
            body_end = header_indices[idx + 1] - 1
        else:
            body_end = n - 1

        body_lines = lines[header_end + 1:body_end + 1]
        # Trim trailing blanks AND trailing proofread markers — the >>>>> line
        # lives between letters, not inside one. Anywhere else in the body
        # (rare) it's still handled below as a standalone paragraph.
        while body_lines and (body_lines[-1].strip() == "" or body_lines[-1].strip() == PROOFREAD_MARKER):
            body_lines.pop()

        paragraphs: list[str] = []
        current: list[str] = []
        for bl in body_lines:
            stripped = bl.strip()
            if stripped == "" or stripped == PROOFREAD_MARKER:
                if current:
                    paragraphs.append(join_paragraph_lines(current))
                    current = []
                if stripped == PROOFREAD_MARKER:
                    paragraphs.append(PROOFREAD_MARKER)
            else:
                current.append(bl)
        if current:
            paragraphs.append(join_paragraph_lines(current))

        body_data: list[dict] = []
        for p in paragraphs:
            stripped = p.strip()
            if stripped.startswith(OCR_NOTE_PREFIX):
                kind = "ocr_note"
            elif stripped == PROOFREAD_MARKER:
                kind = "proofread_marker"
            else:
                kind = "prose"
            entry = {"kind": kind, "text": p}
            if kind == "prose":
                parens = extract_parentheticals(p)
                if parens:
                    entry["parentheticals"] = parens
            body_data.append(entry)

        meta = extract_header_meta(header_raw, year)
        # Letter spans header through last non-blank, non->>>>> body line.
        letter_line_end = header_end + 1 + len(body_lines)
        entries.append(Entry(
            id=f"{year}-{letter_counter:04d}",
            type="letter",
            line_start=h + 1,
            line_end=letter_line_end,
            author=meta["author"],
            location=meta["location"],
            date=meta["date"],
            header_raw=header_raw,
            body=body_data,
        ))

    return entries


def verify(path: Path, year: int, entries: list[Entry]) -> list[str]:
    errors: list[str] = []
    raw = path.read_text(encoding="utf-8")
    header_count = sum(1 for line in raw.split("\n") if HEADER_RE.match(line))
    letter_count = sum(1 for e in entries if e.type == "letter")
    if header_count != letter_count:
        errors.append(
            f"Header count mismatch: {header_count} source headers, {letter_count} letters"
        )

    for e in entries:
        if e.type != "letter":
            continue
        iso = e.date["iso"] if e.date else None
        if iso is None:
            errors.append(f"{e.id}: unparseable date in {e.header_raw!r}")
            continue
        y = int(iso[:4])
        if y != year:
            errors.append(f"{e.id}: wrong year — {iso} in {year}.txt")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, help="single year (1939-1945)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    if args.year:
        years_to_process = [args.year]
    else:
        years_to_process = YEARS

    if not args.verify_only:
        OUT.mkdir(exist_ok=True)

    total_errors = 0
    grand_total_letters = 0
    for year in years_to_process:
        path = ROOT / f"kriegstagebuch-{year}.txt"
        if not path.exists():
            print(f"SKIP: {path} does not exist")
            continue
        entries = parse_file(path, year)
        errors = verify(path, year, entries)
        letters = sum(1 for e in entries if e.type == "letter")
        grand_total_letters += letters

        print(f"{year}: {letters:4d} letters, {len(errors)} issue(s)")
        for err in errors:
            print(f"  - {err}")
        total_errors += len(errors)

        if not args.verify_only:
            out_path = OUT / f"kriegstagebuch-{year}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {"source_file": path.name, "year": year,
                     "entries": [asdict(e) for e in entries]},
                    f, ensure_ascii=False, indent=2,
                )

    print(f"\nTotal: {grand_total_letters} letters across {len(years_to_process)} file(s), "
          f"{total_errors} issue(s)")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
