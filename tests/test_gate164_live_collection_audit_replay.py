"""Gate 164: the audit, health, provenance and build-context services.

Hermetic. No network, no database: every case here exercises the pure logic
with supplied structures. The parts that need real rows are proven by
`scripts/verify_nativeforge_live_collection_audit_replay.sh` against the
recorded Gate 163 collection, which is where an end-to-end replay belongs.
"""

from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from nativeforge.services.canonical_artifact_build_context_service import (
    CANONICAL,
    ENVIRONMENT_SCOPED,
    AmbientStateRefused,
    build_context_invariant_failures,
    canonical_build,
    describe_scope,
    environment_scoped_build,
    in_canonical_build,
)
from nativeforge.services.live_collection_audit_service import (
    AUDIT_SECTIONS,
    audit_invariant_failures,
    build_live_collection_audit,
)
from nativeforge.services.live_collection_customer_provenance_service import (
    BLOCKED_FIELD_MARKERS,
    CUSTOMER_VISIBLE_FIELDS,
    build_customer_provenance,
    provenance_invariant_failures,
)
from nativeforge.services.live_evidence_health_service import (
    CONDITIONS,
    HEALTHY,
    HEALTHY_WITH_GAP,
    build_live_evidence_health,
    live_evidence_health_invariant_failures,
)


def _complete_audit() -> dict:
    """An audit view with every section populated and the known gap present."""
    return {
        "schema_version": "nf_live_collection_audit_v1",
        "audit_chain_complete": True,
        "missing_sections": [],
        "is_a_second_ledger": False,
        "sections": {
            "source": {
                "source_id": "nf-seed-2026-api-grants-gov-search2",
                "source_name": "Grants.gov Search2 API",
                "host": "api.grants.gov",
                "declared_endpoint": "https://api.grants.gov/v1/api/search2",
            },
            "authorization": {
                "terms": {"guard_status": "ATTRIBUTION_REQUIRED"},
                "human_review": {"decision": "approved"},
                "live_fetch_opt_in": {"decision": "approved"},
                "activation": {"activation_approved_by": "MAYHEM"},
            },
            "request": {
                "request_fingerprint": "a" * 64,
                "fingerprint_matches_declared_endpoint": True,
                "method": "POST",
            },
            "response": {
                "payload_id": "b" * 64,
                "sha256": "c" * 64,
                "http_status": None,
                "http_status_known": False,
                "http_status_note": "UNKNOWN / not captured. Not inferred.",
            },
            "execution": {
                "attempt_id": "b" * 64,
                "authorized_source_id": "nf-seed-2026-api-grants-gov-search2",
                "execution_proof_available": True,
                "proof_hash_matches_payload": True,
            },
            "normalization": {
                "opportunity_number": "O-BJA-2026-172662",
                "title": "Coordinated Tribal Assistance Solicitation",
                "agency_code": "USDOJ-OJP-BJA",
                "source_opportunity_id": "363308",
                "raw_payload_reference": "c" * 64,
            },
        },
    }


# ----------------------------------------------------- the build context


def test_canonical_is_not_the_default():
    """Nothing existing changes behaviour until a caller asks for it."""
    assert in_canonical_build() is False


def test_a_canonical_build_refuses_ambient_auth_state():
    from nativeforge.lib.settings import auth_environment_presence

    with pytest.raises(AmbientStateRefused) as raised:
        with canonical_build(reason="test"):
            auth_environment_presence()
    # The refusal names the reader; "something ambient" is not actionable.
    assert raised.value.reader == "settings.auth_environment_overlay"


def test_an_explicit_environ_is_an_input_not_an_ambient_read():
    from nativeforge.lib.settings import auth_environment_presence

    with canonical_build(reason="test"):
        supplied = auth_environment_presence({"OIDC_ISSUER": "supplied"})
    assert supplied["OIDC_ISSUER"] is True


def test_an_exception_restores_the_prior_state():
    with pytest.raises(RuntimeError):
        with canonical_build(reason="test"):
            raise RuntimeError("boom")
    assert in_canonical_build() is False


def test_nesting_restores_to_the_enclosing_state_not_the_default():
    with canonical_build(reason="outer"):
        assert in_canonical_build() is True
        with environment_scoped_build(reason="inner"):
            assert in_canonical_build() is False
        # Restored to the ENCLOSING canonical build, not to the default.
        assert in_canonical_build() is True
    assert in_canonical_build() is False


def test_a_reused_pooled_worker_does_not_inherit_the_flag():
    """The specific failure `threading.local()` would have produced.

    Every FastAPI endpoint in this app is `def`, so Starlette runs them in a
    worker threadpool whose threads are reused between requests.
    """
    with ThreadPoolExecutor(max_workers=1) as pool:

        def enter_and_leave() -> int:
            with canonical_build(reason="request 1"):
                pass
            return threading.get_ident()

        def look() -> tuple[bool, int]:
            return in_canonical_build(), threading.get_ident()

        first = pool.submit(enter_and_leave).result(timeout=10)
        seen, second = pool.submit(look).result(timeout=10)

    assert first == second, "the pool did not reuse the worker"
    assert seen is False


def test_concurrent_asyncio_tasks_do_not_share_the_context():
    async def canonical_task() -> bool:
        with canonical_build(reason="task A"):
            await asyncio.sleep(0.02)
            return in_canonical_build()

    async def plain_task() -> bool:
        await asyncio.sleep(0.01)
        return in_canonical_build()

    async def both() -> tuple[bool, bool]:
        return await asyncio.gather(canonical_task(), plain_task())

    canonical, plain = asyncio.run(both())
    assert canonical is True
    assert plain is False


def test_a_context_that_claims_canonical_while_permitting_is_refused():
    assert build_context_invariant_failures(
        {
            "schema_version": "nf_canonical_artifact_build_context_v1",
            "scope": CANONICAL,
            "ambient_secret_state": "permitted",
        }
    )


def test_describe_scope_says_which_kind_it_is():
    assert describe_scope(CANONICAL)["identical_on_every_machine"] is True
    assert describe_scope(ENVIRONMENT_SCOPED)["reads_ambient_secret_state"] is True


# ------------------------------------------------------------ the audit


def test_an_audit_with_no_connection_reports_every_section_missing():
    audit = build_live_collection_audit(connection=None, job_id="anything")
    assert audit["audit_chain_complete"] is False
    assert sorted(audit["missing_sections"]) == sorted(AUDIT_SECTIONS)


def test_a_complete_audit_passes_its_invariants():
    assert audit_invariant_failures(_complete_audit()) == []


def test_a_backfilled_http_status_is_refused():
    """200 because the body said errorcode 0 is a transport fact nobody has."""
    audit = _complete_audit()
    audit["sections"]["response"]["http_status"] = 200
    assert "a_present_http_status_was_marked_unknown" in audit_invariant_failures(audit)


def test_an_absent_status_must_be_explained():
    audit = _complete_audit()
    audit["sections"]["response"].pop("http_status_note")
    assert "an_absent_http_status_was_not_explained" in audit_invariant_failures(audit)


def test_a_proof_that_names_other_bytes_is_refused():
    audit = _complete_audit()
    audit["sections"]["execution"]["proof_hash_matches_payload"] = False
    assert (
        "a_proof_that_does_not_match_the_payload_it_names"
        in audit_invariant_failures(audit)
    )


def test_complete_and_missing_must_agree():
    audit = _complete_audit()
    audit["missing_sections"] = ["execution"]
    assert any(
        f.startswith("complete_alongside_missing_sections")
        for f in audit_invariant_failures(audit)
    )


# ----------------------------------------------------------- the health


def _healthy_inputs() -> dict:
    return {
        "audit": _complete_audit(),
        "replay_without_network": True,
        "fresh_connection_replay": True,
        "canonical_artifact_generation_hermetic": True,
        "unauthorized_live_attempts": 0,
        "unauthorized_live_rows": 0,
    }


def test_the_known_gap_is_healthy_with_a_named_gap():
    health = build_live_evidence_health(**_healthy_inputs())
    assert health["health_status"] == HEALTHY_WITH_GAP
    assert health["known_evidence_gaps"] == ["http_status_not_captured"]
    assert health["unmet_conditions"] == []
    assert live_evidence_health_invariant_failures(health) == []


def test_a_gap_cannot_be_reported_as_plain_healthy():
    health = build_live_evidence_health(**_healthy_inputs())
    collapsed = {**health, "health_status": HEALTHY}
    assert any(
        f.startswith("plain_healthy_while_carrying_gaps")
        for f in live_evidence_health_invariant_failures(collapsed)
    )


def test_a_gap_status_must_name_a_gap():
    health = build_live_evidence_health(**_healthy_inputs())
    unnamed = {**health, "known_evidence_gaps": []}
    assert (
        "claimed_a_known_gap_without_naming_one"
        in live_evidence_health_invariant_failures(unnamed)
    )


def test_unsupplied_measurements_are_not_a_pass():
    """Absent evidence must not read as satisfied."""
    inputs = _healthy_inputs()
    inputs["replay_without_network"] = None
    inputs["fresh_connection_replay"] = None
    health = build_live_evidence_health(**inputs)
    assert "replay_without_network" in health["unmet_conditions"]
    assert health["health_status"] == "unreplayable"


def test_an_unauthorized_live_row_outranks_a_gap():
    inputs = _healthy_inputs()
    inputs["unauthorized_live_rows"] = 1
    health = build_live_evidence_health(**inputs)
    assert health["health_status"] == "unauthorized"


def test_corruption_outranks_everything():
    inputs = _healthy_inputs()
    inputs["audit"]["sections"]["execution"]["authorized_source_id"] = "someone-else"
    health = build_live_evidence_health(**inputs)
    assert health["health_status"] == "corrupt"


def test_every_declared_condition_is_measured():
    health = build_live_evidence_health(**_healthy_inputs())
    assert set(health["conditions"]) == set(CONDITIONS)


# ------------------------------------------------------- the provenance


def test_customer_provenance_is_built_from_the_allowlist():
    dto = build_customer_provenance(
        audit=_complete_audit(), retrieved_at="2026-09-18T15:22:52Z"
    )
    assert set(dto["provenance"]) == set(CUSTOMER_VISIBLE_FIELDS)
    assert provenance_invariant_failures(dto) == []


def test_no_internal_marker_reaches_the_customer_dto():
    dto = build_customer_provenance(audit=_complete_audit(), retrieved_at="x")
    serialized = json.dumps(dto).lower()
    leaked = [m for m in BLOCKED_FIELD_MARKERS if m.lower() in serialized]
    assert leaked == []


def test_an_internal_field_smuggled_into_the_dto_is_refused():
    dto = build_customer_provenance(audit=_complete_audit(), retrieved_at="x")
    dto["provenance"]["reviewed_by"] = "MAYHEM"
    assert provenance_invariant_failures(dto)


def test_attribution_is_required_and_carried():
    dto = build_customer_provenance(audit=_complete_audit(), retrieved_at="x")
    assert dto["attribution_required"] is True
    assert dto["provenance"]["attribution_notice"]
    assert dto["provenance"]["attribution_satisfied"] is True


def test_a_missing_notice_fails_when_attribution_is_required():
    dto = build_customer_provenance(audit=_complete_audit(), retrieved_at="x")
    dto["provenance"]["attribution_notice"] = None
    assert (
        "attribution_is_required_and_the_notice_is_absent"
        in provenance_invariant_failures(dto)
    )
