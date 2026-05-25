#!/usr/bin/env python3
"""Download the RNNoise model used by the audio proofreader's "High" denoise
level into models/rnnoise.rnnn.

High denoising runs ffmpeg's `arnndn` filter (a recurrent net trained to isolate
speech from noise), which needs a model file. We use the "somnolent hogwash"
general-purpose voice model from the public GregorR/rnnoise-models collection.
If the model is absent, High falls back to an aggressive afftdn chain, so this
is optional — but RNNoise preserves speech far better.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

MODEL_URL = ("https://raw.githubusercontent.com/GregorR/rnnoise-models/master/"
             "somnolent-hogwash-2018-09-01/sh.rnnn")
DEST = Path(__file__).resolve().parent / "models" / "rnnoise.rnnn"


def main() -> int:
    if DEST.is_file() and DEST.stat().st_size > 0:
        print(f"Already present: {DEST} ({DEST.stat().st_size} bytes)")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading RNNoise model → {DEST}")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=30) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001 - report any network/HTTP failure
        print(f"Download failed: {e}", file=sys.stderr)
        return 1
    DEST.write_bytes(data)
    print(f"Saved {len(data)} bytes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
