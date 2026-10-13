"""
Tests for XLSX ingestion.

Verifies:
- Valid MT5 XLSX loads successfully
- Parameters are dynamically detected (not hard-coded)
- Metrics are dynamically detected
- Thousands of rows can be processed
- Missing columns produce appropriate warnings
"""

import pytest

from tests.conftest import make_xlsx_bytes
from app.services.ingestion.xlsx_parser import parse_xlsx


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
