"""
MT5 XLSX optimization report parser.

Handles Excel exports from MetaTrader 5 Strategy Tester optimization runs.

MT5 XLSX structure (typical):
- One workbook, one or more sheets
- A header section (rows 1-N) with metadata key-value pairs
- A data table with a header row followed by optimization pass rows
- Explicitly recognized metric headers are metrics wherever they appear
- Unknown/extra columns are preserved as parameters, never discarded

The parser does NOT assume a fixed set of parameter names.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.services.ingestion.base import (
    NormalizedBatchMetadata,
    NormalizedExperiment,
    NormalizedExperimentBatch,
    NormalizedMetric,
    NormalizedParameter,
)
from app.services.ingestion.normalizer import (
    KNOWN_METRIC_HEADERS as KNOWN_METRIC_NAMES,
    PASS_COLUMN_VARIANTS,
    classify_columns,
    normalize_metric_header,
    normalize_timeframe,
)
from app.services.metrics import finite_metric_value

def _normalize_col_name(name: Any) -> str:
    """Lowercase strip for comparison."""
    return str(name).strip().lower()


def _infer_data_type(value: Any) -> Tuple[str, str]:
    """
    Return (value_as_str, data_type) for a parameter value.
    """
    if isinstance(value, bool):
        return str(value).lower(), "boolean"
    if isinstance(value, int):
        return str(value), "integer"
    if isinstance(value, float):
        # Check if it's effectively an integer
        if value == int(value):
            return str(int(value)), "integer"
        return str(value), "float"
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "false", "yes", "no"):
            return lower.replace("yes", "true").replace("no", "false"), "boolean"
        try:
            int(value)
            return value, "integer"
        except ValueError:
            pass
        try:
            float(value)
            return value, "float"
        except ValueError:
            pass
    return str(value), "string"


def _safe_float(value: Any) -> Optional[float]:
    """Convert to a finite float, treating invalid and non-finite values as missing."""
    return finite_metric_value(value)[0]


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

_META_KEY_MAP = {
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
    "expert advisor": "strategy_name",
    "from": "test_start",
    "to": "test_end",
    "date from": "test_start",
    "date to": "test_end",
}


def _extract_metadata_from_header_rows(
    df_raw: pd.DataFrame,
) -> Tuple[Dict[str, Any], int]:
    """
    Scan the first rows of the dataframe for key-value metadata pairs.
    Returns (metadata_dict, first_data_row_index).

    MT5 exports often have:
      Row 0: "Expert: MyEA.ex5"    (or two-column key/value)
      Row 1: "Symbol: EURUSD"
      ...
      Row N: actual header row with column names like "Pass", "InpParam1", "Profit", ...
    """
    metadata: Dict[str, Any] = {}
    header_row_idx = 0

    for i, row in df_raw.iterrows():
        values = [v for v in row.values if pd.notna(v) and str(v).strip()]
        if not values:
            continue

        # Detect if this looks like a data-header row:
        # it would have known metric/param column names or "Pass"
        normalized_values = [_normalize_col_name(v) for v in values]
        if any(v in PASS_COLUMN_VARIANTS or v in KNOWN_METRIC_NAMES for v in normalized_values):
            header_row_idx = int(str(i))
            break

        # Try to extract key: value from single or two-column rows
        raw_first = str(values[0]).strip()
        if ":" in raw_first:
            key, _, val = raw_first.partition(":")
            key = key.strip().lower()
            val = val.strip()
            meta_field = _META_KEY_MAP.get(key)
            if meta_field:
                metadata[meta_field] = val
        elif len(values) >= 2:
            key = str(values[0]).strip().lower()
            val = values[1]
            meta_field = _META_KEY_MAP.get(key)
            if meta_field:
                metadata[meta_field] = val
    else:
        # Never found a header row — try to use row 0 as header
        header_row_idx = 0

    return metadata, header_row_idx


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_xlsx(
    content: bytes,
    filename: str,
) -> NormalizedExperimentBatch:
    """
    Parse an MT5 XLSX optimization report.

    Args:
        content: Raw file bytes.
        filename: Original filename (used in metadata / warnings).

    Returns:
        NormalizedExperimentBatch

    Raises:
        ValueError: If the file cannot be parsed as a valid MT5 optimization report.
    """
    warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Load workbook
    # ------------------------------------------------------------------
    try:
        xls = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Cannot open XLSX file: {exc}") from exc

    sheet_names = xls.sheet_names

    # Prefer a sheet containing "optimization" in its name
    target_sheet = None
    for name in sheet_names:
        if "optim" in name.lower() or "result" in name.lower():
            target_sheet = name
            break
    if target_sheet is None:
        target_sheet = sheet_names[0]

    # ------------------------------------------------------------------
    # 2. Load raw sheet — no header so we can scan for metadata rows
    # ------------------------------------------------------------------
    try:
        df_raw = pd.read_excel(
            io.BytesIO(content),
            sheet_name=target_sheet,
            header=None,
            engine="openpyxl",
        )
    except Exception as exc:
        raise ValueError(f"Cannot read sheet '{target_sheet}': {exc}") from exc

    if df_raw.empty:
        raise ValueError("The selected worksheet is empty.")

    # ------------------------------------------------------------------
    # 3. Extract metadata from pre-header rows
    # ------------------------------------------------------------------
    raw_metadata, header_row_idx = _extract_metadata_from_header_rows(df_raw)

    # ------------------------------------------------------------------
    # 4. Re-read with the detected header row
    # ------------------------------------------------------------------
    try:
        df = pd.read_excel(
            io.BytesIO(content),
            sheet_name=target_sheet,
            header=header_row_idx,
            engine="openpyxl",
        )
    except Exception as exc:
        raise ValueError(f"Cannot read sheet with header row {header_row_idx}: {exc}") from exc

    # Drop rows that are entirely NaN
    df = df.dropna(how="all")

    if df.empty:
        raise ValueError("No data rows found after the header row.")

    columns = list(df.columns)
    # ------------------------------------------------------------------
    # 5. Classify explicit metric/pass headers independently of position
    # ------------------------------------------------------------------
    pass_col_idx, metric_col_indices, param_col_indices = classify_columns(columns)

    if pass_col_idx is None:
        warnings.append("No 'Pass' column found; optimization_pass will be set to row index.")

    param_cols = [columns[i] for i in param_col_indices]
    metric_cols = [columns[i] for i in metric_col_indices]

    # Warn if expected metrics are missing
    required_metric_lower = {"profit factor", "equity dd %"}
    found_metric_lower = {_normalize_col_name(c) for c in metric_cols}
    if not metric_cols:
        warnings.append(
            "No recognized metric columns found; non-pass columns were preserved as parameters."
        )
    for req in required_metric_lower:
        if req not in found_metric_lower:
            warnings.append(f"Expected metric column not found: '{req}'")

    if "win rate" not in found_metric_lower and "win rate %" not in found_metric_lower:
        warnings.append("Win Rate metric not found — win_rate rules will produce INSUFFICIENT_DATA")
    if found_metric_lower & {"equity dd", "drawdown"}:
        warnings.append(
            "Ambiguous drawdown values were preserved without a unit and are not used "
            "for percentage qualification."
        )

    # ------------------------------------------------------------------
    # 8. Build normalized metadata
    # ------------------------------------------------------------------
    raw_tf = raw_metadata.get("timeframe") or raw_metadata.get("period")
    if raw_tf:
        raw_tf_str, norm_tf = normalize_timeframe(raw_tf)
    else:
        raw_tf_str, norm_tf = None, None

    deposit_raw = raw_metadata.get("deposit")
    deposit_val = _safe_float(deposit_raw)

    test_start = _parse_date(raw_metadata.get("test_start"))
    test_end = _parse_date(raw_metadata.get("test_end"))

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
        source_format="xlsx",
    )

    # ------------------------------------------------------------------
    # 9. Parse rows into NormalizedExperiment objects
    # ------------------------------------------------------------------
    experiments: List[NormalizedExperiment] = []
    non_finite_metric_seen = False

    for row_num, (_, row) in enumerate(df.iterrows()):
        # Optimization pass number
        opt_pass: Optional[int] = None
        if pass_col_idx is not None:
            pass_val = row.iloc[pass_col_idx]
            try:
                opt_pass = int(float(pass_val))
            except (ValueError, TypeError):
                opt_pass = row_num

        # Parameters
        params: List[NormalizedParameter] = []
        for col in param_cols:
            raw_val = row[col]
            if pd.isna(raw_val) if isinstance(raw_val, float) else False:
                continue
            val_str, dtype = _infer_data_type(raw_val)
            params.append(NormalizedParameter(
                name=str(col).strip(),
                value=val_str,
                data_type=dtype,
            ))

        # Metrics
        metrics: List[NormalizedMetric] = []
        for col in metric_cols:
            raw_val = row[col]
            float_val, non_finite = finite_metric_value(raw_val)
            non_finite_metric_seen = non_finite_metric_seen or non_finite
            canonical, unit = normalize_metric_header(col)
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
        raise ValueError("No experiments could be extracted from the file.")
    if non_finite_metric_seen:
        warnings.append("Non-finite metric values were treated as missing.")

    return NormalizedExperimentBatch(
        metadata=batch_meta,
        experiments=experiments,
        warnings=warnings,
    )
