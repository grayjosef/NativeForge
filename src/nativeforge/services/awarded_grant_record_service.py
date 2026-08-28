"""Awarded grant record, tenant lane (Gate 108B).

An active award record, distinct from the pursuit opportunity it came from.

## This does not replace Gate 91

`awarded_grant_portfolio_service` already owns the award record: its lifecycle
statuses, its required detail fields, and the rule that a missing award date
produces a review item rather than a computed one. That service is imported and
its vocabulary is bridged, not restated.

What this adds is the tenant-lane surface. Gates 103 and 104 built the tenant
beta contract around `tenant_id`; Gates 90 and 91 built the awarded lane around
`customer_org_id`. This record sits exactly on that seam.

## Two identity spaces, deliberately not merged

```text
customer_org_id   Gates 90-91   grant_lane_separation, awarded_grant_portfolio,
                                award_transition
tenant_id         Gates 103-104 the tenant beta lane
```

There is no bridge between them anywhere in the tree, and this gate does not
invent one. Declaring that one tenant equals one customer org is a product and
data-model claim nobody has verified, and a silent equivalence between two
identity spaces is how a cross-tenant leak gets built.

So both ids are carried, both must be supplied by the caller, and neither is
derived from the other:

```text
tenant_org_binding_status   caller_supplied   both ids given
                            unknown           one is missing
```

An invariant fails a record claiming `caller_supplied` without both. Reconciling
the two spaces is follow-up work, named in doc 594 and not attempted here.

## An award may exist before anyone knows what it obliges

The state this contract is built to allow. A tenant can mark a grant awarded on
the day they get the letter, months before anyone reads the terms.

```text
requirements_extraction_status   unknown or needs_human_review is normal
active_obligations_created       false until evidence or a person says otherwise
```

That is not a degraded record. It is an honest one, and refusing to create it
until requirements are known would push tenants into tracking awards in a
spreadsheet - which is the problem the product exists to solve.

## Pursuit history is not consumed

Creating an award does not delete, close or rewrite the pursuit record it came
from. `source_opportunity_id` and `pursuit_record_id` are both carried, and
constants assert that neither history was touched.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.awarded_grant_portfolio_service import (
    LIFECYCLE_STATUSES as PORTFOLIO_LIFECYCLE_STATUSES,
)
from nativeforge.services.awarded_grant_portfolio_service import (
    REQUIRED_AWARD_DETAIL_FIELDS,
)

SCHEMA_VERSION = "nf_awarded_grant_record_v1"

AWARD_STATUSES = frozenset(
    {
        "draft_award_record",
        "active_award",
        "closeout_pending",
        "closed",
        "cancelled",
        "mistaken_award",
        "unknown",
    }
)

# Gate 91's four lifecycle statuses mapped onto the seven above. Imported so the
# two vocabularies stay related; a test fails if Gate 91 grows one this misses.
PORTFOLIO_LIFECYCLE_TO_AWARD_STATUS: dict[str, str] = {
    "awarded_active": "active_award",
    "awarded_closeout": "closeout_pending",
    "awarded_closed": "closed",
    "unknown": "unknown",
}

# Statuses where the tenant currently holds obligations.
LIVE_AWARD_STATUSES = frozenset({"active_award", "closeout_pending"})

REQUIREMENTS_EXTRACTION_STATUSES = frozenset(
    {
        "not_attempted",
        "human_entered",
        "evidence_extracted",
        "unsupported_document_type",
        "needs_human_review",
        "unknown",
    }
)

# Extraction outcomes that can support an active obligation.
OBLIGATION_CAPABLE_EXTRACTION = frozenset({"human_entered", "evidence_extracted"})

TENANT_ORG_BINDING_STATUSES = frozenset({"caller_supplied", "unknown"})

AWARD_RECORD_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "award_id",
    "source_opportunity_id",
    "pursuit_record_id",
    "award_title",
    "funding_agency",
    "assistance_listing_numbers",
    "award_number",
    "award_status",
    "award_start_date",
    "award_end_date",
    "performance_period",
    "total_award_amount",
    "match_required",
    "match_amount",
    "match_percent",
    "award_document_status",
    "requirements_extraction_status",
    "human_review_required",
    "evidence_status",
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


def build_award_id(
    *, tenant_id: Any, source_opportunity_id: Any, award_number: Any
) -> str:
    """Deterministic and tenant-scoped by construction."""
    return hashlib.sha256(
        "|".join(
            str(part if part is not None else "")
            for part in (tenant_id, source_opportunity_id, award_number)
        ).encode()
    ).hexdigest()


def build_awarded_grant_record(
    *,
    tenant_id: Any,
    source_opportunity_id: Any = None,
    pursuit_record_id: Any = None,
    customer_org_id: Any = None,
    award_title: Any = None,
    funding_agency: Any = None,
    assistance_listing_numbers: Any = None,
    award_number: Any = None,
    award_status: Any = None,
    award_start_date: Any = None,
    award_end_date: Any = None,
    total_award_amount: Any = None,
    match_required: Any = None,
    match_amount: Any = None,
    match_percent: Any = None,
    award_document_status: Any = None,
    requirements_extraction_status: Any = None,
    human_review_acknowledged: bool = False,
) -> dict[str, Any]:
    """One awarded grant for one tenant. Nothing about it is inferred."""
    status = _norm(award_status, AWARD_STATUSES, fallback="draft_award_record")
    extraction = _norm(
        requirements_extraction_status,
        REQUIREMENTS_EXTRACTION_STATUSES,
        fallback="not_attempted",
    )

    blocked_reasons: list[str] = []

    if not tenant_id:
        blocked_reasons.append("award_without_a_tenant")
    if not source_opportunity_id:
        blocked_reasons.append("award_without_a_source_opportunity")

    # Gate 91's required detail fields, imported rather than restated. Missing
    # any is a review item, never a silent assumption.
    supplied = {
        "award_number": award_number,
        "award_start_date": award_start_date,
        "award_end_date": award_end_date,
        "award_amount": total_award_amount,
    }
    missing_details = sorted(
        field for field in REQUIRED_AWARD_DETAIL_FIELDS if not supplied.get(field)
    )
    for field in missing_details:
        blocked_reasons.append(f"award_detail_missing:{field}")

    # No performance period is computed from a default. Two dates or nothing.
    if award_start_date and award_end_date:
        performance_period = {
            "start": award_start_date,
            "end": award_end_date,
            "derived_from": "award_dates_as_supplied",
        }
    else:
        performance_period = {
            "start": award_start_date,
            "end": award_end_date,
            "derived_from": "incomplete_award_dates",
        }

    # Match is a claim about money. It is never computed from the other two.
    if match_required is True and match_amount is None and match_percent is None:
        blocked_reasons.append("match_required_without_an_amount_or_percent")

    # The two identity spaces, related only as the caller related them.
    binding = "caller_supplied" if (tenant_id and customer_org_id) else "unknown"
    if not customer_org_id:
        blocked_reasons.append("no_customer_org_id_supplied_for_the_gate91_lane")

    if extraction == "unsupported_document_type":
        evidence_status = "unsupported_document_type"
    elif extraction == "evidence_extracted":
        evidence_status = "evidence_backed"
    elif extraction == "human_entered":
        evidence_status = "human_entered"
    elif extraction == "not_attempted":
        evidence_status = "not_established"
    else:
        evidence_status = "unknown"

    # An award may exist long before anyone knows what it obliges.
    active_obligations_supported = extraction in OBLIGATION_CAPABLE_EXTRACTION

    human_review_required = bool(
        (blocked_reasons and not human_review_acknowledged)
        or extraction in {"needs_human_review", "unknown", "unsupported_document_type"}
        or status == "mistaken_award"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "tenant_org_binding_status": binding,
            "award_id": build_award_id(
                tenant_id=tenant_id,
                source_opportunity_id=source_opportunity_id,
                award_number=award_number,
            ),
            "source_opportunity_id": source_opportunity_id,
            "pursuit_record_id": pursuit_record_id,
            "award_title": award_title,
            "funding_agency": funding_agency,
            "assistance_listing_numbers": list(assistance_listing_numbers or []),
            "award_number": award_number,
            "award_status": status,
            "award_start_date": award_start_date,
            "award_end_date": award_end_date,
            "performance_period": performance_period,
            "total_award_amount": total_award_amount,
            "match_required": match_required,
            "match_amount": match_amount,
            "match_percent": match_percent,
            "award_document_status": award_document_status,
            "requirements_extraction_status": extraction,
            "evidence_status": evidence_status,
            "active_obligations_supported": active_obligations_supported,
            "missing_award_details": missing_details,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: an award record consumes nothing it came from.
            "is_pursuit_record": False,
            "pursuit_history_preserved": True,
            "source_history_preserved": True,
            "source_opportunity_deleted": False,
            "pursuit_record_deleted": False,
            "fabricated": False,
            "requirements_invented": False,
            "dates_inferred": False,
            "live_fetch_performed": False,
        }
    )


def portfolio_lifecycle_is_fully_mapped() -> bool:
    """Every Gate 91 lifecycle status has a mapping. Detected, not assumed."""
    return set(PORTFOLIO_LIFECYCLE_STATUSES) == set(
        PORTFOLIO_LIFECYCLE_TO_AWARD_STATUS
    )


def award_record_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in AWARD_RECORD_FIELDS:
        if field not in record:
            fails.append(f"award_record_missing_field:{field}")

    for constant in (
        "is_pursuit_record",
        "source_opportunity_deleted",
        "pursuit_record_deleted",
        "fabricated",
        "requirements_invented",
        "dates_inferred",
        "live_fetch_performed",
    ):
        if record.get(constant) is not False:
            fails.append(f"award_record_claimed:{constant}")

    for constant in ("pursuit_history_preserved", "source_history_preserved"):
        if record.get(constant) is not True:
            fails.append(f"award_record_dropped:{constant}")

    if record.get("award_status") not in AWARD_STATUSES:
        fails.append("award_status_out_of_vocabulary")
    if record.get("requirements_extraction_status") not in (
        REQUIREMENTS_EXTRACTION_STATUSES
    ):
        fails.append("requirements_extraction_status_out_of_vocabulary")
    if record.get("tenant_org_binding_status") not in TENANT_ORG_BINDING_STATUSES:
        fails.append("tenant_org_binding_status_out_of_vocabulary")

    # Tenant-scoped by construction.
    if not record.get("tenant_id"):
        fails.append("award_record_without_a_tenant")

    # The binding is only as good as what the caller supplied.
    if record.get("tenant_org_binding_status") == "caller_supplied" and not (
        record.get("tenant_id") and record.get("customer_org_id")
    ):
        fails.append("binding_claimed_without_both_identities")

    # Unsupported documents can never support obligations.
    if record.get(
        "requirements_extraction_status"
    ) == "unsupported_document_type" and record.get("active_obligations_supported"):
        fails.append("unsupported_document_supported_obligations")

    # active_obligations_supported must agree with the provenance.
    expected_supported = (
        record.get("requirements_extraction_status") in OBLIGATION_CAPABLE_EXTRACTION
    )
    if record.get("active_obligations_supported") is not expected_supported:
        fails.append("active_obligations_supported_disagrees_with_the_provenance")

    # No performance period is invented from one date.
    period = record.get("performance_period") or {}
    if period.get("derived_from") == "award_dates_as_supplied" and not (
        period.get("start") and period.get("end")
    ):
        fails.append("performance_period_claimed_without_both_dates")

    # Identity reproducible from the record's own fields.
    expected_id = build_award_id(
        tenant_id=record.get("tenant_id"),
        source_opportunity_id=record.get("source_opportunity_id"),
        award_number=record.get("award_number"),
    )
    if record.get("award_id") != expected_id:
        fails.append("award_id_not_derivable_from_its_fields")

    return fails
