"""Gate 164G/164H/164I: health, customer provenance, and the no-network proof.

Runs with sockets denied for the whole phase, so "no network" is a property of
what happened rather than a reading of the code.

The health lane takes `replay_without_network` and `fresh_connection_replay`
as SUPPLIED evidence, so this phase performs them here and hands the results
over - the lane must not grade work it did itself.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
JOB = "gate163-first-live-collection"

out: dict[str, object] = {}
detail: list[str] = []

network_attempts = {"count": 0}
_REAL_SOCKET = socket.socket


def _refuse(*args, **kwargs):  # noqa: ANN002, ANN003
    network_attempts["count"] += 1
    raise RuntimeError("a socket was attempted during the Gate 164 health phase")


socket.socket = _refuse  # type: ignore[assignment]

try:
    from nativeforge.db.session import SessionLocal, engine
    from nativeforge.repositories.source_collection_execution_attempt_repository import (  # noqa: E501
        count_attempts,
    )
    from nativeforge.repositories.source_collection_raw_payload_repository import (
        count_payloads,
    )
    from nativeforge.services.canonical_artifact_build_context_service import (
        canonical_build,
        in_canonical_build,
    )
    from nativeforge.services.live_collection_audit_service import (
        audit_invariant_failures,
        build_live_collection_audit,
    )
    from nativeforge.services.live_collection_customer_provenance_service import (
        build_customer_provenance,
        provenance_invariant_failures,
    )
    from nativeforge.services.live_evidence_health_service import (
        build_live_evidence_health,
        live_evidence_health_invariant_failures,
    )
    from nativeforge.services.source_raw_payload_replay_service import replay_payload

    # ---- the fresh-connection replay, performed HERE -------------------
    opening = SessionLocal()
    attempt_id = opening.execute(
        sa.text(
            "SELECT attempt_id FROM nf_source_collection_raw_payloads WHERE job_id = :j"
        ),
        {"j": JOB},
    ).scalar()
    received_at = opening.execute(
        sa.text(
            "SELECT received_at FROM nf_source_collection_raw_payloads "
            "WHERE job_id = :j"
        ),
        {"j": JOB},
    ).scalar()
    opening.close()
    engine.dispose()

    fresh = SessionLocal()
    try:
        replay = replay_payload(
            connection=fresh, organization_id=DEMO, attempt_id=str(attempt_id)
        )
        body = base64.b64decode(replay.get("body_base64") or b"")
        replay_ok = bool(
            replay.get("hash_verified")
            and hashlib.sha256(body).hexdigest() == replay.get("payload_sha256")
        )

        audit = build_live_collection_audit(
            connection=fresh, organization_id=DEMO, job_id=JOB
        )
        detail.extend(audit_invariant_failures(audit))

        attempts = count_attempts(connection=fresh, organization_id=DEMO)
        payloads = count_payloads(connection=fresh, organization_id=DEMO)
    finally:
        fresh.close()

    # ---- canonical artifact generation, inside the boundary -----------
    with canonical_build(reason="gate164 health evidence") as context:
        hermetic = in_canonical_build() and context["ambient_secret_state"] == (
            "refused"
        )
    out["canonical_artifact_generation_hermetic"] = bool(hermetic)

    # ---- health -------------------------------------------------------
    health = build_live_evidence_health(
        audit=audit,
        replay_without_network=network_attempts["count"] == 0 and replay_ok,
        fresh_connection_replay=replay_ok,
        canonical_artifact_generation_hermetic=hermetic,
        unauthorized_live_attempts=attempts.get("unauthorized_live_attempts"),
        unauthorized_live_rows=payloads.get("unauthorized_live_rows"),
    )
    health_failures = live_evidence_health_invariant_failures(health)
    detail.extend(health_failures)

    out["health_status"] = health["health_status"]
    out["health_is_healthy_with_known_gap"] = (
        health["health_status"] == "healthy_with_known_evidence_gap"
    )
    out["known_evidence_gaps"] = health["known_evidence_gaps"]
    out["the_gap_is_named"] = health["known_evidence_gaps"] == [
        "http_status_not_captured"
    ]
    out["health_unmet_conditions"] = health["unmet_conditions"]
    out["no_unmet_health_conditions"] = not health["unmet_conditions"]
    out["health_invariants_clean"] = not health_failures

    # A gap must not be collapsible into plain healthy.
    fabricated = {**health, "health_status": "healthy"}
    out["a_gap_cannot_be_reported_as_plain_healthy"] = bool(
        "plain_healthy_while_carrying_gaps"
        in " ".join(live_evidence_health_invariant_failures(fabricated))
    )
    # Nor claimed without naming one.
    empty_gap = {**health, "known_evidence_gaps": []}
    out["a_gap_status_must_name_a_gap"] = bool(
        "claimed_a_known_gap_without_naming_one"
        in live_evidence_health_invariant_failures(empty_gap)
    )

    # ---- customer provenance -------------------------------------------
    provenance = build_customer_provenance(audit=audit, retrieved_at=received_at)
    provenance_failures = provenance_invariant_failures(provenance)
    detail.extend(provenance_failures)

    out["customer_provenance_safe"] = not provenance_failures
    out["provenance_fields"] = sorted(provenance["provenance"])
    out["provenance_carries_the_attribution_notice"] = bool(
        provenance["provenance"].get("attribution_notice")
    )
    out["provenance_names_the_authority"] = bool(
        provenance["provenance"].get("source_authority")
    )
    out["provenance_says_it_was_normalized_from_source_evidence"] = bool(
        provenance["provenance"].get("normalized_from_source_evidence")
    )

    # The negative proof: an internal field smuggled in must be refused.
    leaky = json.loads(json.dumps(provenance))
    leaky["provenance"]["reviewed_by"] = "MAYHEM"
    out["an_internal_field_in_the_dto_is_refused"] = bool(
        provenance_invariant_failures(leaky)
    )

    # And the serialized DTO carries no internal marker at all.
    serialized = json.dumps(provenance).lower()
    from nativeforge.services.live_collection_customer_provenance_service import (
        BLOCKED_FIELD_MARKERS,
    )

    present = sorted(m for m in BLOCKED_FIELD_MARKERS if m.lower() in serialized)
    out["no_internal_marker_in_the_customer_dto"] = not present
    if present:
        detail.append(f"internal markers present: {present}")

    out["unauthorized_live_attempts"] = attempts.get("unauthorized_live_attempts")
    out["unauthorized_live_rows"] = payloads.get("unauthorized_live_rows")
    out["live_attempts"] = attempts.get("live_attempts")
    out["authorized_live_attempts"] = attempts.get("authorized_live_attempts")
except Exception as exc:  # noqa: BLE001
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
finally:
    socket.socket = _REAL_SOCKET  # type: ignore[assignment]

out["network_requests_during_this_phase"] = network_attempts["count"]
out["no_network_during_health_and_provenance"] = network_attempts["count"] == 0

for key in (
    "canonical_artifact_generation_hermetic",
    "health_is_healthy_with_known_gap",
    "the_gap_is_named",
    "no_unmet_health_conditions",
    "health_invariants_clean",
    "a_gap_cannot_be_reported_as_plain_healthy",
    "a_gap_status_must_name_a_gap",
    "customer_provenance_safe",
    "provenance_carries_the_attribution_notice",
    "provenance_names_the_authority",
    "provenance_says_it_was_normalized_from_source_evidence",
    "an_internal_field_in_the_dto_is_refused",
    "no_internal_marker_in_the_customer_dto",
    "no_network_during_health_and_provenance",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
