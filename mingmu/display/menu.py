"""
Interactive terminal main menu for MingMu (明眸) with keyboard navigation.
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
from mingmu.utils.keyboard import read_key
from mingmu.utils.user_info import get_user_device_info


def _clear() -> None:
    """Clear terminal screen."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def _pause() -> None:
    """Wait for user to press Enter before returning to menu."""
    print()
    print(dim(f"  ↵ {t('press_enter')}"))
    try:
        read_key()
    except (EOFError, KeyboardInterrupt):
        pass


def _select_language_menu(renderer: TableRenderer) -> None:
    """Interactive submenu to select interface language via keyboard navigation."""
    current_code = get_language()
    lang_list = list(SUPPORTED_LANGUAGES.items())

    # Find current active language index
    selected_idx = 0
    for idx, (code, _) in enumerate(lang_list):
        if code == current_code:
            selected_idx = idx
            break

    # Build selectable list: all 8 languages + Return option
    items: list[tuple[str, str, str]] = [
        (code, nat_name, eng_name) for code, (nat_name, eng_name) in lang_list
    ]
    back_label = t("menu_opt_0_title") + " / Return"
    items.append(("0", back_label, ""))

    card_width = renderer.width
    inner = card_width - 2

    while True:
        _clear()
        print(blue(BOX.top_left + BOX.horizontal * inner + BOX.top_right))
        title = bold(bright_white(f"  🌐  {t('language_menu_title')}"))
        print(blue(BOX.vertical) + _pad(title, inner) + blue(BOX.vertical))
        print(blue(BOX.t_right + BOX.horizontal * inner + BOX.t_left))

        for idx, (code, nat_name, eng_name) in enumerate(items):
            is_active = (idx == selected_idx)
            is_current = "  ● (active)" if code == current_code else ""
            num_tag = f"[{idx + 1 if idx < len(lang_list) else 0}]"

            if is_active:
                cursor = cyan(bold(" ▶ "))
                key_tag = cyan(bold(num_tag))
                if code == "0":
                    label = bold(bright_white(nat_name))
                else:
                    label = bold(bright_white(f"{nat_name}  ·  {eng_name}{is_current}"))
                line = f" {cursor}{key_tag} {label}"
            else:
                cursor = "   "
                key_tag = dim(num_tag)
                if code == "0":
                    label = dim(nat_name)
                else:
                    label = white(f"{nat_name}  ·  {eng_name}{dim(is_current)}")
                line = f" {cursor}{key_tag} {label}"

            print(blue(BOX.vertical) + _pad(line, inner) + blue(BOX.vertical))

        print(blue(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right))
        print()

        hint = t("nav_hint", default="Use W / S to navigate  ·  [Enter] Select  ·  [q] Exit")
        print("  " + bold(cyan("● ")) + dim(hint))

        try:
            key = read_key()
        except (KeyboardInterrupt, EOFError):
            return

        if key in ("quit", "escape", "q"):
            return
        elif key == "up":
            selected_idx = (selected_idx - 1) % len(items)
        elif key == "down":
            selected_idx = (selected_idx + 1) % len(items)
        elif key in ("enter", "space"):
            chosen_code, nat_name, _ = items[selected_idx]
            if chosen_code != "0":
                set_language(chosen_code)
                save_language_preference(chosen_code)
                print(green(f"\n  ✓ {t('language_saved', lang=nat_name)}"))
                time.sleep(1.0)
            return
        elif key.isdigit():
            val = int(key)
            if val == 0:
                return
            elif 1 <= val <= len(lang_list):
                chosen_code, nat_name, _ = items[val - 1]
                set_language(chosen_code)
                save_language_preference(chosen_code)
                print(green(f"\n  ✓ {t('language_saved', lang=nat_name)}"))
                time.sleep(1.0)
                return


def show_menu(width: int | None = None) -> None:
    """Run the main interactive menu loop with keyboard arrow navigation."""
    renderer = TableRenderer(width=width)
    selected_idx = 0

    while True:
        _clear()
        # Print colored ASCII banner centered to full width
        print(get_banner(width=renderer.width))

        # Personalized user & device welcome message
        user_info = get_user_device_info()
        print("  " + bold(cyan("● ")) + bold(bright_white(user_info.welcome_message())))
        print()

        # Menu options list
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

        if selected_idx >= len(menu_items):
            selected_idx = 0

        # Draw menu card using full width
        card_width = renderer.width
        inner = card_width - 2
        print(blue(BOX.top_left + BOX.horizontal * inner + BOX.top_right))
        menu_title = bold(bright_white(f"  🧭  {t('select_view')}"))
        print(blue(BOX.vertical) + _pad(menu_title, inner) + blue(BOX.vertical))
        print(blue(BOX.t_right + BOX.horizontal * inner + BOX.t_left))

        max_desc_w = max(20, inner - 38)
        for idx, (key, icon, title, desc) in enumerate(menu_items):
            is_active = (idx == selected_idx)
            desc_clipped = desc if len(desc) <= max_desc_w else desc[:max_desc_w - 1] + "…"
            if is_active:
                cursor = cyan(bold(" ▶ "))
                key_tag = cyan(bold(f"[{key}]"))
                title_tag = bold(bright_white(f"{icon} {title:<26}"))
                desc_tag = cyan(f"· {desc_clipped}")
                line = f" {cursor}{key_tag} {title_tag} {desc_tag}"
            else:
                cursor = "   "
                key_tag = dim(f"[{key}]")
                title_tag = white(f"{icon} {title:<26}")
                desc_tag = dim(f"· {desc_clipped}")
                line = f" {cursor}{key_tag} {title_tag} {desc_tag}"
            print(blue(BOX.vertical) + _pad(line, inner) + blue(BOX.vertical))

        print(blue(BOX.bottom_left + BOX.horizontal * inner + BOX.bottom_right))
        print()

        # Keyboard navigation prompt
        nav_hint = t("nav_hint", default="Use W / S to navigate  ·  [Enter] Select  ·  [q] Exit")
        print("  " + bold(cyan("● ")) + dim(nav_hint))

        try:
            key = read_key()
        except (KeyboardInterrupt, EOFError):
            print("\n" + cyan(f"  {t('stopped_goodbye')} 👋\n"))
            break

        if key in ("quit", "escape", "q"):
            print("\n" + cyan(f"  {t('stopped_goodbye')} 👋\n"))
            break
        elif key == "up":
            selected_idx = (selected_idx - 1) % len(menu_items)
            continue
        elif key == "down":
            selected_idx = (selected_idx + 1) % len(menu_items)
            continue
        elif key in ("home",):
            selected_idx = 0
            continue
        elif key in ("end",):
            selected_idx = len(menu_items) - 1
            continue

        # Check if user triggered action via Enter / Space or direct number key
        action_key = None
        if key in ("enter", "space"):
            action_key = menu_items[selected_idx][0]
        elif key.isdigit():
            for i, item in enumerate(menu_items):
                if item[0] == key:
                    selected_idx = i
                    action_key = key
                    break

        if action_key is None:
            continue

        if action_key in ("0", "q", "exit", "quit"):
            print("\n" + cyan(f"  {t('stopped_goodbye')} 👋\n"))
            break

        elif action_key == "1":
            _clear()
            sections = [
                build_battery_section(),
                build_cpu_section(),
                build_memory_section(),
            ]
            print(renderer.render(sections))
            _pause()

        elif action_key == "2":
            _clear()
            print(renderer.render([build_advanced_battery_section()]))
            _pause()

        elif action_key == "3":
            _clear()
            print(renderer.render([build_advanced_cpu_section()]))
            _pause()

        elif action_key == "4":
            _clear()
            print(renderer.render([build_advanced_memory_section()]))
            _pause()

        elif action_key == "5":
            _run_interactive_watch(renderer)

        elif action_key == "6":
            _select_language_menu(renderer)

        elif action_key == "7":
            _clear()
            print(render_help_view(width=renderer.width))
            _pause()


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
