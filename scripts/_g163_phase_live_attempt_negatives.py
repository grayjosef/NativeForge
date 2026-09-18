"""Gate 163: an unauthorized live attempt must fail, for each way of being one.

The world-state conversion replaced `live_attempts == 0` with
`unauthorized_live_attempts == 0`. That is only a safety property if
"unauthorized" actually catches things, so each linkage is broken on its own
and must produce its own named failure.

The falsifiability control is the first case: the REAL recorded attempt must
classify as authorized. Without it, every failure below could be "the
classifier refuses everything".

Writes nothing. Classification reads recorded evidence; the negative rows are
dicts that never touch the database.
"""

from __future__ import annotations

import json
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_live_attempt_authorization_service import (  # noqa: E402
    classify_live_attempt,
    classify_live_attempts,
    live_attempt_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
AUTHORIZED = "nf-seed-2026-api-grants-gov-search2"

out: dict[str, object] = {}
detail: list[str] = []

session = SessionLocal()
try:
    # ---- the control: the REAL row must classify as authorized -------
    real = (
        session.execute(
            sa.text(
                "SELECT attempt_id, source_id, transport_kind, "
                "authorized_source_id, request_url_fingerprint, "
                "raw_payload_persisted, raw_payload_sha256, "
                "execution_proof_available "
                "FROM nf_source_collection_execution_attempts "
                "WHERE transport_kind = 'live'"
            )
        )
        .mappings()
        .first()
    )
    if real is None:
        out["the_real_live_attempt_exists"] = False
        detail.append("no live attempt row found; the control cannot run")
        print(json.dumps({**out, "detail": "; ".join(detail)}, sort_keys=True))
        raise SystemExit(0)

    out["the_real_live_attempt_exists"] = True
    genuine = dict(real)
    verdict = classify_live_attempt(genuine, connection=session, organization_id=DEMO)
    out["the_real_live_attempt_is_authorized"] = bool(verdict["authorized"])
    out["the_real_attempt_meets_every_linkage"] = not verdict["unmet_linkages"]
    out["real_attempt_unmet"] = verdict["unmet_linkages"]
    if not verdict["authorized"]:
        detail.append(f"the real attempt was refused: {verdict['unmet_linkages']}")

    # ---- one broken linkage at a time --------------------------------
    cases = (
        (
            "no_authorized_source_id",
            {**genuine, "authorized_source_id": None},
            "authorized_source_id_present",
        ),
        (
            "a_source_outside_the_authorized_set",
            {
                **genuine,
                "source_id": "nf-seed-2026-fed-001",
                "authorized_source_id": "nf-seed-2026-fed-001",
            },
            "source_is_in_the_authorized_set",
        ),
        (
            "a_source_that_disagrees_with_its_authorization",
            {**genuine, "source_id": "nf-seed-2026-fed-017"},
            "source_id_matches_authorization",
        ),
        (
            "a_request_to_a_different_authority",
            {**genuine, "request_url_fingerprint": "0" * 64},
            "request_authority_matches",
        ),
        (
            "a_proof_with_no_persisted_payload",
            {
                **genuine,
                "raw_payload_persisted": False,
                "execution_proof_available": True,
            },
            "proof_linkage_is_valid",
        ),
        (
            "a_proof_with_no_hash",
            {
                **genuine,
                "raw_payload_sha256": None,
                "execution_proof_available": True,
            },
            "proof_linkage_is_valid",
        ),
    )

    for label, row, expected_linkage in cases:
        result = classify_live_attempt(row, connection=session, organization_id=DEMO)
        refused = bool(result["unauthorized"])
        named = expected_linkage in result["unmet_linkages"]
        out[f"{label}_is_unauthorized"] = refused
        # The refusal must name THIS linkage. A refusal for the wrong reason is
        # not evidence that this linkage is checked.
        out[f"{label}_names_its_linkage"] = named
        if not refused:
            detail.append(f"{label} classified as AUTHORIZED")
        if not named:
            detail.append(
                f"{label} did not name {expected_linkage}: {result['unmet_linkages']}"
            )

    # ---- with no connection, nothing is verifiable -------------------
    blind = classify_live_attempt(genuine, connection=None)
    out["without_a_connection_nothing_is_authorized"] = bool(blind["unauthorized"])

    # ---- a hermetic row is not unauthorized --------------------------
    #
    # The distinction the whole conversion rests on: hermetic rows are not
    # live, so they are neither authorized nor unauthorized live attempts.
    hermetic = classify_live_attempt(
        {**genuine, "transport_kind": "hermetic"},
        connection=session,
        organization_id=DEMO,
    )
    out["a_hermetic_row_is_not_a_live_attempt"] = bool(not hermetic["is_live"])
    out["a_hermetic_row_is_not_unauthorized"] = bool(not hermetic["unauthorized"])

    # ---- the summary invariants ---------------------------------------
    clean = classify_live_attempts([genuine], connection=session, organization_id=DEMO)
    out["a_clean_summary_passes_its_invariants"] = not live_attempt_invariant_failures(
        clean
    )
    out["clean_summary"] = {
        key: clean[key]
        for key in (
            "live_attempts",
            "authorized_live_attempts",
            "unauthorized_live_attempts",
            "unsigned_live_attempts",
            "source_mismatch_live_attempts",
            "live_rows_outside_authorized_set",
        )
    }

    dirty = classify_live_attempts(
        [genuine, {**genuine, "authorized_source_id": None}],
        connection=session,
        organization_id=DEMO,
    )
    failures = live_attempt_invariant_failures(dirty)
    out["a_summary_with_an_unauthorized_row_fails"] = bool(failures)
    out["and_the_failure_names_the_counter"] = any(
        "unauthorized_live_attempts" in failure for failure in failures
    )
    out["and_it_carries_detail"] = bool(dirty["unauthorized_detail"])
    out["dirty_summary_failures"] = failures
finally:
    session.close()

for key in (
    "the_real_live_attempt_exists",
    "the_real_live_attempt_is_authorized",
    "the_real_attempt_meets_every_linkage",
    "no_authorized_source_id_is_unauthorized",
    "no_authorized_source_id_names_its_linkage",
    "a_source_outside_the_authorized_set_is_unauthorized",
    "a_source_outside_the_authorized_set_names_its_linkage",
    "a_source_that_disagrees_with_its_authorization_is_unauthorized",
    "a_source_that_disagrees_with_its_authorization_names_its_linkage",
    "a_request_to_a_different_authority_is_unauthorized",
    "a_request_to_a_different_authority_names_its_linkage",
    "a_proof_with_no_persisted_payload_is_unauthorized",
    "a_proof_with_no_persisted_payload_names_its_linkage",
    "a_proof_with_no_hash_is_unauthorized",
    "a_proof_with_no_hash_names_its_linkage",
    "without_a_connection_nothing_is_authorized",
    "a_hermetic_row_is_not_a_live_attempt",
    "a_hermetic_row_is_not_unauthorized",
    "a_clean_summary_passes_its_invariants",
    "a_summary_with_an_unauthorized_row_fails",
    "and_the_failure_names_the_counter",
    "and_it_carries_detail",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
