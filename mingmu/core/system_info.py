"""
System & Host Telemetry collector.

Gathers host identity, kernel versions, system uptime, boot timestamp,
and active process counts.
"""

from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass
from datetime import datetime

import psutil

from mingmu.display.formatters import count, seconds_to_human
from mingmu.display.table import MetricRow, Section
from mingmu.i18n import t
from mingmu.utils.platform_detect import get_platform_info
from mingmu.utils.thresholds import Status

log = logging.getLogger(__name__)


@dataclass(slots=True)
class SystemInfoData:
    """General system metadata and runtime telemetry."""

    hostname: str
    os_name: str
    os_version: str
    kernel: str
    architecture: str
    uptime_seconds: float
    boot_time_iso: str
    process_count: int
    user_count: int


def collect_system_info() -> SystemInfoData:
    """Collect system runtime and host telemetry."""
    now = time.time()
    boot_ts = psutil.boot_time()
    uptime_sec = max(0.0, now - boot_ts)
    boot_dt = datetime.fromtimestamp(boot_ts).strftime("%Y-%m-%d %H:%M:%S")

    pinfo = get_platform_info()

    # Process count
    try:
        proc_count = len(psutil.pids())
    except Exception:
        proc_count = 0

    # Logged-in user count
    try:
        users = psutil.users()
        user_count = len(users)
    except Exception:
        user_count = 0

    return SystemInfoData(
        hostname=platform.node() or "localhost",
        os_name=pinfo.system,
        os_version=pinfo.release,
        kernel=platform.release(),
        architecture=pinfo.machine,
        uptime_seconds=uptime_sec,
        boot_time_iso=boot_dt,
        process_count=proc_count,
        user_count=user_count,
    )


def build_system_info_section(info: SystemInfoData | None = None) -> Section:
    """Build a table ``Section`` for host and runtime telemetry."""
    if info is None:
        info = collect_system_info()

    rows: list[MetricRow] = [
        MetricRow(t("uptime"), seconds_to_human(info.uptime_seconds), Status.INFO),
        MetricRow(t("boot_time"), info.boot_time_iso, Status.INFO),
        MetricRow(t("hostname"), info.hostname, Status.INFO),
        MetricRow(t("os_version"), f"{info.os_name} {info.os_version}", Status.INFO),
        MetricRow(t("architecture"), info.architecture, Status.INFO),
        MetricRow(t("process_count"), count(info.process_count), Status.INFO),
    ]

    return Section(
        title=t("sec_system_info"),
        icon="SYS",
        overall_status=Status.GOOD,
        rows=rows,
    )
