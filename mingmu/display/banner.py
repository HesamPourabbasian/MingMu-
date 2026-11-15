"""
ASCII banner and visual art for MingMu (明眸).
"""

from __future__ import annotations

import shutil
from mingmu import __app_name__, __app_name_cn__, __version__
from mingmu.display.colors import blue, bold, bright_white, cyan, dim, magenta
from mingmu.utils.platform_detect import get_platform_info


# High-impact block ASCII art for MINGMU
ASCII_ART_LINES = [
    r"███╗   ███╗██╗███╗   ██╗ ██████╗ ███╗   ███╗██╗   ██╗",
    r"████╗ ████║██║████╗  ██║██╔════╝ ████╗ ████║██║   ██║",
    r"██╔████╔██║██║██╔██╗ ██║██║  ███╗██╔████╔██║██║   ██║",
    r"██║╚██╔╝██║██║██║╚██╗██║██║   ██║██║╚██╔╝██║██║   ██║",
    r"██║ ╚═╝ ██║██║██║ ╚████║╚██████╔╝██║ ╚═╝ ██║╚██████╔╝",
    r"╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ",
]

# Color gradient progression across lines
_LINE_COLORS = [cyan, cyan, blue, blue, magenta, magenta]


def get_banner(compact: bool = False, width: int | None = None) -> str:
    """Generate the styled, colored ASCII art banner centered to full terminal width."""
    lines: list[str] = []

    # Use full terminal width for centering
    if width is None:
        try:
            term_width = max(shutil.get_terminal_size().columns, 60)
        except Exception:
            term_width = 80
    else:
        term_width = width

    lines.append("")
    eyebrow = "github.com/HesamPourabbasian"
    eyebrow_padding = max(0, (term_width - len(eyebrow)) // 2)
    lines.append(" " * eyebrow_padding + magenta(eyebrow))

    for i, line in enumerate(ASCII_ART_LINES):
        color_func = _LINE_COLORS[i % len(_LINE_COLORS)]
        # Center line
        padding = max(0, (term_width - len(line)) // 2)
        lines.append(" " * padding + bold(color_func(line)))

    rail_width = min(64, max(12, term_width - 8))
    rail = "+" + "-" * (rail_width - 2) + "+"
    lines.append(" " * max(0, (term_width - rail_width) // 2) + cyan(rail))

    # Sub-header with Chinese characters and tagline
    sub = f"「 {bold(bright_white(__app_name_cn__))} 」  ·  B R I G H T   E Y E S  ·  v{__version__}"
    # remove visible escape length for padding
    import re
    clean_sub = re.sub(r"\x1b\[[0-9;]*m", "", sub)
    padding_sub = max(0, (term_width - len(clean_sub)) // 2)
    lines.append(" " * padding_sub + cyan(sub))

    telemetry = "# sensors: battery | cpu | memory"
    padding_telemetry = max(0, (term_width - len(telemetry)) // 2)
    lines.append(" " * padding_telemetry + magenta(telemetry))

    # Platform subtitle
    pinfo = get_platform_info()
    plat_str = f"{pinfo.system} ({pinfo.machine})  ·  Kernel {pinfo.release.split('.')[0]}  ·  Python {pinfo.python_version}"
    padding_plat = max(0, (term_width - len(plat_str)) // 2)
    lines.append(" " * padding_plat + dim(plat_str))
    lines.append("")

    return "\n".join(lines)


def get_bar_width(term_width: int | None = None) -> int:
    """Compute dynamic progress bar width that scales with terminal size."""
    if term_width is None:
        try:
            cols = shutil.get_terminal_size().columns
        except Exception:
            cols = 80
    else:
        cols = term_width
    return max(16, min(50, cols * 26 // 100))


def render_progress_bar(
    percent_val: float,
    width: int | None = None,
    filled_char: str = "█",
    empty_char: str = "░",
) -> str:
    """Return a styled progress bar string: [██████░░░░░░] 50.0%."""
    from mingmu.display.colors import cyan, green, yellow, red, dim
    bar_width = width if width is not None else get_bar_width()
    clamped = max(0.0, min(100.0, percent_val))
    filled_len = int(round(clamped / 100.0 * bar_width))
    empty_len = bar_width - filled_len
    
    if clamped < 70.0:
        bar_color = green
    elif clamped < 90.0:
        bar_color = yellow
    else:
        bar_color = red
        
    bar = bar_color(filled_char * filled_len) + dim(empty_char * empty_len)
    return f"{cyan('[')}{bar}{cyan(']')} {percent_val:.1f}%"
