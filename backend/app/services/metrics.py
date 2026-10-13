"""Shared numeric validity policy for persisted experiment metrics."""

from __future__ import annotations

import math
from typing import Any


def finite_metric_value(value: Any) -> tuple[float | None, bool]:
    """Return a finite metric as float, otherwise missing and whether it was non-finite."""
    if value is None or isinstance(value, bool):
        return None, False
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None, False
    if not math.isfinite(number):
        return None, True
    return number, False
