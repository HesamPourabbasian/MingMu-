"""
User and hardware device detection utilities across macOS, Linux, and Windows.
"""

from __future__ import annotations

import getpass
import logging
import os
import platform
import subprocess
from functools import lru_cache
from typing import NamedTuple

from mingmu.utils.platform_detect import is_linux, is_macos, is_windows

log = logging.getLogger(__name__)


class UserDeviceInfo(NamedTuple):
    username: str
    display_name: str
    device_model: str

    def welcome_message(self) -> str:
        """Return the formatted welcome greeting string."""
        from mingmu.i18n import t

        if self.display_name and self.display_name.lower() != self.username.lower():
            user_part = f"{self.display_name} ({self.username})"
        else:
            user_part = self.username
        return t("welcome", user=user_part, model=self.device_model)


def _detect_macos_hardware() -> str:
    """Retrieve Mac hardware model and chip info (e.g. MacBook Air Apple M1)."""
    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"],
            text=True,
            timeout=2.0,
            stderr=subprocess.DEVNULL,
        )
        model_name: str | None = None
        chip_name: str | None = None
        for line in raw.splitlines():
            if "Model Name:" in line:
                model_name = line.split(":", 1)[1].strip()
            elif "Chip:" in line or "Processor Name:" in line:
                chip_name = line.split(":", 1)[1].strip()
        if model_name and chip_name:
            return f"{model_name} ({chip_name})"
        elif model_name:
            return model_name
    except Exception as exc:
        log.debug("macOS hardware detection failed: %s", exc)

    # Fallback to sysctl
    try:
        hw_model = subprocess.check_output(["sysctl", "-n", "hw.model"], text=True, timeout=1.0).strip()
        if hw_model:
            return hw_model
    except Exception:
        pass
    return "Mac"


def _detect_linux_hardware() -> str:
    """Retrieve Linux system product/model name from sysfs DMI."""
    for path in (
        "/sys/class/dmi/id/product_name",
        "/sys/devices/virtual/dmi/id/product_name",
    ):
        try:
            if os.path.exists(path):
                with open(path) as f:
                    name = f.read().strip()
                    if name and name.lower() not in ("none", "system product name", "o.e.m."):
                        return name
        except OSError:
            pass

    # Check device tree model (e.g. Raspberry Pi)
    dt_model = "/proc/device-tree/model"
    if os.path.exists(dt_model):
        try:
            with open(dt_model) as f:
                model = f.read().strip().rstrip("\x00")
                if model:
                    return model
        except OSError:
            pass

    return f"Linux {platform.machine()} PC"


def _detect_windows_hardware() -> str:
    """Retrieve Windows system manufacturer and model via PowerShell/WMI."""
    try:
        from mingmu.utils.windows_sensors import _run_powershell_json
        script = """
        $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
        if ($cs) {
            @{ Manufacturer = $cs.Manufacturer; Model = $cs.Model }
        }
        """
        data = _run_powershell_json(script, timeout=2.5)
        if isinstance(data, dict):
            mfg = data.get("Manufacturer", "").strip()
            mod = data.get("Model", "").strip()
            if mfg and mod and mfg.lower() not in mod.lower():
                return f"{mfg} {mod}"
            elif mod:
                return mod
    except Exception as exc:
        log.debug("Windows hardware detection failed: %s", exc)

    return f"Windows {platform.machine()} PC"


@lru_cache(maxsize=1)
def get_user_device_info() -> UserDeviceInfo:
    """Resolve the system username, display name, and device hardware model."""
    username = getpass.getuser() or os.environ.get("USER") or os.environ.get("USERNAME") or "User"
    display_name = username

    # 1. Resolve full/display name
    if is_macos():
        try:
            import pwd
            gecos = pwd.getpwnam(username).pw_gecos
            if gecos:
                display_name = gecos.split(",")[0].strip()
        except Exception:
            pass
        if display_name == username:
            try:
                full = subprocess.check_output(["id", "-F"], text=True, timeout=1.0, stderr=subprocess.DEVNULL).strip()
                if full:
                    display_name = full
            except Exception:
                pass
    elif is_linux():
        try:
            import pwd
            gecos = pwd.getpwnam(username).pw_gecos
            if gecos:
                display_name = gecos.split(",")[0].strip()
        except Exception:
            pass
    elif is_windows():
        try:
            from mingmu.utils.windows_sensors import _run_powershell_json
            script = f"""
            $u = Get-CimInstance Win32_UserAccount -Filter "Name='{username}'" -ErrorAction SilentlyContinue
            if ($u -and $u.FullName) {{ $u.FullName }}
            """
            fn = _run_powershell_json(script, timeout=2.0)
            if isinstance(fn, str) and fn.strip():
                display_name = fn.strip()
        except Exception:
            pass

    # 2. Resolve hardware device model
    if is_macos():
        device_model = _detect_macos_hardware()
    elif is_linux():
        device_model = _detect_linux_hardware()
    elif is_windows():
        device_model = _detect_windows_hardware()
    else:
        device_model = f"{platform.system()} Device"

    return UserDeviceInfo(
        username=username,
        display_name=display_name,
        device_model=device_model,
    )
