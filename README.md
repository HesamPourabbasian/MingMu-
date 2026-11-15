# MingMu (明眸)

> Cross-Platform System Health and Hardware Diagnostic Monitor for Windows, macOS, and Linux.

MingMu ("Bright Eyes") is a professional command-line interface (CLI) monitoring tool engineered to deliver accurate, real-time hardware diagnostics for battery condition, processor performance, and memory utilization across modern operating systems.

---

## Overview

Modern hardware architectures manage power, clock frequencies, and thermals through distinct operating system abstractions. Traditional command-line utilities often require root privileges, fail to expose low-level thermal registers, or are restricted to a single operating system.

MingMu provides a unified, cross-platform telemetry pipeline by interfacing directly with native system subsystems:

- **Windows**: Queries the Windows Management Instrumentation (WMI/CIM) subsystem via non-elevated PowerShell calls to read `Win32_Battery`, `BatteryStaticData`, `BatteryFullChargedCapacity`, `BatteryCycleCount`, and `MSAcpi_ThermalZoneTemperature`. Configures console output for standard UTF-8 Unicode rendering across Windows Terminal, PowerShell, and Command Prompt.
- **macOS**: Queries Apple Silicon internal thermal sensors (Performance Cores, Efficiency Cores, SoC Die, and Battery Gas Gauge) via rootless `IOHIDEventSystem` hooks, alongside official calibrated health metrics via `system_profiler` and `ioreg`.
- **Linux**: Interrogates kernel `sysfs` trees (`/sys/class/power_supply/`, `/sys/class/thermal/`) and procfs virtual memory statistics.

All metrics are evaluated against deterministic threshold rules and formatted into bordered Unicode tables styled with Colorama ANSI color profiles.

---

## Key Features

### Hardware Telemetry

- **Battery Health and Electrical Telemetry**:
  - Live charge level with color-coded visual progress gauges.
  - Operating health condition (e.g., Normal, Fair, Service Recommended).
  - Maximum Capacity retention percentage.
  - Accumulated hardware cycle count compared against the 1,000-cycle design rating.
  - Internal battery temperature via gas-gauge sensors.
  - Live terminal voltage, current amperage flow, and active power wattage rate.
  - Estimated remaining runtime on battery discharge.

- **Processor and Thermal Diagnostics**:
  - Real-time overall and individual per-core compute utilization.
  - Physical CPU core count versus logical hyperthreaded/virtual core count.
  - Active and maximum hardware clock frequencies.
  - Thermal telemetry: Package temperature, Performance Cores (pACC), Efficiency Cores (eACC), SoC Die junction, or ACPI thermal zones.
  - Load average metrics (1m, 5m, 15m) and core-normalized Load Factor calculations on POSIX systems.
  - Identification of top CPU-consuming processes (PID, Name, CPU %, Memory %).

- **Memory and Swap Saturation**:
  - Physical RAM breakdown: Total, Used, Available, Free, Active, Inactive, and Wired (Kernel) memory.
  - Visual utilization gauges for both physical RAM and virtual swap storage.
  - Swap utilization metrics and detection of memory exhaustion conditions.
  - Identification of top memory-consuming processes (PID, Name, Memory %, Resident Set Size).

### Display and Usability

- **Cyberpunk Shell Theme**: Cyan and blue framing, magenta telemetry accents, ASCII command prompts, and text tags create a high-contrast neon dashboard without emoji icons.
- **Full-Width Responsive Layout**: Automatically adapts to full terminal width dynamically, ensuring borders and progress bars scale proportionally to any terminal dimensions.
- **Personalized Hardware Greeting**: Automatically detects system user accounts and hardware models (e.g., Apple Silicon Mac, Windows PC, Linux machine) to display tailored status headers.
- **Interactive Main Menu**: Terminal dashboard featuring stylized ASCII branding, numbered shortcuts, and instant help manuals.
- **Multi-Language Support (i18n)**: Full native localization supporting 8 languages (English, Spanish, Japanese, Russian, French, German, Chinese, Turkish) with runtime switching and persistent configuration.
- **Advanced Diagnostic Views**: Dedicated expanded inspection screens for deep-dive analysis of individual subsystems.
- **Real-Time Watch Mode**: Compact dashboard updates changed rows in place to avoid screen flicker, with configurable sampling intervals.
- **Headless and Pipeline Support**: Full JSON schema export (`--json`) and plain-text logging compatibility (`--no-color`).

---

## Supported Operating Systems

- **Windows**: Windows 10, Windows 11, and Windows Server (x86_64 / ARM64).
- **macOS**: macOS 11 Big Sur through macOS 15+ (Apple Silicon M-series and Intel x86_64).
- **Linux**: Ubuntu, Debian, Fedora, Arch Linux, CentOS, openSUSE, and other POSIX distributions.

### Prerequisites

- Python 3.10 or higher.
- A terminal with ANSI color support (Windows Terminal, PowerShell 7+, Command Prompt, macOS Terminal, iTerm2, Alacritty, Kitty, GNOME Terminal).

---

## Installation

### Method 1: Global Installation via Pipx (Recommended)

Installing with `pipx` ensures MingMu runs globally in an isolated environment without dependency conflicts.

```bash
# Clone or navigate to the project directory
cd mingmu

# Install globally in editable mode
pipx install --editable .
```

Verify the installation:

```bash
mingmu --version
```

### Method 2: Development Installation via Poetry

For local development, source modifications, or running unit tests:

```bash
# Install dependencies into Poetry virtual environment
poetry install

# Run MingMu within the Poetry environment
poetry run mingmu

# Or activate the Poetry shell
poetry shell
mingmu
```

### Method 3: Installation via Pip (Windows / Standard Virtualenv)

```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate

pip install -e .
```

---

## Usage Reference

### Interactive Menu Mode

Running `mingmu` with no arguments in an interactive terminal session launches the main navigation menu with full keyboard navigation:

```bash
mingmu
```

#### Keyboard Navigation Controls

- **W / S keys**, **Up / Down Arrows (`↑` / `↓`)**, or **Vim keys (`k` / `j`)**: Move the active cursor selection up and down smoothly.
- **Enter (`↵`)** or **Space**: Activate and open the highlighted view or diagnostic monitor.
- **Escape** or **`q`**: Exit the application or return from submenus.
- **Direct Numbers (`0`-`7`)**: Instant shortcut jump directly to the target view.

The menu displays a personalized greeting with the detected system user and hardware model, rendering full-width bordered cards:

- `[1]` **Full System Overview**: Combined table displaying Battery, CPU, and Memory summaries.
- `[2]` **Advanced Battery Monitor**: Detailed electrical metrics, health condition, voltage, wattage, and hardware identifiers.
- `[3]` **Advanced CPU Monitor**: Per-core utilization bars, die and core temperatures, load factor, and top processes.
- `[4]` **Advanced Memory Monitor**: Detailed physical memory classification, swap usage, and heavy memory consumers.
- `[5]` **Live Watch Dashboard**: Real-time auto-refreshing monitor (press Ctrl+C to return to menu).
- `[6]` **Language Selection**: Interactive switcher for 8 supported languages with preference saved to disk.
- `[7]` **Help and Documentation**: Built-in reference manual explaining all metrics, status levels, and CLI commands.
- `[0]` **Exit**: Close MingMu.

---

### Command-Line Interface (Direct Commands and Scripting)

MingMu includes subcommands and options for direct terminal invocation and scripting pipelines.

#### Direct Table Outputs

```bash
# Print the full system overview table and exit immediately
mingmu --all

# Inspect battery health summary
mingmu battery

# Inspect advanced battery diagnostics (electrical specs, condition, cycle consumption)
mingmu battery --advanced
mingmu battery -a

# Inspect CPU health summary
mingmu cpu

# Inspect advanced CPU diagnostics (per-core breakdown, core thermals, top processes)
mingmu cpu --advanced
mingmu cpu -a

# Inspect memory health summary
mingmu ram

# Inspect advanced memory diagnostics (active/wired/swap breakdown, top processes)
mingmu ram --advanced
mingmu ram -a

# Display the comprehensive built-in documentation manual
mingmu help-guide
```

#### Real-Time Watch Mode

```bash
# Refresh system metrics continuously every 2.0 seconds (default)
mingmu watch

# Refresh every 5.0 seconds
mingmu watch --interval 5

# Stop automatically after 10 iterations
mingmu watch --interval 2 --count 10
```

#### Multi-Language Support (i18n)

MingMu provides built-in localization across all metric labels, status badges, section headers, menus, and greeting prompts:

```bash
# View system overview in Spanish
mingmu --lang es --all

# View advanced battery diagnostics in Japanese
mingmu --lang ja battery -a

# View advanced CPU diagnostics in Russian
mingmu --lang ru cpu -a

# View advanced memory diagnostics in German
mingmu --lang de ram -a

# View system overview in French
mingmu --lang fr --all

# View system overview in Chinese
mingmu --lang zh --all

# View system overview in Turkish
mingmu --lang tr --all
```

Supported language codes:
- `en`: English (Default)
- `es`: Spanish (Espanol)
- `ja`: Japanese (Nihongo)
- `ru`: Russian (Russkiy)
- `fr`: French (Francais)
- `de`: German (Deutsch)
- `zh`: Chinese (Zhongwen)
- `tr`: Turkish (Turkce)

Language preferences can also be configured interactively via menu option `[6]` and are saved across sessions to `~/.mingmu/config.json`.

#### Automation, Formatting, and Logging

```bash
# Specify interface language (en, es, ja, ru, fr, de, zh, tr)
mingmu --lang es --all
mingmu -l ja battery

# Export all telemetry as a structured JSON object
mingmu --json

# Disable all ANSI colors and escape sequences (suitable for plain-text logs)
mingmu --no-color

# Force table rendering to a specific terminal column width
mingmu --width 80

# Display standard Click CLI option flags
mingmu --help
```

---

## Health Evaluation Thresholds

MingMu evaluates raw metrics against defined baseline thresholds and assigns a status indicator:

- **GOOD**: Nominal operating conditions. No intervention required.
- **WARNING**: Metric is elevated above typical baseline. Workload or wear should be monitored.
- **CRITICAL**: Parameter is operating near or at hardware limit. Requires prompt action.

### Metric Threshold Reference

| Metric | Warning Threshold | Critical Threshold | Evaluation Direction |
|---|---|---|---|
| Battery State of Charge | Below 30.0% | Below 15.0% | Inverted (Lower is worse) |
| Battery Temperature | Above 35.0 deg C | Above 45.0 deg C | Ascending |
| Battery Cycle Count | Above 800 cycles | Above 1,000 cycles | Ascending |
| CPU Utilization | Above 70.0% | Above 90.0% | Ascending |
| CPU Package Temperature | Above 75.0 deg C | Above 95.0 deg C | Ascending |
| CPU Load Factor (1m / Cores) | Above 1.50 | Above 3.00 | Ascending |
| RAM Utilization | Above 75.0% | Above 90.0% | Ascending |
| Swap Utilization | Above 50.0% | Above 80.0% | Ascending |

---

## Project Structure

```
mingmu/
|-- pyproject.toml              # Build backend configuration, dependencies, and CLI entry point
|-- README.md                   # Technical documentation
|-- mingmu/
|   |-- __init__.py             # Package version and constants
|   |-- __main__.py             # Direct execution entry point (python -m mingmu)
|   |-- cli.py                  # Click CLI group, subcommand routing, and Windows console setup
|   |-- core/
|   |   |-- advanced.py         # Advanced diagnostic tables for Battery, CPU, and RAM
|   |   |-- battery.py          # Battery telemetry collector (macOS, Linux, Windows)
|   |   |-- cpu.py              # CPU metrics, multi-core breakdown, and top process monitor
|   |   `-- memory.py           # Physical RAM and virtual swap memory collector
|   |-- display/
|   |   |-- banner.py           # ASCII art rendering and dynamic progress bar formatters
|   |   |-- colors.py           # Colorama color abstraction layer and status badges
|   |   |-- formatters.py       # Human-readable unit formatters (bytes, time, frequency)
|   |   |-- help_view.py        # Complete documentation manual renderer
|   |   |-- menu.py             # Interactive terminal menu loop and keyboard navigation
|   |   `-- table.py            # Box-drawing Unicode table layout engine
|   |-- i18n/
|   |   |-- __init__.py         # Internationalization manager, configuration, and t() engine
|   |   |-- help_translations.py # Localized manual and documentation guides for 8 languages
|   |   `-- translations.py     # Translation dictionaries for 8 supported languages
|   `-- utils/
|       |-- keyboard.py         # Cross-platform raw keystroke reader and navigation engine
|       |-- macos_sensors.py    # macOS IOHIDEventSystem thermal and power telemetry
|       |-- platform_detect.py  # Platform detection for Windows, macOS, and Linux
|       |-- thresholds.py       # Boundary containers and health classification rules
|       |-- user_info.py        # System username and hardware model detection
|       `-- windows_sensors.py  # Windows WMI/CIM and PowerShell telemetry integration
`-- tests/
    |-- test_advanced.py        # Tests for advanced diagnostic sections, banners, and help view
    |-- test_collectors.py      # Tests for telemetry collectors and section builders
    |-- test_formatters.py      # Tests for string formatters and byte conversions
    |-- test_i18n.py            # Tests for multi-language translation, fallback, and config
    |-- test_keyboard.py        # Tests for keyboard navigation and single-keystroke input
    `-- test_platform.py        # Tests for platform detection and Windows support
```

---

## Running the Test Suite

Execute unit tests across all modules using pytest:

```bash
poetry run pytest -v
```

To run tests with code coverage reporting:

```bash
poetry run pytest --cov=mingmu tests/
```

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

Copyright (c) 2026 Hesam Pourabbasain.
