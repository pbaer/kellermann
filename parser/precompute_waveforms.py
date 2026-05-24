#!/usr/bin/env python3
"""Precompute waveform peak sidecars ("<clip>.mp3.peaks") for every audio clip
so the proofreading tool's waveform renders instantly instead of shelling out to
ffmpeg per block.

Idempotent: skips clips whose sidecar is already newer than the source file.
Safe to run repeatedly — run.sh calls it before launching the server, and the
server itself builds any missing sidecar lazily in the background.
"""
from __future__ import annotations

import sys

import proofread_audio as audio

CLIP_EXTS = {".mp3", ".m4a", ".wav", ".ogg"}


def main() -> int:
    root = audio.AUDIO_ROOT
    clips = sorted(p for p in root.rglob("*")
                   if p.is_file() and p.suffix.lower() in CLIP_EXTS)
    if not clips:
        print(f"No audio clips under {root}", file=sys.stderr)
        return 0
    built = skipped = failed = 0
    for c in clips:
        sc = audio.peaks_sidecar_path(c)
        try:
            fresh = sc.exists() and sc.stat().st_mtime >= c.stat().st_mtime
        except OSError:
            fresh = False
        if fresh:
            skipped += 1
            continue
        print(f"  {c.relative_to(root)} …", end="", flush=True)
        if audio.generate_peaks_file(c):
            print(" ok")
            built += 1
        else:
            print(" FAILED")
            failed += 1
    print(f"waveforms: {built} built, {skipped} up-to-date, {failed} failed "
          f"({len(clips)} clips)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
