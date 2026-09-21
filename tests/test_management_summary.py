from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.anomalies import detect_anomalies
from kpi_dashboard.kpis import DateWindow, KPIEngine
from kpi_dashboard.management_summary import (
    MANAGEMENT_SUMMARY_SCHEMA,
    ManagementSummaryError,
    OpenAIResponsesProvider,
    build_management_context,
    generate_management_summary,
)


REPORTING_DB = ROOT / "data" / "processed" / "reporting.db"


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, *, system_prompt, user_prompt, schema):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema": schema,
            }
        )
        return self.responses.pop(0)


def latest_week():
    frames = KPIEngine(REPORTING_DB).load_frames()
    window = DateWindow(pd.Timestamp("2026-09-14"), pd.Timestamp("2026-09-20"))
    snapshot = KPIEngine(REPORTING_DB).snapshot(window)
    anomalies = detect_anomalies(frames, window, snapshot=snapshot)
    return snapshot, anomalies


def valid_response():
    return {
        "executive_summary": "Revenue changed -10.62% versus the previous period while delayed jobs reached 39.",
        "positive_changes": ["Northwest revenue is 73.7% above its scaled target."],
        "risks": ["Southwest revenue is 36.5% below its scaled target."],
        "recommended_attention": ["Review the 39 delayed jobs highlighted by the application."],
    }


def test_context_contains_only_validated_kpis_anomalies_and_scope():
    snapshot, anomalies = latest_week()

    context = build_management_context(snapshot, anomalies, department="Southwest", region="West")

    assert set(context) == {"scope", "validated_kpis", "validated_anomalies"}
    assert context["scope"] == {"department": "Southwest", "region": "West"}
    serialized = json.dumps(context)
    assert "opportunity_id" not in serialized
    assert "ticket_id" not in serialized
    assert "customer_name" not in serialized


def test_valid_grounded_summary_is_returned_and_prompt_contains_metrics():
    snapshot, anomalies = latest_week()
    provider = FakeProvider([valid_response()])

    summary = generate_management_summary(snapshot, anomalies, provider)

    assert summary.executive_summary.startswith("Revenue changed -10.62%")
    assert summary.risks == ("Southwest revenue is 36.5% below its scaled target.",)
    assert provider.calls[0]["schema"] == MANAGEMENT_SUMMARY_SCHEMA
    assert '"revenue_growth_pct": -10.62' in provider.calls[0]["user_prompt"]


def test_unsupported_numeric_claim_is_rejected_after_retries():
    snapshot, anomalies = latest_week()
    bad = valid_response()
    bad["risks"] = ["Revenue may decline by 99% next week."]
    provider = FakeProvider([bad, bad])

    with pytest.raises(ManagementSummaryError):
        generate_management_summary(snapshot, anomalies, provider, max_attempts=2)

    assert len(provider.calls) == 2


def test_schema_mismatch_is_retried_then_valid_response_succeeds():
    snapshot, anomalies = latest_week()
    invalid = valid_response() | {"invented_field": "nope"}
    provider = FakeProvider([invalid, valid_response()])

    summary = generate_management_summary(snapshot, anomalies, provider)

    assert summary.executive_summary
    assert len(provider.calls) == 2


def test_invalid_attempt_count_is_rejected():
    snapshot, anomalies = latest_week()

    with pytest.raises(ValueError):
        generate_management_summary(snapshot, anomalies, FakeProvider([]), max_attempts=0)


def test_openai_provider_uses_strict_json_schema_format():
    recorded = {}

    class FakeResponses:
        def create(self, **kwargs):
            recorded.update(kwargs)
            return SimpleNamespace(output_text=json.dumps(valid_response()))

    client = SimpleNamespace(responses=FakeResponses())
    provider = OpenAIResponsesProvider(model="test-model", client=client)

    payload = provider.generate(
        system_prompt="system",
        user_prompt="user",
        schema=MANAGEMENT_SUMMARY_SCHEMA,
    )

    assert payload["executive_summary"]
    assert recorded["model"] == "test-model"
    assert recorded["instructions"] == "system"
    assert recorded["input"] == "user"
    assert recorded["text"]["format"]["type"] == "json_schema"
    assert recorded["text"]["format"]["strict"] is True
    assert recorded["text"]["format"]["schema"] == MANAGEMENT_SUMMARY_SCHEMA
