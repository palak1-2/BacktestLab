"""Parse and validate an MT5 win-rate companion CSV for an XML batch."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.ingestion.base import NormalizedExperimentBatch, NormalizedMetric
from app.services.ingestion.normalizer import normalize_metric_header

REQUIRED_HEADERS = (
    "pass",
    "profitable_trades",
    "total_trades",
    "win_rate_pct",
    "frame_status",
    "parameter_values",
)
_INTEGER = re.compile(r"^[0-9]+$")
_WIN_RATE_TOLERANCE = Decimal("0.000000005")
_MAX_PASS_ID = 2**63 - 1
_MAX_MQL_COUNT = 2**31 - 1


@dataclass(frozen=True)
class WinRateRecord:
    pass_id: int
    profitable_trades: int
    total_trades: int
    win_rate_pct: Decimal
    parameters: dict[str, str]


def _finite_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Companion CSV contains an invalid {field}.") from None
    if not result.is_finite():
        raise ValueError(f"Companion CSV contains a non-finite {field}.")
    return result


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Companion CSV parameter_values contains duplicate names.")
        result[key] = value
    return result


def _parse_parameters(raw: str) -> dict[str, str]:
    try:
        values = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("Companion CSV contains malformed parameter_values JSON.") from None
    if not isinstance(values, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in values.items()
    ):
        raise ValueError("Companion CSV parameter_values must be an object of string values.")
    return values


def parse_winrate_csv(content: bytes) -> dict[int, WinRateRecord]:
    """Validate CSV encoding, shape, pass identifiers, counts, rates, and JSON values."""
    try:
        text = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("Companion CSV must be valid UTF-8.") from None

    try:
        rows = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(rows, None)
        if headers is None:
            raise ValueError("Companion CSV is empty.")
        headers = [header.strip() for header in headers]
        normalized_headers = [header.casefold() for header in headers]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("Companion CSV contains duplicate headers.")
        missing = [header for header in REQUIRED_HEADERS if header not in headers]
        if missing:
            raise ValueError(
                "Companion CSV is missing required headers: " + ", ".join(missing) + "."
            )

        positions = {header: headers.index(header) for header in REQUIRED_HEADERS}
        records: dict[int, WinRateRecord] = {}
        for row_number, row in enumerate(rows, start=2):
            if not row:
                continue
            if len(row) != len(headers):
                raise ValueError(f"Companion CSV row {row_number} has an invalid number of fields.")

            raw_pass = row[positions["pass"]].strip()
            if not _INTEGER.fullmatch(raw_pass):
                raise ValueError(f"Companion CSV row {row_number} has an invalid pass ID.")
            pass_id = int(raw_pass)
            if pass_id > _MAX_PASS_ID:
                raise ValueError(f"Companion CSV row {row_number} has an out-of-range pass ID.")
            if pass_id in records:
                raise ValueError(f"Companion CSV contains duplicate pass ID {pass_id}.")

            if row[positions["frame_status"]].strip() != "valid":
                raise ValueError(f"Companion CSV pass {pass_id} is not marked valid.")

            raw_wins = row[positions["profitable_trades"]].strip()
            raw_total = row[positions["total_trades"]].strip()
            if not _INTEGER.fullmatch(raw_wins) or not _INTEGER.fullmatch(raw_total):
                raise ValueError(f"Companion CSV pass {pass_id} has invalid trade counts.")
            wins, total = int(raw_wins), int(raw_total)
            if wins > _MAX_MQL_COUNT or total > _MAX_MQL_COUNT:
                raise ValueError(f"Companion CSV pass {pass_id} has out-of-range trade counts.")
            if total == 0:
                raise ValueError(f"Companion CSV pass {pass_id} has zero total trades.")
            if wins > total:
                raise ValueError(f"Companion CSV pass {pass_id} has inconsistent trade counts.")

            supplied_rate = _finite_decimal(
                row[positions["win_rate_pct"]], f"win rate for pass {pass_id}"
            )
            if supplied_rate < 0 or supplied_rate > 100:
                raise ValueError(f"Companion CSV pass {pass_id} has an out-of-range Win Rate.")
            calculated_rate = Decimal(100 * wins) / Decimal(total)
            if abs(supplied_rate - calculated_rate) > _WIN_RATE_TOLERANCE:
                raise ValueError(f"Companion CSV pass {pass_id} has an inconsistent Win Rate.")

            parameters = _parse_parameters(row[positions["parameter_values"]])
            records[pass_id] = WinRateRecord(
                pass_id=pass_id,
                profitable_trades=wins,
                total_trades=total,
                win_rate_pct=supplied_rate,
                parameters=parameters,
            )
    except csv.Error:
        raise ValueError("Companion CSV is malformed.") from None

    if not records:
        raise ValueError("Companion CSV contains no pass records.")
    return records


def _parameter_matches(xml_value: str, data_type: str, csv_value: str) -> bool:
    if data_type in {"integer", "float"}:
        try:
            xml_number = Decimal(xml_value.strip())
            csv_number = Decimal(csv_value.strip())
        except (InvalidOperation, ValueError):
            return False
        return (
            xml_number.is_finite()
            and csv_number.is_finite()
            and xml_number == csv_number
        )
    if data_type == "boolean":
        return xml_value == csv_value and xml_value in {"true", "false"}
    if data_type == "string":
        return xml_value == csv_value
    return False


def enrich_xml_batch_with_winrate(
    batch: NormalizedExperimentBatch,
    csv_content: bytes,
) -> None:
    """Validate exact XML/CSV pairing, then append independently sourced Win Rates."""
    if batch.metadata.source_format != "xml":
        raise ValueError("A Win Rate companion CSV can only be paired with an XML report.")

    records = parse_winrate_csv(csv_content)
    experiments_by_pass: dict[int, Any] = {}
    for experiment in batch.experiments:
        pass_id = experiment.optimization_pass
        if (
            isinstance(pass_id, bool)
            or not isinstance(pass_id, int)
            or pass_id < 0
            or pass_id > _MAX_PASS_ID
        ):
            raise ValueError("XML report contains a missing or invalid optimization pass ID.")
        if pass_id in experiments_by_pass:
            raise ValueError(f"XML report contains duplicate pass ID {pass_id}.")
        experiments_by_pass[pass_id] = experiment

    xml_passes = set(experiments_by_pass)
    csv_passes = set(records)
    if xml_passes != csv_passes:
        missing = sorted(xml_passes - csv_passes)
        extra = sorted(csv_passes - xml_passes)
        if missing:
            raise ValueError(f"Companion CSV is missing XML pass IDs: {missing}.")
        raise ValueError(f"Companion CSV has pass IDs not present in XML: {extra}.")

    staged_metrics: list[tuple[Any, NormalizedMetric | None]] = []
    for pass_id, experiment in experiments_by_pass.items():
        canonical_metrics: dict[str, list[NormalizedMetric]] = {}
        for metric in experiment.metrics:
            canonical, _ = normalize_metric_header(metric.name)
            canonical_metrics.setdefault(canonical, []).append(metric)
        duplicates = [name for name, values in canonical_metrics.items() if len(values) > 1]
        if duplicates:
            raise ValueError(
                f"XML pass {pass_id} contains ambiguous duplicate metrics: {', '.join(sorted(duplicates))}."
            )

        source_win_rates = canonical_metrics.get("win_rate", [])
        record = records[pass_id]
        staged_metric: NormalizedMetric | None = None
        if source_win_rates:
            existing = source_win_rates[0]
            try:
                source_rate = _finite_decimal(existing.value, f"XML Win Rate for pass {pass_id}")
            except ValueError:
                raise ValueError(f"XML pass {pass_id} contains an invalid pre-existing Win Rate.") from None
            calculated_rate = (
                Decimal(100 * record.profitable_trades) / Decimal(record.total_trades)
            )
            if existing.unit != "%" or abs(source_rate - calculated_rate) > _WIN_RATE_TOLERANCE:
                raise ValueError(f"XML pass {pass_id} has a conflicting pre-existing Win Rate.")
        else:
            staged_metric = NormalizedMetric(
                name="win_rate",
                value=float(Decimal(100 * record.profitable_trades) / Decimal(record.total_trades)),
                unit="%",
            )

        trades_metrics = canonical_metrics.get("trades", [])
        if len(trades_metrics) != 1 or trades_metrics[0].value is None:
            raise ValueError(f"XML pass {pass_id} is missing a usable Trades metric.")
        try:
            xml_trades = _finite_decimal(trades_metrics[0].value, f"XML Trades metric for pass {pass_id}")
        except ValueError:
            raise ValueError(f"XML pass {pass_id} contains an invalid Trades metric.") from None
        if xml_trades != Decimal(record.total_trades):
            raise ValueError(f"XML pass {pass_id} Trades metric does not match the companion CSV.")

        xml_parameters = {parameter.name: parameter for parameter in experiment.parameters}
        for name, parameter in xml_parameters.items():
            if name not in record.parameters:
                raise ValueError(
                    f"Companion CSV pass {pass_id} is missing XML parameter '{name}'."
                )
            if not _parameter_matches(
                parameter.value, parameter.data_type, record.parameters[name]
            ):
                raise ValueError(
                    f"XML pass {pass_id} parameter '{name}' conflicts with the companion CSV."
                )
        staged_metrics.append((experiment, staged_metric))

    for experiment, metric in staged_metrics:
        if metric is not None:
            experiment.metrics.append(metric)


def paired_import_hash(xml_hash: str, csv_hash: str) -> str:
    """Return a domain-separated identity incorporating both source file hashes."""
    import hashlib

    digest = hashlib.sha256(b"BacktestLab\x00paired-xml-winrate-csv\x00v1\x00")
    digest.update(bytes.fromhex(xml_hash))
    digest.update(bytes.fromhex(csv_hash))
    return digest.hexdigest()


def pairing_provenance(xml_hash: str, csv_hash: str) -> str:
    """Return safe provenance without filenames, account IDs, or parameter values."""
    return (
        "Paired XML/Win Rate CSV enrichment v1; "
        f"XML SHA-256={xml_hash}; companion CSV SHA-256={csv_hash}."
    )
