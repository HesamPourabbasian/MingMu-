"""Compact, low-flicker live dashboard rendering."""

from __future__ import annotations

import shutil
import sys
from datetime import datetime

from mingmu import __app_name__
from mingmu.display.colors import (
    blue,
    bold,
    bright_white,
    cyan,
    dim,
    magenta,
    overall_badge,
)
from mingmu.display.table import BOX, MetricRow, Section, _pad, _visible_len
from mingmu.i18n import t


def _summary_rows(section: Section) -> list[MetricRow]:
    """Choose a small set of useful live metrics for a section."""
    if not section.rows:
        return []

    if section.icon in ("BAT", "CPU"):
        primary = section.rows[0]
        temperature = next(
            (row for row in section.rows if row.label == t("temperature")),
            None,
        )
        if temperature is not None and temperature is not primary:
            return [primary, temperature]
        return [primary]

    if section.icon == "RAM":
        return section.rows[:2]

    return section.rows[:2]


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[:width - 3] + "..."


def _metric_cell(metric: MetricRow | None, width: int) -> str:
    """Render a fixed-width label/value pair for the two-column live view."""
    if metric is None:
        return " " * width

    value_width = min(18, max(12, width // 2))
    label_width = max(1, width - value_width - 1)
    label = _truncate(metric.label.strip(), label_width).ljust(label_width)
    value = _truncate(metric.value, value_width).rjust(value_width)
    return f"{dim(label)} {bright_white(value)}"


def render_live_dashboard(
    sections: list[Section],
    width: int | None = None,
    interval: float = 2.0,
) -> str:
    """Render a compact live view that fits comfortably on a terminal screen."""
    if width is None:
        try:
            width = max(shutil.get_terminal_size().columns, 60)
        except (ValueError, OSError):
            width = 80

    width = max(width, 60)
    inner = width - 2

    def row(content: str = "") -> str:
        return blue(BOX.vertical) + _pad(content, inner) + blue(BOX.vertical)

    def border(color, left: str, right: str) -> str:
        return color(left + BOX.horizontal * inner + right)

    lines = [border(cyan, BOX.top_left, BOX.top_right)]
    title = bold(bright_white(f"  {__app_name__.upper()}  /  SYSTEM MONITOR"))
    live_tag = cyan("[ LIVE ]")
    gap = max(1, inner - _visible_len(title) - _visible_len(live_tag) - 2)
    lines.append(row(title + " " * gap + live_tag + "  "))
    timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    lines.append(row(dim(f"  UPDATED  {timestamp}   |   INTERVAL  {interval:g}s")))
    lines.append(border(blue, BOX.t_right, BOX.t_left))

    for section in sections:
        badge = overall_badge(section.overall_status)
        heading = f"  {magenta(f'[{section.icon}]')}  {bold(bright_white(section.title))}"
        gap = max(2, inner - _visible_len(heading) - _visible_len(badge) - 2)
        lines.append(row(heading + " " * gap + badge + "  "))

        metrics = _summary_rows(section)
        cell_width = max(1, (inner - 4) // 2)
        metric_line = (
            "  "
            + _metric_cell(metrics[0] if metrics else None, cell_width)
            + "  "
            + _metric_cell(metrics[1] if len(metrics) > 1 else None, cell_width)
        )
        lines.append(row(metric_line))

    lines.append(border(blue, BOX.t_right, BOX.t_left))
    lines.append(row(dim(f"  {t('live_monitoring', interval=interval)}")))
    lines.append(border(cyan, BOX.bottom_left, BOX.bottom_right))
    return "\n".join(lines)


class LiveDisplay:
    """Update changed dashboard rows in place instead of clearing the screen."""

    def __init__(self) -> None:
        try:
            self._interactive = sys.stdout.isatty()
        except Exception:
            self._interactive = False
        self._previous_lines: list[str] = []

    def __enter__(self) -> "LiveDisplay":
        if self._interactive:
            sys.stdout.write("\x1b[2J\x1b[H\x1b[?25l")
            sys.stdout.flush()
        return self

    def render(self, frame: str) -> None:
        lines = frame.splitlines()
        if not self._interactive:
            sys.stdout.write(frame + "\n")
            sys.stdout.flush()
            return

        updates: list[str] = []
        for index, line in enumerate(lines):
            if index >= len(self._previous_lines) or line != self._previous_lines[index]:
                updates.append(f"\x1b[{index + 1};1H{line}\x1b[K")

        for index in range(len(lines), len(self._previous_lines)):
            updates.append(f"\x1b[{index + 1};1H\x1b[2K")

        if updates:
            sys.stdout.write("".join(updates))
            sys.stdout.flush()
        self._previous_lines = lines

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._interactive:
            row = max(1, len(self._previous_lines) + 1)
            sys.stdout.write(f"\x1b[{row};1H\x1b[?25h\n")
            sys.stdout.flush()
