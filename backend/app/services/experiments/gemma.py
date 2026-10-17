"""Optional local Ollama interpretation of deterministic Research Autopsy output."""

from __future__ import annotations

import ipaddress
import json
import logging
import math
import os
import re
from typing import Any, Literal, NotRequired, TypedDict
from urllib.parse import urlsplit

import httpx


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TIMEOUT_SECONDS = 180.0
MAX_CONTEXT_BYTES = 24_000
MAX_RESPONSE_CHARS = 8_000
MAX_HTTP_RESPONSE_BYTES = 1_048_576
MAX_FINDINGS = 10
MAX_PARAMETERS = 6
MAX_GROUPS_PER_PARAMETER = 5
MAX_EVIDENCE_IDS = 8

logger = logging.getLogger(__name__)


class Observation(TypedDict):
    text: str
    finding_ids: list[str]
    evidence_experiment_ids: list[int]


class FollowUpQuestion(TypedDict):
    question: str
    finding_ids: list[str]
    evidence_experiment_ids: list[int]


class Interpretation(TypedDict):
    summary: str
    observations: list[Observation]
    follow_up_questions: list[FollowUpQuestion]
    referenced_finding_ids: list[str]
    limitations: list[str]


class AIResult(TypedDict):
    status: Literal["success", "unavailable", "error"]
    reason: NotRequired[str]
    model: NotRequired[str]
    interpretation: NotRequired[Interpretation]
    context_truncated: NotRequired[bool]


class ModelInterpretation(TypedDict):
    observation: str
    question: str
    limitation: str


SYSTEM_PROMPT = """You are a concise research assistant for BacktestLab.
Interpret the supplied deterministic research finding.

Return exactly three JSON string fields:
observation, question, limitation.

The observation and question MUST explicitly name the finding's metric,
using natural words such as "profit factor", "drawdown", or "win rate".

Use qualitative language only.
Do NOT write digits, percentages, quantities, counts, ordinal words,
or number words such as one, two, first, second, single, twice, or half.
Do not repeat numerical thresholds from the input.

Do not claim robustness, causation, profitability, or future performance.
Do not invent evidence or discuss metrics outside the selected finding.
Provide a cautious observation, a testable research question, and a limitation.
Keep each field concise."""

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "observation": {"type": "string", "minLength": 1, "maxLength": 350},
        "question": {"type": "string", "minLength": 1, "maxLength": 300},
        "limitation": {"type": "string", "minLength": 1, "maxLength": 300},
    },
    "required": ["observation", "question", "limitation"],
    "additionalProperties": False,
}

_NUMERIC_CLAIM = re.compile(
    r"\d|(?<![A-Za-z])(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"thirty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"forty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"fifty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"sixty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"seventy(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"eighty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"ninety(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"hundred|thousand|million|billion|trillion|first|second|third|fourth|fifth|"
    r"sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|"
    r"fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|"
    r"thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth|"
    r"hundredth|thousandth|millionth|billionth|once|twice|thrice|single|couple|pair|"
    r"half|double|doubled|doubling|triple|tripled|tripling|twofold|threefold|tenfold)"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)


def _display_value(value: Any, limit: int = 120) -> tuple[Any, bool]:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit], True
    return value, False


def _finite_context_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError("Duplicate JSON object key.")
        parsed[key] = value
    return parsed


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _strict_json_loads(raw: str | bytes) -> Any:
    return json.loads(
        raw,
        object_pairs_hook=_unique_json_object,
        parse_constant=_reject_json_constant,
    )


def build_gemma_context(autopsy: dict[str, Any]) -> dict[str, Any]:
    """Build a stable, bounded context using only deterministic Autopsy output."""
    findings = autopsy.get("findings", [])
    parameters = autopsy.get("parameter_analysis", {}).get("parameters", [])
    context_findings = []
    evidence_truncated = False
    for finding in findings[:MAX_FINDINGS]:
        evidence_ids = finding.get("evidence_experiment_ids", [])
        evidence_truncated = evidence_truncated or len(evidence_ids) > MAX_EVIDENCE_IDS
        context_findings.append({
            "finding_id": finding.get("finding_id"),
            "kind": finding.get("kind"),
            "title": finding.get("title"),
            "description": finding.get("description"),
            "metric": finding.get("metric"),
            "operator": finding.get("operator"),
            "threshold": finding.get("threshold"),
            "count": finding.get("count"),
            "evidence_count": finding.get("evidence_count", len(evidence_ids)),
            "evidence_experiment_ids": evidence_ids[:MAX_EVIDENCE_IDS],
            "evidence_truncated": len(evidence_ids) > MAX_EVIDENCE_IDS,
        })

    eligible_subjects = []
    seen_finding_ids: set[str] = set()
    for finding in context_findings:
        finding_id = finding.get("finding_id")
        kind = finding.get("kind")
        metric = finding.get("metric")
        if (
            not isinstance(finding_id, str)
            or not finding_id
            or finding_id in seen_finding_ids
            or not isinstance(kind, str)
            or not isinstance(metric, str)
        ):
            continue
        evidence_ids = [
            experiment_id
            for experiment_id in finding.get("evidence_experiment_ids", [])
            if type(experiment_id) is int and experiment_id > 0
        ]
        evidence_ids = list(dict.fromkeys(evidence_ids))[:MAX_EVIDENCE_IDS]
        if not evidence_ids:
            continue
        seen_finding_ids.add(finding_id)
        eligible_subjects.append({
            "finding_id": finding_id,
            "finding_type": kind,
            "metric": metric,
            "title": finding.get("title"),
            "description": finding.get("description"),
            "evidence_experiment_ids": evidence_ids,
        })

    context_parameters = []
    omitted_groups = 0
    values_truncated = False
    for parameter in parameters[:MAX_PARAMETERS]:
        groups = parameter.get("groups", [])
        context_groups = []
        for group in groups[:MAX_GROUPS_PER_PARAMETER]:
            group_value, value_truncated = _display_value(group.get("value"))
            evidence_ids = group.get("evidence_experiment_ids", [])
            values_truncated = values_truncated or value_truncated
            evidence_truncated = evidence_truncated or len(evidence_ids) > MAX_EVIDENCE_IDS
            context_groups.append({
                "kind": group.get("kind"),
                "value": group_value,
                "value_truncated": value_truncated,
                "minimum": group.get("minimum"),
                "maximum": group.get("maximum"),
                "experiment_count": group.get("experiment_count"),
                "low_support": group.get("low_support"),
                "outcomes": group.get("outcomes"),
                "evidence_experiment_ids": evidence_ids[:MAX_EVIDENCE_IDS],
                "evidence_count": len(evidence_ids),
                "evidence_truncated": len(evidence_ids) > MAX_EVIDENCE_IDS,
            })
        omitted_groups += max(0, len(groups) - MAX_GROUPS_PER_PARAMETER)
        context_parameters.append({
            "name": parameter.get("name"),
            "experiment_count": parameter.get("experiment_count"),
            "usable_value_count": parameter.get("usable_value_count"),
            "missing_parameter_count": parameter.get("missing_parameter_count"),
            "unusable_value_count": parameter.get("unusable_value_count"),
            "unusable_values": {
                reason: {
                    "count": details.get("count"),
                    "evidence_experiment_ids": details.get("evidence_experiment_ids", [])[:MAX_EVIDENCE_IDS],
                    "evidence_truncated": len(details.get("evidence_experiment_ids", [])) > MAX_EVIDENCE_IDS,
                }
                for reason, details in parameter.get("unusable_values", {}).items()
            },
            "groups": context_groups,
            "omitted_group_count": max(0, len(groups) - MAX_GROUPS_PER_PARAMETER),
        })

    context = {
        "batch_reference": autopsy.get("import_batch_id"),
        "status_counts": autopsy.get("status_counts", {}),
        "metric_summary": {
            metric: {
                field: _finite_context_number(value)
                for field, value in autopsy.get("metric_summary", {}).get(metric, {}).items()
                if field in {"available_count", "missing_count", "min", "median", "max"}
            }
            for metric in ("profit_factor", "equity_drawdown_pct", "win_rate")
            if metric in autopsy.get("metric_summary", {})
        },
        "failure_and_data_gap_findings": context_findings,
        "eligible_subjects": eligible_subjects,
        "omitted_finding_count": max(0, len(findings) - MAX_FINDINGS),
        "parameter_analysis": {
            "grouping_method": autopsy.get("parameter_analysis", {}).get("grouping_method"),
            "minimum_group_support": autopsy.get("parameter_analysis", {}).get("minimum_group_support"),
            "interpretation": autopsy.get("parameter_analysis", {}).get("interpretation"),
            "parameters": context_parameters,
            "omitted_parameter_count": max(0, len(parameters) - MAX_PARAMETERS),
            "omitted_group_count": omitted_groups,
        },
        "deterministic_caveats": autopsy.get("analysis_notes", []),
        "context_truncated": (
            len(findings) > MAX_FINDINGS
            or len(parameters) > MAX_PARAMETERS
            or omitted_groups > 0
            or evidence_truncated
            or values_truncated
            or any(
                details["evidence_truncated"]
                for parameter in context_parameters
                for details in parameter["unusable_values"].values()
            )
        ),
    }
    return context


def _validate_text(value: Any, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= maximum
        and _NUMERIC_CLAIM.search(value) is None
    )


def _subject_anchor(metric: str) -> str:
    anchors = {
        "profit_factor": "profit factor",
        "equity_drawdown_pct": "drawdown",
        "win_rate": "win rate",
    }
    return anchors.get(metric, " ".join(metric.split("_"))).casefold()


def _eligible_subject(context: dict[str, Any]) -> dict[str, Any] | None:
    """Select the first eligible finding in deterministic Autopsy order."""
    return next(iter(context["eligible_subjects"]), None)


def validate_interpretation(raw: Any, context: dict[str, Any]) -> Interpretation | None:
    """Validate brief prose and attach the Python-selected finding references."""
    if not isinstance(raw, dict) or set(raw) != set(OUTPUT_SCHEMA["required"]):
        return None

    observation = raw["observation"]
    question = raw["question"]
    limitation = raw["limitation"]
    if (
        not _validate_text(observation, maximum=350)
        or not _validate_text(question, maximum=300)
        or not _validate_text(limitation, maximum=300)
    ):
        return None

    subject = _eligible_subject(context)
    if subject is None:
        return None
    anchor = _subject_anchor(subject["metric"])
    if anchor not in observation.casefold() or anchor not in question.casefold():
        return None

    finding_id = subject["finding_id"]
    evidence_ids = subject["evidence_experiment_ids"]
    summary = subject.get("title")
    if not isinstance(summary, str) or not summary.strip():
        summary = f"Research finding for {subject['metric'].replace('_', ' ')}"

    return {
        "summary": summary.strip()[:600],
        "observations": [{
            "text": observation.strip(),
            "finding_ids": [finding_id],
            "evidence_experiment_ids": evidence_ids,
        }],
        "follow_up_questions": [{
            "question": question.strip(),
            "finding_ids": [finding_id],
            "evidence_experiment_ids": evidence_ids,
        }],
        "referenced_finding_ids": [finding_id],
        "limitations": [
            limitation.strip(),
            "This interpretation concerns only the selected deterministic finding.",
        ],
    }


def _prose_validation_diagnostics(raw: Any) -> list[str]:
    """Return bounded field/category codes only; never include model prose."""
    if not isinstance(raw, dict):
        return ["invalid_structure"]

    candidates: list[tuple[str, Any, int]] = [
    ("observation", raw.get("observation"), 350),
    ("question", raw.get("question"), 300),
    ("limitation", raw.get("limitation"), 300),
]

    diagnostics: list[str] = []
    for label, value, maximum in candidates:
        codes: list[str] = []
        if not isinstance(value, str):
            codes.append("invalid_type")
        else:
            if not value.strip():
                codes.append("empty")
            if len(value) > maximum:
                codes.append("length")
            if _NUMERIC_CLAIM.search(value):
                codes.append("numeric_claim")
        diagnostics.extend(f"{label}.{code}" for code in codes)
    return diagnostics[:10]


def _local_ollama_url() -> str | None:
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.query or parsed.fragment:
        return None
    try:
        parsed.port
    except ValueError:
        return None
    hostname = parsed.hostname.lower()
    try:
        is_local = hostname == "localhost" or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_local = False
    if not is_local:
        return None
    return f"{base_url}/api/generate"


def _configured_timeout() -> float | None:
    raw_timeout = os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        timeout = float(raw_timeout)
    except ValueError:
        return None
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        return None
    return timeout


def generate_interpretation(autopsy: dict[str, Any]) -> AIResult:
    """Call local Ollama and return a safe, validated AI result."""
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL).strip()
    url = _local_ollama_url()
    timeout = _configured_timeout()
    if not model or url is None or timeout is None:
        return {
            "status": "unavailable",
            "reason": "Local AI configuration is invalid or incomplete.",
        }

    context = build_gemma_context(autopsy)
    subject = _eligible_subject(context)
    if subject is None:
        return {
            "status": "unavailable",
            "reason": "No deterministic findings with evidence are available to interpret.",
        }
    model_context = {
        key: subject.get(key)
        for key in ("finding_id", "finding_type", "metric", "title", "description")
    }
    try:
        context_json = (
            json.dumps(model_context, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )
    except (TypeError, ValueError):
        return {
            "status": "unavailable",
            "reason": "The deterministic report could not be represented as bounded JSON.",
        }
    if len(context_json.encode("utf-8")) > MAX_CONTEXT_BYTES:
        return {
            "status": "unavailable",
            "reason": "The deterministic report is too large for the bounded local AI context.",
        }

    prompt = (
        "Interpret this one deterministic finding. Return JSON with exactly three short fields: "
        "observation, question, and limitation. Keep the interpretation cautious and qualitative. "
        "Do not include finding or experiment IDs; Python adds verified references.\n\n"
        "Selected finding:\n"
        f"<research_data>{context_json}</research_data>"
    )
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": OUTPUT_SCHEMA,
    }

    try:
        response = httpx.post(url, json=payload, timeout=timeout, trust_env=False)
    except httpx.TimeoutException:
        return {"status": "unavailable", "reason": "Local Ollama request timed out."}
    except httpx.RequestError:
        return {"status": "unavailable", "reason": "Local Ollama server is unavailable."}

    if response.status_code < 200 or response.status_code >= 300:
        return {
            "status": "unavailable",
            "reason": "Local Ollama returned an unsuccessful response; verify the configured model is available.",
        }
    if len(response.content) > MAX_HTTP_RESPONSE_BYTES:
        return {"status": "error", "reason": "Local Ollama response exceeded the allowed size."}

    try:
        response_payload = _strict_json_loads(response.content)
    except (RecursionError, json.JSONDecodeError, ValueError):
        return {"status": "error", "reason": "Local Ollama returned an invalid response."}
    if not isinstance(response_payload, dict):
        return {"status": "error", "reason": "Local Ollama returned an invalid response."}

    model_output = response_payload.get("response")
    if not isinstance(model_output, str) or len(model_output) > MAX_RESPONSE_CHARS:
        return {"status": "error", "reason": "Local model output was missing or exceeded the allowed size."}
    try:
        parsed_output = _strict_json_loads(model_output)
    except (RecursionError, ValueError):
        return {"status": "error", "reason": "Local model output was not valid JSON."}

    interpretation = validate_interpretation(parsed_output, context)
    if interpretation is not None:
        return {
            "status": "success",
            "model": model,
            "interpretation": interpretation,
            "context_truncated": context["context_truncated"],
        }

    diagnostics = _prose_validation_diagnostics(parsed_output) or ["schema_or_reference"]
    logger.warning("Gemma interpretation rejected by validator: %s", ", ".join(diagnostics))
    return {
        "status": "error",
        "reason": "Local model output did not match the allowed research interpretation schema.",
    }
