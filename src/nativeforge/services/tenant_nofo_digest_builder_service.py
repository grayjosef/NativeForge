"""Tenant NOFO digest builder (Gate 104F).

Assembles a weekly or daily digest from snapshots, change detection,
explanations and suppression state. It builds a preview. It sends nothing.

## Preview only, and the field says so

```text
delivery_status        preview_only
email_delivery_live    false
source_monitoring_live false
live_source_coverage   false
```

There is no email service in this repository — Gate 103 found zero, Gate 104A
confirmed it. `delivery_status` may only be `preview_only` or `not_configured`
here, and an invariant fails `queued`, `sent` or anything else. A digest that
could report itself sent would be a digest somebody eventually believes was.

## Weekly is the default; daily is opt-in

Per the product requirement, and matching Gate 103C's entitlement default. A
daily digest built for a tenant whose profile does not enable daily alerts is
refused with a reason rather than silently produced.

## Suppressed items are counted, not deleted

The distinction that keeps the digest honest. A suppressed opportunity is removed
from the **visible** list and still appears in `items_suppressed`, so a tenant can
always see that four things were withheld and go look at them in the pipeline.

```text
items_total      everything the comparison produced
items_visible    what the tenant is shown
items_suppressed withheld from this view, still counted
```

`items_total` equals visible plus suppressed plus unchanged, and an invariant
checks the arithmetic. A digest whose totals do not add up is hiding something,
whether or not anybody meant it to.

## Unverified deadlines and unknown burdens are counted on the face of it

`items_with_unverified_deadlines` and `items_with_unknown_reporting_burden` sit
in the digest header rather than being buried per-item. A weekly digest where
nine of eleven deadlines cannot be vouched for should say so at the top.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.tenant_nofo_digest_change_detection_service import (
    ACTIONABLE_CHANGE_TYPES,
    change_detection_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_item_explanation_service import (
    VISIBLE_ITEM_STATUSES,
    build_digest_item_explanation,
)
from nativeforge.services.tenant_pursuit_suppression_service import (
    is_suppressed_for_tenant,
)

SCHEMA_VERSION = "nf_tenant_nofo_digest_builder_v1"

CADENCES = frozenset({"weekly", "daily", "manual_preview", "unknown"})
DEFAULT_CADENCE = "weekly"

DELIVERY_STATUSES = frozenset(
    {"not_configured", "preview_only", "queued", "sent", "failed", "unknown"}
)

# The only statuses this gate may produce. Anything further needs a delivery
# path that does not exist.
PREVIEW_DELIVERY_STATUSES = frozenset({"preview_only", "not_configured"})

# Statuses that assert something left the building.
DELIVERED_STATUSES = frozenset({"queued", "sent"})

DIGEST_FIELDS: tuple[str, ...] = (
    "digest_id",
    "tenant_id",
    "cadence",
    "period_start",
    "period_end",
    "snapshot_ids",
    "delivery_status",
    "email_delivery_live",
    "source_monitoring_live",
    "live_source_coverage",
    "items_total",
    "items_visible",
    "items_suppressed",
    "items_human_review",
    "items_with_unverified_deadlines",
    "items_with_unknown_reporting_burden",
    "digest_items",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_digest_id(
    *, tenant_id: Any, cadence: Any, period_start: Any, period_end: Any
) -> str:
    """Deterministic from the digest's own period, with no clock in it."""
    return hashlib.sha256(
        "|".join(
            str(p if p is not None else "")
            for p in (tenant_id, cadence, period_start, period_end)
        ).encode("utf-8")
    ).hexdigest()


def build_tenant_digest(
    *,
    tenant_id: Any,
    current_snapshot: dict[str, Any],
    change_detection: dict[str, Any],
    previous_snapshot: dict[str, Any] | None = None,
    suppressions: list[dict[str, Any]] | None = None,
    cadence: Any = None,
    period_start: Any = None,
    period_end: Any = None,
    daily_alerts_enabled: bool = False,
    nativeforge_self_assessed_opportunity_ids: list[Any] | None = None,
) -> dict[str, Any]:
    """One tenant digest. Nothing is sent and nothing is deleted."""
    requested_cadence = str(cadence).strip() if cadence else DEFAULT_CADENCE
    resolved_cadence = (
        requested_cadence if requested_cadence in CADENCES else DEFAULT_CADENCE
    )

    blocked_reasons: list[str] = []

    # Daily is opt-in. A daily digest for a tenant without it falls back.
    if resolved_cadence == "daily" and not daily_alerts_enabled:
        blocked_reasons.append("daily_alerts_not_enabled_for_this_tenant")
        resolved_cadence = DEFAULT_CADENCE

    # Validate the input rather than trusting it. A digest built on a change
    # detection that failed its own invariants would inherit the failure
    # silently, and the digest is the surface a tenant actually reads.
    upstream_failures = change_detection_invariant_failures(change_detection)
    if upstream_failures:
        blocked_reasons.extend(
            f"change_detection_invariant:{f}" for f in upstream_failures
        )

    suppression_records = list(suppressions or [])
    self_assessed = {
        str(o) for o in (nativeforge_self_assessed_opportunity_ids or [])
    }

    rows_by_id = {
        str(r.get("opportunity_id")): r
        for r in current_snapshot.get("opportunity_rows") or []
    }
    changes_by_id = {
        str(c.get("opportunity_id")): c
        for c in change_detection.get("changes") or []
    }

    items: list[dict[str, Any]] = []
    for opportunity_id in sorted(changes_by_id):
        change = changes_by_id[opportunity_id]
        row = rows_by_id.get(opportunity_id)
        if row is None:
            # A removal: the row is only in the previous snapshot. The change
            # record carries it, so the item is still explainable.
            row = change.get("previous_row") or {"opportunity_id": opportunity_id}

        explanation = build_digest_item_explanation(
            tenant_id=tenant_id,
            opportunity_row=row,
            change=change,
            allowability_is_nativeforge_itself=opportunity_id in self_assessed,
        )

        suppressed = is_suppressed_for_tenant(
            suppressions=suppression_records,
            tenant_id=tenant_id,
            opportunity_id=opportunity_id,
            view="daily_alert" if resolved_cadence == "daily" else "weekly_digest",
        )

        actionable = bool(
            set(change.get("change_types") or []) & ACTIONABLE_CHANGE_TYPES
        )
        visible = (
            not suppressed
            and actionable
            and explanation["digest_item_status"] in VISIBLE_ITEM_STATUSES
        )

        items.append(
            {
                "opportunity_id": opportunity_id,
                "digest_item_status": explanation["digest_item_status"],
                "headline": explanation["headline"],
                "change_types": sorted(change.get("change_types") or []),
                "visible": visible,
                "suppressed": suppressed,
                "requires_human_review": bool(change.get("requires_human_review"))
                or explanation["digest_item_status"] == "needs_human_review",
                "deadline_verified": explanation["deadline_verified"],
                "deadline_note": explanation["deadline_note"],
                "reporting_burden_status": explanation["reporting_burden_status"],
                "allowability_label": explanation["allowability_label"],
                "allowability_self_assessment_capped": explanation[
                    "allowability_self_assessment_capped"
                ],
                "why_this_matches": explanation["why_this_matches"],
                "why_this_may_not_match": explanation["why_this_may_not_match"],
                "explanation": explanation,
                # An item is a row in a preview. It has not been delivered.
                "delivered": False,
            }
        )

    items.sort(key=lambda i: str(i["opportunity_id"]))

    visible_items = [i for i in items if i["visible"]]
    suppressed_items = [i for i in items if i["suppressed"]]
    review_items = [i for i in items if i["requires_human_review"]]
    unverified = [i for i in items if not i["deadline_verified"]]
    unknown_burden = [
        i
        for i in items
        if i["reporting_burden_status"] not in {"preview_available", "partial"}
    ]

    snapshot_ids = [
        s.get("snapshot_id")
        for s in (previous_snapshot, current_snapshot)
        if s is not None
    ]

    # No delivery path exists, so the strongest honest status is preview_only.
    delivery_status = "preview_only"
    blocked_reasons.append("no_email_delivery_service_exists")
    if suppressed_items:
        blocked_reasons.append(f"items_suppressed:{len(suppressed_items)}")
    if unverified:
        blocked_reasons.append(f"items_with_unverified_deadlines:{len(unverified)}")
    if unknown_burden:
        blocked_reasons.append(
            f"items_with_unknown_reporting_burden:{len(unknown_burden)}"
        )
    blocked_reasons.extend(change_detection.get("blocked_reasons") or [])

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "digest_id": build_digest_id(
                tenant_id=tenant_id,
                cadence=resolved_cadence,
                period_start=period_start,
                period_end=period_end,
            ),
            "tenant_id": tenant_id,
            "cadence": resolved_cadence,
            "requested_cadence": requested_cadence,
            "period_start": period_start,
            "period_end": period_end,
            "snapshot_ids": snapshot_ids,
            "comparison_kind": change_detection.get("comparison_kind"),
            "delivery_status": delivery_status,
            "items_total": len(items),
            "items_visible": len(visible_items),
            "items_suppressed": len(suppressed_items),
            "items_human_review": len(review_items),
            "items_with_unverified_deadlines": len(unverified),
            "items_with_unknown_reporting_burden": len(unknown_burden),
            "digest_items": items,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Nothing left the building.
            "email_delivery_live": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "emails_sent": 0,
            "items_deleted": 0,
            "fabricated": False,
        }
    )


def digest_invariant_failures(digest: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if digest.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if digest.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "email_delivery_live",
        "source_monitoring_live",
        "live_source_coverage",
    ):
        if digest.get(constant) is not False:
            fails.append(f"digest_claimed:{constant}")
    if digest.get("emails_sent") != 0:
        fails.append("digest_sent_email")
    if digest.get("items_deleted") != 0:
        fails.append("digest_deleted_items")

    for field in DIGEST_FIELDS:
        if field not in digest:
            fails.append(f"digest_missing_field:{field}")

    cadence = digest.get("cadence")
    if cadence not in CADENCES:
        fails.append("cadence_out_of_vocabulary")

    # Preview only.
    delivery = digest.get("delivery_status")
    if delivery not in DELIVERY_STATUSES:
        fails.append("delivery_status_out_of_vocabulary")
    if delivery in DELIVERED_STATUSES:
        fails.append(f"digest_claimed_delivery:{delivery}")
    if delivery not in PREVIEW_DELIVERY_STATUSES:
        fails.append("delivery_status_beyond_preview")

    items = digest.get("digest_items")
    if not isinstance(items, list):
        fails.append("digest_items_not_a_list")
        return fails

    for item in items:
        if item.get("delivered") is not False:
            fails.append(f"item_claimed_delivery:{item.get('opportunity_id')}")
        # A suppressed item is never shown, and is never dropped.
        if item.get("suppressed") and item.get("visible"):
            fails.append(f"suppressed_item_shown:{item.get('opportunity_id')}")

    # The arithmetic has to add up, or something is hidden.
    if digest.get("items_total") != len(items):
        fails.append("items_total_disagrees_with_the_items")
    if digest.get("items_visible") != sum(1 for i in items if i.get("visible")):
        fails.append("items_visible_disagrees_with_the_items")
    if digest.get("items_suppressed") != sum(1 for i in items if i.get("suppressed")):
        fails.append("items_suppressed_disagrees_with_the_items")
    if digest.get("items_with_unverified_deadlines") != sum(
        1 for i in items if not i.get("deadline_verified")
    ):
        fails.append("unverified_count_disagrees_with_the_items")

    # Suppressed items are counted, never deleted.
    if digest.get("items_suppressed") and not any(
        i.get("suppressed") for i in items
    ):
        fails.append("suppressed_items_counted_but_absent")

    # A digest with nothing delivered must say why.
    if not digest.get("blocked_reasons"):
        fails.append("preview_digest_without_a_caveat")

    # Identity reproducible from its own fields.
    expected = build_digest_id(
        tenant_id=digest.get("tenant_id"),
        cadence=digest.get("cadence"),
        period_start=digest.get("period_start"),
        period_end=digest.get("period_end"),
    )
    if digest.get("digest_id") != expected:
        fails.append("digest_id_not_derivable_from_its_fields")

    return fails
