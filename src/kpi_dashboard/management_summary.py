from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
import os
import re
from typing import Any, Mapping, Protocol, Sequence

from .anomalies import Anomaly
from .kpis import KPISnapshot


MANAGEMENT_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "positive_changes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_attention": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "executive_summary",
        "positive_changes",
        "risks",
        "recommended_attention",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are writing a concise management summary from validated business metrics.
Use only the JSON facts supplied by the application. Do not calculate new KPIs, infer hidden causes,
or invent numbers. Any numeric value you mention must be copied exactly from the supplied JSON.
Treat anomaly messages as application-generated findings, not as proof of an underlying cause.
Keep the executive summary concise and make every bullet specific enough to be actionable for review.
If there is no supported positive change, return an empty positive_changes array.
"""

_NUMBER_RE = re.compile(r"(?<![\w-])-?\d[\d,]*(?:\.\d+)?")


class ManagementSummaryError(RuntimeError):
    """Raised when a management summary cannot be safely produced."""


class SummaryValidationError(ValueError):
    """Raised when model output fails local schema or grounding checks."""


class SummaryProvider(Protocol):
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ManagementSummary:
    executive_summary: str
    positive_changes: tuple[str, ...]
    risks: tuple[str, ...]
    recommended_attention: tuple[str, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ManagementSummary":
        expected = {
            "executive_summary",
            "positive_changes",
            "risks",
            "recommended_attention",
        }
        if set(payload) != expected:
            missing = sorted(expected - set(payload))
            extra = sorted(set(payload) - expected)
            raise SummaryValidationError(
                f"summary keys do not match schema; missing={missing}, extra={extra}"
            )

        executive_summary = payload["executive_summary"]
        if not isinstance(executive_summary, str) or not executive_summary.strip():
            raise SummaryValidationError("executive_summary must be a non-empty string")

        def validate_list(name: str) -> tuple[str, ...]:
            value = payload[name]
            if not isinstance(value, list):
                raise SummaryValidationError(f"{name} must be an array")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise SummaryValidationError(f"{name} must contain only non-empty strings")
            return tuple(item.strip() for item in value)

        return cls(
            executive_summary=executive_summary.strip(),
            positive_changes=validate_list("positive_changes"),
            risks=validate_list("risks"),
            recommended_attention=validate_list("recommended_attention"),
        )

    def to_dict(self) -> dict[str, str | list[str]]:
        payload = asdict(self)
        for key in ("positive_changes", "risks", "recommended_attention"):
            payload[key] = list(payload[key])
        return payload


class OpenAIResponsesProvider:
    """OpenAI Responses API adapter using strict JSON-schema Structured Outputs."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")
        if client is not None:
            self.client = client
            return

        try:
            from openai import OpenAI
        except (ImportError, AttributeError) as exc:  # pragma: no cover - environment-specific
            raise ManagementSummaryError(
                "OpenAI SDK is unavailable. Install dependencies with `pip install -r requirements.txt`."
            ) from exc

        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "management_summary",
                    "schema": dict(schema),
                    "strict": True,
                }
            },
        )
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise ManagementSummaryError("OpenAI response did not contain output text")
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ManagementSummaryError("OpenAI response was not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise ManagementSummaryError("OpenAI response JSON must be an object")
        return payload


def build_management_context(
    snapshot: KPISnapshot,
    anomalies: Sequence[Anomaly],
    *,
    department: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Build the only business facts that the LLM is allowed to see."""
    return {
        "scope": {
            "department": department or "All",
            "region": region or "All",
        },
        "validated_kpis": snapshot.to_dict(),
        "validated_anomalies": [item.to_dict() for item in anomalies],
    }


def _decimal(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(",", ""))
    except InvalidOperation:
        return None


def _numbers_in_value(value: Any) -> set[Decimal]:
    numbers: set[Decimal] = set()
    if isinstance(value, bool) or value is None:
        return numbers
    if isinstance(value, (int, float, Decimal)):
        parsed = _decimal(str(value))
        if parsed is not None:
            numbers.add(parsed)
        return numbers
    if isinstance(value, str):
        for token in _NUMBER_RE.findall(value):
            parsed = _decimal(token)
            if parsed is not None:
                numbers.add(parsed)
        return numbers
    if isinstance(value, Mapping):
        for item in value.values():
            numbers.update(_numbers_in_value(item))
        return numbers
    if isinstance(value, (list, tuple, set)):
        for item in value:
            numbers.update(_numbers_in_value(item))
    return numbers


def _summary_text(summary: ManagementSummary) -> str:
    return "\n".join(
        [
            summary.executive_summary,
            *summary.positive_changes,
            *summary.risks,
            *summary.recommended_attention,
        ]
    )


def validate_grounded_numbers(summary: ManagementSummary, context: Mapping[str, Any]) -> None:
    """Reject numeric claims that are absent from the application-supplied facts."""
    allowed = _numbers_in_value(context)
    claimed = {
        parsed
        for token in _NUMBER_RE.findall(_summary_text(summary))
        if (parsed := _decimal(token)) is not None
    }
    invented = sorted(claimed - allowed)
    if invented:
        rendered = ", ".join(str(value) for value in invented)
        raise SummaryValidationError(f"summary contains unsupported numeric value(s): {rendered}")


def generate_management_summary(
    snapshot: KPISnapshot,
    anomalies: Sequence[Anomaly],
    provider: SummaryProvider,
    *,
    department: str | None = None,
    region: str | None = None,
    max_attempts: int = 2,
) -> ManagementSummary:
    """Generate and locally validate a grounded management summary."""
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    context = build_management_context(
        snapshot,
        anomalies,
        department=department,
        region=region,
    )
    user_prompt = (
        "Write the management summary from this application-generated JSON only. "
        "Do not introduce any other facts or numbers.\n\n"
        + json.dumps(context, indent=2, sort_keys=True)
    )

    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            payload = provider.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=MANAGEMENT_SUMMARY_SCHEMA,
            )
            summary = ManagementSummary.from_mapping(payload)
            validate_grounded_numbers(summary, context)
            return summary
        except Exception as exc:  # provider and validation failures fail closed at this boundary
            last_error = exc

    raise ManagementSummaryError(
        f"management summary failed validation after {max_attempts} attempt(s)"
    ) from last_error
