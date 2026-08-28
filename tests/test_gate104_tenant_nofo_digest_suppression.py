"""Gate 104 - tenant NOFO digest and pursuit suppression.

Hermetic. Nothing here sends a message, activates a collector, fetches a URL, or
deletes anything.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from nativeforge.services.deadline_provenance_service import VERIFIED_STATUSES
from nativeforge.services.opportunity_deadline_and_amendment_model_service import (
    AMENDMENT_CATEGORIES,
    MATERIAL_CATEGORIES,
)
from nativeforge.services.tenant_beta_demo_fixture_service import (
    REAL_TRIBE_NAME_TOKENS,
)
from nativeforge.services.tenant_nofo_digest_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    FALSE_DECLARATION_KEYS,
    TenantDigestArtifactError,
    artifact_claim_failures,
    build_digest_artifact_bundle,
    render_summary,
    write_digest_artifacts,
)
from nativeforge.services.tenant_nofo_digest_builder_service import (
    CADENCES,
    DEFAULT_CADENCE,
    DELIVERED_STATUSES,
    PREVIEW_DELIVERY_STATUSES,
    build_tenant_digest,
    digest_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_change_detection_service import (
    CHANGE_TYPES,
    COMPARISON_KINDS,
    HUMAN_REVIEW_CHANGE_TYPES,
    change_detection_invariant_failures,
    detect_digest_changes,
    summarise_changes,
)
from nativeforge.services.tenant_nofo_digest_demo_fixture_service import (
    DEMO_TENANT_ID,
    PERIOD_END,
    PERIOD_START,
    REFERENCE_NOW,
    REQUIRED_CHANGE_TYPES,
    build_digest_demo_fixture_set,
    demo_fixture_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_item_explanation_service import (
    DIGEST_ITEM_STATUSES,
    build_digest_item_explanation,
    explanation_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_readiness_service import (
    DEMO_SCOPE,
    OPERATIONAL_COMPONENT_KEYS,
    build_digest_readiness,
    digest_readiness_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_snapshot_service import (
    COLLECTION_PROVEN_STATUSES,
    SNAPSHOT_KINDS,
    build_digest_snapshot,
    build_opportunity_row,
    snapshot_invariant_failures,
)
from nativeforge.services.tenant_pursuit_suppression_service import (
    ACTIVE_SUPPRESSION_STATUSES,
    SUPPRESSION_STATUSES,
    is_suppressed_for_tenant,
    summarise_suppressions,
    suppress_for_tenant,
    suppression_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

GATE104_SERVICES = (
    "tenant_nofo_digest_snapshot_service",
    "tenant_nofo_digest_change_detection_service",
    "tenant_nofo_digest_item_explanation_service",
    "tenant_pursuit_suppression_service",
    "tenant_nofo_digest_builder_service",
    "tenant_nofo_digest_readiness_service",
    "tenant_nofo_digest_demo_fixture_service",
    "tenant_nofo_digest_artifact_service",
)


@pytest.fixture
def fixtures():
    return build_digest_demo_fixture_set()


@pytest.fixture
def changes(fixtures):
    return detect_digest_changes(
        tenant_id=DEMO_TENANT_ID,
        current_snapshot=fixtures["current_snapshot"],
        previous_snapshot=fixtures["previous_snapshot"],
        now=REFERENCE_NOW,
    )


# --------------------------------------------------------------------------
# 104B - snapshots
# --------------------------------------------------------------------------


def test_snapshot_kinds_are_the_four_declared(fixtures) -> None:
    assert SNAPSHOT_KINDS == frozenset(
        {"demo_fixture", "recorded_fixture", "live_observation", "unknown"}
    )
    for key in ("previous_snapshot", "current_snapshot"):
        assert fixtures[key]["snapshot_kind"] == "demo_fixture"
        assert not snapshot_invariant_failures(fixtures[key])


def test_a_live_observation_without_proven_collection_is_refused() -> None:
    """The kind is not enough. Collection status has to back it."""
    snapshot = build_digest_snapshot(
        tenant_id="t1",
        snapshot_label="claims-live",
        snapshot_kind="live_observation",
        source_collection_status="not_active",
    )
    assert snapshot["requested_snapshot_kind"] == "live_observation"
    assert snapshot["snapshot_kind"] == "unknown"
    assert any(
        "live_observation_without_proven_collection" in r
        for r in snapshot["blocked_reasons"]
    )
    assert not snapshot_invariant_failures(snapshot)


def test_a_live_observation_with_proven_collection_is_accepted() -> None:
    """Not vacuous: the refusal above is a check, not a blanket ban."""
    snapshot = build_digest_snapshot(
        tenant_id="t1",
        snapshot_label="really-live",
        snapshot_kind="live_observation",
        source_collection_status="collected",
    )
    assert snapshot["snapshot_kind"] == "live_observation"
    assert "collected" in COLLECTION_PROVEN_STATUSES


def test_no_snapshot_claims_coverage(fixtures) -> None:
    for key in ("previous_snapshot", "current_snapshot"):
        snapshot = fixtures[key]
        assert snapshot["source_monitoring_live"] is False
        assert snapshot["live_source_coverage"] is False
        assert snapshot["collectors_active"] == 0
        assert snapshot["fetch_performed"] is False


def test_a_date_without_provenance_is_not_verified() -> None:
    row = build_opportunity_row(opportunity_id="o1", deadline="2026-06-01")
    assert row["deadline_provenance_status"] == "unverified_deadline"
    assert row["deadline_verified"] is False


def test_snapshot_invariants_reject_a_coverage_claim(fixtures) -> None:
    snapshot = fixtures["current_snapshot"]
    fails = snapshot_invariant_failures(dict(snapshot, live_source_coverage=True))
    assert "snapshot_claimed:live_source_coverage" in fails


# --------------------------------------------------------------------------
# 104C - change detection
# --------------------------------------------------------------------------


def test_the_fixture_pair_produces_every_required_change_type(changes) -> None:
    seen = {t for c in changes["changes"] for t in c["change_types"]}
    for required in REQUIRED_CHANGE_TYPES:
        assert required in seen, required


def test_no_previous_snapshot_means_first_seen_not_new(fixtures) -> None:
    """Forty 'new' opportunities on a first run would be forty months old."""
    result = detect_digest_changes(
        tenant_id=DEMO_TENANT_ID,
        current_snapshot=fixtures["current_snapshot"],
        previous_snapshot=None,
        now=REFERENCE_NOW,
    )
    assert result["comparison_kind"] == "first_seen_only"
    seen = {t for c in result["changes"] for t in c["change_types"]}
    assert "first_seen" in seen
    assert "new_match" not in seen
    assert not change_detection_invariant_failures(result)


def test_change_detection_identifies_new_match(changes) -> None:
    entry = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-new-match"
    )
    assert "new_match" in entry["change_types"]


def test_deadline_changed_requires_verified_provenance_on_both_sides(
    changes,
) -> None:
    verified = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-deadline-verified"
    )
    assert "deadline_changed" in verified["change_types"]
    assert verified["deadline_provenance_status"] in VERIFIED_STATUSES

    unverified = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-deadline-unverif"
    )
    assert "deadline_changed" not in unverified["change_types"]
    assert "deadline_changed_unverified" in unverified["change_types"]
    assert unverified["requires_human_review"] is True


def test_a_raw_date_difference_alone_is_not_a_deadline_change() -> None:
    """Two unreliable records disagreeing is not a deadline moving."""

    def snap(label, deadline):
        return build_digest_snapshot(
            tenant_id="t1",
            snapshot_label=label,
            snapshot_kind="demo_fixture",
            observed_at=f"2026-01-0{label[-1]}T00:00:00+00:00",
            opportunity_rows=[
                build_opportunity_row(
                    opportunity_id="o1",
                    deadline=deadline,
                    deadline_provenance_status="unverified_deadline",
                    eligibility_match_status="matched",
                    tenant_match_reasons=["r"],
                )
            ],
        )

    result = detect_digest_changes(
        tenant_id="t1",
        current_snapshot=snap("week2", "2026-07-01"),
        previous_snapshot=snap("week1", "2026-06-01"),
        now=REFERENCE_NOW,
    )
    types = result["changes"][0]["change_types"]
    assert "deadline_changed" not in types
    assert "deadline_changed_unverified" in types


def test_change_detection_identifies_amended(changes) -> None:
    entry = next(c for c in changes["changes"] if c["opportunity_id"] == "opp-amended")
    assert "amended" in entry["change_types"]
    # Bridged from the existing model rather than a second vocabulary.
    assert "eligibility_change" in MATERIAL_CATEGORIES
    assert "eligibility_change" in AMENDMENT_CATEGORIES


def test_change_detection_identifies_exclusion_and_downgrade(changes) -> None:
    excluded = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-excluded"
    )
    assert "newly_excluded" in excluded["change_types"]
    assert excluded["previous_eligibility_match_status"] == "matched"

    downgraded = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-downgraded"
    )
    assert "downgraded" in downgraded["change_types"]
    assert downgraded["previous_eligibility_match_status"] == "matched"


def test_removed_from_source_preserves_the_previous_row(changes) -> None:
    entry = next(c for c in changes["changes"] if c["opportunity_id"] == "opp-removed")
    assert "removed_from_source" in entry["change_types"]
    assert entry["deleted"] is False
    assert entry["previous_row_preserved"] is True
    assert entry["previous_row"]["opportunity_id"] == "opp-removed"


def test_change_detection_deletes_nothing(changes) -> None:
    assert changes["rows_deleted"] == 0
    assert changes["fetch_performed"] is False
    assert changes["source_monitoring_live"] is False


def test_the_comparison_labels_itself_as_fixture_to_fixture(changes) -> None:
    assert changes["comparison_kind"] == "fixture_to_fixture"
    assert (
        "comparison_between_recorded_snapshots_not_live_checks"
        in changes["blocked_reasons"]
    )


def test_change_invariants_reject_new_match_without_a_baseline(fixtures) -> None:
    result = detect_digest_changes(
        tenant_id=DEMO_TENANT_ID,
        current_snapshot=fixtures["current_snapshot"],
        previous_snapshot=None,
        now=REFERENCE_NOW,
    )
    forged = dict(result)
    forged["changes"] = [
        dict(forged["changes"][0], change_types=["new_match"]),
        *forged["changes"][1:],
    ]
    fails = change_detection_invariant_failures(forged)
    assert any("new_match_without_a_previous_snapshot" in f for f in fails)


def test_change_invariants_reject_a_deletion(changes) -> None:
    forged = dict(changes, rows_deleted=3)
    assert "comparison_deleted_rows" in change_detection_invariant_failures(forged)


def test_change_summary_reports_no_coverage(changes) -> None:
    summary = summarise_changes(changes)
    assert summary["source_monitoring_live"] is False
    assert summary["rows_deleted"] == 0
    # Two rows are absent from week 1 and matched in week 2: `opp-new-match`
    # and `opp-approaching`. `opp-review` is also new but is
    # `needs_human_review`, so it is deliberately not counted as a match.
    assert summary["by_change_type"]["new_match"] == 2
    new_matches = {
        c["opportunity_id"]
        for c in changes["changes"]
        if "new_match" in c["change_types"]
    }
    assert new_matches == {"opp-new-match", "opp-approaching"}
    assert "opp-review" not in new_matches


# --------------------------------------------------------------------------
# 104D - item explanation
# --------------------------------------------------------------------------


def _row_for(fixtures, opportunity_id):
    for row in fixtures["current_snapshot"]["opportunity_rows"]:
        if row["opportunity_id"] == opportunity_id:
            return row
    raise AssertionError(opportunity_id)


def test_matches_and_exclusions_are_separate_fields(fixtures, changes) -> None:
    row = _row_for(fixtures, "opp-excluded")
    change = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-excluded"
    )
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
    )
    assert explanation["why_this_may_not_match"]
    assert explanation["why_this_matches"] == []
    assert explanation["digest_item_status"] == "newly_excluded"
    assert not explanation_invariant_failures(explanation)


def test_a_match_states_its_reasons(fixtures, changes) -> None:
    row = _row_for(fixtures, "opp-new-match")
    change = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-new-match"
    )
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
    )
    assert explanation["why_this_matches"]
    assert explanation["headline"] == "Matches your tenant profile"


def test_an_unverified_deadline_is_visible(fixtures, changes) -> None:
    row = _row_for(fixtures, "opp-deadline-unverif")
    change = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-deadline-unverif"
    )
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
    )
    assert explanation["deadline_verified"] is False
    assert "not verified" in explanation["deadline_note"]
    assert any("deadline_not_verified" in r for r in explanation["blocked_reasons"])


def test_a_suspected_placeholder_is_not_shown_as_a_deadline(fixtures, changes) -> None:
    row = _row_for(fixtures, "opp-review")
    change = next(c for c in changes["changes"] if c["opportunity_id"] == "opp-review")
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
    )
    assert explanation["deadline_provenance_status"] == "suspected_placeholder"
    assert "placeholder" in explanation["deadline_note"].lower()
    assert explanation["deadline_verified"] is False


def test_unsupported_reporting_burden_is_visible(fixtures, changes) -> None:
    row = _row_for(fixtures, "opp-review")
    change = next(c for c in changes["changes"] if c["opportunity_id"] == "opp-review")
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
    )
    assert explanation["reporting_burden_status"] == "unsupported_document_type"
    assert "UNSUPPORTED_DOCUMENT_TYPE" in explanation["reporting_burden_note"]


def test_the_allowability_self_assessment_cap_reaches_the_surface(
    fixtures, changes
) -> None:
    """Where a cap like this usually dies is the presentation layer."""
    row = _row_for(fixtures, "opp-new-match")
    change = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-new-match"
    )
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID,
        opportunity_row=row,
        change=change,
        allowability_is_nativeforge_itself=True,
    )
    assert explanation["allowability_self_assessment_capped"] is True
    assert "requires_human_review" in explanation["allowability_note"]
    assert not explanation_invariant_failures(explanation)


def test_an_explanation_determines_no_eligibility(fixtures, changes) -> None:
    row = _row_for(fixtures, "opp-new-match")
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row
    )
    assert explanation["eligibility_determined"] is False
    assert explanation["deadline_guaranteed"] is False
    assert explanation["reporting_requirements_verified"] is False


def test_explanation_invariants_reject_an_unexplained_exclusion(
    fixtures, changes
) -> None:
    row = _row_for(fixtures, "opp-excluded")
    change = next(
        c for c in changes["changes"] if c["opportunity_id"] == "opp-excluded"
    )
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
    )
    fails = explanation_invariant_failures(dict(explanation, why_this_may_not_match=[]))
    assert "exclusion_without_an_explanation" in fails


def test_explanation_invariants_reject_a_dropped_cap(fixtures) -> None:
    row = _row_for(fixtures, "opp-new-match")
    explanation = build_digest_item_explanation(
        tenant_id=DEMO_TENANT_ID,
        opportunity_row=row,
        allowability_is_nativeforge_itself=True,
    )
    fails = explanation_invariant_failures(
        dict(explanation, allowability_note="Allowability: clearly allowable.")
    )
    assert "self_assessment_cap_dropped_from_the_explanation" in fails


def test_digest_item_statuses_are_closed(fixtures, changes) -> None:
    for change in changes["changes"]:
        row = _row_for_or_none(fixtures, change["opportunity_id"])
        if row is None:
            continue
        explanation = build_digest_item_explanation(
            tenant_id=DEMO_TENANT_ID, opportunity_row=row, change=change
        )
        assert explanation["digest_item_status"] in DIGEST_ITEM_STATUSES


def _row_for_or_none(fixtures, opportunity_id):
    for row in fixtures["current_snapshot"]["opportunity_rows"]:
        if row["opportunity_id"] == opportunity_id:
            return row
    return None


# --------------------------------------------------------------------------
# 104E - suppression
# --------------------------------------------------------------------------


def test_suppression_is_tenant_specific(fixtures) -> None:
    suppressions = fixtures["suppressions"]
    assert is_suppressed_for_tenant(
        suppressions=suppressions,
        tenant_id=DEMO_TENANT_ID,
        opportunity_id="opp-suppressed",
    )
    assert not is_suppressed_for_tenant(
        suppressions=suppressions,
        tenant_id="some-other-tenant",
        opportunity_id="opp-suppressed",
    )


def test_suppression_never_deletes_anything(fixtures) -> None:
    record = fixtures["suppressions"][0]
    assert record["opportunity_deleted"] is False
    assert record["source_record_deleted"] is False
    assert record["provenance_deleted"] is False
    assert record["audit_record_deleted"] is False
    assert record["suppressed_globally"] is False


def test_suppression_preserves_history_and_pipeline_visibility(fixtures) -> None:
    record = fixtures["suppressions"][0]
    assert record["source_history_preserved"] is True
    assert record["provenance_preserved"] is True
    assert record["visible_in_pipeline"] is True
    assert not suppression_invariant_failures(record)


def test_suppression_requires_a_pursuit_record_or_human_review() -> None:
    without = suppress_for_tenant(
        tenant_id="t1",
        opportunity_id="o1",
        suppression_reason="pursuit_started",
        suppressed_at="2026-01-01T00:00:00+00:00",
    )
    assert without["suppression_status"] == "human_review_required"
    assert "no_pursuit_record_and_no_human_review" in without["blocked_reasons"]
    assert without["suppression_status"] not in ACTIVE_SUPPRESSION_STATUSES

    with_review = suppress_for_tenant(
        tenant_id="t1",
        opportunity_id="o1",
        suppression_reason="tenant_requested",
        suppressed_at="2026-01-01T00:00:00+00:00",
        human_review_acknowledged=True,
        audit_event_id="a1",
    )
    assert with_review["suppression_status"] in ACTIVE_SUPPRESSION_STATUSES


def test_an_awarded_pursuit_routes_to_the_awarded_workspace() -> None:
    record = suppress_for_tenant(
        tenant_id="t1",
        opportunity_id="o1",
        suppression_reason="pursuit_awarded",
        suppressed_at="2026-01-01T00:00:00+00:00",
        pursuit_record_id="p1",
        audit_event_id="a1",
    )
    assert record["visible_in_awarded_workspace"] is True
    assert record["visible_in_pipeline"] is True
    assert not suppression_invariant_failures(record)


def test_a_non_awarded_pursuit_does_not_route_to_awarded() -> None:
    record = suppress_for_tenant(
        tenant_id="t1",
        opportunity_id="o1",
        suppression_reason="pursuit_started",
        suppressed_at="2026-01-01T00:00:00+00:00",
        pursuit_record_id="p1",
        audit_event_id="a1",
    )
    assert record["visible_in_awarded_workspace"] is False


def test_suppression_summary_is_per_tenant_never_global(fixtures) -> None:
    summary = summarise_suppressions(fixtures["suppressions"])
    assert summary["suppressed_by_tenant"] == {DEMO_TENANT_ID: 1}
    assert summary["suppressed_globally"] is False
    assert summary["opportunities_deleted"] == 0


@pytest.mark.parametrize(
    "key",
    [
        "opportunity_deleted",
        "source_record_deleted",
        "provenance_deleted",
        "audit_record_deleted",
        "suppressed_globally",
    ],
)
def test_suppression_invariants_reject_a_deletion_claim(fixtures, key: str) -> None:
    record = fixtures["suppressions"][0]
    fails = suppression_invariant_failures(dict(record, **{key: True}))
    assert f"suppression_claimed:{key}" in fails


@pytest.mark.parametrize(
    "key", ["source_history_preserved", "provenance_preserved", "visible_in_pipeline"]
)
def test_suppression_invariants_reject_dropping_a_preserved_fact(
    fixtures, key: str
) -> None:
    record = fixtures["suppressions"][0]
    fails = suppression_invariant_failures(dict(record, **{key: False}))
    assert f"suppression_dropped:{key}" in fails


def test_a_suppression_without_a_tenant_is_global_and_refused() -> None:
    record = suppress_for_tenant(
        tenant_id=None,
        opportunity_id="o1",
        suppression_reason="pursuit_started",
        suppressed_at="2026-01-01T00:00:00+00:00",
        pursuit_record_id="p1",
    )
    assert record["suppression_status"] == "unknown"
    fails = suppression_invariant_failures(record)
    assert "suppression_without_a_tenant_is_global" in fails


def test_suppression_statuses_are_the_six_declared() -> None:
    assert SUPPRESSION_STATUSES == frozenset(
        {
            "not_suppressed",
            "suppressed_from_new_digest",
            "suppressed_from_daily_alert",
            "suppressed_from_weekly_digest",
            "human_review_required",
            "unknown",
        }
    )


# --------------------------------------------------------------------------
# 104F - digest builder
# --------------------------------------------------------------------------


def _digest(fixtures, changes, **kwargs):
    params = dict(
        tenant_id=DEMO_TENANT_ID,
        current_snapshot=fixtures["current_snapshot"],
        change_detection=changes,
        previous_snapshot=fixtures["previous_snapshot"],
        suppressions=fixtures["suppressions"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    params.update(kwargs)
    return build_tenant_digest(**params)


def test_weekly_is_the_default_cadence(fixtures, changes) -> None:
    assert DEFAULT_CADENCE == "weekly"
    digest = _digest(fixtures, changes)
    assert digest["cadence"] == "weekly"
    assert not digest_invariant_failures(digest)


def test_daily_is_opt_in(fixtures, changes) -> None:
    without = _digest(fixtures, changes, cadence="daily", daily_alerts_enabled=False)
    assert without["requested_cadence"] == "daily"
    assert without["cadence"] == "weekly"
    assert "daily_alerts_not_enabled_for_this_tenant" in without["blocked_reasons"]

    with_optin = _digest(fixtures, changes, cadence="daily", daily_alerts_enabled=True)
    assert with_optin["cadence"] == "daily"
    assert "daily" in CADENCES


def test_the_digest_is_preview_only(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    assert digest["delivery_status"] in PREVIEW_DELIVERY_STATUSES
    assert digest["delivery_status"] not in DELIVERED_STATUSES
    assert digest["email_delivery_live"] is False
    assert digest["emails_sent"] == 0


def test_no_digest_item_claims_delivery(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    for item in digest["digest_items"]:
        assert item["delivered"] is False


def test_suppressed_items_are_counted_not_deleted(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    assert digest["items_suppressed"] == 1
    assert digest["items_deleted"] == 0
    suppressed = [i for i in digest["digest_items"] if i["suppressed"]]
    assert len(suppressed) == 1
    assert suppressed[0]["visible"] is False
    # Still present in the item list, so a tenant can see what was withheld.
    assert suppressed[0]["opportunity_id"] == "opp-suppressed"


def test_the_digest_arithmetic_adds_up(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    items = digest["digest_items"]
    assert digest["items_total"] == len(items)
    assert digest["items_visible"] == sum(1 for i in items if i["visible"])
    assert digest["items_suppressed"] == sum(1 for i in items if i["suppressed"])


def test_the_digest_header_counts_unverified_deadlines(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    assert digest["items_with_unverified_deadlines"] > 0
    assert digest["items_with_unknown_reporting_burden"] > 0


def test_digest_invariants_reject_a_delivery_claim(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    fails = digest_invariant_failures(dict(digest, delivery_status="sent"))
    assert "digest_claimed_delivery:sent" in fails


def test_digest_invariants_reject_an_email_claim(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    fails = digest_invariant_failures(dict(digest, email_delivery_live=True))
    assert "digest_claimed:email_delivery_live" in fails


def test_digest_invariants_reject_a_shown_suppressed_item(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    items = list(digest["digest_items"])
    for index, item in enumerate(items):
        if item["suppressed"]:
            items[index] = dict(item, visible=True)
    fails = digest_invariant_failures(dict(digest, digest_items=items))
    assert any("suppressed_item_shown" in f for f in fails)


# --------------------------------------------------------------------------
# 104G - readiness
# --------------------------------------------------------------------------


def test_the_preview_is_ready_and_scoped() -> None:
    readiness = build_digest_readiness()
    assert readiness["ready_for_demo_preview"] is True
    assert readiness["demo_scope"] == DEMO_SCOPE
    assert "fixture" in DEMO_SCOPE
    assert not digest_readiness_invariant_failures(readiness)


def test_the_operational_digest_is_not_ready() -> None:
    readiness = build_digest_readiness()
    assert readiness["ready_for_operational_digest"] is False
    assert set(readiness["operational_components_missing"]) == set(
        OPERATIONAL_COMPONENT_KEYS
    )


@pytest.mark.parametrize("key", list(OPERATIONAL_COMPONENT_KEYS))
def test_each_operational_component_is_absent(key: str) -> None:
    assert build_digest_readiness()[key] is False


def test_readiness_claims_no_email_or_coverage() -> None:
    readiness = build_digest_readiness()
    assert readiness["email_delivery_available"] is False
    assert readiness["source_monitoring_live"] is False
    assert readiness["live_source_coverage"] is False
    assert readiness["emails_sent"] == 0
    assert readiness["collectors_active"] == 0


def test_readiness_invariants_reject_forged_operational_readiness() -> None:
    readiness = build_digest_readiness()
    fails = digest_readiness_invariant_failures(
        dict(readiness, ready_for_operational_digest=True)
    )
    assert "operational_readiness_disagrees_with_its_components" in fails


# --------------------------------------------------------------------------
# 104H - demo fixtures
# --------------------------------------------------------------------------


def test_the_fixture_set_is_labelled(fixtures) -> None:
    assert fixtures["fixture_status"] == "demo_fixture"
    assert not demo_fixture_invariant_failures(fixtures)


def test_the_fixture_set_claims_no_live_anything(fixtures) -> None:
    assert fixtures["source_monitoring_live"] is False
    assert fixtures["live_source_coverage"] is False
    assert fixtures["collectors_active"] == 0
    assert fixtures["fetch_performed"] is False
    assert fixtures["email_delivery_live"] is False


def test_no_fixture_names_a_real_tribe(fixtures) -> None:
    assert fixtures["real_tribe_named"] is False
    blob = json.dumps(fixtures).lower()
    for token in REAL_TRIBE_NAME_TOKENS:
        assert token not in blob, token


def test_the_fixture_pair_has_both_snapshots(fixtures) -> None:
    assert fixtures["previous_snapshot"]["row_count"] > 0
    assert fixtures["current_snapshot"]["row_count"] > 0
    assert (
        fixtures["previous_snapshot"]["snapshot_id"]
        != fixtures["current_snapshot"]["snapshot_id"]
    )


def test_the_fixture_includes_a_suppressed_pursuit(fixtures) -> None:
    assert len(fixtures["suppressions"]) == 1
    record = fixtures["suppressions"][0]
    assert record["suppression_status"] == "suppressed_from_new_digest"
    assert record["pursuit_record_id"]


def test_fixture_invariants_reject_a_live_snapshot(fixtures) -> None:
    forged = dict(
        fixtures,
        current_snapshot=dict(
            fixtures["current_snapshot"], snapshot_kind="live_observation"
        ),
    )
    fails = demo_fixture_invariant_failures(forged)
    assert "current_snapshot_is_not_a_demo_fixture" in fails


# --------------------------------------------------------------------------
# 104 - the services do not fetch or send
# --------------------------------------------------------------------------


def _service_source(name: str) -> str:
    return (REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", GATE104_SERVICES)
def test_no_gate104_service_imports_an_http_or_mail_client(name: str) -> None:
    banned = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "urllib3",
        "http.client",
        "socket",
        "smtplib",
        "email.message",
        "boto3",
    }
    tree = ast.parse(_service_source(name))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & banned, f"{name} imports {imported & banned}"


@pytest.mark.parametrize("name", GATE104_SERVICES)
def test_no_gate104_service_imports_a_collector(name: str) -> None:
    tree = ast.parse(_service_source(name))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    offending = {
        m
        for m in modules
        if any(
            token in m
            for token in (
                "polite_http",
                "live_network_guard",
                "real_url_resolver",
                "live_fetch",
                "source_connectors",
                "source_check_bridge",
            )
        )
    }
    assert not offending, f"{name} imports {offending}"


@pytest.mark.parametrize("name", GATE104_SERVICES)
def test_every_gate104_service_declares_a_schema_version(name: str) -> None:
    module = __import__(f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"])
    assert module.SCHEMA_VERSION.startswith("nf_")


# --------------------------------------------------------------------------
# 104I - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_digest_artifacts(repo_root=first)
    write_digest_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("digest artifacts not generated in this tree")
    write_digest_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_six_artifacts_are_written(tmp_path: Path) -> None:
    result = write_digest_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 6
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("digest artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    for key in DECLARATION_KEYS:
        assert key in text, f"{name} omits {key}"


def test_the_artifacts_claim_no_email_or_coverage() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "tenant_nofo_digest_contract.json"
    if not path.exists():
        pytest.skip("digest artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in FALSE_DECLARATION_KEYS:
        assert payload[key] is False, key
    assert payload["digest_contract_available"] is True
    assert payload["weekly_digest_preview_available"] is True


def test_the_preview_artifact_is_labelled_fixture_to_fixture() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "tenant_nofo_digest_preview.json"
    if not path.exists():
        pytest.skip("digest artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["comparison_kind"] == "fixture_to_fixture"
    assert payload["digest"]["delivery_status"] == "preview_only"
    assert payload["digest"]["emails_sent"] == 0


def test_the_suppression_matrix_shows_preservation() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "tenant_pursuit_suppression_matrix.csv"
    if not path.exists():
        pytest.skip("digest artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row = lines[1]
    assert DEMO_TENANT_ID in row
    assert "suppressed_from_new_digest" in row
    # preserved, preserved, visible, not deleted, not global
    assert "True,True,True,False,False" in row


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_digest_artifact_bundle()
    assert artifact_claim_failures(bundle, render_summary(bundle)) == []


def test_the_writer_refuses_a_forged_declaration(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.tenant_nofo_digest_artifact_service as mod

    real = mod.build_digest_artifact_bundle

    def lying():
        bundle = real()
        bundle["declarations"]["email_delivery_available"] = True
        return bundle

    monkeypatch.setattr(mod, "build_digest_artifact_bundle", lying)
    with pytest.raises(TenantDigestArtifactError):
        mod.write_digest_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_a_deletion(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.tenant_nofo_digest_artifact_service as mod

    real = mod.build_digest_artifact_bundle

    def deleting():
        bundle = real()
        records = list(bundle["fixtures"]["suppressions"])
        records[0] = dict(records[0], opportunity_deleted=True)
        bundle["fixtures"] = dict(bundle["fixtures"], suppressions=records)
        return bundle

    monkeypatch.setattr(mod, "build_digest_artifact_bundle", deleting)
    with pytest.raises(TenantDigestArtifactError):
        mod.write_digest_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_no_artifact_contains_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("digest artifacts not generated in this tree")
    for path in sorted(directory.glob("*")):
        text = path.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "eyJ" not in text
        for marker in ("Bearer ", "api_key=", "postgresql://", "password="):
            assert marker not in text, f"{path.name} contains {marker!r}"


def test_the_artifact_dir_is_not_gitignored() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", f"{ARTIFACT_DIR}/{ARTIFACT_NAMES[0]}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert proc.returncode != 0, "digest artifacts are gitignored"


# --------------------------------------------------------------------------
# 104 - cross-cutting
# --------------------------------------------------------------------------


def test_the_gate_sends_nothing_and_deletes_nothing(fixtures, changes) -> None:
    digest = _digest(fixtures, changes)
    readiness = build_digest_readiness()
    assert digest["emails_sent"] == 0
    assert digest["items_deleted"] == 0
    assert changes["rows_deleted"] == 0
    assert readiness["emails_sent"] == 0
    assert readiness["collectors_active"] == 0


def test_no_environment_variable_can_enable_delivery(
    monkeypatch, fixtures, changes
) -> None:
    for name in (
        "NF_EMAIL_DELIVERY_LIVE",
        "NF_DIGEST_SEND",
        "NF_SOURCE_MONITORING_LIVE",
        "NF_LIVE_SOURCE_COVERAGE",
    ):
        monkeypatch.setenv(name, "true")
    digest = _digest(fixtures, changes)
    assert digest["email_delivery_live"] is False
    assert digest["delivery_status"] == "preview_only"
    assert build_digest_readiness()["email_delivery_available"] is False


def test_change_and_comparison_vocabularies_are_closed(changes) -> None:
    assert changes["comparison_kind"] in COMPARISON_KINDS
    for change in changes["changes"]:
        for change_type in change["change_types"]:
            assert change_type in CHANGE_TYPES
    assert HUMAN_REVIEW_CHANGE_TYPES <= CHANGE_TYPES
