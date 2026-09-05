"""Deterministic synthetic video fixture generator for GlyphCue packaging experiments.

Generates a public-safe, deterministic MP4 video with structured subtitle cards
for offline smoke-testing, output fidelity verification, and DirectML performance benchmarking.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np

# Canonical fixture specifications
FIXTURE_FILENAME = "glyphcue_synthetic_fixture_v1.mp4"
FIXTURE_WIDTH = 1280
FIXTURE_HEIGHT = 720
FIXTURE_FPS = 10
FIXTURE_DURATION_SEC = 6
FIXTURE_TOTAL_FRAMES = FIXTURE_FPS * FIXTURE_DURATION_SEC


class CueSpec(NamedTuple):
    start_frame: int
    end_frame: int
    start_ms: int
    end_ms: int
    text: str


FIXTURE_CUES: tuple[CueSpec, ...] = (
    CueSpec(0, 20, 0, 2000, "GLYPHCUE V1 PACKAGING TEST"),
    CueSpec(20, 40, 2000, 4000, "SYNTHETIC SUBTITLE RECONSTRUCTION"),
    CueSpec(40, 60, 4000, 6000, "HIGH FIDELITY DETERMINISTIC FIXTURE"),
)

EXPECTED_FIXTURE_SHA256 = "72a7621639730b62b5a06a266499ea66768df277cad15553cab6d2487b972465"
EXPECTED_FIXTURE_SIZE = 183789


def generate_fixture(output_path: Path | str) -> tuple[int, str]:
    """Generate the deterministic synthetic video fixture at output_path.

    Returns:
        tuple[int, str]: (file_size_bytes, sha256_hash)
    """
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(dest), fourcc, FIXTURE_FPS, (FIXTURE_WIDTH, FIXTURE_HEIGHT))

    try:
        for i in range(FIXTURE_TOTAL_FRAMES):
            frame = np.full((FIXTURE_HEIGHT, FIXTURE_WIDTH, 3), 20, dtype=np.uint8)
            active_text: str | None = None
            for cue in FIXTURE_CUES:
                if cue.start_frame <= i < cue.end_frame:
                    active_text = cue.text
                    break

            if active_text is not None:
                # Subtitle background box
                cv2.rectangle(frame, (100, 560), (1180, 660), (0, 0, 0), -1)
                # Subtitle text
                cv2.putText(
                    frame,
                    active_text,
                    (140, 630),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,
                    (255, 255, 255),
                    3,
                    cv2.LINE_AA,
                )
            out.write(frame)
    finally:
        out.release()

    data = dest.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    size = len(data)
    return size, sha256


def verify_fixture(fixture_path: Path | str) -> bool:
    """Verify that a fixture file matches the expected size and SHA-256 hash."""
    path = Path(fixture_path)
    if not path.is_file():
        return False
    data = path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    return sha256 == EXPECTED_FIXTURE_SHA256 and len(data) == EXPECTED_FIXTURE_SIZE


if __name__ == "__main__":
    out_dir = Path("build_artifacts") if len(sys.argv) < 2 else Path(sys.argv[1])
    target = out_dir / FIXTURE_FILENAME if out_dir.is_dir() or not out_dir.suffix else out_dir
    size, sha = generate_fixture(target)
    print(f"Generated synthetic fixture: {target}")
    print(f"Size: {size} bytes (Expected: {EXPECTED_FIXTURE_SIZE})")
    print(f"SHA-256: {sha}")
    if sha == EXPECTED_FIXTURE_SHA256 and size == EXPECTED_FIXTURE_SIZE:
        print("VERIFIED: Fixture matches expected hash and size.")
        sys.exit(0)
    else:
        print("ERROR: Hash or size mismatch against canonical specification!", file=sys.stderr)
        sys.exit(1)
