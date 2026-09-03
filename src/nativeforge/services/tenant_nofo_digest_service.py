"""Gate 140C: the org-scoped digest preview, assembled from what is stored.

Gate 104 built every component of a digest — snapshots, change detection,
per-item explanations, suppression, a weekly-default builder — and wired none of
them to an organization or a request. `ready_for_demo_preview` has been true for
thirty-six gates with nothing able to ask for one.

This is the assembler: it reads the tenant's profile, its watchlist and its
persisted suppressions, all anchored on `organization_id`, and hands them to the
Gate 104 builder.

## What it does not do

```text
live source calls   none. The candidates are labelled fixture snapshots, and
                    every response carries live_source_coverage: false.
email               none. There is no email service in this repository and
                    delivery_status may only be preview_only.
monitoring claims   source_monitoring_live is False in every response and an
                    invariant fails if it is ever true.
fabrication         no eligibility is invented, no deadline is computed. Both
                    come from the snapshot row, with their provenance status.
```

## Weekly is the default and daily is opt-in

From the tenant's own profile. `nf_tenant_beta_profiles.digest_frequency` is
`daily | weekly | none`, and a daily digest for a profile that has not enabled
daily is refused by the Gate 104 builder with a reason rather than produced.

That setting is a stored column, so enabling and disabling it is a profile
write — not a flag this service keeps.

## UNKNOWN survives

An item whose eligibility is unknown stays unknown; one whose deadline nobody
has verified is reported with `due_date_status` saying so, and the digest header
counts both. The item fields this service emits include
`eligibility_status`, `eligibility_evidence`, `due_date_status` and `blockers`
precisely so an uncertain item can be shown as uncertain rather than dropped or
rounded up.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

SCHEMA_VERSION = "nf_tenant_nofo_digest_service_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

DEFAULT_CADENCE = "weekly"

#: The fields every digest item carries, in the order the brief names them.
#: Declared so a test can assert a real item against it rather than against a
#: reader's memory.
DIGEST_ITEM_FIELDS: tuple[str, ...] = (
    "opportunity_id",
    "source",
    "title",
    "jurisdiction",
    "program_area",
    "due_date",
    "due_date_status",
    "match_reason",
    "eligibility_status",
    "eligibility_evidence",
    "blockers",
    "recommended_action",
    "pursuit_status",
    "digest_visibility_status",
)

#: Statuses that mean nobody has established the fact. They must survive the
#: assembly rather than being rounded to a yes or a no.
UNRESOLVED_STATUSES: frozenset[str] = frozenset(
    {"unknown", "needs_human_review", "unsupported"}
)

DAILY_NOT_ENABLED = "daily_digest_requested_but_the_profile_has_not_enabled_it"
NO_PROFILE = "no_tenant_profile_for_this_organization"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _recommended_action(row: dict[str, Any], explanation: dict[str, Any]) -> str:
    """What a person should do next, from the row's own uncertainty.

    Never "apply". This service does not know whether a tenant should apply for
    anything, and a recommendation that implied it would be the fabrication the
    whole eligibility contract exists to prevent.
    """
    if str(row.get("eligibility_match_status") or "") in UNRESOLVED_STATUSES:
        return "review_eligibility_with_a_human"
    if not row.get("deadline_verified"):
        return "verify_the_deadline_against_the_notice"
    if explanation.get("human_review_reasons"):
        return "resolve_the_named_human_review_reasons"
    return "review_and_decide_whether_to_pursue"


def _item(
    row: dict[str, Any], explanation: dict[str, Any], *, visibility: str
) -> dict[str, Any]:
    """One digest item, in the declared shape.

    Every uncertain field keeps its status. Nothing is defaulted to a
    confident value: an absent deadline stays absent and reports why.
    """
    match_reasons = list(row.get("tenant_match_reasons") or [])
    exclusions = list(row.get("tenant_exclusion_reasons") or [])
    blockers = sorted(
        set(
            list(explanation.get("human_review_reasons") or [])
            + list(row.get("human_review_reasons") or [])
            + exclusions
        )
    )

    return {
        "opportunity_id": row.get("opportunity_id"),
        "source": row.get("source_name") or row.get("source_id"),
        "source_id": row.get("source_id"),
        "title": row.get("title"),
        "jurisdiction": row.get("state_scope") or row.get("federal_scope"),
        "program_area": row.get("agency"),
        "due_date": row.get("deadline"),
        # The provenance status, never a guess. An unverified deadline says so.
        "due_date_status": row.get("deadline_provenance_status") or "unknown",
        "due_date_verified": bool(row.get("deadline_verified")),
        "match_reason": match_reasons,
        "eligibility_status": row.get("eligibility_match_status") or "unknown",
        "eligibility_evidence": {
            "confidence": row.get("eligibility_confidence") or "unknown",
            "match_reasons": match_reasons,
            "exclusion_reasons": exclusions,
            "raw_payload_evidence_status": row.get("raw_payload_evidence_status")
            or "unknown",
        },
        "blockers": blockers,
        "recommended_action": _recommended_action(row, explanation),
        "pursuit_status": row.get("pursuit_status") or "not_pursued",
        "digest_visibility_status": visibility,
        # Per item, so a reader of one line does not have to find the header.
        "live_source_coverage": False,
        "source_monitoring_live": False,
    }


def build_org_digest_preview(
    *,
    connection: Any = None,
    organization_id: Any = None,
    cadence: Any = None,
    profile: dict[str, Any] | None = None,
    current_snapshot: dict[str, Any] | None = None,
    previous_snapshot: dict[str, Any] | None = None,
    now: Any = None,
    **offered: Any,
) -> dict[str, Any]:
    """Assemble one organization's digest preview. Calls no source, sends no mail."""
    from nativeforge.services.tenant_nofo_digest_builder_service import (
        build_tenant_digest,
    )
    from nativeforge.services.tenant_nofo_digest_change_detection_service import (
        detect_digest_changes,
    )
    from nativeforge.services.tenant_nofo_digest_demo_fixture_service import (
        build_digest_demo_fixture_set,
    )
    from nativeforge.services.tenant_nofo_digest_item_explanation_service import (
        build_digest_item_explanation,
    )
    from nativeforge.services.tenant_pursuit_suppression_repository_service import (
        list_suppressions,
    )
    from nativeforge.services.tenant_source_watchlist_service import list_watchlist

    anchor = _as_uuid(organization_id)
    blocked: list[str] = []
    caveats: list[str] = []

    for key in ("tenant_id", "customer_org_id", "organization_profile_id"):
        if str(offered.get(key) or "").strip():
            blocked.append(f"not_an_anchor_for_a_digest:{key}")

    if anchor is None:
        blocked.append("digest_without_an_organization_id_anchor")

    # -- the profile, which carries the cadence the tenant chose ------------
    resolved_profile = profile
    if resolved_profile is None and connection is not None and anchor is not None:
        from nativeforge.services.tenant_profile_repository_service import (
            get_tenant_profile,
        )

        found = get_tenant_profile(connection=connection, organization_id=str(anchor))
        resolved_profile = found if found.get("rows_read") else None
    if resolved_profile is None:
        blocked.append(NO_PROFILE)

    profile_frequency = (
        str((resolved_profile or {}).get("digest_frequency") or "").strip().lower()
    )
    daily_enabled = profile_frequency == "daily"

    requested = str(cadence or DEFAULT_CADENCE).strip().lower() or DEFAULT_CADENCE
    if requested == "daily" and not daily_enabled:
        blocked.append(DAILY_NOT_ENABLED)

    # -- the watchlist and the suppressions, both org-anchored --------------
    watchlist = (
        list_watchlist(connection=connection, organization_id=str(anchor))
        if connection is not None and anchor is not None
        else {"entries": [], "rows_read": 0}
    )
    stored = (
        list_suppressions(connection=connection, organization_id=str(anchor))
        if connection is not None and anchor is not None
        else {"suppressions": [], "rows_read": 0}
    )
    suppressions = list(stored.get("suppressions") or [])

    # -- the candidates: labelled fixture snapshots, never a live fetch -----
    fixtures = build_digest_demo_fixture_set()
    current = (
        current_snapshot
        if current_snapshot is not None
        else fixtures["current_snapshot"]
    )
    previous = (
        previous_snapshot
        if previous_snapshot is not None
        else fixtures["previous_snapshot"]
    )

    changes = detect_digest_changes(
        tenant_id=str(anchor) if anchor else "",
        previous_snapshot=previous,
        current_snapshot=current,
    )

    digest: dict[str, Any] = {}
    if not blocked:
        digest = build_tenant_digest(
            # The organization id, which is what the suppressions were
            # anchored on. The Gate 104 builder uses this field as an opaque
            # key, so handing it the anchor keeps the two consistent without
            # either treating a tenant label as authority.
            tenant_id=str(anchor),
            current_snapshot=current,
            change_detection=changes,
            previous_snapshot=previous,
            suppressions=suppressions,
            cadence=requested,
            daily_alerts_enabled=daily_enabled,
        )
        # The Gate 104 builder's `blocked_reasons` are CAVEATS about the
        # digest's content, not reasons it was not produced:
        #
        #     items_with_unverified_deadlines:5
        #     comparison_between_recorded_snapshots_not_live_checks
        #     no_email_delivery_service_exists
        #
        # Every one is true and none of them stops a preview. Folding them
        # into `blocked_reasons` made a working digest report itself blocked -
        # the same wrong-list mistake Gate 138F made putting a
        # production-write blocker into a customer-auth list, and it would
        # have made "blocked" mean nothing here too.
        caveats.extend(digest.get("blocked_reasons") or [])

    # -- the items, in the declared shape ----------------------------------
    suppressed_ids = {
        record["opportunity_id"]
        for record in suppressions
        if not record.get("lifted_at")
    }
    rows = list(current.get("opportunity_rows") or [])
    visible: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    for row in rows:
        explanation = build_digest_item_explanation(
            tenant_id=str(anchor) if anchor else "", opportunity_row=row
        )
        if row.get("opportunity_id") in suppressed_ids:
            withheld.append(_item(row, explanation, visibility="suppressed"))
        else:
            visible.append(_item(row, explanation, visibility="visible"))

    unresolved_eligibility = sum(
        1 for item in visible if item["eligibility_status"] in UNRESOLVED_STATUSES
    )
    unverified_deadlines = sum(1 for item in visible if not item["due_date_verified"])

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "organization_id": str(anchor) if anchor else None,
            "cadence": requested,
            "default_cadence": DEFAULT_CADENCE,
            "daily_alerts_enabled": daily_enabled,
            "profile_digest_frequency": profile_frequency or None,
            "watchlist_entry_count": int(watchlist.get("rows_read") or 0),
            "suppression_count": len(suppressed_ids),
            "items": visible,
            "items_visible": len(visible),
            "items_suppressed": len(withheld),
            "items_total": len(rows),
            "suppressed_items": withheld,
            # Counted on the face of it, as the Gate 104 builder does.
            "items_with_unresolved_eligibility": unresolved_eligibility,
            "items_with_unverified_deadlines": unverified_deadlines,
            "digest_id": digest.get("digest_id"),
            "delivery_status": digest.get("delivery_status", "preview_only"),
            # Constants, and an invariant refuses each of them.
            "live_source_coverage": False,
            "source_monitoring_live": False,
            "email_delivery_live": False,
            "emails_sent": 0,
            "live_source_called": False,
            "collectors_active": 0,
            "network_calls": 0,
            "fabricated": False,
            "candidate_provenance": "labelled_fixture_snapshots",
            # What is true of this digest's content, kept apart from what
            # stopped it being produced.
            "caveats": sorted(set(caveats)),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def digest_preview_invariant_failures(preview: dict[str, Any]) -> list[str]:
    """What must never be true of a digest preview."""
    fails: list[str] = []

    for field in (
        "live_source_coverage",
        "source_monitoring_live",
        "email_delivery_live",
        "live_source_called",
        "fabricated",
    ):
        if preview.get(field):
            fails.append(f"claimed:{field}")
    for field in ("emails_sent", "collectors_active", "network_calls"):
        if preview.get(field):
            fails.append(f"nonzero:{field}")

    if preview.get("delivery_status") not in {"preview_only", "not_configured", None}:
        fails.append(f"delivery_status_claimed:{preview.get('delivery_status')}")

    # The arithmetic, which is what stops a digest hiding something quietly.
    total = int(preview.get("items_total") or 0)
    visible = int(preview.get("items_visible") or 0)
    suppressed = int(preview.get("items_suppressed") or 0)
    if total and visible + suppressed != total:
        fails.append(f"items_do_not_add_up:{visible}+{suppressed}!={total}")

    if preview.get("cadence") == "daily" and not preview.get("daily_alerts_enabled"):
        if not preview.get("blocked_reasons"):
            fails.append("a_daily_digest_was_produced_without_the_setting")

    # A digest that was PRODUCED with unverified deadlines must say so.
    # Counting them and then saying nothing would be the quiet rounding-up
    # this whole contract exists to prevent.
    #
    # Only when it was produced: a refused digest never reached the builder,
    # so it has no caveats to report and demanding them made a correct
    # refusal fail an invariant.
    if (
        not preview.get("blocked_reasons")
        and preview.get("items_with_unverified_deadlines")
        and not preview.get("caveats")
    ):
        fails.append("unverified_deadlines_counted_and_no_caveat_recorded")

    for item in preview.get("items") or []:
        missing = [field for field in DIGEST_ITEM_FIELDS if field not in item]
        if missing:
            fails.append(f"item_missing_fields:{item.get('opportunity_id')}:{missing}")
        if item.get("source_monitoring_live"):
            fails.append(f"item_claimed_monitoring:{item.get('opportunity_id')}")
        # A confident status with no evidence behind it is the fabrication.
        evidence = item.get("eligibility_evidence") or {}
        if item.get("eligibility_status") not in UNRESOLVED_STATUSES and not (
            evidence.get("match_reasons") or evidence.get("exclusion_reasons")
        ):
            fails.append(
                f"eligibility_claimed_without_evidence:{item.get('opportunity_id')}"
            )
        # And a verified deadline with no date is a claim about nothing.
        if item.get("due_date_verified") and not item.get("due_date"):
            fails.append(
                f"deadline_verified_without_a_date:{item.get('opportunity_id')}"
            )

    return fails
