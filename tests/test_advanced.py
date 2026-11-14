"""Tests for advanced metric builders and help views."""

from mingmu.core.advanced import (
    build_advanced_battery_section,
    build_advanced_cpu_section,
    build_advanced_memory_section,
)
from mingmu.display.banner import get_banner, render_progress_bar
from mingmu.display.help_view import render_help_view
from mingmu.utils.thresholds import Status


def test_banner_generation():
    banner = get_banner()
    assert "明眸" in banner
    assert "B R I G H T   E Y E S" in banner


def test_progress_bar():
    bar = render_progress_bar(75.0, width=20)
    assert "75.0%" in bar
    assert "[" in bar and "]" in bar


def test_advanced_battery_section():
    sec = build_advanced_battery_section()
    assert sec.title == "ADVANCED BATTERY DIAGNOSTICS"
    assert len(sec.rows) > 0


def test_advanced_cpu_section():
    sec = build_advanced_cpu_section()
    assert sec.title == "ADVANCED CPU & THERMAL DIAGNOSTICS"
    assert len(sec.rows) > 0


def test_advanced_memory_section():
    sec = build_advanced_memory_section()
    assert sec.title == "ADVANCED MEMORY & SWAP DIAGNOSTICS"
    assert len(sec.rows) > 0


def test_help_view():
    view = render_help_view(width=80)
    assert "HELP & DOCUMENTATION GUIDE" in view
    assert "STATUS INDICATORS" in view
    assert "COMMAND-LINE SHORTCUTS" in view
