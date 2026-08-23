"""Tests: Gate 58 API-layer tenant + capability + authority enforcement.

Two kinds of test here:

  1. **Behaviour** — the enforcement seam denies what it must deny.
  2. **Bypass / registry** — a static analysis of the API package that fails if
     any org-scoped route handler does not reach a tenant enforcement primitive.

(2) is the point of Gate 58. Enforcement functions existing is not the same as
request paths being unable to skip them.
"""

from __future__ import annotations

import ast
import pathlib
import uuid

import pytest

from nativeforge.services.api_enforcement_service import (
    build_request_enforcement_context,
    enforce_authority_sensitive_action,
    enforce_capability,
    enforce_seat_invite,
    enforce_source_promotion,
    enforce_tenant_access,
    enforcement_decision_invariant_failures,
)
from nativeforge.services.authority_proof_workflow_service import (
    build_authority_proof,
)
from nativeforge.services.continuous_source_discovery_service import (
    build_source_candidate,
)
from nativeforge.services.org_tenant_seat_model_service import (
    DEFAULT_SEAT_CAP,
    build_org_tenant,
)

ORG_A = "org-aaaa"
ORG_B = "org-bbbb"


def _ctx(
    *,
    org: str | None = ORG_A,
    actor: str | None = "u1",
    role: str | None = "grant_lead",
    membership: str | None = "active",
    proof: dict | None = None,
) -> dict:
    return build_request_enforcement_context(
        requesting_org_id=org,
        actor_id=actor,
        actor_role=role,
        membership_state=membership,
        authority_proof=proof,
    )


def _verified_rep_proof() -> dict:
    return build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="verified",
        verified_by="ops",
    )


# ───────────────────────── tenant access ─────────────────────────


@pytest.mark.parametrize(
    "object_type",
    ["workspace", "evidence_intake", "feedback_report", "package_export_preview"],
)
def test_cross_org_access_denied_for_each_scoped_object(object_type: str) -> None:
    d = enforce_tenant_access(
        context=_ctx(),
        resource_org_id=ORG_B,
        object_type=object_type,
        action="view",
    )
    assert d["allowed"] is False
    assert "cross_org_denied" in d["blocked_reasons"]
    events = [e["event_type"] for e in d["audit_events"]]
    assert "cross_org_access_attempt" in events
    assert "tenant_access_denied" in events
    assert enforcement_decision_invariant_failures(d) == []


def test_same_org_access_allowed() -> None:
    d = enforce_tenant_access(
        context=_ctx(), resource_org_id=ORG_A, object_type="workspace", action="view"
    )
    assert d["allowed"] is True
    assert enforcement_decision_invariant_failures(d) == []


def test_missing_tenant_denies() -> None:
    d = enforce_tenant_access(
        context=_ctx(org=None),
        resource_org_id=ORG_A,
        object_type="workspace",
        action="view",
    )
    assert d["allowed"] is False
    assert "missing_tenant" in d["blocked_reasons"]
    assert d["audit_events"], "denial must be auditable"


def test_missing_resource_org_denies() -> None:
    d = enforce_tenant_access(
        context=_ctx(), resource_org_id=None, object_type="workspace", action="view"
    )
    assert d["allowed"] is False
    assert "missing_resource_org" in d["blocked_reasons"]


def test_missing_membership_denies_capability() -> None:
    d = enforce_capability(
        context=_ctx(membership="removed"), capability="view_workspace"
    )
    assert d["allowed"] is False
    assert "membership_not_active" in d["blocked_reasons"]


def test_unknown_role_denies_capability() -> None:
    d = enforce_capability(context=_ctx(role="wizard"), capability="view_workspace")
    assert d["allowed"] is False
    assert "missing_or_unknown_role" in d["blocked_reasons"]


# ───────────────────────── capability / production gates ────────────────────


@pytest.mark.parametrize(
    "capability",
    [
        "controlled_customer_pilot_go",
        "production_rollout_go",
        "enable_login_live",
        "enable_production_storage",
        "declare_pen_test_passed",
        "final_submit_to_portal",
    ],
)
@pytest.mark.parametrize(
    "role", ["org_owner", "org_admin", "authorized_representative", "operator_internal"]
)
def test_production_gates_cannot_be_bypassed_by_any_role(
    capability: str, role: str
) -> None:
    d = enforce_capability(context=_ctx(role=role), capability=capability)
    assert d["allowed"] is False
    assert "capability_permanently_blocked_at_this_stage" in d["blocked_reasons"]


def test_reviewer_cannot_final_approve() -> None:
    d = enforce_capability(
        context=_ctx(role="reviewer", proof=_verified_rep_proof()),
        capability="approve_package_readiness",
    )
    assert d["allowed"] is False


def test_operator_internal_cannot_become_customer_authority() -> None:
    d = enforce_authority_sensitive_action(
        context=_ctx(role="operator_internal", proof=_verified_rep_proof()),
        action="official_package_approval",
    )
    assert d["allowed"] is False
    assert "internal_role_cannot_hold_customer_authority" in d["blocked_reasons"]


def test_internal_role_capability_carries_no_customer_authority() -> None:
    d = enforce_capability(
        context=_ctx(role="operator_internal"), capability="support_review_access"
    )
    assert d["allowed"] is True
    assert d["carries_customer_authority"] is False


# ───────────────────────── authority-sensitive actions ─────────────────────


def test_absent_authority_proof_blocks_authority_action() -> None:
    d = enforce_authority_sensitive_action(
        context=_ctx(role="authorized_representative"),
        action="final_application_package_signoff",
    )
    assert d["allowed"] is False
    assert "authority_proof_absent" in d["blocked_reasons"]
    assert d["submission_ready_claimed"] is False


@pytest.mark.parametrize("state", ["submitted", "rejected", "expired", "revoked"])
def test_non_verified_authority_states_block(state: str) -> None:
    proof = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state=state,
        verified_by="ops",
    )
    d = enforce_authority_sensitive_action(
        context=_ctx(role="authorized_representative", proof=proof),
        action="final_application_package_signoff",
    )
    assert d["allowed"] is False
    assert any("authority_proof_state_blocks" in r for r in d["blocked_reasons"])


def test_verified_authority_allows_then_missing_evidence_still_blocks() -> None:
    ctx = _ctx(role="authorized_representative", proof=_verified_rep_proof())

    ok = enforce_authority_sensitive_action(
        context=ctx, action="official_package_approval"
    )
    assert ok["allowed"] is True
    assert enforcement_decision_invariant_failures(ok) == []

    blocked = enforce_authority_sensitive_action(
        context=ctx,
        action="official_package_approval",
        missing_evidence=["tribal_resolution"],
    )
    assert blocked["allowed"] is False
    assert "missing_evidence_present" in blocked["blocked_reasons"]


def test_authority_action_never_claims_final_eligibility() -> None:
    d = enforce_authority_sensitive_action(
        context=_ctx(role="authorized_representative", proof=_verified_rep_proof()),
        action="final_eligibility_assertion",
    )
    assert d["final_eligibility_claimed"] is False
    assert d["submission_ready_claimed"] is False


# ───────────────────────── seat invites ─────────────────────────


def _full_tenant() -> dict:
    return build_org_tenant(
        organization_profile_id=ORG_A,
        display_name="Org A",
        memberships=[
            {"user_id": f"u{i}", "role": "grant_lead", "state": "active"}
            for i in range(DEFAULT_SEAT_CAP)
        ],
    )


def test_sixth_seat_invite_blocked_through_the_seam() -> None:
    d = enforce_seat_invite(
        context=_ctx(role="org_admin"),
        tenant=_full_tenant(),
        invitee_id="u6",
        invitee_role="reviewer",
    )
    assert d["allowed"] is False
    events = [e["event_type"] for e in d["audit_events"]]
    assert "seat_invite_blocked_limit" in events


def test_actor_without_manage_seats_cannot_invite() -> None:
    d = enforce_seat_invite(
        context=_ctx(role="viewer"),
        tenant=build_org_tenant(
            organization_profile_id=ORG_A, display_name="Org A"
        ),
        invitee_id="u2",
        invitee_role="reviewer",
    )
    assert d["allowed"] is False
    assert "actor_cannot_manage_seats" in d["blocked_reasons"]


# ───────────────────────── source promotion ─────────────────────────


def test_source_promotion_requires_review_through_the_seam() -> None:
    cand = build_source_candidate(
        source_url="https://example.gov/feed",
        source_type="federal_agency_native_relevant",
        access_method="rss",
        terms_review_state="permitted",
        robots_allows=True,
        state="triaged",
        extraction_timestamp="2026-08-01",
        provenance={"publisher": "US Agency"},
    )
    denied = enforce_source_promotion(
        context=_ctx(role="operator_internal"), candidate=cand, approver_id=None
    )
    assert denied["allowed"] is False
    assert "human_review_approval_required" in denied["blocked_reasons"]
    assert denied["live_ingest_claimed"] is False

    allowed = enforce_source_promotion(
        context=_ctx(role="operator_internal"), candidate=cand, approver_id="ops"
    )
    assert allowed["allowed"] is True
    assert allowed["promotion_detail"]["resulting_state"] == "monitoring"


def test_unknown_source_cannot_be_promoted_through_the_seam() -> None:
    cand = build_source_candidate(
        source_url="https://example.org/x", source_type="unknown", state="unknown"
    )
    d = enforce_source_promotion(
        context=_ctx(role="operator_internal"), candidate=cand, approver_id="ops"
    )
    assert d["allowed"] is False


# ═════════════════ BYPASS / REGISTRY TESTS (the point of Gate 58) ════════════

API_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "nativeforge" / "api"

TENANT_PRIMITIVES = {
    "_same_org",
    "same_org",
    "guard_same_org_403",
    "guard_same_org_404",
    "evaluate_same_org",
    "enforce_tenant_access",
    "evaluate_tenant_scoped_access",
    "assert_tenant_access",
}

ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}
ORG_PARAMS = {"org_id", "organization_id"}


def _called_names(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Name):
                out.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                out.add(fn.attr)
    return out


def _build_api_index() -> tuple[dict[str, set[str]], dict[str, str], list[tuple]]:
    calls_map: dict[str, set[str]] = {}
    aliases: dict[str, str] = {}
    handlers: list[tuple[str, str, bool, set[str]]] = []

    for path in sorted(API_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    if a.asname:
                        aliases[a.asname] = a.name.split(".")[-1]
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls_map.setdefault(node.name, set()).update(_called_names(node))

            is_route = any(
                isinstance(
                    (d.func if isinstance(d, ast.Call) else d), ast.Attribute
                )
                and (d.func if isinstance(d, ast.Call) else d).attr in ROUTE_METHODS
                for d in node.decorator_list
            )
            if not is_route:
                continue
            args = [a.arg for a in node.args.args] + [
                a.arg for a in node.args.kwonlyargs
            ]
            handlers.append(
                (
                    path.name,
                    node.name,
                    any(a in ORG_PARAMS for a in args),
                    _called_names(node),
                )
            )
    return calls_map, aliases, handlers


def _reaches_primitive(
    names: set[str],
    calls_map: dict[str, set[str]],
    aliases: dict[str, str],
    depth: int = 0,
    seen: set[str] | None = None,
) -> bool:
    """Resolve import aliases while walking the call graph.

    Alias resolution matters: the evidence-pack handlers import
    `discovery_evidence_pack_handler as _discovery_evidence_pack_handler`, and
    without following that rename they look unenforced when they are not.
    """
    if depth > 5:
        return False
    seen = seen or set()
    for raw in names:
        n = aliases.get(raw, raw)
        if raw in TENANT_PRIMITIVES or n in TENANT_PRIMITIVES:
            return True
        if n in seen or n not in calls_map:
            continue
        seen.add(n)
        if _reaches_primitive(calls_map[n], calls_map, aliases, depth + 1, seen):
            return True
    return False


def test_every_org_scoped_route_handler_reaches_tenant_enforcement() -> None:
    """Fails if a handler takes an org path param but skips tenant enforcement.

    This is the anti-bypass invariant. If it fails, a new route was added that
    can read another organization's data. Fix the route, do not relax the test.
    """
    calls_map, aliases, handlers = _build_api_index()
    org_scoped = [h for h in handlers if h[2]]
    assert org_scoped, "no org-scoped handlers discovered — scanner is broken"

    unenforced = [
        f"{f}::{n}"
        for f, n, _, calls in org_scoped
        if not _reaches_primitive(calls, calls_map, aliases)
    ]
    assert unenforced == [], (
        "org-scoped route handlers without tenant enforcement: "
        + ", ".join(sorted(unenforced))
    )


def test_scanner_detects_a_deliberately_unsafe_handler() -> None:
    """Prove the scanner can actually fail — a green test that never fails is
    worthless. Synthesizes an unsafe handler and asserts it is caught."""
    unsafe = ast.parse(
        "\n".join(
            [
                "@demo_router.get('/v1/x/{org_id}/leak')",
                "def leaky_handler(org_id, ctx, db):",
                "    return {'secret': 'cross tenant'}",
                "",
            ]
        )
    )
    fn = unsafe.body[0]
    assert isinstance(fn, ast.FunctionDef)
    calls = _called_names(fn)
    assert not _reaches_primitive(calls, {}, {}), (
        "scanner failed to flag a handler that performs no enforcement"
    )


def test_tenant_guard_is_the_single_enforcement_point() -> None:
    """All same_org helpers must delegate rather than re-implement the check.

    Before Gate 58 this logic was copy-pasted into 14 modules and had already
    drifted (eleven raised 403, three raised 404). Re-introducing a local
    implementation is what this test prevents.
    """
    offenders: list[str] = []
    for path in sorted(API_DIR.glob("*.py")):
        if path.name == "tenant_guard.py":
            continue
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in {"_same_org", "same_org"}:
                continue
            calls = _called_names(node)
            if not calls & {"guard_same_org_403", "guard_same_org_404"}:
                offenders.append(f"{path.name}::{node.name}")
    assert offenders == [], (
        "same_org helpers not delegating to tenant_guard: " + ", ".join(offenders)
    )


def test_guard_records_denial_and_preserves_status_codes() -> None:
    from fastapi import HTTPException

    from nativeforge.api.org_context import OrgContext
    from nativeforge.api.tenant_guard import (
        guard_same_org_403,
        guard_same_org_404,
        recent_denials,
        reset_recent_denials,
    )

    a = uuid.uuid4()
    b = uuid.uuid4()
    ctx = OrgContext(org_id=a, org_type="demo")

    reset_recent_denials()

    # Same org passes both variants without recording anything.
    guard_same_org_403(a, ctx)
    guard_same_org_404(a, ctx)
    assert recent_denials() == []

    with pytest.raises(HTTPException) as e403:
        guard_same_org_403(b, ctx)
    assert e403.value.status_code == 403
    assert e403.value.detail == "path org_id does not match authenticated org"

    with pytest.raises(HTTPException) as e404:
        guard_same_org_404(b, ctx)
    assert e404.value.status_code == 404
    assert e404.value.detail == "organization not found"

    events = recent_denials()
    assert events, "denials must be recorded"
    assert all(ev.get("persisted") is False for ev in events), (
        "modeled audit events must not claim persistence"
    )
    reset_recent_denials()
