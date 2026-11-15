"""Unit tests for GPU telemetry collector and table section builders."""

from unittest.mock import MagicMock, patch
import pytest

from mingmu.core.gpu import (
    GPUInfo,
    build_advanced_gpu_section,
    build_gpu_section,
    collect_gpu,
    _collect_linux,
    _collect_macos,
    _collect_nvidia,
    _collect_windows,
)
from mingmu.display.table import Status
from mingmu.i18n import t


def test_gpu_info_defaults():
    info = GPUInfo()
    assert not info.present
    assert info.name == "Unknown"
    assert info.usage_percent is None
    assert info.temperature_c is None
    assert info.memory_total_bytes is None
    assert info.memory_used_bytes is None
    assert info.memory_percent is None
    assert info.displays == []
    assert not info.is_unified_memory


def test_collect_gpu_live():
    info = collect_gpu()
    assert isinstance(info, GPUInfo)
    assert info.name is not None
    assert isinstance(info.displays, list)


def test_build_gpu_section_not_present():
    info = GPUInfo(present=False, name="Unknown")
    section = build_gpu_section(info)
    assert section.icon == "GPU"
    assert section.overall_status == Status.UNKNOWN
    assert len(section.rows) == 1
    assert section.rows[0].value == t("no_gpu_detected")


def test_build_gpu_section_discrete_gpu():
    info = GPUInfo(
        present=True,
        name="NVIDIA GeForce RTX 4090",
        vendor="NVIDIA",
        core_count=16384,
        usage_percent=45.0,
        temperature_c=58.0,
        memory_total_bytes=24 * 1024**3,
        memory_used_bytes=8 * 1024**3,
        displays=["3840 x 2160 @ 144Hz"],
    )
    section = build_gpu_section(info)
    assert section.icon == "GPU"
    assert section.overall_status == Status.GOOD
    labels = [r.label for r in section.rows]
    assert t("gpu_model") in labels
    assert t("gpu_cores") in labels
    assert t("gpu_usage") in labels
    assert t("temperature") in labels
    assert t("vram_usage") in labels
    assert t("active_display") in labels


def test_build_gpu_section_unified_memory():
    info = GPUInfo(
        present=True,
        name="Apple M1",
        vendor="Apple",
        core_count=8,
        temperature_c=32.0,
        is_unified_memory=True,
    )
    section = build_gpu_section(info)
    assert section.icon == "GPU"
    assert section.overall_status == Status.GOOD
    arch_row = next((r for r in section.rows if r.label == t("vram_architecture")), None)
    assert arch_row is not None
    assert arch_row.value == t("vram_unified")


def test_build_gpu_section_threshold_warning_and_critical():
    # Warning
    info_warn = GPUInfo(present=True, name="Test GPU", temperature_c=86.0)
    sec_warn = build_gpu_section(info_warn)
    assert sec_warn.overall_status == Status.WARNING

    # Critical
    info_crit = GPUInfo(present=True, name="Test GPU", usage_percent=96.0)
    sec_crit = build_gpu_section(info_crit)
    assert sec_crit.overall_status == Status.CRITICAL


def test_build_advanced_gpu_section_live():
    section = build_advanced_gpu_section()
    assert section.icon == "GPU"
    assert len(section.rows) >= 1


def test_build_advanced_gpu_section_not_present():
    with patch("mingmu.core.gpu.collect_gpu", return_value=GPUInfo(present=False)):
        section = build_advanced_gpu_section()
        assert section.overall_status == Status.UNKNOWN
        assert section.rows[0].value == t("no_gpu_detected")


def test_build_advanced_gpu_section_full():
    mock_info = GPUInfo(
        present=True,
        name="AMD Radeon RX 7900 XTX",
        vendor="AMD",
        core_count=6144,
        driver_version="23.11.1",
        usage_percent=60.0,
        temperature_c=62.0,
        memory_total_bytes=24 * 1024**3,
        memory_used_bytes=12 * 1024**3,
        displays=["2560 x 1440 @ 165Hz", "1920 x 1080 @ 60Hz"],
        api_support="DirectX 12 Ultimate / Vulkan 1.3",
    )
    with patch("mingmu.core.gpu.collect_gpu", return_value=mock_info):
        section = build_advanced_gpu_section()
        assert section.icon == "GPU"
        assert section.overall_status == Status.GOOD
        labels = [r.label for r in section.rows]
        assert t("gpu_model") in labels
        assert t("gpu_cores") in labels
        assert t("graphics_api") in labels
        assert t("driver_version") in labels
        assert t("gpu_usage") in labels
        assert t("gpu_temp") in labels
        assert t("vram_usage") in labels
        assert any(t("active_display") in l for l in labels)


def test_collect_nvidia_success():
    info = GPUInfo()
    fake_csv = "NVIDIA GeForce RTX 3080, 535.129.03, 10240, 3500, 6740, 45, 52"
    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"), \
         patch("subprocess.check_output", return_value=fake_csv):
        ok = _collect_nvidia(info)
        assert ok is True
        assert info.present is True
        assert "RTX 3080" in info.name
        assert info.temperature_c == 52.0
        assert info.usage_percent == 45.0
        assert info.memory_total_bytes == 10240 * 1024 * 1024
        assert info.memory_used_bytes == 3500 * 1024 * 1024
        assert info.driver_version == "535.129.03"


def test_collect_windows_fallback():
    info = GPUInfo()
    mock_reading = MagicMock()
    mock_reading.name = "Intel Iris Xe Graphics"
    mock_reading.driver_version = "31.0.101.4575"
    mock_reading.adapter_ram_bytes = 2 * 1024**3
    mock_reading.resolution = "1920 x 1080"

    with patch("mingmu.core.gpu._collect_nvidia", return_value=False), \
         patch("mingmu.utils.windows_sensors.get_windows_gpu_readings", return_value=[mock_reading]):
        _collect_windows(info)
        assert info.present is True
        assert info.name == "Intel Iris Xe Graphics"
        assert info.driver_version == "31.0.101.4575"
        assert info.memory_total_bytes == 2 * 1024**3
        assert "1920 x 1080" in info.displays
