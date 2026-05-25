#!/usr/bin/env python3
"""Local HTML-based proof-listening tool for the audio interview transcript.

Serves an editor UI at http://localhost:8766 where each timestamped block of
transcript text can be edited while playing back the corresponding audio
from its starting timestamp. Committing writes back to
sources/audio/transcript.txt atomically.

Mirrors the conventions of proofread_letters.py for the kriegstagebuch letters:
the >>>>> marker occupies the blank-separator slot between two consecutive
blocks, and "Mark as proofread" advances it past the current block.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import threading
import urllib.parse
from array import array
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = ROOT / "sources" / "audio"
MAPS_ROOT = ROOT / "sources" / "maps"
TRANSCRIPT = AUDIO_ROOT / "transcript.txt"
HERE = Path(__file__).resolve().parent
PORT = 8766
MAP_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
PROOFREAD_MARKER = ">>>>>"
ANNOTATION_MARKER = "#####"

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

        ##### annotation paragraphs (per CLAUDE.md: short notes about ambiguous
        OCR or unknown abbreviations) belong to the immediately preceding
        prose paragraph and get folded into that block — they don't form
        nav-pane entries on their own. The block's line range is extended over
        any blanks/markers up through the last folded annotation; preview and
        speaker detection ignore the annotation lines.
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
            is_pure_annotation = stripped.startswith(ANNOTATION_MARKER)
            # Walk to end of this paragraph.
            while i < n:
                s = self.lines[i].strip()
                if s == "" or s == PROOFREAD_MARKER:
                    break
                if CLIP_HEADER_RE.match(self.lines[i]):
                    break
                i += 1
            prose_end = i - 1  # inclusive; last line of prose paragraph
            block_end = prose_end

            # If this paragraph is prose, look ahead for ##### annotation
            # paragraphs and fold them into this block. Skip blank/marker
            # separators between them. Stop at a clip header or a fresh prose
            # paragraph.
            if not is_pure_annotation:
                j = i
                while j < n:
                    if CLIP_HEADER_RE.match(self.lines[j]):
                        break
                    s = self.lines[j].strip()
                    if s == "" or s == PROOFREAD_MARKER:
                        j += 1
                        continue
                    if not s.startswith(ANNOTATION_MARKER):
                        break  # next prose paragraph — stop folding
                    # Consume this annotation paragraph.
                    block_end = j
                    j += 1
                    while j < n:
                        s2 = self.lines[j].strip()
                        if (s2 == "" or s2 == PROOFREAD_MARKER
                                or CLIP_HEADER_RE.match(self.lines[j])):
                            break
                        block_end = j
                        j += 1
                i = j

            first = self.lines[block_start]
            start_seconds = parse_timestamp(first)
            # Preview and speaker detection use only the prose paragraph —
            # the annotation isn't part of the recorded speech.
            prose_lines = self.lines[block_start:prose_end + 1]
            preview = self._make_preview(prose_lines)
            speakers = sorted({m.group(1) for line in prose_lines
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


def safe_map_path(rel: str) -> Path | None:
    """Resolve `rel` against MAPS_ROOT, refusing path traversal."""
    try:
        candidate = (MAPS_ROOT / rel).resolve()
        candidate.relative_to(MAPS_ROOT.resolve())
    except (ValueError, OSError):
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    if candidate.suffix.lower() not in MAP_EXTS:
        return None
    return candidate


def _natural_key(s: str) -> list:
    """Sort key that orders embedded numbers numerically (so -2 precedes -10)."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]


def list_maps() -> list[str]:
    if not MAPS_ROOT.exists():
        return []
    names = [p.name for p in MAPS_ROOT.iterdir()
             if p.is_file() and p.suffix.lower() in MAP_EXTS]
    return sorted(names, key=_natural_key)


# Waveform peak extraction. The display only needs a coarse amplitude envelope,
# so audio is decoded to 8 kHz mono and reduced to per-bucket (min, max) pairs.
#
# Decoding per block with ffmpeg is too slow to feel instant, so peaks for the
# whole clip are precomputed once into a sidecar file ("<clip>.mp3.peaks") and
# the server just slices the requested window out of that (sub-millisecond).
# precompute_waveforms.py (and run.sh) build the sidecars up front; if one is
# missing the server still answers from a fast windowed ffmpeg decode and kicks
# off the sidecar build in the background so the next request is instant.
WAVEFORM_SR = 8000
PEAKS_PER_SEC = 200                  # sidecar resolution — one (min,max) per 5 ms
PEAKS_MAGIC = b"WKP1"
PEAKS_SUFFIX = ".peaks"

_peaks_mem: dict = {}                # clip path str -> (mtime, pps, mins, maxs)
_peaks_lock = threading.Lock()
_peaks_building: set = set()         # clips with an in-flight background build


def compute_waveform(path: Path, start: float, dur: float, buckets: int):
    """Windowed ffmpeg fallback: decode just [start, start+dur] to mono PCM and
    reduce to per-bucket (min, max) floats in [-1, 1]. Returns (mins, maxs) or
    None on failure. -ss before -i fast-seeks then decodes precisely, so the
    window aligns without decoding the whole file."""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", str(path),
           "-t", f"{dur:.3f}", "-ac", "1", "-ar", str(WAVEFORM_SR),
           "-f", "s16le", "-"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout
    n = len(raw) // 2
    mins = [0.0] * buckets
    maxs = [0.0] * buckets
    if n == 0:
        return mins, maxs
    samples = array("h")          # signed 16-bit, native (little-endian) order
    samples.frombytes(raw[:n * 2])
    inv = 1.0 / 32768.0
    step = n / buckets
    for b in range(buckets):
        lo = int(b * step)
        hi = int((b + 1) * step)
        if hi <= lo:
            hi = lo + 1
        if hi > n:
            hi = n
        if lo >= n:
            lo = n - 1
        seg = samples[lo:hi]
        if not seg:
            continue
        mins[b] = round(min(seg) * inv, 4)
        maxs[b] = round(max(seg) * inv, 4)
    return mins, maxs


def peaks_sidecar_path(path: Path) -> Path:
    """Sidecar peaks file for a clip, e.g. '01 Foo.mp3' -> '01 Foo.mp3.peaks'."""
    return path.with_name(path.name + PEAKS_SUFFIX)


def generate_peaks_file(path: Path) -> bool:
    """Decode the whole clip once and write a sidecar of int16 (min, max) peaks
    at PEAKS_PER_SEC. Returns True on success. Writes atomically via a temp file.
    """
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-ac", "1", "-ar", str(WAVEFORM_SR), "-f", "s16le", "-"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    raw = proc.stdout
    n = len(raw) // 2
    samples = array("h")
    samples.frombytes(raw[:n * 2])
    bucket = max(1, WAVEFORM_SR // PEAKS_PER_SEC)     # samples per bucket (= 40)
    num = (n + bucket - 1) // bucket
    mins = array("h", bytes(2 * num))
    maxs = array("h", bytes(2 * num))
    for b in range(num):
        lo = b * bucket
        hi = min(n, lo + bucket)
        seg = samples[lo:hi]
        if seg:
            mins[b] = min(seg)
            maxs[b] = max(seg)
    header = PEAKS_MAGIC + struct.pack("<II", PEAKS_PER_SEC, num)
    sc = peaks_sidecar_path(path)
    tmp = sc.with_name(sc.name + ".tmp")
    try:
        with tmp.open("wb") as f:
            f.write(header)
            f.write(mins.tobytes())
            f.write(maxs.tobytes())
        os.replace(tmp, sc)
    except OSError:
        return False
    return True


def load_peaks(path: Path):
    """Return (pps, mins, maxs) from the sidecar via an mtime-keyed in-memory
    cache, or None if there's no readable sidecar."""
    sc = peaks_sidecar_path(path)
    try:
        mtime = sc.stat().st_mtime
    except OSError:
        return None
    key = str(path)
    with _peaks_lock:
        cached = _peaks_mem.get(key)
        if cached and cached[0] == mtime:
            return cached[1], cached[2], cached[3]
    try:
        data = sc.read_bytes()
    except OSError:
        return None
    if len(data) < 12 or data[:4] != PEAKS_MAGIC:
        return None
    pps, num = struct.unpack("<II", data[4:12])
    body = data[12:]
    if len(body) < 4 * num:
        return None
    mins = array("h"); mins.frombytes(body[:2 * num])
    maxs = array("h"); maxs.frombytes(body[2 * num:4 * num])
    with _peaks_lock:
        _peaks_mem[key] = (mtime, pps, mins, maxs)
    return pps, mins, maxs


def _build_peaks_async(path: Path) -> None:
    """Build a missing sidecar in a background thread (deduped per clip)."""
    key = str(path)
    with _peaks_lock:
        if key in _peaks_building:
            return
        _peaks_building.add(key)

    def worker():
        try:
            generate_peaks_file(path)
        finally:
            with _peaks_lock:
                _peaks_building.discard(key)

    threading.Thread(target=worker, daemon=True).start()


def waveform_window(path: Path, start: float, dur: float, buckets: int):
    """Per-bucket (min, max) floats in [-1, 1] for [start, start+dur]. Slices
    the precomputed sidecar when present; otherwise decodes just the window with
    ffmpeg and kicks off a background sidecar build for next time."""
    peaks = load_peaks(path)
    if peaks is None:
        _build_peaks_async(path)
        return compute_waveform(path, start, dur, buckets)
    pps, mins, maxs = peaks
    out_min = [0.0] * buckets
    out_max = [0.0] * buckets
    i0 = max(0, int(round(start * pps)))
    i1 = min(len(mins), int(round((start + dur) * pps)))
    span = i1 - i0
    if span <= 0:
        return out_min, out_max
    inv = 1.0 / 32768.0
    step = span / buckets
    for b in range(buckets):
        lo = i0 + int(b * step)
        hi = i0 + int((b + 1) * step)
        if hi <= lo:
            hi = lo + 1
        if hi > i1:
            hi = i1
        mn = 32767
        mx = -32768
        for i in range(lo, hi):
            v = mins[i]
            if v < mn:
                mn = v
            v = maxs[i]
            if v > mx:
                mx = v
        if mn > mx:
            mn = mx = 0
        out_min[b] = round(mn * inv, 4)
        out_max[b] = round(mx * inv, 4)
    return out_min, out_max


# --- optional noise reduction -------------------------------------------------
# Opt-in denoising for hiss/static-heavy clips, in increasing strength:
#   low    — gentle afftdn (FFT spectral denoise), full band
#   medium — stronger afftdn + band-limit
#   high   — arnndn (RNNoise: a recurrent net trained to isolate *speech* from
#            noise) when models/rnnoise.rnnn is installed, with a light afftdn
#            pass and band-limiting to mop up residual hiss; falls back to an
#            aggressive afftdn chain if the model is missing.
# The whole clip is rendered once and cached in .proc-cache/, keyed by clip +
# the exact filter chain + source mtime, so any change (chain edit, installing
# the RNNoise model, a new source file) invalidates stale caches automatically.
PROC_CACHE = AUDIO_ROOT / ".proc-cache"
RNNOISE_MODEL = HERE / "models" / "rnnoise.rnnn"
PROC_LEVELS = ("low", "medium", "high")
# Render to FLAC, not MP3: MP3 has no sample-accurate timestamps, so the browser
# *estimates* the playback timeline and currentTime drifts during long playback
# (the playhead creeps ahead of the audio). FLAC is lossless with exact sample
# counts and no encoder delay, so currentTime stays sample-accurate.
PROC_FORMAT = "flac"


def proc_chain(level: str):
    """Return the ffmpeg -af filter chain for a denoise strength, or None."""
    if level == "low":
        return "highpass=f=70,afftdn=nr=12:nf=-40:tn=1"
    if level == "medium":
        return "highpass=f=90,afftdn=nr=24:nf=-32:tn=1,lowpass=f=7500"
    if level == "high":
        if RNNOISE_MODEL.is_file():
            # RNNoise alone, full-band: strong speech-preserving denoise. We
            # deliberately don't stack afftdn or a low-pass on top — that
            # over-processed and muffled the voice ("filtered out almost
            # everything"); RNNoise already removes the broadband hiss.
            return f"highpass=f=80,arnndn=m={RNNOISE_MODEL}"
        return "highpass=f=90,afftdn=nr=33:nf=-28:tn=1"
    return None


# Background render jobs, so the client can show real progress. token -> dict.
_proc_jobs: dict = {}
_proc_jobs_lock = threading.Lock()


def _proc_token(rel: str, chain: str, mtime: float) -> str:
    # PROC_FORMAT is part of the key so switching formats invalidates old renders.
    h = hashlib.sha1(f"{rel}|{chain}|{PROC_FORMAT}|{mtime}".encode("utf-8"))
    return h.hexdigest()[:16] + "." + PROC_FORMAT


def safe_proc_path(token: str):
    """Resolve a /audio-proc/<token> request to a cache file, refusing anything
    that isn't a bare cache filename (no path traversal)."""
    if not re.fullmatch(r"[0-9a-f]{16}\.(flac|mp3|wav)", token):
        return None
    p = PROC_CACHE / token
    return p if p.is_file() else None


def _probe_duration(path: Path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _set_job(token: str, **kw) -> None:
    with _proc_jobs_lock:
        job = _proc_jobs.setdefault(
            token, {"progress": 0.0, "status": "running", "url": None})
        job.update(kw)


def _proc_worker(token: str, src: Path, chain: str, out: Path) -> None:
    """Render the clip with ffmpeg, parsing -progress to report fraction done."""
    duration = _probe_duration(src) or 0.0
    try:
        PROC_CACHE.mkdir(exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", chain,
               "-c:a", "flac", "-f", "flac",
               "-progress", "pipe:1", "-nostats", str(tmp)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
        for line in proc.stdout:
            line = line.strip()
            if duration > 0 and (line.startswith("out_time_us=")
                                 or line.startswith("out_time_ms=")):
                val = line.split("=", 1)[1]
                if val and val != "N/A":
                    try:                       # both fields are microseconds
                        secs = int(val) / 1_000_000.0
                        _set_job(token, progress=max(0.0, min(0.99, secs / duration)))
                    except ValueError:
                        pass
        proc.wait()
        if proc.returncode == 0 and tmp.exists():
            os.replace(tmp, out)
            # Build the waveform sidecar for the processed file too, so the
            # waveform can be drawn from the *same* file that's played (the
            # filters + re-encode shift the timeline ~10-25ms vs the original,
            # which otherwise makes the playhead look off when denoise is on).
            generate_peaks_file(out)
            _set_job(token, progress=1.0, status="done", url="/audio-proc/" + token)
        else:
            try:
                tmp.unlink()
            except OSError:
                pass
            _set_job(token, status="error")
    except (OSError, subprocess.SubprocessError):
        _set_job(token, status="error")


def start_process_job(rel: str, level: str):
    """Ensure a denoised render of `rel` at `level` is cached or building.
    Returns (token, ready, url) — ready True if the file already exists — or None
    on bad input. A build already in flight isn't restarted."""
    if level not in PROC_LEVELS:
        return None
    chain = proc_chain(level)
    src = safe_audio_path(rel)
    if not src or not chain:
        return None
    token = _proc_token(rel, chain, src.stat().st_mtime)
    out = PROC_CACHE / token
    if out.exists():
        return token, True, "/audio-proc/" + token
    with _proc_jobs_lock:
        job = _proc_jobs.get(token)
        if job and job["status"] == "running":
            return token, False, None
        if job and job["status"] == "done" and out.exists():
            return token, True, job["url"]
        _proc_jobs[token] = {"progress": 0.0, "status": "running", "url": None}
    threading.Thread(target=_proc_worker, args=(token, src, chain, out),
                     daemon=True).start()
    return token, False, None


def process_status(token: str):
    """Status dict for a render job/token: {ready, progress, url?, error?}."""
    if safe_proc_path(token):
        return {"ready": True, "progress": 1.0, "url": "/audio-proc/" + token}
    with _proc_jobs_lock:
        job = _proc_jobs.get(token)
    if not job:
        return {"ready": False, "progress": 0.0, "error": "unknown"}
    if job["status"] == "error":
        return {"ready": False, "progress": 0.0, "error": "failed"}
    if job["status"] == "done":
        return {"ready": True, "progress": 1.0, "url": job["url"]}
    return {"ready": False, "progress": job["progress"]}


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
            ".flac": "audio/flac",
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

        if path == "/api/audio/search-index":
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

        if path == "/api/audio/process":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            rel = urllib.parse.unquote(qs.get("clip", [""])[0])
            level = qs.get("level", [""])[0]
            res = start_process_job(rel, level)
            if not res:
                self._send_json({"error": "bad request"}, 400)
                return
            token, ready, url = res
            self._send_json({"token": token, "ready": ready, "url": url})
            return

        if path == "/api/audio/process-status":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            token = qs.get("token", [""])[0]
            self._send_json(process_status(token))
            return

        if path.startswith("/audio-proc/"):
            token = urllib.parse.unquote(path[len("/audio-proc/"):])
            p = safe_proc_path(token)
            if not p:
                self._send(b"not found", "text/plain", 404)
                return
            self._send_audio(p)
            return

        if path == "/api/audio/waveform":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                start = max(0.0, float(qs.get("start", ["0"])[0]))
                dur = float(qs.get("dur", ["0"])[0])
                buckets = int(qs.get("buckets", ["1000"])[0])
            except ValueError:
                self._send_json({"error": "bad params"}, 400)
                return
            # Source can be an original clip (clip=…) or a processed render
            # (proc=<token>) so the waveform matches whatever is being played.
            proc = qs.get("proc", [""])[0]
            if proc:
                p = safe_proc_path(proc)
            else:
                p = safe_audio_path(urllib.parse.unquote(qs.get("clip", [""])[0]))
            if not p or dur <= 0:
                self._send_json({"error": "not found"}, 404)
                return
            buckets = max(1, min(4000, buckets))
            result = waveform_window(p, start, dur, buckets)
            if result is None:
                self._send_json({"error": "decode failed"}, 500)
                return
            mins, maxs = result
            self._send_json({"start": start, "dur": dur, "buckets": buckets,
                             "sample_rate": WAVEFORM_SR, "min": mins, "max": maxs})
            return

        if path == "/api/maps":
            self._send_json(list_maps())
            return

        if path.startswith("/maps/"):
            rel = urllib.parse.unquote(path[len("/maps/"):])
            p = safe_map_path(rel)
            if not p:
                self._send(b"not found", "text/plain", 404)
                return
            ctype = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(p.suffix.lower(), "application/octet-stream")
            self._send(p.read_bytes(), ctype,
                       extra={"Cache-Control": "private, max-age=3600"})
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
