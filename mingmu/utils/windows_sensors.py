"""
Windows-specific telemetry and sensor integration via PowerShell and WMI/CIM.

Queries Windows battery subsystem (Win32_Battery, BatteryStaticData,
BatteryFullChargedCapacity, BatteryCycleCount) and thermal zones
(MSAcpi_ThermalZoneTemperature) without requiring administrative privileges.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, NamedTuple

log = logging.getLogger(__name__)


class WindowsBatteryReadings(NamedTuple):
    condition: str | None
    health_percent: float | None
    cycle_count: int | None
    design_capacity_mah: int | None
    full_charge_capacity_mah: int | None
    voltage_mv: int | None
    temperature_c: float | None
    device_name: str | None


class WindowsThermalReadings(NamedTuple):
    cpu_temp_c: float | None
    battery_temp_c: float | None


def _run_powershell_json(script: str, timeout: float = 3.0) -> Any:
    """Execute a PowerShell snippet and parse its JSON output."""
    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"& {{ {script} }} | ConvertTo-Json -Compress",
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            shell=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout.strip())
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        log.debug("PowerShell command failed: %s", exc)
    return None


def get_windows_battery_readings() -> WindowsBatteryReadings:
    """Retrieve extended battery telemetry on Windows."""
    script = """
    $res = @{}
    try {
        $bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($bat) {
            $res.Name = $bat.Name
            $res.DeviceID = $bat.DeviceID
            $res.DesignVoltage = $bat.DesignVoltage
            $res.Chemistry = $bat.Chemistry
        }
        $static = Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($static) {
            $res.DesignedCapacity = $static.DesignedCapacity
        }
        $full = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($full) {
            $res.FullChargedCapacity = $full.FullChargedCapacity
        }
        $cycles = Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cycles) {
            $res.CycleCount = $cycles.CycleCount
        }
        $status = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($status) {
            $res.Voltage = $status.Voltage
        }
    } catch {}
    $res
    """
    data = _run_powershell_json(script, timeout=4.0)
    if not isinstance(data, dict):
        return WindowsBatteryReadings(
            condition=None,
            health_percent=None,
            cycle_count=None,
            design_capacity_mah=None,
            full_charge_capacity_mah=None,
            voltage_mv=None,
            temperature_c=None,
            device_name=None,
        )

    design_cap = data.get("DesignedCapacity")
    full_cap = data.get("FullChargedCapacity")
    cycle_count = data.get("CycleCount")
    voltage = data.get("Voltage") or data.get("DesignVoltage")
    name = data.get("Name") or data.get("DeviceID")

    health_pct: float | None = None
    condition: str | None = None

    if isinstance(design_cap, (int, float)) and isinstance(full_cap, (int, float)) and design_cap > 0:
        health_pct = round((full_cap / design_cap) * 100.0, 1)
        if health_pct >= 80.0:
            condition = "Normal"
        elif health_pct >= 60.0:
            condition = "Fair"
        else:
            condition = "Service Recommended"
    elif data.get("Name"):
        condition = "Normal"

    return WindowsBatteryReadings(
        condition=condition,
        health_percent=health_pct,
        cycle_count=int(cycle_count) if isinstance(cycle_count, (int, float)) and cycle_count >= 0 else None,
        design_capacity_mah=int(design_cap) if isinstance(design_cap, (int, float)) else None,
        full_charge_capacity_mah=int(full_cap) if isinstance(full_cap, (int, float)) else None,
        voltage_mv=int(voltage) if isinstance(voltage, (int, float)) else None,
        temperature_c=None,
        device_name=str(name).strip() if name else None,
    )


def get_windows_thermal_readings() -> WindowsThermalReadings:
    """Retrieve temperature readings from ACPI thermal zones on Windows."""
    script = """
    $temps = @()
    try {
        $zones = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue
        foreach ($z in $zones) {
            # Value is in tenths of Kelvin
            $c = ($z.CurrentTemperature - 2732) / 10.0
            if ($c -gt 0 -and $c -lt 140) {
                $temps += $c
            }
        }
    } catch {}
    $temps
    """
    raw = _run_powershell_json(script, timeout=2.5)
    cpu_temp: float | None = None
    if isinstance(raw, list) and raw:
        valid = [float(t) for t in raw if isinstance(t, (int, float)) and 0 < t < 140]
        if valid:
            cpu_temp = round(sum(valid) / len(valid), 1)
    elif isinstance(raw, (int, float)) and 0 < raw < 140:
        cpu_temp = round(float(raw), 1)

    return WindowsThermalReadings(cpu_temp_c=cpu_temp, battery_temp_c=None)
