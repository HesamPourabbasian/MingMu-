"""Tests for Network collection structures and section builders."""

from mingmu.core.network import (
    NetworkInfo,
    NetworkInterfaceInfo,
    build_advanced_network_section,
    build_network_section,
    collect_network,
)
from mingmu.utils.thresholds import Status


def test_network_info_creation():
    iface = NetworkInterfaceInfo(
        name="en0",
        ip_address="192.168.1.50",
        netmask="255.255.255.0",
        is_up=True,
        speed_mbps=1000,
        mtu=1500,
    )
    info = NetworkInfo(
        bytes_sent=10 * 1024**2,
        bytes_recv=50 * 1024**2,
        packets_sent=5000,
        packets_recv=15000,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
        interfaces=[iface],
        connections_count=12,
    )

    sec = build_network_section(info)
    assert sec.title == "NETWORK"
    assert sec.icon == "NET"
    assert sec.overall_status == Status.GOOD
    labels = [r.label for r in sec.rows]
    assert "Bytes Received" in labels
    assert "Bytes Sent" in labels
    assert any("en0" in l for l in labels)


def test_network_warning_on_errors():
    info = NetworkInfo(
        bytes_sent=1000,
        bytes_recv=1000,
        errin=5000,
        errout=1000,
    )
    sec = build_network_section(info)
    assert sec.overall_status == Status.WARNING


def test_collect_network_live():
    info = collect_network()
    assert info.bytes_sent >= 0
    assert info.bytes_recv >= 0
    sec = build_network_section(info)
    assert sec.title == "NETWORK"
    assert len(sec.rows) > 0


def test_build_advanced_network_section_live():
    sec = build_advanced_network_section()
    assert sec.title == "ADVANCED NETWORK DIAGNOSTICS"
    assert len(sec.rows) > 0
