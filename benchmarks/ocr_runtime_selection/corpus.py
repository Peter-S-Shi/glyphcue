"""Diagnostic corpus for Milestone 3 OCR runtime selection.

Every image is generated on demand from the text strings below using
system fonts -- nothing here is a scraped video frame, a real subtitle
screenshot, or any other copyrighted material. This keeps the corpus
small, reproducible, and copyright-safe, per ROADMAP.md Milestone 3.

Font paths are Windows system fonts (this benchmark was run on Windows;
see the ADR for the exact machine/environment). Regenerating this
corpus on a different OS will use different glyph rendering but the
same text content and categories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONTS_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


@dataclass(frozen=True)
class CorpusItem:
    id: str
    category: str
    ground_truth: str
    render: Callable[[], Image.Image]


def _plain_crop(text: str, font_path: Path, font_size: int = 32, size=(320, 64)) -> Image.Image:
    image = Image.new("RGB", size, color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), font_size)
    draw.text((10, 12), text, font=font, fill=(255, 255, 255))
    return image


def _bilingual_crop(line1: str, font1: Path, line2: str, font2: Path, size=(360, 90)) -> Image.Image:
    image = Image.new("RGB", size, color=(15, 15, 15))
    draw = ImageDraw.Draw(image)
    f1 = ImageFont.truetype(str(font1), 26)
    f2 = ImageFont.truetype(str(font2), 26)
    draw.text((10, 6), line1, font=f1, fill=(255, 255, 255))
    draw.text((10, 46), line2, font=f2, fill=(255, 255, 255))
    return image


def _low_quality_crop(text: str, font_path: Path, size=(320, 64)) -> Image.Image:
    image = _plain_crop(text, font_path, font_size=30, size=size)
    image = image.filter(ImageFilter.GaussianBlur(radius=1.6))
    # Low contrast + mild dark overlay to simulate compressed/dim source.
    overlay = Image.new("RGB", size, color=(40, 40, 40))
    image = Image.blend(image, overlay, alpha=0.35)
    return image


def _subtitle_style_crop(text: str, font_path: Path, size=(420, 80)) -> Image.Image:
    """Bold white text with a black outline + drop shadow on a busy
    gradient background -- representative of a real burned-in subtitle
    over live-action video, without using any actual video frame."""
    image = Image.new("RGB", size, color=(0, 0, 0))
    for x in range(size[0]):
        shade = int(40 + 60 * (x / size[0]))
        for y in range(size[1]):
            image.putpixel((x, y), (shade, shade // 2, shade // 3))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 34)
    x, y = 14, 20
    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (0, 2), (2, 0)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))
    return image


CORPUS: list[CorpusItem] = [
    CorpusItem(
        id="english_clean",
        category="English",
        ground_truth="The quick brown fox jumps over the lazy dog.",
        render=lambda: _plain_crop(
            "The quick brown fox jumps over the lazy dog.", _FONTS_DIR / "arial.ttf", 22, (480, 50)
        ),
    ),
    CorpusItem(
        id="chinese_clean",
        category="Chinese",
        ground_truth="今天天气非常好，我们一起去公园散步。",
        render=lambda: _plain_crop(
            "今天天气非常好，我们一起去公园散步。", _FONTS_DIR / "simhei.ttf", 26, (560, 50)
        ),
    ),
    CorpusItem(
        id="japanese_clean",
        category="Japanese",
        ground_truth="今日はとても良い天気ですね。",
        render=lambda: _plain_crop(
            "今日はとても良い天気ですね。", _FONTS_DIR / "msgothic.ttc", 26, (460, 50)
        ),
    ),
    CorpusItem(
        id="bilingual_crop",
        category="Bilingual crop",
        ground_truth="Hello, welcome!|你好，欢迎！",
        render=lambda: _bilingual_crop(
            "Hello, welcome!", _FONTS_DIR / "arial.ttf", "你好，欢迎！", _FONTS_DIR / "simhei.ttf"
        ),
    ),
    CorpusItem(
        id="low_quality_crop",
        category="Low-quality crop",
        ground_truth="Please stand by for further instructions.",
        render=lambda: _low_quality_crop(
            "Please stand by for further instructions.", _FONTS_DIR / "arial.ttf", (560, 50)
        ),
    ),
    CorpusItem(
        id="subtitle_style_representative",
        category="Representative subtitle style",
        ground_truth="This is a burned-in subtitle example.",
        render=lambda: _subtitle_style_crop(
            "This is a burned-in subtitle example.", _FONTS_DIR / "arialbd.ttf", (620, 70)
        ),
    ),
]


def generate_corpus(output_dir: Path) -> list[tuple[CorpusItem, Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for item in CORPUS:
        image = item.render()
        path = output_dir / f"{item.id}.png"
        image.save(path)
        results.append((item, path))
    return results
