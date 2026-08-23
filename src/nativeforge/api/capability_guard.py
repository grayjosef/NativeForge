"""Capability enforcement adapter for read routes (Gate 71).

Gate 58 put a tenant guard on all 205 org-scoped handlers. This module is the
next layer — role/capability enforcement — and it is deliberately **not attached
to any live route**.

Why not, precisely:

  1. Every route on both planes resolves its organization from the
     ``X-NF-Org-Id`` header via ``get_org_context_with_db`` /
     ``get_org_context_dev``. The org *type* is looked up from the persisted
     ``organizations`` row, which is not spoofable — but *which org you are*
     comes from a client header. No route carries a verified actor.
  2. ``resolve_request_identity`` can only ever return ``anonymous``,
     ``demo_operator``, or ``oidc_configured_unverified``, because no OIDC
     verifier is configured. None of those is a customer.
  3. ``enforce_capability`` requires ``role_known`` **and**
     ``membership_active``. With no membership store, ``membership_state`` is
     always ``unknown``, so every capability check denies.

Attaching enforcement to a live route today therefore has exactly two possible
outcomes: deny every request including the demo, or trust a client header as
role proof. The first breaks the demo; the second is the vulnerability this
whole campaign exists to avoid. So this adapter runs in **dry-run** mode: it
computes the decision a live route *would* reach, records it, and does not
change any response.

``evaluate_read_capability`` is the dry-run path and is what the tests exercise.
``require_read_capability`` is the live path that raises 403 — it exists, is
tested, and is attached to nothing. When Gate 69/70 land verified identity and
trusted membership, wiring becomes a one-line change per route rather than a
redesign.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from nativeforge.api.request_identity import (
    ROLE_ASSERTION_HEADERS,
    get_current_identity,
)
from nativeforge.services.api_enforcement_service import (
    build_request_enforcement_context,
    enforce_capability,
)
from nativeforge.services.security_audit_sink_service import submit_events

# Identity states that could ever carry a customer role. Deliberately empty of
# demo_operator: Cloudflare Access proves an operator got through the edge, not
# that a customer logged in.
CUSTOMER_IDENTITY_STATES = frozenset({"oidc_verified"})

# States that exist today, none of which is a customer.
NON_CUSTOMER_IDENTITY_STATES = frozenset(
    {
        "anonymous",
        "demo_operator",
        "oidc_unconfigured",
        "oidc_configured_unverified",
        "unknown",
    }
)

# Read capabilities from the existing Gate 57 vocabulary. No new names are
# invented here: reads of workspace content fall under view_workspace, and audit
# reads under view_org_audit_events. Inventing view_evidence / view_feedback /
# view_source_registry would create a second vocabulary that drifts from
# ROLE_CAPABILITIES.
READ_CAPABILITIES = frozenset({"view_workspace", "view_org_audit_events"})

# What each surveyed read route family would check. Names on the left are the
# route families in docs 409/411, not new capabilities.
READ_ROUTE_CAPABILITY_MAP = {
    "workspace_read": "view_workspace",
    "evidence_read": "view_workspace",
    "feedback_read": "view_workspace",
    "package_export_preview": "view_workspace",
    "source_registry_read": "view_workspace",
    "org_audit_read": "view_org_audit_events",
}

DRY_RUN = "dry_run"
LIVE = "live"


def _identity_is_customer(identity: dict[str, Any] | None) -> bool:
    if not identity:
        return False
    if not identity.get("verification_trusted"):
        return False
    return identity.get("identity_state") in CUSTOMER_IDENTITY_STATES


def evaluate_read_capability(
    *,
    capability: str,
    organization_id: str | None,
    identity: dict[str, Any] | None = None,
    trusted_role: str | None = None,
    membership_state: str | None = None,
    request_headers: dict[str, str] | None = None,
    mode: str = DRY_RUN,
) -> dict[str, Any]:
    """Compute the capability decision a read route would reach.

    ``trusted_role`` must come from a membership directory lookup, never from a
    request. There is no parameter for a client-supplied role, which is the
    cheapest way to guarantee one is never honoured.
    """
    blocked: list[str] = []

    if capability not in READ_CAPABILITIES:
        # Write and authority capabilities are out of scope for this gate, and
        # an unrecognised name is a caller bug.
        blocked.append(f"capability_not_a_wired_read_capability:{capability}")

    # A role or capability asserted by the client is recorded and refused. Not
    # merely ignored — a silently ignored spoof lets the caller believe it
    # worked.
    asserted = sorted(
        {
            k.lower()
            for k in (request_headers or {})
            if k.lower() in ROLE_ASSERTION_HEADERS
        }
    )
    if asserted:
        blocked.append("client_asserted_role_headers_rejected:" + ",".join(asserted))

    resolved_identity = identity if identity is not None else get_current_identity()
    identity_state = (resolved_identity or {}).get("identity_state") or "anonymous"

    if not _identity_is_customer(resolved_identity):
        blocked.append(f"identity_is_not_a_verified_customer:{identity_state}")

    # X-NF-Org-Id gets a request into an org's routes; it is not proof of
    # membership in that org. The role must come from the directory.
    if not trusted_role:
        blocked.append("no_trusted_role_from_membership_directory")

    context = build_request_enforcement_context(
        requesting_org_id=organization_id,
        # No verified actor exists on any route today, so this is empty and the
        # enforcement service adds missing_actor of its own accord.
        actor_id=(resolved_identity or {}).get("subject"),
        actor_role=trusted_role,
        membership_state=membership_state,
        plane="read",
    )
    decision = enforce_capability(context=context, capability=capability)
    if not decision.get("allowed"):
        blocked.extend(decision.get("blocked_reasons") or [])

    allowed = not blocked

    # Denials are audited through the sink so they are accounted rather than
    # dropped. In dry-run the sink is in modeled mode and writes nothing.
    sink = submit_events(decision.get("audit_events") or [], mode="modeled")

    return {
        "schema_version": "nf_capability_read_guard_v1",
        "mode": mode if mode in {DRY_RUN, LIVE} else "unknown",
        "capability": capability,
        "organization_id": organization_id,
        "identity_state": identity_state,
        "trusted_role": trusted_role,
        "membership_state": membership_state,
        "allowed": allowed,
        "blocked_reasons": blocked,
        "client_asserted_headers_rejected": asserted,
        # In dry-run the computed decision changes no response.
        "enforced": mode == LIVE,
        "would_deny_in_live_mode": not allowed,
        "audit_sink": {
            "accepted": sink["accepted"],
            "event_count": sink["event_count"],
            "events_refused": len(sink["events_refused"]),
            "persisted": sink["persisted"],
        },
        # Honest boundaries, unchanged by this module.
        "customer_login_live": False,
        "production_persistence_claimed": False,
    }


def require_read_capability(
    *,
    capability: str,
    organization_id: str | None,
    identity: dict[str, Any] | None = None,
    trusted_role: str | None = None,
    membership_state: str | None = None,
    request_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Live enforcement: raise 403 unless the capability is held.

    **Attached to no route.** With no verified identity and no membership store
    every call denies, so attaching this would 403 the demo. It exists and is
    tested so that wiring is a one-line change per route once Gate 69/70 land,
    rather than a redesign under time pressure.
    """
    decision = evaluate_read_capability(
        capability=capability,
        organization_id=organization_id,
        identity=identity,
        trusted_role=trusted_role,
        membership_state=membership_state,
        request_headers=request_headers,
        mode=LIVE,
    )
    if not decision["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"capability not held: {capability}",
        )
    return decision


def capability_guard_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if decision.get("allowed"):
        if decision.get("blocked_reasons"):
            fails.append("allowed_with_blocked_reasons")
        if not decision.get("trusted_role"):
            fails.append("allowed_without_trusted_role")
        if decision.get("identity_state") in NON_CUSTOMER_IDENTITY_STATES:
            fails.append("allowed_for_non_customer_identity")
        if decision.get("client_asserted_headers_rejected"):
            fails.append("allowed_despite_client_asserted_role")
    else:
        if not decision.get("blocked_reasons"):
            fails.append("denied_without_reason")

    if decision.get("mode") == DRY_RUN and decision.get("enforced"):
        fails.append("dry_run_claims_enforcement")
    for forbidden in ("customer_login_live", "production_persistence_claimed"):
        if decision.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
