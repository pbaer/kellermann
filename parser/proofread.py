#!/usr/bin/env python3
"""Combined local proofreading tool: kriegstagebuch letters + audio transcript.

Serves a single page at http://localhost:8770 with a toggle between the two
proofreading experiences. Each experience runs in its own <iframe>, so its
full state — editor contents (including uncommitted edits), nav selection,
scroll position, audio playback position, map pan/zoom and search query — is
preserved while switching between modes. You can leave uncommitted changes in
one tool, flip to the other to check something, and flip back untouched.

Rather than reimplement either tool, this module imports proofread_letters.py
and proofread_audio.py and reuses their State + request handlers verbatim:

    /                       -> proofread.html          (the shell)
    /tool/letters           -> proofread_letters.html  (letters tool, in an iframe)
    /tool/audio             -> proofread_audio.html     (audio tool, in an iframe)
    /api/letters/...        -> letters State  (proofread_letters.py)
    /page/<n>.png           -> letters page scans
    /api/blocks, /api/block -> audio State    (proofread_audio.py)
    /audio/..., /maps/...   -> audio clips / map images

Run parse.py (and map_pdf.py / render_pages.py) first so the letters JSON and
page images exist; the audio side needs sources/audio/transcript.txt.
"""
from __future__ import annotations

import re
import sys
import threading
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path

import proofread_letters as letters_mod
import proofread_audio as audio_mod

HERE = Path(__file__).resolve().parent
PORT = 8770

# The letters State (proofread_letters.py) was written for a single-threaded server and
# mutates line numbers in place on save. We now serve on a threading server
# (audio streaming would otherwise block every other request), so serialize all
# letters reads/writes through one lock. The audio State has its own lock.
LETTERS_LOCK = threading.Lock()


class Handler(audio_mod.Handler):
    """Routes the shell + both tools' APIs.

    Subclasses the audio handler to inherit its _send / _send_json / _send_audio
    helpers and its do_GET/do_POST for the audio endpoints. Letters endpoints are
    delegated to proofread_letters.Handler's methods (called with this instance,
    since it is a BaseHTTPRequestHandler with the same helper surface).
    """

    def _send_file(self, name: str, ctype: str) -> None:
        p = HERE / name
        if not p.exists():
            self._send(f"{name} missing".encode("utf-8"), "text/plain", 500)
            return
        self._send(p.read_bytes(), ctype)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            self._send_file("proofread.html", "text/html; charset=utf-8")
            return
        if path == "/tool/letters":
            self._send_file("proofread_letters.html", "text/html; charset=utf-8")
            return
        if path == "/tool/audio":
            self._send_file("proofread_audio.html", "text/html; charset=utf-8")
            return
        if path == "/proofread_shared.js":
            self._send_file("proofread_shared.js", "application/javascript; charset=utf-8")
            return

        # Letters-owned GET routes -> proofread_letters.Handler.do_GET. (The two tools
        # shared a /api/search-index route name; each now namespaces its own as
        # /api/{letters,audio}/search-index, so the combined server can route by
        # path.)
        if (path == "/api/letters" or path == "/api/letters/search-index"
                or path.startswith("/api/letter/")
                or re.fullmatch(r"/page/\d+\.png", path)):
            with LETTERS_LOCK:
                return letters_mod.Handler.do_GET(self)

        # Everything else (audio search-index, blocks/clips/maps, plus the 404
        # fallback) is handled by the audio tool.
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        # Letters-owned POSTs: save a letter, or advance the letters marker
        # (letter ids are YYYY-NNNN; audio block ids are NNNN, so the dashed
        # mark-proofread pattern disambiguates from the audio one).
        if (path.startswith("/api/letter/")
                or re.fullmatch(r"/api/mark-proofread/\d{4}-\d{4}", path)):
            with LETTERS_LOCK:
                return letters_mod.Handler.do_POST(self)

        return super().do_POST()


def main() -> int:
    if not letters_mod.STATE.letters:
        print("No letters loaded. Did you run parse.py first?", file=sys.stderr)
        return 1
    if not audio_mod.STATE.blocks:
        print("No transcript blocks parsed.", file=sys.stderr)
        return 1
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"Combined proofreader serving at http://localhost:{PORT}  "
          f"({len(letters_mod.STATE.letters)} letters · "
          f"{len(audio_mod.STATE.blocks)} audio blocks)")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
