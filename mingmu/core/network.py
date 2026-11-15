"""
Network metrics collector.

Gathers network throughput (bytes/packets sent and received, errors, drops),
interface configurations (IP addresses, link speeds, MTU), and connection states.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field

import psutil

from mingmu.display.formatters import bytes_to_human, count
from mingmu.display.table import MetricRow, Section
from mingmu.i18n import t
from mingmu.utils.thresholds import Status

log = logging.getLogger(__name__)


# ── Data containers ──────────────────────────────────────────

@dataclass(slots=True)
class NetworkInterfaceInfo:
    """Configuration and state of a single network interface."""

    name: str
    ip_address: str = "N/A"
    netmask: str = "N/A"
    is_up: bool = False
    speed_mbps: int = 0
    mtu: int = 0


@dataclass(slots=True)
class NetworkInfo:
    """Aggregated network telemetry."""

    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    errin: int = 0
    errout: int = 0
    dropin: int = 0
    dropout: int = 0
    interfaces: list[NetworkInterfaceInfo] = field(default_factory=list)
    connections_count: int | None = None


# ── Collector ────────────────────────────────────────────────

def collect_network() -> NetworkInfo:
    """Collect network I/O counters, interface configurations, and connection stats."""
    info = NetworkInfo()

    # 1. Total I/O counters
    try:
        io_total = psutil.net_io_counters()
        if io_total:
            info.bytes_sent = io_total.bytes_sent
            info.bytes_recv = io_total.bytes_recv
            info.packets_sent = io_total.packets_sent
            info.packets_recv = io_total.packets_recv
            info.errin = io_total.errin
            info.errout = io_total.errout
            info.dropin = io_total.dropin
            info.dropout = io_total.dropout
    except Exception as exc:
        log.debug("Failed to read network I/O counters: %s", exc)

    # 2. Interface addresses & stats
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for if_name, addr_list in addrs.items():
            # Skip loopback interface from primary list
            if if_name in ("lo", "lo0"):
                continue

            ipv4 = "N/A"
            mask = "N/A"
            for snic in addr_list:
                if snic.family == socket.AF_INET:
                    ipv4 = snic.address
                    mask = snic.netmask or "N/A"
                    break

            # Interface operational parameters
            if_stat = stats.get(if_name)
            is_up = if_stat.isup if if_stat else False
            speed = if_stat.speed if if_stat else 0
            mtu = if_stat.mtu if if_stat else 0

            # Only include interfaces that have an assigned IP or are up
            if is_up or ipv4 != "N/A":
                info.interfaces.append(NetworkInterfaceInfo(
                    name=if_name,
                    ip_address=ipv4,
                    netmask=mask,
                    is_up=is_up,
                    speed_mbps=speed,
                    mtu=mtu,
                ))
    except Exception as exc:
        log.debug("Failed to list network interfaces: %s", exc)

    # 3. Connection count (requires permissions, catch gracefully)
    try:
        conns = psutil.net_connections(kind="inet")
        info.connections_count = len(conns)
    except (psutil.AccessDenied, PermissionError, OSError):
        info.connections_count = None
    except Exception as exc:
        log.debug("Failed to list network connections: %s", exc)
        info.connections_count = None

    return info


# ── Table Section Builders ───────────────────────────────────

def build_network_section(info: NetworkInfo | None = None) -> Section:
    """Build a compact overview table ``Section`` for network activity."""
    if info is None:
        info = collect_network()

    rows: list[MetricRow] = []

    # Traffic summary
    rows.append(MetricRow(
        t("bytes_received"),
        bytes_to_human(info.bytes_recv),
        Status.INFO,
    ))
    rows.append(MetricRow(
        t("bytes_sent"),
        bytes_to_human(info.bytes_sent),
        Status.INFO,
    ))

    # Active interfaces summary
    active_ifs = [iface for iface in info.interfaces if iface.is_up and iface.ip_address != "N/A"]
    if active_ifs:
        primary = active_ifs[0]
        rows.append(MetricRow(
            f"{t('net_interface')} ({primary.name})",
            primary.ip_address,
            Status.GOOD,
        ))

    rows.append(MetricRow(
        t("net_active_interfaces"),
        str(len(active_ifs)),
        Status.INFO,
    ))

    # Error status check (elevated errors/drops warrant WARNING)
    overall = Status.GOOD
    if (info.errin + info.errout) > 1000 or (info.dropin + info.dropout) > 1000:
        overall = Status.WARNING

    return Section(title=t("sec_network"), icon="NET", overall_status=overall, rows=rows)


def build_advanced_network_section() -> Section:
    """Build an expanded, detailed diagnostics table for network adapters & stats."""
    info = collect_network()
    rows: list[MetricRow] = []

    # Traffic I/O
    rows.append(MetricRow(t("bytes_received"), bytes_to_human(info.bytes_recv), Status.INFO))
    rows.append(MetricRow(t("bytes_sent"), bytes_to_human(info.bytes_sent), Status.INFO))
    rows.append(MetricRow(t("packets_received"), count(info.packets_recv), Status.INFO))
    rows.append(MetricRow(t("packets_sent"), count(info.packets_sent), Status.INFO))

    # Errors & Drops
    err_str = f"In: {count(info.errin)} · Out: {count(info.errout)}"
    err_stat = Status.WARNING if (info.errin + info.errout) > 0 else Status.GOOD
    rows.append(MetricRow(t("net_errors"), err_str, err_stat))

    drop_str = f"In: {count(info.dropin)} · Out: {count(info.dropout)}"
    drop_stat = Status.WARNING if (info.dropin + info.dropout) > 0 else Status.GOOD
    rows.append(MetricRow(t("net_drops"), drop_str, drop_stat))

    # Active connections count
    if info.connections_count is not None:
        rows.append(MetricRow(t("net_connections"), count(info.connections_count), Status.INFO))

    # Interface breakdown
    for iface in info.interfaces:
        up_badge = Status.GOOD if iface.is_up else Status.UNKNOWN
        speed_str = f" · {iface.speed_mbps} Mbps" if iface.speed_mbps > 0 else ""
        mtu_str = f" · MTU {iface.mtu}" if iface.mtu > 0 else ""
        rows.append(MetricRow(
            f"  net> {iface.name}",
            f"{iface.ip_address}{speed_str}{mtu_str}",
            up_badge,
        ))

    overall = Status.GOOD
    if (info.errin + info.errout) > 1000 or (info.dropin + info.dropout) > 1000:
        overall = Status.WARNING

    return Section(
        title=t("sec_adv_network"),
        icon="NET",
        overall_status=overall,
        rows=rows,
    )
