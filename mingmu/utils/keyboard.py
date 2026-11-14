"""
Cross-platform single-keystroke keyboard navigation reader.

Provides non-blocking and raw key reading on macOS, Linux, and Windows:
- Up Arrow (also 'k', 'w')
- Down Arrow (also 'j', 's')
- Left Arrow (also 'h', 'a')
- Right Arrow (also 'l', 'd')
- Enter / Return
- Escape / 'q' (Quit)
- Number keys (0-9)
"""

from __future__ import annotations

import os
import platform
import sys
from typing import Literal


def is_interactive() -> bool:
    """Return True if stdin and stdout are interactive TTY devices."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def read_key() -> str:
    """Read a single keypress or escape sequence from the user.

    Returns normalized key string:
    - 'up', 'down', 'left', 'right'
    - 'enter'
    - 'escape'
    - 'quit'
    - '0'..'9'
    - 'space'
    - 'back'
    """
    if not is_interactive():
        # Fallback for non-TTY environments (pipes, scripts, tests)
        try:
            line = sys.stdin.readline().strip().lower()
            if not line:
                return "quit"
            if line in ("up", "u", "k", "w"):
                return "up"
            if line in ("down", "d", "j", "s"):
                return "down"
            if line in ("enter", "return", "ok"):
                return "enter"
            if line in ("q", "quit", "exit"):
                return "quit"
            if line in ("esc", "escape"):
                return "escape"
            return line
        except (EOFError, KeyboardInterrupt):
            return "quit"

    if platform.system() == "Windows":
        return _read_windows_key()
    else:
        return _read_posix_key()


def _read_windows_key() -> str:
    """Read single keystroke on Windows using msvcrt."""
    import msvcrt

    try:
        ch = msvcrt.getwch()
    except (KeyboardInterrupt, EOFError):
        return "quit"

    if ch in ("\x00", "\xe0"):
        # Extended key prefix
        try:
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "up"
            elif ch2 == "P":
                return "down"
            elif ch2 == "K":
                return "left"
            elif ch2 == "M":
                return "right"
            elif ch2 == "G":  # Home
                return "home"
            elif ch2 == "O":  # End
                return "end"
        except Exception:
            pass
        return "other"

    if ch == "\x03":  # Ctrl+C
        raise KeyboardInterrupt
    elif ch in ("\r", "\n"):
        return "enter"
    elif ch == "\x1b":
        return "escape"
    elif ch in ("k", "K", "w", "W"):
        return "up"
    elif ch in ("j", "J", "s", "S"):
        return "down"
    elif ch in ("q", "Q"):
        return "quit"
    elif ch in (" ",):
        return "space"
    elif ch == "\x08":  # Backspace
        return "back"
    return ch.lower()


def _read_posix_key() -> str:
    """Read single keystroke on POSIX (macOS, Linux) using termios & tty."""
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt

        if ch == "\x1b":
            # Check if there are trailing chars in escape sequence
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                ch2 = sys.stdin.read(1)
                if ch2 in ("[", "O"):
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "up"
                    elif ch3 == "B":
                        return "down"
                    elif ch3 == "C":
                        return "right"
                    elif ch3 == "D":
                        return "left"
                    elif ch3 == "H":  # Home
                        return "home"
                    elif ch3 == "F":  # End
                        return "end"
                    elif ch3 in ("1", "2", "3", "4", "5", "6", "7", "8"):
                        # Extended escape (e.g. \x1b[3~ for Delete)
                        select.select([sys.stdin], [], [], 0.01)
                        try:
                            sys.stdin.read(1)
                        except Exception:
                            pass
                        return "other"
            return "escape"

        if ch in ("\r", "\n"):
            return "enter"
        elif ch in ("k", "K", "w", "W"):
            return "up"
        elif ch in ("j", "J", "s", "S"):
            return "down"
        elif ch in ("q", "Q"):
            return "quit"
        elif ch == " ":
            return "space"
        elif ch in ("\x7f", "\x08"):
            return "back"

        return ch.lower()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
