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
    yellow,
)
from mingmu.display.table import BOX, _pad


def render_help_view(width: int | None = None) -> str:
    """Render the full MingMu reference guide and help manual at full terminal width."""
    try:
        term_width = width or max(shutil.get_terminal_size().columns, 70)
    except Exception:
        term_width = 80

    inner = term_width - 2

    lines: list[str] = []

    def border_top():
        return blue(BOX.top_left + BOX.horizontal * inner + BOX.top_right)

    def border_mid():
        return blue(BOX.t_right + BOX.horizontal * inner + BOX.t_left)

    def border_bottom():
        return blue(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right)

    def row(text: str = "", align: str = "left"):
        return blue(BOX.vertical) + _pad(f"  {text}  " if text else "", inner, align) + blue(BOX.vertical)

    def header(title: str):
        lines.append(border_mid())
        lines.append(row(bold(cyan(title))))
        lines.append(border_mid())

    # Header
    lines.append(border_top())
    lines.append(row(bold(bright_white(f"{__app_name_cn__}  {__app_name__}  ·  HELP & DOCUMENTATION GUIDE")), "center"))
    lines.append(row(dim(f"v{__version__}  ·  Professional System Health Monitor"), "center"))

    # 1. Overview
    header("1. ABOUT MINGMU (明眸)")
    lines.append(row("MingMu (明眸, meaning 'Bright Eyes') is a high-performance system"))
    lines.append(row("health monitor engineered for macOS, POSIX Linux, and Windows."))
    lines.append(row("It tracks thermal health, battery condition, processor loads, and"))
    lines.append(row("memory saturation to diagnose bottlenecks and prevent thermal throttling."))

    # 2. Status Indicators
    header("2. STATUS INDICATORS & HEALTH BADGES")
    lines.append(row(f"{green('● GOOD')}      : Operating well within optimal parameters. No action needed."))
    lines.append(row(f"{yellow('▲ WARNING')}   : Metric is elevated above typical baseline. Monitor closely."))
    lines.append(row(f"{red('✖ CRITICAL')}  : Operating near or at hardware limit. Requires immediate attention."))
    lines.append(row(f"{dim('○ UNKNOWN')}   : Metric unavailable or unreadable by system permissions."))
    lines.append(row(f"{cyan('ℹ INFO')}      : Informational hardware or runtime attribute."))

    # 3. Battery Health & Diagnostics
    header("3. BATTERY HEALTH & DIAGNOSTICS")
    lines.append(row(bold("• Health Condition") + " : Sourced from official OS battery management."))
    lines.append(row("  - 'Normal': Battery operating with healthy chemical capacitance."))
    lines.append(row("  - 'Service Recommended': Capacity degraded below 80% or cell error."))
    lines.append(row(bold("• Maximum Capacity") + " : Calibrated ratio of full charge vs design capacity."))
    lines.append(row("  Healthy batteries generally remain above 80% for 500-1000 charge cycles."))
    lines.append(row(bold("• Cycle Count") + " : Total discharge cycles accumulated. Most laptop cells"))
    lines.append(row("  are rated for 1,000 cycles before requiring replacement."))
    lines.append(row(bold("• Temperature") + " : Monitored via battery gas gauge sensors (IOHID/sysfs)."))
    lines.append(row("  Healthy range is < 35.0°C. Warning: 35–45°C. Critical: > 45°C."))

    # 4. CPU Metrics & Architecture
    header("4. CPU & THERMAL METRICS")
    lines.append(row(bold("• Overall & Per-Core Usage") + " : Real-time active compute utilization."))
    lines.append(row(bold("• Apple Silicon Thermals") + " : Direct IOHID event monitoring for:"))
    lines.append(row("  - Performance Cores (pACC): High-frequency compute cores."))
    lines.append(row("  - Efficiency Cores (eACC): Low-power background compute cores."))
    lines.append(row("  - SoC Die Temp: Core silicon substrate junction temperature."))
    lines.append(row(bold("• Load Averages (1m, 5m, 15m)") + " : Average system queue depth."))
    lines.append(row("  Load Factor = 1m Load / Logical Cores. Factor > 1.0 indicates queued tasks."))

    # 5. Memory & Swap Saturation
    header("5. MEMORY (RAM) & SWAP SATURATION")
    lines.append(row(bold("• Physical Memory") + " : Breakdowns of Used, Available, Free, and Wired."))
    lines.append(row("  - Wired: OS kernel and critical buffers that cannot be paged to disk."))
    lines.append(row(bold("• Swap Memory") + " : Virtual memory written to SSD storage when RAM is exhausted."))
    lines.append(row("  Excessive swap usage (>50%) causes disk thrashing and UI stuttering."))

    # 6. Command Line Interface (CLI)
    header("6. COMMAND-LINE SHORTCUTS & USAGE")
    lines.append(row(f"{bright_white('mingmu')}                  Open the interactive visual menu."))
    lines.append(row(f"{bright_white('mingmu --all')}            Print full system overview table."))
    lines.append(row(f"{bright_white('mingmu battery')}          Display battery metrics table."))
    lines.append(row(f"{bright_white('mingmu battery -a')}       Display advanced battery breakdown."))
    lines.append(row(f"{bright_white('mingmu cpu')}              Display CPU metrics table."))
    lines.append(row(f"{bright_white('mingmu cpu -a')}           Display advanced CPU & per-core table."))
    lines.append(row(f"{bright_white('mingmu ram')}              Display memory metrics table."))
    lines.append(row(f"{bright_white('mingmu ram -a')}           Display advanced memory table."))
    lines.append(row(f"{bright_white('mingmu watch')}            Launch live auto-refresh dashboard."))
    lines.append(row(f"{bright_white('mingmu --json')}           Export all metrics in clean JSON."))
    lines.append(row(f"{bright_white('mingmu --no-color')}       Disable ANSI colors for plain logs."))

    lines.append(border_bottom())
    return "\n".join(lines)
