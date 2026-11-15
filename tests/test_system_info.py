"""Tests for System Info collection and section builder."""

from mingmu.core.system_info import (
    SystemInfoData,
    build_system_info_section,
    collect_system_info,
)
from mingmu.utils.thresholds import Status


def test_system_info_creation():
    info = SystemInfoData(
        hostname="test-host",
        os_name="Darwin",
        os_version="23.4.0",
        kernel="23.4.0",
        architecture="arm64",
        uptime_seconds=3665.0,
        boot_time_iso="2026-11-15 12:00:00",
        process_count=245,
        user_count=1,
    )

    sec = build_system_info_section(info)
    assert sec.title == "SYSTEM INFO"
    assert sec.icon == "SYS"
    assert sec.overall_status == Status.GOOD
    labels = [r.label for r in sec.rows]
    assert "System Uptime" in labels
    assert "Boot Time" in labels
    assert "Hostname" in labels
    assert "OS Version" in labels
    assert "Architecture" in labels
    assert "Process Count" in labels

    values = [r.value for r in sec.rows]
    assert "test-host" in values
    assert "1h 1m" in values


def test_collect_system_info_live():
    info = collect_system_info()
    assert info.uptime_seconds > 0
    assert info.hostname
    sec = build_system_info_section(info)
    assert sec.title == "SYSTEM INFO"
    assert len(sec.rows) == 6
