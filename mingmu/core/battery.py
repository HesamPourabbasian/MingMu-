"""
Battery metrics collector.

Gathers battery charge, temperature, cycle count, power source, and
time-remaining data.  Uses ``psutil`` as the primary source and falls
back to platform-specific commands (``ioreg`` on macOS, ``upower`` or
sysfs on Linux) for extended data like temperature and cycle count.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

import psutil

from mingmu.display.formatters import count, percent, seconds_to_human, temperature
from mingmu.display.table import MetricRow, Section
from mingmu.utils.platform_detect import is_linux, is_macos, is_windows
from mingmu.utils.thresholds import (
    BATTERY_CHARGE,
    BATTERY_CYCLE_COUNT,
    BATTERY_TEMPERATURE,
    Status,
)

log = logging.getLogger(__name__)


# ── Data container ───────────────────────────────────────────

@dataclass(slots=True)
class BatteryInfo:
    """Raw battery metrics."""

    present: bool = False
    charge_percent: float | None = None
    is_charging: bool = False
    power_plugged: bool = False
    time_remaining_sec: int | None = None
    temperature_c: float | None = None
    cycle_count: int | None = None
    design_capacity_mah: int | None = None
    current_capacity_mah: int | None = None
    health_percent: float | None = None
    power_source: str = "Unknown"
    condition: str | None = None


# ── macOS helpers (ioreg) ────────────────────────────────────

def _parse_ioreg_battery() -> dict[str, Any]:
    """Parse ``ioreg -r -n AppleSmartBattery`` output into a dict."""
    try:
        raw = subprocess.check_output(
            ["ioreg", "-r", "-n", "AppleSmartBattery"],
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {}

    data: dict[str, Any] = {}
    for line in raw.splitlines():
        match = re.match(r'\s*"(\w+)"\s*=\s*(.*)', line.strip().strip("|").strip())
        if match:
            key, val = match.group(1), match.group(2).strip()
            # Attempt numeric conversion
            if val.isdigit():
                data[key] = int(val)
            elif val in ("Yes", "No"):
                data[key] = val == "Yes"
            else:
                data[key] = val
    return data


def _parse_battery_data_dict(raw: str) -> dict[str, int]:
    """Parse the ``BatteryData`` inline dict from ioreg output.

    The format looks like: ``{\"Key1\"=123,\"Key2\"=456,...}``
    """
    result: dict[str, int] = {}
    for match in re.finditer(r'"(\w+)"=(\d+)', raw):
        result[match.group(1)] = int(match.group(2))
    return result


def _collect_macos(info: BatteryInfo) -> None:
    """Enrich *info* with macOS-specific battery data."""
    # 1. Parse ioreg for cycle count and raw capacities
    data = _parse_ioreg_battery()
    if data:
        raw_temp = data.get("Temperature")
        if isinstance(raw_temp, int) and raw_temp > 0:
            # Apple reports in centi-degrees Celsius (divide by 100)
            info.temperature_c = round(raw_temp / 100.0, 1)

        info.cycle_count = data.get("CycleCount")

        # Capacity — try nested BatteryData dict first (mAh values)
        battery_data_raw = data.get("BatteryData")
        if isinstance(battery_data_raw, str):
            bd = _parse_battery_data_dict(battery_data_raw)
            design = bd.get("DesignCapacity")
            full_charge = bd.get("FullChargeCapacity")
            if design and design > 0:
                info.design_capacity_mah = design
            if full_charge and full_charge > 0:
                info.current_capacity_mah = full_charge
        else:
            dc = data.get("DesignCapacity")
            mc = data.get("MaxCapacity")
            if isinstance(dc, int) and dc > 100:
                info.design_capacity_mah = dc
            if isinstance(mc, int) and mc > 100:
                info.current_capacity_mah = mc

        if info.design_capacity_mah and info.current_capacity_mah:
            info.health_percent = round(
                (info.current_capacity_mah / info.design_capacity_mah) * 100, 1
            )

    # 2. Apple Silicon thermal sensors via IOHID (gas gauge battery temp)
    if info.temperature_c is None:
        try:
            from mingmu.utils.macos_sensors import get_macos_thermal_readings
            thermals = get_macos_thermal_readings()
            if thermals.battery_temp_c is not None:
                info.temperature_c = thermals.battery_temp_c
        except Exception as exc:
            log.debug("macOS thermal readings failed: %s", exc)

    # 3. macOS battery health condition & official maximum capacity
    try:
        from mingmu.utils.macos_sensors import get_macos_battery_profile
        profile = get_macos_battery_profile()
        if profile.condition:
            info.condition = profile.condition
        if profile.max_capacity_pct is not None:
            # Override with Apple's official Maximum Capacity percentage
            info.health_percent = profile.max_capacity_pct
    except Exception as exc:
        log.debug("macOS battery profile failed: %s", exc)


def _collect_windows(info: BatteryInfo) -> None:
    """Enrich *info* with Windows-specific battery data."""
    try:
        from mingmu.utils.windows_sensors import get_windows_battery_readings
        win_data = get_windows_battery_readings()
        if win_data.condition:
            info.condition = win_data.condition
        if win_data.health_percent is not None:
            info.health_percent = win_data.health_percent
        if win_data.cycle_count is not None:
            info.cycle_count = win_data.cycle_count
        if win_data.design_capacity_mah is not None:
            info.design_capacity_mah = win_data.design_capacity_mah
        if win_data.full_charge_capacity_mah is not None:
            info.current_capacity_mah = win_data.full_charge_capacity_mah
        if win_data.temperature_c is not None:
            info.temperature_c = win_data.temperature_c
    except Exception as exc:
        log.debug("Windows battery collection error: %s", exc)


# ── Linux helpers ────────────────────────────────────────────

def _collect_linux(info: BatteryInfo) -> None:
    """Enrich *info* with Linux-specific battery data."""
    # Try psutil sensors first
    temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
    for name in ("BAT0", "BAT1", "battery", "acpitz"):
        if name in temps and temps[name]:
            info.temperature_c = round(temps[name][0].current, 1)
            break

    # Cycle count from sysfs
    for path in (
        "/sys/class/power_supply/BAT0/cycle_count",
        "/sys/class/power_supply/BAT1/cycle_count",
    ):
        try:
            with open(path) as f:
                val = int(f.read().strip())
                if val >= 0:
                    info.cycle_count = val
                    break
        except (OSError, ValueError):
            continue

    # Capacity info from sysfs
    for bat in ("BAT0", "BAT1"):
        base = f"/sys/class/power_supply/{bat}"
        try:
            with open(f"{base}/charge_full_design") as f:
                info.design_capacity_mah = int(f.read().strip()) // 1000
            with open(f"{base}/charge_full") as f:
                info.current_capacity_mah = int(f.read().strip()) // 1000
            if info.design_capacity_mah and info.current_capacity_mah:
                info.health_percent = round(
                    (info.current_capacity_mah / info.design_capacity_mah) * 100, 1
                )
            break
        except (OSError, ValueError):
            continue


# ── Public API ───────────────────────────────────────────────

def collect_battery() -> BatteryInfo:
    """Collect battery metrics from all available sources."""
    info = BatteryInfo()
    battery = psutil.sensors_battery()

    if battery is None:
        info.present = False
        return info

    info.present = True
    info.charge_percent = round(battery.percent, 1)
    info.power_plugged = battery.power_plugged
    info.is_charging = battery.power_plugged

    if battery.power_plugged:
        info.power_source = "AC Power"
    else:
        info.power_source = "Battery"

    if battery.secsleft and battery.secsleft > 0:
        info.time_remaining_sec = int(battery.secsleft)

    # Platform-specific enrichment
    try:
        if is_macos():
            _collect_macos(info)
        elif is_linux():
            _collect_linux(info)
        elif is_windows():
            _collect_windows(info)
    except Exception as exc:
        log.debug("Platform-specific battery collection failed: %s", exc)

    return info


def build_battery_section(info: BatteryInfo | None = None) -> Section:
    """Build a table ``Section`` for battery metrics."""
    if info is None:
        info = collect_battery()

    if not info.present:
        return Section(
            title="BATTERY",
            icon="🔋",
            overall_status=Status.UNKNOWN,
            rows=[MetricRow("Battery", "Not detected", Status.UNKNOWN)],
        )

    rows: list[MetricRow] = []

    # Charge level
    charge_status = BATTERY_CHARGE.evaluate(info.charge_percent)
    rows.append(MetricRow("Charge Level", percent(info.charge_percent), charge_status))

    # Condition (e.g. Normal, Service Recommended)
    cond_status = Status.GOOD
    if info.condition:
        cond_lower = info.condition.lower()
        if any(term in cond_lower for term in ("normal", "good")):
            cond_status = Status.GOOD
        elif any(term in cond_lower for term in ("fair", "check")):
            cond_status = Status.WARNING
        else:
            cond_status = Status.CRITICAL
        rows.append(MetricRow("Condition", info.condition, cond_status))

    # Temperature
    temp_status = BATTERY_TEMPERATURE.evaluate(info.temperature_c)
    rows.append(MetricRow("Temperature", temperature(info.temperature_c), temp_status))

    # Power source
    power_status = Status.CHARGING if info.is_charging else Status.INFO
    rows.append(MetricRow("Power Source", info.power_source, power_status))

    # Cycle count
    cycle_status = Status.INFO
    if info.cycle_count is not None:
        cycle_status = BATTERY_CYCLE_COUNT.evaluate(info.cycle_count)
        rows.append(MetricRow("Cycle Count", count(info.cycle_count), cycle_status))

    # Battery health / maximum capacity
    if info.health_percent is not None:
        health_threshold = BATTERY_CHARGE  # reuse charge thresholds
        health_status = health_threshold.evaluate(info.health_percent)
        rows.append(MetricRow("Maximum Capacity", percent(info.health_percent), health_status))

    # Time remaining
    if not info.is_charging and info.time_remaining_sec:
        rows.append(MetricRow(
            "Time Remaining",
            seconds_to_human(info.time_remaining_sec),
            Status.INFO,
        ))

    # Determine overall status (worst of charge + temp + condition)
    statuses = [charge_status, temp_status]
    if info.condition:
        statuses.append(cond_status)
    if Status.CRITICAL in statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(title="BATTERY", icon="🔋", overall_status=overall, rows=rows)
