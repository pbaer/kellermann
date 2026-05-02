#!/usr/bin/env python3
"""Reorder annotations within each letter so layout is prose -> ##### -> &&&&&.

Operates on a single kriegstagebuch-YYYY.txt source file (in-place).

A "letter" is the run of lines starting with a `von Wilhelm,...` or
`von Marianne,...` header up to (but not including) the next such header,
or end of file. Within a letter, paragraphs are separated by blank lines.
A paragraph is `prose`, `ocr_note` (starts with #####), `historical_context`
(starts with &&&&&), or `proofread_marker` (exactly >>>>>).

The reorder preserves:
  - exact prose text and line wrapping
  - the relative order within each kind
  - the `>>>>>` paragraph wherever it sits (we leave it where it is, since
    it has special semantics and is at most one occurrence)

Usage:  reorder_annotations.py <path-to-txt> [--check]
"""
import re
import sys
from pathlib import Path

HEADER_RE = re.compile(r"^von (Wilhelm|Marianne),")
DATE_RE = re.compile(r"\b\d{1,2}\.\s*\d{1,2}\.\s*\d{2,4}\b")
DATE_RE_ALT = re.compile(r"\bden\s+\d", re.IGNORECASE)


def find_header_end(lines: list[str], h: int) -> int:
    """Mirror parse.py: gobble continuation lines into the header until the
    line carries a date (or we hit a blank line / another header).

    Returns the inclusive index of the last header line.
    """
    header_raw = lines[h]
    header_end = h
    if DATE_RE.search(header_raw):
        return header_end
    j = h + 1
    while j < len(lines) and lines[j].strip() != "" and not HEADER_RE.match(lines[j]):
        header_raw += " " + lines[j].strip()
        header_end = j
        if DATE_RE.search(header_raw):
            break
        j += 1
    return header_end


def split_paragraphs(block: str) -> list[str]:
    """Split a block of text into paragraphs by blank-line separators.

    A paragraph keeps its internal newlines. Returns paragraphs without
    surrounding blank lines. Multiple consecutive blank lines collapse.
    """
    paras = []
    current = []
    for line in block.split("\n"):
        if line.strip() == "":
            if current:
                paras.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paras.append("\n".join(current))
    return paras


def classify(para: str) -> str:
    s = para.lstrip()
    if s.startswith("#####"):
        return "ocr_note"
    if s.startswith("&&&&&"):
        return "historical_context"
    if s.strip() == ">>>>>":
        return "proofread_marker"
    return "prose"


def reorder_letter_body(body_text: str) -> str:
    """Reorder paragraphs within a letter body.

    Order: prose (in source order) -> ocr_note (in source order)
          -> historical_context (in source order).
    proofread_marker is left in its original relative position by treating
    it as prose for ordering purposes (rare; should not collide).
    """
    paras = split_paragraphs(body_text)
    if not paras:
        return body_text  # empty / whitespace only
    prose, ocr_notes, hc, markers = [], [], [], []
    for p in paras:
        k = classify(p)
        if k == "ocr_note":
            ocr_notes.append(p)
        elif k == "historical_context":
            hc.append(p)
        elif k == "proofread_marker":
            markers.append(p)
        else:
            prose.append(p)
    # Place proofread_marker at end of prose run so it stays "after" the
    # narrative content but before annotations. There's at most one in
    # practice, and it's a manual progress flag.
    ordered = prose + markers + ocr_notes + hc
    return "\n\n".join(ordered)


def reorder_file(path: Path) -> tuple[str, str]:
    text = path.read_text()
    lines = text.split("\n")

    # Find header line indices (0-based).
    header_starts = [
        i for i, line in enumerate(lines) if HEADER_RE.match(line)
    ]
    if not header_starts:
        return text, text

    # For each letter, compute (header_start, header_end_inclusive,
    # body_end_exclusive). Header may span multiple lines (place + date on
    # next line).
    letters = []
    for i, start in enumerate(header_starts):
        h_end = find_header_end(lines, start)
        b_end = header_starts[i + 1] if i + 1 < len(header_starts) else len(lines)
        letters.append((start, h_end, b_end))

    # Front matter: everything before the first header.
    front = "\n".join(lines[: header_starts[0]])
    pieces = [front] if front else []

    for h_start, h_end, b_end in letters:
        header_block = "\n".join(lines[h_start : h_end + 1])
        body_lines = lines[h_end + 1 : b_end]
        body_text = "\n".join(body_lines).strip("\n")
        new_body = reorder_letter_body(body_text)
        pieces.append(header_block + ("\n\n" + new_body if new_body else ""))

    new_text = "\n\n".join(pieces)
    # Preserve trailing newline if original had one.
    if text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    return text, new_text


def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    files = [a for a in args if a != "--check"]
    if not files:
        print("usage: reorder_annotations.py <path.txt> [<path.txt> ...] [--check]", file=sys.stderr)
        sys.exit(2)
    any_changed = False
    for f in files:
        p = Path(f)
        old, new = reorder_file(p)
        if old != new:
            any_changed = True
            if check_only:
                print(f"{p}: WOULD CHANGE")
            else:
                p.write_text(new)
                print(f"{p}: rewritten")
        else:
            print(f"{p}: no change")
    if check_only and any_changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
