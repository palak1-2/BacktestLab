"""
MT5 XML SpreadsheetML optimization report parser.

Handles XML exports from MetaTrader 5 Strategy Tester, typically named
ReportOptimizer-<digits>.xml.

The XML format is Microsoft Office SpreadsheetML (Office 2003 XML).
Structure:
  <Workbook>
    <DocumentProperties> ... title, author, created ... </DocumentProperties>
    <Worksheet ss:Name="...">
      <Table>
        <Row>  <Cell> <Data> </Row>
        ...
      </Table>
    </Worksheet>
  </Workbook>

The parser:
  1. Parses the XML with lxml or stdlib ElementTree (lxml preferred)
  2. Extracts DocumentProperties metadata
  3. Finds the optimization result worksheet
  4. Reads all rows into a list-of-lists
  5. Detects the header row (row containing "Pass" or known metric names)
  6. Applies the same parameter/metric split logic as the XLSX parser
  7. Returns a NormalizedExperimentBatch

The rest of the application does NOT know whether the source was XML.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from lxml import etree as ET
    USING_LXML = True
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore
    USING_LXML = False

from app.services.ingestion.base import (
    NormalizedBatchMetadata,
    NormalizedExperiment,
    NormalizedExperimentBatch,
    NormalizedMetric,
    NormalizedParameter,
)
from app.services.ingestion.normalizer import normalize_timeframe
from app.services.ingestion.normalizer import (
    normalize_metric_header,
    validate_unique_metric_headers,
)
from app.services.metrics import finite_metric_value

# SpreadsheetML namespaces
_NS = {
    "ss": "urn:schemas-microsoft-com:office:spreadsheet",
    "o":  "urn:schemas-microsoft-com:office:office",
    "x":  "urn:schemas-microsoft-com:office:excel",
    "html": "http://www.w3.org/TR/REC-html40",
}

# Re-use the same constants as the XLSX parser
KNOWN_METRIC_NAMES: Set[str] = {
    "result", "profit", "expected payoff", "profit factor",
    "recovery factor", "sharpe ratio", "custom", "equity dd %",
    "equity dd", "drawdown %", "drawdown", "trades", "win rate",
    "win rate %", "profit per trade", "loss per trade",
    "biggest win", "biggest loss", "pass",
}

PASS_COLUMN_VARIANTS: Set[str] = {"pass", "#", "no.", "no", "id"}

_META_KEY_MAP: Dict[str, str] = {
    "symbol": "symbol",
    "period": "timeframe",
    "timeframe": "timeframe",
    "server": "server",
    "deposit": "deposit",
    "leverage": "leverage",
    "build": "mt5_build",
    "mt5 build": "mt5_build",
    "expert": "strategy_name",
    "ea": "strategy_name",
    "from": "test_start",
    "to": "test_end",
    "date from": "test_start",
    "date to": "test_end",
}


def _ncl(name: Any) -> str:
    """Normalize column name to lowercase stripped string."""
    return str(name).strip().lower()


def _safe_float(v: Any) -> Optional[float]:
    return finite_metric_value(v)[0]


def _safe_int(v: Any) -> Optional[int]:
    f = _safe_float(v)
    if f is None:
        return None
    return int(f)


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _infer_data_type(value: str) -> Tuple[str, str]:
    lower = value.strip().lower()
    if lower in ("true", "false"):
        return lower, "boolean"
    try:
        int_v = int(value)
        return str(int_v), "integer"
    except ValueError:
        pass
    try:
        float(value)
        return value, "float"
    except ValueError:
        pass
    return value, "string"


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------


def _ns(tag: str, prefix: str = "ss") -> str:
    """Return fully-qualified tag name for namespace prefix."""
    return f"{{{_NS[prefix]}}}{tag}"


def _find_all(element: Any, tag: str, prefix: str = "ss") -> List[Any]:
    return element.findall(f".//{_ns(tag, prefix)}")


def _find_one(element: Any, tag: str, prefix: str = "ss") -> Optional[Any]:
    return element.find(f".//{_ns(tag, prefix)}")


def _get_cell_value(cell: Any) -> str:
    """Extract the text value from a SpreadsheetML Cell element."""
    data = _find_one(cell, "Data")
    if data is not None and data.text:
        return data.text.strip()
    return ""


def _parse_rows(table: Any) -> List[List[str]]:
    """
    Parse all Row/Cell elements from a Table element.
    Handles ss:Index gaps (sparse cells).
    """
    rows: List[List[str]] = []
    for row_el in _find_all(table, "Row"):
        cells_in_row: List[str] = []
        col_idx = 0
        for cell_el in row_el.findall(_ns("Cell")):
            # Handle ss:Index attribute (1-based)
            idx_attr = cell_el.get(_ns("Index"))
            if idx_attr:
                target = int(idx_attr) - 1  # 0-based
                while len(cells_in_row) < target:
                    cells_in_row.append("")
                col_idx = target

            val = _get_cell_value(cell_el)

            # Handle ss:MergeAcross
            merge_across = cell_el.get(_ns("MergeAcross"))
            merge_count = int(merge_across) if merge_across else 0

            cells_in_row.append(val)
            col_idx += 1

            for _ in range(merge_count):
                cells_in_row.append("")
                col_idx += 1

        rows.append(cells_in_row)
    return rows


def _extract_doc_properties(root: Any) -> Dict[str, Any]:
    """Extract DocumentProperties metadata."""
    meta: Dict[str, Any] = {}
    dp = _find_one(root, "DocumentProperties", prefix="o")
    if dp is None:
        return meta

    field_map = {
        "Title": "title",
        "Author": "author",
        "Created": "created",
        "Description": "description",
    }
    for xml_field, py_field in field_map.items():
        el = dp.find(_ns(xml_field, prefix="o"))
        if el is not None and el.text:
            meta[py_field] = el.text.strip()
    return meta


def _extract_metadata_from_rows(rows: List[List[str]]) -> Tuple[Dict[str, Any], int]:
    """
    Find metadata key-value pairs in pre-header rows.
    Returns (metadata_dict, header_row_index).
    """
    metadata: Dict[str, Any] = {}
    header_row_idx = 0

    for i, row in enumerate(rows):
        non_empty = [v for v in row if v.strip()]
        if not non_empty:
            continue

        # Check if this looks like the column-header row
        normalized = [_ncl(v) for v in non_empty]
        if any(v in PASS_COLUMN_VARIANTS or v in KNOWN_METRIC_NAMES for v in normalized):
            header_row_idx = i
            break

        # Try key: value extraction
        first = non_empty[0]
        if ":" in first:
            key, _, val = first.partition(":")
            key = key.strip().lower()
            val = val.strip()
            meta_field = _META_KEY_MAP.get(key)
            if meta_field:
                metadata[meta_field] = val
        elif len(non_empty) >= 2:
            key = _ncl(non_empty[0])
            meta_field = _META_KEY_MAP.get(key)
            if meta_field:
                metadata[meta_field] = non_empty[1]

    return metadata, header_row_idx


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_xml(
    content: bytes,
    filename: str,
) -> NormalizedExperimentBatch:
    """
    Parse an MT5 SpreadsheetML XML optimization report.

    Args:
        content: Raw file bytes.
        filename: Original filename.

    Returns:
        NormalizedExperimentBatch

    Raises:
        ValueError: On invalid / unrecognized XML structure.
    """
    warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Parse XML
    # ------------------------------------------------------------------
    try:
        if USING_LXML:
            root = ET.fromstring(content)
        else:
            root = ET.fromstring(content.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise ValueError(f"Cannot parse XML: {exc}") from exc

    # ------------------------------------------------------------------
    # 2. Extract DocumentProperties
    # ------------------------------------------------------------------
    doc_props = _extract_doc_properties(root)
    title = doc_props.get("title", "")

    # ------------------------------------------------------------------
    # 3. Find the optimization worksheet
    #    Prefer worksheet with "optimization" or "result" in name.
    # ------------------------------------------------------------------
    worksheets = root.findall(f".//{_ns('Worksheet')}")
    if not worksheets:
        raise ValueError("No Worksheet elements found in XML.")

    target_ws = None
    for ws in worksheets:
        name_attr = ws.get(_ns("Name")) or ""
        if "optim" in name_attr.lower() or "result" in name_attr.lower():
            target_ws = ws
            break
    if target_ws is None:
        target_ws = worksheets[0]

    ws_name = target_ws.get(_ns("Name"), "Sheet1")

    # ------------------------------------------------------------------
    # 4. Parse all rows from the Table
    # ------------------------------------------------------------------
    table = _find_one(target_ws, "Table")
    if table is None:
        raise ValueError(f"No Table element found in worksheet '{ws_name}'.")

    rows = _parse_rows(table)

    if not rows:
        raise ValueError("No rows found in the optimization table.")

    # ------------------------------------------------------------------
    # 5. Extract metadata from pre-header rows
    # ------------------------------------------------------------------
    raw_metadata, header_row_idx = _extract_metadata_from_rows(rows)

    # Supplement with DocumentProperties
    if title and not raw_metadata.get("strategy_name"):
        # Try to extract EA name from title like "ReportOptimizer MyEA EURUSD H1"
        raw_metadata.setdefault("strategy_name", title)

    # ------------------------------------------------------------------
    # 6. Identify header row and data rows
    # ------------------------------------------------------------------
    if header_row_idx >= len(rows):
        raise ValueError("Could not find header row in XML worksheet.")

    header_cols = rows[header_row_idx]
    data_rows = rows[header_row_idx + 1:]

    if not header_cols or all(h == "" for h in header_cols):
        raise ValueError("Header row is empty.")

    # Pad header to reasonable length
    max_cols = max((len(r) for r in data_rows), default=len(header_cols))
    while len(header_cols) < max_cols:
        header_cols.append(f"col_{len(header_cols)}")

    col_lower = [_ncl(c) for c in header_cols]

    # ------------------------------------------------------------------
    # 7. Identify pass column
    # ------------------------------------------------------------------
    pass_col_idx: Optional[int] = None
    for i, cl in enumerate(col_lower):
        if cl in PASS_COLUMN_VARIANTS:
            pass_col_idx = i
            break

    if pass_col_idx is None:
        warnings.append("No 'Pass' column found; optimization_pass will be set to row index.")

    # ------------------------------------------------------------------
    # 8. Split columns into parameters / metrics
    # ------------------------------------------------------------------
    first_metric_idx: Optional[int] = None
    for i, cl in enumerate(col_lower):
        if cl in KNOWN_METRIC_NAMES and cl not in PASS_COLUMN_VARIANTS:
            first_metric_idx = i
            break

    if first_metric_idx is None:
        warnings.append("Could not auto-detect metric columns; using position heuristic.")
        first_metric_idx = max(1, len(header_cols) // 2)

    param_col_indices: List[int] = []
    metric_col_indices: List[int] = []

    for i in range(len(header_cols)):
        if i == pass_col_idx:
            continue
        if i < first_metric_idx:
            param_col_indices.append(i)
        else:
            metric_col_indices.append(i)

    param_cols = [header_cols[i] for i in param_col_indices]
    metric_cols = [header_cols[i] for i in metric_col_indices]
    validate_unique_metric_headers(metric_cols)

    found_metric_lower = {_ncl(c) for c in metric_cols}
    if "win rate" not in found_metric_lower and "win rate %" not in found_metric_lower:
        warnings.append("Win Rate metric not found — win_rate rules will produce INSUFFICIENT_DATA")
    if found_metric_lower & {"equity dd", "drawdown"}:
        warnings.append(
            "Ambiguous drawdown values were preserved without a unit and are not used "
            "for percentage qualification."
        )

    # ------------------------------------------------------------------
    # 9. Build batch metadata
    # ------------------------------------------------------------------
    raw_tf = raw_metadata.get("timeframe") or raw_metadata.get("period")
    raw_tf_str, norm_tf = normalize_timeframe(raw_tf) if raw_tf else (None, None)

    deposit_val = _safe_float(raw_metadata.get("deposit"))
    test_start = _parse_date(str(raw_metadata.get("test_start", "") or ""))
    test_end = _parse_date(str(raw_metadata.get("test_end", "") or ""))

    batch_meta = NormalizedBatchMetadata(
        strategy_name=raw_metadata.get("strategy_name"),
        symbol=raw_metadata.get("symbol"),
        timeframe=norm_tf,
        raw_timeframe=raw_tf_str,
        test_start=test_start,
        test_end=test_end,
        server=raw_metadata.get("server"),
        deposit=deposit_val,
        leverage=str(raw_metadata.get("leverage")) if raw_metadata.get("leverage") else None,
        mt5_build=str(raw_metadata.get("mt5_build")) if raw_metadata.get("mt5_build") else None,
        source_file=filename,
        source_format="xml",
    )

    # ------------------------------------------------------------------
    # 10. Parse data rows
    # ------------------------------------------------------------------
    experiments: List[NormalizedExperiment] = []
    non_finite_metric_seen = False

    for row_num, row in enumerate(data_rows):
        # Pad short rows
        while len(row) < len(header_cols):
            row.append("")

        # Skip completely empty rows
        if all(v == "" for v in row):
            continue

        # Optimization pass
        opt_pass: Optional[int] = None
        if pass_col_idx is not None and pass_col_idx < len(row):
            opt_pass = _safe_int(row[pass_col_idx])

        # Parameters
        params: List[NormalizedParameter] = []
        for col_i, col_name in zip(param_col_indices, param_cols):
            if col_i >= len(row):
                continue
            raw_val = row[col_i]
            if raw_val == "":
                continue
            val_str, dtype = _infer_data_type(raw_val)
            params.append(NormalizedParameter(
                name=str(col_name).strip(),
                value=val_str,
                data_type=dtype,
            ))

        # Metrics
        metrics: List[NormalizedMetric] = []
        for col_i, col_name in zip(metric_col_indices, metric_cols):
            if col_i >= len(row):
                continue
            raw_val = row[col_i]
            float_val, non_finite = finite_metric_value(raw_val)
            non_finite_metric_seen = non_finite_metric_seen or non_finite
            canonical, unit = normalize_metric_header(col_name)
            metrics.append(NormalizedMetric(
                name=canonical,
                value=float_val,
                unit=unit,
            ))

        experiments.append(NormalizedExperiment(
            optimization_pass=opt_pass,
            parameters=params,
            metrics=metrics,
        ))

    if not experiments:
        raise ValueError("No experiments could be extracted from the XML file.")
    if non_finite_metric_seen:
        warnings.append("Non-finite metric values were treated as missing.")

    return NormalizedExperimentBatch(
        metadata=batch_meta,
        experiments=experiments,
        warnings=warnings,
    )
