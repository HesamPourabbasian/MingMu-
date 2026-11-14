"""
Memory (RAM) metrics collector.

Gathers physical memory usage, available memory, swap statistics, and
computes a health condition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psutil

from mingmu.display.formatters import bytes_to_human, percent
from mingmu.display.table import MetricRow, Section
from mingmu.utils.thresholds import MEMORY_USAGE, SWAP_USAGE, Status

log = logging.getLogger(__name__)


# ── Data container ───────────────────────────────────────────

@dataclass(slots=True)
class MemoryInfo:
    """Raw memory metrics."""

    total: int = 0
    used: int = 0
    available: int = 0
    percent_used: float = 0.0
    cached: int = 0
    buffers: int = 0
    swap_total: int = 0
    swap_used: int = 0
    swap_free: int = 0
    swap_percent: float = 0.0


# ── Public API ───────────────────────────────────────────────

def collect_memory() -> MemoryInfo:
    """Collect memory metrics via psutil."""
    info = MemoryInfo()

    vm = psutil.virtual_memory()
    info.total = vm.total
    info.used = vm.used
    info.available = vm.available
    info.percent_used = round(vm.percent, 1)

    # cached / buffers may not be available on all platforms
    info.cached = getattr(vm, "cached", 0)
    info.buffers = getattr(vm, "buffers", 0)

    swap = psutil.swap_memory()
    info.swap_total = swap.total
    info.swap_used = swap.used
    info.swap_free = swap.free
    info.swap_percent = round(swap.percent, 1)

    return info


def build_memory_section(info: MemoryInfo | None = None) -> Section:
    """Build a table ``Section`` for memory metrics."""
    if info is None:
        info = collect_memory()

    rows: list[MetricRow] = []

    # Used / Total
    mem_status = MEMORY_USAGE.evaluate(info.percent_used)
    rows.append(MetricRow(
        "Used / Total",
        f"{bytes_to_human(info.used)} / {bytes_to_human(info.total)}",
        mem_status,
    ))

    # Usage percentage
    rows.append(MetricRow("Usage", percent(info.percent_used), mem_status))

    # Available
    rows.append(MetricRow("Available", bytes_to_human(info.available), Status.INFO))

    # Cached (Linux mainly)
    if info.cached > 0:
        rows.append(MetricRow("Cached", bytes_to_human(info.cached), Status.INFO))

    # Swap
    if info.swap_total > 0:
        swap_status = SWAP_USAGE.evaluate(info.swap_percent)
        rows.append(MetricRow(
            "Swap Used / Total",
            f"{bytes_to_human(info.swap_used)} / {bytes_to_human(info.swap_total)}",
            swap_status,
        ))
        rows.append(MetricRow("Swap Usage", percent(info.swap_percent), swap_status))
    else:
        rows.append(MetricRow("Swap", "Not configured", Status.INFO))

    # Overall
    all_statuses = [mem_status]
    if info.swap_total > 0:
        all_statuses.append(SWAP_USAGE.evaluate(info.swap_percent))

    if Status.CRITICAL in all_statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(title="MEMORY", icon="💾", overall_status=overall, rows=rows)
