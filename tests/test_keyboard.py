"""
Unit tests for cross-platform keyboard reader utility.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import patch
import pytest

from mingmu.utils.keyboard import is_interactive, read_key


def test_is_interactive_check() -> None:
    """Test is_interactive returns a boolean."""
    res = is_interactive()
    assert isinstance(res, bool)


def test_read_key_non_interactive_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test read_key fallback when stdin is not a TTY."""
    # Simulate non-interactive stdin
    dummy_stdin = io.StringIO("up\ndown\nenter\nq\n")
    monkeypatch.setattr(sys, "stdin", dummy_stdin)

    assert read_key() == "up"
    assert read_key() == "down"
    assert read_key() == "enter"
    assert read_key() == "quit"


def test_read_key_non_interactive_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test read_key handles EOF gracefully."""
    dummy_stdin = io.StringIO("")
    monkeypatch.setattr(sys, "stdin", dummy_stdin)
    assert read_key() == "quit"


def test_read_key_posix_escape_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test POSIX arrow key reading logic."""
    from mingmu.utils.keyboard import _read_posix_key

    # Mock stdin.read to return escape sequence \x1b [ A (Up arrow)
    read_chars = ["\x1b", "[", "A"]
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr(sys.stdin, "read", lambda n: read_chars.pop(0))

    with patch("termios.tcgetattr", return_value=[]), \
         patch("termios.tcsetattr", return_value=None), \
         patch("tty.setraw", return_value=None), \
         patch("select.select", return_value=([sys.stdin], [], [])):
        key = _read_posix_key()
        assert key == "up"


def test_read_key_posix_down_arrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test POSIX Down arrow sequence \x1b [ B."""
    from mingmu.utils.keyboard import _read_posix_key

    read_chars = ["\x1b", "[", "B"]
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr(sys.stdin, "read", lambda n: read_chars.pop(0))

    with patch("termios.tcgetattr", return_value=[]), \
         patch("termios.tcsetattr", return_value=None), \
         patch("tty.setraw", return_value=None), \
         patch("select.select", return_value=([sys.stdin], [], [])):
        key = _read_posix_key()
        assert key == "down"


def test_read_key_posix_enter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test POSIX Enter key."""
    from mingmu.utils.keyboard import _read_posix_key

    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr(sys.stdin, "read", lambda n: "\r")

    with patch("termios.tcgetattr", return_value=[]), \
         patch("termios.tcsetattr", return_value=None), \
         patch("tty.setraw", return_value=None):
        key = _read_posix_key()
        assert key == "enter"
