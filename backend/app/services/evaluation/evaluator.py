"""
Deterministic qualification evaluator.

Applies QUALIFICATION_RULES to an experiment's metrics and returns
a structured evaluation response.

Overall status logic:
  QUALIFIED        — every required rule returned PASS
  REJECTED         — at least one required rule returned FAIL
  INSUFFICIENT_DATA — no required rule FAIL, but one or more are missing data

The LLM must NEVER override this logic.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.services.evaluation.rules import (
    FAIL,
    INSUFFICIENT_DATA,
    PASS,
    QUALIFICATION_RULES,
    QualificationRule,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


class RuleResult:
    __slots__ = ("rule", "actual_value", "status")

    def __init__(
        self,
        rule: QualificationRule,
        actual_value: Optional[float],
        status: str,
    ) -> None:
        self.rule = rule
        self.actual_value = actual_value
        self.status = status

    def to_dict(self) -> dict:
        return {
            "metric": self.rule.metric,
            "operator": self.rule.operator,
            "threshold": self.rule.threshold,
            "actual_value": self.actual_value,
            "status": self.status,
        }


class EvaluationResult:
    __slots__ = ("overall_status", "rule_results")

    def __init__(self, overall_status: str, rule_results: List[RuleResult]) -> None:
        self.overall_status = overall_status
        self.rule_results = rule_results

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "rules": [r.to_dict() for r in self.rule_results],
        }


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def evaluate_experiment(metrics: Dict[str, Optional[float]]) -> EvaluationResult:
    """
    Evaluate an experiment against QUALIFICATION_RULES.

    Args:
        metrics: dict mapping canonical metric name → float value (or None if absent).

    Returns:
        EvaluationResult with overall_status and per-rule details.

    Algorithm:
        1. Evaluate each rule individually.
        2. If any required rule FAILs → REJECTED (definitive).
        3. If no FAIL but any required rule is INSUFFICIENT_DATA → INSUFFICIENT_DATA.
        4. If all required rules PASS → QUALIFIED.
    """
    rule_results: List[RuleResult] = []
    any_fail = False
    any_insufficient = False

    for rule in QUALIFICATION_RULES:
        actual = metrics.get(rule.metric)  # None if metric absent
        status = rule.evaluate(actual)

        if rule.required:
            if status == FAIL:
                any_fail = True
            elif status == INSUFFICIENT_DATA:
                any_insufficient = True

        rule_results.append(RuleResult(rule=rule, actual_value=actual, status=status))

    # Determine overall
    if any_fail:
        overall = "REJECTED"
    elif any_insufficient:
        overall = "INSUFFICIENT_DATA"
    else:
        overall = "QUALIFIED"

    return EvaluationResult(overall_status=overall, rule_results=rule_results)


def metrics_from_experiment_model(experiment) -> Dict[str, Optional[float]]:
    """
    Convert SQLAlchemy Experiment.metrics list to the dict format
    expected by evaluate_experiment().
    """
    return {m.name: m.value for m in experiment.metrics}
