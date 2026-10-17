"""
Pydantic schemas for request/response serialization.

Kept separate from ORM models. The API layer translates between these
schemas and the SQLAlchemy models via the service layer — never directly.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations (mirroring model enums without coupling to SQLAlchemy)
# ---------------------------------------------------------------------------


class ExperimentTypeSchema(str, Enum):
    discovery = "discovery"
    validation = "validation"


class EvaluationStatusSchema(str, Enum):
    qualified = "QUALIFIED"
    rejected = "REJECTED"
    insufficient_data = "INSUFFICIENT_DATA"
    pending = "PENDING"


class DataTypeSchema(str, Enum):
    integer = "integer"
    float = "float"
    boolean = "boolean"
    string = "string"


class SourceFormatSchema(str, Enum):
    xlsx = "xlsx"
    xml = "xml"


# ---------------------------------------------------------------------------
# Parameter / Metric
# ---------------------------------------------------------------------------


class ParameterSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    value: str
    data_type: DataTypeSchema


class MetricSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    value: Optional[float]
    unit: Optional[str]

    @field_validator("value", mode="before")
    @classmethod
    def non_finite_values_are_missing(cls, value: Any) -> Any:
        if value is None:
            return None
        try:
            if not math.isfinite(float(value)):
                return None
        except (OverflowError, TypeError, ValueError):
            return value
        return value


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------


class ExperimentSummarySchema(BaseModel):
    """Lightweight schema used in list responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_name: Optional[str]
    strategy_version: Optional[str]
    symbol: Optional[str]
    timeframe: Optional[str]
    optimization_pass: Optional[int]
    experiment_type: ExperimentTypeSchema
    evaluation_status: Optional[EvaluationStatusSchema]
    created_at: datetime


class ExperimentDetailSchema(BaseModel):
    """Full schema with parameters and metrics, used in detail/evaluation endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_batch_id: int
    strategy_name: Optional[str]
    strategy_version: Optional[str]
    symbol: Optional[str]
    timeframe: Optional[str]
    raw_timeframe: Optional[str]
    test_start: Optional[datetime]
    test_end: Optional[datetime]
    server: Optional[str]
    deposit: Optional[float]
    leverage: Optional[str]
    mt5_build: Optional[str]
    source_file: Optional[str]
    source_format: Optional[SourceFormatSchema]
    optimization_pass: Optional[int]
    experiment_type: ExperimentTypeSchema
    evaluation_status: Optional[EvaluationStatusSchema]
    created_at: datetime
    parameters: List[ParameterSchema]
    metrics: List[MetricSchema]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class RuleResultSchema(BaseModel):
    metric: str
    operator: str
    threshold: float
    actual_value: Optional[float]
    status: str  # PASS | FAIL | INSUFFICIENT_DATA


class EvaluationResponseSchema(BaseModel):
    experiment_id: int
    overall_status: EvaluationStatusSchema
    rules: List[RuleResultSchema]


# ---------------------------------------------------------------------------
# Import response
# ---------------------------------------------------------------------------


class ImportResponseSchema(BaseModel):
    imported: bool
    duplicate: bool = False
    source_format: SourceFormatSchema
    source_file: str
    source_hash: str
    import_batch_id: Optional[int]
    experiments_created: int
    qualified: int
    rejected: int
    insufficient_data: int
    pending: int
    warnings: List[str] = Field(default_factory=list)
    detail: Optional[str] = None  # error message if imported=False


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------


class PaginatedExperimentsSchema(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ExperimentSummarySchema]


class ImportBatchSummarySchema(BaseModel):
    id: int
    source_file: str
    source_format: SourceFormatSchema
    created_at: datetime
    experiments_created: int
    warnings: List[str] = Field(default_factory=list)


class PaginatedImportBatchesSchema(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ImportBatchSummarySchema]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthSchema(BaseModel):
    status: str
