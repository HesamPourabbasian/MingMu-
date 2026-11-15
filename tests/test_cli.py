"""Unit tests for MingMu CLI dispatcher and subcommands."""

import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from mingmu.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "MingMu" in result.output
    assert "2.0.0" in result.output


def test_cli_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "battery" in result.output
    assert "cpu" in result.output
    assert "gpu" in result.output
    assert "ram" in result.output
    assert "disk" in result.output
    assert "net" in result.output
    assert "report" in result.output
    assert "watch" in result.output


def test_cli_all(runner):
    result = runner.invoke(main, ["--all"])
    assert result.exit_code == 0
    assert "BATTERY" in result.output or "CPU" in result.output
    assert "GPU" in result.output
    assert "DISK" in result.output
    assert "NETWORK" in result.output
    assert "SYSTEM INFO" in result.output


def test_cli_json(runner):
    result = runner.invoke(main, ["--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["version"] == "2.0.0"
    assert "sections" in data
    assert "GPU / GRAPHICS" in data["sections"]
    assert "DISK" in data["sections"]
    assert "NETWORK" in data["sections"]
    assert "SYSTEM INFO" in data["sections"]


def test_cli_battery(runner):
    result = runner.invoke(main, ["battery"])
    assert result.exit_code == 0
    assert "BATTERY" in result.output


def test_cli_battery_advanced(runner):
    result = runner.invoke(main, ["battery", "-a"])
    assert result.exit_code == 0
    assert "BATTERY" in result.output


def test_cli_cpu(runner):
    result = runner.invoke(main, ["cpu"])
    assert result.exit_code == 0
    assert "CPU" in result.output


def test_cli_cpu_advanced(runner):
    result = runner.invoke(main, ["cpu", "-a"])
    assert result.exit_code == 0
    assert "CPU" in result.output


def test_cli_gpu(runner):
    result = runner.invoke(main, ["gpu"])
    assert result.exit_code == 0
    assert "GPU" in result.output


def test_cli_gpu_advanced(runner):
    result = runner.invoke(main, ["gpu", "-a"])
    assert result.exit_code == 0
    assert "GPU" in result.output


def test_cli_ram(runner):
    result = runner.invoke(main, ["ram"])
    assert result.exit_code == 0
    assert "MEMORY" in result.output


def test_cli_ram_advanced(runner):
    result = runner.invoke(main, ["ram", "-a"])
    assert result.exit_code == 0
    assert "MEMORY" in result.output


def test_cli_disk(runner):
    result = runner.invoke(main, ["disk"])
    assert result.exit_code == 0
    assert "DISK" in result.output


def test_cli_disk_advanced(runner):
    result = runner.invoke(main, ["disk", "-a"])
    assert result.exit_code == 0
    assert "ADVANCED DISK & FILESYSTEM DIAGNOSTICS" in result.output


def test_cli_net(runner):
    result = runner.invoke(main, ["net"])
    assert result.exit_code == 0
    assert "NETWORK" in result.output


def test_cli_net_advanced(runner):
    result = runner.invoke(main, ["net", "-a"])
    assert result.exit_code == 0
    assert "ADVANCED NETWORK DIAGNOSTICS" in result.output


def test_cli_help_guide(runner):
    result = runner.invoke(main, ["help-guide"])
    assert result.exit_code == 0
    assert "HELP & DOCUMENTATION GUIDE" in result.output


def test_cli_report(runner, tmp_path: Path):
    target = tmp_path / "cli_report.html"
    result = runner.invoke(main, ["report", "-o", str(target)])
    assert result.exit_code == 0
    assert target.exists()
    assert "[OK]" in result.output


def test_cli_report_flag(runner, tmp_path: Path):
    target = tmp_path / "flag_report.html"
    result = runner.invoke(main, ["--report", str(target)])
    assert result.exit_code == 0
    assert target.exists()


def test_cli_watch_bounded(runner):
    result = runner.invoke(main, ["watch", "--interval", "0.01", "--count", "1"])
    assert result.exit_code == 0
    assert "SYSTEM MONITOR" in result.output


def test_cli_watch_json_bounded(runner):
    result = runner.invoke(main, ["--json", "watch", "--interval", "0.01", "--count", "1"])
    assert result.exit_code == 0
    assert "watch" in result.output
