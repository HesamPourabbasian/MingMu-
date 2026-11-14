"""
Value formatters for human-readable display.

Every formatter accepts a raw numeric value and returns a short,
consistently formatted string suitable for table cells.
"""

from __future__ import annotations


def bytes_to_human(n: int | float | None) -> str:
    """Convert bytes to a human-readable string (e.g. ``8.4 GB``)."""
    if n is None:
        return "N/A"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def percent(value: float | None, decimals: int = 1) -> str:
    """Format a percentage value (e.g. ``78.3%``)."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def temperature(celsius: float | None) -> str:
    """Format a temperature in Celsius (e.g. ``42.5°C``)."""
    if celsius is None:
        return "N/A"
    return f"{celsius:.1f}°C"


def frequency(mhz: float | None) -> str:
    """Format a CPU frequency (e.g. ``3.20 GHz`` or ``800 MHz``)."""
    if mhz is None:
        return "N/A"
    if mhz >= 1000:
        return f"{mhz / 1000:.2f} GHz"
    return f"{mhz:.0f} MHz"


def seconds_to_human(seconds: int | float | None) -> str:
    """Convert seconds to ``Xh Ym`` or ``Xm Ys`` format."""
    if seconds is None or seconds < 0:
        return "N/A"
    seconds = int(seconds)
    if seconds == 0:
        return "0s"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not hours:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


def count(value: int | None) -> str:
    """Format an integer count, returning ``N/A`` for ``None``."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def load_average(value: float | None) -> str:
    """Format a load average value."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"
