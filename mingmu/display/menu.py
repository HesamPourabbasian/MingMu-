"""
Interactive terminal main menu for MingMu (明眸).
"""

from __future__ import annotations

import os
import platform
import sys
import time

from mingmu import __app_name__, __app_name_cn__, __version__
from mingmu.core.advanced import (
    build_advanced_battery_section,
    build_advanced_cpu_section,
    build_advanced_memory_section,
)
from mingmu.core.battery import build_battery_section
from mingmu.core.cpu import build_cpu_section
from mingmu.core.memory import build_memory_section
from mingmu.display.banner import get_banner
from mingmu.display.colors import (
    blue,
    bold,
    bright_white,
    cyan,
    dim,
    green,
    magenta,
    red,
    white,
    yellow,
)
from mingmu.display.help_view import render_help_view
from mingmu.display.table import BOX, TableRenderer, _pad
from mingmu.utils.user_info import get_user_device_info


def _clear() -> None:
    """Clear terminal screen."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def _pause() -> None:
    """Wait for user to press Enter before returning to menu."""
    print()
    try:
        input(dim("  ↵ Press [Enter] to return to Main Menu..."))
    except (EOFError, KeyboardInterrupt):
        print()


def show_menu(width: int | None = None) -> None:
    """Run the main interactive menu loop filling the full terminal width."""
    renderer = TableRenderer(width=width)

    while True:
        _clear()
        # Print colored ASCII banner centered to full width
        print(get_banner(width=renderer.width))

        # Personalized user & device welcome message
        user_info = get_user_device_info()
        print("  " + bold(cyan("● ")) + bold(bright_white(user_info.welcome_message())))
        print()

        # Menu options frame
        menu_items = [
            ("1", "📊", "Full System Overview", "All-in-one summary of Battery, CPU, & RAM"),
            ("2", "🔋", "Advanced Battery Monitor", "Detailed charging, health, voltage, & wattage"),
            ("3", "🖥 ", "Advanced CPU Monitor", "Per-core bars, SoC die temps, & top processes"),
            ("4", "💾", "Advanced Memory Monitor", "RAM breakdown, active/wired, swap, & top consumers"),
            ("5", "⏱ ", "Live Watch Dashboard", "Auto-refreshing real-time system monitor"),
            ("6", "❓", "Help & Documentation", "Complete guide explaining metrics, thresholds, & CLI"),
            ("0", "🚪", "Exit", "Close MingMu"),
        ]

        # Draw menu card using full width
        card_width = renderer.width
        inner = card_width - 2
        print(blue(BOX.top_left + BOX.horizontal * inner + BOX.top_right))
        menu_title = bold(bright_white("  🧭  SELECT MONITORING VIEW"))
        print(blue(BOX.vertical) + _pad(menu_title, inner) + blue(BOX.vertical))
        print(blue(BOX.t_right + BOX.horizontal * inner + BOX.t_left))

        for key, icon, title, desc in menu_items:
            key_tag = cyan(bold(f" [{key}] "))
            title_tag = bold(white(f"{icon} {title:<26}"))
            desc_tag = dim(f"· {desc}")
            line = f"  {key_tag} {title_tag} {desc_tag}"
            print(blue(BOX.vertical) + _pad(line, inner) + blue(BOX.vertical))

        print(blue(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right))
        print()

        try:
            choice = input(bold(cyan("  明眸 ❯ ")) + bright_white("Enter choice [0-6]: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n" + cyan("  MingMu stopped. Goodbye! 👋\n"))
            break

        if choice in ("0", "q", "exit", "quit"):
            print("\n" + cyan("  MingMu stopped. Goodbye! 👋\n"))
            break

        elif choice == "1":
            _clear()
            sections = [
                build_battery_section(),
                build_cpu_section(),
                build_memory_section(),
            ]
            print(renderer.render(sections))
            _pause()

        elif choice == "2":
            _clear()
            print(renderer.render([build_advanced_battery_section()]))
            _pause()

        elif choice == "3":
            _clear()
            print(renderer.render([build_advanced_cpu_section()]))
            _pause()

        elif choice == "4":
            _clear()
            print(renderer.render([build_advanced_memory_section()]))
            _pause()

        elif choice == "5":
            _run_interactive_watch(renderer)

        elif choice == "6":
            _clear()
            print(render_help_view(width=renderer.width))
            _pause()

        else:
            print(red("\n  ⚠  Invalid option. Please enter a number between 0 and 6."))
            time.sleep(1.0)


def _run_interactive_watch(renderer: TableRenderer) -> None:
    """Run live watch mode from the menu, with graceful return on Ctrl+C."""
    interval = 2.0
    try:
        while True:
            _clear()
            sections = [
                build_battery_section(),
                build_cpu_section(),
                build_memory_section(),
            ]
            print(renderer.render(sections))
            print()
            print(dim(f"  ↻  Live Monitoring (every {interval}s)  ·  Press Ctrl+C to return to Menu"))
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
