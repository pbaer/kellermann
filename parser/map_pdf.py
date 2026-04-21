#!/usr/bin/env python3
"""OCR each page of kriegstagebuch.pdf, then map each letter to its page.

Primary alignment is a monotone walk over OCR date candidates: for each letter
we look for an OCR line whose day+month digits match the letter's date, pick
the author-compatible one with the best header similarity, and advance a
cursor. Year is ignored because OCR on year digits is routinely garbled.

Letters the primary pass misses still get a page attribution via two fallback
passes:

  * Fuzzy-line match — scans OCR lines on the pages we already narrowed the
    letter down to, and fuzzy-matches their text to the letter's header. This
    catches cases like "den 25. x 1939" where the month digit failed to OCR.
  * Bbox interpolation — when a letter sits between two matched letters on the
    same page, we estimate its bbox vertically between their bboxes. Those
    get flagged `bbox_approx: true` so the UI can distinguish them.

Output:
  parser/out/ocr.jsonl         — one page per line, list of {text, bbox}
  parser/out/letter_pages.json — [{letter_id, header, pdf_page, content_page,
                                   ocr_snippet, bbox, bbox_approx, page_range}]
"""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
PDF = ROOT / "kriegstagebuch.pdf"
OCR_CACHE = OUT / "ocr.jsonl"
MAPPING = OUT / "letter_pages.json"
YEARS = range(1939, 1946)

# Exact date pattern: day, month, year all digits, with . or , separators.
DATE_LOOSE = re.compile(r"\b(\d{1,2})[.,]\s*(\d{1,2})[.,]\s*(\d{2,4})\b")

# Header-ish prefix on an OCR line — "von", "yon", "vor", "vorn", ...
VON_PREFIX = re.compile(r"\b(?:von|yon|vorn|vor|yor|van|yan)\b", re.IGNORECASE)


def ocr_all_pages() -> list[list[dict]]:
    if OCR_CACHE.exists():
        print(f"Loading cached OCR from {OCR_CACHE}")
        return [json.loads(line) for line in OCR_CACHE.open("r", encoding="utf-8")]

    print("Running OCR on all pages (takes a few minutes)...")
    doc = pymupdf.open(PDF)
    pages: list[list[dict]] = []
    with OCR_CACHE.open("w", encoding="utf-8") as f:
        for i in range(doc.page_count):
            page = doc[i]
            tp = page.get_textpage_ocr(language="deu", dpi=200)
            raw = page.get_text("dict", textpage=tp)
            lines_out: list[dict] = []
            for block in raw.get("blocks", []):
                for ln in block.get("lines", []):
                    text = "".join(s.get("text", "") for s in ln.get("spans", []))
                    if not text.strip():
                        continue
                    lines_out.append({"text": text, "bbox": list(ln.get("bbox", [0, 0, 0, 0]))})
            pages.append(lines_out)
            f.write(json.dumps(lines_out, ensure_ascii=False) + "\n")
            if (i + 1) % 10 == 0 or i == doc.page_count - 1:
                print(f"  OCR {i + 1}/{doc.page_count}")
    return pages


def build_date_candidates(pages: list[list[dict]]) -> list[dict]:
    """Flat list of date-like OCR hits across all pages, in PDF order."""
    out: list[dict] = []
    for pidx, lines in enumerate(pages):
        for li, ln in enumerate(lines):
            for m in DATE_LOOSE.finditer(ln["text"]):
                try:
                    out.append({
                        "pdf_page": pidx + 1,
                        "line_idx": li,
                        "day": int(m.group(1)),
                        "month": int(m.group(2)),
                        "year_raw": m.group(3),
                        "text": ln["text"],
                        "bbox": ln["bbox"],
                    })
                except ValueError:
                    pass
    return out


def is_author_compatible(ocr_text: str, author: str) -> bool:
    """Permissive check: the OCR line's author-position word looks like the target."""
    t = ocr_text.lower()
    m = re.search(r"\b(?:von|yon|vorn|vor|yor)\s+(\w{2,})", t)
    if not m:
        return True  # no anchor → don't reject
    first = m.group(1)
    if author == "Wilhelm":
        return first[0] in "wv" or "ilh" in first or "ilb" in first
    if author == "Marianne":
        return first[0] in "mnb" or "ari" in first or "mar" in first
    return True


def fuzzy_match_on_pages(letter: dict, pages: list[list[dict]],
                         page_range: tuple[int, int], claimed: set[tuple[int, int]]
                         ) -> dict | None:
    """Find the best OCR line on pages[page_range[0]-1 .. page_range[1]-1]
    that looks like this letter's header. Used as a fallback when the date
    regex missed the header entirely.

    Returns {pdf_page, line_idx, bbox, text, score} or None.
    Won't return a line that's already been claimed by an exact match.
    """
    header_lower = letter["header_raw"].lower()
    iso = letter["date"]["iso"] if letter["date"] else None
    target_d = int(iso.split("-")[2]) if iso else None

    best = None
    for page_num in range(page_range[0], page_range[1] + 1):
        pidx = page_num - 1
        if pidx < 0 or pidx >= len(pages):
            continue
        for li, ln in enumerate(pages[pidx]):
            if (pidx, li) in claimed:
                continue
            text = ln["text"]
            text_lower = text.lower()
            # Require some header-ish signal: either "von"-like prefix OR the
            # day number present, so we don't drift onto body lines.
            has_von = bool(VON_PREFIX.search(text))
            has_day = False
            if target_d is not None:
                has_day = bool(
                    re.search(rf"(?<!\d){target_d}(?!\d)", text)
                    or re.search(rf"(?<!\d){target_d:02d}(?!\d)", text)
                )
            if not (has_von or has_day):
                continue
            if not is_author_compatible(text, letter["author"]):
                continue
            score = SequenceMatcher(None, header_lower, text_lower).ratio()
            if has_von and has_day:
                score += 0.15
            elif has_von:
                score += 0.05
            if best is None or score > best["score"]:
                best = {
                    "pdf_page": page_num,
                    "line_idx": li,
                    "bbox": ln["bbox"],
                    "text": text,
                    "score": score,
                }
    if best and best["score"] >= 0.35:
        return best
    return None


def interpolate_bbox(results: list[dict], idx: int) -> dict | None:
    """For an unmatched letter known to be on a specific page, estimate its
    bbox from same-page matched neighbors. Returns the new fields to merge,
    or None if we can't make a useful guess.
    """
    r = results[idx]
    page = r.get("pdf_page")
    if page is None:
        pr = r.get("page_range") or []
        if len(pr) == 2 and pr[0] == pr[1]:
            page = pr[0]
    if page is None:
        return None

    def letter_page(other: dict) -> int | None:
        if other.get("pdf_page"):
            return other["pdf_page"]
        pr = other.get("page_range") or []
        if len(pr) == 2 and pr[0] == pr[1]:
            return pr[0]
        return None

    # Walk outward; stop as soon as we cross off the page.
    prev_idx = None
    prev_bbox = None
    for j in range(idx - 1, -1, -1):
        pg = letter_page(results[j])
        if pg is not None and pg != page:
            break
        if results[j].get("bbox"):
            prev_idx = j
            prev_bbox = results[j]["bbox"]
            break

    next_idx = None
    next_bbox = None
    for j in range(idx + 1, len(results)):
        pg = letter_page(results[j])
        if pg is not None and pg != page:
            break
        if results[j].get("bbox"):
            next_idx = j
            next_bbox = results[j]["bbox"]
            break

    if prev_bbox and next_bbox:
        gap = [k for k in range(prev_idx + 1, next_idx) if not results[k].get("bbox")]
        if idx not in gap:
            return None
        pos = gap.index(idx) + 1
        total = len(gap) + 1
        py1 = prev_bbox[3]
        ny0 = next_bbox[1]
        header_h = max(prev_bbox[3] - prev_bbox[1], next_bbox[3] - next_bbox[1], 18.0)
        frac = pos / total
        center_y = py1 + frac * (ny0 - py1)
        return {
            "pdf_page": page,
            "bbox": [min(prev_bbox[0], next_bbox[0]),
                     center_y - header_h / 2,
                     max(prev_bbox[2], next_bbox[2]),
                     center_y + header_h / 2],
            "bbox_approx": True,
        }
    if prev_bbox:
        header_h = max(prev_bbox[3] - prev_bbox[1], 18.0)
        spacing = header_h * 3
        return {
            "pdf_page": page,
            "bbox": [prev_bbox[0],
                     prev_bbox[3] + spacing,
                     prev_bbox[2],
                     prev_bbox[3] + spacing + header_h],
            "bbox_approx": True,
        }
    if next_bbox:
        header_h = max(next_bbox[3] - next_bbox[1], 18.0)
        spacing = header_h * 3
        top = next_bbox[1] - spacing - header_h
        return {
            "pdf_page": page,
            "bbox": [next_bbox[0], top, next_bbox[2], top + header_h],
            "bbox_approx": True,
        }
    return None


def main() -> int:
    OUT.mkdir(exist_ok=True)
    pages = ocr_all_pages()
    candidates = build_date_candidates(pages)
    print(f"OCR done: {len(pages)} pages, {len(candidates)} date candidates")

    letters: list[dict] = []
    for year in YEARS:
        jp = OUT / f"kriegstagebuch-{year}.json"
        if not jp.exists():
            continue
        d = json.load(jp.open())
        for e in d["entries"]:
            if e["type"] == "letter":
                letters.append(e)
    print(f"Loaded {len(letters)} letters")

    results: list[dict] = []
    cursor = 0  # index into candidates
    # Lines already claimed by a primary match — keep fuzzy pass from stealing
    # them.
    claimed_lines: set[tuple[int, int]] = set()

    # ---- Pass 1: exact day+month match (monotone cursor walk). ----
    for letter in letters:
        iso = letter["date"]["iso"] if letter["date"] else None
        if not iso:
            results.append({
                "letter_id": letter["id"],
                "header": letter["header_raw"],
                "pdf_page": None,
                "content_page": None,
                "reason": "letter has no ISO date",
            })
            continue

        _, target_m, target_d = map(int, iso.split("-"))

        cand_matching = [i for i in range(cursor, min(cursor + 20, len(candidates)))
                         if candidates[i]["day"] == target_d
                         and candidates[i]["month"] == target_m]

        filtered = [i for i in cand_matching
                    if is_author_compatible(candidates[i]["text"], letter["author"])]
        pool = filtered if filtered else cand_matching

        best = None
        if pool:
            if len(pool) == 1:
                best = pool[0]
            else:
                header_norm = letter["header_raw"].lower()
                best = max(pool, key=lambda i: SequenceMatcher(
                    None, header_norm, candidates[i]["text"].lower()).ratio())

        if best is not None and not filtered:
            if not is_author_compatible(candidates[best]["text"], letter["author"]):
                best = None

        if best is None:
            results.append({
                "letter_id": letter["id"],
                "header": letter["header_raw"],
                "pdf_page": None,
                "content_page": None,
            })
            continue

        c = candidates[best]
        claimed_lines.add((c["pdf_page"] - 1, c["line_idx"]))
        results.append({
            "letter_id": letter["id"],
            "header": letter["header_raw"],
            "pdf_page": c["pdf_page"],
            "content_page": c["pdf_page"] - 1,
            "ocr_snippet": c["text"],
            "bbox": c["bbox"],
            "match_type": "exact",
        })
        cursor = best + 1

    exact_count = sum(1 for r in results if r.get("match_type") == "exact")

    # ---- Pass 2: interpolate a provisional page_range for unmatched
    # letters. Since PDF order tracks .txt order, each sits between its
    # matched neighbors.
    for i, r in enumerate(results):
        if r.get("pdf_page") is not None:
            continue
        prev_p = next((results[j]["pdf_page"] for j in range(i - 1, -1, -1)
                       if results[j].get("pdf_page") is not None), None)
        next_p = next((results[j]["pdf_page"] for j in range(i + 1, len(results))
                       if results[j].get("pdf_page") is not None), None)
        if prev_p is not None and next_p is not None:
            r["page_range"] = [prev_p, next_p]
        elif prev_p is not None:
            r["page_range"] = [prev_p, prev_p + 2]
        elif next_p is not None:
            r["page_range"] = [max(1, next_p - 2), next_p]

    # ---- Pass 3: fuzzy line-match fallback for unmatched letters. Walk in
    # order with a running floor-page so monotonicity stays intact when an
    # earlier fuzzy match bumps a later letter's start page forward.
    fuzzy_count = 0
    letter_by_idx = {i: l for i, l in enumerate(letters)}
    floor_page = 0  # minimum page any further letter may live on
    for i, r in enumerate(results):
        if r.get("pdf_page") is not None:
            floor_page = max(floor_page, r["pdf_page"])
            continue
        pr = r.get("page_range")
        if not pr:
            continue
        start = max(pr[0], floor_page)
        # Look ahead for the next letter with a pinned page; we can't overshoot it.
        next_pinned = next((results[j]["pdf_page"] for j in range(i + 1, len(results))
                            if results[j].get("pdf_page") is not None), None)
        end = pr[1] if next_pinned is None else min(pr[1], next_pinned)
        if start > end:
            continue
        letter = letter_by_idx[i]
        if not letter.get("date") or not letter["date"].get("iso"):
            continue
        fm = fuzzy_match_on_pages(letter, pages, (start, end), claimed_lines)
        if fm is None:
            continue
        claimed_lines.add((fm["pdf_page"] - 1, fm["line_idx"]))
        r["pdf_page"] = fm["pdf_page"]
        r["content_page"] = fm["pdf_page"] - 1
        r["bbox"] = fm["bbox"]
        r["ocr_snippet"] = fm["text"]
        r["match_type"] = "fuzzy"
        r.pop("page_range", None)
        fuzzy_count += 1
        floor_page = fm["pdf_page"]

    # Rebuild page_range for letters still without a page.
    for i, r in enumerate(results):
        if r.get("pdf_page") is not None:
            continue
        prev_p = next((results[j]["pdf_page"] for j in range(i - 1, -1, -1)
                       if results[j].get("pdf_page") is not None), None)
        next_p = next((results[j]["pdf_page"] for j in range(i + 1, len(results))
                       if results[j].get("pdf_page") is not None), None)
        if prev_p is not None and next_p is not None:
            r["page_range"] = [prev_p, next_p]
        elif prev_p is not None:
            r["page_range"] = [prev_p, prev_p + 2]
        elif next_p is not None:
            r["page_range"] = [max(1, next_p - 2), next_p]
        else:
            r.pop("page_range", None)

    # ---- Pass 4: interpolate bbox for letters that know their page but
    # have no bbox yet. Uses same-page matched neighbors.
    interp_count = 0
    for i, r in enumerate(results):
        if r.get("bbox"):
            continue
        est = interpolate_bbox(results, i)
        if est is None:
            continue
        r.update(est)
        r["content_page"] = est["pdf_page"] - 1
        r["match_type"] = r.get("match_type") or "interpolated"
        interp_count += 1

    # Drop page_range on letters that now have a specific page — keeps the
    # downstream consumer simple (one of pdf_page, page_range).
    for r in results:
        if r.get("pdf_page"):
            r.pop("page_range", None)

    # ---- Write output ----
    with MAPPING.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Merge page / bbox info back into the per-year letter JSON for downstream
    # tools that don't want to join against letter_pages.json.
    results_by_id = {r["letter_id"]: r for r in results}
    for year in YEARS:
        jp = OUT / f"kriegstagebuch-{year}.json"
        if not jp.exists():
            continue
        d = json.load(jp.open(encoding="utf-8"))
        for e in d["entries"]:
            if e["type"] != "letter":
                continue
            r = results_by_id.get(e["id"])
            if not r:
                continue
            # Reset these so stale values don't linger.
            for k in ("pdf_page", "pdf_page_range"):
                e.pop(k, None)
            if r.get("pdf_page"):
                e["pdf_page"] = r["pdf_page"]
            elif r.get("page_range"):
                e["pdf_page_range"] = r["page_range"]
        with jp.open("w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

    total = len(results)
    with_bbox = sum(1 for r in results if r.get("bbox"))
    with_exact_bbox = sum(1 for r in results if r.get("bbox") and not r.get("bbox_approx"))
    with_approx_bbox = sum(1 for r in results if r.get("bbox_approx"))
    with_page_only = sum(1 for r in results if r.get("pdf_page") and not r.get("bbox"))
    with_range = sum(1 for r in results if r.get("page_range"))

    print(f"Wrote mapping to {MAPPING}")
    print(f"Merged page info into per-year JSON files")
    print(f"Primary exact match:       {exact_count}/{total}")
    print(f"  + fuzzy-line fallback:   +{fuzzy_count}")
    print(f"  + bbox interpolation:    +{interp_count}")
    print(f"Total with bbox:           {with_bbox}/{total}  "
          f"(exact {with_exact_bbox} + approx {with_approx_bbox})")
    print(f"Page-only (no bbox):       {with_page_only}")
    print(f"Page range only:           {with_range}")

    ranges = [(r["page_range"][1] - r["page_range"][0] + 1)
              for r in results if r.get("page_range")]
    if ranges:
        from collections import Counter
        c = Counter(ranges)
        print(f"Page range widths:         {dict(sorted(c.items()))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
