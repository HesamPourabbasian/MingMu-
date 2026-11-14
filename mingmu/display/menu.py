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
from mingmu.i18n import (
    SUPPORTED_LANGUAGES,
    get_language,
    save_language_preference,
    set_language,
    t,
)
from mingmu.utils.user_info import get_user_device_info


def _clear() -> None:
    """Clear terminal screen."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def _pause() -> None:
    """Wait for user to press Enter before returning to menu."""
    print()
    try:
        input(dim(f"  ↵ {t('press_enter')}"))
    except (EOFError, KeyboardInterrupt):
        print()


def _select_language_menu(renderer: TableRenderer) -> None:
    """Interactive submenu to select interface language."""
    _clear()
    card_width = renderer.width
    inner = card_width - 2

    print(blue(BOX.top_left + BOX.horizontal * inner + BOX.top_right))
    title = bold(bright_white(f"  🌐  {t('language_menu_title')}"))
    print(blue(BOX.vertical) + _pad(title, inner) + blue(BOX.vertical))
    print(blue(BOX.t_right + BOX.horizontal * inner + BOX.t_left))

    current_code = get_language()
    lang_list = list(SUPPORTED_LANGUAGES.items())

    for idx, (code, (native_name, eng_name)) in enumerate(lang_list, start=1):
        is_current = "  ● (active)" if code == current_code else ""
        key_tag = cyan(bold(f" [{idx}] "))
        label = f"{native_name}  ·  {eng_name}{is_current}"
        line = f"  {key_tag} {bold(white(label))}"
        print(blue(BOX.vertical) + _pad(line, inner) + blue(BOX.vertical))

    # Back option
    back_line = f"  {cyan(bold(' [0] '))} {bold(white(t('menu_opt_0_title') + ' / Return'))}"
    print(blue(BOX.vertical) + _pad(back_line, inner) + blue(BOX.vertical))
    print(blue(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right))
    print()

    try:
        choice = input(bold(cyan("  明眸 ❯ ")) + bright_white(f"Select language [1-{len(lang_list)}, 0]: ")).strip()
    except (KeyboardInterrupt, EOFError):
        return

    if choice in ("0", "q", "exit", "back"):
        return

    try:
        choice_idx = int(choice)
        if 1 <= choice_idx <= len(lang_list):
            selected_code, (nat_name, _) = lang_list[choice_idx - 1]
            set_language(selected_code)
            save_language_preference(selected_code)
            print(green(f"\n  ✓ {t('language_saved', lang=nat_name)}"))
            time.sleep(1.2)
    except ValueError:
        pass


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
            ("1", "📊", t("menu_opt_1_title"), t("menu_opt_1_desc")),
            ("2", "🔋", t("menu_opt_2_title"), t("menu_opt_2_desc")),
            ("3", "🖥 ", t("menu_opt_3_title"), t("menu_opt_3_desc")),
            ("4", "💾", t("menu_opt_4_title"), t("menu_opt_4_desc")),
            ("5", "⏱ ", t("menu_opt_5_title"), t("menu_opt_5_desc")),
            ("6", "🌐", t("menu_opt_6_title"), t("menu_opt_6_desc")),
            ("7", "❓", t("menu_opt_7_title"), t("menu_opt_7_desc")),
            ("0", "🚪", t("menu_opt_0_title"), t("menu_opt_0_desc")),
        ]

        # Draw menu card using full width
        card_width = renderer.width
        inner = card_width - 2
        print(blue(BOX.top_left + BOX.horizontal * inner + BOX.top_right))
        menu_title = bold(bright_white(f"  🧭  {t('select_view')}"))
        print(blue(BOX.vertical) + _pad(menu_title, inner) + blue(BOX.vertical))
        print(blue(BOX.t_right + BOX.horizontal * inner + BOX.t_left))

        for key, icon, title, desc in menu_items:
            key_tag = cyan(bold(f" [{key}] "))
            title_tag = bold(white(f"{icon} {title:<28}"))
            desc_tag = dim(f"· {desc}")
            line = f"  {key_tag} {title_tag} {desc_tag}"
            print(blue(BOX.vertical) + _pad(line, inner) + blue(BOX.vertical))

        print(blue(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right))
        print()

        try:
            choice = input(bold(cyan("  明眸 ❯ ")) + bright_white(t("enter_choice"))).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n" + cyan(f"  {t('stopped_goodbye')} 👋\n"))
            break

        if choice in ("0", "q", "exit", "quit"):
            print("\n" + cyan(f"  {t('stopped_goodbye')} 👋\n"))
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
            _select_language_menu(renderer)

        elif choice == "7":
            _clear()
            print(render_help_view(width=renderer.width))
            _pause()

        else:
            print(red(f"\n  ⚠  {t('invalid_option')}"))
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
            print(dim(f"  ↻  {t('live_monitoring', interval=interval)}"))
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
