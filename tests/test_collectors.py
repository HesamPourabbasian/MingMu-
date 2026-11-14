"""Tests for battery and CPU collection structures and evaluations."""

from mingmu.core.battery import BatteryInfo, build_battery_section
from mingmu.core.cpu import CPUInfo, build_cpu_section
from mingmu.core.memory import MemoryInfo, build_memory_section
from mingmu.utils.thresholds import Status


def test_battery_section_building():
    info = BatteryInfo(
        present=True,
        charge_percent=85.0,
        is_charging=False,
        power_source="Battery",
        temperature_c=31.5,
        condition="Normal",
        cycle_count=150,
        health_percent=92.0,
    )
    sec = build_battery_section(info)
    assert sec.title == "BATTERY"
    assert sec.overall_status == Status.GOOD
    labels = [r.label for r in sec.rows]
    assert "Charge Level" in labels
    assert "Condition" in labels
    assert "Temperature" in labels


def test_battery_critical_condition():
    info = BatteryInfo(
        present=True,
        charge_percent=10.0,
        temperature_c=50.0,
        condition="Service Recommended",
    )
    sec = build_battery_section(info)
    assert sec.overall_status == Status.CRITICAL


def test_cpu_section_building():
    info = CPUInfo(
        usage_percent=25.0,
        temperature_c=42.0,
        physical_cores=8,
        logical_cores=8,
    )
    sec = build_cpu_section(info)
    assert sec.title == "CPU"
    assert sec.overall_status == Status.GOOD


def test_memory_section_building():
    info = MemoryInfo(
        total=16 * 1024**3,
        used=8 * 1024**3,
        available=8 * 1024**3,
        percent_used=50.0,
    )
    sec = build_memory_section(info)
    assert sec.title == "MEMORY"
    assert sec.overall_status == Status.GOOD
