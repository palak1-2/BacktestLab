"""
Tests for XML SpreadsheetML ingestion.

Verifies:
- Valid MT5 XML loads
- Metadata is extracted from DocumentProperties and header rows
- Optimization rows are parsed correctly
- Parameters and metrics are dynamically detected
"""

import json
from xml.sax.saxutils import escape

import pytest

from tests.conftest import make_xml_bytes
from app.services.ingestion.xml_parser import parse_xml
from app.models.experiment import ExperimentMetric
from app.services.experiments.service import save_batch


def _xml_with_metrics(headers: list[str], values: list[str]) -> bytes:
    return _xml_table(["Pass", *headers], ["1", *values])


def _xml_table(
    headers: list[str],
    values: list[object],
    document_properties: dict[str, str] | None = None,
    worksheet_metadata: list[tuple[str, str]] | None = None,
) -> bytes:
    namespace = 'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"'
    office_namespace = 'xmlns:o="urn:schemas-microsoft-com:office:office"'

    def row(items: list[object]) -> str:
        cells = "".join(
            f'<ss:Cell><ss:Data ss:Type="String">{item}</ss:Data></ss:Cell>'
            for item in items
        )
        return f"<ss:Row>{cells}</ss:Row>"

    properties = ""
    if document_properties is not None:
        properties = "<o:DocumentProperties>" + "".join(
            f"<o:{name}>{escape(value)}</o:{name}>"
            for name, value in document_properties.items()
        ) + "</o:DocumentProperties>"

    metadata_rows = "".join(row([key, value]) for key, value in (worksheet_metadata or []))
    xml = (
        f'<ss:Workbook {namespace} {office_namespace}>'
        f'{properties}<ss:Worksheet ss:Name="Results"><ss:Table>'
        f'{metadata_rows}{row(headers)}{row(values)}'
        "</ss:Table></ss:Worksheet></ss:Workbook>"
    )
    return xml.encode("utf-8")


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
    def test_namespaced_document_properties_merge_into_batch_metadata(self):
        batch = parse_xml(
            _xml_table(
                ["Pass", "InitialLot", "Profit Factor"],
                ["1", "0.25", "1.8"],
                document_properties={
                    "Title": "ReportOptimizer TestEA",
                    "Server": "Broker-Server",
                    "Deposit": "10000 USD",
                    "Leverage": "1:100",
                    "Build": "4150",
                },
            ),
            "synthetic.xml",
        )

        assert batch.metadata.strategy_name == "ReportOptimizer TestEA"
        assert batch.metadata.server == "Broker-Server"
        assert batch.metadata.deposit == 10000.0
        assert batch.metadata.leverage == "1:100"
        assert batch.metadata.mt5_build == "4150"
        assert [(p.name, p.value) for p in batch.experiments[0].parameters] == [
            ("InitialLot", "0.25")
        ]
        assert [(m.name, m.value) for m in batch.experiments[0].metrics] == [
            ("profit_factor", 1.8)
        ]

    def test_worksheet_metadata_takes_precedence_over_document_properties(self):
        batch = parse_xml(
            _xml_table(
                ["Pass", "Profit Factor"],
                ["1", "1.8"],
                document_properties={
                    "Server": "Properties-Server",
                    "Deposit": "10000 USD",
                    "Leverage": "1:100",
                    "Build": "4150",
                },
                worksheet_metadata=[
                    ("Server", "Worksheet-Server"),
                    ("Deposit", "25000 EUR"),
                    ("Leverage", "1:200"),
                    ("Build", "4200"),
                ],
            ),
            "synthetic.xml",
        )

        assert batch.metadata.server == "Worksheet-Server"
        assert batch.metadata.deposit == 25000.0
        assert batch.metadata.leverage == "1:200"
        assert batch.metadata.mt5_build == "4200"

    def test_missing_optional_document_properties_remain_missing(self):
        batch = parse_xml(
            _xml_table(["Pass", "Profit Factor"], ["1", "1.8"]),
            "synthetic.xml",
        )

        assert batch.metadata.server is None
        assert batch.metadata.deposit is None
        assert batch.metadata.leverage is None
        assert batch.metadata.mt5_build is None
        assert len(batch.experiments) == 1

    @pytest.mark.parametrize("invalid_deposit", ["not an amount", "NaN", "Infinity", "10000 USD extra"])
    def test_invalid_document_property_deposit_is_ignored(self, invalid_deposit):
        batch = parse_xml(
            _xml_table(
                ["Pass", "InitialLot", "Profit Factor"],
                ["1", "0.25", "1.8"],
                document_properties={
                    "Server": "Broker-Server",
                    "Deposit": invalid_deposit,
                    "Leverage": "1:100",
                    "Build": "4150",
                },
            ),
            "synthetic.xml",
        )

        assert batch.metadata.deposit is None
        assert "Invalid deposit metadata was ignored." in batch.warnings
        assert batch.metadata.server == "Broker-Server"
        assert batch.metadata.leverage == "1:100"
        assert batch.metadata.mt5_build == "4150"
        assert [parameter.name for parameter in batch.experiments[0].parameters] == ["InitialLot"]
        assert [(metric.name, metric.value) for metric in batch.experiments[0].metrics] == [
            ("profit_factor", 1.8)
        ]

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
    def test_interleaved_columns_preserve_parameter_values_and_types(self):
        batch = parse_xml(
            _xml_table(
                ["Pass", "InitialLot", "Profit Factor", "EnableFeature",
                 "Cycle1_Lot", "Win Rate", "TargetTF"],
                ["7", "0.25", "1.8", "true", "2.5", "65.0", "H1"],
            ),
            "synthetic.xml",
        )
        experiment = batch.experiments[0]
        parameters = {parameter.name: parameter for parameter in experiment.parameters}

        assert experiment.optimization_pass == 7
        assert {metric.name for metric in experiment.metrics} == {"profit_factor", "win_rate"}
        assert {name: (item.value, item.data_type) for name, item in parameters.items()} == {
            "InitialLot": ("0.25", "float"),
            "EnableFeature": ("true", "boolean"),
            "Cycle1_Lot": ("2.5", "float"),
            "TargetTF": ("H1", "string"),
        }

    def test_metrics_first_layout_keeps_following_parameters(self):
        batch = parse_xml(
            _xml_table(
                ["Profit Factor", "Pass", "InpInitialLot", "Equity DD %"],
                ["1.8", "3", "0.1", "12.5"],
            ),
            "synthetic.xml",
        )
        experiment = batch.experiments[0]

        assert experiment.optimization_pass == 3
        assert [(parameter.name, parameter.value) for parameter in experiment.parameters] == [
            ("InpInitialLot", "0.1")
        ]
        assert {metric.name for metric in experiment.metrics} == {
            "profit_factor",
            "equity_drawdown_pct",
        }

    def test_no_known_metric_headers_are_preserved_as_parameters(self):
        batch = parse_xml(
            _xml_table(["Pass", "InitialLot", "TargetTF"], ["2", "0.2", "M15"]),
            "synthetic.xml",
        )
        experiment = batch.experiments[0]

        assert experiment.metrics == []
        assert [parameter.name for parameter in experiment.parameters] == ["InitialLot", "TargetTF"]
        assert any("No recognized metric columns" in warning for warning in batch.warnings)

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

    def test_missing_win_rate_remains_missing_and_qualification_insufficient(self, db_session):
        batch = parse_xml(
            _xml_table(
                ["Pass", "Profit Factor", "Equity DD %"],
                ["1", "2.0", "10.0"],
            ),
            "synthetic.xml",
        )
        _, statuses = save_batch(db_session, batch, "c" * 64)

        assert "win_rate" not in {metric.name for metric in batch.experiments[0].metrics}
        assert statuses["INSUFFICIENT_DATA"] == 1

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
        batch = parse_xml(_xml_with_metrics([header], ["12.5"]), "synthetic.xml")
        metric = batch.experiments[0].metrics[0]

        assert (metric.name, metric.value, metric.unit) == (expected_name, 12.5, expected_unit)

    @pytest.mark.parametrize(
        ("header", "expected_name"),
        [("Equity DD", "equity_dd"), ("Drawdown", "drawdown")],
    )
    def test_ambiguous_drawdown_headers_do_not_populate_percentage_metric(
        self, header, expected_name
    ):
        batch = parse_xml(_xml_with_metrics([header], ["125.0"]), "synthetic.xml")
        metrics = {metric.name: metric for metric in batch.experiments[0].metrics}

        assert expected_name in metrics
        assert metrics[expected_name].unit == ""
        assert metrics[expected_name].value == 125.0
        assert "equity_drawdown_pct" not in metrics
        assert any("Ambiguous drawdown" in warning for warning in batch.warnings)

    def test_equity_dd_and_percentage_columns_persist_as_distinct_metrics(self, db_session):
        batch = parse_xml(
            _xml_with_metrics(["Equity DD", "Equity DD %"], ["125.0", "12.5"]),
            "synthetic.xml",
        )

        import_batch, _ = save_batch(db_session, batch, "f" * 64)
        stored = db_session.query(ExperimentMetric).all()

        assert {metric.name for metric in stored} == {"equity_dd", "equity_drawdown_pct"}
        assert import_batch.experiments_created == 1

    @pytest.mark.parametrize("invalid_value", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_required_metrics_become_missing_with_warning(self, db_session, invalid_value):
        batch = parse_xml(
            _xml_with_metrics(
                ["Profit Factor", "Equity DD %", "Win Rate"],
                [invalid_value, invalid_value, invalid_value],
            ),
            "synthetic.xml",
        )
        import_batch, statuses = save_batch(db_session, batch, "a" * 64)

        assert [metric.value for metric in batch.experiments[0].metrics] == [None, None, None]
        assert statuses["INSUFFICIENT_DATA"] == 1
        assert "Non-finite metric values were treated as missing." in batch.warnings
        assert json.loads(import_batch.warnings) == batch.warnings
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
            parse_xml(_xml_with_metrics(headers, ["1.0", "2.0"]), "synthetic.xml")

    def test_safe_float_rejects_non_finite_values(self):
        from app.services.ingestion.xml_parser import _safe_float

        for invalid in ("NaN", "Infinity", "-Infinity"):
            assert _safe_float(invalid) is None


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
