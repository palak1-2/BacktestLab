"""
REST API router for experiments.

Endpoints:
  POST /experiments/import      — upload XLSX or XML, ingest, evaluate
  GET  /experiments             — list with filters + pagination
  GET  /experiments/{id}        — experiment detail with parameters & metrics
  GET  /experiments/{id}/evaluation — deterministic evaluation result
  GET  /health                  — service liveness check
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.experiment import (
    EvaluationResponseSchema,
    EvaluationStatusSchema,
    ExperimentDetailSchema,
    ExperimentTypeSchema,
    HealthSchema,
    ImportBatchSummarySchema,
    ImportResponseSchema,
    PaginatedImportBatchesSchema,
    PaginatedExperimentsSchema,
    RuleResultSchema,
    SourceFormatSchema,
)
from app.services.evaluation.evaluator import (
    evaluate_experiment,
    metrics_from_experiment_model,
)
from app.services.experiments.autopsy import build_autopsy
from app.services.experiments.gemma import generate_interpretation
from app.services.experiments.service import (
    compute_file_hash,
    get_import_batches,
    get_experiment_by_id,
    get_experiments,
    is_duplicate,
    save_batch,
)
from app.services.ingestion.xlsx_parser import parse_xlsx
from app.services.ingestion.winrate_csv import (
    enrich_xml_batch_with_winrate,
    paired_import_hash,
    pairing_provenance,
)
from app.services.ingestion.xml_parser import parse_xml

router = APIRouter()

MAX_UPLOAD_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _batch_warnings(raw_warnings: Optional[str]) -> list[str]:
    if not raw_warnings:
        return []
    try:
        parsed = json.loads(raw_warnings)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed) else []


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthSchema, tags=["system"])
def health() -> HealthSchema:
    """Liveness probe."""
    return HealthSchema(status="ok")


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@router.post("/experiments/import", response_model=ImportResponseSchema, tags=["experiments"])
async def import_experiments(
    file: UploadFile = File(...),
    winrate_csv: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
) -> ImportResponseSchema:
    """
    Import an MT5 optimization report (XLSX or XML).

    - Detects format from file extension and content-type.
    - Computes SHA-256 to prevent duplicate imports.
    - Parses, normalizes, evaluates, and bulk-inserts all experiments.
    - Returns a summary including qualification status counts.
    """
    # ------------------------------------------------------------------
    # Validate file type
    # ------------------------------------------------------------------
    filename = file.filename or "upload"
    content_type = file.content_type or ""

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    is_xlsx = ext == "xlsx" or "spreadsheetml" in content_type or "excel" in content_type
    is_xml = ext == "xml" or "xml" in content_type

    if not is_xlsx and not is_xml:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Only .xlsx and .xml are accepted.",
        )
    if winrate_csv is not None and (not is_xml or is_xlsx):
        raise HTTPException(
            status_code=422,
            detail="The winrate_csv companion is only supported with an XML report.",
        )

    # ------------------------------------------------------------------
    # Read file bytes
    # ------------------------------------------------------------------
    content = await file.read(MAX_UPLOAD_BYTES + 1)

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_MB} MB.",
        )

    companion_content: Optional[bytes] = None
    if winrate_csv is not None:
        companion_content = await winrate_csv.read(MAX_UPLOAD_BYTES + 1)
        if not companion_content:
            raise HTTPException(status_code=400, detail="Uploaded winrate_csv is empty.")
        if len(companion_content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Companion CSV too large. Maximum size is {MAX_UPLOAD_MB} MB.",
            )

    # ------------------------------------------------------------------
    # Deduplication check
    # ------------------------------------------------------------------
    xml_hash = compute_file_hash(content)
    companion_hash = (
        compute_file_hash(companion_content) if companion_content is not None else None
    )
    if companion_content is None:
        source_hash = xml_hash
    else:
        assert companion_hash is not None
        source_hash = paired_import_hash(xml_hash, companion_hash)
    existing = is_duplicate(db, source_hash)
    if existing:
        return ImportResponseSchema(
            imported=False,
            duplicate=True,
            source_format=SourceFormatSchema(existing.source_format.value),
            source_file=existing.source_file,
            source_hash=source_hash,
            import_batch_id=existing.id,
            experiments_created=existing.experiments_created,
            qualified=0,
            rejected=0,
            insufficient_data=0,
            pending=0,
            warnings=[],
            detail="File already imported. Use import_batch_id to query experiments.",
        )

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------
    try:
        if is_xlsx:
            batch = parse_xlsx(content, filename)
        else:
            batch = parse_xml(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected parsing error: {exc}",
        )

    if companion_content is not None:
        try:
            enrich_xml_batch_with_winrate(batch, companion_content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        assert companion_hash is not None
        batch.warnings = [
            warning
            for warning in batch.warnings
            if warning != "Win Rate metric not found — win_rate rules will produce INSUFFICIENT_DATA"
        ]
        batch.warnings.append(pairing_provenance(xml_hash, companion_hash))

    # ------------------------------------------------------------------
    # Persist + evaluate
    # ------------------------------------------------------------------
    try:
        import_batch, status_counts = save_batch(db, batch, source_hash)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error during import: {exc}",
        )

    source_fmt = SourceFormatSchema(batch.metadata.source_format)

    return ImportResponseSchema(
        imported=True,
        duplicate=False,
        source_format=source_fmt,
        source_file=filename,
        source_hash=source_hash,
        import_batch_id=import_batch.id,
        experiments_created=import_batch.experiments_created,
        qualified=status_counts.get("QUALIFIED", 0),
        rejected=status_counts.get("REJECTED", 0),
        insufficient_data=status_counts.get("INSUFFICIENT_DATA", 0),
        pending=status_counts.get("PENDING", 0),
        warnings=batch.warnings,
    )


# ---------------------------------------------------------------------------
# Research Autopsy
# ---------------------------------------------------------------------------


@router.get("/research/autopsy/{import_batch_id}", tags=["research"])
def get_research_autopsy(
    import_batch_id: int,
    include_ai: bool = Query(
        False,
        description="Request an optional interpretation from a locally configured Ollama model.",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Return deterministic findings and, when requested, an optional local AI interpretation."""
    result = build_autopsy(db, import_batch_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Import batch {import_batch_id} not found.",
        )
    if include_ai:
        result["ai_interpretation"] = generate_interpretation(result)
    return result


# ---------------------------------------------------------------------------
# List experiments
# ---------------------------------------------------------------------------


@router.get(
    "/import-batches",
    response_model=PaginatedImportBatchesSchema,
    tags=["experiments"],
)
def list_import_batches(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    db: Session = Depends(get_db),
) -> PaginatedImportBatchesSchema:
    """List import batches newest first with parsed warning metadata."""
    total, batches = get_import_batches(db, page=page, page_size=page_size)
    return PaginatedImportBatchesSchema(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            ImportBatchSummarySchema(
                id=batch.id,
                source_file=batch.source_file,
                source_format=SourceFormatSchema(batch.source_format.value),
                created_at=batch.created_at,
                experiments_created=batch.experiments_created,
                warnings=_batch_warnings(batch.warnings),
            )
            for batch in batches
        ],
    )


@router.get("/experiments", response_model=PaginatedExperimentsSchema, tags=["experiments"])
def list_experiments(
    strategy_name: Optional[str] = Query(None, description="Filter by strategy name (partial match)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol (partial match)"),
    timeframe: Optional[str] = Query(None, description="Filter by normalized timeframe (e.g. H1)"),
    experiment_type: Optional[str] = Query(None, description="discovery | validation"),
    evaluation_status: Optional[str] = Query(None, description="QUALIFIED | REJECTED | INSUFFICIENT_DATA | PENDING"),
    import_batch_id: Optional[int] = Query(None, ge=1, description="Filter by import batch ID"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    db: Session = Depends(get_db),
) -> PaginatedExperimentsSchema:
    """
    List experiments with optional filtering and pagination.

    Avoids loading thousands of rows unnecessarily by applying filters
    at the database level and using LIMIT/OFFSET.
    """
    # Validate enum inputs
    if experiment_type and experiment_type not in ("discovery", "validation"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid experiment_type '{experiment_type}'. Use 'discovery' or 'validation'.",
        )
    if evaluation_status and evaluation_status not in (
        "QUALIFIED", "REJECTED", "INSUFFICIENT_DATA", "PENDING"
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid evaluation_status '{evaluation_status}'.",
        )

    total, items = get_experiments(
        db,
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        experiment_type=experiment_type,
        evaluation_status=evaluation_status,
        import_batch_id=import_batch_id,
        page=page,
        page_size=page_size,
    )

    return PaginatedExperimentsSchema(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


# ---------------------------------------------------------------------------
# Experiment detail
# ---------------------------------------------------------------------------


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentDetailSchema,
    tags=["experiments"],
)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> ExperimentDetailSchema:
    """Return full experiment record including parameters and metrics."""
    experiment = get_experiment_by_id(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found.")
    return experiment


# ---------------------------------------------------------------------------
# Evaluation endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/experiments/{experiment_id}/evaluation",
    response_model=EvaluationResponseSchema,
    tags=["experiments"],
)
def get_evaluation(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> EvaluationResponseSchema:
    """
    Return the complete deterministic evaluation for an experiment.

    Re-evaluates on demand using current rules (so rule threshold changes
    are reflected without re-importing).
    """
    experiment = get_experiment_by_id(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found.")

    metric_dict = metrics_from_experiment_model(experiment)
    eval_result = evaluate_experiment(metric_dict)

    return EvaluationResponseSchema(
        experiment_id=experiment_id,
        overall_status=EvaluationStatusSchema(eval_result.overall_status),
        rules=[
            RuleResultSchema(
                metric=rr.rule.metric,
                operator=rr.rule.operator,
                threshold=rr.rule.threshold,
                actual_value=rr.actual_value,
                status=rr.status,
            )
            for rr in eval_result.rule_results
        ],
    )
