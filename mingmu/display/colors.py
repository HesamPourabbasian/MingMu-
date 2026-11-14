"""
Colorama-based colour palette and helpers.

All colour logic is isolated here so the rest of the codebase never
imports ``colorama`` directly.  Disabling colour output is a single
flag flip.
"""

from __future__ import annotations

from colorama import Fore, Style, init as colorama_init

from mingmu.i18n import t
from mingmu.utils.thresholds import Status

# Initialise colorama (autoreset so we don't leak colours).
colorama_init(autoreset=True)

# ── Private state ────────────────────────────────────────────

_colors_enabled: bool = True


def disable_colors() -> None:
    """Globally disable coloured output."""
    global _colors_enabled
    _colors_enabled = False


def enable_colors() -> None:
    """Globally enable coloured output."""
    global _colors_enabled
    _colors_enabled = True


def colors_enabled() -> bool:
    """Return whether colours are currently enabled."""
    return _colors_enabled


# ── Low-level painters ───────────────────────────────────────

def _paint(text: str, color: str) -> str:
    if not _colors_enabled:
        return text
    return f"{color}{text}{Style.RESET_ALL}"


def green(text: str) -> str:
    return _paint(text, Fore.GREEN)


def yellow(text: str) -> str:
    return _paint(text, Fore.YELLOW)


def red(text: str) -> str:
    return _paint(text, Fore.RED)


def cyan(text: str) -> str:
    return _paint(text, Fore.CYAN)


def blue(text: str) -> str:
    return _paint(text, Fore.BLUE)


def magenta(text: str) -> str:
    return _paint(text, Fore.MAGENTA)


def white(text: str) -> str:
    return _paint(text, Fore.WHITE)


def bright_white(text: str) -> str:
    return _paint(text, Style.BRIGHT + Fore.WHITE)


def dim(text: str) -> str:
    return _paint(text, Style.DIM)


def bold(text: str) -> str:
    return _paint(text, Style.BRIGHT)


# ── Semantic helpers ─────────────────────────────────────────

# Map status → colour function
_STATUS_COLORS: dict[Status, callable] = {
    Status.GOOD: green,
    Status.WARNING: yellow,
    Status.CRITICAL: red,
    Status.UNKNOWN: dim,
    Status.INFO: cyan,
    Status.CHARGING: cyan,
}

# Map status → dot indicator
_STATUS_INDICATORS: dict[Status, str] = {
    Status.GOOD: "●",
    Status.WARNING: "▲",
    Status.CRITICAL: "✖",
    Status.UNKNOWN: "○",
    Status.INFO: "ℹ",
    Status.CHARGING: "⚡",
}


def status_color(text: str, status: Status) -> str:
    """Colour *text* according to *status*."""
    painter = _STATUS_COLORS.get(status, dim)
    return painter(text)


def status_badge(status: Status) -> str:
    """Return a coloured ``● Status`` badge."""
    indicator = _STATUS_INDICATORS.get(status, "○")
    label = t(f"status_{status.value.lower()}", default=status.value)
    return status_color(f"{indicator} {label}", status)


def overall_badge(status: Status) -> str:
    """Return a coloured ``[STATUS]`` tag for section headers."""
    label = t(f"status_{status.value.lower()}", default=status.value).upper()
    return status_color(f"[{label}]", status)
