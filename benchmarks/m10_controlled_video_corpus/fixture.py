"""Milestone 10 controlled/synthetic representative-video fixtures.

These are NOT a substitute for the repo owner's realistic private video
corpus (see docs/m10_private_corpus_incident.md) -- they are small,
deterministic, demo-safe stand-ins that let M10's real-video Path A
evaluation close reproducibly on any machine, without requiring
copyrighted/private source material or an unbounded run time.

Every frame is rendered in-script from known text (same approach as
`benchmarks/selective_ocr_pipeline/fixture.py` and
`benchmarks/multilingual_reconstruction/fixture.py`) -- no scraped video
or real subtitle screenshot. Ground truth is exact by construction: the
text/timing below is authored BEFORE any GlyphCue pipeline ever sees
these frames, never reverse-engineered from a GlyphCue prediction.

Three fixtures, matching the three real-world conditions the (larger,
private) representative-video corpus targets:

- `clean_single_language`: one static-background English line -- the
  easy/normal case.
- `bilingual_typical`: a static-background two-line English+Chinese
  block -- the typical multilingual case.
- `difficult_noisy_background`: the SAME text content as
  `clean_single_language`, but with independent per-frame random pixel
  noise added to the background -- a controlled, reproducible version of
  a real finding from the (crashed) private-corpus run: a real sample's
  ChangeTriggeredOcrPolicy triggered on nearly every analyzed frame
  (177 triggers over ~17.5 real media-seconds), consistent with a
  non-static real-world background crossing the change-detection
  threshold far more often than the clean fixtures this policy was
  originally verified against (see ADR 0002's own stated limitation).
  This fixture exists to measure that trigger-rate effect directly and
  reproducibly, not just anecdotally.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 480, 160
FRAME_MS = 100  # one frame every 100ms, matching selective_ocr_pipeline's fixture


@dataclass(frozen=True)
class ControlledFixture:
    id: str
    languages: tuple[str, ...]
    # (start_ms, end_ms, {language: text}) -- text is "" for a blank span.
    segments: tuple[tuple[int, int, dict], ...]
    noisy_background: bool = False


_EN_GT = "The quick brown fox jumps over the lazy dog"
_ZH_GT = "今天天气非常好，我们一起去公园散步"

FIXTURES: list[ControlledFixture] = [
    ControlledFixture(
        id="clean_single_language",
        languages=("en",),
        segments=(
            (0, 2000, {"en": _EN_GT}),
            (2000, 4000, {"en": ""}),
            (4000, 6000, {"en": _EN_GT}),
        ),
    ),
    ControlledFixture(
        id="bilingual_typical",
        languages=("en", "zh"),
        segments=(
            (0, 3000, {"en": _EN_GT, "zh": _ZH_GT}),
            (3000, 6000, {"en": "", "zh": ""}),
        ),
    ),
    ControlledFixture(
        id="difficult_noisy_background",
        languages=("en",),
        segments=(
            (0, 2000, {"en": _EN_GT}),
            (2000, 4000, {"en": ""}),
            (4000, 6000, {"en": _EN_GT}),
        ),
        noisy_background=True,
    ),
]


def _render_frame(fixture: ControlledFixture, text_by_language: dict, rng: np.random.Generator) -> np.ndarray:
    if fixture.noisy_background:
        # Independent per-frame random noise -- background pixels shift
        # every frame even though no real content changed, the controlled
        # analogue of a real (non-static) camera/compression background.
        base = rng.integers(15, 26, size=(HEIGHT, WIDTH, 3), dtype=np.uint8)
        image = Image.fromarray(base, mode="RGB")
    else:
        image = Image.new("RGB", (WIDTH, HEIGHT), color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    y = 20
    for language in fixture.languages:
        text = text_by_language.get(language, "")
        if text:
            font_path = "simhei.ttf" if language == "zh" else "arialbd.ttf"
            font = ImageFont.truetype(font_path, 24)
            draw.text((16, y), text, font=font, fill=(255, 255, 255))
        y += 50
    return np.array(image)


def generate_fixture(fixture: ControlledFixture, path: Path, seed: int = 20260831) -> list[tuple[int, dict]]:
    """Writes `fixture` to `path`; returns [(pts_ms, text_by_language), ...]
    for every frame actually written, for use as ground truth."""
    rng = np.random.default_rng(seed)
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = WIDTH
    stream.height = HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0

    frames_written: list[tuple[int, dict]] = []
    total_ms = fixture.segments[-1][1]
    for pts_ms in range(0, total_ms, FRAME_MS):
        text_by_language = next(
            texts for start, end, texts in fixture.segments if start <= pts_ms < end
        )
        array = _render_frame(fixture, text_by_language, rng)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
        frames_written.append((pts_ms, text_by_language))
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return frames_written
