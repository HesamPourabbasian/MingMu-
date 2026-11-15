"""Tests for Disk & Filesystem collection structures and section builders."""

from mingmu.core.disk import (
    DiskIOCounters,
    DiskInfo,
    PartitionUsage,
    build_advanced_disk_section,
    build_disk_section,
    collect_disk,
)
from mingmu.utils.thresholds import Status


def test_disk_info_creation():
    part = PartitionUsage(
        device="/dev/disk1s1",
        mountpoint="/",
        fstype="apfs",
        total_bytes=500 * 1024**3,
        used_bytes=250 * 1024**3,
        free_bytes=250 * 1024**3,
        percent_used=50.0,
        status=Status.GOOD,
    )
    io = DiskIOCounters(
        read_bytes=1024**3,
        write_bytes=2 * 1024**3,
        read_count=10000,
        write_count=20000,
    )
    info = DiskInfo(
        partitions=[part],
        total_bytes=500 * 1024**3,
        used_bytes=250 * 1024**3,
        free_bytes=250 * 1024**3,
        percent_used=50.0,
        io_counters=io,
    )

    sec = build_disk_section(info)
    assert sec.title == "DISK"
    assert sec.icon == "DSK"
    assert sec.overall_status == Status.GOOD
    labels = [r.label for r in sec.rows]
    assert any("Disk Usage" in l for l in labels)
    assert any("Used / Total" in l for l in labels)
    assert any("Free Space" in l for l in labels)


def test_disk_critical_condition():
    part = PartitionUsage(
        device="/dev/disk1s1",
        mountpoint="/",
        fstype="apfs",
        total_bytes=100 * 1024**3,
        used_bytes=98 * 1024**3,
        free_bytes=2 * 1024**3,
        percent_used=98.0,
        status=Status.CRITICAL,
    )
    info = DiskInfo(
        partitions=[part],
        total_bytes=100 * 1024**3,
        used_bytes=98 * 1024**3,
        free_bytes=2 * 1024**3,
        percent_used=98.0,
    )
    sec = build_disk_section(info)
    assert sec.overall_status == Status.CRITICAL


def test_collect_disk_live():
    info = collect_disk()
    assert isinstance(info.partitions, list)
    sec = build_disk_section(info)
    assert sec.title == "DISK"
    assert len(sec.rows) > 0


def test_build_advanced_disk_section_live():
    sec = build_advanced_disk_section()
    assert sec.title == "ADVANCED DISK & FILESYSTEM DIAGNOSTICS"
    assert len(sec.rows) > 0
