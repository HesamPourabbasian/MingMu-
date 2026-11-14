"""
CPU metrics collector.

Gathers CPU usage, frequency, core counts, load averages, temperature,
and top processes.  Computes an overall condition from thresholds.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import psutil

from mingmu.display.formatters import (
    count,
    frequency,
    load_average,
    percent,
    temperature,
)
from mingmu.display.table import MetricRow, Section
from mingmu.utils.platform_detect import is_linux, is_macos, is_windows
from mingmu.utils.thresholds import (
    CPU_LOAD_FACTOR,
    CPU_TEMPERATURE,
    CPU_USAGE,
    Status,
)

log = logging.getLogger(__name__)


# ── Data container ───────────────────────────────────────────

@dataclass(slots=True)
class CPUInfo:
    """Raw CPU metrics."""

    usage_percent: float | None = None
    per_core_usage: list[float] = field(default_factory=list)
    physical_cores: int | None = None
    logical_cores: int | None = None
    freq_current_mhz: float | None = None
    freq_min_mhz: float | None = None
    freq_max_mhz: float | None = None
    temperature_c: float | None = None
    load_avg_1: float | None = None
    load_avg_5: float | None = None
    load_avg_15: float | None = None
    load_factor: float | None = None  # load_avg_1 / logical_cores
    top_processes: list[tuple[str, float]] = field(default_factory=list)


# ── Temperature helpers ──────────────────────────────────────

def _get_cpu_temperature() -> float | None:
    """Best-effort CPU temperature reading."""
    # Linux: psutil.sensors_temperatures()
    if is_linux():
        try:
            temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
            for name in ("coretemp", "k10temp", "cpu_thermal", "cpu-thermal", "acpitz"):
                if name in temps and temps[name]:
                    # Return highest core temp
                    return max(s.current for s in temps[name])
        except (AttributeError, Exception) as exc:
            log.debug("Linux temperature read failed: %s", exc)

    # macOS: IOHIDEventSystem thermal sensors (works on Apple Silicon & Intel)
    if is_macos():
        try:
            from mingmu.utils.macos_sensors import get_macos_thermal_readings
            thermals = get_macos_thermal_readings()
            if thermals.cpu_temp_c is not None:
                return thermals.cpu_temp_c
        except Exception as exc:
            log.debug("macOS CPU temperature read failed: %s", exc)

    # Windows: ACPI Thermal Zone queries
    if is_windows():
        try:
            from mingmu.utils.windows_sensors import get_windows_thermal_readings
            win_thermals = get_windows_thermal_readings()
            if win_thermals.cpu_temp_c is not None:
                return win_thermals.cpu_temp_c
        except Exception as exc:
            log.debug("Windows CPU temperature read failed: %s", exc)

    return None


# ── Top processes ────────────────────────────────────────────

def _get_top_cpu_processes(n: int = 3) -> list[tuple[str, float]]:
    """Return the top *n* CPU-consuming processes as (name, cpu%)."""
    try:
        procs: list[tuple[str, float]] = []
        for proc in psutil.process_iter(["name", "cpu_percent"]):
            try:
                cpu = proc.info["cpu_percent"] or 0.0  # type: ignore[index]
                name = proc.info["name"] or "?"  # type: ignore[index]
                procs.append((name, cpu))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x[1], reverse=True)
        return procs[:n]
    except Exception as exc:
        log.debug("Top process listing failed: %s", exc)
        return []


# ── Public API ───────────────────────────────────────────────

def collect_cpu() -> CPUInfo:
    """Collect CPU metrics from all available sources."""
    info = CPUInfo()

    # Overall usage (blocking call — brief sample)
    info.usage_percent = psutil.cpu_percent(interval=0.5)

    # Per-core usage
    info.per_core_usage = psutil.cpu_percent(interval=0, percpu=True)

    # Core counts
    info.physical_cores = psutil.cpu_count(logical=False)
    info.logical_cores = psutil.cpu_count(logical=True)

    # Frequency
    freq = psutil.cpu_freq()
    if freq:
        info.freq_current_mhz = freq.current
        info.freq_min_mhz = freq.min if freq.min else None
        info.freq_max_mhz = freq.max if freq.max else None

    # Load averages (POSIX systems only)
    if hasattr(os, "getloadavg"):
        try:
            la1, la5, la15 = os.getloadavg()
            info.load_avg_1 = round(la1, 2)
            info.load_avg_5 = round(la5, 2)
            info.load_avg_15 = round(la15, 2)
            if info.logical_cores and info.logical_cores > 0:
                info.load_factor = round(la1 / info.logical_cores, 2)
        except (OSError, AttributeError):
            pass

    # Temperature
    info.temperature_c = _get_cpu_temperature()

    # Top processes
    info.top_processes = _get_top_cpu_processes()

    return info


def build_cpu_section(info: CPUInfo | None = None) -> Section:
    """Build a table ``Section`` for CPU metrics."""
    if info is None:
        info = collect_cpu()

    rows: list[MetricRow] = []

    # Overall usage
    usage_status = CPU_USAGE.evaluate(info.usage_percent)
    rows.append(MetricRow("Overall Usage", percent(info.usage_percent), usage_status))

    # Per-core summary (min / max)
    if info.per_core_usage:
        core_min = min(info.per_core_usage)
        core_max = max(info.per_core_usage)
        rows.append(MetricRow(
            "Core Range",
            f"{percent(core_min)} – {percent(core_max)}",
            Status.INFO,
        ))

    # Temperature
    temp_status = CPU_TEMPERATURE.evaluate(info.temperature_c)
    rows.append(MetricRow("Temperature", temperature(info.temperature_c), temp_status))

    # Frequency
    if info.freq_current_mhz:
        freq_label = frequency(info.freq_current_mhz)
        if info.freq_max_mhz and info.freq_max_mhz > 0:
            freq_label += f" / {frequency(info.freq_max_mhz)}"
        rows.append(MetricRow("Frequency", freq_label, Status.INFO))

    # Core count
    rows.append(MetricRow(
        "Cores (Phys / Logical)",
        f"{count(info.physical_cores)} / {count(info.logical_cores)}",
        Status.INFO,
    ))

    # Load average
    if info.load_avg_1 is not None:
        load_str = (
            f"{load_average(info.load_avg_1)}  "
            f"{load_average(info.load_avg_5)}  "
            f"{load_average(info.load_avg_15)}"
        )
        load_status = CPU_LOAD_FACTOR.evaluate(info.load_factor)
        rows.append(MetricRow("Load Avg (1 · 5 · 15m)", load_str, load_status))
    elif is_windows():
        rows.append(MetricRow("Load Avg (1 · 5 · 15m)", "N/A (POSIX only)", Status.INFO))

    # Top processes
    for name, cpu_pct in info.top_processes:
        if cpu_pct > 0:
            rows.append(MetricRow(
                f"  ↳ {name[:20]}",
                percent(cpu_pct),
                Status.INFO,
            ))

    # Overall
    all_statuses = [usage_status, temp_status]
    if info.load_factor is not None:
        all_statuses.append(CPU_LOAD_FACTOR.evaluate(info.load_factor))

    if Status.CRITICAL in all_statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(title="CPU", icon="🖥 ", overall_status=overall, rows=rows)
