"""Customer auth activation artifacts (Gate 115H).

Six files describing what stands between NativeForge and customer login.
Written to `artifacts/customer_auth_activation_boundary/`.

```text
customer_auth_activation_gate.json           fifteen gates, twelve missing
customer_auth_route_readiness_matrix.csv     five routes, none of them present
customer_auth_role_mapping_matrix.csv        provider claims to roles
dev_org_header_shutdown_readiness.json       what must happen before it goes
customer_auth_activation_demo_fixtures.json  the fixture set entire
customer_auth_activation_readiness_summary.md  what none of it permits yet
```

## No secret reaches a file

Every value written here is a boolean, a count, a route path, a role name or a
blocked reason. Before writing anything, this service scans the assembled
payload for every configured `OIDC_*` environment value and refuses to write if
one appears - the third such check in the chain, after the preflight service's
and the activation gate's.

A committed artifact is the worst possible place for a client secret, because it
survives in history after the file is deleted.

## The summary is the file somebody will quote

So it opens with the two sentences that are true and closes off the one that is
not: an activation boundary exists; customer auth is not live. Between those,
"NativeForge has authentication" is a sentence somebody could write from a
contract's existence, and this file exists to make writing it harder.
"""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_activation_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_auth_activation_boundary"

# Claims that must always carry the same value, whatever is measured. Each is
# either a structural fact about the contract or a boundary with no true branch.
FIXED_CLAIMS: dict[str, bool] = {
    "customer_auth_activation_contract_available": True,
    "customer_auth_live": False,
    "login_live": False,
    "dev_header_must_disable_before_production_auth": True,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "operational_awarded_tracking_ready": False,
    "operational_digest_ready": False,
}

# Claims whose value is whatever the environment says. Listed so the artifact
# is required to carry them even when they are false, rather than omitting a
# gate that happens not to be satisfied.
MEASURED_CLAIMS: tuple[str, ...] = (
    "provider_configured",
    "secret_present",
    "issuer_jwks_validated",
    "callback_session_validated",
    "org_binding_passed",
    "role_mapping_passed",
)

# The demo mapping the role matrix is rendered from. Invented group names; no
# provider was contacted and no directory was read.
DEMO_ROLE_MAPPING: dict[str, str] = {
    "nf-platform-admins": "platform_admin",
    "nf-tenant-admins": "tenant_admin",
    "nf-grants-managers": "grants_manager",
    "nf-grants-viewers": "grants_viewer",
    "nf-auditors": "auditor",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _csv(columns: tuple[str, ...], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _flag(value: Any) -> str:
    return str(bool(value)).lower()


def scan_for_secret_values(payload: Any) -> list[str]:
    """Which configured environment values appear in this payload.

    Returns key *names*, never values. An empty list is the only acceptable
    result, and every caller here treats a non-empty one as a hard refusal.
    """
    from nativeforge.services.customer_auth_activation_gate_service import (
        OIDC_ENV_KEYS,
    )

    blob = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    leaked: list[str] = []
    for key in OIDC_ENV_KEYS:
        raw = os.environ.get(key) or ""
        if raw and len(raw) >= 8 and raw in blob:
            leaked.append(key)
    return leaked


def build_activation_declaration() -> dict[str, Any]:
    """Every required claim, each read from the service that owns it."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    gate = build_customer_auth_activation_gate()
    shutdown = build_dev_header_shutdown_readiness()
    persistence = build_capability_matrix()
    awarded = build_awarded_requirements_readiness()
    digest = build_digest_readiness()
    beta = build_tenant_beta_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "customer_auth_activation_contract_available": True,
            # Measured, every one.
            "customer_auth_live": bool(gate["customer_auth_live"]),
            "login_live": bool(gate["login_live"]),
            "activation_allowed": bool(gate["activation_allowed"]),
            "provider_configured": bool(gate["provider_configured"]),
            "secret_present": bool(gate["secret_present"]),
            "issuer_jwks_validated": bool(gate["issuer_jwks_validated"]),
            "callback_session_validated": bool(gate["callback_session_validated"]),
            "org_binding_passed": bool(gate["org_binding_passed"]),
            "role_mapping_passed": bool(gate["role_mapping_passed"]),
            "owner_approval_present": bool(gate["owner_approval_present"]),
            "required_auth_gate_count": len(REQUIRED_AUTH_GATES),
            "missing_auth_gate_count": len(gate["missing_auth_gates"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            # The dev header boundary.
            "dev_header_enabled_default": bool(
                shutdown["dev_header_enabled_default"]
            ),
            "dev_header_used_by_routes": shutdown["dev_header_used_by_routes"],
            "dev_header_safe_to_disable_now": bool(shutdown["safe_to_disable_now"]),
            "dev_header_must_disable_before_production_auth": bool(
                shutdown["must_disable_before_production_auth"]
            ),
            # Downstream lanes, unchanged by this gate.
            "customer_persistence_live": bool(
                persistence["customer_persistence_live"]
            ),
            "beta_onboarding_ready": bool(beta["ready_for_beta_onboarding"]),
            "operational_awarded_tracking_ready": bool(
                awarded["ready_for_operational_awarded_tracking"]
            ),
            "operational_digest_ready": bool(
                digest.get("ready_for_operational_digest", False)
            ),
            # Constants, each naming something that is not customer app auth.
            "cloudflare_access_is_customer_auth": False,
            "dev_header_is_customer_auth": False,
            "frontend_preview_is_backend_login": False,
            "secret_value_emitted": False,
            "secrets_stored": False,
            "network_calls": False,
            "identity_provider_contacted": False,
            "real_users_created": False,
            "real_sessions_created": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "fabricated": False,
        }
    )


def render_route_matrix(readiness: dict[str, Any]) -> str:
    columns = ("requirement", "kind", "satisfied", "detail")
    rows: list[list[Any]] = []
    for field in (
        "login_route_available",
        "logout_route_available",
        "callback_route_available",
        "session_route_available",
        "current_user_route_available",
    ):
        matched = (readiness.get("matched_routes") or {}).get(field) or []
        rows.append([field, "route", _flag(readiness[field]), "; ".join(matched)])
    for field in (
        "route_auth_enforced",
        "route_org_resolution_enforced",
        "route_role_mapping_enforced",
        "route_session_cookie_policy_enforced",
    ):
        rows.append([field, "enforcement", _flag(readiness[field]), ""])
    rows.append(
        [
            "ready_for_live_login",
            "rollup",
            _flag(readiness["ready_for_live_login"]),
            "; ".join(readiness["blocked_reasons"]),
        ]
    )
    # Named explicitly so the artifact records what does not count as auth.
    for field in (
        "cloudflare_access_is_customer_auth",
        "frontend_preview_is_backend_login",
        "dev_header_is_customer_auth",
    ):
        rows.append([field, "not_customer_auth", _flag(readiness[field]), ""])
    return _csv(columns, rows)


def render_role_mapping_matrix(matrix: dict[str, Any]) -> str:
    columns = (
        "provider_role_claims",
        "mapping_status",
        "mapped_roles",
        "least_privilege_role",
        "can_view_grants",
        "can_edit_grants",
        "can_manage_persistence",
        "can_verify_binding",
        "human_review_required",
        "blocked_reasons",
    )
    rows = [
        [
            "; ".join(row["provider_role_claims"]) or "(none)",
            row["mapping_status"],
            "; ".join(row["mapped_roles"]) or "(none)",
            row["least_privilege_role"],
            _flag(row["can_view_grants"]),
            _flag(row["can_edit_grants"]),
            _flag(row["can_manage_persistence"]),
            _flag(row["can_verify_binding"]),
            _flag(row["human_review_required"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in matrix["rows"]
    ]
    return _csv(columns, rows)


def build_demo_role_mapping_matrix() -> dict[str, Any]:
    """Role mapping cases for the artifact. Invented claims, no directory read."""
    from nativeforge.services.customer_auth_role_mapping_service import (
        build_role_mapping_matrix,
    )

    resolved = {"organization_id_resolved": True, "membership_verified": True}
    return build_role_mapping_matrix(
        cases=[
            {"provider_role_claims": []},
            {
                "provider_role_claims": ["some-unmapped-group"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                **resolved,
            },
            {
                "provider_role_claims": ["platform_admin"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-platform-admins"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-platform-admins"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-tenant-admins"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-grants-managers"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-grants-viewers"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-auditors"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                **resolved,
            },
            {
                "provider_role_claims": [
                    "nf-platform-admins",
                    "nf-grants-viewers",
                ],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                **resolved,
            },
            {
                "provider_role_claims": ["nf-platform-admins"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                "organization_id_resolved": False,
                "membership_verified": True,
            },
            {
                "provider_role_claims": ["nf-platform-admins"],
                "configured_mapping": DEMO_ROLE_MAPPING,
                "binder_authorized": True,
                "organization_id_resolved": True,
                "membership_verified": False,
            },
        ]
    )


def render_readiness_summary(
    declaration: dict[str, Any], gate: dict[str, Any], shutdown: dict[str, Any]
) -> str:
    lines: list[str] = []
    lines.append("# Customer auth activation readiness (Gate 115)")
    lines.append("")
    lines.append(
        "A customer auth **activation boundary** exists. **Customer auth is not "
        "live and login is not live.** No route in this application requires a "
        "credential, no identity provider is configured, and nobody has "
        "authorized activation."
    )
    lines.append("")
    lines.append("## The gates")
    lines.append("")
    lines.append("```text")
    total = declaration["required_auth_gate_count"]
    satisfied_count = total - declaration["missing_auth_gate_count"]
    lines.append(f"satisfied  {satisfied_count} of {total}")
    lines.append("")
    for name in sorted(gate.get("missing_auth_gates") or []):
        lines.append(f"missing    {name}")
    lines.append("```")
    lines.append("")
    lines.append("## What lifts each one")
    lines.append("")
    lines.append("```text")
    for entry in gate.get("next_required_actions") or []:
        lines.append(f"{entry['gate']}")
        lines.append(f"    {entry['action']}")
    lines.append("```")
    lines.append("")
    lines.append("## Three things that are not customer app auth")
    lines.append("")
    lines.append("```text")
    lines.append(
        "Cloudflare Access    gates who reaches the tunnel; establishes no "
        "NativeForge principal, organization or role"
    )
    lines.append(
        "the frontend preview a served page is not a backend session"
    )
    lines.append(
        "X-NF-Org-Id          UUID-validated and existence-checked, and it "
        "establishes nothing about who is asking"
    )
    lines.append("```")
    lines.append("")
    lines.append("## The dev header")
    lines.append("")
    lines.append("```text")
    lines.append(
        f"enabled by default                    "
        f"{_flag(shutdown['dev_header_enabled_default'])}"
    )
    lines.append(
        f"route modules depending on it         "
        f"{shutdown['dev_header_used_by_routes']}"
    )
    lines.append(
        f"safe to disable now                   "
        f"{_flag(shutdown['safe_to_disable_now'])}"
    )
    lines.append(
        f"must disable before production auth   "
        f"{_flag(shutdown['must_disable_before_production_auth'])}"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "Those first two lines are why it cannot go yet, and the last is why it "
        "cannot stay. Removing it today would break the application without "
        "making anything safer; letting it reach production auth would leave an "
        "unauthenticated way to read another Tribe's data by typing a UUID."
    )
    lines.append("")
    lines.append("## Secrets")
    lines.append("")
    lines.append(
        "No secret value appears in any file in this directory. Presence is "
        "reported as a boolean, and three independent checks scan for leakage: "
        "in the preflight service, in the activation gate, and here before "
        "anything is written."
    )
    lines.append("")
    lines.append("## What is true")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if FIXED_CLAIMS[claim]:
            lines.append(f"{claim:52s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append("## Claims this gate does not make")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if not FIXED_CLAIMS[claim]:
            lines.append(f"{claim:52s} {_flag(declaration[claim])}")
    for claim in sorted(MEASURED_CLAIMS):
        lines.append(f"{claim:52s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append(
        "No identity provider was contacted, no network call was made, no user "
        "or session was created, no URL was fetched, no collector ran and no "
        "source was monitored."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_activation_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all six artifacts. Refuses outright if any secret value appears."""
    from nativeforge.services.customer_auth_activation_demo_fixture_service import (
        build_activation_demo_fixture_set,
    )
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    declaration = build_activation_declaration()
    gate = build_customer_auth_activation_gate()
    routes = build_route_readiness()
    shutdown = build_dev_header_shutdown_readiness()
    roles = build_demo_role_mapping_matrix()
    fixture = build_activation_demo_fixture_set()

    contents = {
        "customer_auth_activation_gate.json": json.dumps(
            gate, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_route_readiness_matrix.csv": render_route_matrix(routes),
        "customer_auth_role_mapping_matrix.csv": render_role_mapping_matrix(roles),
        "dev_org_header_shutdown_readiness.json": json.dumps(
            shutdown, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_activation_demo_fixtures.json": json.dumps(
            fixture, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_activation_readiness_summary.md": render_readiness_summary(
            declaration, gate, shutdown
        ),
    }

    # The last check before anything reaches disk. A committed artifact is the
    # worst place for a client secret: it survives in history after deletion.
    leaked = scan_for_secret_values("".join(contents.values()))
    if leaked:
        raise RuntimeError(
            "refusing to write auth artifacts: a configured environment value "
            f"appears in the payload for {sorted(leaked)}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Any] = {}
    for name, body in contents.items():
        path = out_dir / name
        path.write_text(body, encoding="utf-8")
        written[name] = str(path)

    written["declaration"] = declaration
    written["gate"] = gate
    written["shutdown"] = shutdown
    written["roles"] = roles
    written["fixture"] = fixture
    return written


def activation_artifact_invariant_failures(
    declaration: dict[str, Any],
    *,
    summary_text: str = "",
    route_matrix_text: str = "",
    role_matrix_text: str = "",
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for claim, expected in FIXED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"artifact_missing_claim:{claim}")
        elif declaration[claim] is not expected:
            fails.append(f"artifact_claim_wrong:{claim}")

    for claim in MEASURED_CLAIMS:
        if claim not in declaration:
            fails.append(f"artifact_missing_claim:{claim}")
        elif not isinstance(declaration[claim], bool):
            fails.append(f"artifact_claim_is_not_a_boolean:{claim}")

    # secret_present must be a boolean and nothing richer. A string here would
    # mean somebody widened it into carrying a value.
    if not isinstance(declaration.get("secret_present"), bool):
        fails.append("secret_present_is_not_a_boolean")

    for constant in (
        "cloudflare_access_is_customer_auth",
        "dev_header_is_customer_auth",
        "frontend_preview_is_backend_login",
        "secret_value_emitted",
        "secrets_stored",
        "network_calls",
        "identity_provider_contacted",
        "real_users_created",
        "real_sessions_created",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"activation_artifact_claimed:{constant}")

    # Live requires every gate. Restated here because this is the artifact a
    # reader quotes, and it must not be able to disagree with the gate.
    if declaration.get("customer_auth_live") and declaration.get(
        "missing_auth_gate_count"
    ):
        fails.append("artifact_reports_auth_live_with_missing_gates")

    if declaration.get("customer_auth_live") and not declaration.get(
        "owner_approval_present"
    ):
        fails.append("artifact_reports_auth_live_without_owner_approval")

    if summary_text:
        plain = summary_text.replace("**", "")
        if "Customer auth is not live and login is not live" not in plain:
            fails.append("summary_does_not_say_auth_is_not_live")
        if "Cloudflare Access" not in summary_text:
            fails.append("summary_omits_that_cloudflare_access_is_not_auth")
        if "X-NF-Org-Id" not in summary_text:
            fails.append("summary_omits_the_dev_header")
        if "No secret value appears" not in summary_text:
            fails.append("summary_omits_the_secret_posture")
        for name in declaration.get("missing_auth_gates") or []:
            if name not in summary_text:
                fails.append(f"summary_omits_missing_gate:{name}")

    if route_matrix_text:
        parsed = list(csv.reader(io.StringIO(route_matrix_text)))
        body = parsed[1:]
        satisfied = {row[0]: row[2] for row in body if len(row) >= 3}
        if satisfied.get("ready_for_live_login") == "true":
            fails.append("route_matrix_reports_login_ready")
        for field in (
            "cloudflare_access_is_customer_auth",
            "dev_header_is_customer_auth",
        ):
            if satisfied.get(field) != "false":
                fails.append(f"route_matrix_counts_as_auth:{field}")

    if role_matrix_text:
        parsed = list(csv.reader(io.StringIO(role_matrix_text)))
        header, body = parsed[0], parsed[1:]
        role = header.index("least_privilege_role")
        verify = header.index("can_verify_binding")
        edit = header.index("can_edit_grants")
        for row in body:
            if row[role] == "unknown" and (
                row[verify] == "true" or row[edit] == "true"
            ):
                fails.append("role_matrix_grants_an_unknown_role")
            if row[role] in {"grants_viewer", "auditor"} and row[verify] == "true":
                fails.append(f"role_matrix_lets_a_read_only_role_verify:{row[role]}")
            if row[role] == "grants_manager" and row[verify] == "true":
                fails.append("role_matrix_lets_grants_manager_verify")

    return fails
