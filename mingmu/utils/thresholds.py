"""
Health-assessment thresholds.

Centralised threshold definitions used to classify raw metrics into
status levels (GOOD / WARNING / CRITICAL).  Every threshold is a
simple pair ``(warning, critical)`` — values *below* warning are GOOD,
*between* warning and critical are WARNING, and *above* critical are
CRITICAL.  For metrics where "lower is worse" (e.g. battery charge),
the logic is inverted in the respective collector.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ── Status Levels ─────────────────────────────────────────────

class Status(Enum):
    """Health-status classification."""

    GOOD = "Good"
    WARNING = "Warning"
    CRITICAL = "Critical"
    UNKNOWN = "Unknown"
    INFO = "Info"
    CHARGING = "Charging"


# ── Threshold container ──────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Threshold:
    """A (warning, critical) boundary pair.

    By default, values are evaluated in *ascending* order:
        value < warning  → GOOD
        warning ≤ value < critical  → WARNING
        value ≥ critical  → CRITICAL

    Set ``inverted=True`` for metrics where *lower* is *worse*
    (e.g. battery charge percentage).
    """

    warning: float
    critical: float
    inverted: bool = False

    def evaluate(self, value: float | None) -> Status:
        """Return the status for *value*."""
        if value is None:
            return Status.UNKNOWN
        if self.inverted:
            if value > self.warning:
                return Status.GOOD
            if value > self.critical:
                return Status.WARNING
            return Status.CRITICAL
        else:
            if value < self.warning:
                return Status.GOOD
            if value < self.critical:
                return Status.WARNING
            return Status.CRITICAL


# ── Battery thresholds ────────────────────────────────────────

BATTERY_CHARGE = Threshold(warning=30.0, critical=15.0, inverted=True)
BATTERY_TEMPERATURE = Threshold(warning=35.0, critical=45.0)
BATTERY_CYCLE_COUNT = Threshold(warning=800, critical=1000)

# ── CPU thresholds ────────────────────────────────────────────

CPU_USAGE = Threshold(warning=70.0, critical=90.0)
CPU_TEMPERATURE = Threshold(warning=75.0, critical=95.0)
CPU_LOAD_FACTOR = Threshold(warning=1.5, critical=3.0)
# load_factor = load_avg_1m / logical_core_count

# ── Memory thresholds ────────────────────────────────────────

MEMORY_USAGE = Threshold(warning=75.0, critical=90.0)
SWAP_USAGE = Threshold(warning=50.0, critical=80.0)

# ── Disk thresholds ──────────────────────────────────────────

DISK_USAGE = Threshold(warning=80.0, critical=90.0)

# ── GPU thresholds ───────────────────────────────────────────

GPU_USAGE = Threshold(warning=80.0, critical=95.0)
GPU_TEMPERATURE = Threshold(warning=80.0, critical=95.0)
GPU_MEMORY = Threshold(warning=80.0, critical=95.0)

