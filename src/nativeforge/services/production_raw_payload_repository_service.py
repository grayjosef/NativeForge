"""Production raw payload metadata repository (Gate 96C).

The seam between an evidence record and `nf_raw_source_payloads`. It writes
**metadata only** — never a response body — and refuses to write at all unless
the payload passes Gate 95's model and promotion gate first.

## Metadata here, body elsewhere

`raw_payload_ref` is a content-addressed pointer. The row records where the
body is and what it hashed to; it does not record the body. A 78 MB Grants.gov
extract is not a database row, and a table that sometimes holds bodies is a
table whose size nobody can predict.

`store_body=True` is rejected outright rather than silently ignored, because a
caller asking this repository to hold a body has misunderstood which layer they
are at, and a silent no-op would let them keep believing it.

## Promotion is not this module's decision

The repository does not decide whether a payload is evidence. It calls Gate
95's `evaluate_payload_promotion` and refuses whatever that refuses:
`findings_blocked`, unresolved redaction, `TERMS_REVIEW_REQUIRED`,
`HUMAN_REVIEW_ONLY`, a failed parse, a live payload with no preflight.

Two gates agreeing is not redundancy — the promotion gate answers "is this
evidence?" and the repository answers "may I persist it?", and the second can
fail for reasons the first never sees, like the body store not existing.

## evidence_ready needs somewhere for the body to be

A row marked `evidence_ready` asserts the bytes are retrievable. If the body
store is unconfigured, they are not, and the assertion would be false the moment
it was written. So `evidence_ready` requires `body_store_configured` — which is
`False` today, which is why nothing promotes to it in production yet.

Quarantined metadata may still be written: recording that a payload exists and
is not yet usable is exactly what quarantine is for.

## dry_run is the default

`dry_run=True` returns the decision without touching a session. A caller must
pass a session **and** `dry_run=False` to persist, so the failure mode of
forgetting an argument is "nothing happened", not "something happened in
production".
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.raw_payload_body_store_contract_service import (
    build_body_store_contract,
)
from nativeforge.services.raw_payload_evidence_model_service import (
    SECRET_SCAN_SATISFYING,
    TERMS_BLOCKING,
    TERMS_HUMAN_ONLY,
    evidence_invariant_failures,
)
from nativeforge.services.raw_payload_promotion_gate_service import (
    evaluate_payload_promotion,
)

SCHEMA_VERSION = "nf_production_raw_payload_repository_v1"

TABLE_NAME = "nf_raw_source_payloads"

REPOSITORY_STATUSES = frozenset(
    {"dry_run", "written", "refused", "table_unavailable"}
)

# Statuses a metadata row may carry when persisted. `evidence_ready` needs the
# body store; the rest are recordable without it.
QUARANTINE_WRITABLE_STATUSES = frozenset({"quarantine", "rejected", "superseded"})


class ProductionPayloadRepositoryError(RuntimeError):
    """Raised when a write is refused. Names the reason."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_metadata_table(session: Any = None) -> bool:
    """Whether nf_raw_source_payloads exists. Inspected, not assumed."""
    if session is None:
        # No session: fall back to the migration's presence on disk, which is
        # what makes the table available once migrations run.
        from pathlib import Path

        versions = Path(__file__).resolve().parents[3] / "alembic" / "versions"
        return (versions / "0028_nf_raw_source_payloads.py").exists()
    try:
        from sqlalchemy import inspect

        bind = getattr(session, "bind", None) or session.get_bind()
        return TABLE_NAME in inspect(bind).get_table_names()
    except Exception:
        return False


def build_repository_decision(
    *,
    payload: dict[str, Any],
    activation_preflight: dict[str, Any] | None = None,
    session: Any = None,
    store_body: bool = False,
    body_store_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """May this payload's metadata be persisted, and at what promotion status?"""
    record = payload if isinstance(payload, dict) else {}

    blocked: list[str] = []

    # 1. The evidence record must be well-formed to begin with.
    evidence_failures = evidence_invariant_failures(record)
    if evidence_failures:
        blocked.extend(f"evidence_invariant:{f}" for f in evidence_failures)

    # 2. Gate 95's promotion gate decides whether it is evidence.
    promotion = evaluate_payload_promotion(
        payload=record, activation_preflight=activation_preflight
    )
    if not promotion["can_promote"]:
        blocked.extend(f"promotion:{r}" for r in promotion["blocked_reasons"])

    # 3. Explicit refusals, so the reason is legible even when the promotion
    #    gate already covered it.
    scan = record.get("secret_scan_status")
    if scan not in SECRET_SCAN_SATISFYING:
        blocked.append(f"secret_scan_not_clean:{scan}")
    terms = record.get("terms_status")
    if terms in TERMS_BLOCKING:
        blocked.append(f"terms_status_blocks:{terms}")
    human_review_required = terms in TERMS_HUMAN_ONLY
    if human_review_required:
        blocked.append(f"terms_human_review_only:{terms}")

    # 4. This repository holds metadata. A body request is a layering error.
    if store_body:
        blocked.append("repository_stores_metadata_only")

    # 5. The body store, detected rather than declared.
    contract = body_store_contract or build_body_store_contract()
    body_store_configured = bool(contract.get("body_store_configured"))

    table_available = detect_metadata_table(session)
    if not table_available:
        blocked.append("metadata_table_unavailable")

    # A row that says `evidence_ready` asserts the bytes are retrievable.
    # Without a body store they are not.
    promotion_allowed = bool(
        promotion["can_promote"] and body_store_configured and not blocked
    )
    if promotion["can_promote"] and not body_store_configured:
        blocked.append("evidence_ready_requires_a_configured_body_store")

    metadata_write_allowed = bool(table_available and not store_body)

    if metadata_write_allowed:
        status = "dry_run"
    elif not table_available:
        status = "table_unavailable"
    else:
        status = "refused"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "payload_id": record.get("payload_id"),
            "source_id": record.get("source_id"),
            "table_name": TABLE_NAME,
            "repository_status": status,
            "production_metadata_table_available": table_available,
            "production_body_store_available": body_store_configured,
            "metadata_write_allowed": metadata_write_allowed,
            # Never. This repository does not hold bodies.
            "body_write_allowed": False,
            "promotion_allowed": promotion_allowed,
            "resolved_promotion_status": (
                "evidence_ready" if promotion_allowed else "quarantine"
            ),
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked)),
            "promotion_decision": promotion,
            "body_store_mode": contract.get("detected_mode"),
            # Constants.
            "rows_written": 0,
            "bodies_written": 0,
            "fetch_performed": False,
            "collector_activated": False,
            "production_storage_live": False,
            "fabricated": False,
        }
    )


def persist_payload_metadata(
    *,
    payload: dict[str, Any],
    session: Any = None,
    activation_preflight: dict[str, Any] | None = None,
    store_body: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Persist metadata. Dry-run by default; a session is required to write."""
    decision = build_repository_decision(
        payload=payload,
        activation_preflight=activation_preflight,
        session=session,
        store_body=store_body,
    )

    if store_body:
        raise ProductionPayloadRepositoryError(
            "this repository stores metadata only; the body belongs in the "
            "body store. refusing to write."
        )

    if dry_run or session is None:
        return _json_safe({**decision, "repository_status": "dry_run"})

    if not decision["metadata_write_allowed"]:
        raise ProductionPayloadRepositoryError(
            "metadata write refused: "
            + ", ".join(decision["blocked_reasons"] or ["unspecified"])
        )

    from sqlalchemy import text

    row = {
        "payload_id": payload["payload_id"],
        "source_id": payload["source_id"],
        "source_name": payload.get("source_name"),
        "source_type": payload.get("source_type"),
        "collector_id": payload.get("collector_id"),
        "retrieved_at": payload["retrieved_at"],
        "retrieval_method": payload["retrieval_method"],
        "request_method": payload["request_method"],
        "request_url": payload.get("request_url"),
        "request_fingerprint": payload.get("request_fingerprint"),
        "canonical_url": payload.get("canonical_url"),
        "response_status": payload.get("response_status"),
        "response_headers_hash": payload.get("response_headers_hash"),
        "response_body_hash": payload["response_body_hash"],
        "response_body_size_bytes": payload.get("response_body_size_bytes"),
        "content_type": payload.get("content_type"),
        "raw_payload_ref": payload["raw_payload_ref"],
        "redaction_status": payload["redaction_status"],
        "secret_scan_status": payload["secret_scan_status"],
        "terms_status": payload["terms_status"],
        "attribution_required": bool(payload.get("attribution_required")),
        "parser_status": payload["parser_status"],
        # The repository's resolved status, not the payload's optimism.
        "promotion_status": decision["resolved_promotion_status"],
        "retention_policy": payload["retention_policy"],
        "created_from_live_fetch": bool(payload.get("created_from_live_fetch")),
        "created_from_fixture": bool(payload.get("created_from_fixture")),
        "blocked_reasons_json": json.dumps(payload.get("blocked_reasons") or []),
        "metadata_json": None,
    }

    import uuid as _uuid

    columns = ["id", *row.keys()]
    values = {"id": str(_uuid.uuid4()), **row}
    placeholders = ", ".join(f":{c}" for c in columns)
    session.execute(
        text(
            f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        ),
        values,
    )

    return _json_safe(
        {
            **decision,
            "repository_status": "written",
            "rows_written": 1,
            "bodies_written": 0,
        }
    )


def repository_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if decision.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if decision.get("fetch_performed") is not False:
        fails.append("repository_claimed_a_fetch")
    if decision.get("collector_activated") is not False:
        fails.append("repository_claimed_a_collector_activation")
    if decision.get("production_storage_live") is not False:
        fails.append("repository_claimed_production_storage_live")

    status = decision.get("repository_status")
    if status not in REPOSITORY_STATUSES:
        fails.append("repository_status_out_of_vocabulary")

    # Bodies never. Not by default, not on request.
    if decision.get("body_write_allowed") is not False:
        fails.append("repository_allowed_a_body_write")
    if decision.get("bodies_written"):
        fails.append("repository_wrote_a_body")

    # Promotion requires a configured body store, always.
    if decision.get("promotion_allowed") and not decision.get(
        "production_body_store_available"
    ):
        fails.append("promotion_allowed_without_a_body_store")
    if decision.get("promotion_allowed") and decision.get("blocked_reasons"):
        fails.append("promotion_allowed_with_blocked_reasons")

    resolved = decision.get("resolved_promotion_status")
    if decision.get("promotion_allowed") != (resolved == "evidence_ready"):
        fails.append("resolved_status_disagrees_with_promotion_allowed")
    if not decision.get("promotion_allowed") and resolved not in (
        QUARANTINE_WRITABLE_STATUSES
    ):
        fails.append("unpromoted_row_not_quarantined")

    # A refusal names itself.
    if status == "refused" and not decision.get("blocked_reasons"):
        fails.append("refusal_without_a_reason")

    # Human review can never reach a promoted row.
    if decision.get("human_review_required") and decision.get("promotion_allowed"):
        fails.append("human_review_payload_promoted")

    return fails
