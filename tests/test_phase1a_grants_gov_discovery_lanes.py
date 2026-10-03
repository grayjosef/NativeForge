"""Phase 1A: the Grants.gov discovery lanes are dispatchable and unauthorized.

Four Tranche 2 publishers - HUD ONAP, IHS, EPA, CDFI - do not publish their
own machine-readable feed. Each close report says "Grants.gov owns the
records", and their commits added semantic services rather than transports.
Forecasts are a fifth lane on the same endpoint. So Phase 1A registers three
lane adapter keys sharing one builder and one executor, and five registry rows
that carry the per-publisher query.

Two things these tests hold apart, because conflating them is the whole risk:

    CAPABILITY     the fleet could dispatch this row
    AUTHORIZATION  a human decided it may

Every lane below must be the first and must not be the second.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from nativeforge.services.grants_gov_lane_binding_service import (
    LANE_ADAPTER_KEYS,
    SEED_LANE_BINDINGS,
    build_grants_gov_lane_search_body,
    lane_invariant_failures,
    search_grants_gov_lane,
)
from nativeforge.services.source_collector_capability_service import (
    ADAPTER_CAPABILITIES,
    measure_collector_capability,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)

ROOT = Path(__file__).resolve().parents[1]
SEED_CSV = ROOT / "fixtures" / "source_ingestion" / "NF_SOURCE_SEED_2026.csv"

BASELINE_SEED = "nf-seed-2026-api-grants-gov-search2"
SEARCH2 = "https://api.grants.gov/v1/api/search2"

#: Checks that depend only on the adapter, not on a database connection.
ADAPTER_CHECKS = (
    "adapter_is_known",
    "adapter_module_resolves",
    "request_builds_for_source",
    "endpoint_matches_registry",
    "transport_is_injectable",
)


def _rows() -> dict[str, dict]:
    return load_registry_rows()


# ------------------------------------------------------- capability


@pytest.mark.parametrize("seed_id", sorted(SEED_LANE_BINDINGS))
def test_every_lane_row_is_dispatchable(seed_id: str):
    """The Phase 1A objective, stated per row."""
    row = _rows().get(seed_id)
    assert row is not None, f"{seed_id} is not in the seed registry"

    result = measure_collector_capability(
        connection=None, registry_row=row, source_id=seed_id
    )
    measured = result.get("measured") or {}
    failing = [name for name in ADAPTER_CHECKS if not measured.get(name)]
    assert failing == [], f"{seed_id} fails {failing}: {result.get('notes')}"


def test_the_already_working_grants_gov_row_still_dispatches():
    """Phase 1A must not disturb the one source that actually collects."""
    row = _rows()[BASELINE_SEED]
    result = measure_collector_capability(
        connection=None, registry_row=row, source_id=BASELINE_SEED
    )
    measured = result.get("measured") or {}
    assert [n for n in ADAPTER_CHECKS if not measured.get(n)] == []


def test_the_capability_map_gained_only_the_lane_keys():
    """A capability entry is a dispatch permission. Adding one quietly is how
    a source starts being reachable without anybody deciding it should be."""
    assert set(ADAPTER_CAPABILITIES) == {"grants_gov_search2", *LANE_ADAPTER_KEYS}


# ------------------------------------------------------- authorization


@pytest.mark.parametrize("seed_id", sorted(SEED_LANE_BINDINGS))
def test_no_lane_row_claims_operator_approval(seed_id: str):
    """Capability is not authorization, enforced on the row itself.

    The one approved row in this file reads `gate163:operator_approved:MAYHEM`.
    A lane that acquired that string would be claiming a human decision nobody
    made.
    """
    row = _rows()[seed_id]
    evidence = str(row.get("health_evidence") or "")
    assert "operator_approved" not in evidence, evidence
    assert "awaiting_human_authorization" in evidence


def test_exactly_the_historically_approved_rows_carry_approval():
    """Pins the blast radius of this change to zero approvals.

    Two rows carried `operator_approved` before Phase 1A - Grants.gov search2
    (gate163) and Federal Register documents (gate171). Phase 1A added five
    rows and must not have added a third approval.
    """
    text = SEED_CSV.read_text(encoding="utf-8")
    approved = [line for line in text.splitlines() if "operator_approved" in line]
    assert len(approved) == 2, [line.split(",")[0] for line in approved]


# ------------------------------------------- what a lane may not ask for


@pytest.mark.parametrize("seed_id", sorted(SEED_LANE_BINDINGS))
def test_no_lane_reinstates_keyword_discovery(seed_id: str):
    """Wave 1 removed keyword discovery because the Tribal-eligible
    opportunities whose titles never say "Tribal" are the ones that matter:
    of the first 100 sampled elig-07 titles, 4 contained Native wording.

    The capability-registered baseline builder still produces
    `{"keyword": "Grants.gov Search2 API"}` - it searches for its own name.
    No lane may do that.
    """
    body = build_grants_gov_lane_search_body({"seed_id": seed_id})
    assert "keyword" not in body, body


@pytest.mark.parametrize("seed_id", sorted(SEED_LANE_BINDINGS))
def test_no_lane_filters_discovery_by_eligibility(seed_id: str):
    """ELIGIBILITY != VISIBILITY, enforced rather than documented.

    HUD's FR-6900-N-74 is a $5,000,000 ICDBG award that declares applicant
    type 25 only and is returned 0 of 3 times by codes 07/08/11. A discovery
    lane that filtered on the Tribal eligibility codes would never see it.
    """
    body = build_grants_gov_lane_search_body({"seed_id": seed_id})
    assert "eligibilities" not in body, body
    assert lane_invariant_failures(body) == []


def test_the_lane_invariants_can_still_fire():
    """Falsifies the two tests above. A check that cannot fail is not one."""
    assert "a_lane_must_not_carry_a_keyword" in lane_invariant_failures(
        {"keyword": "tribal", "oppStatuses": "posted", "rows": 10}
    )
    assert "a_discovery_lane_must_not_filter_by_eligibility" in (
        lane_invariant_failures(
            {"eligibilities": "07", "oppStatuses": "posted", "rows": 10}
        )
    )
    assert "a_lane_must_be_bounded" in lane_invariant_failures(
        {"oppStatuses": "posted", "rows": 0}
    )


def test_an_unknown_seed_id_is_refused_rather_than_guessed():
    """A lane builder that invented a default query would make every
    unbound row silently collectable."""
    with pytest.raises(ValueError):
        build_grants_gov_lane_search_body({"seed_id": "nf-seed-2026-not-a-lane"})


# ------------------------------------------- per-publisher semantics


def test_each_lane_asks_the_publisher_its_own_question():
    """The measured parameters, not plausible ones.

    CDFI is the reason the evidence string exists: TREAS, TREAS-CDFI and CDFI
    all returned exactly what the NONSENSE control returned, and USDOT-CDFI
    was found only by reading records.
    """
    bodies = {
        seed: build_grants_gov_lane_search_body({"seed_id": seed})
        for seed in SEED_LANE_BINDINGS
    }
    assert bodies["nf-seed-2026-api-grants-gov-cdfi"]["agencies"] == "USDOT-CDFI"
    assert bodies["nf-seed-2026-api-grants-gov-ihs"]["agencies"] == "HHS-IHS"
    assert bodies["nf-seed-2026-api-grants-gov-epa"]["agencies"] == "EPA"
    assert bodies["nf-seed-2026-api-grants-gov-hud-onap"]["cfda"] == "14.862"
    assert (
        bodies["nf-seed-2026-api-grants-gov-forecast"]["oppStatuses"] == "forecasted"
    )


def test_every_binding_carries_its_evidence():
    """HABEAS DATA. A lane parameter without a retrievable reason is a guess
    that will be read as a fact by whoever maintains it next."""
    for seed_id, binding in SEED_LANE_BINDINGS.items():
        assert len(str(binding.get("evidence") or "").strip()) > 40, seed_id


def test_hud_keeps_its_forecast_reach():
    """2B measured 3 of 3 first-party links stale while live FY2026 forecasts
    of $125M and $90M were linked from neither. A posted-only lane would
    inherit exactly that blindness."""
    body = build_grants_gov_lane_search_body(
        {"seed_id": "nf-seed-2026-api-grants-gov-hud-onap"}
    )
    assert "forecasted" in body["oppStatuses"]


def test_cdfi_can_legitimately_return_nothing():
    """63 records, every one archived, and a negative control proved the zero
    is the publisher's answer. An empty lane is `empty`, never `fetch_error`."""
    captured: dict = {}

    def fake_post(url, body):
        captured["url"] = url
        return {"errorcode": 0, "data": {"oppHits": []}}

    result = search_grants_gov_lane(
        {"seed_id": "nf-seed-2026-api-grants-gov-cdfi"},
        http_post=fake_post,
    )
    assert captured["url"] == SEARCH2
    assert result["outcome"] == "empty"
    assert result["hit_count"] == 0
    assert result["never_synthesized"] is True


def test_a_transport_failure_is_not_an_empty_publisher():
    """The Gate 140 defect, refused in a new place: a refusal that reads as
    `hit_count: 0` is indistinguishable from a publisher with nothing."""

    def broken_post(url, body):
        raise RuntimeError("connection reset")

    result = search_grants_gov_lane(
        {"seed_id": "nf-seed-2026-api-grants-gov-epa"}, http_post=broken_post
    )
    assert result["outcome"] == "fetch_error"
    assert result["search_live"] is False
    assert "connection reset" in result["api_error"]


# ------------------------------------------------------- registry health


def test_the_seed_registry_did_not_shrink():
    """`EXPECTED_ROW_COUNT` is enforced as a floor. Phase 1A adds rows."""
    from nativeforge.services.source_ingestion_seed_schema_service import (
        MINIMUM_ROW_COUNT,
    )

    with SEED_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= MINIMUM_ROW_COUNT


def test_every_lane_row_targets_the_one_endpoint():
    """Capability requires the row's `source_url` to equal the adapter's
    endpoint constant exactly. Every lane shares that endpoint."""
    rows = _rows()
    for seed_id in SEED_LANE_BINDINGS:
        assert rows[seed_id]["source_url"] == SEARCH2, seed_id
