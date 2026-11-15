"""
HTML Diagnostic Health Report Generator for MingMu (明眸).

Generates a standalone, dark-themed, responsive HTML report featuring
system hardware diagnostics, status badges, and telemetry tables.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from pathlib import Path

from mingmu import __app_name__, __app_name_cn__, __version__
from mingmu.display.table import Section
from mingmu.utils.platform_detect import get_platform_info
from mingmu.utils.thresholds import Status

log = logging.getLogger(__name__)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from strings."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _status_color(status: Status) -> str:
    """Map Status to a neon hex color."""
    if status == Status.GOOD:
        return "#00ff88"
    elif status == Status.WARNING:
        return "#ffb800"
    elif status == Status.CRITICAL:
        return "#ff3366"
    elif status in (Status.INFO, Status.CHARGING):
        return "#00f0ff"
    return "#8892b0"


def generate_html_report(
    sections: list[Section],
    output_path: str | Path | None = None,
) -> Path:
    """Generate a self-contained HTML system health report file."""
    pinfo = get_platform_info()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine worst overall status across all sections
    all_statuses = [sec.overall_status for sec in sections]
    if Status.CRITICAL in all_statuses:
        system_status = Status.CRITICAL
    elif Status.WARNING in all_statuses:
        system_status = Status.WARNING
    else:
        system_status = Status.GOOD

    sys_status_color = _status_color(system_status)

    # Resolve output file path
    if output_path is None:
        filename = f"mingmu_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        target_path = Path.cwd() / filename
    else:
        target_path = Path(output_path).resolve()

    # Build section cards HTML
    sections_html: list[str] = []
    for sec in sections:
        card_color = _status_color(sec.overall_status)
        rows_html: list[str] = []

        for row in sec.rows:
            clean_label = html.escape(_strip_ansi(row.label.strip().lstrip("↳ ")))
            clean_val = html.escape(_strip_ansi(row.value.strip()))
            badge_color = _status_color(row.status)
            badge_text = html.escape(row.status.value)

            # Check if value represents a percentage gauge
            gauge_html = ""
            pct_match = re.search(r"(\d+(?:\.\d+)?)%", clean_val)
            if pct_match and ("[" in clean_val or "Usage" in clean_label or "Level" in clean_label):
                pct_val = float(pct_match.group(1))
                bar_col = "#00ff88" if pct_val < 70 else ("#ffb800" if pct_val < 90 else "#ff3366")
                gauge_html = f"""
                <div class="progress-track">
                    <div class="progress-bar" style="width: {min(100.0, pct_val):.1f}%; background-color: {bar_col};"></div>
                </div>
                """

            rows_html.append(f"""
            <tr>
                <td class="metric-label">{clean_label}</td>
                <td class="metric-value">
                    {clean_val}
                    {gauge_html}
                </td>
                <td class="metric-status">
                    <span class="badge" style="color: {badge_color}; border-color: {badge_color};">
                        {badge_text}
                    </span>
                </td>
            </tr>
            """)

        sections_html.append(f"""
        <div class="card">
            <div class="card-header">
                <div class="card-title">
                    <span class="icon-tag">[{html.escape(sec.icon)}]</span>
                    <h3>{html.escape(sec.title)}</h3>
                </div>
                <span class="badge" style="color: {card_color}; border-color: {card_color}; font-weight: bold;">
                    [{html.escape(sec.overall_status.value.upper())}]
                </span>
            </div>
            <div class="table-container">
                <table class="report-table">
                    <thead>
                        <tr>
                            <th>METRIC</th>
                            <th>VALUE</th>
                            <th>STATUS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(rows_html)}
                    </tbody>
                </table>
            </div>
        </div>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{__app_name_cn__} {__app_name__} — System Diagnostic Report</title>
    <style>
        :root {{
            --bg-base: #0a0e17;
            --bg-card: rgba(18, 26, 43, 0.75);
            --border-card: rgba(0, 240, 255, 0.18);
            --border-hover: rgba(0, 240, 255, 0.4);
            --cyan: #00f0ff;
            --magenta: #ff007f;
            --text-main: #f0f4f8;
            --text-dim: #8892b0;
            --table-hover: rgba(0, 240, 255, 0.05);
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            line-height: 1.5;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            background: linear-gradient(135deg, rgba(18, 26, 43, 0.95), rgba(10, 14, 23, 0.95));
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 24px 30px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .brand-cn {{
            font-size: 2.2rem;
            font-weight: 900;
            color: var(--cyan);
            text-shadow: 0 0 12px rgba(0, 240, 255, 0.4);
        }}
        .brand-en {{
            font-size: 1.6rem;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: #fff;
        }}
        .brand-sub {{
            color: var(--text-dim);
            font-size: 0.85rem;
            letter-spacing: 1px;
        }}
        .meta-chips {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .chip {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.85rem;
            color: var(--text-dim);
        }}
        .chip strong {{
            color: var(--cyan);
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(550px, 1fr));
            gap: 20px;
        }}
        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 10px;
            padding: 20px;
            backdrop-filter: blur(10px);
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            border-color: var(--border-hover);
            box-shadow: 0 4px 20px rgba(0, 240, 255, 0.12);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 12px;
            margin-bottom: 14px;
        }}
        .card-title {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .icon-tag {{
            color: var(--magenta);
            font-weight: bold;
            font-family: monospace;
            font-size: 0.95rem;
        }}
        .card-title h3 {{
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 0.5px;
        }}
        .badge {{
            display: inline-block;
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid;
            font-family: monospace;
            letter-spacing: 0.5px;
            background: rgba(0, 0, 0, 0.3);
        }}
        .table-container {{
            overflow-x: auto;
        }}
        .report-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        .report-table th {{
            text-align: left;
            color: var(--text-dim);
            font-size: 0.75rem;
            letter-spacing: 1px;
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }}
        .report-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            vertical-align: middle;
        }}
        .report-table tr:hover {{
            background-color: var(--table-hover);
        }}
        .metric-label {{
            color: #cbd5e1;
            font-weight: 500;
            width: 40%;
        }}
        .metric-value {{
            color: #ffffff;
            font-weight: 600;
            font-family: monospace;
            width: 45%;
        }}
        .metric-status {{
            text-align: right;
            width: 15%;
        }}
        .progress-track {{
            background: rgba(255, 255, 255, 0.1);
            height: 6px;
            border-radius: 3px;
            margin-top: 6px;
            overflow: hidden;
            width: 100%;
            max-width: 220px;
        }}
        .progress-bar {{
            height: 100%;
            border-radius: 3px;
        }}
        footer {{
            text-align: center;
            margin-top: 36px;
            padding: 18px;
            color: var(--text-dim);
            font-size: 0.85rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }}
        footer a {{
            color: var(--cyan);
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <span class="brand-cn">{__app_name_cn__}</span>
                <div>
                    <div class="brand-en">{__app_name__}</div>
                    <div class="brand-sub">HARDWARE & SYSTEM HEALTH TELEMETRY · v{__version__}</div>
                </div>
            </div>
            <div class="meta-chips">
                <div class="chip">System: <strong>{pinfo.system} ({pinfo.machine})</strong></div>
                <div class="chip">Kernel: <strong>{pinfo.release.split('.')[0]}</strong></div>
                <div class="chip">Generated: <strong>{now_str}</strong></div>
                <div class="chip" style="border-color: {sys_status_color};">Status: <strong style="color: {sys_status_color};">[{system_status.value.upper()}]</strong></div>
            </div>
        </header>

        <div class="grid">
            {"".join(sections_html)}
        </div>

        <footer>
            Generated by <strong>{__app_name_cn__} {__app_name__} v{__version__}</strong> · Open-source hardware telemetry monitor for macOS, Linux, and Windows.
        </footer>
    </div>
</body>
</html>
"""

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(html_content, encoding="utf-8")
    log.info("Report written to %s", target_path)
    return target_path
