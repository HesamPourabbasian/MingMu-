"""
Advanced, detailed metric tables for Battery, CPU, and Memory.
"""

from __future__ import annotations

import logging
import os
import psutil

from mingmu.core.battery import (
    _collect_linux,
    _collect_macos,
    _parse_battery_data_dict,
    _parse_ioreg_battery,
    collect_battery,
)
from mingmu.core.cpu import _get_cpu_temperature, collect_cpu
from mingmu.core.memory import collect_memory
from mingmu.display.banner import render_progress_bar
from mingmu.display.formatters import bytes_to_human, count, frequency, load_average, percent, seconds_to_human, temperature
from mingmu.display.table import MetricRow, Section, TableRenderer
from mingmu.i18n import t
from mingmu.utils.platform_detect import is_linux, is_macos, is_windows
from mingmu.utils.thresholds import (
    BATTERY_CHARGE,
    BATTERY_CYCLE_COUNT,
    BATTERY_TEMPERATURE,
    CPU_LOAD_FACTOR,
    CPU_TEMPERATURE,
    CPU_USAGE,
    MEMORY_USAGE,
    SWAP_USAGE,
    Status,
)

log = logging.getLogger(__name__)


def build_advanced_battery_section() -> Section:
    """Build a comprehensive, detailed Battery metrics table."""
    info = collect_battery()

    if not info.present:
        return Section(
            title=t("sec_adv_battery"),
            icon="BAT",
            overall_status=Status.UNKNOWN,
            rows=[MetricRow(t("col_status"), t("no_battery"), Status.UNKNOWN)],
        )

    rows: list[MetricRow] = []

    # Visual gauge bar
    charge_pct = info.charge_percent or 0.0
    bar_str = render_progress_bar(charge_pct)
    charge_status = BATTERY_CHARGE.evaluate(charge_pct)
    rows.append(MetricRow(t("charge_level"), bar_str, charge_status))

    # Condition & Maximum Capacity
    cond_status = Status.GOOD
    if info.condition:
        cond_lower = info.condition.lower()
        if any(term in cond_lower for term in ("normal", "good")):
            cond_status = Status.GOOD
            cond_display = t("cond_normal", default=info.condition)
        elif any(term in cond_lower for term in ("fair", "check")):
            cond_status = Status.WARNING
            cond_display = t("cond_fair", default=info.condition)
        else:
            cond_status = Status.CRITICAL
            cond_display = t("cond_service", default=info.condition)
        rows.append(MetricRow(t("health_condition"), cond_display, cond_status))

    if info.health_percent is not None:
        health_status = BATTERY_CHARGE.evaluate(info.health_percent)
        rows.append(MetricRow(t("maximum_capacity"), percent(info.health_percent), health_status))

    # Temperature
    temp_status = BATTERY_TEMPERATURE.evaluate(info.temperature_c)
    rows.append(MetricRow(t("battery_temp"), temperature(info.temperature_c), temp_status))

    # Cycle count with lifespan percentage
    if info.cycle_count is not None:
        cycle_status = BATTERY_CYCLE_COUNT.evaluate(info.cycle_count)
        consumed_pct = (info.cycle_count / 1000.0) * 100.0
        rows.append(MetricRow(t("cycle_count"), f"{info.cycle_count:,} / 1,000 ({consumed_pct:.1f}% used)", cycle_status))

    # Power Source & State
    state_str = t("plugged_charging") if info.is_charging else t("discharging_battery")
    rows.append(MetricRow(t("power_state"), state_str, Status.CHARGING if info.is_charging else Status.INFO))

    # Electrical metrics (Voltage, Amperage, Wattage) on macOS
    if is_macos():
        try:
            data = _parse_ioreg_battery()
            voltage_mv = data.get("Voltage")
            raw_amp = data.get("Amperage")
            if isinstance(raw_amp, int) and raw_amp >= (1 << 63):
                # Convert uint64 to signed int64
                raw_amp = raw_amp - (1 << 64)

            if isinstance(voltage_mv, (int, float)) and voltage_mv > 0:
                voltage_v = voltage_mv / 1000.0
                rows.append(MetricRow(t("terminal_voltage"), f"{voltage_v:.2f} V", Status.INFO))
                if isinstance(raw_amp, int):
                    rows.append(MetricRow(t("current_flow"), f"{raw_amp:+} mA", Status.INFO))
                    power_w = abs(voltage_v * (raw_amp / 1000.0))
                    rows.append(MetricRow(t("power_rate"), f"{power_w:.2f} W", Status.INFO))

            serial = str(data.get("Serial", "")).strip('"')
            device_name = str(data.get("DeviceName", "")).strip('"')
            if device_name:
                ident = f"{device_name} ({serial})" if serial else device_name
                rows.append(MetricRow(t("hardware_model"), ident, Status.INFO))
        except Exception as exc:
            log.debug("Advanced macOS battery details error: %s", exc)
    elif is_windows():
        try:
            from mingmu.utils.windows_sensors import get_windows_battery_readings
            win_data = get_windows_battery_readings()
            if win_data.voltage_mv:
                rows.append(MetricRow(t("terminal_voltage"), f"{win_data.voltage_mv / 1000.0:.2f} V", Status.INFO))
            if win_data.device_name:
                rows.append(MetricRow(t("hardware_model"), win_data.device_name, Status.INFO))
        except Exception as exc:
            log.debug("Advanced Windows battery error: %s", exc)

    # Capacities (Full Charge vs Design)
    if info.current_capacity_mah and info.design_capacity_mah:
        rows.append(MetricRow(
            t("capacity_cur_design"),
            f"{info.current_capacity_mah:,} / {info.design_capacity_mah:,} mAh",
            Status.INFO,
        ))

    # Time remaining
    if not info.is_charging and info.time_remaining_sec:
        rows.append(MetricRow(t("estimated_runtime"), seconds_to_human(info.time_remaining_sec), Status.INFO))

    # Section overall status
    overall = Status.GOOD
    for st in [charge_status, cond_status, temp_status]:
        if st == Status.CRITICAL:
            overall = Status.CRITICAL
            break
        elif st == Status.WARNING:
            overall = Status.WARNING

    return Section(
        title=t("sec_adv_battery"),
        icon="BAT",
        overall_status=overall,
        rows=rows,
    )


def build_advanced_cpu_section() -> Section:
    """Build a comprehensive, detailed CPU & Thermal metrics table."""
    info = collect_cpu()
    rows: list[MetricRow] = []

    # Visual gauge bar for overall usage
    usage_val = info.usage_percent or 0.0
    bar_str = render_progress_bar(usage_val)
    usage_status = CPU_USAGE.evaluate(usage_val)
    rows.append(MetricRow(t("overall_usage"), bar_str, usage_status))

    # Cores & Architecture
    rows.append(MetricRow(
        t("cores_phys_log"),
        f"{count(info.physical_cores)} Physical / {count(info.logical_cores)} Logical",
        Status.INFO,
    ))

    # Frequency
    if info.freq_current_mhz:
        freq_str = frequency(info.freq_current_mhz)
        if info.freq_max_mhz and info.freq_max_mhz > 0:
            freq_str += f" (Max: {frequency(info.freq_max_mhz)})"
        rows.append(MetricRow(t("frequency"), freq_str, Status.INFO))

    # Thermals breakdown
    temp_status = CPU_TEMPERATURE.evaluate(info.temperature_c)
    rows.append(MetricRow(t("package_temp"), temperature(info.temperature_c), temp_status))

    if is_macos():
        try:
            from mingmu.utils.macos_sensors import _IOHIDSensors
            reader = _IOHIDSensors()
            temps = reader.read_temperatures()
            pacc = [v for k, v in temps.items() if "pacc" in k.lower()]
            eacc = [v for k, v in temps.items() if "eacc" in k.lower()]
            soc = [v for k, v in temps.items() if "soc" in k.lower() or "die" in k.lower()]
            if pacc:
                rows.append(MetricRow(t("perf_cores_temp"), f"{sum(pacc)/len(pacc):.1f}°C", Status.INFO))
            if eacc:
                rows.append(MetricRow(t("eff_cores_temp"), f"{sum(eacc)/len(eacc):.1f}°C", Status.INFO))
            if soc:
                rows.append(MetricRow(t("soc_die_temp"), f"{sum(soc)/len(soc):.1f}°C", Status.INFO))
        except Exception as exc:
            log.debug("Error getting detailed macOS thermals: %s", exc)
    elif is_windows():
        try:
            from mingmu.utils.windows_sensors import get_windows_thermal_readings
            win_thermals = get_windows_thermal_readings()
            if win_thermals.cpu_temp_c is not None:
                rows.append(MetricRow(t("acpi_thermal_zone"), f"{win_thermals.cpu_temp_c:.1f}°C", Status.INFO))
        except Exception as exc:
            log.debug("Advanced Windows CPU thermals error: %s", exc)

    # Load averages & load factor
    if info.load_avg_1 is not None:
        load_status = CPU_LOAD_FACTOR.evaluate(info.load_factor)
        factor_str = f" [Factor: {info.load_factor:.2f}]" if info.load_factor is not None else ""
        rows.append(MetricRow(t("load_avg"), f"{info.load_avg_1:.2f} · {info.load_avg_5:.2f} · {info.load_avg_15:.2f}{factor_str}", load_status))

    # Per-Core breakdown with mini bars
    if info.per_core_usage:
        for idx, core_pct in enumerate(info.per_core_usage):
            core_bar = render_progress_bar(core_pct, width=12)
            c_status = CPU_USAGE.evaluate(core_pct)
            rows.append(MetricRow(f"  ↳ {t('core_label', idx=idx)}", core_bar, c_status))

    # Top CPU processes
    try:
        top_procs: list[tuple[int, str, float, float]] = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                c = p.info["cpu_percent"] or 0.0
                m = p.info["memory_percent"] or 0.0
                name = p.info["name"] or "?"
                pid = p.info["pid"] or 0
                if c > 0.0:
                    top_procs.append((pid, name[:18], c, m))
            except Exception:
                continue
        top_procs.sort(key=lambda x: x[2], reverse=True)
        for pid, name, c_pct, m_pct in top_procs[:4]:
            rows.append(MetricRow(f"  cpu> PID {pid:<5} {name}", f"CPU: {c_pct:.1f}% · RAM: {m_pct:.1f}%", Status.INFO))
    except Exception as exc:
        log.debug("Top CPU processes error: %s", exc)

    overall = Status.GOOD
    for st in [usage_status, temp_status]:
        if st == Status.CRITICAL:
            overall = Status.CRITICAL
            break
        elif st == Status.WARNING:
            overall = Status.WARNING

    return Section(
        title=t("sec_adv_cpu"),
        icon="CPU",
        overall_status=overall,
        rows=rows,
    )


def build_advanced_memory_section() -> Section:
    """Build a comprehensive, detailed Memory & Swap metrics table."""
    info = collect_memory()
    rows: list[MetricRow] = []

    # Visual gauge bar for physical RAM
    mem_status = MEMORY_USAGE.evaluate(info.percent_used)
    bar_str = render_progress_bar(info.percent_used)
    rows.append(MetricRow(t("ram_utilization"), bar_str, mem_status))

    # Physical memory breakdown
    rows.append(MetricRow(t("used_total"), f"{bytes_to_human(info.used)} / {bytes_to_human(info.total)}", mem_status))
    rows.append(MetricRow(t("available_memory"), bytes_to_human(info.available), Status.INFO))

    # Extended macOS / Linux memory types
    try:
        vm = psutil.virtual_memory()
        active = getattr(vm, "active", 0)
        inactive = getattr(vm, "inactive", 0)
        wired = getattr(vm, "wired", 0)
        free_bytes = getattr(vm, "free", 0)

        if active > 0:
            rows.append(MetricRow(t("active_memory"), bytes_to_human(active), Status.INFO))
        if inactive > 0:
            rows.append(MetricRow(t("inactive_memory"), bytes_to_human(inactive), Status.INFO))
        if wired > 0:
            rows.append(MetricRow(t("wired_memory"), bytes_to_human(wired), Status.INFO))
        if free_bytes > 0:
            rows.append(MetricRow(t("free_unallocated"), bytes_to_human(free_bytes), Status.INFO))
    except Exception as exc:
        log.debug("Virtual memory breakdown error: %s", exc)

    # Swap utilization
    if info.swap_total > 0:
        swap_status = SWAP_USAGE.evaluate(info.swap_percent)
        swap_bar = render_progress_bar(info.swap_percent)
        rows.append(MetricRow(t("swap_utilization"), swap_bar, swap_status))
        rows.append(MetricRow(t("swap_used_total"), f"{bytes_to_human(info.swap_used)} / {bytes_to_human(info.swap_total)}", swap_status))
        rows.append(MetricRow(t("swap_free"), bytes_to_human(info.swap_free), Status.INFO))
    else:
        rows.append(MetricRow(t("swap_space"), t("swap_inactive"), Status.INFO))

    # Top memory processes
    try:
        top_procs: list[tuple[int, str, float, int]] = []
        for p in psutil.process_iter(["pid", "name", "memory_percent", "memory_info"]):
            try:
                m_pct = p.info["memory_percent"] or 0.0
                rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
                name = p.info["name"] or "?"
                pid = p.info["pid"] or 0
                top_procs.append((pid, name[:18], m_pct, rss))
            except Exception:
                continue
        top_procs.sort(key=lambda x: x[2], reverse=True)
        for pid, name, m_pct, rss in top_procs[:4]:
            rows.append(MetricRow(f"  mem> PID {pid:<5} {name}", f"{m_pct:.1f}% ({bytes_to_human(rss)})", Status.INFO))
    except Exception as exc:
        log.debug("Top memory processes error: %s", exc)

    overall = Status.GOOD
    for st in [mem_status]:
        if st == Status.CRITICAL:
            overall = Status.CRITICAL
            break
        elif st == Status.WARNING:
            overall = Status.WARNING

    return Section(
        title=t("sec_adv_memory"),
        icon="RAM",
        overall_status=overall,
        rows=rows,
    )
