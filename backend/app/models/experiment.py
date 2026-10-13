"""
SQLAlchemy ORM models for the Backtest Research Manager.

Design principles:
- Parameters and metrics are fully dynamic (EAV pattern) — no hard-coded columns.
- ImportBatch tracks file-level deduplication via SHA-256 hash.
- Schema is intentionally extensible for future features (strategy versioning, AI layer).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ExperimentType(str, enum.Enum):
    discovery = "discovery"
    validation = "validation"


class EvaluationStatus(str, enum.Enum):
    qualified = "QUALIFIED"
    rejected = "REJECTED"
    insufficient_data = "INSUFFICIENT_DATA"
    pending = "PENDING"


class DataType(str, enum.Enum):
    integer = "integer"
    float = "float"
    boolean = "boolean"
    string = "string"


class SourceFormat(str, enum.Enum):
    xlsx = "xlsx"
    xml = "xml"


# ---------------------------------------------------------------------------
# ImportBatch — one record per uploaded file
# ---------------------------------------------------------------------------


class ImportBatch(Base):
    """
    Represents a single file import event.

    source_hash (SHA-256) prevents the same physical file from being
    imported twice. Future: could be linked to a user / session.
    """

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    source_format: Mapped[SourceFormat] = mapped_column(Enum(SourceFormat), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Denormalized counts stored at import time for fast summary queries
    experiments_created: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list

    experiments: Mapped[List["Experiment"]] = relationship("Experiment", back_populates="import_batch")


# ---------------------------------------------------------------------------
# Experiment — one row per optimization pass
# ---------------------------------------------------------------------------


class Experiment(Base):
    """
    Core research record.

    Every optimization pass from an MT5 export becomes one Experiment.
    Parameters and metrics are stored in child tables (EAV) to support
    any EA with any number of parameters.

    Fields intentionally left nullable where MT5 exports may omit them
    (e.g., server, leverage differ between reports).
    """

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Import provenance
    import_batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_batches.id"), nullable=False, index=True
    )

    # Research identity — the EA / strategy concept
    strategy_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    strategy_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # MT5 test configuration
    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    timeframe: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)  # normalized e.g. "H1"
    raw_timeframe: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # preserved original
    test_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    test_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # MT5 environment metadata
    server: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deposit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leverage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    mt5_build: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_format: Mapped[Optional[SourceFormat]] = mapped_column(Enum(SourceFormat), nullable=True)

    # Optimization pass number from the MT5 export
    optimization_pass: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Research classification
    experiment_type: Mapped[ExperimentType] = mapped_column(
        Enum(ExperimentType), default=ExperimentType.discovery, nullable=False
    )

    # Cached evaluation result (recomputed on demand; null = not yet evaluated)
    evaluation_status: Mapped[Optional[EvaluationStatus]] = mapped_column(
        Enum(EvaluationStatus), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    import_batch: Mapped["ImportBatch"] = relationship("ImportBatch", back_populates="experiments")
    parameters: Mapped[List["ExperimentParameter"]] = relationship(
        "ExperimentParameter", back_populates="experiment", cascade="all, delete-orphan"
    )
    metrics: Mapped[List["ExperimentMetric"]] = relationship(
        "ExperimentMetric", back_populates="experiment", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ExperimentParameter — dynamic EA parameters (EAV)
# ---------------------------------------------------------------------------


class ExperimentParameter(Base):
    """
    Stores a single EA parameter for one experiment.

    name  = "InpOneTradePerBar"
    value = "false"
    data_type = "boolean"

    Values are stored as strings for universality; data_type carries the
    semantic type so consumers can cast correctly.
    """

    __tablename__ = "experiment_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[DataType] = mapped_column(Enum(DataType), nullable=False)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="parameters")

    __table_args__ = (
        UniqueConstraint("experiment_id", "name", name="uq_experiment_parameter"),
    )


# ---------------------------------------------------------------------------
# ExperimentMetric — dynamic metrics (EAV)
# ---------------------------------------------------------------------------


class ExperimentMetric(Base):
    """
    Stores a single numeric metric for one experiment.

    name  = "profit_factor"
    value = 2.1
    unit  = ""  (dimensionless)

    name  = "equity_drawdown_pct"
    value = 12.4
    unit  = "%"
    """

    __tablename__ = "experiment_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("experiment_id", "name", name="uq_experiment_metric"),
    )
