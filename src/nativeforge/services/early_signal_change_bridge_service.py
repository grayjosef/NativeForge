"""Gate 170 → 176: change events as early-signal evidence (not duplicate narratives)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.early_funding_signal_service import (
    AMENDMENT_WITHOUT_ORIGINAL,
    DERIVED_FACT,
    OTHER_SIGNAL,
    PROGRAM_CYCLE_DEVIATION,
    build_signal,
    link_signal_to_opportunity,
    signal_invariant_failures,
)
from nativeforge.services.opportunity_change_read_model_service import (
    EVENTS,
    EXPLANATIONS,
)

SCHEMA_VERSION = "nf_early_signal_change_bridge_v1"

#: Gate 170 owns the change type; 176 names what it may signal operationally.
_CHANGE_TO_SIGNAL: dict[str, str] = {
    "DEADLINE_SHORTENED": OTHER_SIGNAL,
    "DEADLINE_EXTENDED": OTHER_SIGNAL,
    "DEADLINE_CHANGED": OTHER_SIGNAL,
    "AMENDMENT_PUBLISHED": AMENDMENT_WITHOUT_ORIGINAL,
    "FORECAST_TO_POSTED": OTHER_SIGNAL,
    "STATUS_CHANGED": OTHER_SIGNAL,
    "REOPENED": OTHER_SIGNAL,
    "CANCELLED": OTHER_SIGNAL,
    "PROGRAM_CYCLE_DEVIATION": PROGRAM_CYCLE_DEVIATION,
}


def propose_signal_from_change_event(
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Build a 176 signal from one Gate 170 row. Returns None if unsupported."""
    change_type = str(event.get("change_type") or "")
    signal_type = _CHANGE_TO_SIGNAL.get(change_type)
    if not signal_type:
        return None

    canonical_id = str(event.get("canonical_id") or "")
    source_id = str(event.get("source_id") or "canonical_change_graph")
    detail_key = str(event.get("change_event_id") or change_type)
    program_key = canonical_id or str(event.get("normalized_opportunity_number") or "")

    explanation = EXPLANATIONS.get(change_type, "A material change was observed.")
    supporting = (
        f"{explanation} prior={event.get('prior_value')!r} "
        f"new={event.get('new_value')!r}"
    )

    payload_sha = hashlib.sha256(
        json.dumps(event, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    signal = build_signal(
        signal_type=signal_type,
        source_id=source_id,
        detail_key=detail_key,
        program_key=program_key,
        funder_name=event.get("funder_name"),
        raw_payload_sha256=payload_sha,
        supporting_text=supporting,
        confidence_class=DERIVED_FACT,
        observed_at=event.get("detected_at"),
    )
    failures = signal_invariant_failures(signal)
    if failures:
        return None
    if canonical_id:
        linked = link_signal_to_opportunity(
            signal=signal,
            canonical_id=canonical_id,
            opportunity_exists=True,
        )
        if linked.get("accepted"):
            signal = linked["signal"]
    return signal


def project_recent_change_events_to_signals(
    connection: sa.engine.Connection,
    *,
    limit: int = 200,
) -> dict[str, Any]:
    """Idempotent projection: derived signal ids dedupe repeats."""
    from nativeforge.services.early_signal_write_service import upsert_signal

    rows = connection.execute(
        sa.text(
            f"SELECT e.*, c.funder_agency_name AS funder_name, "
            f"c.normalized_opportunity_number "
            f"FROM {EVENTS} e "
            f"LEFT JOIN nf_canonical_opportunities c "
            f"ON c.canonical_id = e.canonical_id "
            f"ORDER BY e.detected_at DESC, e.change_event_id LIMIT :lim"
        ),
        {"lim": int(limit)},
    ).mappings().all()

    inserted = 0
    skipped = 0
    for row in rows:
        signal = propose_signal_from_change_event(dict(row))
        if not signal:
            skipped += 1
            continue
        result = upsert_signal(connection, signal=signal)
        if result.get("written"):
            inserted += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "examined": len(rows),
        "signals_written": inserted,
        "skipped": skipped,
    }
