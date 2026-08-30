"""Centralized semantic design tokens, per DESIGN.md sections 37/42/43.

These are frozen production constants, not per-widget magic values. Any
new widget should reference this module rather than hard-coding colors,
spacing, or radii.
"""

from __future__ import annotations


class Color:
    # Background / surfaces
    VOID = "#08090c"
    SURFACE_0 = "#0f1217"
    SURFACE_1 = "#151921"
    SURFACE_2 = "#1b212c"
    SURFACE_3 = "#232b38"
    SURFACE_HOVER = "#2a3444"

    # Borders
    BORDER_SUBTLE = "#1e2634"
    BORDER_MEDIUM = "#2a3547"
    BORDER_STRONG = "#3b4960"
    FOCUS_BORDER = "#0099ff"

    # Text
    TEXT_PRIMARY = "#f8fafc"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_MUTED = "#64748b"
    TEXT_DISABLED = "#475569"

    # Accent
    ACCENT = "#0099ff"
    ACCENT_HOVER = "#26abff"

    # Semantic
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    DANGER = "#ef4444"
    INFO = "#0ea5e9"


class Spacing:
    MICRO = 4
    COMPACT = 6
    STANDARD = 8
    CARD_COMPACT = 10
    CARD_STANDARD = 12
    PANEL_MAJOR = 16
    SEPARATION_RARE = 24


class Radius:
    SMALL = 4
    MEDIUM = 8
    LARGE = 12
    PILL = 9999


def base_stylesheet() -> str:
    """QSS implementing the dark-precision surface/text baseline."""
    return f"""
    QMainWindow, QWidget {{
        background-color: {Color.VOID};
        color: {Color.TEXT_PRIMARY};
    }}
    QSplitter::handle {{
        background-color: {Color.BORDER_SUBTLE};
    }}
    """
