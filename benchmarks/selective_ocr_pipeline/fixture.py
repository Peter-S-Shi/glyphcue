"""Generates a small, copyright-safe representative subtitle video for
Milestone 4 selective-vs-dense OCR verification.

No scraped video or real subtitle screenshot is used: every frame is
rendered in-script from known text using a Windows system font (same
approach as benchmarks/ocr_runtime_selection/corpus.py).
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 480, 120
FRAME_MS = 100  # one frame every 100ms -> 10fps-equivalent sampling

# (start_ms, end_ms, text) -- two real subtitle states with a gap
# between them (no text), like a real burned-in caption track.
SEGMENTS = [
    (0, 1500, "The quick brown fox"),
    (1500, 3000, "jumps over the lazy dog"),
    (3000, 4000, ""),
]


def _render_frame(text: str) -> np.ndarray:
    image = Image.new("RGB", (WIDTH, HEIGHT), color=(20, 20, 20))
    if text:
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("arialbd.ttf", 28)
        draw.text((16, HEIGHT // 2 - 18), text, font=font, fill=(255, 255, 255))
    return np.array(image)


def generate_fixture(path: Path) -> list[tuple[int, str]]:
    """Writes the fixture video to `path`; returns [(pts_ms, text), ...]
    for every frame actually written, for use as ground truth."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = WIDTH
    stream.height = HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0

    frames_written: list[tuple[int, str]] = []
    total_ms = SEGMENTS[-1][1]
    for pts_ms in range(0, total_ms, FRAME_MS):
        text = next(t for start, end, t in SEGMENTS if start <= pts_ms < end)
        array = _render_frame(text)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
        frames_written.append((pts_ms, text))
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return frames_written
