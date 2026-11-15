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
            if line in ("up", "u", "k", "w", "\x1b[a", "\x1boa"):
                return "up"
            if line in ("down", "d", "j", "s", "\x1b[b", "\x1bob"):
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


def _read_posix_char(fd: int) -> str:
    """Read one key without allowing TextIOWrapper to buffer arrow bytes."""
    reader = sys.stdin.read
    if getattr(reader, "__self__", None) is sys.stdin:
        encoding = getattr(sys.stdin, "encoding", None) or "utf-8"
        return os.read(fd, 1).decode(encoding, errors="replace")
    # Keep custom file-like streams usable for embedded callers and tests.
    return reader(1)


def _read_posix_key() -> str:
    """Read single keystroke on POSIX (macOS, Linux) using termios & tty."""
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = _read_posix_char(fd)

        if ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt

        if ch == "\x1b":
            # Collect the whole CSI/SS3 sequence. Some macOS terminals send
            # escape bytes separately, and modified arrows contain parameters
            # between the introducer and the final direction byte.
            r, _, _ = select.select([fd], [], [], 0.2)
            if not r:
                return "escape"

            sequence = _read_posix_char(fd)
            if sequence not in ("[", "O"):
                return "escape"

            final = ""
            for _ in range(15):
                r, _, _ = select.select([fd], [], [], 0.1)
                if not r:
                    break
                final = _read_posix_char(fd)
                if final in "ABCDHF~":
                    break

            return {
                "A": "up",
                "B": "down",
                "C": "right",
                "D": "left",
                "H": "home",
                "F": "end",
            }.get(final, "other")

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
