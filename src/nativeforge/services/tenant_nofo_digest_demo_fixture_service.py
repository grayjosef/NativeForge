"""Tenant NOFO digest demo fixtures (Gate 104H).

A labelled two-snapshot pair covering every change type the digest must
demonstrate, built without any collection.

## Why fixtures at all

Doc 570 flagged it and Gate 104A confirmed it: change detection needs two
observations, and with no live collection there is no second one. A recorded pair
is the only honest substrate, and every snapshot here is `demo_fixture` —
`live_observation` is refused by the snapshot contract unless collection status
proves it, so a fixture cannot drift into claiming otherwise.

## What the pair covers

```text
opp-new-match          absent from week 1, matched in week 2
opp-deadline-verified  verified deadline moved  -> deadline_changed
opp-deadline-unverif   unverified date moved    -> deadline_changed_unverified
opp-amended            material amendment       -> amended
opp-excluded           matched -> excluded
opp-downgraded         matched -> downgraded
opp-review             needs human review
opp-suppressed         pursued, so withheld from the new-opportunity view
opp-approaching        verified deadline inside 30 days
opp-removed            present in week 1, absent from week 2
```

Ten opportunities, every required case, and each one exercises a different
refusal rather than a different happy path.

## No real anything

Generic opportunity ids and agency names. No real Tribe is named — Gate 103's
token list is imported and scanned rather than restated. No verified deadline is
fabricated: the two verified deadlines are labelled `verified_deadline` because
the *fixture* asserts its own provenance, which is what a recorded fixture is
allowed to do, and the digest carries that label rather than a bare date.

No reporting requirement is fabricated either — one item is
`unsupported_document_type` and one is `unknown`, which is what the corpus
actually looks like.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tenant_beta_demo_fixture_service import (
    REAL_TRIBE_NAME_TOKENS,
)
from nativeforge.services.tenant_nofo_digest_snapshot_service import (
    build_digest_snapshot,
    build_opportunity_row,
)
from nativeforge.services.tenant_pursuit_suppression_service import (
    suppress_for_tenant,
)

SCHEMA_VERSION = "nf_tenant_nofo_digest_demo_fixture_v1"

DEMO_TENANT_ID = "nf-demo-tenant-01"

# Fixed reference clock. A real `now` would move `approaching_deadline` in and
# out of range and make the artifacts differ between runs.
PREVIOUS_OBSERVED_AT = "2026-01-01T00:00:00+00:00"
CURRENT_OBSERVED_AT = "2026-01-08T00:00:00+00:00"
REFERENCE_NOW = "2026-01-08T00:00:00+00:00"

PERIOD_START = "2026-01-01"
PERIOD_END = "2026-01-08"

# The change cases this fixture must demonstrate. Asserted by test, so a future
# edit that drops one fails rather than quietly narrowing the demo.
REQUIRED_CHANGE_TYPES: tuple[str, ...] = (
    "new_match",
    "deadline_changed",
    "deadline_changed_unverified",
    "amended",
    "newly_excluded",
    "downgraded",
    "human_review_required",
    "approaching_deadline",
    "removed_from_source",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _row(opportunity_id: str, **kwargs: Any) -> dict[str, Any]:
    defaults = {
        "source_id": "demo-source-001",
        "source_name": "Demo Federal Program Office",
        "agency": "Demo Agency",
        "source_kind": "federal_api",
        "federal_scope": True,
        "raw_payload_evidence_status": "not_applicable",
    }
    defaults.update(kwargs)
    return build_opportunity_row(opportunity_id=opportunity_id, **defaults)


def build_previous_snapshot() -> dict[str, Any]:
    """Week one. Every row a fixture, and the snapshot says so."""
    return build_digest_snapshot(
        tenant_id=DEMO_TENANT_ID,
        snapshot_label="demo-week-1",
        snapshot_kind="demo_fixture",
        observed_at=PREVIOUS_OBSERVED_AT,
        source_collection_status="not_active",
        opportunity_rows=[
            _row(
                "opp-deadline-verified",
                title="Tribal Water Infrastructure",
                deadline="2026-06-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["federal scope matches tenant priority"],
                reporting_burden_preview_status="preview_available",
            ),
            _row(
                "opp-deadline-unverif",
                title="Community Facilities Grant",
                deadline="2026-07-01T00:00:00+00:00",
                deadline_provenance_status="unverified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["federal scope matches tenant priority"],
                reporting_burden_preview_status="unknown",
            ),
            _row(
                "opp-amended",
                title="Cultural Preservation Program",
                deadline="2026-08-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["program priority match"],
                reporting_burden_preview_status="partial",
            ),
            _row(
                "opp-excluded",
                title="State Municipal Fund",
                eligibility_match_status="matched",
                tenant_match_reasons=["state scope match"],
                reporting_burden_preview_status="not_assessed",
            ),
            _row(
                "opp-downgraded",
                title="Regional Broadband Initiative",
                eligibility_match_status="matched",
                tenant_match_reasons=["service area overlap"],
                reporting_burden_preview_status="not_assessed",
            ),
            _row(
                "opp-suppressed",
                title="Housing Improvement Program",
                deadline="2026-09-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["program priority match"],
                reporting_burden_preview_status="preview_available",
            ),
            _row(
                "opp-removed",
                title="Withdrawn Pilot Program",
                eligibility_match_status="matched",
                tenant_match_reasons=["federal scope match"],
                reporting_burden_preview_status="unknown",
            ),
        ],
    )


def build_current_snapshot() -> dict[str, Any]:
    """Week two. Same tenant, one week later, still a fixture."""
    return build_digest_snapshot(
        tenant_id=DEMO_TENANT_ID,
        snapshot_label="demo-week-2",
        snapshot_kind="demo_fixture",
        observed_at=CURRENT_OBSERVED_AT,
        source_collection_status="not_active",
        opportunity_rows=[
            _row(
                "opp-new-match",
                title="Tribal Broadband Connectivity",
                deadline="2026-10-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=[
                    "federal scope matches tenant priority",
                    "program area matches a declared tenant priority",
                ],
                reporting_burden_preview_status="preview_available",
                software_capacity_allowability_label="possibly_allowable",
            ),
            _row(
                "opp-deadline-verified",
                title="Tribal Water Infrastructure",
                # Verified on both sides, so this is a real deadline change.
                deadline="2026-05-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["federal scope matches tenant priority"],
                reporting_burden_preview_status="preview_available",
            ),
            _row(
                "opp-deadline-unverif",
                title="Community Facilities Grant",
                # The date moved and nobody can vouch for either side.
                deadline="2026-06-15T00:00:00+00:00",
                deadline_provenance_status="unverified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["federal scope matches tenant priority"],
                reporting_burden_preview_status="unknown",
            ),
            _row(
                "opp-amended",
                title="Cultural Preservation Program",
                deadline="2026-08-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["program priority match"],
                amendment_status="eligibility_change",
                reporting_burden_preview_status="partial",
            ),
            _row(
                "opp-excluded",
                title="State Municipal Fund",
                eligibility_match_status="excluded",
                tenant_exclusion_reasons=[
                    "applicant class restricted to municipalities",
                ],
                reporting_burden_preview_status="not_assessed",
            ),
            _row(
                "opp-downgraded",
                title="Regional Broadband Initiative",
                eligibility_match_status="downgraded",
                tenant_exclusion_reasons=[
                    "match confidence lowered - service area overlap unconfirmed",
                ],
                reporting_burden_preview_status="not_assessed",
            ),
            _row(
                "opp-review",
                title="Multi-Agency Capacity Fund",
                deadline="2026-11-01T00:00:00+00:00",
                deadline_provenance_status="suspected_placeholder",
                eligibility_match_status="needs_human_review",
                human_review_reasons=[
                    "recognition status required by this program is unknown "
                    "for this tenant",
                ],
                reporting_burden_preview_status="unsupported_document_type",
            ),
            _row(
                "opp-approaching",
                title="Emergency Preparedness Supplement",
                # Inside 30 days of the reference clock, and verified.
                deadline="2026-01-25T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["federal scope matches tenant priority"],
                reporting_burden_preview_status="preview_available",
            ),
            _row(
                "opp-suppressed",
                title="Housing Improvement Program",
                deadline="2026-09-01T00:00:00+00:00",
                deadline_provenance_status="verified_deadline",
                eligibility_match_status="matched",
                tenant_match_reasons=["program priority match"],
                reporting_burden_preview_status="preview_available",
                pursuit_status="pursuing",
                suppression_status="suppressed_from_new_digest",
            ),
        ],
    )


def build_demo_suppressions() -> list[dict[str, Any]]:
    """One pursued opportunity, suppressed for this tenant only."""
    return [
        suppress_for_tenant(
            tenant_id=DEMO_TENANT_ID,
            opportunity_id="opp-suppressed",
            suppression_reason="pursuit_started",
            suppressed_at=CURRENT_OBSERVED_AT,
            pursuit_record_id="demo-pursuit-0001",
            audit_event_id="demo-audit-0001",
        )
    ]


def build_digest_demo_fixture_set() -> dict[str, Any]:
    """Both snapshots, the suppression, and what the pair is for."""
    previous = build_previous_snapshot()
    current = build_current_snapshot()
    suppressions = build_demo_suppressions()

    blob = json.dumps([previous, current, suppressions]).lower()
    named = [token for token in REAL_TRIBE_NAME_TOKENS if token in blob]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": DEMO_TENANT_ID,
            "fixture_status": "demo_fixture",
            "previous_snapshot": previous,
            "current_snapshot": current,
            "suppressions": suppressions,
            "reference_now": REFERENCE_NOW,
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "required_change_types": list(REQUIRED_CHANGE_TYPES),
            "real_tribe_named": bool(named),
            "blocked_reasons": sorted(
                {
                    "demo_fixture_snapshots_are_not_live_observations",
                    "no_source_collection_occurred",
                    *previous["blocked_reasons"],
                    *current["blocked_reasons"],
                }
            ),
            # A fixture is not collection, monitoring, or coverage.
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "collectors_active": 0,
            "fetch_performed": False,
            "email_delivery_live": False,
            "fabricated": False,
        }
    )


def demo_fixture_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if fixture.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "live_source_coverage",
        "fetch_performed",
        "email_delivery_live",
        "real_tribe_named",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"fixture_claimed:{constant}")
    if fixture.get("collectors_active") != 0:
        fails.append("fixture_claimed_active_collectors")

    if fixture.get("fixture_status") != "demo_fixture":
        fails.append("fixture_set_not_marked_demo_fixture")

    # Both snapshots must be fixtures, never live observations.
    for key in ("previous_snapshot", "current_snapshot"):
        snapshot = fixture.get(key) or {}
        if snapshot.get("snapshot_kind") != "demo_fixture":
            fails.append(f"{key}_is_not_a_demo_fixture")
        if snapshot.get("source_collection_status") == "collected":
            fails.append(f"{key}_claimed_collection")

    # Suppressions stay tenant-scoped and delete nothing.
    for record in fixture.get("suppressions") or []:
        if record.get("tenant_id") != fixture.get("tenant_id"):
            fails.append("suppression_for_a_different_tenant")
        if record.get("opportunity_deleted") is not False:
            fails.append("fixture_suppression_deleted_an_opportunity")

    if not fixture.get("blocked_reasons"):
        fails.append("fixture_set_without_a_caveat")

    return fails
