"""Tests for platform detection and Windows support."""

from mingmu.utils.platform_detect import Platform, get_platform, is_supported, is_windows, is_macos, is_linux
from mingmu.utils.windows_sensors import (
    WindowsBatteryReadings,
    WindowsThermalReadings,
    get_windows_battery_readings,
    get_windows_thermal_readings,
)


def test_platform_enums():
    assert Platform.WINDOWS.value == "windows"
    assert Platform.MACOS.value == "macos"
    assert Platform.LINUX.value == "linux"


def test_current_platform_supported():
    assert is_supported() is True


def test_windows_readings_types():
    bat = get_windows_battery_readings()
    assert isinstance(bat, WindowsBatteryReadings)

    therm = get_windows_thermal_readings()
    assert isinstance(therm, WindowsThermalReadings)


def test_user_device_info():
    from mingmu.utils.user_info import get_user_device_info, UserDeviceInfo
    info = get_user_device_info()
    assert isinstance(info, UserDeviceInfo)
    assert len(info.username) > 0
    assert len(info.device_model) > 0
    msg = info.welcome_message()
    assert "Hello " in msg
    assert "you are using " in msg
