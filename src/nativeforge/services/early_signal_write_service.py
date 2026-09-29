"""Persist Gate 176 signals (0062), idempotent by signal_id."""

from __future__ import annotations

import datetime as dt
from typing import Any

import sqlalchemy as sa

from nativeforge.services.early_funding_signal_service import signal_invariant_failures
from nativeforge.services.early_signal_repository_service import SIGNALS
from nativeforge.services.intelligence_sql_dialect_service import sql_bool_param

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
        "review_required": sql_bool_param(
            connection, value=bool(signal.get("review_required"))
        ),
        "is_miss_evidence": sql_bool_param(
            connection, value=bool(signal.get("is_miss_evidence"))
        ),
        "is_forward_looking": sql_bool_param(
            connection, value=bool(signal.get("is_forward_looking"))
        ),
        "linked_canonical_id": signal.get("linked_canonical_id"),
        "linked_gap_id": signal.get("linked_gap_id"),
        "creates_opportunity": sql_bool_param(connection, value=False),
        "auto_onboarding_permitted": sql_bool_param(connection, value=False),
        "observed_at": signal.get("observed_at") or now,
        "model_version": signal.get("model_version"),
        "created_at": now,
    }

    cols = ", ".join(row.keys())
    vals = ", ".join(f":{k}" for k in row)
    result = connection.execute(
        sa.text(
            f"INSERT INTO {SIGNALS} ({cols}) VALUES ({vals}) "
            f"ON CONFLICT(signal_id) DO NOTHING"
        ),
        row,
    )
    inserted = bool(getattr(result, "rowcount", 0))
    return {
        "written": inserted,
        "unchanged": not inserted,
        "signal_id": signal["signal_id"],
    }
