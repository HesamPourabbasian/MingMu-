"""
Graphics Processing Unit (GPU) metrics collector.

Gathers graphics card telemetry across macOS (Apple Silicon / Intel Metal / IOKit),
Linux (NVIDIA SMI, AMD sysfs, DRM, lspci), and Windows (WMI VideoController & NVIDIA).
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
    driver_date: str | None = None
    api_support: str | None = None
    temperature_c: float | None = None
    usage_percent: float | None = None
    renderer_usage_percent: float | None = None
    tiler_usage_percent: float | None = None
    memory_total_bytes: int | None = None
    memory_used_bytes: int | None = None
    memory_free_bytes: int | None = None
    memory_percent: float | None = None
    is_unified_memory: bool = False
    power_draw_w: float | None = None
    power_limit_w: float | None = None
    fan_speed_percent: float | None = None
    clock_core_mhz: int | None = None
    clock_mem_mhz: int | None = None
    pcie_link: str | None = None
    recovery_count: int | None = None
    displays: list[str] = field(default_factory=list)
    processes: list[tuple[str, str, str]] = field(default_factory=list)
    other_gpus: list[GPUInfo] = field(default_factory=list)


# ── NVIDIA SMI helper (Cross-Platform) ───────────────────────

def _collect_nvidia(info: GPUInfo) -> bool:
    """Attempt comprehensive telemetry collection via nvidia-smi if available."""
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return False

    try:
        # Multi-metric query
        query_fields = (
            "name,driver_version,memory.total,memory.used,memory.free,"
            "utilization.gpu,temperature.gpu,power.draw,power.limit,"
            "clocks.current.graphics,clocks.current.memory,fan.speed,"
            "pcie.link.gen.current,pcie.link.width.current"
        )
        cmd = [
            nvsmi,
            f"--query-gpu={query_fields}",
            "--format=csv,noheader,nounits",
        ]
        raw = subprocess.check_output(cmd, text=True, timeout=3.0, stderr=subprocess.DEVNULL)
        lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
        if not lines:
            return False

        def _parse_nvidia_line(target: GPUInfo, parts: list[str]) -> None:
            target.present = True
            target.name = parts[0]
            target.vendor = "NVIDIA"
            target.api_support = "DirectX 12 Ultimate / Vulkan 1.3 / CUDA"
            target.driver_version = parts[1]

            # VRAM
            try:
                tot_mb = float(parts[2])
                used_mb = float(parts[3])
                free_mb = float(parts[4])
                target.memory_total_bytes = int(tot_mb * 1024 * 1024)
                target.memory_used_bytes = int(used_mb * 1024 * 1024)
                target.memory_free_bytes = int(free_mb * 1024 * 1024)
                if tot_mb > 0:
                    target.memory_percent = round((used_mb / tot_mb) * 100.0, 1)
            except (ValueError, IndexError, TypeError):
                pass

            # Utilization %
            try:
                target.usage_percent = float(parts[5])
            except (ValueError, IndexError, TypeError):
                pass

            # Temperature °C
            try:
                target.temperature_c = float(parts[6])
            except (ValueError, IndexError, TypeError):
                pass

            # Power draw & limit
            try:
                if len(parts) > 7 and parts[7]:
                    target.power_draw_w = float(parts[7])
                if len(parts) > 8 and parts[8]:
                    target.power_limit_w = float(parts[8])
            except (ValueError, IndexError, TypeError):
                pass

            # Clocks
            try:
                if len(parts) > 9 and parts[9]:
                    target.clock_core_mhz = int(float(parts[9]))
                if len(parts) > 10 and parts[10]:
                    target.clock_mem_mhz = int(float(parts[10]))
            except (ValueError, IndexError, TypeError):
                pass

            # Fan speed
            try:
                if len(parts) > 11 and parts[11]:
                    target.fan_speed_percent = float(parts[11])
            except (ValueError, IndexError, TypeError):
                pass

            # PCIe Link
            try:
                if len(parts) > 13 and parts[12] and parts[13]:
                    target.pcie_link = f"PCIe Gen{parts[12]} x{parts[13]}"
            except (ValueError, IndexError, TypeError):
                pass

        # Primary GPU
        first_parts = [p.strip() for p in lines[0].split(",")]
        _parse_nvidia_line(info, first_parts)

        # Secondary GPUs if multi-GPU setup
        for extra_line in lines[1:]:
            extra_parts = [p.strip() for p in extra_line.split(",")]
            extra_info = GPUInfo()
            _parse_nvidia_line(extra_info, extra_parts)
            info.other_gpus.append(extra_info)

        # Query compute processes
        try:
            p_cmd = [
                nvsmi,
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ]
            p_raw = subprocess.check_output(p_cmd, text=True, timeout=2.0, stderr=subprocess.DEVNULL)
            for p_line in p_raw.strip().splitlines():
                if not p_line.strip():
                    continue
                p_parts = [p.strip() for p in p_line.split(",")]
                if len(p_parts) >= 3:
                    pid, pname, vram = p_parts[0], p_parts[1], f"{p_parts[2]} MiB"
                    info.processes.append((pid, pname, vram))
        except Exception:
            pass

        return True
    except Exception as exc:
        log.debug("nvidia-smi collection failed: %s", exc)

    return False


# ── macOS collector ──────────────────────────────────────────

def _collect_macos(info: GPUInfo) -> None:
    """Enrich GPU telemetry on macOS via system_profiler and IOKit IOAccelerator."""
    # 1. Hardware Profile via system_profiler
    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            text=True,
            timeout=3.0,
            stderr=subprocess.DEVNULL,
        )
        info.present = True

        current_gpu = info
        is_first = True

        for line in raw.splitlines():
            line_s = line.strip()
            if "Chipset Model:" in line_s:
                chip_name = line_s.split(":", 1)[1].strip()
                if is_first:
                    info.name = chip_name
                    is_first = False
                else:
                    new_gpu = GPUInfo(present=True, name=chip_name)
                    info.other_gpus.append(new_gpu)
                    current_gpu = new_gpu
            elif "Vendor:" in line_s and not current_gpu.vendor:
                current_gpu.vendor = line_s.split(":", 1)[1].strip()
            elif "Bus:" in line_s and not current_gpu.pcie_link:
                bus_name = line_s.split(":", 1)[1].strip()
                current_gpu.pcie_link = "Apple Fabric Interconnect (SoC)" if "Built-In" in bus_name else bus_name
            elif "Total Number of Cores:" in line_s and current_gpu.core_count is None:
                c_match = re.search(r"\d+", line_s)
                if c_match:
                    current_gpu.core_count = int(c_match.group())
            elif "Metal Support:" in line_s or "Metal Family:" in line_s:
                current_gpu.api_support = line_s.split(":", 1)[1].strip()
            elif "VRAM (Total):" in line_s or "VRAM (Dynamic, Max):" in line_s:
                vram_str = line_s.split(":", 1)[1].strip()
                num_match = re.search(r"(\d+)\s*(GB|MB)", vram_str, re.IGNORECASE)
                if num_match:
                    val = int(num_match.group(1))
                    unit = num_match.group(2).upper()
                    if unit == "GB":
                        current_gpu.memory_total_bytes = val * 1024**3
                    elif unit == "MB":
                        current_gpu.memory_total_bytes = val * 1024**2
            elif "Resolution:" in line_s:
                res = line_s.split(":", 1)[1].strip()
                if res not in info.displays:
                    info.displays.append(res)
    except Exception as exc:
        log.debug("macOS SPDisplaysDataType failed: %s", exc)

    # Detect Apple Silicon architecture
    if "Apple" in (info.name or "") or "Apple" in (info.vendor or ""):
        info.is_unified_memory = True
        info.vendor = "Apple"
        if not info.pcie_link:
            info.pcie_link = "Apple Silicon SoC UltraFabric"

    # 2. Real-time GPU Compute & VRAM Telemetry via IOKit IOAccelerator
    try:
        io_raw = subprocess.check_output(
            ["ioreg", "-r", "-c", "IOAccelerator", "-d", "1", "-l"],
            text=True,
            timeout=2.0,
            stderr=subprocess.DEVNULL,
        )

        def _find_int(pattern: str, text: str) -> int | None:
            m = re.search(pattern, text)
            return int(m.group(1)) if m else None

        dev_util = _find_int(r'"Device Utilization %"\s*=\s*(\d+)', io_raw)
        ren_util = _find_int(r'"Renderer Utilization %"\s*=\s*(\d+)', io_raw)
        tiler_util = _find_int(r'"Tiler Utilization %"\s*=\s*(\d+)', io_raw)
        alloc_mem = _find_int(r'"Alloc system memory"\s*=\s*(\d+)', io_raw)
        in_use_mem = _find_int(r'"In use system memory"\s*=\s*(\d+)', io_raw)
        rec_count = _find_int(r'"recoveryCount"\s*=\s*(\d+)', io_raw)
        hw_cores = _find_int(r'"gpu-core-count"\s*=\s*(\d+)', io_raw)

        if dev_util is not None:
            info.usage_percent = float(dev_util)
        if ren_util is not None:
            info.renderer_usage_percent = float(ren_util)
        if tiler_util is not None:
            info.tiler_usage_percent = float(tiler_util)

        if alloc_mem is not None and alloc_mem > 0:
            info.memory_total_bytes = alloc_mem
        if in_use_mem is not None and in_use_mem > 0:
            info.memory_used_bytes = in_use_mem
            if info.memory_total_bytes and info.memory_total_bytes > 0:
                info.memory_free_bytes = max(0, info.memory_total_bytes - in_use_mem)
                info.memory_percent = round((in_use_mem / info.memory_total_bytes) * 100.0, 1)

        if rec_count is not None:
            info.recovery_count = rec_count

        if hw_cores and info.core_count is None:
            info.core_count = hw_cores
    except Exception as exc:
        log.debug("macOS IOAccelerator query failed: %s", exc)

    # 3. Active GPU compositor processes
    try:
        pids = set(re.findall(r'"fLastSubmissionPID"\s*=\s*(\d+)', io_raw if 'io_raw' in locals() else ""))
        import psutil
        for p_str in sorted(pids):
            try:
                p_int = int(p_str)
                proc = psutil.Process(p_int)
                rss_str = bytes_to_human(proc.memory_info().rss)
                info.processes.append((p_str, proc.name(), f"{rss_str} RAM"))
            except Exception:
                pass
    except Exception:
        pass

    # 4. Thermal readings from IOHID GPU sensors
    try:
        from mingmu.utils.macos_sensors import get_macos_thermal_readings
        thermals = get_macos_thermal_readings()
        if thermals.gpu_temp_c is not None:
            info.temperature_c = thermals.gpu_temp_c
    except Exception as exc:
        log.debug("macOS GPU thermal read failed: %s", exc)


# ── Linux collector ──────────────────────────────────────────

def _collect_linux(info: GPUInfo) -> None:
    """Enrich GPU telemetry on Linux via sysfs, hwmon, DRM, or lspci."""
    if _collect_nvidia(info):
        return

    # Check AMD / Intel cards via sysfs DRM
    cards_found = 0
    for card_idx in range(6):
        card_dir = f"/sys/class/drm/card{card_idx}/device"
        if not os.path.exists(card_dir):
            continue

        target = info if cards_found == 0 else GPUInfo(present=True)
        target.present = True
        cards_found += 1

        # Read compute utilization
        busy_path = f"{card_dir}/gpu_busy_percent"
        if os.path.exists(busy_path):
            try:
                with open(busy_path) as f:
                    target.usage_percent = float(f.read().strip())
            except Exception:
                pass

        # Read memory utilization
        mem_busy = f"{card_dir}/mem_busy_percent"
        if os.path.exists(mem_busy):
            try:
                with open(mem_busy) as f:
                    target.renderer_usage_percent = float(f.read().strip())
            except Exception:
                pass

        # VRAM stats
        vram_tot = f"{card_dir}/mem_info_vram_total"
        vram_used = f"{card_dir}/mem_info_vram_used"
        try:
            if os.path.exists(vram_tot):
                with open(vram_tot) as f:
                    target.memory_total_bytes = int(f.read().strip())
            if os.path.exists(vram_used):
                with open(vram_used) as f:
                    target.memory_used_bytes = int(f.read().strip())
            if target.memory_total_bytes and target.memory_used_bytes is not None and target.memory_total_bytes > 0:
                target.memory_percent = round((target.memory_used_bytes / target.memory_total_bytes) * 100.0, 1)
                target.memory_free_bytes = max(0, target.memory_total_bytes - target.memory_used_bytes)
        except Exception:
            pass

        # Thermals and power via hwmon
        hwmon_dir = f"{card_dir}/hwmon"
        if os.path.exists(hwmon_dir):
            try:
                for h in os.listdir(hwmon_dir):
                    h_path = os.path.join(hwmon_dir, h)
                    t_path = os.path.join(h_path, "temp1_input")
                    if os.path.exists(t_path) and target.temperature_c is None:
                        with open(t_path) as f:
                            millic = float(f.read().strip())
                            target.temperature_c = round(millic / 1000.0, 1)

                    p_path = os.path.join(h_path, "power1_average")
                    if os.path.exists(p_path) and target.power_draw_w is None:
                        with open(p_path) as f:
                            micro_w = float(f.read().strip())
                            target.power_draw_w = round(micro_w / 1e6, 1)

                    fan_path = os.path.join(h_path, "pwm1")
                    if os.path.exists(fan_path) and target.fan_speed_percent is None:
                        with open(fan_path) as f:
                            pwm_val = float(f.read().strip())
                            target.fan_speed_percent = round((pwm_val / 255.0) * 100.0, 1)
            except Exception:
                pass

        # PCIe link
        try:
            spd_path = f"{card_dir}/current_link_speed"
            wid_path = f"{card_dir}/current_link_width"
            if os.path.exists(spd_path) and os.path.exists(wid_path):
                with open(spd_path) as fs, open(wid_path) as fw:
                    target.pcie_link = f"PCIe {fs.read().strip()} x{fw.read().strip()}"
        except Exception:
            pass

        # Driver
        driver_link = f"{card_dir}/driver"
        if os.path.islink(driver_link):
            target.driver_version = os.path.basename(os.readlink(driver_link))

        if target is not info:
            info.other_gpus.append(target)

    # Fallback to lspci for GPU identification
    try:
        raw = subprocess.check_output(
            ["lspci"],
            text=True,
            timeout=2.0,
            stderr=subprocess.DEVNULL,
        )
        for line in raw.splitlines():
            line_l = line.lower()
            if any(k in line_l for k in ("vga compatible controller", "3d controller", "display controller")):
                info.present = True
                parts = line.split(":", 2)
                if len(parts) >= 3 and info.name == "Unknown":
                    info.name = parts[2].strip()
                    if "amd" in parts[2].lower():
                        info.vendor = "AMD"
                        info.api_support = "Vulkan 1.3 / OpenGL 4.6"
                    elif "intel" in parts[2].lower():
                        info.vendor = "Intel"
                        info.api_support = "Vulkan 1.3 / OpenCL"
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
            for idx, g in enumerate(readings):
                target = info if idx == 0 else GPUInfo(present=True)
                target.present = True
                target.name = g.name or "Unknown"
                target.driver_version = g.driver_version
                target.driver_date = g.driver_date
                target.api_support = "DirectX 12 / Direct3D"
                if g.adapter_ram_bytes:
                    target.memory_total_bytes = g.adapter_ram_bytes
                if g.resolution:
                    disp_str = g.resolution
                    if g.refresh_rate:
                        disp_str += f" @ {g.refresh_rate}Hz"
                    if g.bits_per_pixel:
                        disp_str += f" ({g.bits_per_pixel}-bit)"
                    target.displays.append(disp_str)
                if g.usage_percent is not None:
                    target.usage_percent = g.usage_percent
                if g.pnp_id:
                    target.pcie_link = g.pnp_id

                if idx > 0:
                    info.other_gpus.append(target)
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

    # Model name (and secondary GPU indicator if present)
    model_str = info.name
    if info.other_gpus:
        model_str += f" (+{len(info.other_gpus)} {t('secondary_gpu')})"
    rows.append(MetricRow(t("gpu_model"), model_str, Status.INFO))

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
    mem_stat = Status.INFO
    if info.memory_total_bytes:
        if info.memory_used_bytes is not None:
            pct = info.memory_percent or 0.0
            mem_stat = GPU_MEMORY.evaluate(pct)
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
    all_statuses = [usage_stat, temp_stat, mem_stat]
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

    # Bus Interface
    if info.pcie_link:
        rows.append(MetricRow(t("gpu_pcie"), info.pcie_link, Status.INFO))

    # Compute Cores
    if info.core_count:
        rows.append(MetricRow(t("gpu_cores"), f"{count(info.core_count)} Cores", Status.INFO))

    # API Support (Metal / DirectX / Vulkan / CUDA)
    if info.api_support:
        rows.append(MetricRow(t("graphics_api"), info.api_support, Status.INFO))

    # Driver version & date
    if info.driver_version:
        drv_val = info.driver_version
        if info.driver_date:
            drv_val += f" ({info.driver_date})"
        rows.append(MetricRow(t("driver_version"), drv_val, Status.INFO))

    # GPU compute utilization (with bar)
    usage_stat = Status.INFO
    if info.usage_percent is not None:
        usage_stat = GPU_USAGE.evaluate(info.usage_percent)
        bar_str = render_progress_bar(info.usage_percent)
        rows.append(MetricRow(t("gpu_usage"), bar_str, usage_stat))

    # 3D Renderer Utilization
    if info.renderer_usage_percent is not None:
        ren_stat = GPU_USAGE.evaluate(info.renderer_usage_percent)
        rows.append(MetricRow(f"  ↳ {t('gpu_renderer_usage')}", render_progress_bar(info.renderer_usage_percent), ren_stat))

    # 2D / Geometry Tiler Utilization
    if info.tiler_usage_percent is not None:
        til_stat = GPU_USAGE.evaluate(info.tiler_usage_percent)
        rows.append(MetricRow(f"  ↳ {t('gpu_tiler_usage')}", render_progress_bar(info.tiler_usage_percent), til_stat))

    # Clocks
    if info.clock_core_mhz:
        clock_str = f"Core: {info.clock_core_mhz} MHz"
        if info.clock_mem_mhz:
            clock_str += f" · Mem: {info.clock_mem_mhz} MHz"
        rows.append(MetricRow(t("gpu_clocks"), clock_str, Status.INFO))

    # Thermals
    temp_stat = Status.INFO
    if info.temperature_c is not None:
        temp_stat = GPU_TEMPERATURE.evaluate(info.temperature_c)
        rows.append(MetricRow(t("gpu_temp"), temperature(info.temperature_c), temp_stat))

    # Power draw & limit
    if info.power_draw_w is not None:
        pwr_str = f"{info.power_draw_w:.1f} W"
        if info.power_limit_w:
            pwr_str += f" / {info.power_limit_w:.1f} W"
        rows.append(MetricRow(t("gpu_power"), pwr_str, Status.INFO))

    # Fan speed
    if info.fan_speed_percent is not None:
        rows.append(MetricRow(t("gpu_fan"), percent(info.fan_speed_percent), Status.INFO))

    # Driver stability / recoveries
    if info.recovery_count is not None:
        rec_status = Status.GOOD if info.recovery_count == 0 else Status.WARNING
        rows.append(MetricRow(t("gpu_driver_stability"), f"{info.recovery_count} Recoveries / 0 Hangs", rec_status))

    # Memory details
    mem_stat = Status.INFO
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
        if info.memory_free_bytes:
            rows.append(MetricRow(
                f"  ↳ {t('available')}",
                bytes_to_human(info.memory_free_bytes),
                Status.INFO,
            ))
    elif info.memory_total_bytes:
        rows.append(MetricRow(t("vram_total"), bytes_to_human(info.memory_total_bytes), Status.INFO))
    elif info.is_unified_memory:
        rows.append(MetricRow(t("vram_architecture"), f"{t('vram_unified')} (SoC Dynamic Shared Memory)", Status.INFO))
        if info.memory_used_bytes:
            rows.append(MetricRow(f"  ↳ {t('vram_in_use')}", bytes_to_human(info.memory_used_bytes), Status.INFO))
        if info.memory_total_bytes:
            rows.append(MetricRow(f"  ↳ {t('vram_allocated')}", bytes_to_human(info.memory_total_bytes), Status.INFO))

    # Connected Displays
    if info.displays:
        for idx, disp in enumerate(info.displays):
            rows.append(MetricRow(f"  ↳ {t('active_display')} #{idx + 1}", disp, Status.INFO))

    # Active GPU Processes
    if info.processes:
        rows.append(MetricRow(t("gpu_processes"), f"{len(info.processes)} Active Tasks", Status.INFO))
        for pid, pname, vram in info.processes[:4]:
            rows.append(MetricRow(f"  ↳ PID {pid}", f"{pname} ({vram})", Status.INFO))

    # Secondary GPUs
    if info.other_gpus:
        for idx, sec_gpu in enumerate(info.other_gpus, 2):
            rows.append(MetricRow(f"{t('secondary_gpu')} #{idx}", sec_gpu.name, Status.INFO))
            if sec_gpu.core_count:
                rows.append(MetricRow(f"  ↳ {t('gpu_cores')}", f"{sec_gpu.core_count} Cores", Status.INFO))
            if sec_gpu.usage_percent is not None:
                rows.append(MetricRow(f"  ↳ {t('gpu_usage')}", percent(sec_gpu.usage_percent), GPU_USAGE.evaluate(sec_gpu.usage_percent)))
            if sec_gpu.memory_total_bytes:
                rows.append(MetricRow(f"  ↳ {t('vram_total')}", bytes_to_human(sec_gpu.memory_total_bytes), Status.INFO))

    all_statuses = [usage_stat, temp_stat, mem_stat]
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
