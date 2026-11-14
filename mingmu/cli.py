"""
MingMu CLI — command-line interface and menu dispatcher.

Usage examples::

    mingmu                # interactive main menu with colored ASCII art
    mingmu --all          # full system overview table (direct output)
    mingmu battery        # battery health table
    mingmu battery -a     # advanced battery diagnostics table
    mingmu cpu            # CPU health table
    mingmu cpu -a         # advanced CPU & per-core diagnostics table
    mingmu ram            # memory health table
    mingmu ram -a         # advanced memory & swap diagnostics table
    mingmu watch          # live-refresh dashboard (default 2s)
    mingmu help-guide     # view comprehensive help documentation
    mingmu --json         # machine-readable JSON dump
    mingmu --no-color     # disable coloured output
"""

from __future__ import annotations

import json
import os
import platform
import signal
import sys
import time
from typing import Sequence

import click

from mingmu import __app_name__, __app_name_cn__, __version__
from mingmu.core.advanced import (
    build_advanced_battery_section,
    build_advanced_cpu_section,
    build_advanced_memory_section,
)
from mingmu.core.battery import build_battery_section
from mingmu.core.cpu import build_cpu_section
from mingmu.core.memory import build_memory_section
from mingmu.display.colors import disable_colors
from mingmu.display.help_view import render_help_view
from mingmu.display.menu import show_menu
from mingmu.display.table import Section, TableRenderer
from mingmu.i18n import SUPPORTED_LANGUAGES, init_language, t
from mingmu.utils.platform_detect import get_platform_info, is_supported


# Enable UTF-8 encoding in Windows console (PowerShell / cmd / Windows Terminal)
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ── Helpers ──────────────────────────────────────────────────

def _render_sections(sections: list[Section], width: int | None) -> str:
    """Render a list of sections into a table string."""
    renderer = TableRenderer(width=width)
    return renderer.render(sections)


def _all_sections() -> list[Section]:
    """Collect and build every overview section."""
    return [
        build_battery_section(),
        build_cpu_section(),
        build_memory_section(),
    ]


def _clear_screen() -> None:
    """Clear terminal screen (cross-platform)."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def _sections_to_dict(sections: list[Section]) -> dict:
    """Convert sections to a JSON-serialisable dict."""
    from datetime import datetime

    pinfo = get_platform_info()
    output: dict = {
        "app": f"{__app_name_cn__} {__app_name__}",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "platform": {
            "system": pinfo.system,
            "release": pinfo.release,
            "machine": pinfo.machine,
            "python": pinfo.python_version,
        },
        "sections": {},
    }
    for section in sections:
        sec_data: dict = {
            "status": section.overall_status.value,
            "metrics": {},
        }
        for row in section.rows:
            sec_data["metrics"][row.label.strip().lstrip("↳ ")] = {
                "value": row.value,
                "status": row.status.value,
            }
        output["sections"][section.title] = sec_data
    return output


# ── Click CLI ────────────────────────────────────────────────

class MingMuGroup(click.Group):
    """Custom group that shows the interactive menu or full overview
    when invoked without a subcommand."""

    def invoke(self, ctx: click.Context) -> None:
        super().invoke(ctx)
        # If no subcommand was given, decide between menu and overview
        if ctx.invoked_subcommand is None:
            if ctx.obj.get("as_json") or ctx.obj.get("show_all") or not sys.stdin.isatty():
                ctx.invoke(overview)
            else:
                show_menu(width=ctx.obj.get("width"))


@click.group(
    cls=MingMuGroup,
    invoke_without_command=True,
    help=f"{__app_name_cn__} {__app_name__} — Professional System Health Monitor",
)
@click.option("--all", "show_all", is_flag=True, help="Print full system overview table directly.")
@click.option("--menu", "force_menu", is_flag=True, help="Launch interactive main menu.")
@click.option(
    "-l", "--lang",
    type=click.Choice(list(SUPPORTED_LANGUAGES.keys()), case_sensitive=False),
    default=None,
    help="Set interface language (en, es, ja, ru, fr, de, zh, tr).",
)
@click.option("--no-color", is_flag=True, help="Disable coloured output.")
@click.option("--json", "as_json", is_flag=True, help="Output in JSON format.")
@click.option("--width", type=int, default=None, help="Force table width (columns).")
@click.version_option(__version__, prog_name=__app_name__)
@click.pass_context
def main(
    ctx: click.Context,
    show_all: bool,
    force_menu: bool,
    lang: str | None,
    no_color: bool,
    as_json: bool,
    width: int | None,
) -> None:
    """MingMu (明眸) system health monitor."""
    ctx.ensure_object(dict)
    ctx.obj["show_all"] = show_all
    ctx.obj["force_menu"] = force_menu
    ctx.obj["lang"] = lang
    ctx.obj["no_color"] = no_color
    ctx.obj["as_json"] = as_json
    ctx.obj["width"] = width

    init_language(cli_override=lang)

    if no_color:
        disable_colors()

    if not is_supported():
        click.echo(
            click.style(
                f"⚠  MingMu supports macOS, Linux, and Windows only. Detected: {platform.system()}",
                fg="red",
            ),
            err=True,
        )
        sys.exit(1)

    if force_menu:
        show_menu(width=width)
        ctx.exit()


# ── Subcommands ──────────────────────────────────────────────

@main.command(name="menu", short_help="Open interactive main menu.")
@click.pass_context
def menu_cmd(ctx: click.Context) -> None:
    """Launch the interactive terminal menu with ASCII banner."""
    show_menu(width=ctx.obj.get("width"))


@main.command(name="battery", short_help="Show battery health.")
@click.option("-a", "--advanced", is_flag=True, help="Display detailed electrical & health diagnostics.")
@click.pass_context
def battery_cmd(ctx: click.Context, advanced: bool) -> None:
    """Display battery metrics table."""
    if advanced:
        sections = [build_advanced_battery_section()]
    else:
        sections = [build_battery_section()]
    _output(ctx, sections)


@main.command(name="cpu", short_help="Show CPU health.")
@click.option("-a", "--advanced", is_flag=True, help="Display per-core usage, die thermals, & top processes.")
@click.pass_context
def cpu_cmd(ctx: click.Context, advanced: bool) -> None:
    """Display CPU metrics table."""
    if advanced:
        sections = [build_advanced_cpu_section()]
    else:
        sections = [build_cpu_section()]
    _output(ctx, sections)


@main.command(name="ram", short_help="Show memory health.")
@click.option("-a", "--advanced", is_flag=True, help="Display detailed RAM breakdown, swap, & top consumers.")
@click.pass_context
def ram_cmd(ctx: click.Context, advanced: bool) -> None:
    """Display memory metrics table."""
    if advanced:
        sections = [build_advanced_memory_section()]
    else:
        sections = [build_memory_section()]
    _output(ctx, sections)


@main.command(name="help-guide", short_help="Comprehensive help & metric explanation.")
@click.pass_context
def help_guide_cmd(ctx: click.Context) -> None:
    """Display complete MingMu documentation guide."""
    click.echo(render_help_view(width=ctx.obj.get("width")))


@main.command(name="watch", short_help="Live-refresh mode.")
@click.option(
    "-i", "--interval",
    type=float,
    default=2.0,
    show_default=True,
    help="Refresh interval in seconds.",
)
@click.option(
    "-c", "--count",
    "max_count",
    type=int,
    default=None,
    help="Stop after N refreshes (default: unlimited).",
)
@click.pass_context
def watch_cmd(ctx: click.Context, interval: float, max_count: int | None) -> None:
    """Continuously refresh system metrics.

    Press Ctrl+C to stop.
    """
    def _handle_sigint(signum: int, frame: object) -> None:
        click.echo("\n" + click.style(f"  {t('stopped_goodbye')} 👋", fg="cyan"))
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    iteration = 0
    while True:
        _clear_screen()
        sections = _all_sections()

        if ctx.obj.get("as_json"):
            data = _sections_to_dict(sections)
            data["watch"] = {"iteration": iteration, "interval": interval}
            click.echo(json.dumps(data, indent=2))
        else:
            table = _render_sections(sections, ctx.obj.get("width"))
            click.echo(table)
            click.echo()
            from mingmu.display.colors import dim as dim_text
            click.echo(dim_text(f"  ↻  {t('live_monitoring', interval=interval)}"))

        iteration += 1
        if max_count is not None and iteration >= max_count:
            break

        time.sleep(interval)


# ── Default overview command ─────────────────────────────────

def overview() -> None:
    """Full system overview table (direct output)."""
    ctx = click.get_current_context()
    sections = _all_sections()
    _output(ctx, sections)


# ── Output dispatcher ────────────────────────────────────────

def _output(ctx: click.Context, sections: list[Section]) -> None:
    """Print sections as table or JSON."""
    if ctx.obj.get("as_json"):
        data = _sections_to_dict(sections)
        click.echo(json.dumps(data, indent=2))
    else:
        table = _render_sections(sections, ctx.obj.get("width"))
        click.echo(table)
