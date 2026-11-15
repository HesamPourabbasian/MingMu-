"""
Box-drawing table renderer.

Builds professional terminal tables using Unicode box-drawing
characters, with per-cell colouring via the ``colors`` module.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Sequence

from mingmu import __app_name__, __app_name_cn__, __version__
from mingmu.i18n import t
from mingmu.display.colors import (
    blue,
    bold,
    bright_white,
    cyan,
    dim,
    magenta,
    overall_badge,
    status_badge,
)
from mingmu.utils.platform_detect import get_platform_info
from mingmu.utils.thresholds import Status


# ── Box-drawing character sets ───────────────────────────────

@dataclass(frozen=True, slots=True)
class BoxChars:
    """Characters for drawing table borders."""

    top_left: str = "┌"
    top_right: str = "┐"
    bottom_left: str = "└"
    bottom_right: str = "┘"
    horizontal: str = "─"
    vertical: str = "│"
    t_down: str = "┬"
    t_up: str = "┴"
    t_right: str = "├"
    t_left: str = "┤"
    cross: str = "┼"


BOX = BoxChars()

# Heavy variant for section dividers
HEAVY_H = "━"


# ── Helpers ──────────────────────────────────────────────────

def _visible_len(text: str) -> int:
    """Return the visible (non-ANSI) length of *text*."""
    import re
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


def _pad(text: str, width: int, align: str = "left") -> str:
    """Pad *text* to *width* respecting invisible ANSI escapes."""
    visible = _visible_len(text)
    padding = max(0, width - visible)
    if align == "center":
        left = padding // 2
        right = padding - left
        return " " * left + text + " " * right
    elif align == "right":
        return " " * padding + text
    return text + " " * padding


def get_table_width() -> int:
    """Determine the table width based on terminal size (uses full width)."""
    try:
        cols = shutil.get_terminal_size().columns
    except (ValueError, OSError):
        cols = 80
    # Take full width of terminal (minimum 60 columns)
    return max(cols, 60)


# ── Row data ─────────────────────────────────────────────────

@dataclass(slots=True)
class MetricRow:
    """A single metric to display in a section table."""

    label: str
    value: str
    status: Status = Status.INFO

    def status_text(self) -> str:
        return status_badge(self.status)


@dataclass(slots=True)
class Section:
    """A titled block of metric rows."""

    title: str
    icon: str
    overall_status: Status
    rows: list[MetricRow] = field(default_factory=list)


# ── Table renderer ───────────────────────────────────────────

class TableRenderer:
    """Render sections into a bordered, coloured terminal table."""

    def __init__(self, width: int | None = None) -> None:
        self.width = width or get_table_width()
        # Inner content width (excluding left/right border + padding)
        self.inner = self.width - 2  # minus two │ chars

    # ── Border lines ──

    def _top_border(self) -> str:
        return cyan(BOX.top_left + BOX.horizontal * self.inner + BOX.top_right)

    def _bottom_border(self) -> str:
        return cyan(BOX.bottom_left + BOX.horizontal * self.inner + BOX.bottom_right)

    def _divider(self) -> str:
        return blue(BOX.t_right + BOX.horizontal * self.inner + BOX.t_left)

    def _col_divider(self, col_widths: Sequence[int]) -> str:
        segments = BOX.horizontal * col_widths[0]
        for w in col_widths[1:]:
            segments += BOX.cross + BOX.horizontal * w
        return magenta(BOX.t_right + segments + BOX.t_left)

    def _row(self, content: str, align: str = "center") -> str:
        """A full-width content row."""
        padded = _pad(content, self.inner, align)
        return blue(BOX.vertical) + padded + blue(BOX.vertical)

    def _col_row(self, cells: Sequence[str], col_widths: Sequence[int],
                 aligns: Sequence[str] | None = None) -> str:
        """A row split into columns."""
        if aligns is None:
            aligns = ["left"] * len(cells)
        parts: list[str] = []
        for cell, w, a in zip(cells, col_widths, aligns):
            parts.append(_pad(cell, w, a))
        content = blue(BOX.vertical).join(parts)
        return blue(BOX.vertical) + content + blue(BOX.vertical)

    # ── Build the full output ──

    def render(self, sections: list[Section]) -> str:
        """Render all sections into a complete table string."""
        lines: list[str] = []
        pinfo = get_platform_info()

        # ── Header ──
        lines.append(self._top_border())
        title = bold(cyan(f"◆ {__app_name_cn__}  {__app_name__} ◆"))
        subtitle = dim(f"v{__version__}  ·  {pinfo.system} {pinfo.machine}")
        lines.append(self._row(f"  {title}  "))
        lines.append(self._row(f"  {subtitle}  "))
        lines.append(self._divider())

        # ── Timestamp row ──
        from datetime import datetime

        ts = dim(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        lines.append(self._row(f"  {ts}  "))

        # ── Sections ──
        for section in sections:
            lines.append(self._divider())
            self._render_section(lines, section)

        lines.append(self._bottom_border())
        return "\n".join(lines)

    def _render_section(self, lines: list[str], section: Section) -> None:
        """Render one metric section (header + data rows)."""
        # Section header
        badge = overall_badge(section.overall_status)
        header_text = f"  {magenta(section.icon)}  {bold(bright_white(section.title))}"
        # Calculate padding so badge is right-aligned
        header_visible_len = _visible_len(header_text) + _visible_len(badge) + 4
        gap = max(1, self.inner - header_visible_len)
        header_line = header_text + " " * gap + badge + "  "
        lines.append(blue(BOX.vertical) + _pad(header_line, self.inner) + blue(BOX.vertical))

        if not section.rows:
            lines.append(self._row(dim(f"  {t('no_data_available', default='No data available')}")))
            return

        # Column layout: | Metric | Value | Status |
        col1_w = max(22, self.inner * 35 // 100)  # ~35%
        col3_w = max(16, self.inner * 25 // 100)   # ~25%
        col2_w = self.inner - col1_w - col3_w - 2   # remainder minus 2 separators

        col_widths = [col1_w, col2_w, col3_w]

        # Column header
        lines.append(self._col_divider(col_widths))
        lines.append(self._col_row(
            [dim(f"  {t('col_metric', default='Metric')}"),
             dim(f"  {t('col_value', default='Value')}"),
             dim(f"  {t('col_status', default='Status')}")],
            col_widths,
        ))
        lines.append(self._col_divider(col_widths))

        # Data rows
        for row in section.rows:
            lines.append(self._col_row(
                [f"  {row.label}", f"  {bright_white(row.value)}", f"  {row.status_text()}"],
                col_widths,
            ))
