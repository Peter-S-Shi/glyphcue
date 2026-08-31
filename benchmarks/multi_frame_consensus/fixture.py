"""Generates copyright-safe, per-language noisy OCR-reading fixtures for
Milestone 5 single-frame-vs-consensus evaluation.

Every image is rendered in-script from known ground-truth text using a
Windows system font (same approach as
benchmarks/ocr_runtime_selection/corpus.py and
benchmarks/selective_ocr_pipeline/fixture.py) -- no scraped video frame
or real subtitle screenshot is used anywhere.

Each ground-truth line gets N independently-noised image variants,
simulating N repeated real-world OCR samples of the same on-screen
subtitle across frames with slightly different compression/motion
degradation -- the scenario multi-frame consensus is meant to help
with. Clean text alone isn't useful evidence here: real PaddleOCR reads
clean generated subtitle crops essentially perfectly (see Milestone 3's
benchmark), so there is nothing for consensus to correct.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

VARIANTS_PER_LINE = 5


@dataclass(frozen=True)
class EvalItem:
    id: str
    language: str
    ground_truth: str
    font_path: str
    canvas_size: tuple[int, int]


ITEMS: list[EvalItem] = [
    EvalItem(
        id="english_line",
        language="en",
        ground_truth="The quick brown fox jumps over the lazy dog.",
        font_path="arial.ttf",
        canvas_size=(620, 60),
    ),
    EvalItem(
        id="chinese_line",
        language="zh",
        ground_truth="今天天气非常好，我们一起去公园散步。",
        font_path="simhei.ttf",
        canvas_size=(620, 60),
    ),
    EvalItem(
        id="japanese_line",
        language="ja",
        ground_truth="今日はとても良い天気ですね。",
        font_path="msgothic.ttc",
        canvas_size=(560, 60),
    ),
]


def _render_clean(item: EvalItem) -> Image.Image:
    image = Image.new("RGB", item.canvas_size, color=(15, 15, 15))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(item.font_path, 28)
    draw.text((10, item.canvas_size[1] // 2 - 18), item.ground_truth, font=font, fill=(255, 255, 255))
    return image


def _light_noise_variant(clean: Image.Image, rng: random.Random) -> np.ndarray:
    """A mild read: a small blur only, no occlusion -- a normal,
    successfully-recognizable confirmation frame."""
    blur_radius = rng.uniform(0.3, 0.7)
    degraded = clean.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return np.array(degraded)


def _heavy_noise_variant(clean: Image.Image, rng: random.Random) -> np.ndarray:
    """One severely-degraded read: strong blur, reduced contrast, additive
    pixel noise, AND a random localized occlusion patch (simulating a
    compression block artifact or a moment of motion blur covering part
    of a character). This is the "one bad frame" a real burned-in
    subtitle track occasionally has."""
    blur_radius = rng.uniform(1.0, 2.2)
    degraded = clean.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    array = np.array(degraded).astype(np.float64)
    contrast = rng.uniform(0.5, 0.7)
    array = (array - 128) * contrast + 128
    np_rng = np.random.default_rng(rng.randint(0, 2**31 - 1))
    noise_array = np_rng.normal(0, 18, size=array.shape)
    array = np.clip(array + noise_array, 0, 255).astype(np.uint8)

    height, width = array.shape[0], array.shape[1]
    patch_w = rng.randint(width // 12, width // 6)
    patch_h = rng.randint(height // 3, height - 4)
    x0 = rng.randint(0, max(1, width - patch_w))
    y0 = rng.randint(0, max(1, height - patch_h))
    array[y0 : y0 + patch_h, x0 : x0 + patch_w] = rng.choice([0, 15, 30])

    return array


def generate_mixed_variants(item: EvalItem, seed: int) -> list[np.ndarray]:
    """The realistic scenario a single-frame pipeline handles badly: the
    FIRST OCR confirmation (e.g. right as ChangeTriggeredOcrPolicy first
    detects the change, mid-transition) is severely degraded, followed
    by 4 ordinary, clean confirmation reads once the subtitle has fully
    settled. A single-frame baseline that trusts the first reading gets
    this wrong; consensus across all frames should not."""
    rng = random.Random(seed)
    clean = _render_clean(item)
    variants = [_heavy_noise_variant(clean, rng)]
    variants += [_light_noise_variant(clean, rng) for _ in range(VARIANTS_PER_LINE - 1)]
    return variants


def generate_all_noisy_variants(item: EvalItem, seed: int) -> list[np.ndarray]:
    """A deliberately harder, worst-case scenario: every single read is
    independently heavily degraded (no clean confirmations at all) --
    used to honestly document where the simple majority-vote baseline
    stops helping (see docs/consensus/multi_frame_consensus.md)."""
    rng = random.Random(seed)
    clean = _render_clean(item)
    return [_heavy_noise_variant(clean, rng) for _ in range(VARIANTS_PER_LINE)]
