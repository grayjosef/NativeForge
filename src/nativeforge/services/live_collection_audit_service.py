"""One audit view of a live collection, composed from what is already recorded.

Gate 164B. Every field is read from an existing table: the registry row, the
decision records, the activation row, the raw payload, the execution attempt,
the robots evidence. Nothing here is a second copy.

## Why composition and not a ledger

An audit ledger written alongside the collection would be a SECOND account of
the same event, and two accounts can disagree. The one that disagreed would
not announce itself - it would simply be the one someone happened to read.

So this composes. If the payload row and the attempt row contradict each
other, that contradiction is the audit's output rather than something the
audit has already smoothed over.

## HTTP status is absent, not zero

The transport status was never captured (doc 849 section 12). It appears here
as `None` with `http_status_known: false`, beside the application-level
`errorcode` and `msg` which WERE recorded. Two different facts, reported
separately, and the absent one is not filled in.

## No secrets, no network

Reads recorded rows. The request URL is never stored - only its fingerprint -
so the audit reports the fingerprint and the registry's declared endpoint, and
lets a reader compare them.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_live_collection_audit_v1"

#: The sections a complete audit chain has. Named, so "complete" is a list a
#: reader can check rather than a boolean somebody computed.
AUDIT_SECTIONS: tuple[str, ...] = (
    "source",
    "authorization",
    "request",
    "response",
    "execution",
    "normalization",
)

NOT_IMPLIED: tuple[str, ...] = (
    "an audit view is not an authorization",
    "a complete chain is not a claim the response was correct",
    "an absent HTTP status is a gap in evidence, not a failed request",
    "this composes recorded rows; it is not a second ledger",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _row(connection: Any, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    import sqlalchemy as sa

    found = connection.execute(sa.text(sql), params).mappings().first()
    return None if found is None else dict(found)


def build_live_collection_audit(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
) -> dict[str, Any]:
    """Compose the audit for one collection job."""
    sections: dict[str, Any] = {}
    missing: list[str] = []

    if connection is None or not str(job_id or "").strip():
        return _result(sections={}, missing=list(AUDIT_SECTIONS))

    payload = _row(
        connection,
        "SELECT attempt_id, job_id, source_id, authorized_source_id, "
        "response_status, media_type, payload_size_bytes, payload_sha256, "
        "payload_status, body_storage_mode, source_url_fingerprint, "
        "response_header_metadata, received_at, collector_invoked, "
        "live_fetch_performed "
        "FROM nf_source_collection_raw_payloads WHERE job_id = :job",
        {"job": str(job_id)},
    )
    if payload is None:
        return _result(sections={}, missing=list(AUDIT_SECTIONS))

    source_id = str(payload["source_id"])

    # ---- source ------------------------------------------------------
    registry_row: dict[str, Any] = {}
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )

        registry_row = dict(load_registry_rows().get(source_id) or {})
    except Exception:  # noqa: BLE001
        registry_row = {}

    declared_url = str(registry_row.get("source_url") or "")
    host = declared_url.split("//", 1)[-1].split("/", 1)[0].lower()
    sections["source"] = {
        "source_id": source_id,
        "source_name": registry_row.get("source_name"),
        "host": host or None,
        "declared_endpoint": declared_url or None,
        "adapter_key": registry_row.get("adapter_key"),
    }
    if not (source_id and host):
        missing.append("source")

    # ---- authorization -----------------------------------------------
    decisions: list[dict[str, Any]] = []
    try:
        import sqlalchemy as sa

        decisions = [
            dict(r)
            for r in connection.execute(
                sa.text(
                    "SELECT decision_kind, decision, guard_status, reviewed_by, "
                    "reviewed_at, review_authority, evidence_ref "
                    "FROM nf_source_authorization_decisions "
                    "WHERE source_id = :s ORDER BY decision_kind"
                ),
                {"s": source_id},
            )
            .mappings()
            .all()
        ]
    except Exception:  # noqa: BLE001
        decisions = []

    activation = _row(
        connection,
        "SELECT activation_approved_by, activation_approved_at, "
        "activation_approval_artifact_id FROM nf_active_opportunity_sources "
        "WHERE source_id = :s",
        {"s": source_id},
    )
    by_kind = {str(d["decision_kind"]): d for d in decisions}
    sections["authorization"] = {
        "terms": by_kind.get("terms"),
        "human_review": by_kind.get("human_review"),
        "live_fetch_opt_in": by_kind.get("live_fetch"),
        "activation": activation,
        "reviewers": sorted(
            {str(d.get("reviewed_by")) for d in decisions if d.get("reviewed_by")}
        ),
    }
    if not (
        by_kind.get("terms")
        and by_kind.get("human_review")
        and by_kind.get("live_fetch")
        and activation
    ):
        missing.append("authorization")

    # ---- request -----------------------------------------------------
    attempt = _row(
        connection,
        "SELECT attempt_id, source_id, authorized_source_id, execution_status, "
        "transport_kind, transport_outcome, http_status, bytes_received, "
        "request_method, request_url_fingerprint, raw_payload_sha256, "
        "raw_payload_persisted, execution_proof_available, live_source_call "
        "FROM nf_source_collection_execution_attempts WHERE attempt_id = :a",
        {"a": str(payload["attempt_id"])},
    )

    fingerprint = str(payload["source_url_fingerprint"] or "")
    expected_fingerprint = None
    try:
        from nativeforge.services.source_raw_payload_persistence_service import (
            fingerprint_url,
        )

        expected_fingerprint = fingerprint_url(declared_url)
    except Exception:  # noqa: BLE001
        expected_fingerprint = None

    sections["request"] = {
        "method": None if attempt is None else attempt.get("request_method"),
        "authority": host or None,
        "path": declared_url.split(host, 1)[-1] if host and declared_url else None,
        "request_fingerprint": fingerprint or None,
        "fingerprint_matches_declared_endpoint": bool(
            fingerprint and expected_fingerprint and fingerprint == expected_fingerprint
        ),
        "warrant_kind": "source_collection",
        "bounded": True,
    }
    if not fingerprint:
        missing.append("request")

    # ---- response ----------------------------------------------------
    headers = payload.get("response_header_metadata")
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except Exception:  # noqa: BLE001
            headers = {"unparseable": True}

    sections["response"] = {
        "payload_id": payload["attempt_id"],
        "byte_count": payload["payload_size_bytes"],
        "sha256": payload["payload_sha256"],
        "media_type": payload["media_type"],
        "payload_status": payload["payload_status"],
        "storage_mode": payload["body_storage_mode"],
        "safe_response_metadata": headers,
        # Two separate facts. The transport status was never captured; the
        # application-level answer was. Neither is inferred from the other.
        "http_status": payload["response_status"],
        "http_status_known": payload["response_status"] is not None,
        "http_status_note": (
            None
            if payload["response_status"] is not None
            else "UNKNOWN / not captured - see doc 849 section 12. Not inferred."
        ),
    }
    if not payload["payload_sha256"]:
        missing.append("response")

    # ---- execution ---------------------------------------------------
    sections["execution"] = {
        "attempt_id": None if attempt is None else attempt.get("attempt_id"),
        "authorized_source_id": None
        if attempt is None
        else attempt.get("authorized_source_id"),
        "transport_kind": None if attempt is None else attempt.get("transport_kind"),
        "live_source_call": None
        if attempt is None
        else bool(attempt.get("live_source_call")),
        "execution_proof_available": None
        if attempt is None
        else bool(attempt.get("execution_proof_available")),
        "proof_hash_matches_payload": bool(
            attempt is not None
            and attempt.get("raw_payload_sha256") == payload["payload_sha256"]
        ),
    }
    if attempt is None or not attempt.get("execution_proof_available"):
        missing.append("execution")

    # ---- normalization ------------------------------------------------
    #
    # Derived from the stored bytes at read time rather than stored again.
    normalized: dict[str, Any] | None = None
    try:
        from nativeforge.services.source_raw_payload_replay_service import (
            replay_payload,
        )

        replay = replay_payload(
            connection=connection,
            organization_id=organization_id,
            attempt_id=str(payload["attempt_id"]),
        )
        if replay.get("hash_verified") and replay.get("body_base64"):
            import base64

            body = base64.b64decode(replay["body_base64"])
            parsed = json.loads(body.decode("utf-8"))
            hits = list((parsed.get("data") or {}).get("oppHits") or [])
            first = hits[0] if hits else {}
            normalized = {
                "source_opportunity_id": first.get("id"),
                "opportunity_number": first.get("number"),
                "title": first.get("title"),
                "agency_code": first.get("agencyCode"),
                "open_date": first.get("openDate"),
                "close_date": first.get("closeDate"),
                "raw_payload_reference": payload["payload_sha256"],
                "derived_from": "the stored bytes, re-verified by hash at read time",
                "application_errorcode": parsed.get("errorcode"),
                "application_message": parsed.get("msg"),
            }
    except Exception:  # noqa: BLE001
        normalized = None

    sections["normalization"] = normalized
    if not normalized:
        missing.append("normalization")

    return _result(sections=sections, missing=missing)


def _result(*, sections: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    unique_missing = sorted(set(missing))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "audit_sections": list(AUDIT_SECTIONS),
            "sections": sections,
            "missing_sections": unique_missing,
            "audit_chain_complete": not unique_missing,
            "is_a_second_ledger": False,
            "composed_from": (
                "the registry row, the decision records, the activation row, "
                "the raw payload, the execution attempt, and the stored bytes"
            ),
            "not_implied": list(NOT_IMPLIED),
        }
    )


def audit_invariant_failures(audit: dict[str, Any]) -> list[str]:
    """Refuse an audit that contradicts itself or overclaims."""
    fails: list[str] = []

    if audit.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if audit.get("is_a_second_ledger") is not False:
        fails.append("the_audit_became_a_ledger")

    complete = bool(audit.get("audit_chain_complete"))
    missing = list(audit.get("missing_sections") or [])
    if complete and missing:
        fails.append(f"complete_alongside_missing_sections:{missing}")
    if not complete and not missing:
        fails.append("incomplete_without_naming_a_section")

    sections = audit.get("sections") or {}
    if complete and set(sections) != set(AUDIT_SECTIONS):
        fails.append("sections_do_not_match_the_declared_set")

    response = sections.get("response") or {}
    # The known gap must be REPORTED, not silently absent and not invented.
    if "http_status" in response:
        known = response.get("http_status_known")
        if response.get("http_status") is None and known is not False:
            fails.append("an_absent_http_status_was_not_marked_unknown")
        if response.get("http_status") is not None and known is not True:
            fails.append("a_present_http_status_was_marked_unknown")
        if response.get("http_status") is None and not response.get("http_status_note"):
            fails.append("an_absent_http_status_was_not_explained")

    execution = sections.get("execution") or {}
    if execution.get("execution_proof_available") and not execution.get(
        "proof_hash_matches_payload"
    ):
        fails.append("a_proof_that_does_not_match_the_payload_it_names")

    return sorted(set(fails))
