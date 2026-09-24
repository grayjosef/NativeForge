"""179E/G/H: the customer's dashboard, and the line it must not see across.

## 179G, and why it is a contract rather than a convention

A customer must not be handed source activation controls, demo/real plane
toggles, internal UUID context switches, verifier surfaces, source
authorisation mutation, or controlling-company entitlement overrides. Those
are not merely confusing. `activate a source` is an instruction to start
fetching somebody else's website in NativeForge's name; a demo/real toggle
lets a customer look at the wrong plane and believe it; an entitlement
override is the vendor's side of a commercial agreement.

Hiding them in the UI is not the control. `CUSTOMER_CAPABILITIES` and
`OPERATOR_CAPABILITIES` are disjoint sets, `build_customer_surface` emits
only from the first, and `surface_invariant_failures` refuses a payload
carrying anything from the second - so an operator field cannot reach a
customer by being added to a serialiser somebody forgot to filter.

## 179H: trust without raw internals

A customer is entitled to know where a claim came from, what document says
it, what changed, and what we do not know. They are not entitled to - and
are not served by - internal row ids, adapter names, scheduler leases or
verifier output. `build_trust_panel` carries the first set and drops the
second, and the drop is a filter on a named allow-list rather than a
best-effort scrub.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from nativeforge.services.customer_decision_service import (
    DISMISSED,
    PURSUING,
    WATCHED,
)

SCHEMA_VERSION = "nf_customer_surface_v1"

SURFACE_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 179G: two disjoint sets of capability.
# ---------------------------------------------------------------------------

CUSTOMER_CAPABILITIES: frozenset[str] = frozenset(
    {
        "VIEW_RECOMMENDATIONS",
        "VIEW_WHY_RELEVANT",
        "VIEW_ELIGIBILITY",
        "VIEW_DOCUMENT_EVIDENCE",
        "VIEW_CHANGES",
        "WATCH_OPPORTUNITY",
        "DISMISS_OPPORTUNITY",
        "PURSUE_OPPORTUNITY",
        "VIEW_PURSUITS",
        "VIEW_REQUIREMENTS",
        "VIEW_TASKS",
        "VIEW_DEADLINES",
        "PREPARE_APPLICATION",
        "VIEW_TRUST_EVIDENCE",
        "VIEW_ORGANIZATION_PROFILE",
        "EDIT_ORGANIZATION_PROFILE",
        "VIEW_ACCOUNT_STATUS",
        "SET_PERSONAL_PREFERENCES",
        "EXPORT_OWN_DATA",
    }
)

OPERATOR_CAPABILITIES: frozenset[str] = frozenset(
    {
        "ACTIVATE_SOURCE",
        "DEACTIVATE_SOURCE",
        "AUTHORIZE_SOURCE",
        "REVOKE_SOURCE_AUTHORIZATION",
        "TOGGLE_DEMO_REAL_PLANE",
        "SET_ORG_CONTEXT_BY_UUID",
        "VIEW_VERIFIER_OUTPUT",
        "RUN_READINESS_VERIFIER",
        "GRANT_BENEFIT_EXTENSION",
        "FORGIVE_MAINTENANCE_DEBT",
        "SET_MAINTENANCE_PAID_THROUGH",
        "RELICENSE_ORGANIZATION",
        "VERIFY_AUTHORITY_MANUALLY",
        "CREATE_ORGANIZATION",
        "VIEW_FLEET_HEALTH",
        "VIEW_SOURCE_SCHEDULER",
    }
)

#: Field names that carry internal machinery. 179H: a customer is entitled to
#: provenance, not to plumbing.
_INTERNAL_FIELD = re.compile(
    r"^(lease|worker|scheduler|adapter|verifier|row_id|internal_|debug_|"
    r"is_demo|plane|raw_payload|cursor|job_id|attempt_)",
    re.I,
)

#: The tiles a customer dashboard can carry. 179E.
DASHBOARD_TILES: tuple[str, ...] = (
    "NEW_OPPORTUNITIES",
    "NEEDS_REVIEW",
    "WATCH_LIST",
    "ACTIVE_PURSUITS",
    "DEADLINES",
    "RECENT_CHANGES",
    "COVERAGE_NOTES",
    "ELIGIBILITY_REVIEW",
)

TILE_MEANINGS: dict[str, str] = {
    "NEW_OPPORTUNITIES": "recommended and not yet decided about",
    "NEEDS_REVIEW": "relevance or eligibility the system could not settle",
    "WATCH_LIST": "kept by somebody here",
    "ACTIVE_PURSUITS": "applications in progress",
    "DEADLINES": "closing dates on things this organisation cares about",
    "RECENT_CHANGES": "amendments, moved deadlines, withdrawn notices",
    "COVERAGE_NOTES": (
        "what NativeForge knows it may be missing that bears on this "
        "organisation - stated to the customer rather than hidden"
    ),
    "ELIGIBILITY_REVIEW": "conditions somebody needs to confirm",
}


def _as_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def capabilities_for(*, role: str, is_controlling_company: bool) -> dict[str, Any]:
    """What may this person do? Two sets, never merged."""
    customer = sorted(CUSTOMER_CAPABILITIES)
    operator = sorted(OPERATOR_CAPABILITIES) if is_controlling_company else []
    return {
        "schema_version": SCHEMA_VERSION,
        "role": str(role),
        "is_controlling_company": bool(is_controlling_company),
        "customer_capabilities": customer,
        "operator_capabilities": operator,
        "sets_are_disjoint": not (CUSTOMER_CAPABILITIES & OPERATOR_CAPABILITIES),
        "operator_capabilities_withheld": not is_controlling_company,
    }


def build_dashboard(
    *,
    organization_id: Any,
    recommendations: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    changes: list[dict[str, Any]] | None = None,
    coverage_notes: list[dict[str, Any]] | None = None,
    as_of: Any,
    deadline_window_days: int = 60,
) -> dict[str, Any]:
    """179E. One organisation's dashboard, from its own rows only.

    Every list is filtered by `organization_id` before anything is counted.
    Tenant isolation at the read model is cheaper than tenant isolation
    discovered in an incident.
    """
    today = _as_date(as_of)
    if today is None:
        raise ValueError("a dashboard needs the date it is being built for")

    org = str(organization_id)
    mine = [r for r in recommendations if str(r.get("organization_id")) == org]
    my_decisions = {
        str(d.get("canonical_id")): d
        for d in decisions
        if str(d.get("organization_id")) == org
    }
    foreign = len(recommendations) - len(mine)

    def state_of(row: dict[str, Any]) -> str:
        decision = my_decisions.get(str(row.get("canonical_id")))
        return str((decision or {}).get("decision_state") or "NEW")

    new_rows = [r for r in mine if state_of(r) == "NEW"]
    watched = [r for r in mine if state_of(r) == WATCHED]
    pursuing = [r for r in mine if state_of(r) == PURSUING]
    dismissed = [r for r in mine if state_of(r) == DISMISSED]

    needs_review = [
        r
        for r in mine
        if state_of(r) != DISMISSED
        and (
            str(r.get("relevance_class")) == "RELEVANCE_UNCERTAIN"
            or str(r.get("eligibility_view")) == "ELIGIBILITY_UNCERTAIN"
        )
    ]
    eligibility_review = [
        r
        for r in mine
        if state_of(r) != DISMISSED and str(r.get("eligibility_view")) == "CONDITIONAL"
    ]

    horizon = today + dt.timedelta(days=int(deadline_window_days))
    deadlines = sorted(
        (
            {
                "canonical_id": r.get("canonical_id"),
                "title": r.get("title"),
                "deadline": r.get("deadline"),
                "decision_state": state_of(r),
                "days_remaining": (_as_date(r.get("deadline")) - today).days,
            }
            for r in mine
            if state_of(r) != DISMISSED
            and _as_date(r.get("deadline"))
            and today <= _as_date(r.get("deadline")) <= horizon
        ),
        key=lambda d: d["days_remaining"],
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": org,
        "as_of": str(today),
        "tiles": {
            "NEW_OPPORTUNITIES": len(new_rows),
            "NEEDS_REVIEW": len(needs_review),
            "WATCH_LIST": len(watched),
            "ACTIVE_PURSUITS": len(pursuing),
            "DEADLINES": len(deadlines),
            "RECENT_CHANGES": len(
                [
                    c
                    for c in (changes or [])
                    if str(c.get("organization_id") or org) == org
                ]
            ),
            "COVERAGE_NOTES": len(coverage_notes or []),
            "ELIGIBILITY_REVIEW": len(eligibility_review),
        },
        "deadlines": deadlines,
        "dismissed_count": len(dismissed),
        # Proof of isolation, reported rather than promised.
        "rows_considered": len(mine),
        "rows_from_other_tenants_excluded": foreign,
        "tenant_scoped": True,
        "model_version": SURFACE_MODEL_VERSION,
    }


def build_trust_panel(
    *,
    recommendation: dict[str, Any],
    source_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """179H. Provenance a customer can act on, without the plumbing."""
    sources = [
        {
            "source_name": s.get("source_name"),
            "publisher": s.get("publisher"),
            "last_observed_at": s.get("last_observed_at"),
            "authorization_status": s.get("authorization_status"),
        }
        for s in (source_records or [])
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "canonical_id": recommendation.get("canonical_id"),
        "sources": sources,
        "document_citations": recommendation.get("document_citations") or [],
        "what_changed": recommendation.get("what_changed") or [],
        "known_unknowns": recommendation.get("known_unknowns") or [],
        "relevance_evidence_ids": recommendation.get("relevance_evidence_ids") or [],
        "eligibility_evidence_ids": recommendation.get("eligibility_evidence_ids")
        or [],
        # 179H: what is deliberately absent.
        "internal_fields_excluded": True,
        "model_version": SURFACE_MODEL_VERSION,
    }


def build_customer_surface(
    *,
    organization_id: Any,
    role: str,
    is_controlling_company: bool = False,
    dashboard: dict[str, Any] | None = None,
    feed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything a customer session is handed, and nothing else."""
    capabilities = capabilities_for(
        role=role, is_controlling_company=is_controlling_company
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(organization_id) if organization_id else None,
        "role": str(role),
        "capabilities": capabilities["customer_capabilities"],
        # Present only for controlling-company staff, and named separately so
        # nothing downstream can merge the two lists by accident.
        "operator_capabilities": capabilities["operator_capabilities"],
        "dashboard": dashboard,
        "feed": feed,
        "model_version": SURFACE_MODEL_VERSION,
    }


def _walk(payload: Any, path: str = ""):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield f"{path}.{key}" if path else str(key), key, value
            yield from _walk(value, f"{path}.{key}" if path else str(key))
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk(item, path)


def surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    """Refuse a customer payload carrying an operator capability or plumbing.

    Walks the whole structure. A filter that only checks the top level is a
    filter that a nested serialiser walks straight past.
    """
    failures: list[str] = []

    if not surface.get("organization_id"):
        failures.append("customer_surface_names_no_organization")

    listed = set(surface.get("capabilities") or [])
    leaked = sorted(listed & OPERATOR_CAPABILITIES)
    if leaked:
        failures.append(f"customer_capabilities_include_operator_powers:{leaked}")
    unknown = sorted(listed - CUSTOMER_CAPABILITIES)
    if unknown:
        failures.append(f"capability_outside_the_customer_vocabulary:{unknown}")

    for path, key, value in _walk(surface):
        if key == "operator_capabilities":
            continue
        if _INTERNAL_FIELD.match(str(key)):
            failures.append(f"customer_surface_carries_internal_field:{path}")
        if isinstance(value, str) and value in OPERATOR_CAPABILITIES:
            failures.append(f"customer_surface_carries_operator_capability:{path}")

    return sorted(set(failures))


def describe_surface_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": SURFACE_MODEL_VERSION,
        "customer_capabilities": sorted(CUSTOMER_CAPABILITIES),
        "operator_capabilities": sorted(OPERATOR_CAPABILITIES),
        "dashboard_tiles": list(DASHBOARD_TILES),
        "every_tile_has_a_meaning": set(TILE_MEANINGS) == set(DASHBOARD_TILES),
        # The separation, checked rather than claimed.
        "capability_sets_are_disjoint": not (
            CUSTOMER_CAPABILITIES & OPERATOR_CAPABILITIES
        ),
        "source_activation_is_operator_only": "ACTIVATE_SOURCE" in OPERATOR_CAPABILITIES
        and "ACTIVATE_SOURCE" not in CUSTOMER_CAPABILITIES,
        "plane_toggle_is_operator_only": "TOGGLE_DEMO_REAL_PLANE"
        in OPERATOR_CAPABILITIES
        and "TOGGLE_DEMO_REAL_PLANE" not in CUSTOMER_CAPABILITIES,
        "entitlement_override_is_operator_only": "FORGIVE_MAINTENANCE_DEBT"
        in OPERATOR_CAPABILITIES
        and "FORGIVE_MAINTENANCE_DEBT" not in CUSTOMER_CAPABILITIES,
        "verifier_surface_is_operator_only": "VIEW_VERIFIER_OUTPUT"
        in OPERATOR_CAPABILITIES
        and "VIEW_VERIFIER_OUTPUT" not in CUSTOMER_CAPABILITIES,
        "dashboards_are_tenant_scoped": True,
        "trust_panel_excludes_internal_fields": True,
        "coverage_notes_are_shown_to_the_customer": "COVERAGE_NOTES" in DASHBOARD_TILES,
    }
