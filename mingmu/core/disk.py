"""
Disk & Filesystem metrics collector.

Gathers partition usage (total, used, free, percent), mount points,
filesystem types, and storage I/O statistics (read/write bytes and ops).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import psutil

from mingmu.display.banner import render_progress_bar
from mingmu.display.formatters import bytes_to_human, count, percent
from mingmu.display.table import MetricRow, Section
from mingmu.i18n import t
from mingmu.utils.thresholds import DISK_USAGE, Status

log = logging.getLogger(__name__)


# ── Data containers ──────────────────────────────────────────

@dataclass(slots=True)
class PartitionUsage:
    """Storage statistics for a single filesystem partition."""

    device: str
    mountpoint: str
    fstype: str
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    percent_used: float = 0.0
    status: Status = Status.GOOD


@dataclass(slots=True)
class DiskIOCounters:
    """Cumulative disk input/output transfer statistics."""

    read_bytes: int = 0
    write_bytes: int = 0
    read_count: int = 0
    write_count: int = 0


@dataclass(slots=True)
class DiskInfo:
    """Aggregated disk and partition metrics."""

    partitions: list[PartitionUsage] = field(default_factory=list)
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    percent_used: float = 0.0
    io_counters: DiskIOCounters | None = None


# ── Collector ────────────────────────────────────────────────

# Common virtual or pseudo filesystems to ignore on POSIX systems
_IGNORED_FSTYPES = {
    "squashfs",
    "tmpfs",
    "devtmpfs",
    "overlay",
    "aufs",
    "iso9660",
    "udf",
    "autofs",
    "tracefs",
    "debugfs",
    "pstore",
    "securityfs",
    "bpf",
    "cgroup",
    "cgroup2",
    "configfs",
    "ramfs",
    "proc",
    "sysfs",
}


def collect_disk() -> DiskInfo:
    """Collect partition usage and disk I/O metrics via psutil."""
    info = DiskInfo()
    seen_mounts: set[str] = set()

    try:
        raw_parts = psutil.disk_partitions(all=False)
    except Exception as exc:
        log.debug("Failed to list disk partitions: %s", exc)
        raw_parts = []

    for part in raw_parts:
        if part.fstype.lower() in _IGNORED_FSTYPES:
            continue
        if part.mountpoint in seen_mounts:
            continue
        # Skip snap / loopback devices
        if "/snap/" in part.mountpoint or part.device.startswith("/dev/loop"):
            continue

        try:
            usage = psutil.disk_usage(part.mountpoint)
            if usage.total <= 0:
                continue

            pct = round(usage.percent, 1)
            stat = DISK_USAGE.evaluate(pct)

            p_info = PartitionUsage(
                device=part.device,
                mountpoint=part.mountpoint,
                fstype=part.fstype,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent_used=pct,
                status=stat,
            )
            info.partitions.append(p_info)
            seen_mounts.add(part.mountpoint)
        except (PermissionError, OSError) as exc:
            log.debug("Cannot read disk usage for %s: %s", part.mountpoint, exc)

    # Calculate overall storage across primary partitions
    if info.partitions:
        info.total_bytes = sum(p.total_bytes for p in info.partitions)
        info.used_bytes = sum(p.used_bytes for p in info.partitions)
        info.free_bytes = sum(p.free_bytes for p in info.partitions)
        if info.total_bytes > 0:
            info.percent_used = round((info.used_bytes / info.total_bytes) * 100.0, 1)

    # Collect disk I/O counters
    try:
        raw_io = psutil.disk_io_counters()
        if raw_io:
            info.io_counters = DiskIOCounters(
                read_bytes=raw_io.read_bytes,
                write_bytes=raw_io.write_bytes,
                read_count=raw_io.read_count,
                write_count=raw_io.write_count,
            )
    except Exception as exc:
        log.debug("Failed to read disk I/O counters: %s", exc)

    return info


# ── Table Section Builders ───────────────────────────────────

def build_disk_section(info: DiskInfo | None = None) -> Section:
    """Build a compact overview table ``Section`` for disk storage."""
    if info is None:
        info = collect_disk()

    rows: list[MetricRow] = []

    if not info.partitions:
        return Section(
            title=t("sec_disk"),
            icon="DSK",
            overall_status=Status.UNKNOWN,
            rows=[MetricRow(t("disk_usage"), t("no_data_available"), Status.UNKNOWN)],
        )

    # Primary partition or aggregate
    primary = info.partitions[0]
    pri_status = primary.status

    rows.append(MetricRow(
        f"{t('disk_usage')} ({primary.mountpoint})",
        percent(primary.percent_used),
        pri_status,
    ))

    rows.append(MetricRow(
        t("used_total"),
        f"{bytes_to_human(primary.used_bytes)} / {bytes_to_human(primary.total_bytes)}",
        pri_status,
    ))

    rows.append(MetricRow(
        t("disk_free"),
        bytes_to_human(primary.free_bytes),
        Status.INFO,
    ))

    # Overall I/O summary if available
    if info.io_counters:
        rows.append(MetricRow(
            t("disk_throughput"),
            f"R: {bytes_to_human(info.io_counters.read_bytes)} · W: {bytes_to_human(info.io_counters.write_bytes)}",
            Status.INFO,
        ))

    # Determine overall status (worst among partitions)
    all_statuses = [p.status for p in info.partitions]
    if Status.CRITICAL in all_statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(title=t("sec_disk"), icon="DSK", overall_status=overall, rows=rows)


def build_advanced_disk_section() -> Section:
    """Build an expanded, detailed diagnostics table for all filesystems & I/O."""
    info = collect_disk()
    rows: list[MetricRow] = []

    if not info.partitions:
        return Section(
            title=t("sec_adv_disk"),
            icon="DSK",
            overall_status=Status.UNKNOWN,
            rows=[MetricRow(t("disk_usage"), t("no_data_available"), Status.UNKNOWN)],
        )

    # Per-partition breakdown with visual progress bars
    for part in info.partitions:
        bar_str = render_progress_bar(part.percent_used)
        label_part = f"{part.mountpoint} ({part.fstype})"
        rows.append(MetricRow(label_part, bar_str, part.status))
        rows.append(MetricRow(
            f"  ↳ {t('used_total')}",
            f"{bytes_to_human(part.used_bytes)} / {bytes_to_human(part.total_bytes)} (Free: {bytes_to_human(part.free_bytes)})",
            Status.INFO,
        ))

    # Disk I/O telemetry
    if info.io_counters:
        rows.append(MetricRow(
            t("disk_io_read"),
            f"{bytes_to_human(info.io_counters.read_bytes)} ({count(info.io_counters.read_count)} ops)",
            Status.INFO,
        ))
        rows.append(MetricRow(
            t("disk_io_write"),
            f"{bytes_to_human(info.io_counters.write_bytes)} ({count(info.io_counters.write_count)} ops)",
            Status.INFO,
        ))

    all_statuses = [p.status for p in info.partitions]
    if Status.CRITICAL in all_statuses:
        overall = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        overall = Status.WARNING
    else:
        overall = Status.GOOD

    return Section(
        title=t("sec_adv_disk"),
        icon="DSK",
        overall_status=overall,
        rows=rows,
    )
