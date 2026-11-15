"""Tests for HTML Report generator."""

from pathlib import Path
import pytest

from mingmu.core.battery import build_battery_section
from mingmu.core.cpu import build_cpu_section
from mingmu.core.disk import build_disk_section
from mingmu.core.memory import build_memory_section
from mingmu.core.network import build_network_section
from mingmu.core.system_info import build_system_info_section
from mingmu.display.report import generate_html_report
from mingmu.display.table import MetricRow, Section
from mingmu.utils.thresholds import Status


def test_generate_html_report(tmp_path: Path):
    target_file = tmp_path / "test_report.html"

    sections = [
        build_battery_section(),
        build_cpu_section(),
        build_memory_section(),
        build_disk_section(),
        build_network_section(),
        build_system_info_section(),
    ]

    out = generate_html_report(sections, output_path=target_file)
    assert out.exists()
    assert out == target_file

    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "MingMu" in content
    assert "明眸" in content
    assert "BATTERY" in content or "CPU" in content
    assert "DISK" in content
    assert "NETWORK" in content
    assert "SYSTEM INFO" in content


def test_generate_html_report_custom_sections(tmp_path: Path):
    target_file = tmp_path / "custom.html"
    sec = Section(
        title="TEST DIAGNOSTICS",
        icon="TST",
        overall_status=Status.CRITICAL,
        rows=[MetricRow("Warning Metric", "95.5%", Status.CRITICAL)],
    )

    out = generate_html_report([sec], output_path=target_file)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "TEST DIAGNOSTICS" in content
    assert "CRITICAL" in content
    assert "95.5%" in content
