"""
Graphics Processing Unit (GPU) metrics collector.

Gathers graphics card telemetry across macOS (Apple Silicon / Intel Metal),
Linux (NVIDIA SMI, AMD sysfs, DRM), and Windows (WMI VideoController & NVIDIA).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

from mingmu.display.banner import render_progress_bar
from mingmu.display.formatters import bytes_to_human, count, percent, temperature
from mingmu.display.table import MetricRow, Section
from mingmu.i18n import t
from mingmu.utils.platform_detect import is_linux, is_macos, is_windows
from mingmu.utils.thresholds import GPU_MEMORY, GPU_TEMPERATURE, GPU_USAGE, Status

log = logging.getLogger(__name__)


# ── Data container ───────────────────────────────────────────

@dataclass(slots=True)
class GPUInfo:
    """Raw graphics card / display adapter metrics."""

    present: bool = False
    name: str = "Unknown"
    vendor: str | None = None
    core_count: int | None = None
    driver_version: str | None = None
    api_support: str | None = None
    temperature_c: float | None = None
    usage_percent: float | None = None
    memory_total_bytes: int | None = None
    memory_used_bytes: int | None = None
    memory_free_bytes: int | None = None
    memory_percent: float | None = None
    is_unified_memory: bool = False
    displays: list[str] = field(default_factory=list)


# ── NVIDIA SMI helper (Cross-Platform) ───────────────────────

def _collect_nvidia(info: GPUInfo) -> bool:
    """Attempt telemetry collection via nvidia-smi if available."""
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return False

    try:
        cmd = [
            nvsmi,
            "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        raw = subprocess.check_output(cmd, text=True, timeout=2.5, stderr=subprocess.DEVNULL)
        line = raw.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]

        if len(parts) >= 7:
            info.present = True
            info.name = parts[0]
            info.vendor = "NVIDIA"
            info.driver_version = parts[1]

            # VRAM (reported in MiB)
            try:
                tot_mb = float(parts[2])
                used_mb = float(parts[3])
                free_mb = float(parts[4])
                info.memory_total_bytes = int(tot_mb * 1024 * 1024)
                info.memory_used_bytes = int(used_mb * 1024 * 1024)
                info.memory_free_bytes = int(free_mb * 1024 * 1024)
                if tot_mb > 0:
                    info.memory_percent = round((used_mb / tot_mb) * 100.0, 1)
            except (ValueError, TypeError):
                pass

            # Utilization %
            try:
                info.usage_percent = float(parts[5])
            except (ValueError, TypeError):
                pass

            # Temperature °C
            try:
                info.temperature_c = float(parts[6])
            except (ValueError, TypeError):
                pass

            return True
    except Exception as exc:
        log.debug("nvidia-smi collection failed: %s", exc)

    return False


# ── macOS collector ──────────────────────────────────────────

def _collect_macos(info: GPUInfo) -> None:
    """Enrich GPU telemetry on macOS via system_profiler and IOHID."""
    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            text=True,
            timeout=3.0,
            stderr=subprocess.DEVNULL,
        )
        info.present = True

        for line in raw.splitlines():
            line_s = line.strip()
            if "Chipset Model:" in line_s:
                info.name = line_s.split(":", 1)[1].strip()
            elif "Vendor:" in line_s and not info.vendor:
                info.vendor = line_s.split(":", 1)[1].strip()
            elif "Total Number of Cores:" in line_s and info.core_count is None:
                c_match = re.search(r"\d+", line_s)
                if c_match:
                    info.core_count = int(c_match.group())
            elif "Metal Support:" in line_s or "Metal Family:" in line_s:
                info.api_support = line_s.split(":", 1)[1].strip()
            elif "VRAM (Total):" in line_s or "VRAM (Dynamic, Max):" in line_s:
                vram_str = line_s.split(":", 1)[1].strip()
                # Parse e.g. "8 GB" or "1536 MB"
                num_match = re.search(r"(\d+)\s*(GB|MB)", vram_str, re.IGNORECASE)
                if num_match:
                    val = int(num_match.group(1))
                    unit = num_match.group(2).upper()
                    if unit == "GB":
                        info.memory_total_bytes = val * 1024**3
                    elif unit == "MB":
                        info.memory_total_bytes = val * 1024**2
            elif "Resolution:" in line_s:
                res = line_s.split(":", 1)[1].strip()
                if res not in info.displays:
                    info.displays.append(res)
    except Exception as exc:
        log.debug("macOS SPDisplaysDataType failed: %s", exc)

    # Detect Apple Silicon unified architecture
    if "Apple" in (info.name or "") or "Apple" in (info.vendor or ""):
        info.is_unified_memory = True
        info.vendor = "Apple"

    # Thermal readings from IOHID
    try:
        from mingmu.utils.macos_sensors import get_macos_thermal_readings
        thermals = get_macos_thermal_readings()
        if thermals.gpu_temp_c is not None:
            info.temperature_c = thermals.gpu_temp_c
    except Exception as exc:
        log.debug("macOS GPU thermal read failed: %s", exc)


# ── Linux collector ──────────────────────────────────────────

def _collect_linux(info: GPUInfo) -> None:
    """Enrich GPU telemetry on Linux via sysfs or lspci."""
    if _collect_nvidia(info):
        return

    # Check AMD GPU via sysfs (gpu_busy_percent, hwmon)
    for card_idx in range(4):
        card_dir = f"/sys/class/drm/card{card_idx}/device"
        if os.path.exists(card_dir):
            info.present = True
            # Utilization
            busy_path = f"{card_dir}/gpu_busy_percent"
            if os.path.exists(busy_path):
                try:
                    with open(busy_path) as f:
                        info.usage_percent = float(f.read().strip())
                except Exception:
                    pass

            # Thermals via hwmon
            hwmon_dir = f"{card_dir}/hwmon"
            if os.path.exists(hwmon_dir):
                try:
                    for h in os.listdir(hwmon_dir):
                        t_path = os.path.join(hwmon_dir, h, "temp1_input")
                        if os.path.exists(t_path):
                            with open(t_path) as f:
                                millic = float(f.read().strip())
                                info.temperature_c = round(millic / 1000.0, 1)
                                break
                except Exception:
                    pass

            # Driver
            driver_link = f"{card_dir}/driver"
            if os.path.islink(driver_link):
                info.driver_version = os.path.basename(os.readlink(driver_link))
            break

    # Fallback to lspci for GPU identification
    if info.name == "Unknown":
        try:
            raw = subprocess.check_output(
                ["lspci"],
                text=True,
                timeout=2.0,
                stderr=subprocess.DEVNULL,
            )
            for line in raw.splitlines():
                if any(k in line.lower() for k in ("vga compatible controller", "3d controller", "display controller")):
                    info.present = True
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        info.name = parts[2].strip()
                    break
        except Exception:
            pass


# ── Windows collector ────────────────────────────────────────

def _collect_windows(info: GPUInfo) -> None:
    """Enrich GPU telemetry on Windows via WMI or nvidia-smi."""
    if _collect_nvidia(info):
        return

    try:
        from mingmu.utils.windows_sensors import get_windows_gpu_readings
        readings = get_windows_gpu_readings()
        if readings:
            g = readings[0]
            info.present = True
            info.name = g.name or "Unknown"
            info.driver_version = g.driver_version
            if g.adapter_ram_bytes:
                info.memory_total_bytes = g.adapter_ram_bytes
            if g.resolution:
                info.displays.append(g.resolution)
    except Exception as exc:
        log.debug("Windows GPU telemetry failed: %s", exc)


# ── Public Collector API ─────────────────────────────────────

def collect_gpu() -> GPUInfo:
    """Collect graphics processing unit telemetry from available sources."""
    info = GPUInfo()

    if is_macos():
        _collect_macos(info)
    elif is_linux():
        _collect_linux(info)
    elif is_windows():
        _collect_windows(info)

    if not info.present and info.name != "Unknown":
        info.present = True

    return info


# ── Section Builders ─────────────────────────────────────────

def build_gpu_section(info: GPUInfo | None = None) -> Section:
    """Build a compact overview table ``Section`` for GPU metrics."""
    if info is None:
        info = collect_gpu()

    if not info.present:
        return Section(
            title=t("sec_gpu"),
            icon="GPU",
            overall_status=Status.UNKNOWN,
            rows=[MetricRow(t("sec_gpu"), t("no_gpu_detected"), Status.UNKNOWN)],
        )

    rows: list[MetricRow] = []

    # Model name
    rows.append(MetricRow(t("gpu_model"), info.name, Status.INFO))

    # Core count
    if info.core_count:
        rows.append(MetricRow(t("gpu_cores"), str(info.core_count), Status.INFO))

    # Usage
    usage_stat = Status.INFO
    if info.usage_percent is not None:
        usage_stat = GPU_USAGE.evaluate(info.usage_percent)
        rows.append(MetricRow(t("gpu_usage"), percent(info.usage_percent), usage_stat))

    # Temperature
    temp_stat = Status.INFO
    if info.temperature_c is not None:
        temp_stat = GPU_TEMPERATURE.evaluate(info.temperature_c)
        rows.append(MetricRow(t("temperature"), temperature(info.temperature_c), temp_stat))

    # VRAM or Memory architecture
    if info.memory_total_bytes:
        if info.memory_used_bytes is not None:
            mem_stat = GPU_MEMORY.evaluate(info.memory_percent)
            rows.append(MetricRow(
                t("vram_usage"),
                f"{bytes_to_human(info.memory_used_bytes)} / {bytes_to_human(info.memory_total_bytes)}",
                mem_stat,
            ))
        else:
            rows.append(MetricRow(t("vram_total"), bytes_to_human(info.memory_total_bytes), Status.INFO))
    elif info.is_unified_memory:
        rows.append(MetricRow(t("vram_architecture"), t("vram_unified"), Status.INFO))

    # Display Resolution
    if info.displays:
        rows.append(MetricRow(t("active_display"), info.displays[0], Status.INFO))

    # Overall status evaluation
    all_statuses = [usage_stat, temp_stat]
    if Status.CRITICAL in all_statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(title=t("sec_gpu"), icon="GPU", overall_status=overall, rows=rows)


def build_advanced_gpu_section() -> Section:
    """Build an expanded, comprehensive diagnostics table for GPU & Displays."""
    info = collect_gpu()

    if not info.present:
        return Section(
            title=t("sec_adv_gpu"),
            icon="GPU",
            overall_status=Status.UNKNOWN,
            rows=[MetricRow(t("sec_gpu"), t("no_gpu_detected"), Status.UNKNOWN)],
        )

    rows: list[MetricRow] = []

    # Model and Vendor
    vendor_str = f" ({info.vendor})" if info.vendor and info.vendor not in info.name else ""
    rows.append(MetricRow(t("gpu_model"), f"{info.name}{vendor_str}", Status.INFO))

    # Compute Cores
    if info.core_count:
        rows.append(MetricRow(t("gpu_cores"), f"{count(info.core_count)} Cores", Status.INFO))

    # API Support (Metal / DirectX)
    if info.api_support:
        rows.append(MetricRow(t("graphics_api"), info.api_support, Status.INFO))

    # Driver version
    if info.driver_version:
        rows.append(MetricRow(t("driver_version"), info.driver_version, Status.INFO))

    # GPU compute utilization (with bar if available)
    usage_stat = Status.INFO
    if info.usage_percent is not None:
        usage_stat = GPU_USAGE.evaluate(info.usage_percent)
        bar_str = render_progress_bar(info.usage_percent)
        rows.append(MetricRow(t("gpu_usage"), bar_str, usage_stat))

    # Thermals
    temp_stat = Status.INFO
    if info.temperature_c is not None:
        temp_stat = GPU_TEMPERATURE.evaluate(info.temperature_c)
        rows.append(MetricRow(t("gpu_temp"), temperature(info.temperature_c), temp_stat))

    # Memory details
    if info.memory_total_bytes and info.memory_used_bytes is not None:
        pct = info.memory_percent or 0.0
        vram_bar = render_progress_bar(pct)
        mem_stat = GPU_MEMORY.evaluate(pct)
        rows.append(MetricRow(t("vram_usage"), vram_bar, mem_stat))
        rows.append(MetricRow(
            f"  ↳ {t('used_total')}",
            f"{bytes_to_human(info.memory_used_bytes)} / {bytes_to_human(info.memory_total_bytes)}",
            Status.INFO,
        ))
    elif info.memory_total_bytes:
        rows.append(MetricRow(t("vram_total"), bytes_to_human(info.memory_total_bytes), Status.INFO))
    elif info.is_unified_memory:
        rows.append(MetricRow(t("vram_architecture"), f"{t('vram_unified')} (SoC Dynamic Shared Memory)", Status.INFO))

    # Connected Displays
    if info.displays:
        for idx, disp in enumerate(info.displays):
            rows.append(MetricRow(f"  ↳ {t('active_display')} #{idx + 1}", disp, Status.INFO))

    all_statuses = [usage_stat, temp_stat]
    if Status.CRITICAL in all_statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(
        title=t("sec_adv_gpu"),
        icon="GPU",
        overall_status=overall,
        rows=rows,
    )
