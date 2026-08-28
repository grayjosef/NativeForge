"""Tenant pursuit suppression (Gate 104E).

Once a tenant starts pursuing an opportunity, it stops appearing in that tenant's
"new / unpursued" digest. It is not deleted, not hidden from the pipeline, and
not suppressed for anybody else.

## Suppression is a view filter, and nothing else

The four things it must never do, each a constant on every record and each held
by an invariant:

```text
source_history_preserved  true    the opportunity stays in source history
provenance_preserved      true    audit and provenance records are untouched
visible_in_pipeline       true    it stays in the tenant's pursuit pipeline
opportunity_deleted       false   nothing is removed from anywhere
```

A tenant who starts a pursuit and later wants to know why they stopped seeing an
opportunity must be able to find it. Suppression that deletes is indistinguishable
from data loss, and the whole point of the feature is that the item moved rather
than vanished.

## Tenant-specific, never global

`suppress_for_tenant` takes one tenant id and produces one record. There is no
"suppress everywhere" path, and `summarise_suppressions` reports per-tenant
counts so a caller cannot aggregate its way into a global view by accident.

Two tenants pursuing the same opportunity produce two independent records; one
tenant's suppression says nothing about the other's digest. An invariant fails
any record whose tenant id is missing, because a suppression with no owner is a
global one.

## Suppression needs a pursuit record, or a person

```text
pursuit_record_id present  ->  suppressed_from_new_digest
no pursuit record          ->  human_review_required
```

The reason is auditability. A suppression with nothing behind it cannot be
explained six months later, and "why did we stop seeing this?" is exactly the
question an operator asks after missing a deadline. An invariant fails any
suppressed record with neither a pursuit record nor a human review marker.

## Awarded belongs in the Awarded Grants workspace

An opportunity marked awarded is suppressed from the new-opportunity digest and
`visible_in_awarded_workspace` becomes true. Doc 570 is explicit that the pursuit
pipeline and the Awarded Grants workspace are different sections answering
different questions — *should we chase this* versus *what are we now responsible
for* — and this service routes rather than blurs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_pursuit_suppression_v1"

SUPPRESSION_STATUSES = frozenset(
    {
        "not_suppressed",
        "suppressed_from_new_digest",
        "suppressed_from_daily_alert",
        "suppressed_from_weekly_digest",
        "human_review_required",
        "unknown",
    }
)

# Statuses where the item is actually withheld from a digest view.
ACTIVE_SUPPRESSION_STATUSES = frozenset(
    {
        "suppressed_from_new_digest",
        "suppressed_from_daily_alert",
        "suppressed_from_weekly_digest",
    }
)

SUPPRESSION_REASONS = frozenset(
    {
        "pursuit_started",
        "pursuit_submitted",
        "pursuit_awarded",
        "pursuit_declined",
        "tenant_requested",
        "human_review_pending",
        "unknown",
    }
)

# Reasons that mean a pursuit record should exist to back the suppression.
PURSUIT_BACKED_REASONS = frozenset(
    {"pursuit_started", "pursuit_submitted", "pursuit_awarded", "pursuit_declined"}
)

# The reason that routes an item into the Awarded Grants workspace.
AWARDED_REASONS = frozenset({"pursuit_awarded"})

SUPPRESSION_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "opportunity_id",
    "suppression_reason",
    "suppression_status",
    "suppressed_at",
    "pursuit_record_id",
    "audit_event_id",
    "source_history_preserved",
    "provenance_preserved",
    "visible_in_pipeline",
    "visible_in_awarded_workspace",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def build_suppression_id(
    *, tenant_id: Any, opportunity_id: Any, suppressed_at: Any
) -> str:
    """Deterministic, and tenant-scoped by construction."""
    return hashlib.sha256(
        "|".join(
            str(p if p is not None else "")
            for p in (tenant_id, opportunity_id, suppressed_at)
        ).encode("utf-8")
    ).hexdigest()


def suppress_for_tenant(
    *,
    tenant_id: Any,
    opportunity_id: Any,
    suppression_reason: Any = None,
    suppressed_at: Any = None,
    pursuit_record_id: Any = None,
    audit_event_id: Any = None,
    human_review_acknowledged: bool = False,
    suppress_from: Any = None,
) -> dict[str, Any]:
    """Suppress one opportunity for one tenant. Nothing is deleted."""
    reason = _norm(suppression_reason, SUPPRESSION_REASONS, fallback="unknown")
    requested = _norm(
        suppress_from,
        ACTIVE_SUPPRESSION_STATUSES,
        fallback="suppressed_from_new_digest",
    )

    blocked_reasons: list[str] = []

    if not tenant_id:
        blocked_reasons.append("suppression_without_a_tenant")
    if not opportunity_id:
        blocked_reasons.append("suppression_without_an_opportunity")

    # A suppression needs something behind it, or a person.
    backed = bool(pursuit_record_id) or human_review_acknowledged
    if reason in PURSUIT_BACKED_REASONS and not pursuit_record_id:
        blocked_reasons.append(f"{reason}_without_a_pursuit_record")
    if not backed:
        blocked_reasons.append("no_pursuit_record_and_no_human_review")
    if reason == "unknown":
        blocked_reasons.append("suppression_reason_unknown")
    if not audit_event_id:
        blocked_reasons.append("no_audit_event_recorded")

    if not tenant_id or not opportunity_id:
        status = "unknown"
    elif not backed:
        # Not refused outright - held for a person, and still not suppressing.
        status = "human_review_required"
    else:
        status = requested

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "suppression_id": build_suppression_id(
                tenant_id=tenant_id,
                opportunity_id=opportunity_id,
                suppressed_at=suppressed_at,
            ),
            "tenant_id": tenant_id,
            "opportunity_id": opportunity_id,
            "suppression_reason": reason,
            "suppression_status": status,
            "suppressed_at": suppressed_at,
            "pursuit_record_id": pursuit_record_id,
            "audit_event_id": audit_event_id,
            "human_review_acknowledged": bool(human_review_acknowledged),
            # The four that make this a view filter rather than a deletion.
            "source_history_preserved": True,
            "provenance_preserved": True,
            "visible_in_pipeline": True,
            "visible_in_awarded_workspace": reason in AWARDED_REASONS,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: suppression removes nothing from anywhere.
            "opportunity_deleted": False,
            "source_record_deleted": False,
            "provenance_deleted": False,
            "audit_record_deleted": False,
            "suppressed_globally": False,
            "fabricated": False,
        }
    )


def is_suppressed_for_tenant(
    *,
    suppressions: list[dict[str, Any]],
    tenant_id: Any,
    opportunity_id: Any,
    view: str = "new_digest",
) -> bool:
    """Whether this opportunity is withheld from this tenant's view.

    Scoped by tenant id on the way in, so a suppression belonging to another
    tenant can never satisfy this call.
    """
    view_status = {
        "new_digest": "suppressed_from_new_digest",
        "daily_alert": "suppressed_from_daily_alert",
        "weekly_digest": "suppressed_from_weekly_digest",
    }.get(view)
    for record in suppressions:
        if str(record.get("tenant_id")) != str(tenant_id):
            continue
        if str(record.get("opportunity_id")) != str(opportunity_id):
            continue
        status = record.get("suppression_status")
        if status in ACTIVE_SUPPRESSION_STATUSES:
            # `suppressed_from_new_digest` covers the new/unpursued view for
            # every cadence; the narrower statuses apply to their own view only.
            if status == "suppressed_from_new_digest" or status == view_status:
                return True
    return False


def summarise_suppressions(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-tenant counts. There is deliberately no global suppression total."""
    by_tenant: dict[str, int] = {}
    by_status = {status: 0 for status in sorted(SUPPRESSION_STATUSES)}
    for record in records:
        tenant = str(record.get("tenant_id"))
        status = record.get("suppression_status")
        if status in ACTIVE_SUPPRESSION_STATUSES:
            by_tenant[tenant] = by_tenant.get(tenant, 0) + 1
        if status in by_status:
            by_status[status] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(records),
            "suppressed_by_tenant": dict(sorted(by_tenant.items())),
            "by_suppression_status": by_status,
            "tenants_with_suppressions": len(by_tenant),
            "opportunities_deleted": 0,
            "provenance_deleted": 0,
            "suppressed_globally": False,
            "fabricated": False,
        }
    )


def suppression_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for field in SUPPRESSION_FIELDS:
        if field not in record:
            fails.append(f"suppression_missing_field:{field}")

    # Nothing is ever deleted.
    for constant in (
        "opportunity_deleted",
        "source_record_deleted",
        "provenance_deleted",
        "audit_record_deleted",
        "suppressed_globally",
    ):
        if record.get(constant) is not False:
            fails.append(f"suppression_claimed:{constant}")

    # And the preserved facts stay preserved.
    for constant in (
        "source_history_preserved",
        "provenance_preserved",
        "visible_in_pipeline",
    ):
        if record.get(constant) is not True:
            fails.append(f"suppression_dropped:{constant}")

    status = record.get("suppression_status")
    if status not in SUPPRESSION_STATUSES:
        fails.append("suppression_status_out_of_vocabulary")
    if record.get("suppression_reason") not in SUPPRESSION_REASONS:
        fails.append("suppression_reason_out_of_vocabulary")

    # Tenant-specific by construction. A suppression with no owner is global.
    if not record.get("tenant_id"):
        fails.append("suppression_without_a_tenant_is_global")

    # An active suppression needs a pursuit record or an acknowledged review.
    if status in ACTIVE_SUPPRESSION_STATUSES:
        if not record.get("pursuit_record_id") and not record.get(
            "human_review_acknowledged"
        ):
            fails.append("suppressed_without_a_pursuit_record_or_human_review")
        if not record.get("opportunity_id"):
            fails.append("suppressed_without_an_opportunity")

    # Awarded routes to the awarded workspace, and only awarded does.
    if record.get("visible_in_awarded_workspace") != (
        record.get("suppression_reason") in AWARDED_REASONS
    ):
        fails.append("awarded_workspace_visibility_disagrees_with_the_reason")

    # A refusal must name itself.
    if status in {"human_review_required", "unknown"} and not record.get(
        "blocked_reasons"
    ):
        fails.append("suppression_refusal_without_a_reason")

    # Identity reproducible from the record's own fields.
    expected = build_suppression_id(
        tenant_id=record.get("tenant_id"),
        opportunity_id=record.get("opportunity_id"),
        suppressed_at=record.get("suppressed_at"),
    )
    if record.get("suppression_id") != expected:
        fails.append("suppression_id_not_derivable_from_its_fields")

    return fails
