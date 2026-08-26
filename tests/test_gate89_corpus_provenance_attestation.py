"""Gate 89E - corpus provenance attestation.

An attestation is a human statement, and the failure mode this campaign keeps
finding is not dishonesty - it is optimism recorded as fact. `real_fetch: true`,
`never_synthesized: true` and a commit message reading "40 real ingested grants"
were all written in good faith and all turned out to mean less than they
appeared to.

So the tests here hold a statement to the same standard as a flag: it verifies
records only by naming transport that exists, it cannot overturn committed
evidence, and it cannot create a runtime fact about a system by describing the
past.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nativeforge.services.corpus_provenance_attestation_service import (
    ATTESTATION_STATUSES,
    COLLECTION_METHODS,
    CORE_FIELDS,
    RECORDING_METHODS,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    UPGRADE_PERMITTING_STATUSES,
    attestation_invariant_failures,
    build_attestation_contract,
    validate_corpus_provenance_attestation,
)
from nativeforge.services.discovery_baseline_x_service import (
    CIRCULAR_TRANSPORT_FILE,
    INDEPENDENT_TRANSPORT_FILE,
    build_discovery_baseline_x,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# What the repository already knows, as the validator expects to receive it.
COMMITTED_EVIDENCE = {
    "circular_artifact_paths": [CIRCULAR_TRANSPORT_FILE],
    "artifact_backed_record_ids": ["nf14-mixed-broad-01"],
    "suspected_placeholder_record_ids": ["nf13-real-fed-001", "nf13-real-fed-002"],
}


def _complete(**overrides) -> dict:
    """An attestation that satisfies every requirement."""
    base = {
        "attestation_id": "att-001",
        "attested_at": "2026-08-26T00:00:00Z",
        "attested_by": "corpus author",
        "attestation_scope": "nf14 batch",
        "corpus_files": ["fixtures/real_grants_corpus/nf14_mixed_corpus.json"],
        "record_id_ranges": ["nf14-mixed-broad-01..17"],
        "source_systems": ["api.grants.gov"],
        "collection_method": "live_fetch",
        "collection_window": "2026-05-19",
        "raw_transport_available": True,
        "raw_transport_artifact_paths": [INDEPENDENT_TRANSPORT_FILE],
        "source_terms_reviewed": True,
        "source_terms_status": "reviewed_cleared",
        "live_fetch_performed": True,
        "fetch_tool_or_script": "tier1 batch orchestrator",
        "field_mapping_summary": "search_hit + fetch_detail -> row",
        "deadline_source": "synopsis.responseDate",
        "eligibility_source": "synopsis.applicantEligibilityDesc",
        "provenance_limitations": ["only the broad and edge segments were pulled"],
        "known_placeholders": [],
        "known_circular_sources": [CIRCULAR_TRANSPORT_FILE],
        "records_to_exclude_from_verified": [],
        "records_allowed_for_verified_upgrade": ["nf14-mixed-broad-01"],
        "human_statement": "Pulled on 2026-05-19 with the batch orchestrator.",
    }
    base.update(overrides)
    return base


def _validate(attestation, evidence=COMMITTED_EVIDENCE) -> dict:
    return validate_corpus_provenance_attestation(
        attestation=attestation, committed_evidence=evidence
    )


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------


def test_complete_attestation_validates_and_permits_upgrade() -> None:
    result = _validate(_complete())
    assert result["attestation_status"] == "valid_complete_attestation"
    assert result["permits_verified_upgrade"] is True
    assert result["records_eligible_for_upgrade"] == ["nf14-mixed-broad-01"]
    assert result["raw_transport_paths"] == [INDEPENDENT_TRANSPORT_FILE]
    assert result["missing_fields"] == []
    assert attestation_invariant_failures(result) == []


def test_complete_attestation_still_creates_no_runtime_facts() -> None:
    """The strongest possible attestation buys none of these."""
    result = _validate(_complete())
    assert result["creates_live_coverage"] is False
    assert result["creates_source_monitoring"] is False
    assert result["permits_improvement_claim"] is False


# ---------------------------------------------------------------------------
# Limited
# ---------------------------------------------------------------------------


def test_missing_raw_transport_produces_limited_and_upgrades_nothing() -> None:
    """"Yes it was fetched" with nothing to point at verifies no records."""
    result = _validate(
        _complete(raw_transport_available=False, raw_transport_artifact_paths=[])
    )
    assert result["attestation_status"] == "valid_limited_attestation"
    assert result["permits_verified_upgrade"] is False
    assert result["records_eligible_for_upgrade"] == []
    assert "no_raw_transport_available" in result["limitations"]
    assert attestation_invariant_failures(result) == []


def test_generated_data_cannot_be_verified_even_with_an_artifact() -> None:
    """A method that is not a recording cannot produce a verified recording."""
    result = _validate(
        _complete(collection_method="generated", live_fetch_performed=False)
    )
    assert result["attestation_status"] == "valid_limited_attestation"
    assert result["permits_verified_upgrade"] is False
    assert any(
        limitation.startswith("collection_method_is_not_a_recording")
        for limitation in result["limitations"]
    )


@pytest.mark.parametrize(
    "method", ["generated", "synthesized", "copied_from_another_corpus_row"]
)
def test_non_recording_methods_never_verify(method: str) -> None:
    result = _validate(
        _complete(collection_method=method, live_fetch_performed=False)
    )
    assert result["permits_verified_upgrade"] is False


def test_no_records_offered_yields_limited_not_complete() -> None:
    result = _validate(_complete(records_allowed_for_verified_upgrade=[]))
    assert result["attestation_status"] == "valid_limited_attestation"
    assert "no_records_offered_for_upgrade" in result["limitations"]


def test_blank_limitations_is_recorded_as_a_limitation() -> None:
    """Claiming no limitations makes an attestation weaker, not stronger."""
    result = _validate(_complete(provenance_limitations=[]))
    assert "attestation_states_no_limitations" in result["limitations"]


def test_incomplete_attestation_cannot_be_complete() -> None:
    """A missing non-core field blocks verification without rejecting outright."""
    result = _validate(_complete(field_mapping_summary=None))
    assert result["attestation_status"] == "valid_limited_attestation"
    assert "field_mapping_summary" in result["missing_fields"]
    assert result["permits_verified_upgrade"] is False


# ---------------------------------------------------------------------------
# Contradictory
# ---------------------------------------------------------------------------


def test_circular_artifact_offered_as_raw_transport_is_rejected() -> None:
    """Gate 87's finding, enforced against a human statement.

    The SAMHSA fixture names the corpus row as its own source. Offering it as
    corroboration of that row is a contradiction, not a weak point.
    """
    result = _validate(
        _complete(raw_transport_artifact_paths=[CIRCULAR_TRANSPORT_FILE])
    )
    assert result["attestation_status"] == "contradictory_attestation"
    assert result["permits_verified_upgrade"] is False
    assert any(
        r.startswith("cites_circular_artifact_as_raw_transport")
        for r in result["blocked_reasons"]
    )
    assert attestation_invariant_failures(result) == []


def test_claiming_transport_without_a_path_is_rejected() -> None:
    result = _validate(
        _complete(raw_transport_available=True, raw_transport_artifact_paths=[])
    )
    assert result["attestation_status"] == "contradictory_attestation"
    assert "claims_raw_transport_but_names_no_path" in result["blocked_reasons"]


def test_live_fetch_claimed_with_a_generated_method_is_rejected() -> None:
    result = _validate(
        _complete(collection_method="synthesized", live_fetch_performed=True)
    )
    assert result["attestation_status"] == "contradictory_attestation"
    assert any(
        r.startswith("claims_live_fetch_but_method_is")
        for r in result["blocked_reasons"]
    )


def test_a_record_both_excluded_and_offered_is_rejected() -> None:
    result = _validate(
        _complete(
            records_to_exclude_from_verified=["nf14-mixed-broad-01"],
            records_allowed_for_verified_upgrade=["nf14-mixed-broad-01"],
        )
    )
    assert result["attestation_status"] == "contradictory_attestation"
    assert any(
        r.startswith("record_both_excluded_and_offered")
        for r in result["blocked_reasons"]
    )


def test_offering_a_suspected_placeholder_for_upgrade_is_rejected() -> None:
    """An attestation cannot silently overturn a committed finding."""
    result = _validate(
        _complete(records_allowed_for_verified_upgrade=["nf13-real-fed-001"])
    )
    assert result["attestation_status"] == "contradictory_attestation"
    assert any(
        r.startswith("offers_suspected_placeholder_for_upgrade")
        for r in result["blocked_reasons"]
    )


def test_confirming_a_placeholder_is_accepted_rather_than_rejected() -> None:
    """The asymmetry is deliberate.

    Confirming a suspicion is information. Denying one without evidence is not,
    and must not be enough to overturn the finding.
    """
    result = _validate(
        _complete(
            known_placeholders=["nf13-real-fed-001"],
            records_allowed_for_verified_upgrade=["nf13-real-fed-001"],
        )
    )
    assert result["attestation_status"] != "contradictory_attestation"


# ---------------------------------------------------------------------------
# Insufficient and unknown
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", CORE_FIELDS)
def test_a_missing_core_field_produces_insufficient(field: str) -> None:
    result = _validate(_complete(**{field: None}))
    assert result["attestation_status"] == "insufficient_attestation"
    assert f"missing_core_field:{field}" in result["blocked_reasons"]
    assert result["permits_verified_upgrade"] is False
    assert attestation_invariant_failures(result) == []


@pytest.mark.parametrize("attestation", [None, {}])
def test_absent_attestation_is_unknown_and_changes_nothing(attestation) -> None:
    result = _validate(attestation)
    assert result["attestation_status"] == "unknown_attestation"
    assert result["permits_verified_upgrade"] is False
    assert result["records_eligible_for_upgrade"] == []
    assert "no_attestation_supplied" in result["blocked_reasons"]
    assert "gate_88_classifications_remain_authoritative" in result["findings"]
    assert result["missing_fields"] == list(REQUIRED_FIELDS)
    assert attestation_invariant_failures(result) == []


def test_an_unrecognised_collection_method_degrades_to_unknown() -> None:
    result = _validate(_complete(collection_method="vibes"))
    assert any(
        f.startswith("unrecognised_collection_method") for f in result["findings"]
    )
    assert result["collection_method"] == "unknown"
    assert result["permits_verified_upgrade"] is False


@pytest.mark.parametrize(
    "method",
    sorted(COLLECTION_METHODS - RECORDING_METHODS) + ["typo_nobody_anticipated"],
)
def test_verification_requires_an_affirmative_recording_method(method: str) -> None:
    """Deny by default, not subtract-the-denied.

    A first cut of this validator asked whether the method was *absent* from the
    non-recording set. `unknown`, `mixed` and any unanticipated value all passed
    that test, so a typo in one form field could verify a record. Verification
    now requires membership in RECORDING_METHODS.
    """
    result = _validate(
        _complete(collection_method=method, live_fetch_performed=False)
    )
    assert result["permits_verified_upgrade"] is False, method
    assert result["records_eligible_for_upgrade"] == []


@pytest.mark.parametrize("method", sorted(RECORDING_METHODS))
def test_recording_methods_can_verify(method: str) -> None:
    result = _validate(_complete(collection_method=method))
    assert result["attestation_status"] == "valid_complete_attestation"
    assert result["permits_verified_upgrade"] is True


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_excluded_records_are_never_upgradable() -> None:
    result = _validate(
        _complete(
            records_to_exclude_from_verified=["nf14-mixed-broad-02"],
            records_allowed_for_verified_upgrade=[
                "nf14-mixed-broad-01",
                "nf14-mixed-broad-02",
            ],
        )
    )
    # broad-02 is both offered and excluded -> contradiction, nothing upgrades.
    assert result["attestation_status"] == "contradictory_attestation"
    assert result["records_eligible_for_upgrade"] == []


def test_invariant_rejects_upgrade_under_a_non_permitting_status() -> None:
    doctored = _validate(_complete())
    doctored["attestation_status"] = "valid_limited_attestation"
    failures = attestation_invariant_failures(doctored)
    assert "upgrade_permitted_under_status:valid_limited_attestation" in failures


def test_invariant_rejects_a_complete_attestation_without_transport() -> None:
    doctored = _validate(_complete())
    doctored["raw_transport_paths"] = []
    assert "complete_attestation_without_raw_transport" in (
        attestation_invariant_failures(doctored)
    )


@pytest.mark.parametrize(
    "constant",
    ["creates_live_coverage", "creates_source_monitoring", "permits_improvement_claim"],
)
def test_invariant_rejects_a_flipped_runtime_claim(constant: str) -> None:
    doctored = _validate(_complete())
    doctored[constant] = True
    assert f"attestation_claimed:{constant}" in attestation_invariant_failures(
        doctored
    )


def test_invariant_rejects_an_excluded_record_offered_for_upgrade() -> None:
    doctored = _validate(_complete())
    doctored["records_excluded"] = ["nf14-mixed-broad-01"]
    failures = attestation_invariant_failures(doctored)
    assert any(f.startswith("excluded_record_offered_for_upgrade") for f in failures)


def test_every_status_is_in_the_vocabulary() -> None:
    cases = (None, {}, _complete(), _complete(collection_method="generated"))
    for attestation in cases:
        result = _validate(attestation)
        assert result["attestation_status"] in ATTESTATION_STATUSES
        assert result["schema_version"] == SCHEMA_VERSION
        assert result["fabricated"] is False


def test_contract_declares_what_it_cannot_do() -> None:
    contract = build_attestation_contract()
    assert contract["creates_live_coverage"] is False
    assert contract["creates_source_monitoring"] is False
    assert contract["permits_improvement_claim"] is False
    assert set(contract["statuses"]) == ATTESTATION_STATUSES
    assert set(contract["upgrade_permitting_statuses"]) == UPGRADE_PERMITTING_STATUSES
    assert set(contract["collection_methods"]) == COLLECTION_METHODS


def test_service_performs_no_io() -> None:
    source = (
        REPO_ROOT
        / "src/nativeforge/services/corpus_provenance_attestation_service.py"
    ).read_text(encoding="utf-8")
    for banned in (
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "open(",
        "Path(",
        "read_text",
    ):
        assert banned not in source, banned


# ---------------------------------------------------------------------------
# Gate 89 changes nothing
# ---------------------------------------------------------------------------


def test_gate88_classifications_are_unchanged() -> None:
    """No attestation exists, so nothing may move."""
    baseline = build_discovery_baseline_x(repo_root=REPO_ROOT)
    quality = baseline["opportunity_quality"]
    assert quality["recorded_verified_records"] == 18
    assert quality["recorded_asserted_records"] == 166
    assert quality["recorded_circular_records"] == 1
    assert quality["flags_only_records"] == 38
    assert baseline["corpus_summary"]["recorded_records"] == 162
    assert baseline["corpus_summary"]["total_records"] == 185
    assert baseline["readiness_summary"]["baseline_quality_score"] == 0.0865
    assert baseline["improvement_claim_allowed"] is False
    assert baseline["live_coverage_claimed"] is False
    assert baseline["source_monitoring_claimed"] is False


def test_the_stub_records_that_no_attestation_exists() -> None:
    stub = (
        REPO_ROOT
        / "docs/operations/499_GATE89_CORPUS_PROVENANCE_ATTESTATION_STUB.md"
    ).read_text(encoding="utf-8")
    assert "No operator attestation has been provided." in stub
    assert "unknown_attestation" in stub
    assert "records upgraded by Gate 89         0" in stub


def test_the_packet_is_blank_and_asks_about_every_group() -> None:
    """The template must stay a template."""
    packet = (
        REPO_ROOT
        / "docs/operations/498_GATE89_CORPUS_PROVENANCE_ATTESTATION_PACKET.md"
    ).read_text(encoding="utf-8")
    assert "This is a blank form." in packet
    for group in (
        "nf13_real_ingested_grants.json",
        "la_scaled_federal_grants.json",
        "ta_mixed_tier13_grants.json",
        "ta_tier2_state_grants.json",
        "ta_tier3_foundation_grants.json",
        "nf14_mixed_corpus.json",
        "nf_seed_2026_fed_021_samhsa_sm_26_024.json",
        "nf14_grants_gov_broad_edge_pulls.json",
    ):
        assert group in packet, group
    # And it must ask the questions the gate requires.
    for question in (
        "fetched live",
        "What tool",
        "raw API responses",
        "copied from another committed corpus row",
        "placeholder",
        "test doubles",
        "verified recorded",
        "asserted only",
        "robots/terms review",
    ):
        assert question.lower() in packet.lower(), question


def test_the_packet_references_only_paths_that_exist() -> None:
    """A form asking about a file that does not exist invents provenance.

    The Gate 89 prompt listed the nf14 transport under tests/fixtures/grants_gov/;
    it lives in fixtures/real_grants_corpus/. The packet asks about the real one.
    """
    assert (REPO_ROOT / INDEPENDENT_TRANSPORT_FILE).exists()
    assert (REPO_ROOT / CIRCULAR_TRANSPORT_FILE).exists()
    assert not (
        REPO_ROOT / "tests/fixtures/grants_gov/nf14_grants_gov_broad_edge_pulls.json"
    ).exists()
    packet = (
        REPO_ROOT
        / "docs/operations/498_GATE89_CORPUS_PROVENANCE_ATTESTATION_PACKET.md"
    ).read_text(encoding="utf-8")
    assert INDEPENDENT_TRANSPORT_FILE in packet


def test_a_hypothetical_upgrade_would_be_traceable_to_named_records() -> None:
    """Whatever a future gate does, it can only act on named records.

    Not an upgrade - a proof that the mechanism cannot upgrade in bulk.
    """
    result = _validate(_complete())
    assert result["records_eligible_for_upgrade"] == ["nf14-mixed-broad-01"]
    baseline = build_discovery_baseline_x(repo_root=REPO_ROOT)
    known = {m["grant_id"] for m in baseline["per_record"]}
    for record_id in result["records_eligible_for_upgrade"]:
        assert record_id in known, record_id


def test_result_is_json_serialisable() -> None:
    json.dumps(_validate(_complete()))
    json.dumps(_validate(None))
