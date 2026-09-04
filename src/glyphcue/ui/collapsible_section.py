from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from glyphcue.ui.design_tokens import Color, Spacing


class CollapsibleSection(QWidget):
    """A VS Code-style collapsible work area / disclosure panel (Phase B.2 & B.3).

    Participates in resizable vertical allocations (e.g. QSplitter).
    Renders a persistent compact header with disclosure arrow (▼ when expanded,
    ▶ when collapsed), optionally wraps its content in a vertical scroll area,
    and locks/unlocks height bounds cleanly when toggled.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        content: QWidget | None = None,
        expanded: bool = True,
        scrollable_content: bool = False,
        min_expanded_height: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        self.min_expanded_height = min_expanded_height
        self._scrollable_content = scrollable_content

        self._header_button = QPushButton()
        self._header_button.setObjectName("disclosureHeaderBtn")
        self._header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header_button.setStyleSheet(
            f"""
            QPushButton#disclosureHeaderBtn {{
                background-color: {Color.SURFACE_1};
                border: 1px solid {Color.BORDER_SUBTLE};
                border-radius: 4px;
                color: {Color.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-align: left;
                padding: 4px 8px;
                min-height: 20px;
                max-height: 20px;
            }}
            QPushButton#disclosureHeaderBtn:hover {{
                background-color: {Color.SURFACE_2};
                color: {Color.TEXT_PRIMARY};
                border-color: {Color.BORDER_MEDIUM};
            }}
            """
        )
        self._header_button.clicked.connect(self.toggle)

        self._content_widget = content or QWidget()
        if content is None:
            self._content_layout = QVBoxLayout(self._content_widget)
            self._content_layout.setContentsMargins(0, Spacing.COMPACT, 0, Spacing.STANDARD)
            self._content_layout.setSpacing(Spacing.COMPACT)
        else:
            self._content_layout = self._content_widget.layout()  # type: ignore[assignment]

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._header_button)

        if self._scrollable_content:
            self._scroll_area = QScrollArea()
            self._scroll_area.setObjectName("sectionScrollArea")
            self._scroll_area.setWidgetResizable(True)
            self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll_area.setWidget(self._content_widget)
            self._container_widget = self._scroll_area
        else:
            self._container_widget = self._content_widget

        main_layout.addWidget(self._container_widget)
        self._refresh_state()

    def header_text(self) -> str:
        return self._header_button.text()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._refresh_state()
        self.toggled.emit(self._expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def add_widget(self, widget: QWidget) -> None:
        if self._content_layout is not None:
            self._content_layout.addWidget(widget)

    def insert_widget(self, index: int, widget: QWidget) -> None:
        if self._content_layout is not None:
            self._content_layout.insertWidget(index, widget)

    @property
    def content_widget(self) -> QWidget:
        return self._content_widget

    @property
    def content_layout(self) -> QVBoxLayout | None:
        return self._content_layout

    def _refresh_state(self) -> None:
        indicator = "▼" if self._expanded else "▶"
        self._header_button.setText(f"{indicator}  {self._title}")
        self._container_widget.setVisible(self._expanded)
        if self._expanded:
            self.setMinimumHeight(self.min_expanded_height)
            self.setMaximumHeight(16777215)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        else:
            self.setMinimumHeight(0)
            self.setMaximumHeight(30)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
