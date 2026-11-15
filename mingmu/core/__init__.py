"""Core metric collectors for MingMu."""

from mingmu.core.battery import build_battery_section, collect_battery
from mingmu.core.cpu import build_cpu_section, collect_cpu
from mingmu.core.disk import (
    build_advanced_disk_section,
    build_disk_section,
    collect_disk,
)
from mingmu.core.memory import build_memory_section, collect_memory
from mingmu.core.network import (
    build_advanced_network_section,
    build_network_section,
    collect_network,
)
from mingmu.core.system_info import (
    build_system_info_section,
    collect_system_info,
)

__all__ = [
    "collect_battery",
    "build_battery_section",
    "collect_cpu",
    "build_cpu_section",
    "collect_memory",
    "build_memory_section",
    "collect_disk",
    "build_disk_section",
    "build_advanced_disk_section",
    "collect_network",
    "build_network_section",
    "build_advanced_network_section",
    "collect_system_info",
    "build_system_info_section",
]
