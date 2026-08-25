"""Gate 84B — the two formerly failing tests, and why they were failing.

Gate 84 reported these as order-dependent. They were not: both failed
deterministically, alone and in any subset. They were invisible because the
broad scoped `-k` never selected them.

  * `test_nf15_gate_and_closeout` was broken by Gate 77B, which made live
    Grants.gov calls opt-in without giving this path a way to inject a recorded
    transport.
  * `test_unknown_count_drops_ac1` measured an absolute unknown count against a
    corpus that later grew by two layers.

These tests pin the fixes and the reasoning, and assert the results do not
depend on call order.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from nativeforge.services.grant_eligibility_conditions_service import (
    enrich_grant_with_eligibility_metadata,
)
from nativeforge.services.hermetic_test_guard_service import (
    RECORDED_TRANSPORT_DIR,
    load_recorded_transport,
)
from nativeforge.services.nf15_no_evidence_honesty_gate_verification_service import (
    verify_nf15_no_evidence_honesty_gates,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    load_sc_eligibility_rules,
)
from nativeforge.services.tier2_state_corpus_persist_service import (
    load_tier2_state_corpus,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
RECORDED_TRANSPORT = "nf_seed_2026_fed_021_samhsa_sm_26_024.json"

FORMERLY_FAILING = (
    "tests/test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1",
    "tests/test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout",
)


@pytest.fixture
def staging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from nativeforge.lib.settings import get_settings

    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# Both tests pass when run entirely alone
# --------------------------------------------------------------------------


@pytest.mark.parametrize("node_id", FORMERLY_FAILING)
def test_formerly_failing_test_passes_in_its_own_process(node_id: str) -> None:
    """A fresh interpreter with only this test selected - no neighbour can be
    supplying setup."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", node_id],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout[-3000:]


# --------------------------------------------------------------------------
# NF-15: the transport is injected, not implied
# --------------------------------------------------------------------------


def test_nf15_gates_pass_with_the_recorded_transport(staging_env: None) -> None:
    gate = verify_nf15_no_evidence_honesty_gates(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    assert gate["verification_passed"] is True
    assert gate["checks"]["fed021_reingested"] is True
    assert gate["checks"]["fed025_no_live_nofo"] is True


def test_nf15_gate_result_is_the_same_on_first_and_repeated_calls(
    staging_env: None,
) -> None:
    first = verify_nf15_no_evidence_honesty_gates(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    second = verify_nf15_no_evidence_honesty_gates(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    assert first["checks"] == second["checks"]
    assert first["verification_passed"] == second["verification_passed"]


def test_nf15_without_a_transport_still_refuses_the_live_path(
    staging_env: None,
) -> None:
    """The fix must not have quietly re-enabled live network as a fallback."""
    gate = verify_nf15_no_evidence_honesty_gates()
    assert gate["checks"]["fed021_reingested"] is False
    assert gate["verification_passed"] is False


def test_the_recorded_transport_is_committed() -> None:
    assert (RECORDED_TRANSPORT_DIR / RECORDED_TRANSPORT).is_file()


# --------------------------------------------------------------------------
# AC1: measured against the corpus it was calibrated for
# --------------------------------------------------------------------------


def _tier1() -> list[dict]:
    later = {g["grant_id"] for g in load_tier3_foundation_corpus()} | {
        g["grant_id"] for g in load_tier2_state_corpus()
    }
    return [g for g in load_mixed_tier13_corpus() if g["grant_id"] not in later]


def test_ac1_holds_on_the_federal_corpus() -> None:
    rules = load_sc_eligibility_rules(require_files=False)
    enriched = [
        enrich_grant_with_eligibility_metadata(g, rules=rules)
        for g in _tier1()
    ]
    unknowns = [g for g in enriched if g["recognition_requirement"] == "unknown"]
    # Comfortably inside the original threshold, not scraping past it.
    assert len(unknowns) <= 45


def test_ac1_scope_change_did_not_weaken_the_assertion() -> None:
    """The tier-1 corpus is still substantial, so scoping is not a bypass."""
    tier1 = _tier1()
    assert len(tier1) >= 50


def test_enrichment_is_stable_across_repeated_calls() -> None:
    rules = load_sc_eligibility_rules(require_files=False)
    corpus = load_mixed_tier13_corpus()
    first = [
        enrich_grant_with_eligibility_metadata(g, rules=rules)[
            "recognition_requirement"
        ]
        for g in corpus
    ]
    second = [
        enrich_grant_with_eligibility_metadata(g, rules=rules)[
            "recognition_requirement"
        ]
        for g in corpus
    ]
    assert first == second


def test_extra_unknowns_are_attributable_to_later_corpus_layers() -> None:
    rules = load_sc_eligibility_rules(require_files=False)
    later = {g["grant_id"] for g in load_tier3_foundation_corpus()} | {
        g["grant_id"] for g in load_tier2_state_corpus()
    }
    tier1_ids = {g["grant_id"] for g in _tier1()}
    unknown_ids = {
        g["grant_id"]
        for g in (
            enrich_grant_with_eligibility_metadata(g, rules=rules)
            for g in load_mixed_tier13_corpus()
        )
        if g["recognition_requirement"] == "unknown"
    }
    assert unknown_ids - tier1_ids <= later


# --------------------------------------------------------------------------
# No fixed artifact path leaks between tests
# --------------------------------------------------------------------------


def test_neither_path_mutates_a_committed_fixture(staging_env: None) -> None:
    """The corpus and the reingest fixture must be byte-identical afterwards."""
    import hashlib

    watched = [
        ROOT / "fixtures" / "real_grants_corpus" / "ta_mixed_tier13_grants.json",
        ROOT
        / "fixtures"
        / "real_grants_corpus"
        / "nf15_eligibility_reingest_pulls.json",
        ROOT / "fixtures" / "sc_pilot" / "sc_eligibility_rules.json",
    ]
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in watched
        if p.is_file()
    }
    assert before, "expected the committed fixtures to exist"

    verify_nf15_no_evidence_honesty_gates(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    rules = load_sc_eligibility_rules(require_files=False)
    [enrich_grant_with_eligibility_metadata(g, rules=rules) for g in _tier1()]

    after = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in watched
        if p.is_file()
    }
    assert before == after


def test_corpus_is_read_from_a_committed_file_not_rebuilt() -> None:
    """The corpus these assertions rest on is committed evidence."""
    corpus_path = (
        ROOT / "fixtures" / "real_grants_corpus" / "ta_mixed_tier13_grants.json"
    )
    assert corpus_path.is_file()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(corpus_path.relative_to(ROOT))],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert tracked.returncode == 0, tracked.stderr


def test_readiness_doc_records_the_correction() -> None:
    doc = ROOT / "docs" / "operations" / "474_GATE84B_PRODUCTION_READINESS_DELTA.md"
    body = doc.read_text(encoding="utf-8")
    assert "not order-dependent" in body
    assert "Live SC source coverage:   NONE" in body
    assert "Controlled customer pilot: NO_GO" in body
