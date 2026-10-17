"""
Experiment service — database persistence layer.

Translates NormalizedExperimentBatch → SQLAlchemy models using
bulk insertion for performance with thousands of rows.

Deduplication: checks source_hash (SHA-256) before inserting.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import List, Optional, Tuple

from sqlalchemy import insert as sa_insert
from sqlalchemy.orm import Session

from app.models.experiment import (
    EvaluationStatus,
    Experiment,
    ExperimentMetric,
    ExperimentParameter,
    ExperimentType,
    ImportBatch,
    SourceFormat,
)

from app.services.evaluation.evaluator import evaluate_experiment
from app.services.ingestion.base import NormalizedExperimentBatch
from app.services.metrics import finite_metric_value


def compute_file_hash(content: bytes) -> str:
    """Return SHA-256 hex digest of file content."""
    return hashlib.sha256(content).hexdigest()


def is_duplicate(db: Session, source_hash: str) -> Optional[ImportBatch]:
    """Return existing ImportBatch if the file has already been imported."""
    return db.query(ImportBatch).filter(ImportBatch.source_hash == source_hash).first()


def get_import_batches(
    db: Session,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[int, List[ImportBatch]]:
    """Return newest import batches with a bounded database-side page."""
    query = db.query(ImportBatch)
    total = query.count()
    offset = (page - 1) * page_size
    items = (
        query.order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return total, items


def save_batch(
    db: Session,
    batch: NormalizedExperimentBatch,
    source_hash: str,
) -> Tuple[ImportBatch, Counter]:
    """
    Persist a NormalizedExperimentBatch to the database.

    Uses bulk inserts for parameters and metrics to handle thousands of rows
    efficiently.

    Returns:
        (ImportBatch, Counter with status counts)
    """
    # ------------------------------------------------------------------
    # 1. Create ImportBatch record
    # ------------------------------------------------------------------
    source_format_val = SourceFormat(batch.metadata.source_format)

    has_non_finite_metrics = any(
        finite_metric_value(metric.value)[1]
        for experiment in batch.experiments
        for metric in experiment.metrics
    )
    batch_warnings = list(batch.warnings)
    if has_non_finite_metrics and "Non-finite metric values were treated as missing." not in batch_warnings:
        batch_warnings.append("Non-finite metric values were treated as missing.")

    import_batch = ImportBatch(
        source_file=batch.metadata.source_file,
        source_format=source_format_val,
        source_hash=source_hash,
        experiments_created=0,
        warnings=json.dumps(batch_warnings),
    )
    db.add(import_batch)
    db.flush()  # Get import_batch.id without committing

    # ------------------------------------------------------------------
    # 2. Build Experiment + evaluate in one pass
    # ------------------------------------------------------------------
    status_counter: Counter = Counter()
    all_param_rows: List[dict] = []
    all_metric_rows: List[dict] = []

    for norm_exp in batch.experiments:
        # Determine evaluation status
        metric_dict = {
            metric.name: finite_metric_value(metric.value)[0]
            for metric in norm_exp.metrics
        }
        eval_result = evaluate_experiment(metric_dict)
        eval_status = EvaluationStatus(eval_result.overall_status)
        status_counter[eval_result.overall_status] += 1

        # Map timeframe
        experiment = Experiment(
            import_batch_id=import_batch.id,
            strategy_name=batch.metadata.strategy_name,
            strategy_version=batch.metadata.strategy_version,
            symbol=batch.metadata.symbol,
            timeframe=batch.metadata.timeframe,
            raw_timeframe=batch.metadata.raw_timeframe,
            test_start=batch.metadata.test_start,
            test_end=batch.metadata.test_end,
            server=batch.metadata.server,
            deposit=batch.metadata.deposit,
            leverage=batch.metadata.leverage,
            mt5_build=batch.metadata.mt5_build,
            source_file=batch.metadata.source_file,
            source_format=source_format_val,
            optimization_pass=norm_exp.optimization_pass,
            experiment_type=ExperimentType.discovery,
            evaluation_status=eval_status,
        )
        db.add(experiment)
        db.flush()  # Get experiment.id

        # Collect parameter rows for bulk insert
        for param in norm_exp.parameters:
            all_param_rows.append({
                "experiment_id": experiment.id,
                "name": param.name,
                "value": param.value,
                "data_type": param.data_type,
            })

        # Collect metric rows for bulk insert
        for metric in norm_exp.metrics:
            all_metric_rows.append({
                "experiment_id": experiment.id,
                "name": metric.name,
                "value": finite_metric_value(metric.value)[0],
                "unit": metric.unit,
            })

    # ------------------------------------------------------------------
    # 3. Bulk insert parameters and metrics
    # SQLAlchemy 2.x compatible: use insert() + execute() with list of dicts
    # ------------------------------------------------------------------
    if all_param_rows:
        db.execute(sa_insert(ExperimentParameter), all_param_rows)

    if all_metric_rows:
        db.execute(sa_insert(ExperimentMetric), all_metric_rows)

    # ------------------------------------------------------------------
    # 4. Update batch summary
    # ------------------------------------------------------------------
    import_batch.experiments_created = len(batch.experiments)
    db.flush()
    db.commit()

    return import_batch, status_counter


def get_experiments(
    db: Session,
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    experiment_type: Optional[str] = None,
    evaluation_status: Optional[str] = None,
    import_batch_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[int, List[Experiment]]:
    """
    Query experiments with optional filters and pagination.
    Returns (total_count, experiments_on_page).
    """
    q = db.query(Experiment)

    if strategy_name:
        q = q.filter(Experiment.strategy_name.ilike(f"%{strategy_name}%"))
    if symbol:
        q = q.filter(Experiment.symbol.ilike(f"%{symbol}%"))
    if timeframe:
        q = q.filter(Experiment.timeframe == timeframe)
    if experiment_type:
        q = q.filter(Experiment.experiment_type == ExperimentType(experiment_type))
    if evaluation_status:
        q = q.filter(Experiment.evaluation_status == EvaluationStatus(evaluation_status))
    if import_batch_id is not None:
        q = q.filter(Experiment.import_batch_id == import_batch_id)

    total = q.count()
    offset = (page - 1) * page_size
    items = q.order_by(Experiment.id).offset(offset).limit(page_size).all()

    return total, items


def get_experiment_by_id(db: Session, experiment_id: int) -> Optional[Experiment]:
    """Fetch a single experiment with its parameters and metrics eagerly loaded."""
    from sqlalchemy.orm import joinedload
    return (
        db.query(Experiment)
        .options(
            joinedload(Experiment.parameters),
            joinedload(Experiment.metrics),
        )
        .filter(Experiment.id == experiment_id)
        .first()
    )
