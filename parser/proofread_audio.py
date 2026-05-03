#!/usr/bin/env python3
"""Local HTML-based proof-listening tool for the audio interview transcript.

Serves an editor UI at http://localhost:8766 where each timestamped block of
transcript text can be edited while playing back the corresponding audio
from its starting timestamp. Committing writes back to
sources/audio/transcript.txt atomically.

Mirrors the conventions of proofread.py for the kriegstagebuch letters:
the >>>>> marker occupies the blank-separator slot between two consecutive
blocks, and "Mark as proofread" advances it past the current block.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = ROOT / "sources" / "audio"
TRANSCRIPT = AUDIO_ROOT / "transcript.txt"
HERE = Path(__file__).resolve().parent
PORT = 8766
PROOFREAD_MARKER = ">>>>>"

CLIP_HEADER_RE = re.compile(r"^===\s+(.+?)\s+===\s*$")
TIMESTAMP_RE = re.compile(r"^\[(\d+):(\d{2})(?::(\d{2}))?\]")
SPEAKER_RE = re.compile(r"\[(Wilhelm|Tilman)\]")


def parse_timestamp(line: str) -> int | None:
    """Return start time in seconds for a `[m:ss]` or `[h:mm:ss]` prefix."""
    m = TIMESTAMP_RE.match(line)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is None:
        return int(a) * 60 + int(b)
    return int(a) * 3600 + int(b) * 60 + int(c)


class State:
    def __init__(self) -> None:
        if not TRANSCRIPT.exists():
            raise FileNotFoundError(f"{TRANSCRIPT} not found")
        text = TRANSCRIPT.read_text(encoding="utf-8")
        self.trailing_nl = text.endswith("\n")
        lines = text.split("\n")
        if self.trailing_nl and lines and lines[-1] == "":
            lines.pop()
        self.lines: list[str] = lines
        self.path = TRANSCRIPT
        self.blocks: list[dict] = []
        self.parse()

    def parse(self) -> None:
        """Walk self.lines and rebuild self.blocks.

        A block is a paragraph (run of non-blank, non-marker lines) that lives
        under a clip header (=== ... ===). Clip headers and blank/marker lines
        themselves are skipped — they are not blocks.
        """
        self.blocks = []
        current_clip: str | None = None
        i = 0
        n = len(self.lines)
        while i < n:
            stripped = self.lines[i].strip()
            m = CLIP_HEADER_RE.match(self.lines[i])
            if m:
                current_clip = m.group(1)
                i += 1
                continue
            if stripped == "" or stripped == PROOFREAD_MARKER:
                i += 1
                continue
            block_start = i
            while i < n:
                s = self.lines[i].strip()
                if s == "" or s == PROOFREAD_MARKER:
                    break
                if CLIP_HEADER_RE.match(self.lines[i]):
                    break
                i += 1
            block_end = i - 1  # inclusive
            first = self.lines[block_start]
            start_seconds = parse_timestamp(first)
            preview = self._make_preview(self.lines[block_start:block_end + 1])
            speakers = sorted({m.group(1) for line in self.lines[block_start:block_end + 1]
                               for m in SPEAKER_RE.finditer(line)})
            block_id = f"{len(self.blocks):04d}"
            self.blocks.append({
                "id": block_id,
                "clip": current_clip,
                "start_seconds": start_seconds,
                "speakers": speakers,
                "preview": preview,
                "line_start": block_start + 1,
                "line_end": block_end + 1,
            })

    @staticmethod
    def _make_preview(block_lines: list[str], maxlen: int = 70) -> str:
        # Strip leading [m:ss] and any [Speaker] tags for a compact preview.
        joined = " ".join(line.strip() for line in block_lines if line.strip())
        joined = TIMESTAMP_RE.sub("", joined).strip()
        joined = SPEAKER_RE.sub("", joined).strip()
        joined = re.sub(r"\s+", " ", joined)
        if len(joined) > maxlen:
            joined = joined[:maxlen - 1].rstrip() + "…"
        return joined

    def find_proofread_marker(self) -> int | None:
        """Return 1-indexed line of the marker, or None."""
        last = None
        for i, line in enumerate(self.lines):
            if line.strip() == PROOFREAD_MARKER:
                last = i + 1
        return last

    def proofread_boundary_idx(self) -> int:
        marker = self.find_proofread_marker()
        if marker is None:
            return -1
        last_idx = -1
        for i, b in enumerate(self.blocks):
            if b["line_end"] < marker:
                last_idx = i
            else:
                break
        return last_idx

    def raw_text(self, line_start: int, line_end: int) -> str:
        return "\n".join(self.lines[line_start - 1: line_end])

    def block_summary(self, b: dict, idx: int, boundary_idx: int) -> dict:
        return {
            "id": b["id"],
            "clip": b["clip"],
            "start_seconds": b["start_seconds"],
            "speakers": b["speakers"],
            "preview": b["preview"],
            "proofread": idx <= boundary_idx,
            "is_next_to_proofread": idx == boundary_idx + 1,
        }

    def summaries(self) -> list[dict]:
        b = self.proofread_boundary_idx()
        return [self.block_summary(blk, i, b) for i, blk in enumerate(self.blocks)]

    def _write(self) -> None:
        content = "\n".join(self.lines)
        if self.trailing_nl:
            content += "\n"
        tmp = self.path.with_suffix(".txt.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, self.path)

    def save_block(self, bid: str, new_text: str) -> bool:
        block = next((b for b in self.blocks if b["id"] == bid), None)
        if not block:
            return False
        line_start = block["line_start"]
        line_end = block["line_end"]
        new_lines = new_text.split("\n")
        # Strip trailing empty lines from the edited body so the user can't
        # accidentally inject blank-line block separators inside a block.
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()
        if not new_lines:
            return False
        self.lines = self.lines[: line_start - 1] + new_lines + self.lines[line_end:]
        self._write()
        self.parse()
        return True

    def mark_as_proofread(self, bid: str) -> bool:
        target_idx = next((i for i, b in enumerate(self.blocks) if b["id"] == bid), -1)
        if target_idx < 0:
            return False
        if target_idx != self.proofread_boundary_idx() + 1:
            return False
        target = self.blocks[target_idx]

        # Demote existing marker, if any, back to a blank line.
        cur = self.find_proofread_marker()
        if cur is not None:
            self.lines[cur - 1] = ""

        # Promote the first blank line right after the target's body to >>>>>.
        # If the next non-blank thing is a clip header, the blank slot still
        # exists between the body and the header; the marker goes there.
        sep_idx = target["line_end"]  # 0-indexed line right after the body
        if sep_idx < len(self.lines) and self.lines[sep_idx].strip() == "":
            self.lines[sep_idx] = PROOFREAD_MARKER
        else:
            # End of file or convention violation — append a marker line.
            self.lines.insert(sep_idx, PROOFREAD_MARKER)

        self._write()
        self.parse()
        return True


STATE = State()
STATE_LOCK = threading.Lock()


def safe_audio_path(rel: str) -> Path | None:
    """Resolve `rel` against AUDIO_ROOT, refusing path traversal."""
    try:
        candidate = (AUDIO_ROOT / rel).resolve()
        candidate.relative_to(AUDIO_ROOT.resolve())
    except (ValueError, OSError):
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass

    def _send(self, body: bytes, content_type: str, status: int = 200,
              extra: dict | None = None) -> None:
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

    def _send_audio(self, p: Path) -> None:
        # Honor Range requests so the browser can seek without re-downloading.
        # Browsers routinely close <audio> Range connections early — after
        # probing metadata, after seeking past the buffered window, or when
        # the user navigates away mid-load. The next write() then raises
        # ECONNRESET / EPIPE. There's no body left to deliver, no recovery to
        # do; swallow just those specific exceptions so the rest of the
        # tool's error reporting stays unsuppressed.
        size = p.stat().st_size
        rng = self.headers.get("Range")
        ext = p.suffix.lower()
        ctype = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
        }.get(ext, "application/octet-stream")
        try:
            if rng and rng.startswith("bytes="):
                try:
                    spec = rng[len("bytes="):]
                    start_s, end_s = spec.split("-", 1)
                    start = int(start_s) if start_s else 0
                    end = int(end_s) if end_s else size - 1
                    end = min(end, size - 1)
                    if start > end or start >= size:
                        raise ValueError
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                length = end - start + 1
                with p.open("rb") as f:
                    f.seek(start)
                    body = f.read(length)
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                self.wfile.write(body)
                return
            # Full-body response. Stream from disk so a browser that aborts
            # after reading metadata doesn't force us to buffer the whole
            # file in RAM.
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            with p.open("rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            return

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            html_path = HERE / "proofread_audio.html"
            if not html_path.exists():
                self._send(b"proofread_audio.html missing", "text/plain", 500)
                return
            self._send(html_path.read_bytes(), "text/html; charset=utf-8")
            return

        if path == "/proofread_shared.js":
            js_path = HERE / "proofread_shared.js"
            if not js_path.exists():
                self._send(b"proofread_shared.js missing", "text/plain", 500)
                return
            self._send(js_path.read_bytes(),
                       "application/javascript; charset=utf-8")
            return

        if path == "/api/blocks":
            with STATE_LOCK:
                summaries = STATE.summaries()
            self._send_json(summaries)
            return

        if path == "/api/search-index":
            with STATE_LOCK:
                idx = [{"id": b["id"],
                        "text": STATE.raw_text(b["line_start"], b["line_end"])}
                       for b in STATE.blocks]
            self._send_json(idx)
            return

        m = re.fullmatch(r"/api/block/(\d{4})", path)
        if m:
            bid = m.group(1)
            with STATE_LOCK:
                block = next((b for b in STATE.blocks if b["id"] == bid), None)
                if not block:
                    self._send_json({"error": "not found"}, 404)
                    return
                idx = STATE.blocks.index(block)
                boundary = STATE.proofread_boundary_idx()
                payload = {
                    "id": block["id"],
                    "clip": block["clip"],
                    "start_seconds": block["start_seconds"],
                    "speakers": block["speakers"],
                    "raw_text": STATE.raw_text(block["line_start"], block["line_end"]),
                    "line_start": block["line_start"],
                    "line_end": block["line_end"],
                    "audio_url": "/audio/" + urllib.parse.quote(block["clip"] or "", safe="/"),
                    "proofread": idx <= boundary,
                    "is_next_to_proofread": idx == boundary + 1,
                }
            self._send_json(payload)
            return

        if path.startswith("/audio/"):
            rel = urllib.parse.unquote(path[len("/audio/"):])
            p = safe_audio_path(rel)
            if not p:
                self._send(b"not found", "text/plain", 404)
                return
            self._send_audio(p)
            return

        self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        m = re.fullmatch(r"/api/block/(\d{4})", path)
        if m:
            bid = m.group(1)
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
            with STATE_LOCK:
                if not STATE.save_block(bid, new_text):
                    self._send_json({"error": "save failed"}, 400)
                    return
                summaries = STATE.summaries()
            self._send_json({"ok": True, "blocks": summaries})
            return

        m = re.fullmatch(r"/api/mark-proofread/(\d{4})", path)
        if m:
            bid = m.group(1)
            with STATE_LOCK:
                if not STATE.mark_as_proofread(bid):
                    self._send_json({"error": "not the next block after the current proofread boundary"}, 400)
                    return
                summaries = STATE.summaries()
            self._send_json({"ok": True, "blocks": summaries})
            return

        self._send_json({"error": "not found"}, 404)


def main() -> int:
    if not STATE.blocks:
        print("No transcript blocks parsed.", file=sys.stderr)
        return 1
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"Audio proof-listener serving at http://localhost:{PORT}  "
          f"({len(STATE.blocks)} blocks)")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
