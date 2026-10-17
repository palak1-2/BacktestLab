# Backtest Research Manager

> **This project is a research and experiment-management system, not financial advice or an automated trading system.**
>
> It does not execute trades, recommend trades, predict profitability, or automatically decide whether a strategy should go live. The human researcher makes all final decisions.

---

## Project Purpose

A MetaTrader 5 researcher running hundreds or thousands of optimization passes faces a manual, error-prone workflow: identifying useful parameter sets, recording them, and comparing results across experiments.

**Backtest Research Manager** turns raw MT5 optimization exports into structured, queryable experiment records and deterministically evaluates them against research qualification rules.

It is a **research record-keeping system**. The researcher asks:

- "Is this logic really working?"
- "Does this EA require further changes?"
- "Is this parameter set worth keeping or discarding?"

The software provides verifiable evidence from stored experiments. It does not answer these questions automatically.

---

## Architecture

```
MT5 Export (XLSX / XML + optional XML companion CSV)
        │
        ▼
  ┌─────────────┐
  │   Parser    │  xlsx_parser.py / xml_parser.py
  └─────────────┘
        │  NormalizedExperimentBatch
        ▼
  ┌─────────────┐
  │  Evaluator  │  evaluator.py (deterministic rules, no LLM)
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │  Database   │  SQLite (local) / PostgreSQL (production)
  │  (ORM/SA2)  │  Dynamic EAV tables for parameters & metrics
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │  REST API   │  FastAPI
  └─────────────┘
        │
        ▼
  Optional local Ollama interpretation (consumes bounded Python-calculated output)
```

### Directory Structure

```
BacktestLab/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── api/
│   │   │   └── experiments.py   # All REST endpoints
│   │   ├── db/
│   │   │   └── database.py      # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   └── experiment.py    # ORM models (dynamic EAV)
│   │   ├── schemas/
│   │   │   └── experiment.py    # Pydantic request/response schemas
│   │   └── services/
│   │       ├── ingestion/
│   │       │   ├── base.py         # NormalizedExperimentBatch dataclasses
│   │       │   ├── xlsx_parser.py  # MT5 XLSX parser
│   │       │   ├── xml_parser.py   # MT5 SpreadsheetML XML parser
│   │       │   ├── winrate_csv.py  # Validated XML companion enrichment
│   │       │   └── normalizer.py   # Timeframe normalization
│   │       ├── evaluation/
│   │       │   ├── rules.py        # QualificationRule definitions
│   │       │   └── evaluator.py    # Deterministic evaluation engine
│   │       └── experiments/
│   │           ├── service.py      # DB persistence + query layer
│   │           ├── autopsy.py      # Deterministic findings and parameter analysis
│   │           └── gemma.py        # Optional bounded local Ollama interpretation
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_xlsx_ingestion.py
│   │   ├── test_xml_ingestion.py
│   │   ├── test_evaluation.py
│   │   └── test_api.py
│   ├── requirements.txt
│   └── pytest.ini
├── data/
│   └── sample/              # Place your MT5 export files here
└── README.md
```

---

## Technology Stack

| Layer                 | Technology                              |
| --------------------- | --------------------------------------- |
| Language              | Python 3.11+                            |
| API Framework         | FastAPI                                 |
| ORM                   | SQLAlchemy 2.x                          |
| Validation            | Pydantic v2                             |
| Data parsing          | Pandas + openpyxl                       |
| XML parsing           | lxml (fallback: stdlib ElementTree)     |
| Database (local)      | SQLite                                  |
| Database (production) | PostgreSQL (change `DATABASE_URL` only) |
| Testing               | Pytest                                  |

---

## Setup Instructions

### 1. Prerequisites

- Python 3.11 or later
- pip

### 2. Create and activate a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the API

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at:

- **API Base**: http://localhost:8000
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

The SQLite database file `backtest_research.db` is created automatically in the `backend/` directory on first startup.

### Using PostgreSQL instead of SQLite

Set the environment variable before starting:

```bash
export DATABASE_URL=postgresql+psycopg2://user:password@localhost/backtest_research
uvicorn app.main:app --reload
```

No code changes required.

---

## Running Tests

```bash
cd backend
pytest
```

To see coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

---

## Research Autopsy (MVP)

After importing a report, request a deterministic, evidence-linked summary for its `import_batch_id`:

```bash
curl http://localhost:8000/research/autopsy/1
```

The response includes experiment status counts, metric availability and ranges, rule-failure patterns, missing-metric findings, parameter comparisons, and supporting experiment IDs. Findings and comparisons are computed by Python from stored records. Failure groups can overlap, and observed patterns are not causal proof.

Use the returned `finding_id` and `evidence_experiment_ids` to connect future UI cards to the finding and the underlying experiment detail endpoints.

### Optional Local Gemma Interpretation

Research Autopsy can optionally ask a locally running Ollama server for a qualitative interpretation of the deterministic report. This is disabled by default; ordinary requests do not contact Ollama or wait for model inference.

Install Ollama using its official instructions, start its local server, and install a local model yourself. For example:

```bash
ollama pull gemma3:4b
ollama list
curl http://localhost:11434/api/tags
```

Configure the backend before starting it (the shown defaults use Ollama on this machine):

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=gemma3:4b
export OLLAMA_TIMEOUT_SECONDS=60
```

`OLLAMA_BASE_URL` defaults to `http://localhost:11434`; the integration accepts only loopback/local hostnames. `OLLAMA_MODEL` defaults to `gemma3:4b` and can be changed to another locally installed Ollama model. `OLLAMA_TIMEOUT_SECONDS` defaults to `60` and must be between 1 and 180 seconds. The application never downloads models. Confirm a model is installed with `ollama list` and that the local service responds at `/api/tags` before requesting an interpretation.

Opt in on the existing route:

```bash
curl "http://localhost:8000/research/autopsy/1?include_ai=true"
```

The additive `ai_interpretation` result has `status` set to `success`, `unavailable`, or `error`. On unavailable Ollama/model or invalid model output, the endpoint still returns the deterministic report and a concise safe reason. The local model receives a bounded JSON summary—not raw uploaded reports or full experiment rows. Prose is validated and cannot override Python-generated findings, counts, or qualification. AI interpretations are research hypotheses only, not causal proof, predictions, or trading advice. The integration sends requests only to the configured local Ollama service; it does not call a hosted AI provider. Use a locally installed model rather than a cloud-backed model.

The optional AI integration is **experimental**. In local testing, Gemma sometimes generated unsupported or incorrect claims and failed the schema/evidence checks. These outputs are rejected, and the deterministic report remains available. Passing structural validation alone does not prove that every model-generated statement is factually correct.

On success, `ai_interpretation.interpretation` contains `summary`, evidence-linked `observations`, evidence-linked `follow_up_questions`, `referenced_finding_ids`, and `limitations`. Observation and question references are restricted to finding and experiment IDs included in the bounded context. Any evidence-list or context truncation is marked explicitly; omitted evidence is not represented as exhaustive.

## Importing an MT5 Report

### Using curl

```bash
# Import XLSX
curl -X POST http://localhost:8000/experiments/import \
  -F "file=@/path/to/your/ReportOptimizer.xlsx"

# Import XML
curl -X POST http://localhost:8000/experiments/import \
  -F "file=@/path/to/your/ReportOptimizer-253459831.xml"
```

### Paired XML + Win Rate CSV import

When an XML optimization export does not contain Win Rate, an optional companion CSV can supply it. The companion must correspond to the **same optimization run** and cover exactly the XML pass IDs; a CSV from a different or partial run is rejected.

```bash
curl -X POST http://localhost:8000/experiments/import \
  -F "file=@/path/to/ReportOptimizer.xml" \
  -F "winrate_csv=@/path/to/mt5_winrate_poc.csv"
```

The CSV must be UTF-8 with these headers: `pass`, `profitable_trades`, `total_trades`, `win_rate_pct`, `frame_status`, `parameter_values`. `parameter_values` contains JSON mapping parameter names to string values. Validation checks pass coverage, duplicate IDs, valid frame status, positive trade totals, consistent trade counts and percentages, and agreement with the XML parameters. Invalid pairings are rejected; no partial enrichment is silently accepted. The companion field is **not supported with XLSX**.

### Example Response

The following response is illustrative, not a measured import result.

```json
{
  "imported": true,
  "source_format": "xlsx",
  "source_file": "ReportOptimizer.xlsx",
  "source_hash": "a3f2c8...",
  "import_batch_id": 1,
  "experiments_created": 7924,
  "qualified": 120,
  "rejected": 5000,
  "insufficient_data": 2804,
  "pending": 0,
  "warnings": [
    "Win Rate metric not found — win_rate rules will produce INSUFFICIENT_DATA"
  ]
}
```

---

## API Reference

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### `POST /experiments/import`

Upload an MT5 optimization report in the multipart `file` field. An optional `winrate_csv` field is accepted only with XML reports; see the paired import example above.

**Accepted formats**: `.xlsx`, `.xml`

**Deduplication**: A standalone report is identified by its SHA-256 hash; a paired import uses the identities of both the XML and companion CSV. Reimporting the same input returns `"imported": false, "duplicate": true` with the original `import_batch_id` rather than duplicating records. Hashes do not imply that original upload bytes are retained.

---

### `GET /experiments`

List experiments with optional filters and pagination.

**Query parameters:**

| Parameter           | Type   | Description                                             |
| ------------------- | ------ | ------------------------------------------------------- |
| `strategy_name`     | string | Partial name match                                      |
| `symbol`            | string | Partial symbol match (e.g. `EURUSD`)                    |
| `timeframe`         | string | Exact normalized timeframe (e.g. `H1`)                  |
| `experiment_type`   | string | `discovery` or `validation`                             |
| `evaluation_status` | string | `QUALIFIED`, `REJECTED`, `INSUFFICIENT_DATA`, `PENDING` |
| `page`              | int    | Page number (default: 1)                                |
| `page_size`         | int    | Results per page (default: 50, max: 500)                |

```bash
curl "http://localhost:8000/experiments?symbol=EURUSD&evaluation_status=QUALIFIED&page=1&page_size=20"
```

---

### `GET /experiments/{id}`

Return full experiment detail including parameters and metrics.

```bash
curl http://localhost:8000/experiments/42
```

---

### `GET /experiments/{id}/evaluation`

Return the complete deterministic evaluation for an experiment.

Evaluation is computed on demand — changing rule thresholds in `rules.py` is reflected immediately without re-importing data.

```bash
curl http://localhost:8000/experiments/42/evaluation
```

**Example response:**

```json
{
  "experiment_id": 42,
  "overall_status": "INSUFFICIENT_DATA",
  "rules": [
    {
      "metric": "profit_factor",
      "operator": ">",
      "threshold": 1.5,
      "actual_value": 2.1,
      "status": "PASS"
    },
    {
      "metric": "equity_drawdown_pct",
      "operator": "<",
      "threshold": 25.0,
      "actual_value": 12.4,
      "status": "PASS"
    },
    {
      "metric": "win_rate",
      "operator": ">",
      "threshold": 60.0,
      "actual_value": null,
      "status": "INSUFFICIENT_DATA"
    }
  ]
}
```

---

## Qualification Rules

The MVP implements three hard deterministic rules:

| Rule          | Metric                | Operator | Threshold |
| ------------- | --------------------- | -------- | --------- |
| Profit Factor | `profit_factor`       | `>`      | 1.5       |
| Drawdown      | `equity_drawdown_pct` | `<`      | 25%       |
| Win Rate      | `win_rate`            | `>`      | 60%       |

Rules are defined in [`backend/app/services/evaluation/rules.py`](backend/app/services/evaluation/rules.py).

### Overall Status

| Condition                                                 | Status              |
| --------------------------------------------------------- | ------------------- |
| All required rules PASS                                   | `QUALIFIED`         |
| At least one required rule FAILS                          | `REJECTED`          |
| No FAIL, but one or more required rules have missing data | `INSUFFICIENT_DATA` |

---

## Understanding INSUFFICIENT_DATA

MT5 exports do not always include every possible metric. Some tested MT5 optimization exports **do not contain a Win Rate column**. A valid XML + companion CSV import can provide the missing Win Rate values.

When Win Rate is missing:

- The win rate rule returns `INSUFFICIENT_DATA` (not FAIL, not PASS)
- If no rule definitively FAILs → overall status is `INSUFFICIENT_DATA`
- The experiment is **NOT classified as QUALIFIED**

This is intentional: the system records what is known and honestly reports what is unknown.

**Example:**

- Profit Factor = 2.1 → PASS
- Drawdown = 12% → PASS
- Win Rate = _missing_ → INSUFFICIENT_DATA
- **Overall → INSUFFICIENT_DATA**

The researcher can then decide whether to seek additional data or apply judgment.

**Important:** A definitive FAIL always overrides INSUFFICIENT_DATA:

- Profit Factor FAIL + Win Rate missing → **REJECTED** (not INSUFFICIENT_DATA)

---

## Supported File Formats

### MT5 XLSX (`.xlsx`)

Excel exports from MetaTrader 5 Strategy Tester optimization runs.

- Supports any number of parameters (4 to 16+ observed in real exports)
- Detects parameter vs metric columns dynamically
- Extracts metadata from header rows (symbol, timeframe, server, deposit, leverage)
- Preserves all columns — unknown columns are not discarded

### MT5 SpreadsheetML XML (`.xml`)

XML exports such as `ReportOptimizer-253459831.xml`.

- Handles Microsoft SpreadsheetML namespace
- Extracts `DocumentProperties` (title, author, created)
- Supports sparse cells with `ss:Index`
- Same normalization pipeline as XLSX
- Can be paired with a validated Win Rate companion CSV from the same optimization run

### Optional Win Rate companion CSV (`.csv`)

This is **not** a standalone import format. Supply it as `winrate_csv` alongside an XML report. The CSV must have matching pass IDs and parameter values, and internally consistent frame status, trade counts, and Win Rate percentages.

---

## Timeframe Normalization

MT5 may export timeframes as numeric constants. These are normalized:

| Raw Value | Normalized             |
| --------- | ---------------------- |
| `16385`   | `H1`                   |
| `16388`   | `H4`                   |
| `16408`   | `D1`                   |
| `M15`     | `M15` (passed through) |

The original raw value is always preserved in `raw_timeframe`.

---

## Project Roadmap

### MVP (current)

- [x] MT5 XLSX ingestion
- [x] MT5 XML ingestion
- [x] Validated paired XML + Win Rate CSV enrichment
- [x] Dynamic parameter storage (EAV)
- [x] Dynamic metric storage (EAV)
- [x] Deterministic qualification engine
- [x] REST API
- [x] Duplicate detection (SHA-256)
- [x] Automated tests
- [x] Deterministic, evidence-linked Research Autopsy
- [x] Optional local Ollama/Gemma integration (experimental; invalid outputs safely rejected)

### Planned

- [ ] Frontend web interface
- [ ] PostgreSQL deployment support
- [ ] Experiment comparison views
- [ ] Strategy version tracking
- [ ] Candidate / Validation workflow
- [ ] Authentication
- [ ] Vector search for similar experiments
- [ ] Detailed analytics and charts

---

## Research Model

The system is designed around this research workflow:

```
Strategy Logic
      │
      ▼
Strategy Version
      │
      ▼
EA Implementation
      │
      ▼
Parameter Configuration
      │
      ▼
Discovery Experiment  ◄──── imported from MT5 optimizer
      │
      ▼
Candidate
      │
      ▼
Validation Experiments
      │
      ▼
Human Decision
      │
      ▼
Keep / Modify / Discard
      │
      ▼
Potential Live Deployment  (not automated by this system)
```

The EA filename alone is not the research identity — the underlying trading logic is.

---

## License

MIT
