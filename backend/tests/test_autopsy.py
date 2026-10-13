"""Tests for deterministic Research Autopsy summaries."""

import io
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.models.experiment import (
    DataType,
    EvaluationStatus,
    Experiment,
    ExperimentMetric,
    ExperimentParameter,
    ImportBatch,
    SourceFormat,
)
from app.services.evaluation.evaluator import evaluate_experiment
from app.services.experiments.autopsy import _build_parameter_analysis, _parameter_value
from tests.conftest import make_xlsx_bytes


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _import_report(client: TestClient, *, rows: int = 12, include_win_rate: bool = True) -> dict:
    response = client.post(
        "/experiments/import",
        files={"file": ("autopsy.xlsx", io.BytesIO(make_xlsx_bytes(rows, include_win_rate)), XLSX_MIME)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_controlled_batch(db_session, rows: list[dict]) -> int:
    batch = ImportBatch(
        source_file="controlled-fixture.xlsx",
        source_format=SourceFormat.xlsx,
        source_hash="c" * 64,
        experiments_created=len(rows),
    )
    db_session.add(batch)
    db_session.flush()

    for index, row in enumerate(rows):
        metrics = row.get("metrics", {})
        evaluation = evaluate_experiment(metrics)
        experiment = Experiment(
            import_batch_id=batch.id,
            source_file=batch.source_file,
            source_format=SourceFormat.xlsx,
            optimization_pass=index,
            evaluation_status=EvaluationStatus(evaluation.overall_status),
        )
        db_session.add(experiment)
        db_session.flush()
        for name, (value, data_type) in row.get("parameters", {}).items():
            db_session.add(ExperimentParameter(
                experiment_id=experiment.id,
                name=name,
                value=value,
                data_type=data_type,
            ))
        for name, value in metrics.items():
            db_session.add(ExperimentMetric(
                experiment_id=experiment.id,
                name=name,
                value=value,
            ))

    db_session.commit()
    return batch.id


def _get_autopsy(client: TestClient, db_session, rows: list[dict]) -> dict:
    batch_id = _create_controlled_batch(db_session, rows)
    response = client.get(f"/research/autopsy/{batch_id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_autopsy_returns_computed_summary_and_findings(client: TestClient):
    imported = _import_report(client, rows=12, include_win_rate=True)
    response = client.get(f"/research/autopsy/{imported['import_batch_id']}")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_experiments"] == 12
    assert sum(data["status_counts"].values()) == 12
    assert "profit_factor" in data["metric_summary"]
    assert isinstance(data["findings"], list)
    assert data["analysis_notes"]


def test_autopsy_evidence_ids_belong_to_imported_batch(client: TestClient):
    imported = _import_report(client, rows=12, include_win_rate=True)
    data = client.get(f"/research/autopsy/{imported['import_batch_id']}").json()
    valid_ids = {
        item["id"] for item in client.get("/experiments", params={"page_size": 100}).json()["items"]
    }

    for finding in data["findings"]:
        assert set(finding["evidence_experiment_ids"]).issubset(valid_ids)
        assert finding["evidence_count"] >= len(finding["evidence_experiment_ids"])


def test_autopsy_surfaces_missing_win_rate(client: TestClient):
    imported = _import_report(client, rows=8, include_win_rate=False)
    data = client.get(f"/research/autopsy/{imported['import_batch_id']}").json()

    assert "win_rate" not in data["metric_summary"]
    assert any(
        finding["kind"] == "data_gap" and finding["metric"] == "win_rate"
        for finding in data["findings"]
    )


def test_autopsy_unknown_batch_returns_404(client: TestClient):
    response = client.get("/research/autopsy/99999")
    assert response.status_code == 404


def test_parameter_analysis_groups_numeric_values_and_summarizes_metrics(client, db_session):
    values = [1, 1, 1, 2, 3, 4, 5, 6]
    rows = []
    for index, value in enumerate(values):
        metrics = {
            "profit_factor": float(index + 1),
            "equity_drawdown_pct": float(index * 2),
            "win_rate": float(50 + index),
        }
        if index == 2:
            metrics["win_rate"] = None
        if index == 7:
            metrics["profit_factor"] = float("inf")
        rows.append({
            "parameters": {"GridStep": (str(value), DataType.integer)},
            "metrics": metrics,
        })

    data = _get_autopsy(client, db_session, rows)
    analysis = data["parameter_analysis"]
    parameter = analysis["parameters"][0]

    assert analysis["minimum_group_support"] == 3
    assert "up to five" in analysis["grouping_method"]
    assert len(parameter["groups"]) <= 5
    assert parameter["experiment_count"] == 8
    assert parameter["usable_value_count"] == 8
    assert parameter["missing_parameter_count"] == 0
    assert sum(group["experiment_count"] for group in parameter["groups"]) == 8
    first_group = next(group for group in parameter["groups"] if group["minimum"] == 1)
    assert first_group["maximum"] == 1
    assert first_group["experiment_count"] == 3
    assert first_group["low_support"] is False
    assert first_group["outcomes"]["profit_factor"] == {
        "usable_count": 3,
        "missing_count": 0,
        "min": 1.0,
        "median": 2.0,
        "max": 3.0,
        "status": "available",
    }
    assert first_group["outcomes"]["win_rate"]["usable_count"] == 2
    assert first_group["outcomes"]["win_rate"]["missing_count"] == 1
    assert all(
        group["low_support"] is (group["experiment_count"] < 3)
        for group in parameter["groups"]
    )
    final_group = next(group for group in parameter["groups"] if group["maximum"] == 6)
    assert final_group["outcomes"]["profit_factor"]["usable_count"] == 1
    assert final_group["outcomes"]["profit_factor"]["missing_count"] == 1
    assert final_group["outcomes"]["profit_factor"]["status"] == "available"

    returned_ids = {
        item["id"] for item in client.get("/experiments", params={"page_size": 100}).json()["items"]
    }
    grouped_ids = [
        experiment_id
        for group in parameter["groups"]
        for experiment_id in group["evidence_experiment_ids"]
    ]
    assert len(grouped_ids) == parameter["usable_value_count"]
    assert len(set(grouped_ids)) == parameter["usable_value_count"]
    assert set(grouped_ids).issubset(returned_ids)
    for group in parameter["groups"]:
        assert len(group["evidence_experiment_ids"]) == group["experiment_count"]
        assert set(group["evidence_experiment_ids"]).issubset(returned_ids)
        for metric in group["outcomes"].values():
            assert metric["usable_count"] + metric["missing_count"] == group["experiment_count"]


def test_parameter_analysis_handles_negative_decimal_few_and_single_value_groups(client, db_session):
    values = ["-2.5", "-1.25", "0.25", "1.5", "1.5"]
    rows = [
        {
            "parameters": {
                "DecimalParam": (value, DataType.float),
                "ConstantParam": ("9.5", DataType.float),
            },
            "metrics": {"profit_factor": float(index + 1)},
        }
        for index, value in enumerate(values)
    ]
    data = _get_autopsy(client, db_session, rows)
    by_name = {item["name"]: item for item in data["parameter_analysis"]["parameters"]}

    decimal_groups = by_name["DecimalParam"]["groups"]
    assert len(decimal_groups) == 4
    assert [(group["minimum"], group["maximum"]) for group in decimal_groups] == [
        (-2.5, -2.5),
        (-1.25, -1.25),
        (0.25, 0.25),
        (1.5, 1.5),
    ]
    repeated_group = decimal_groups[-1]
    assert repeated_group["experiment_count"] == 2
    assert len(repeated_group["evidence_experiment_ids"]) == 2

    constant_group = by_name["ConstantParam"]["groups"]
    assert len(constant_group) == 1
    assert constant_group[0]["minimum"] == constant_group[0]["maximum"] == 9.5
    assert constant_group[0]["experiment_count"] == 5
    assert len(constant_group[0]["evidence_experiment_ids"]) == 5


def test_integer_parameters_above_float_exactness_remain_distinct(client, db_session):
    lower = 9007199254740992
    upper = 9007199254740993
    rows = [
        {"parameters": {"LargeInteger": (str(value), DataType.integer)}}
        for value in (lower, upper)
    ]
    data = _get_autopsy(client, db_session, rows)
    groups = data["parameter_analysis"]["parameters"][0]["groups"]

    assert [(group["minimum"], group["maximum"]) for group in groups] == [
        (lower, lower),
        (upper, upper),
    ]
    assert all(group["experiment_count"] == 1 for group in groups)
    assert len({experiment_id for group in groups for experiment_id in group["evidence_experiment_ids"]}) == 2


def test_parameter_analysis_groups_exact_categories_and_booleans(client, db_session):
    rows = [
        {"parameters": {"Mode": (" mean ", DataType.string), "Enabled": ("true", DataType.boolean)}},
        {"parameters": {"Mode": ("mean", DataType.string), "Enabled": ("true", DataType.boolean)}},
        {"parameters": {"Mode": ("trend", DataType.string), "Enabled": ("false", DataType.boolean)}},
        {"parameters": {"Mode": ("trend", DataType.string), "Enabled": ("false", DataType.boolean)}},
    ]

    data = _get_autopsy(client, db_session, rows)
    by_name = {item["name"]: item for item in data["parameter_analysis"]["parameters"]}

    mode_groups = {group["value"]: group for group in by_name["Mode"]["groups"]}
    assert set(mode_groups) == {"mean", "trend"}
    assert mode_groups["mean"]["experiment_count"] == 2
    assert mode_groups["mean"]["low_support"] is True
    boolean_groups = {group["value"]: group for group in by_name["Enabled"]["groups"]}
    assert set(boolean_groups) == {"true", "false"}
    assert all(group["kind"] == "boolean" for group in boolean_groups.values())


def test_parameter_analysis_reports_missing_malformed_nonfinite_and_unsupported(client, db_session):
    rows = [
        {"parameters": {"Numeric": ("1", DataType.float), "Flag": ("true", DataType.boolean)}},
        {"parameters": {"Numeric": ("bad", DataType.float), "Flag": ("sometimes", DataType.boolean)}},
        {"parameters": {"Numeric": ("NaN", DataType.float)}},
        {"parameters": {"Numeric": ("Infinity", DataType.float)}},
        {"parameters": {"Numeric": ("-Infinity", DataType.float)}},
        {"parameters": {"Flag": ("false", DataType.boolean)}},
        {"parameters": {}},
    ]
    data = _get_autopsy(client, db_session, rows)
    by_name = {item["name"]: item for item in data["parameter_analysis"]["parameters"]}

    numeric = by_name["Numeric"]
    assert numeric["experiment_count"] == 7
    assert numeric["usable_value_count"] == 1
    assert numeric["missing_parameter_count"] == 2
    assert numeric["unusable_values"]["malformed"]["count"] == 1
    assert numeric["unusable_values"]["non_finite"]["count"] == 3
    assert numeric["unusable_values"]["missing"]["count"] == 2
    assert numeric["unusable_value_count"] == 6
    assert sum(group["experiment_count"] for group in numeric["groups"]) == 1
    for entry in numeric["unusable_values"].values():
        assert len(entry["evidence_experiment_ids"]) == entry["count"]
    numeric_evidence_ids = [
        experiment_id
        for group in numeric["groups"]
        for experiment_id in group["evidence_experiment_ids"]
    ] + [
        experiment_id
        for entry in numeric["unusable_values"].values()
        for experiment_id in entry["evidence_experiment_ids"]
    ]
    assert len(numeric_evidence_ids) == numeric["experiment_count"]
    assert len(set(numeric_evidence_ids)) == numeric["experiment_count"]

    flag = by_name["Flag"]
    assert flag["unusable_values"]["malformed"]["count"] == 1
    assert flag["missing_parameter_count"] == 4
    assert flag["unusable_values"]["missing"]["count"] == 4
    assert flag["groups"][0]["value"] == "false"
    assert flag["groups"][0]["experiment_count"] == 1

    kind, value, reason = _parameter_value(
        SimpleNamespace(value="9007199254740993", data_type=DataType.integer)
    )
    assert (kind, value, reason) == ("numeric", 9007199254740993, None)
    kind, value, reason = _parameter_value(
        SimpleNamespace(value="some-value", data_type="unknown")
    )
    assert (kind, value, reason) == (None, None, "unsupported")


def test_parameter_analysis_marks_all_invalid_outcome_summaries_unavailable():
    experiments = [
        SimpleNamespace(
            id=experiment_id,
            parameters=[SimpleNamespace(name="Mode", value="fixed", data_type=DataType.string)],
        )
        for experiment_id in (10, 11, 12)
    ]
    metrics = {
        10: {"profit_factor": float("inf"), "equity_drawdown_pct": float("nan"), "win_rate": None},
        11: {"profit_factor": float("-inf"), "equity_drawdown_pct": float("nan"), "win_rate": None},
        12: {"profit_factor": None, "equity_drawdown_pct": None, "win_rate": None},
    }

    analysis = _build_parameter_analysis(experiments, metrics)
    group = analysis["parameters"][0]["groups"][0]

    assert group["experiment_count"] == 3
    assert group["evidence_experiment_ids"] == [10, 11, 12]
    for summary in group["outcomes"].values():
        assert summary["usable_count"] == 0
        assert summary["missing_count"] == 3
        assert summary["min"] is None
        assert summary["median"] is None
        assert summary["max"] is None
        assert summary["status"] == "unavailable"


def test_parameter_analysis_is_deterministic_and_does_not_change_qualification(client, db_session):
    rows = [
        {
            "parameters": {"Risk": (str(index % 2), DataType.integer)},
            "metrics": {
                "profit_factor": 2.0 if index else 1.0,
                "equity_drawdown_pct": 10.0,
                "win_rate": None if index == 1 else 70.0,
            },
        }
        for index in range(4)
    ]
    batch_id = _create_controlled_batch(db_session, rows)
    first = client.get(f"/research/autopsy/{batch_id}").json()
    second = client.get(f"/research/autopsy/{batch_id}").json()

    assert first["parameter_analysis"] == second["parameter_analysis"]
    assert first["status_counts"] == {
        "qualified": 2,
        "rejected": 1,
        "incomplete": 1,
        "pending": 0,
    }
    assert "parameter_analysis" in first
    assert "findings" in first and "metric_summary" in first
    assert "not causal" in first["parameter_analysis"]["interpretation"]
