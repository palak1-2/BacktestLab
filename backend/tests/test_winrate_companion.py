"""API tests for optional MT5 Win Rate companion CSV pairing."""

import csv
import io
import json
from decimal import Decimal

import pytest

from app.models.experiment import Experiment, ExperimentMetric, ImportBatch
from app.services.experiments.service import compute_file_hash
from app.services.ingestion.winrate_csv import paired_import_hash


def _xml_bytes(
    passes: list[int | str | None] = [0, 1, 2, 3, 4],
    include_win_rate: bool = False,
    duplicate_win_rate_alias: bool = False,
    win_rates: dict[int, float] | None = None,
) -> bytes:
    namespace = 'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"'
    headers = [
        "Pass", "InpLot", "UseFilter", "Label", "Profit Factor",
        "Equity DD %", "Trades",
    ]
    if include_win_rate:
        headers.append("Win Rate")
    if duplicate_win_rate_alias:
        headers.append("win_rate")

    def row(values: list[object]) -> str:
        cells = "".join(
            f'<ss:Cell><ss:Data ss:Type="String">{"" if value is None else value}</ss:Data></ss:Cell>'
            for value in values
        )
        return f"<ss:Row>{cells}</ss:Row>"

    rows = []
    for pass_id in passes:
        values: list[object] = [
            pass_id,
            f"{0.1 + (int(pass_id or 0) / 100):.2f}" if str(pass_id).lstrip("-").isdigit() else "0.1",
            "true",
            "steady",
            "2.0",
            "10.0",
            "100",
        ]
        if include_win_rate:
            values.append(str((win_rates or {}).get(int(pass_id), 25.0)))
        if duplicate_win_rate_alias:
            values.append("25.0")
        rows.append(row(values))

    return (
        f'<ss:Workbook {namespace}><ss:Worksheet ss:Name="Optimization Results">'
        f'<ss:Table>{row(headers)}{"".join(rows)}</ss:Table>'
        "</ss:Worksheet></ss:Workbook>"
    ).encode("utf-8")


def _csv_text(
    pass_ids: list[int] | None = None,
    wins: dict[int, int] | None = None,
    rows_override: list[list[str]] | None = None,
    headers: list[str] | None = None,
) -> bytes:
    headers = headers or [
        "pass", "profitable_trades", "total_trades", "win_rate_pct",
        "frame_status", "parameter_values",
    ]
    pass_ids = pass_ids if pass_ids is not None else [0, 1, 2, 3, 4]
    wins = wins or {0: 65, 1: 60, 2: 70, 3: 80, 4: 50}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    if rows_override is not None:
        writer.writerows(rows_override)
    else:
        for pass_id in pass_ids:
            p = {
                "InpLot": f"{0.1 + pass_id / 100:.2f}",
                "UseFilter": "true",
                "Label": "steady",
                "InpMagicNumber": "123456",
            }
            win = wins.get(pass_id, 50)
            writer.writerow([
                pass_id,
                win,
                100,
                f"{win:.8f}",
                "valid",
                json.dumps(p, separators=(",", ":")),
            ])
    return output.getvalue().encode("utf-8")


def _post_pair(
    client,
    xml: bytes | None = None,
    csv_content: bytes | None = None,
    xml_name: str = "synthetic.xml",
    csv_name: str = "companion.csv",
):
    return client.post(
        "/experiments/import",
        files={
            "file": (xml_name, io.BytesIO(xml or _xml_bytes()), "application/xml"),
            "winrate_csv": (
                csv_name,
                io.BytesIO(csv_content or _csv_text()),
                "text/csv",
            ),
        },
    )


class TestWinRateCompanionImport:
    def test_five_pass_pair_enriches_and_evaluates_all_records(self, client, db_session):
        response = _post_pair(client)

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["imported"] is True
        assert payload["experiments_created"] == 5
        assert payload["qualified"] == 3
        assert payload["rejected"] == 2
        assert payload["insufficient_data"] == 0
        assert len(payload["source_hash"]) == 64
        assert not any("Win Rate metric not found" in warning for warning in payload["warnings"])
        assert any("Paired XML/Win Rate CSV enrichment v1" in warning for warning in payload["warnings"])

        experiments = (
            db_session.query(Experiment)
            .order_by(Experiment.optimization_pass)
            .all()
        )
        rates = {
            experiment.optimization_pass: next(
                metric.value for metric in experiment.metrics if metric.name == "win_rate"
            )
            for experiment in experiments
        }
        assert rates == {0: 65.0, 1: 60.0, 2: 70.0, 3: 80.0, 4: 50.0}
        assert "Paired XML/Win Rate CSV enrichment v1" in db_session.query(ImportBatch).one().warnings
        assert "companion CSV SHA-256=" in db_session.query(ImportBatch).one().warnings
        autopsy_response = client.get(
            f"/research/autopsy/{payload['import_batch_id']}"
        )
        assert autopsy_response.status_code == 200, autopsy_response.text

        autopsy = autopsy_response.json()
        assert autopsy["status_counts"]["qualified"] == 3
        assert autopsy["status_counts"]["rejected"] == 2
        assert autopsy["status_counts"]["incomplete"] == 0

    def test_order_independent_and_allows_additional_csv_parameters(self, client):
        rows = list(csv.reader(io.StringIO(_csv_text().decode())))
        reversed_csv = io.StringIO(newline="")
        writer = csv.writer(reversed_csv)
        writer.writerow(rows[0])
        writer.writerows(reversed(rows[1:]))
        response = _post_pair(
            client,
            xml=_xml_bytes(passes=[4, 3, 2, 1, 0]),
            csv_content=reversed_csv.getvalue().encode(),
        )

        assert response.status_code == 200
        assert response.json()["experiments_created"] == 5

    def test_identical_pair_deduplicates_and_standalone_hash_is_distinct(self, client, db_session):
        xml = _xml_bytes()
        csv_content = _csv_text()
        standalone = client.post(
            "/experiments/import",
            files={"file": ("standalone.xml", io.BytesIO(xml), "application/xml")},
        )
        paired = _post_pair(client, xml, csv_content)
        repeat = _post_pair(client, xml, csv_content)

        assert standalone.status_code == 200
        assert paired.status_code == 200
        assert repeat.status_code == 200
        assert paired.json()["source_hash"] == paired_import_hash(
            compute_file_hash(xml), compute_file_hash(csv_content)
        )
        assert paired.json()["source_hash"] != standalone.json()["source_hash"]
        assert repeat.json()["duplicate"] is True
        assert db_session.query(ImportBatch).count() == 2

    def test_filenames_do_not_change_paired_identity(self, client):
        first = _post_pair(client, xml_name="run-a.xml", csv_name="run-a.csv")
        second = _post_pair(client, xml_name="renamed.xml", csv_name="renamed.csv")

        assert first.status_code == second.status_code == 200
        assert second.json()["duplicate"] is True
        assert first.json()["source_hash"] == second.json()["source_hash"]

    def test_numeric_parameter_comparison_is_semantic(self, client):
        rows = list(csv.reader(io.StringIO(_csv_text().decode())))
        for row in rows[1:]:
            parameters = json.loads(row[5])
            parameters["InpLot"] = f"{Decimal(parameters['InpLot']):.3f}"
            row[5] = json.dumps(parameters, separators=(",", ":"))
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerows(rows)

        response = _post_pair(client, csv_content=output.getvalue().encode())

        assert response.status_code == 200, response.text

    def test_companion_rejected_for_xlsx(self, client, db_session):
        from tests.conftest import make_xlsx_bytes

        response = client.post(
            "/experiments/import",
            files={
                "file": ("synthetic.xlsx", io.BytesIO(make_xlsx_bytes()), "application/vnd.ms-excel"),
                "winrate_csv": ("pair.csv", io.BytesIO(_csv_text()), "text/csv"),
            },
        )

        assert response.status_code == 422
        assert db_session.query(ImportBatch).count() == 0

    def test_atomic_failure_creates_no_records(self, client, db_session):
        response = _post_pair(client, csv_content=_csv_text(pass_ids=[0, 1, 2, 3]))

        assert response.status_code == 422
        assert "missing XML pass IDs" in response.json()["detail"]
        assert db_session.query(ImportBatch).count() == 0
        assert db_session.query(Experiment).count() == 0
        assert db_session.query(ExperimentMetric).count() == 0

    @pytest.mark.parametrize(
        ("csv_content", "message"),
        [
            (_csv_text(pass_ids=[0, 1, 2, 3, 4, 99]), "not present in XML"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "65.00000000", "valid", '{"InpLot":"0.10","UseFilter":"true","Label":"steady"}'],
                ["0", "65", "100", "65.00000000", "valid", '{"InpLot":"0.10","UseFilter":"true","Label":"steady"}'],
            ]), "duplicate pass ID"),
            (_csv_text(rows_override=[
                ["x", "65", "100", "65", "valid", "{}"],
            ]), "invalid pass ID"),
            (_csv_text(rows_override=[
                ["", "65", "100", "65", "valid", "{}"],
            ]), "invalid pass ID"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "65", "pending", "{}"],
            ]), "not marked valid"),
            (_csv_text(rows_override=[
                ["0", "-1", "100", "65", "valid", "{}"],
            ]), "invalid trade counts"),
            (_csv_text(rows_override=[
                ["0", "65", "0", "0", "valid", "{}"],
            ]), "zero total trades"),
            (_csv_text(rows_override=[
                ["0", "101", "100", "101", "valid", "{}"],
            ]), "inconsistent trade counts"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "NaN", "valid", "{}"],
            ]), "non-finite"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "Infinity", "valid", "{}"],
            ]), "non-finite"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "100.1", "valid", "{}"],
            ]), "out-of-range"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "-1", "valid", "{}"],
            ]), "out-of-range"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "64.9", "valid", "{}"],
            ]), "inconsistent Win Rate"),
            (_csv_text(rows_override=[
                ["0", "65.0", "100", "65", "valid", "{}"],
            ]), "invalid trade counts"),
            (_csv_text(rows_override=[
                ["0", "NaN", "100", "65", "valid", "{}"],
            ]), "invalid trade counts"),
            (_csv_text(rows_override=[
                ["0", "65", "Infinity", "65", "valid", "{}"],
            ]), "invalid trade counts"),
            (_csv_text(rows_override=[
                ["0", "65", "100", "65", "valid", '{"InpLot":null}'],
            ]), "object of string values"),
            (b'pass,profitable_trades,total_trades,win_rate_pct,frame_status,parameter_values\n0,65,100,65,valid,"{"bad":true}\n', "malformed"),
            (b"pass,profitable_trades,total_trades,win_rate_pct,frame_status\n", "missing required headers"),
            (b"\xff\xfe", "UTF-8"),
            (b"pass,pass,profitable_trades,total_trades,win_rate_pct,frame_status,parameter_values\n", "duplicate headers"),
            (b"pass,Pass,profitable_trades,total_trades,win_rate_pct,frame_status,parameter_values\n", "duplicate headers"),
            (b"pass,profitable_trades,total_trades,win_rate_pct,frame_status,parameter_values\n0,65,100,65,valid,{", "malformed parameter_values JSON"),
        ],
    )
    def test_invalid_companion_rejected_atomically(self, client, db_session, csv_content, message):
        response = _post_pair(client, csv_content=csv_content)

        assert response.status_code == 422, response.text
        assert message.lower() in response.json()["detail"].lower()
        assert db_session.query(ImportBatch).count() == 0
        assert db_session.query(Experiment).count() == 0

    @pytest.mark.parametrize(
        ("xml", "csv_content", "message"),
        [
            (_xml_bytes([None, 1, 2, 3, 4]), _csv_text(), "missing or invalid"),
            (_xml_bytes([-1, 1, 2, 3, 4]), _csv_text(), "missing or invalid"),
            (_xml_bytes([0, 0, 2, 3, 4]), _csv_text(), "duplicate pass ID"),
            (_xml_bytes(["0.5", 1, 2, 3, 4]), _csv_text(), "missing or invalid"),
            (_xml_bytes(), _csv_text(rows_override=[
                    ["0", "65", "101", "64.35643564", "valid", '{"InpLot":"0.10","UseFilter":"true","Label":"steady"}'],
                ["1", "60", "100", "60", "valid", '{"InpLot":"0.11","UseFilter":"true","Label":"steady"}'],
                ["2", "70", "100", "70", "valid", '{"InpLot":"0.12","UseFilter":"true","Label":"steady"}'],
                ["3", "80", "100", "80", "valid", '{"InpLot":"0.13","UseFilter":"true","Label":"steady"}'],
                ["4", "50", "100", "50", "valid", '{"InpLot":"0.14","UseFilter":"true","Label":"steady"}'],
            ]), "Trades metric does not match"),
            (_xml_bytes(), _csv_text(rows_override=[
                ["0", "65", "100", "65", "valid", '{"UseFilter":"true","Label":"steady"}'],
                ["1", "60", "100", "60", "valid", '{"InpLot":"0.11","UseFilter":"true","Label":"steady"}'],
                ["2", "70", "100", "70", "valid", '{"InpLot":"0.12","UseFilter":"true","Label":"steady"}'],
                ["3", "80", "100", "80", "valid", '{"InpLot":"0.13","UseFilter":"true","Label":"steady"}'],
                ["4", "50", "100", "50", "valid", '{"InpLot":"0.14","UseFilter":"true","Label":"steady"}'],
            ]), "missing XML parameter"),
            (_xml_bytes(), _csv_text(rows_override=[
                ["0", "65", "100", "65", "valid", '{"InpLot":"0.99","UseFilter":"true","Label":"steady"}'],
                ["1", "60", "100", "60", "valid", '{"InpLot":"0.11","UseFilter":"true","Label":"steady"}'],
                ["2", "70", "100", "70", "valid", '{"InpLot":"0.12","UseFilter":"true","Label":"steady"}'],
                ["3", "80", "100", "80", "valid", '{"InpLot":"0.13","UseFilter":"true","Label":"steady"}'],
                ["4", "50", "100", "50", "valid", '{"InpLot":"0.14","UseFilter":"true","Label":"steady"}'],
            ]), "parameter 'InpLot' conflicts"),
        ],
    )
    def test_xml_pass_and_pairing_mismatches_rejected_atomically(
        self, client, db_session, xml, csv_content, message
    ):
        response = _post_pair(client, xml, csv_content)

        assert response.status_code == 422, response.text
        assert message.lower() in response.json()["detail"].lower()
        assert db_session.query(ImportBatch).count() == 0
        assert db_session.query(Experiment).count() == 0

    def test_conflicting_preexisting_win_rate_rejected_without_persistence(self, client, db_session):
        response = _post_pair(client, xml=_xml_bytes(include_win_rate=True))

        assert response.status_code == 422
        assert "conflicting pre-existing Win Rate" in response.json()["detail"]
        assert db_session.query(ImportBatch).count() == 0
        assert db_session.query(Experiment).count() == 0

    def test_matching_preexisting_win_rate_is_preserved_without_duplicate_metric(
        self, client, db_session
    ):
        response = _post_pair(
            client,
            xml=_xml_bytes(
                include_win_rate=True,
                win_rates={0: 65.0, 1: 60.0, 2: 70.0, 3: 80.0, 4: 50.0},
            ),
        )

        assert response.status_code == 200, response.text
        for experiment in db_session.query(Experiment).all():
            rates = [
                metric for metric in experiment.metrics if metric.name == "win_rate"
            ]
            assert len(rates) == 1

    def test_ambiguous_canonical_metric_rejected_without_persistence(self, client, db_session):
        response = _post_pair(
            client,
            xml=_xml_bytes(include_win_rate=True, duplicate_win_rate_alias=True),
        )

        assert response.status_code == 422
        assert "Multiple metric columns normalize" in response.json()["detail"]
        assert db_session.query(ImportBatch).count() == 0

    def test_xml_fractional_pass_is_not_silently_truncated(self, client, db_session):
        xml = _xml_bytes(["0.5", 1, 2, 3, 4])
        response = _post_pair(client, xml, _csv_text())

        assert response.status_code == 422
        assert db_session.query(ImportBatch).count() == 0
