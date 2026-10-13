"""
Tests for XLSX ingestion.

Verifies:
- Valid MT5 XLSX loads successfully
- Parameters are dynamically detected (not hard-coded)
- Metrics are dynamically detected
- Thousands of rows can be processed
- Missing columns produce appropriate warnings
"""

import io

import openpyxl
import pytest

from tests.conftest import make_xlsx_bytes
from app.services.ingestion.xlsx_parser import parse_xlsx
from app.models.experiment import ExperimentMetric
from app.services.experiments.service import save_batch


def _xlsx_with_metrics(headers: list[str], values: list[object]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Optimization Results"
    sheet.append(["Pass", *headers])
    sheet.append([1, *values])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class TestXlsxBasicLoad:
    def test_returns_normalized_batch(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        assert batch is not None
        assert batch.metadata.source_format == "xlsx"

    def test_source_file_preserved(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "my_report.xlsx")
        assert batch.metadata.source_file == "my_report.xlsx"

    def test_experiment_count_matches_rows(self):
        content = make_xlsx_bytes(num_rows=10)
        batch = parse_xlsx(content, "test.xlsx")
        assert len(batch.experiments) == 10

    def test_metadata_symbol_extracted(self):
        content = make_xlsx_bytes(num_rows=3)
        batch = parse_xlsx(content, "test.xlsx")
        assert batch.metadata.symbol == "EURUSD"

    def test_metadata_timeframe_normalized(self):
        content = make_xlsx_bytes(num_rows=3)
        batch = parse_xlsx(content, "test.xlsx")
        assert batch.metadata.timeframe == "H1"

    def test_metadata_strategy_name(self):
        content = make_xlsx_bytes(num_rows=3)
        batch = parse_xlsx(content, "test.xlsx")
        # strategy_name comes from "Expert: TestEA.ex5"
        assert batch.metadata.strategy_name is not None
        assert "TestEA" in batch.metadata.strategy_name

    def test_optimization_pass_sequential(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        passes = [e.optimization_pass for e in batch.experiments]
        assert passes == list(range(5))


class TestXlsxDynamicParameters:
    def test_custom_param_names_detected(self):
        """Parameters must be dynamic — not tied to a fixed list."""
        custom_params = ["MyCustomParam1", "AnotherEAInput", "GridSize_Custom"]
        content = make_xlsx_bytes(num_rows=3, param_names=custom_params)
        batch = parse_xlsx(content, "test.xlsx")

        found_param_names = {p.name for e in batch.experiments for p in e.parameters}
        for cp in custom_params:
            assert cp in found_param_names, f"Expected param '{cp}' not found"

    def test_param_data_types_inferred(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        for exp in batch.experiments:
            for param in exp.parameters:
                assert param.data_type in ("integer", "float", "boolean", "string")
                assert param.value is not None

    def test_standard_params_detected(self):
        standard_params = ["InpMaxSteps", "InpTakeProfitDist", "InpLotStep"]
        content = make_xlsx_bytes(num_rows=5, param_names=standard_params)
        batch = parse_xlsx(content, "test.xlsx")
        found = {p.name for e in batch.experiments for p in e.parameters}
        for sp in standard_params:
            assert sp in found


class TestXlsxDynamicMetrics:
    def test_profit_factor_detected(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        for exp in batch.experiments:
            metric_names = {m.name for m in exp.metrics}
            assert "profit_factor" in metric_names

    def test_equity_drawdown_detected(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        for exp in batch.experiments:
            metric_names = {m.name for m in exp.metrics}
            assert "equity_drawdown_pct" in metric_names

    def test_drawdown_unit_is_percent(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        for exp in batch.experiments:
            for m in exp.metrics:
                if m.name == "equity_drawdown_pct":
                    assert m.unit == "%"

    def test_win_rate_absent_triggers_warning(self):
        content = make_xlsx_bytes(num_rows=5, include_win_rate=False)
        batch = parse_xlsx(content, "test.xlsx")
        warning_text = " ".join(batch.warnings).lower()
        assert "win rate" in warning_text

    def test_win_rate_present_when_included(self):
        content = make_xlsx_bytes(num_rows=5, include_win_rate=True)
        batch = parse_xlsx(content, "test.xlsx")
        for exp in batch.experiments:
            metric_names = {m.name for m in exp.metrics}
            assert "win_rate" in metric_names

    def test_metric_values_are_float_or_none(self):
        content = make_xlsx_bytes(num_rows=5)
        batch = parse_xlsx(content, "test.xlsx")
        for exp in batch.experiments:
            for m in exp.metrics:
                assert m.value is None or isinstance(m.value, float)

    @pytest.mark.parametrize(
        ("header", "expected_name", "expected_unit"),
        [
            ("Equity DD %", "equity_drawdown_pct", "%"),
            ("Drawdown %", "equity_drawdown_pct", "%"),
        ],
    )
    def test_explicit_percentage_drawdown_headers_are_normalized(
        self, header, expected_name, expected_unit
    ):
        batch = parse_xlsx(_xlsx_with_metrics([header], [12.5]), "synthetic.xlsx")
        metric = batch.experiments[0].metrics[0]

        assert (metric.name, metric.value, metric.unit) == (expected_name, 12.5, expected_unit)

    @pytest.mark.parametrize(
        ("header", "expected_name"),
        [("Equity DD", "equity_dd"), ("Drawdown", "drawdown")],
    )
    def test_ambiguous_drawdown_headers_do_not_populate_percentage_metric(
        self, header, expected_name
    ):
        batch = parse_xlsx(_xlsx_with_metrics([header], [125.0]), "synthetic.xlsx")
        metrics = {metric.name: metric for metric in batch.experiments[0].metrics}

        assert expected_name in metrics
        assert metrics[expected_name].unit == ""
        assert metrics[expected_name].value == 125.0
        assert "equity_drawdown_pct" not in metrics
        assert any("Ambiguous drawdown" in warning for warning in batch.warnings)

    def test_equity_dd_and_percentage_columns_persist_as_distinct_metrics(self, db_session):
        batch = parse_xlsx(
            _xlsx_with_metrics(["Equity DD", "Equity DD %"], [125.0, 12.5]),
            "synthetic.xlsx",
        )

        import_batch, _ = save_batch(db_session, batch, "d" * 64)
        stored = db_session.query(ExperimentMetric).all()

        assert {metric.name for metric in stored} == {"equity_dd", "equity_drawdown_pct"}
        assert import_batch.experiments_created == 1

    @pytest.mark.parametrize("invalid_value", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_required_metrics_become_missing_with_warning(self, db_session, invalid_value):
        batch = parse_xlsx(
            _xlsx_with_metrics(
                ["Profit Factor", "Equity DD %", "Win Rate"],
                [invalid_value, invalid_value, invalid_value],
            ),
            "synthetic.xlsx",
        )
        import_batch, statuses = save_batch(db_session, batch, "e" * 64)

        assert [metric.value for metric in batch.experiments[0].metrics] == [None, None, None]
        assert statuses["INSUFFICIENT_DATA"] == 1
        assert "Non-finite metric values were treated as missing." in batch.warnings
        assert import_batch.warnings == '["Non-finite metric values were treated as missing."]'
        assert all(metric.value is None for metric in db_session.query(ExperimentMetric).all())

    @pytest.mark.parametrize(
        "headers",
        [
            ["Equity DD %", "Drawdown %"],
            ["Profit Factor", "profit_factor"],
        ],
    )
    def test_duplicate_canonical_metric_columns_raise_clear_parse_error(self, headers):
        with pytest.raises(ValueError, match="Multiple metric columns normalize"):
            parse_xlsx(_xlsx_with_metrics(headers, [1.0, 2.0]), "synthetic.xlsx")

    def test_safe_float_rejects_non_finite_values(self):
        from app.services.ingestion.xlsx_parser import _safe_float

        for invalid in ("NaN", "Infinity", "-Infinity"):
            assert _safe_float(invalid) is None


class TestXlsxLargeLoad:
    def test_thousands_of_rows_processed(self):
        """Parser must handle 2000+ rows (representative of real MT5 exports)."""
        content = make_xlsx_bytes(num_rows=2000)
        batch = parse_xlsx(content, "large_test.xlsx")
        assert len(batch.experiments) == 2000

    def test_very_many_params_supported(self):
        """16-parameter EA must be supported."""
        many_params = [
            "InpMaxSteps", "InpTakeProfitDist", "InpSlowdownMode",
            "InpOneTradePerBar", "Cycle1_Lot", "Cycle1_Step",
            "InpInitialLot", "InpLotStep", "InpGridStepPips",
            "InpGlobalTarget", "InpRisk", "InpMagic",
            "InpComment", "InpSlippage", "InpSpread", "InpMaxOrders",
        ]
        content = make_xlsx_bytes(num_rows=100, param_names=many_params)
        batch = parse_xlsx(content, "test.xlsx")
        found = {p.name for e in batch.experiments for p in e.parameters}
        for p in many_params:
            assert p in found


class TestXlsxErrorHandling:
    def test_empty_bytes_raises(self):
        with pytest.raises(ValueError):
            parse_xlsx(b"", "empty.xlsx")

    def test_non_xlsx_bytes_raises(self):
        with pytest.raises(ValueError):
            parse_xlsx(b"NOT AN XLSX FILE", "bad.xlsx")
