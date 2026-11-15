"""Tests for the display formatters module."""

from mingmu.display.formatters import (
    bytes_to_human,
    count,
    frequency,
    load_average,
    percent,
    seconds_to_human,
    temperature,
)


class TestBytesToHuman:
    def test_bytes(self):
        assert bytes_to_human(512) == "512 B"

    def test_kilobytes(self):
        assert bytes_to_human(1024) == "1.0 KB"

    def test_megabytes(self):
        assert bytes_to_human(1024 ** 2) == "1.0 MB"

    def test_gigabytes(self):
        assert bytes_to_human(1024 ** 3) == "1.0 GB"

    def test_terabytes(self):
        assert bytes_to_human(1024 ** 4) == "1.0 TB"

    def test_none(self):
        assert bytes_to_human(None) == "N/A"

    def test_fractional(self):
        result = bytes_to_human(int(8.4 * 1024 ** 3))
        assert "GB" in result


class TestPercent:
    def test_normal(self):
        assert percent(78.3) == "78.3%"

    def test_zero(self):
        assert percent(0.0) == "0.0%"

    def test_hundred(self):
        assert percent(100.0) == "100.0%"

    def test_none(self):
        assert percent(None) == "N/A"

    def test_custom_decimals(self):
        assert percent(50.123, decimals=2) == "50.12%"


class TestTemperature:
    def test_normal(self):
        assert temperature(42.5) == "42.5°C"

    def test_none(self):
        assert temperature(None) == "N/A"


class TestFrequency:
    def test_ghz(self):
        assert frequency(3200.0) == "3.20 GHz"

    def test_mhz(self):
        assert frequency(800.0) == "800 MHz"

    def test_none(self):
        assert frequency(None) == "N/A"


class TestSecondsToHuman:
    def test_days_and_hours(self):
        assert seconds_to_human(90000) == "1d 1h"

    def test_hours_and_minutes(self):
        assert seconds_to_human(5400) == "1h 30m"

    def test_minutes_and_seconds(self):
        assert seconds_to_human(125) == "2m 5s"

    def test_zero(self):
        assert seconds_to_human(0) == "0s"

    def test_none(self):
        assert seconds_to_human(None) == "N/A"

    def test_negative(self):
        assert seconds_to_human(-10) == "N/A"


class TestCount:
    def test_normal(self):
        assert count(1234) == "1,234"

    def test_none(self):
        assert count(None) == "N/A"


class TestLoadAverage:
    def test_normal(self):
        assert load_average(2.34) == "2.34"

    def test_none(self):
        assert load_average(None) == "N/A"
