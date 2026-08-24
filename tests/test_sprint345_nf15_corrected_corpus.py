"""Sprint 344-345: eligibility re-ingest and corrected corpus.

**Unquarantined in Gate 77B.** Both tests were quarantined in Gate 77 because
they called ``api.grants.gov`` at test time and wrote their results back over a
committed corpus fixture. Both defects are now fixed at the source rather than
worked around here:

  * ``default_grants_gov_http_post`` refuses to make a live call unless
    ``NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1`` (doc 429).
  * the re-ingest write-back is redirected under ``artifacts/`` unless two
    separate flags permit overwriting committed evidence (doc 430).

These tests now inject a **recorded transport** transcribed from the committed
corpus, so they exercise the real re-ingest path without asking a third party
anything. The recording reproduces the already-recorded ``SM-26-024`` /
``SAMHSA / HHS`` row; it invents no opportunity, agency or eligibility text.

The cross-program proxy guard is untouched and still raises. What changed is
that this file no longer depends on what Grants.gov happens to return today —
which, as of Gate 77, is an ``HHS-IHS`` opportunity the guard correctly refuses.
"""

from __future__ import annotations

from typing import Any

import pytest

from nativeforge.services.eligibility_evidence_quality_service import (
    is_placeholder_eligibility,
)
from nativeforge.services.hermetic_test_guard_service import load_recorded_transport
from nativeforge.services.nf15_corrected_corpus_classification_service import (
    classify_nf15_corrected_corpus,
)
from nativeforge.services.tribal_grant_eligibility_reingest_service import (
    reingest_nf13_placeholder_grants,
)

RECORDED_SAMHSA_TRANSPORT = "nf_seed_2026_fed_021_samhsa_sm_26_024.json"


@pytest.fixture
def recorded_transport() -> Any:
    """The recorded Grants.gov transport for seed nf-seed-2026-fed-021."""
    return load_recorded_transport(RECORDED_SAMHSA_TRANSPORT)


def test_reingest_fixes_placeholder_grants(recorded_transport: Any) -> None:
    report = reingest_nf13_placeholder_grants(http_post=recorded_transport)
    fed021 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-021")
    fed025 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-025")
    assert fed021["reingested"] is True
    assert fed025["no_live_nofo"] is True
    assert report["proxy_substitution_count"] == 0
    assert not is_placeholder_eligibility(
        str(fed021["updated_grant"]["eligibility_text"])
    )
    assert fed025["updated_grant"]["source_ingestion_state"] == "no_live_nofo"

    # Gate 77B: the recorded agency must survive re-ingest unchanged. If this
    # ever reads HHS-IHS, a live response has leaked into a hermetic test.
    assert fed021["updated_grant"]["agency"] == "SAMHSA / HHS"
    assert fed021["updated_grant"]["opportunity_number"] == "SM-26-024"

    # And the run must not have written the committed fixture.
    assert report["writeback_redirected"] is True
    assert "artifacts/" in str(report["written_path"])
    assert report["hermetic_status"]["mode"] == "hermetic"


def test_corrected_corpus_no_tribal_federal_irrelevant(recorded_transport: Any) -> None:
    result = classify_nf15_corrected_corpus(http_post=recorded_transport)
    assert result["no_tribal_federal_in_irrelevant"] is True
    assert result["label_distribution"].get("irrelevant", 0) < 8
