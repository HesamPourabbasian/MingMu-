"""
macOS-specific hardware sensors reader using IOHIDEventSystem and system_profiler.

Provides direct access to Apple Silicon and Intel thermal sensors (Battery, CPU)
without requiring root/sudo privileges, as well as battery condition metadata.
"""

from __future__ import annotations

import ctypes
import logging
import re
import subprocess
from typing import NamedTuple

log = logging.getLogger(__name__)


class MacThermalReadings(NamedTuple):
    battery_temp_c: float | None
    cpu_temp_c: float | None


class MacBatteryProfile(NamedTuple):
    condition: str | None
    max_capacity_pct: float | None


class _IOHIDSensors:
    """Read thermal sensors from macOS IOHIDEventSystem."""

    def __init__(self) -> None:
        self.available = False
        try:
            self.iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
            self.cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

            # CF functions setup
            self.cf.CFArrayGetCount.restype = ctypes.c_long
            self.cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
            self.cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
            self.cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
            self.cf.CFRelease.restype = None
            self.cf.CFRelease.argtypes = [ctypes.c_void_p]

            self.cf.CFNumberCreate.restype = ctypes.c_void_p
            self.cf.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]

            self.cf.CFDictionaryCreate.restype = ctypes.c_void_p
            self.cf.CFDictionaryCreate.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]

            self.cf.CFStringCreateWithCString.restype = ctypes.c_void_p
            self.cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            self.cf.CFStringGetCString.restype = ctypes.c_bool
            self.cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]

            # IOHID functions setup
            self.iokit.IOHIDEventSystemClientCreate.restype = ctypes.c_void_p
            self.iokit.IOHIDEventSystemClientCreate.argtypes = [ctypes.c_void_p]
            self.iokit.IOHIDEventSystemClientSetMatching.restype = None
            self.iokit.IOHIDEventSystemClientSetMatching.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.iokit.IOHIDEventSystemClientCopyServices.restype = ctypes.c_void_p
            self.iokit.IOHIDEventSystemClientCopyServices.argtypes = [ctypes.c_void_p]

            self.iokit.IOHIDServiceClientCopyProperty.restype = ctypes.c_void_p
            self.iokit.IOHIDServiceClientCopyProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.iokit.IOHIDServiceClientCopyEvent.restype = ctypes.c_void_p
            self.iokit.IOHIDServiceClientCopyEvent.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int32, ctypes.c_int64]

            self.iokit.IOHIDEventGetFloatValue.restype = ctypes.c_double
            self.iokit.IOHIDEventGetFloatValue.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

            self.available = True
        except Exception as exc:
            log.debug("IOHIDSensors initialization failed: %s", exc)

    def read_temperatures(self) -> dict[str, float]:
        if not self.available:
            return {}

        matching = None
        client = None
        services = None
        k1 = k2 = v1 = v2 = prop_key = None

        try:
            keys = (ctypes.c_void_p * 2)()
            values = (ctypes.c_void_p * 2)()

            k1 = self.cf.CFStringCreateWithCString(None, b"PrimaryUsagePage", 0x08000100)
            k2 = self.cf.CFStringCreateWithCString(None, b"PrimaryUsage", 0x08000100)
            v1_val = ctypes.c_int(0xFF00)  # Apple vendor specific
            v2_val = ctypes.c_int(5)       # Temperature sensor usage
            v1 = self.cf.CFNumberCreate(None, 9, ctypes.byref(v1_val))
            v2 = self.cf.CFNumberCreate(None, 9, ctypes.byref(v2_val))

            keys[0], keys[1] = k1, k2
            values[0], values[1] = v1, v2
            matching = self.cf.CFDictionaryCreate(None, keys, values, 2, None, None)

            client = self.iokit.IOHIDEventSystemClientCreate(None)
            self.iokit.IOHIDEventSystemClientSetMatching(client, matching)
            services = self.iokit.IOHIDEventSystemClientCopyServices(client)

            count = self.cf.CFArrayGetCount(services) if services else 0
            prop_key = self.cf.CFStringCreateWithCString(None, b"Product", 0x08000100)
            field = 15 << 16  # kIOHIDEventTypeTemperature

            readings: dict[str, float] = {}
            for i in range(count):
                service = self.cf.CFArrayGetValueAtIndex(services, i)
                name_ref = self.iokit.IOHIDServiceClientCopyProperty(service, prop_key)
                name = ""
                if name_ref:
                    buf = ctypes.create_string_buffer(128)
                    if self.cf.CFStringGetCString(name_ref, buf, 128, 0x08000100):
                        name = buf.value.decode("utf-8", "ignore")
                    self.cf.CFRelease(name_ref)

                event = self.iokit.IOHIDServiceClientCopyEvent(service, 15, 0, 0)
                if event:
                    temp = self.iokit.IOHIDEventGetFloatValue(event, field)
                    if 0 < temp < 150:
                        readings[name] = temp
                    self.cf.CFRelease(event)

            return readings
        except Exception as exc:
            log.debug("Error reading IOHID temperatures: %s", exc)
            return {}
        finally:
            # Clean up CoreFoundation references safely
            for ref in (services, client, matching, k1, k2, v1, v2, prop_key):
                if ref:
                    try:
                        self.cf.CFRelease(ref)
                    except Exception:
                        pass


_sensor_reader: _IOHIDSensors | None = None


def get_macos_thermal_readings() -> MacThermalReadings:
    """Retrieve Battery and CPU temperatures via IOHID."""
    global _sensor_reader
    if _sensor_reader is None:
        _sensor_reader = _IOHIDSensors()

    readings = _sensor_reader.read_temperatures()
    if not readings:
        return MacThermalReadings(battery_temp_c=None, cpu_temp_c=None)

    # Battery temperature
    bat_temp: float | None = None
    for name, temp in readings.items():
        lower = name.lower()
        if "battery" in lower or "gas gauge" in lower:
            bat_temp = round(temp, 1)
            break

    # CPU temperature (prioritize performance/die temps, then efficiency/SOC temps)
    cpu_temps: list[float] = []
    for name, temp in readings.items():
        lower = name.lower()
        if any(token in lower for token in ("pacc", "eacc", "soc mtr", "die temp", "cpu")):
            cpu_temps.append(temp)

    cpu_temp: float | None = None
    if cpu_temps:
        # Use average of CPU core/die sensor readings
        cpu_temp = round(sum(cpu_temps) / len(cpu_temps), 1)

    return MacThermalReadings(battery_temp_c=bat_temp, cpu_temp_c=cpu_temp)


def get_macos_battery_profile() -> MacBatteryProfile:
    """Read Condition and Maximum Capacity from system_profiler."""
    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPPowerDataType"],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log.debug("system_profiler SPPowerDataType failed: %s", exc)
        return MacBatteryProfile(condition=None, max_capacity_pct=None)

    condition: str | None = None
    max_cap: float | None = None

    cond_match = re.search(r"Condition:\s*([^\n\r]+)", raw)
    if cond_match:
        condition = cond_match.group(1).strip()

    cap_match = re.search(r"Maximum Capacity:\s*(\d+)%", raw)
    if cap_match:
        max_cap = float(cap_match.group(1))

    return MacBatteryProfile(condition=condition, max_capacity_pct=max_cap)
