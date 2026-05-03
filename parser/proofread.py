#!/usr/bin/env python3
"""Local HTML-based proofreading tool for kriegstagebuch letters.

Serves an editor UI at http://localhost:8765 where each letter's raw slice of
its source .txt can be edited against its scanned page image. Committing
writes back to the source .txt atomically and updates in-memory line numbers
for downstream letters.

Requires that parse.py (and optionally map_pdf.py and render_pages.py) has
already been run so that parser/out/kriegstagebuch-YYYY.json exists.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "sources" / "documents"
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
YEARS = list(range(1939, 1946))
PORT = 8765
PROOFREAD_MARKER = ">>>>>"
# PDF page dimensions in points (A4, same for every page in this PDF).
PAGE_WIDTH_PT = 595.2
PAGE_HEIGHT_PT = 841.92
# Total PDF pages available as rendered images under out/pages/.
PAGES_DIR = OUT / "pages"
PDF_PAGE_COUNT = len(list(PAGES_DIR.glob("page-*.png"))) if PAGES_DIR.exists() else 0


class State:
    def __init__(self) -> None:
        self.years: dict[int, dict] = {}
        for year in YEARS:
            jp = OUT / f"kriegstagebuch-{year}.json"
            tp = DOCS / f"kriegstagebuch-{year}.txt"
            if not (jp.exists() and tp.exists()):
                continue
            data = json.load(jp.open(encoding="utf-8"))
            text = tp.read_text(encoding="utf-8")
            trailing_nl = text.endswith("\n")
            lines = text.split("\n")
            # If file ends with \n, split produces empty final element. Drop it
            # so indices match line numbers; we'll re-add \n on write.
            if trailing_nl and lines and lines[-1] == "":
                lines.pop()
            self.years[year] = {
                "data": data,
                "lines": lines,
                "path": tp,
                "trailing_nl": trailing_nl,
            }

        # Flat list in source order
        self.letters: list[dict] = []
        for year in sorted(self.years):
            for e in self.years[year]["data"]["entries"]:
                if e["type"] == "letter":
                    e["year"] = year
                    self.letters.append(e)

        self.reconcile()

    # Keep these in sync with parse.py so reconciliation matches parsing.
    _HEADER_RE = re.compile(r"^von (Wilhelm|Marianne),")
    _DATE_RE = re.compile(r"den\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")
    _DATE_RE_ALT = re.compile(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b")

    def reconcile(self) -> None:
        """Re-derive line_start/line_end for all letters from the current .txt.

        Parse.py writes these to the per-year JSON, but the .txt file can move
        underneath (external edits, prior mark_as_proofread operations). This
        re-scans headers to keep line numbers truthful regardless.
        """
        for year, ys in self.years.items():
            lines = ys["lines"]
            header_indices = [i for i, line in enumerate(lines)
                              if self._HEADER_RE.match(line)]
            letter_entries = [e for e in ys["data"]["entries"]
                              if e["type"] == "letter"]
            if len(header_indices) != len(letter_entries):
                print(f"WARNING: {year}: {len(header_indices)} headers in .txt "
                      f"vs {len(letter_entries)} letters in JSON — skipping "
                      f"reconcile. Re-run parse.py.", file=sys.stderr)
                continue
            for idx, (h, entry) in enumerate(zip(header_indices, letter_entries)):
                header_raw = lines[h]
                header_end = h
                if not (self._DATE_RE.search(header_raw)
                        or self._DATE_RE_ALT.search(header_raw)):
                    j = h + 1
                    while (j < len(lines) and lines[j].strip() != ""
                           and not self._HEADER_RE.match(lines[j])):
                        header_raw += " " + lines[j].strip()
                        header_end = j
                        if (self._DATE_RE.search(header_raw)
                                or self._DATE_RE_ALT.search(header_raw)):
                            break
                        j += 1
                if idx + 1 < len(header_indices):
                    body_end = header_indices[idx + 1] - 1
                else:
                    body_end = len(lines) - 1
                body_range = lines[header_end + 1:body_end + 1]
                count = len(body_range)
                while count > 0 and (body_range[count - 1].strip() == ""
                                     or body_range[count - 1].strip() == PROOFREAD_MARKER):
                    count -= 1
                entry["line_start"] = h + 1
                entry["line_end"] = header_end + 1 + count

    def raw_text(self, year: int, line_start: int, line_end: int) -> str:
        lines = self.years[year]["lines"]
        return "\n".join(lines[line_start - 1 : line_end])

    def find_proofread_marker(self) -> tuple[int, int] | None:
        """Return (year, 1-indexed line) of the most recent >>>>> marker."""
        best: tuple[int, int] | None = None
        for year in sorted(self.years):
            for i, line in enumerate(self.years[year]["lines"]):
                if line.strip() == PROOFREAD_MARKER:
                    best = (year, i + 1)  # keep the LAST occurrence anywhere
        return best

    def proofread_boundary_idx(self) -> int:
        """Index into self.letters of the last proofread letter (or -1)."""
        marker = self.find_proofread_marker()
        if not marker:
            return -1
        mark_year, mark_line = marker
        # The proofread letter is the one whose body ends just before (or at)
        # the >>>>> line within mark_year.
        last_idx = -1
        for i, l in enumerate(self.letters):
            if l["year"] != mark_year:
                continue
            if l["line_start"] < mark_line:
                last_idx = i
            else:
                break
        return last_idx

    def letter_summary(self, l: dict, boundary_idx: int, my_idx: int,
                        bbox_status: dict) -> dict:
        status = bbox_status.get(l["id"], "none")
        return {
            "id": l["id"],
            "year": l["year"],
            "author": l["author"],
            "location": l["location"]["raw"] if l["location"] else None,
            "date_iso": l["date"]["iso"] if l["date"] else None,
            "date_raw": l["date"]["raw"] if l["date"] else None,
            "header": l["header_raw"],
            "proofread": my_idx <= boundary_idx,
            "is_next_to_proofread": my_idx == boundary_idx + 1,
            "bbox_status": status,  # "exact" | "approx" | "none"
        }

    def _bbox_status_map(self) -> dict[str, str]:
        mapping_path = OUT / "letter_pages.json"
        if not mapping_path.exists():
            return {}
        out: dict[str, str] = {}
        for rec in json.load(mapping_path.open(encoding="utf-8")):
            if not rec.get("bbox"):
                out[rec["letter_id"]] = "none"
            elif rec.get("bbox_approx"):
                out[rec["letter_id"]] = "approx"
            else:
                out[rec["letter_id"]] = "exact"
        return out

    def summaries(self) -> list[dict]:
        b = self.proofread_boundary_idx()
        bb = self._bbox_status_map()
        return [self.letter_summary(l, b, i, bb) for i, l in enumerate(self.letters)]

    def _write_year(self, year: int) -> None:
        ys = self.years[year]
        content = "\n".join(ys["lines"])
        if ys["trailing_nl"]:
            content += "\n"
        tmp = ys["path"].with_suffix(".txt.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, ys["path"])

    def save_letter(self, lid: str, new_text: str) -> bool:
        letter = next((l for l in self.letters if l["id"] == lid), None)
        if not letter:
            return False
        year = letter["year"]
        ys = self.years[year]
        line_start = letter["line_start"]
        line_end = letter["line_end"]
        new_lines = new_text.split("\n")
        orig_count = line_end - line_start + 1
        delta = len(new_lines) - orig_count

        ys["lines"] = ys["lines"][: line_start - 1] + new_lines + ys["lines"][line_end:]
        self._write_year(year)

        letter["line_end"] = line_start + len(new_lines) - 1
        if delta != 0:
            for e in ys["data"]["entries"]:
                if e is letter:
                    continue
                if e.get("line_start", 0) > line_start:
                    e["line_start"] += delta
                    e["line_end"] += delta
        return True

    def mark_as_proofread(self, lid: str) -> bool:
        """Move the >>>>> marker to separate the target letter from the next.

        The convention: >>>>> occupies the one-line separator slot between
        two consecutive letters, in place of the usual blank line. Moving the
        marker is therefore a pair of in-place swaps — no line insertions or
        deletions, so every letter's line_start/line_end stays valid.

        Allowed only when the target is the very next letter after the
        current proofread boundary.
        """
        target_idx = next((i for i, l in enumerate(self.letters) if l["id"] == lid), -1)
        if target_idx < 0:
            return False
        if target_idx != self.proofread_boundary_idx() + 1:
            return False
        target = self.letters[target_idx]

        affected_years: set[int] = set()

        # Step 1: demote the existing >>>>> back to a blank separator.
        current_marker = self.find_proofread_marker()
        if current_marker:
            mark_year, mark_line = current_marker
            self.years[mark_year]["lines"][mark_line - 1] = ""
            affected_years.add(mark_year)

        # Step 2: promote the blank separator between target and the next
        # letter to >>>>>. If the target is the last letter in the corpus,
        # there is no "next letter" — fall back to appending.
        target_year = target["year"]
        ys = self.years[target_year]
        lines = ys["lines"]
        sep_idx = target["line_end"]  # 0-indexed position of the line right after body
        if sep_idx < len(lines) and lines[sep_idx].strip() == "":
            lines[sep_idx] = PROOFREAD_MARKER
        else:
            # No blank separator (e.g. last letter in file, or convention
            # violation) — insert a new line and re-reconcile.
            lines.insert(sep_idx, PROOFREAD_MARKER)
            self.reconcile()
        affected_years.add(target_year)

        for y in affected_years:
            self._write_year(y)
        return True


STATE = State()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass

    def _send(self, body: bytes, content_type: str, status: int = 200, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status: int = 200) -> None:
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            html_path = HERE / "proofread.html"
            if not html_path.exists():
                self._send(b"proofread.html missing", "text/plain", 500)
                return
            self._send(html_path.read_bytes(), "text/html; charset=utf-8")
            return

        if path == "/proofread_shared.js":
            js_path = HERE / "proofread_shared.js"
            if not js_path.exists():
                self._send(b"proofread_shared.js missing", "text/plain", 500)
                return
            self._send(js_path.read_bytes(), "application/javascript; charset=utf-8")
            return

        if path == "/api/letters":
            self._send_json(STATE.summaries())
            return

        if path == "/api/search-index":
            idx = [{"id": l["id"],
                    "text": STATE.raw_text(l["year"], l["line_start"], l["line_end"])}
                   for l in STATE.letters]
            self._send_json(idx)
            return

        m = re.fullmatch(r"/api/letter/(\d{4}-\d{4})", path)
        if m:
            lid = m.group(1)
            letter = next((l for l in STATE.letters if l["id"] == lid), None)
            if not letter:
                self._send_json({"error": "not found"}, 404)
                return
            idx = STATE.letters.index(letter)
            b = STATE.proofread_boundary_idx()
            # Look up bbox from letter_pages.json cache if present.
            bbox = None
            bbox_approx = False
            mapping_path = OUT / "letter_pages.json"
            if mapping_path.exists():
                mapping = json.load(mapping_path.open(encoding="utf-8"))
                rec = next((r for r in mapping if r["letter_id"] == lid), None)
                if rec:
                    bbox = rec.get("bbox")
                    bbox_approx = bool(rec.get("bbox_approx"))
            self._send_json({
                "id": letter["id"],
                "year": letter["year"],
                "author": letter["author"],
                "location": letter["location"],
                "date": letter["date"],
                "header": letter["header_raw"],
                "raw_text": STATE.raw_text(letter["year"], letter["line_start"], letter["line_end"]),
                "line_start": letter["line_start"],
                "line_end": letter["line_end"],
                "pdf_page": letter.get("pdf_page"),
                "pdf_page_range": letter.get("pdf_page_range"),
                "bbox": bbox,
                "bbox_approx": bbox_approx,
                "page_dims": [PAGE_WIDTH_PT, PAGE_HEIGHT_PT],
                "pdf_page_count": PDF_PAGE_COUNT,
                "proofread": idx <= b,
                "is_next_to_proofread": idx == b + 1,
            })
            return

        m = re.fullmatch(r"/page/(\d+)\.png", path)
        if m:
            n = int(m.group(1))
            width = 3  # page-NNN.png
            p = OUT / "pages" / f"page-{n:0{width}d}.png"
            if not p.exists():
                self._send(b"not found", "text/plain", 404)
                return
            body = p.read_bytes()
            self._send(body, "image/png",
                       extra={"Cache-Control": "public, max-age=3600"})
            return

        self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        m = re.fullmatch(r"/api/letter/(\d{4}-\d{4})", path)
        if m:
            lid = m.group(1)
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self._send_json({"error": "bad json"}, 400)
                return
            new_text = data.get("text")
            if not isinstance(new_text, str):
                self._send_json({"error": "missing text"}, 400)
                return
            if not STATE.save_letter(lid, new_text):
                self._send_json({"error": "save failed"}, 400)
                return
            self._send_json({"ok": True, "letters": STATE.summaries()})
            return

        m = re.fullmatch(r"/api/mark-proofread/(\d{4}-\d{4})", path)
        if m:
            lid = m.group(1)
            if not STATE.mark_as_proofread(lid):
                self._send_json({"error": "not the next letter after the current proofread boundary"}, 400)
                return
            self._send_json({"ok": True, "letters": STATE.summaries()})
            return

        self._send_json({"error": "not found"}, 404)


def main() -> int:
    if not STATE.letters:
        print("No letters loaded. Did you run parse.py first?", file=sys.stderr)
        return 1
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Proofreader serving at http://localhost:{PORT}  ({len(STATE.letters)} letters)")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
