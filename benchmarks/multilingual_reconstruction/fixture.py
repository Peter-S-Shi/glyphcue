"""Copyright-safe, real-geometry multilingual block fixtures for
Milestone 6's targeted real-PaddleOCR verification.

Each fixture stacks two or three DIFFERENT single-language ground-truth
lines (reusing the same ground truths and fonts as
`benchmarks/multi_frame_consensus/fixture.py`, all in-script rendered
from known text, no scraped video frame or real subtitle screenshot)
vertically into ONE image -- simulating a real bilingual/trilingual
burned-in subtitle block sharing one visual region, the exact case
`assign_observations_to_languages`'s vertical-layout signal exists for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_LINE_HEIGHT = 60
_CANVAS_WIDTH = 640


@dataclass(frozen=True)
class MultilingualBlock:
    id: str
    lines: tuple[tuple[str, str, str], ...]
    """(language, ground_truth_text, font_path) tuples, top to bottom."""


BLOCKS: list[MultilingualBlock] = [
    MultilingualBlock(
        id="bilingual_en_zh",
        lines=(
            ("en", "The quick brown fox jumps over the lazy dog.", "arial.ttf"),
            ("zh", "今天天气非常好，我们一起去公园散步。", "simhei.ttf"),
        ),
    ),
    MultilingualBlock(
        id="trilingual_en_zh_ja",
        lines=(
            ("en", "The quick brown fox jumps over the lazy dog.", "arial.ttf"),
            ("zh", "今天天气非常好，我们一起去公园散步。", "simhei.ttf"),
            ("ja", "今日はとても良い天気ですね。", "msgothic.ttc"),
        ),
    ),
]


def render_block(block: MultilingualBlock) -> np.ndarray:
    """Renders `block`'s lines stacked top-to-bottom into one RGB image,
    each on its own `_LINE_HEIGHT`-tall band -- real, non-overlapping
    vertical geometry a real OCR engine will report real polygon
    coordinates for, exactly like a genuine multi-line burned-in block."""
    height = _LINE_HEIGHT * len(block.lines)
    image = Image.new("RGB", (_CANVAS_WIDTH, height), color=(15, 15, 15))
    draw = ImageDraw.Draw(image)
    for index, (_language, text, font_path) in enumerate(block.lines):
        font = ImageFont.truetype(font_path, 28)
        y = index * _LINE_HEIGHT + (_LINE_HEIGHT // 2 - 18)
        draw.text((10, y), text, font=font, fill=(255, 255, 255))
    return np.array(image)
