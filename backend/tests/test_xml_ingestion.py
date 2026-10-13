"""
Tests for XML SpreadsheetML ingestion.

Verifies:
- Valid MT5 XML loads
- Metadata is extracted from DocumentProperties and header rows
- Optimization rows are parsed correctly
- Parameters and metrics are dynamically detected
"""

import pytest

from tests.conftest import make_xml_bytes
from app.services.ingestion.xml_parser import parse_xml


class TestXmlBasicLoad:
    def test_returns_normalized_batch(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "ReportOptimizer-12345.xml")
        assert batch is not None
        assert batch.metadata.source_format == "xml"

    def test_source_file_preserved(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "my_report.xml")
        assert batch.metadata.source_file == "my_report.xml"

    def test_experiment_count_matches_rows(self):
        content = make_xml_bytes(num_rows=8)
        batch = parse_xml(content, "test.xml")
        assert len(batch.experiments) == 8

    def test_optimization_pass_sequential(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        passes = [e.optimization_pass for e in batch.experiments]
        assert passes == list(range(5))


class TestXmlMetadataExtraction:
    def test_symbol_extracted(self):
        content = make_xml_bytes(num_rows=3)
        batch = parse_xml(content, "test.xml")
        assert batch.metadata.symbol == "EURUSD"

    def test_timeframe_normalized(self):
        content = make_xml_bytes(num_rows=3)
        batch = parse_xml(content, "test.xml")
        assert batch.metadata.timeframe == "H1"

    def test_server_extracted(self):
        content = make_xml_bytes(num_rows=3)
        batch = parse_xml(content, "test.xml")
        assert batch.metadata.server == "Demo-Server"

    def test_deposit_extracted(self):
        content = make_xml_bytes(num_rows=3)
        batch = parse_xml(content, "test.xml")
        assert batch.metadata.deposit == 10000.0

    def test_strategy_name_from_doc_properties(self):
        content = make_xml_bytes(num_rows=3)
        batch = parse_xml(content, "test.xml")
        # strategy_name comes from DocumentProperties Title or Expert row
        assert batch.metadata.strategy_name is not None

    def test_leverage_extracted(self):
        content = make_xml_bytes(num_rows=3)
        batch = parse_xml(content, "test.xml")
        assert batch.metadata.leverage is not None
        assert "100" in str(batch.metadata.leverage)


class TestXmlOptimizationRows:
    def test_parameters_detected(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            assert len(exp.parameters) > 0

    def test_metrics_detected(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            assert len(exp.metrics) > 0

    def test_profit_factor_present(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            metric_names = {m.name for m in exp.metrics}
            assert "profit_factor" in metric_names

    def test_drawdown_present(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            metric_names = {m.name for m in exp.metrics}
            assert "equity_drawdown_pct" in metric_names

    def test_win_rate_absent_warning(self):
        content = make_xml_bytes(num_rows=5, include_win_rate=False)
        batch = parse_xml(content, "test.xml")
        warning_text = " ".join(batch.warnings).lower()
        assert "win rate" in warning_text

    def test_win_rate_present_when_included(self):
        content = make_xml_bytes(num_rows=5, include_win_rate=True)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            metric_names = {m.name for m in exp.metrics}
            assert "win_rate" in metric_names

    def test_metric_values_are_float_or_none(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            for m in exp.metrics:
                assert m.value is None or isinstance(m.value, float)

    def test_param_data_types_inferred(self):
        content = make_xml_bytes(num_rows=5)
        batch = parse_xml(content, "test.xml")
        for exp in batch.experiments:
            for p in exp.parameters:
                assert p.data_type in ("integer", "float", "boolean", "string")


class TestXmlErrorHandling:
    def test_empty_bytes_raises(self):
        with pytest.raises((ValueError, Exception)):
            parse_xml(b"", "empty.xml")

    def test_invalid_xml_raises(self):
        with pytest.raises((ValueError, Exception)):
            parse_xml(b"NOT XML AT ALL <<<>>>", "bad.xml")

    def test_xml_without_workbook_raises(self):
        xml = b"<?xml version='1.0'?><root><nothing/></root>"
        with pytest.raises(ValueError, match="Worksheet"):
            parse_xml(xml, "no_worksheet.xml")
