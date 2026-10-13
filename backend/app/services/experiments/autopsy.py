"""Deterministic Research Autopsy summaries built from stored MT5 experiments.

All counts, thresholds, metric summaries, and evidence IDs are computed here.
An LLM may narrate these findings later, but must not replace their values.
"""

from __future__ import annotations

import math
from collections import Counter
from statistics import median
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.experiment import EvaluationStatus, Experiment, ImportBatch
from app.services.evaluation.evaluator import evaluate_experiment
from app.services.evaluation.rules import QUALIFICATION_RULES, FAIL


ANALYSIS_METRICS = ("profit_factor", "equity_drawdown_pct", "win_rate")
MINIMUM_PARAMETER_GROUP_SUPPORT = 3

METRIC_LABELS = {
    "profit_factor": "Profit factor",
    "equity_drawdown_pct": "Equity drawdown",
    "win_rate": "Win rate",
}

FAILURE_COPY = {
    "profit_factor": (
        "Low profit factor",
        "Experiments with a valid profit factor at or below 1.5 did not meet the configured threshold.",
    ),
    "equity_drawdown_pct": (
        "Excessive drawdown",
        "Experiments with valid equity drawdown at or above 25% did not meet the configured threshold.",
    ),
    "win_rate": (
        "Low win rate",
        "Experiments with a valid win rate at or below 60% did not meet the configured threshold.",
    ),
}


def _metric_map(experiment: Experiment) -> dict[str, float | None]:
    return {metric.name: metric.value for metric in experiment.metrics}


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parameter_value(parameter: Any) -> tuple[str | None, Any, str | None]:
    """Return (kind, normalized value, unusable reason) for a stored parameter."""
    raw_value = parameter.value
    if raw_value is None or not str(raw_value).strip():
        return None, None, "missing"

    data_type = getattr(parameter.data_type, "value", parameter.data_type)
    data_type = str(data_type).strip().lower()
    text = str(raw_value).strip()

    if data_type == "integer":
        try:
            number = int(text)
        except (TypeError, ValueError):
            return None, None, "malformed"
        return "numeric", number, None

    if data_type == "float":
        try:
            number = float(text)
        except (OverflowError, TypeError, ValueError):
            return None, None, "malformed"
        if not math.isfinite(number):
            return None, None, "non_finite"
        return "numeric", number, None

    if data_type == "boolean":
        normalized = text.lower()
        if normalized not in {"true", "false"}:
            return None, None, "malformed"
        return "boolean", normalized, None

    if data_type == "string":
        return "categorical", text, None

    return None, None, "unsupported"


def _numeric_groups(values: list[tuple[int | float, int]]) -> list[list[tuple[int | float, int]]]:
    """Partition sorted (value, experiment_id) pairs into at most five equal-count groups."""
    counts = Counter(value for value, _ in values)
    distinct_values = sorted(counts)
    group_count = min(5, len(distinct_values))
    if not group_count:
        return []

    cumulative: list[int] = []
    running_count = 0
    for value in distinct_values:
        running_count += counts[value]
        cumulative.append(running_count)

    boundaries = [0]
    for group_number in range(1, group_count):
        earliest = boundaries[-1] + 1
        latest = len(distinct_values) - (group_count - group_number)
        boundary = min(
            range(earliest, latest + 1),
            key=lambda index: (
                abs(cumulative[index - 1] * group_count - len(values) * group_number),
                index,
            ),
        )
        boundaries.append(boundary)
    boundaries.append(len(distinct_values))

    groups = []
    for start, end in zip(boundaries, boundaries[1:]):
        grouped_values = set(distinct_values[start:end])
        groups.append([(value, experiment_id) for value, experiment_id in values if value in grouped_values])
    return groups


def _build_parameter_analysis(
    experiments: list[Experiment],
    experiment_metrics: dict[int, dict[str, float | None]],
) -> dict[str, Any]:
    names = sorted({parameter.name for experiment in experiments for parameter in experiment.parameters})
    parameters: list[dict[str, Any]] = []
    entries_by_name: dict[str, list[tuple[Experiment, Any]]] = {name: [] for name in names}
    for experiment in experiments:
        for parameter in experiment.parameters:
            entries_by_name[parameter.name].append((experiment, parameter))
    experiments_by_id = {experiment.id: experiment for experiment in experiments}

    for name in names:
        entries = entries_by_name[name]
        grouped: dict[tuple[str, Any], list[Experiment]] = {}
        unusable: dict[str, list[int]] = {
            "missing": [],
            "malformed": [],
            "non_finite": [],
            "unsupported": [],
        }
        present_ids: set[int] = set()
        parameter_types: set[str] = set()

        for experiment, parameter in entries:
            present_ids.add(experiment.id)
            parameter_type = getattr(parameter.data_type, "value", parameter.data_type)
            parameter_types.add(str(parameter_type).strip().lower())
            kind, value, reason = _parameter_value(parameter)
            if reason is not None:
                unusable[reason].append(experiment.id)
                continue
            grouped.setdefault((kind, value), []).append(experiment)

        for experiment in experiments:
            if experiment.id not in present_ids:
                unusable["missing"].append(experiment.id)

        group_records: list[dict[str, Any]] = []

        def add_group(kind: str, group_experiments: list[Experiment], **range_values: Any) -> None:
            evidence_ids = sorted(experiment.id for experiment in group_experiments)
            outcome_summaries = {}
            for metric_name in ANALYSIS_METRICS:
                observed = [
                    number
                    for experiment in group_experiments
                    if (number := _finite_number(experiment_metrics[experiment.id].get(metric_name))) is not None
                ]
                outcome_summaries[metric_name] = {
                    "usable_count": len(observed),
                    "missing_count": len(group_experiments) - len(observed),
                    "min": _rounded(min(observed)) if observed else None,
                    "median": _rounded(_finite_median(observed)) if observed else None,
                    "max": _rounded(max(observed)) if observed else None,
                    "status": "available" if observed else "unavailable",
                }
            group_records.append({
                "kind": kind,
                **range_values,
                "experiment_count": len(group_experiments),
                "low_support": len(group_experiments) < MINIMUM_PARAMETER_GROUP_SUPPORT,
                "evidence_experiment_ids": evidence_ids,
                "outcomes": outcome_summaries,
            })

        numeric_values = sorted(
            (value, experiment.id)
            for (kind, value), matching in grouped.items()
            if kind == "numeric"
            for experiment in matching
        )
        for numeric_group in _numeric_groups(numeric_values):
            group_values = [value for value, _ in numeric_group]
            experiment_ids = {experiment_id for _, experiment_id in numeric_group}
            add_group(
                "numeric_range",
                [experiments_by_id[experiment_id] for experiment_id in sorted(experiment_ids)],
                minimum=min(group_values),
                maximum=max(group_values),
            )

        for (kind, value), matching in sorted(
            grouped.items(),
            key=lambda item: (item[0][0], str(item[0][1])),
        ):
            if kind in {"boolean", "categorical"}:
                add_group(kind, matching, value=value)

        group_records.sort(
            key=lambda group: (
                group["kind"],
                group.get("minimum", group.get("value")),
                group.get("maximum", group.get("value")),
            )
        )
        parameters.append({
            "name": name,
            "parameter_types": sorted(parameter_types),
            "experiment_count": len(experiments),
            "usable_value_count": sum(group["experiment_count"] for group in group_records),
            "missing_parameter_count": len(unusable["missing"]),
            "unusable_value_count": sum(len(ids) for ids in unusable.values()),
            "unusable_values": {
                reason: {
                    "count": len(ids),
                    "evidence_experiment_ids": sorted(ids),
                }
                for reason, ids in unusable.items()
                if ids
            },
            "groups": group_records,
        })

    return {
        "grouping_method": (
            "Numeric observations are sorted and divided into up to five contiguous, "
            "approximately equal-count groups; identical numeric values are never split. "
            "Categorical and boolean values are grouped by exact normalized value."
        ),
        "minimum_group_support": MINIMUM_PARAMETER_GROUP_SUPPORT,
        "interpretation": (
            "These are descriptive associations within the imported experiments, not causal "
            "findings or predictions of future trading performance. Meeting the minimum "
            "support threshold does not establish statistical significance."
        ),
        "parameters": parameters,
    }


def _finite_median(values: list[float]) -> float:
    """Compute a median without overflowing when averaging large finite values."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return ordered[middle - 1] / 2 + ordered[middle] / 2


def build_autopsy(db: Session, import_batch_id: int) -> dict[str, Any] | None:
    """Build a compact, evidence-linked autopsy payload for one imported report."""
    batch = db.query(ImportBatch).filter(ImportBatch.id == import_batch_id).first()
    if batch is None:
        return None

    experiments = (
        db.query(Experiment)
        .options(joinedload(Experiment.metrics), joinedload(Experiment.parameters))
        .filter(Experiment.import_batch_id == import_batch_id)
        .order_by(Experiment.id)
        .all()
    )

    status_counts: Counter[str] = Counter()
    metric_values: dict[str, list[float]] = {}
    experiment_metrics: dict[int, dict[str, float | None]] = {}
    evaluations: dict[int, Any] = {}

    for experiment in experiments:
        metrics = _metric_map(experiment)
        experiment_metrics[experiment.id] = metrics
        evaluation = evaluate_experiment(metrics)
        evaluations[experiment.id] = evaluation
        status_counts[evaluation.overall_status] += 1
        for name, value in metrics.items():
            if value is not None:
                metric_values.setdefault(name, []).append(float(value))

    metric_summary = {}
    all_metric_names = sorted({m.name for exp in experiments for m in exp.metrics})
    for name in all_metric_names:
        values = metric_values.get(name, [])
        metric_summary[name] = {
            "available_count": len(values),
            "missing_count": len(experiments) - len(values),
            "min": _rounded(min(values)) if values else None,
            "median": _rounded(float(median(values))) if values else None,
            "max": _rounded(max(values)) if values else None,
        }

    findings: list[dict[str, Any]] = []
    finding_number = 1
    total = len(experiments)

    # One finding per deterministic qualification rule that actually fails.
    for rule in QUALIFICATION_RULES:
        failed_ids = [
            experiment.id
            for experiment in experiments
            if next(
                (rr.status for rr in evaluations[experiment.id].rule_results if rr.rule.metric == rule.metric),
                None,
            ) == FAIL
        ]
        if failed_ids:
            title, description = FAILURE_COPY.get(
                rule.metric,
                (f"Rule not met: {rule.metric}", f"Experiments failed the configured {rule.metric} threshold."),
            )
            findings.append({
                "finding_id": f"F-{finding_number:03d}",
                "kind": "failure_pattern",
                "title": title,
                "description": description,
                "metric": rule.metric,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "count": len(failed_ids),
                "percentage_of_all": round((len(failed_ids) / total) * 100, 2) if total else 0.0,
                "evidence_experiment_ids": failed_ids[:10],
                "evidence_count": len(failed_ids),
            })
            finding_number += 1

    # Explicitly surface missing qualification metrics; never infer them.
    for rule in QUALIFICATION_RULES:
        available = sum(
            experiment_metrics[exp.id].get(rule.metric) is not None for exp in experiments
        )
        missing = total - available
        if missing:
            findings.append({
                "finding_id": f"F-{finding_number:03d}",
                "kind": "data_gap",
                "title": f"{METRIC_LABELS.get(rule.metric, rule.metric)} data is incomplete",
                "description": (
                    f"{missing} of {total} experiments lack a usable {METRIC_LABELS.get(rule.metric, rule.metric).lower()} value. "
                    "Those experiments cannot pass all configured qualification rules until this metric is available."
                ),
                "metric": rule.metric,
                "count": missing,
                "percentage_of_all": round((missing / total) * 100, 2) if total else 0.0,
                "evidence_experiment_ids": [
                    exp.id for exp in experiments
                    if experiment_metrics[exp.id].get(rule.metric) is None
                ][:10],
                "evidence_count": missing,
            })
            finding_number += 1

    return {
        "import_batch_id": batch.id,
        "source_file": batch.source_file,
        "source_format": batch.source_format.value,
        "total_experiments": total,
        "status_counts": {
            "qualified": status_counts.get("QUALIFIED", 0),
            "rejected": status_counts.get("REJECTED", 0),
            "incomplete": status_counts.get("INSUFFICIENT_DATA", 0),
            "pending": status_counts.get("PENDING", 0),
        },
        "metric_summary": metric_summary,
        "parameter_analysis": _build_parameter_analysis(experiments, experiment_metrics),
        "findings": findings,
        "analysis_notes": [
            "Failure groups can overlap: one experiment may fail multiple rules.",
            "Parameter groups are descriptive associations, not causal findings or predictions of future trading performance.",
            "All values in this response are computed from stored experiment records; no LLM is used here.",
        ],
    }
