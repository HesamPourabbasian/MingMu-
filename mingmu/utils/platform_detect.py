"""
Platform detection utilities.

Provides helpers to identify the current operating system and
determine feature availability across macOS, Linux, and Windows.
"""

from __future__ import annotations

import platform
import sys
from enum import Enum
from functools import lru_cache
from typing import NamedTuple


class Platform(Enum):
    """Supported operating systems."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    UNSUPPORTED = "unsupported"


class PlatformInfo(NamedTuple):
    """Structured platform metadata."""

    platform: Platform
    system: str        # e.g. "Darwin", "Linux", "Windows"
    release: str       # kernel/OS version
    machine: str       # e.g. "arm64", "x86_64", "AMD64"
    python_version: str


@lru_cache(maxsize=1)
def get_platform() -> Platform:
    """Detect the current operating system."""
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        return Platform.MACOS
    elif sys_name == "linux":
        return Platform.LINUX
    elif sys_name == "windows":
        return Platform.WINDOWS
    return Platform.UNSUPPORTED


@lru_cache(maxsize=1)
def get_platform_info() -> PlatformInfo:
    """Return detailed platform metadata."""
    return PlatformInfo(
        platform=get_platform(),
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )


def is_macos() -> bool:
    """Check if running on macOS."""
    return get_platform() == Platform.MACOS


def is_linux() -> bool:
    """Check if running on Linux."""
    return get_platform() == Platform.LINUX


def is_windows() -> bool:
    """Check if running on Windows."""
    return get_platform() == Platform.WINDOWS


def is_supported() -> bool:
    """Check if the current platform is supported."""
    return get_platform() != Platform.UNSUPPORTED
