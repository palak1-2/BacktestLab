"""
Deterministic qualification rules for backtest experiments.

Rules are plain Python objects — not ML models, not LLM prompts.
The human researcher makes the final Keep / Modify / Discard decision.
This module only computes PASS / FAIL / INSUFFICIENT_DATA for each rule.

Adding a new rule requires no schema change — just add it to QUALIFICATION_RULES.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Optional


# ---------------------------------------------------------------------------
# Rule outcome constants
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Rule definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualificationRule:
    """
    A single deterministic qualification threshold.

    metric:    The canonical metric name to look up (e.g. "profit_factor").
    operator:  One of ">", ">=", "<", "<=", "==".
    threshold: The comparison value.
    required:  If True, INSUFFICIENT_DATA for this rule prevents QUALIFIED.
    """

    metric: str
    operator: str
    threshold: float
    required: bool = True

    def evaluate(self, actual_value: Optional[float]) -> str:
        """
        Return PASS, FAIL, or INSUFFICIENT_DATA.

        INSUFFICIENT_DATA is returned when actual_value is None (metric absent).
        A FAIL is always definitive — even if other metrics are missing.
        """
        if (
            actual_value is None
            or isinstance(actual_value, bool)
            or not isinstance(actual_value, Real)
            or not math.isfinite(actual_value)
        ):
            return INSUFFICIENT_DATA

        ops = {
            ">":  lambda a, t: a > t,
            ">=": lambda a, t: a >= t,
            "<":  lambda a, t: a < t,
            "<=": lambda a, t: a <= t,
            "==": lambda a, t: a == t,
        }
        fn = ops.get(self.operator)
        if fn is None:
            raise ValueError(f"Unknown operator: '{self.operator}'")

        return PASS if fn(actual_value, self.threshold) else FAIL


# ---------------------------------------------------------------------------
# Hard qualification rules (initial MVP set)
#
# These are the three required rules. Changing thresholds here is the only
# place that needs to change — the evaluator and API pick them up automatically.
# ---------------------------------------------------------------------------

QUALIFICATION_RULES: list[QualificationRule] = [
    QualificationRule(
        metric="profit_factor",
        operator=">",
        threshold=1.5,
        required=True,
    ),
    QualificationRule(
        metric="equity_drawdown_pct",
        operator="<",
        threshold=25.0,
        required=True,
    ),
    QualificationRule(
        metric="win_rate",
        operator=">",
        threshold=60.0,
        required=True,
    ),
]
