"""Centralized semantic design tokens and QSS stylesheet engine, per DESIGN.md sections 37/42/43.

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
    ACCENT_SUBTLE = "rgba(0, 153, 255, 0.15)"
    ACCENT_GLOW = "rgba(0, 153, 255, 0.35)"

    # Semantic
    SUCCESS = "#10b981"
    SUCCESS_SUBTLE = "rgba(16, 185, 129, 0.15)"
    WARNING = "#f59e0b"
    WARNING_SUBTLE = "rgba(245, 158, 11, 0.16)"
    DANGER = "#ef4444"
    DANGER_SUBTLE = "rgba(239, 68, 68, 0.16)"
    INFO = "#0ea5e9"
    INFO_SUBTLE = "rgba(14, 165, 233, 0.15)"

    # Language Layer Palette (Prototype Alignment)
    LANG_CYAN = "#38bdf8"
    LANG_VIOLET = "#a78bfa"
    LANG_EMERALD = "#34d399"
    LANG_AMBER = "#fbbf24"


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
    """Complete dark-precision QSS stylesheet aligning with the GlyphCue
    Evidence Workbench prototype visual hierarchy."""
    return f"""
    /* Global Base */
    QMainWindow, QWidget {{
        background-color: {Color.VOID};
        color: {Color.TEXT_PRIMARY};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 12px;
    }}

    QSplitter::handle {{
        background-color: {Color.BORDER_SUBTLE};
        width: 1px;
        height: 1px;
    }}
    QSplitter::handle:hover {{
        background-color: {Color.ACCENT};
    }}

    /* Top App Header / Chrome */
    #appHeader {{
        background-color: {Color.SURFACE_0};
        border-bottom: 1px solid {Color.BORDER_SUBTLE};
        min-height: 48px;
        max-height: 48px;
    }}
    #brandLogoBox {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0099ff, stop:1 #0055cc);
        border-radius: 4px;
        color: #ffffff;
        font-weight: 800;
        font-size: 12px;
        padding: 3px 6px;
    }}
    #brandLabel {{
        font-weight: 800;
        font-size: 14px;
        color: {Color.TEXT_PRIMARY};
        letter-spacing: -0.3px;
    }}
    #appBadge {{
        background-color: {Color.SURFACE_2};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 9999px;
        color: {Color.TEXT_SECONDARY};
        font-size: 10px;
        font-weight: 600;
        padding: 2px 7px;
    }}
    #assetStatusPill {{
        background-color: {Color.SURFACE_1};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 9999px;
        color: {Color.TEXT_SECONDARY};
        font-size: 11px;
        padding: 3px 10px;
    }}

    /* Mode Navigation Buttons (Segmented Bar) */
    #modeNavContainer {{
        background-color: {Color.SURFACE_1};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 6px;
        padding: 2px;
    }}
    QPushButton#modeBtn {{
        background-color: transparent;
        color: {Color.TEXT_SECONDARY};
        border: none;
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 500;
    }}
    QPushButton#modeBtn:hover:!checked {{
        color: {Color.TEXT_PRIMARY};
        background-color: {Color.SURFACE_2};
    }}
    QPushButton#modeBtn:checked {{
        background-color: {Color.SURFACE_3};
        color: {Color.TEXT_PRIMARY};
        font-weight: 600;
        border: 1px solid {Color.BORDER_MEDIUM};
    }}

    /* Card Panels & Containers */
    #structureCard, #ocrActionBox, #qaHeaderCard, #timingCard, #evidenceCard, #exportCard, #diagnosticsCard {{
        background-color: {Color.SURFACE_1};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 8px;
        padding: 10px 12px;
    }}
    #structureCard:hover, #ocrActionBox:hover, #qaHeaderCard:hover {{
        border-color: {Color.BORDER_MEDIUM};
    }}

    .section-title, #sectionHeaderLabel {{
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: {Color.TEXT_MUTED};
        margin-bottom: 4px;
    }}

    /* Buttons */
    QPushButton {{
        background-color: {Color.SURFACE_2};
        border: 1px solid {Color.BORDER_MEDIUM};
        border-radius: 6px;
        color: {Color.TEXT_PRIMARY};
        padding: 5px 12px;
        font-weight: 500;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {Color.SURFACE_3};
        border-color: {Color.BORDER_STRONG};
    }}
    QPushButton:pressed {{
        background-color: {Color.SURFACE_HOVER};
    }}
    QPushButton:disabled {{
        background-color: {Color.SURFACE_0};
        border-color: {Color.BORDER_SUBTLE};
        color: {Color.TEXT_DISABLED};
    }}

    /* Primary Action Buttons */
    QPushButton#primaryBtn, QPushButton#runOcrBtn {{
        background-color: {Color.ACCENT};
        color: #ffffff;
        font-weight: 600;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }}
    QPushButton#primaryBtn:hover, QPushButton#runOcrBtn:hover {{
        background-color: {Color.ACCENT_HOVER};
        border-color: rgba(255, 255, 255, 0.3);
    }}

    /* Dominant QA Approve Button */
    QPushButton#approveButton {{
        background-color: {Color.SUCCESS};
        color: #ffffff;
        font-weight: 700;
        font-size: 13px;
        padding: 8px 16px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
    }}
    QPushButton#approveButton:hover {{
        background-color: #15c98d;
    }}
    QPushButton#approveButton:pressed {{
        background-color: #0ea372;
    }}

    /* Danger / Discard Action Button */
    QPushButton#discardButton, QPushButton#subtleDangerBtn {{
        background-color: {Color.DANGER_SUBTLE};
        border: 1px solid rgba(239, 68, 68, 0.35);
        color: {Color.DANGER};
        font-weight: 600;
    }}
    QPushButton#discardButton:hover, QPushButton#subtleDangerBtn:hover {{
        background-color: {Color.DANGER};
        color: #ffffff;
        border-color: {Color.DANGER};
    }}

    /* Inputs, LineEdits, SpinBoxes & TextEdits */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
        background-color: {Color.SURFACE_0};
        border: 1px solid {Color.BORDER_MEDIUM};
        border-radius: 4px;
        color: {Color.TEXT_PRIMARY};
        padding: 4px 8px;
        font-size: 12px;
        selection-background-color: {Color.ACCENT};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border-color: {Color.FOCUS_BORDER};
    }}
    QLineEdit::placeholder {{
        color: {Color.TEXT_MUTED};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 18px;
        border-left: 1px solid {Color.BORDER_SUBTLE};
    }}
    QComboBox QAbstractItemView {{
        background-color: {Color.SURFACE_1};
        border: 1px solid {Color.BORDER_MEDIUM};
        color: {Color.TEXT_PRIMARY};
        selection-background-color: {Color.SURFACE_3};
        selection-color: {Color.TEXT_PRIMARY};
    }}

    /* Review Queue List */
    QListWidget#cueList, QListWidget {{
        background-color: {Color.SURFACE_0};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 6px;
        outline: none;
        padding: 4px;
    }}
    QListWidget#cueList::item, QListWidget::item {{
        background-color: {Color.SURFACE_1};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 6px;
        padding: 6px 8px;
        margin-bottom: 3px;
        color: {Color.TEXT_PRIMARY};
    }}
    QListWidget#cueList::item:hover, QListWidget::item:hover {{
        background-color: {Color.SURFACE_2};
        border-color: {Color.BORDER_MEDIUM};
    }}
    QListWidget#cueList::item:selected, QListWidget::item:selected {{
        background-color: {Color.SURFACE_2};
        border: 1px solid {Color.ACCENT};
        color: {Color.TEXT_PRIMARY};
    }}

    /* Progress Bar */
    QProgressBar {{
        background-color: {Color.SURFACE_0};
        border: 1px solid {Color.BORDER_SUBTLE};
        border-radius: 4px;
        text-align: center;
        font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
        font-size: 10px;
        font-weight: 600;
        color: {Color.TEXT_SECONDARY};
        min-height: 14px;
        max-height: 14px;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0099ff, stop:1 #26abff);
        border-radius: 3px;
    }}

    /* Sliders */
    QSlider::groove:horizontal {{
        height: 4px;
        background-color: {Color.SURFACE_2};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {Color.ACCENT};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background-color: {Color.TEXT_PRIMARY};
        border: 2px solid {Color.ACCENT};
        width: 12px;
        margin-top: -4px;
        margin-bottom: -4px;
        border-radius: 6px;
    }}
    QSlider::handle:horizontal:hover {{
        background-color: #ffffff;
        border-color: {Color.ACCENT_HOVER};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background-color: {Color.SURFACE_0};
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {Color.BORDER_MEDIUM};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {Color.BORDER_STRONG};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {Color.SURFACE_0};
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {Color.BORDER_MEDIUM};
        min-width: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {Color.BORDER_STRONG};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {Color.SURFACE_0};
        border-top: 1px solid {Color.BORDER_SUBTLE};
        color: {Color.TEXT_MUTED};
        font-size: 11px;
    }}
    """
