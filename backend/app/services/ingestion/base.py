"""
Internal normalized representation used by all parsers.

Both XLSX and XML parsers must produce a NormalizedExperimentBatch.
The database service, evaluation engine, and API consume only this structure.
No parser-specific logic leaks beyond its own module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class NormalizedParameter:
    name: str
    value: str               # Always stored as string; data_type conveys semantics
    data_type: str           # "integer" | "float" | "boolean" | "string"


@dataclass
class NormalizedMetric:
    name: str
    value: Optional[float]
    unit: str = ""


@dataclass
class NormalizedExperiment:
    optimization_pass: Optional[int]
    parameters: List[NormalizedParameter] = field(default_factory=list)
    metrics: List[NormalizedMetric] = field(default_factory=list)


@dataclass
class NormalizedBatchMetadata:
    """
    Metadata extracted from the MT5 export header / file properties.
    All fields are optional because different exports provide different
    levels of metadata.
    """
    strategy_name: Optional[str] = None
    strategy_version: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None           # normalized e.g. "H1"
    raw_timeframe: Optional[str] = None       # original value preserved
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None
    server: Optional[str] = None
    deposit: Optional[float] = None
    leverage: Optional[str] = None
    mt5_build: Optional[str] = None
    source_file: str = ""
    source_format: str = ""                   # "xlsx" | "xml"


@dataclass
class NormalizedExperimentBatch:
    """
    Complete output of any parser.  One batch = one uploaded file.
    """
    metadata: NormalizedBatchMetadata
    experiments: List[NormalizedExperiment] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
