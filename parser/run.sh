#!/usr/bin/env bash
# Re-parse the .txt files, refresh the PDF-page mapping, and start the
# proofreading server. Use after making changes that affect letter structure
# (e.g. splitting or merging letters in a kriegstagebuch-*.txt file).
set -euo pipefail

cd "$(dirname "$0")"
PY=".venv/bin/python"

echo "▶ parse.py"
"$PY" parse.py --all

echo
echo "▶ map_pdf.py"
"$PY" map_pdf.py

echo
echo "▶ build_chapter_letters.py"
"$PY" build_chapter_letters.py

echo
echo "▶ proofread.py"
exec "$PY" proofread.py
