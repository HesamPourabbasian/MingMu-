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
    assert info.other_gpus == []
    assert info.processes == []
    assert info.recovery_count is None


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


def test_build_gpu_section_multi_gpu():
    sec_gpu = GPUInfo(present=True, name="Intel UHD Graphics 630")
    info = GPUInfo(
        present=True,
        name="NVIDIA GeForce RTX 3080",
        other_gpus=[sec_gpu],
    )
    section = build_gpu_section(info)
    model_row = next((r for r in section.rows if r.label == t("gpu_model")), None)
    assert model_row is not None
    assert "+1" in model_row.value or t("secondary_gpu") in model_row.value


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
    sec_gpu = GPUInfo(
        present=True,
        name="Intel Iris Plus Graphics",
        core_count=64,
        usage_percent=12.0,
        memory_total_bytes=1536 * 1024**2,
    )
    mock_info = GPUInfo(
        present=True,
        name="AMD Radeon RX 7900 XTX",
        vendor="AMD",
        core_count=6144,
        driver_version="23.11.1",
        driver_date="2023-11",
        usage_percent=60.0,
        renderer_usage_percent=58.0,
        tiler_usage_percent=55.0,
        clock_core_mhz=2500,
        clock_mem_mhz=2500,
        temperature_c=62.0,
        power_draw_w=280.0,
        power_limit_w=355.0,
        fan_speed_percent=45.0,
        recovery_count=0,
        pcie_link="PCIe 4.0 x16",
        memory_total_bytes=24 * 1024**3,
        memory_used_bytes=12 * 1024**3,
        memory_free_bytes=12 * 1024**3,
        displays=["2560 x 1440 @ 165Hz", "1920 x 1080 @ 60Hz"],
        api_support="DirectX 12 Ultimate / Vulkan 1.3",
        processes=[("1234", "game.exe", "8192 MiB"), ("5678", "obs.exe", "1024 MiB")],
        other_gpus=[sec_gpu],
    )
    with patch("mingmu.core.gpu.collect_gpu", return_value=mock_info):
        section = build_advanced_gpu_section()
        assert section.icon == "GPU"
        assert section.overall_status == Status.GOOD
        labels = [r.label for r in section.rows]
        assert t("gpu_model") in labels
        assert t("gpu_pcie") in labels
        assert t("gpu_cores") in labels
        assert t("graphics_api") in labels
        assert t("driver_version") in labels
        assert t("gpu_usage") in labels
        assert any(t("gpu_renderer_usage") in l for l in labels)
        assert any(t("gpu_tiler_usage") in l for l in labels)
        assert t("gpu_clocks") in labels
        assert t("gpu_temp") in labels
        assert t("gpu_power") in labels
        assert t("gpu_fan") in labels
        assert t("gpu_driver_stability") in labels
        assert t("vram_usage") in labels
        assert any(t("active_display") in l for l in labels)
        assert t("gpu_processes") in labels
        assert any(t("secondary_gpu") in l for l in labels)


def test_collect_nvidia_multi_gpu_and_processes():
    info = GPUInfo()
    fake_csv = (
        "NVIDIA GeForce RTX 4090, 550.54.14, 24576, 8192, 16384, 55, 62, 280.5, 450.0, 2520, 10501, 40, 4, 16\n"
        "NVIDIA GeForce RTX 3060, 550.54.14, 12288, 2048, 10240, 15, 48, 65.0, 170.0, 1777, 7500, 30, 4, 16"
    )
    fake_proc_csv = "1234, blender, 4096\n5678, python, 2048"

    def side_effect(cmd, **kwargs):
        if "--query-compute-apps" in cmd[1]:
            return fake_proc_csv
        return fake_csv

    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"), \
         patch("subprocess.check_output", side_effect=side_effect):
        ok = _collect_nvidia(info)
        assert ok is True
        assert info.present is True
        assert "RTX 4090" in info.name
        assert info.temperature_c == 62.0
        assert info.usage_percent == 55.0
        assert info.power_draw_w == 280.5
        assert info.power_limit_w == 450.0
        assert info.clock_core_mhz == 2520
        assert info.clock_mem_mhz == 10501
        assert info.fan_speed_percent == 40.0
        assert info.pcie_link == "PCIe Gen4 x16"
        assert len(info.other_gpus) == 1
        assert "RTX 3060" in info.other_gpus[0].name
        assert len(info.processes) == 2
        assert info.processes[0][0] == "1234"
        assert "blender" in info.processes[0][1]


def test_collect_macos_ioaccelerator():
    info = GPUInfo()
    fake_sp = (
        "Graphics/Displays:\n\n"
        "    Apple M2 Pro:\n\n"
        "      Chipset Model: Apple M2 Pro\n"
        "      Type: GPU\n"
        "      Bus: Built-In\n"
        "      Total Number of Cores: 19\n"
        "      Vendor: Apple (0x106b)\n"
        "      Metal Support: Metal 4\n"
        "      Displays:\n"
        "        Color LCD:\n"
        "          Resolution: 3024 x 1964 Retina\n"
    )
    fake_ioreg = (
        '+-o AGXAccelerator  <class AGXAccelerator>\n'
        '  | "PerformanceStatistics" = {"Device Utilization %"=25,"Renderer Utilization %"=24,'
        '"Tiler Utilization %"=22,"Alloc system memory"=2147483648,"In use system memory"=536870912,'
        '"recoveryCount"=0}\n'
        '  | "gpu-core-count" = 19\n'
    )

    with patch("subprocess.check_output", side_effect=[fake_sp, fake_ioreg, ""]), \
         patch("mingmu.utils.macos_sensors.get_macos_thermal_readings") as mock_thermals:
        mock_thermals.return_value = MagicMock(gpu_temp_c=36.5)
        _collect_macos(info)
        assert info.present is True
        assert info.name == "Apple M2 Pro"
        assert info.core_count == 19
        assert info.usage_percent == 25.0
        assert info.renderer_usage_percent == 24.0
        assert info.tiler_usage_percent == 22.0
        assert info.memory_total_bytes == 2147483648
        assert info.memory_used_bytes == 536870912
        assert info.temperature_c == 36.5
        assert info.recovery_count == 0
        assert "3024 x 1964 Retina" in info.displays


def test_collect_windows_multi_gpu():
    info = GPUInfo()
    reading1 = MagicMock()
    reading1.name = "NVIDIA GeForce RTX 4070 Laptop GPU"
    reading1.driver_version = "31.0.15.5123"
    reading1.driver_date = "20240118"
    reading1.adapter_ram_bytes = 8 * 1024**3
    reading1.resolution = "2560 x 1600"
    reading1.refresh_rate = 240
    reading1.bits_per_pixel = 32
    reading1.usage_percent = 35.0
    reading1.pnp_id = "PCI\\VEN_10DE&DEV_28E0..."

    reading2 = MagicMock()
    reading2.name = "Intel UHD Graphics"
    reading2.driver_version = "31.0.101.4575"
    reading2.driver_date = "20230715"
    reading2.adapter_ram_bytes = 1024**3
    reading2.resolution = "1920 x 1080"
    reading2.refresh_rate = 60
    reading2.bits_per_pixel = 32
    reading2.usage_percent = 5.0
    reading2.pnp_id = "PCI\\VEN_8086&DEV_46A6..."

    with patch("mingmu.core.gpu._collect_nvidia", return_value=False), \
         patch("mingmu.utils.windows_sensors.get_windows_gpu_readings", return_value=[reading1, reading2]):
        _collect_windows(info)
        assert info.present is True
        assert "RTX 4070" in info.name
        assert info.driver_version == "31.0.15.5123"
        assert info.driver_date == "20240118"
        assert info.memory_total_bytes == 8 * 1024**3
        assert "2560 x 1600 @ 240Hz (32-bit)" in info.displays
        assert info.usage_percent == 35.0
        assert len(info.other_gpus) == 1
        assert "Intel UHD" in info.other_gpus[0].name
