"""
Timeframe normalization for MT5 numeric enum values.

MT5 stores timeframes as integer constants in some export formats.
This module maps them to human-readable strings and preserves the original.

Reference: MetaTrader 5 ENUM_TIMEFRAMES
"""

from typing import Any

# MT5 ENUM_TIMEFRAMES integer → string mapping
MT5_TIMEFRAME_MAP: dict[str | int, str] = {
    # Minutes
    1:     "M1",
    2:     "M2",
    3:     "M3",
    4:     "M4",
    5:     "M5",
    6:     "M6",
    10:    "M10",
    12:    "M12",
    15:    "M15",
    20:    "M20",
    30:    "M30",
    # Hours
    16385: "H1",
    16386: "H2",
    16387: "H3",
    16388: "H4",
    16390: "H6",
    16392: "H8",
    16396: "H12",
    # Days / Weeks / Months
    16408: "D1",
    32769: "W1",
    49153: "MN1",
}

# Also accept string representations like "16385" or "H1" already decoded
_STRING_ALIASES: dict[str, str] = {str(k): v for k, v in MT5_TIMEFRAME_MAP.items()}
# Add pass-throughs for already-normalized strings
_KNOWN_TF_STRINGS = set(MT5_TIMEFRAME_MAP.values())


METRIC_CANONICAL_NAMES = {
    "equity dd %": "equity_drawdown_pct",
    "drawdown %": "equity_drawdown_pct",
    "equity dd": "equity_dd",
    "drawdown": "drawdown",
    "profit factor": "profit_factor",
    "profit": "profit",
    "expected payoff": "expected_payoff",
    "recovery factor": "recovery_factor",
    "sharpe ratio": "sharpe_ratio",
    "trades": "trades",
    "win rate": "win_rate",
    "win rate %": "win_rate",
    "result": "result",
    "custom": "custom",
}

METRIC_UNITS = {
    "equity_drawdown_pct": "%",
    "win_rate": "%",
}


def normalize_metric_header(name: Any) -> tuple[str, str]:
    """Map exact known headers; only the explicit percent aliases map to percentage metrics."""
    normalized = str(name).strip().lower()
    canonical = METRIC_CANONICAL_NAMES.get(normalized, normalized.replace(" ", "_"))
    return canonical, METRIC_UNITS.get(canonical, "")


def validate_unique_metric_headers(headers: list[Any]) -> None:
    """Reject source columns that would collide in the one-name-per-experiment metric table."""
    seen: set[str] = set()
    for header in headers:
        canonical, _ = normalize_metric_header(header)
        if canonical in seen:
            raise ValueError(
                f"Multiple metric columns normalize to '{canonical}'; "
                "the report contains ambiguous duplicate metrics."
            )
        seen.add(canonical)


def normalize_timeframe(raw: object) -> tuple[str, str | None]:
    """
    Convert a raw MT5 timeframe value to a normalized string.

    Args:
        raw: The raw value from the MT5 export (int, str, or other).

    Returns:
        (raw_as_str, normalized_str_or_None)

    Examples:
        normalize_timeframe(16385)  → ("16385", "H1")
        normalize_timeframe("H1")  → ("H1", "H1")
        normalize_timeframe("M15") → ("M15", "M15")
        normalize_timeframe(99999) → ("99999", None)
    """
    raw_str = str(raw) if raw is not None else ""

    if raw_str.upper() in _KNOWN_TF_STRINGS:
        return raw_str, raw_str.upper()

    # Try integer lookup
    try:
        int_val = int(float(raw_str))
        if int_val in MT5_TIMEFRAME_MAP:
            return raw_str, MT5_TIMEFRAME_MAP[int_val]
    except (ValueError, TypeError):
        pass

    # Try string alias
    if raw_str in _STRING_ALIASES:
        return raw_str, _STRING_ALIASES[raw_str]

    return raw_str, None
