"""
Comprehensive interactive Help & Documentation view for MingMu (明眸).
"""

from __future__ import annotations

import shutil
from mingmu import __app_name__, __app_name_cn__, __version__
from mingmu.display.colors import (
    blue,
    bold,
    bright_white,
    cyan,
    dim,
    green,
    magenta,
    red,
    status_badge,
    yellow,
)
from mingmu.display.table import BOX, _pad, _visible_len
from mingmu.i18n import get_language
from mingmu.i18n.help_translations import HELP_DATA
from mingmu.utils.thresholds import Status


def _pad_cell(text: str, width: int) -> str:
    """Pad *text* to *width* taking into account ANSI escape codes."""
    vis = _visible_len(text)
    pad = max(0, width - vis)
    return text + (" " * pad)


def render_help_view(width: int | None = None) -> str:
    """Render the full MingMu reference guide and help manual at full terminal width."""
    try:
        term_width = width or max(shutil.get_terminal_size().columns, 70)
    except Exception:
        term_width = 80

    inner = term_width - 2

    lines: list[str] = []

    def border_top() -> str:
        return cyan(BOX.top_left + BOX.horizontal * inner + BOX.top_right)

    def border_mid() -> str:
        return magenta(BOX.t_right + BOX.horizontal * inner + BOX.t_left)

    def border_bottom() -> str:
        return cyan(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right)

    def row(text: str = "", align: str = "left") -> str:
        return blue(BOX.vertical) + _pad(f"  {text}  " if text else "", inner, align) + blue(BOX.vertical)

    def header(title: str) -> None:
        lines.append(border_mid())
        lines.append(row(bold(magenta(title))))
        lines.append(border_mid())

    # Get active language data
    lang = get_language()
    data = HELP_DATA.get(lang, HELP_DATA["en"])

    # Header Card
    lines.append(border_top())
    lines.append(row(bold(bright_white(f"{__app_name_cn__}  {__app_name__}  ·  {data['guide_title']}")), "center"))
    lines.append(row(dim(f"v{__version__}  ·  {data['guide_subtitle']}"), "center"))

    # 1. Overview
    header(data["sec1_title"])
    for line in data["sec1_lines"]:
        lines.append(row(line))

    # 2. Status Indicators & Health Badges
    header(data["sec2_title"])
    badge_w = 15
    lines.append(row(f"{_pad_cell(status_badge(Status.GOOD), badge_w)} : {data['badge_good']}"))
    lines.append(row(f"{_pad_cell(status_badge(Status.WARNING), badge_w)} : {data['badge_warning']}"))
    lines.append(row(f"{_pad_cell(status_badge(Status.CRITICAL), badge_w)} : {data['badge_critical']}"))
    lines.append(row(f"{_pad_cell(status_badge(Status.UNKNOWN), badge_w)} : {data['badge_unknown']}"))
    lines.append(row(f"{_pad_cell(status_badge(Status.INFO), badge_w)} : {data['badge_info']}"))

    # 3. Battery Health & Diagnostics
    header(data["sec3_title"])
    for label, desc in data["sec3_items"]:
        lines.append(row(bold(f"• {label}") + f" : {desc}"))

    # 4. CPU & Thermal Metrics
    header(data["sec4_title"])
    for label, desc in data["sec4_items"]:
        lines.append(row(bold(f"• {label}") + f" : {desc}"))

    # 5. Memory (RAM) & Swap Saturation
    header(data["sec5_title"])
    for label, desc in data["sec5_items"]:
        lines.append(row(bold(f"• {label}") + f" : {desc}"))

    # 6. Command-Line Shortcuts & Usage
    header(data["sec6_title"])
    for cmd, desc in data["sec6_items"]:
        lines.append(row(f"{_pad_cell(bright_white(cmd), 24)} {desc}"))

    lines.append(border_bottom())
    return "\n".join(lines)
