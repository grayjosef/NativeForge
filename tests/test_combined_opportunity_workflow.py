"""Tests: SC state adapter + federal foundation + combined workflow."""

from __future__ import annotations

from nativeforge.services.combined_opportunity_workflow_service import (
    build_combined_opportunity_workflow,
    combined_workflow_invariant_failures,
)
from nativeforge.services.federal_opportunity_foundation_service import (
    build_federal_foundation_pack_for_sc,
    federal_foundation_invariant_failures,
)
from nativeforge.services.sc_state_source_adapter_config_service import (
    build_sc_state_source_adapter_config,
    sc_state_adapter_invariant_failures,
    write_sc_state_source_adapter_config,
)


def test_sc_adapter_is_reference_not_fork() -> None:
    cfg = build_sc_state_source_adapter_config()
    assert sc_state_adapter_invariant_failures(cfg) == []
    assert cfg["is_reference_state_implementation"] is True
    assert cfg["product_fork"] is False
    assert cfg["live_ingest_claimed"] is False
    path = write_sc_state_source_adapter_config(cfg)
    assert path.is_file()


def test_federal_foundation_visible_for_sc() -> None:
    pack = build_federal_foundation_pack_for_sc()
    assert federal_foundation_invariant_failures(pack) == []
    assert pack["count"] >= 1
    for o in pack["opportunities"]:
        assert (
            o["organization_fit_handoff"]["org_geo_must_not_filter_funding_geo"] is True
        )
        assert o["source_layer"] == "federal"


def test_combined_workflow_sc_and_federal_ordering() -> None:
    wf = build_combined_opportunity_workflow()
    assert combined_workflow_invariant_failures(wf) == []
    assert wf["counts"]["sc_state"] >= 1
    assert wf["counts"]["federal"] >= 1
    assert wf["organization_geography_filters_federal"] is False
    assert wf["final_eligibility_claim_allowed"] is False
    layers = [x["source_layer"] for x in wf["combined_ordering"]]
    first_fed = next(i for i, L in enumerate(layers) if L == "federal")
    assert all(L == "sc_state" for L in layers[:first_fed])
    assert wf["missing_data_summary"]["hidden_missing_data"] is False
    assert wf["human_review"]["all_require_human_review"] is True
