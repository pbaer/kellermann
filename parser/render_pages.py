#!/usr/bin/env python3
"""Render each page of sources/documents/kriegstagebuch.pdf to a PNG.

Output: parser/out/pages/page-001.png … page-NNN.png
Page 1 is the cover; page N (N>=2) corresponds to typewriter page N-1.
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "sources" / "documents" / "kriegstagebuch.pdf"
OUT = Path(__file__).resolve().parent / "out" / "pages"
DPI = 200


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(PDF)
    n = doc.page_count
    width = len(str(n))
    for i in range(n):
        page = doc[i]
        pix = page.get_pixmap(dpi=DPI)
        out_path = OUT / f"page-{i + 1:0{width}d}.png"
        pix.save(out_path)
        if (i + 1) % 20 == 0 or i == n - 1:
            print(f"  rendered {i + 1}/{n}")
    print(f"Wrote {n} pages to {OUT}")


if __name__ == "__main__":
    main()
