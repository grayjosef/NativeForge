"""Persist Gate 176 signals (0062), idempotent by signal_id."""

from __future__ import annotations

import datetime as dt
from typing import Any

import sqlalchemy as sa

from nativeforge.services.early_funding_signal_service import signal_invariant_failures
from nativeforge.services.early_signal_repository_service import SIGNALS

SCHEMA_VERSION = "nf_early_signal_write_v1"


def upsert_signal(
    connection: sa.engine.Connection, *, signal: dict[str, Any]
) -> dict[str, Any]:
    failures = signal_invariant_failures(signal)
    if failures:
        return {"written": False, "failures": failures}

    now = dt.datetime.now(dt.UTC)
    row = {
        "signal_id": signal["signal_id"],
        "signal_type": signal["signal_type"],
        "signal_state": signal.get("signal_state"),
        "source_id": signal.get("source_id"),
        "program_key": signal.get("program_key"),
        "program_name": signal.get("program_name"),
        "funder_name": signal.get("funder_name"),
        "raw_payload_sha256": signal.get("raw_payload_sha256"),
        "document_ref": signal.get("document_ref"),
        "supporting_text": signal.get("supporting_text"),
        "possible_opportunity_number": signal.get("possible_opportunity_number"),
        "confidence_class": signal.get("confidence_class"),
        "ambiguity_class": signal.get("ambiguity_class"),
        "review_required": 1 if signal.get("review_required") else 0,
        "is_miss_evidence": 1 if signal.get("is_miss_evidence") else 0,
        "is_forward_looking": 1 if signal.get("is_forward_looking") else 0,
        "linked_canonical_id": signal.get("linked_canonical_id"),
        "linked_gap_id": signal.get("linked_gap_id"),
        "creates_opportunity": 0,
        "auto_onboarding_permitted": 0,
        "observed_at": signal.get("observed_at") or now,
        "model_version": signal.get("model_version"),
        "created_at": now,
    }

    cols = ", ".join(row.keys())
    vals = ", ".join(f":{k}" for k in row)
    connection.execute(
        sa.text(
            f"INSERT INTO {SIGNALS} ({cols}) VALUES ({vals}) "
            f"ON CONFLICT(signal_id) DO NOTHING"
        ),
        row,
    )
    return {"written": True, "signal_id": signal["signal_id"]}
