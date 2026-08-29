"""Customer auth enforcement artifacts (Gate 117I).

Six files describing what now refuses, what a redirect flow would need, and what
none of it makes true. Written to `artifacts/customer_auth_route_enforcement/`.

```text
customer_auth_dependency_contract.json      four modes against four callers
customer_auth_redirect_flow_contract.json   the flow, refusing at each step
customer_auth_state_pkce_contract.json      state and PKCE, fixture values only
customer_auth_token_exchange_boundary.json  six conditions, one of them network
customer_auth_enforcement_demo_fixtures.json  the fixture set entire
customer_auth_route_enforcement_readiness_summary.md
```

## No real state, verifier, token or secret reaches a file

The state and PKCE artifact carries `build_fixture_state_pkce()` values -
prefixed `nf-demo-fixture-`, short enough to fail their own entropy checks, and
labelled. A real generated state has no business in a committed file: it is not
a secret, but a file full of plausible-looking states is a file somebody will
eventually copy into a config.

Before writing, this service scans the assembled payload for every configured
`OIDC_*` environment value and raises rather than writing. It also refuses any
payload carrying a field named like a token.

## The summary's job

Gate 117 is the first gate where NativeForge says no to somebody. That is easy
to read as "auth works now", so the summary states both halves in its first
paragraph: one route refuses, and nobody can log in.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_enforcement_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_auth_route_enforcement"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "auth_dependency_contract_available": True,
    "redirect_flow_contract_available": True,
    "state_pkce_contract_available": True,
    "token_exchange_boundary_available": True,
    "customer_auth_live": False,
    "login_live": False,
    "real_sessions_created": False,
    "real_users_created": False,
    "provider_called": False,
    "secrets_exposed": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
}

# Claims whose value is whatever the application actually serves.
MEASURED_CLAIMS: tuple[str, ...] = (
    "route_auth_enforced",
    "secured_route_count",
)

# Field names that would mean a credential had entered an artifact.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "id_token",
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization_code",
    }
)


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


def scan_for_credential_fields(payload: Any) -> list[str]:
    """Which forbidden field names appear anywhere in this payload.

    Returns names, never values. Walks nested structures because a token buried
    three levels down is still a token in a committed file.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_VALUE_FIELDS:
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def build_enforcement_declaration() -> dict[str, Any]:
    """Every required claim, each read from the service that owns it."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
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

    gate = build_customer_auth_activation_gate()
    routes = build_route_readiness()
    shutdown = build_dev_header_shutdown_readiness()
    persistence = build_capability_matrix()
    beta = build_tenant_beta_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_dependency_contract_available": True,
            "redirect_flow_contract_available": True,
            "state_pkce_contract_available": True,
            "token_exchange_boundary_available": True,
            # Measured.
            "route_auth_enforced": bool(routes["route_auth_enforced"]),
            "secured_route_count": routes["secured_route_count"],
            "route_org_resolution_enforced": bool(
                routes["route_org_resolution_enforced"]
            ),
            "route_role_mapping_enforced": bool(routes["route_role_mapping_enforced"]),
            "ready_for_live_login": bool(routes["ready_for_live_login"]),
            "application_route_count": routes["application_route_count"],
            # Unchanged by this gate.
            "customer_auth_live": bool(gate["customer_auth_live"]),
            "login_live": bool(gate["login_live"]),
            "missing_auth_gate_count": len(gate["missing_auth_gates"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "dev_header_safe_to_disable_now": bool(shutdown["safe_to_disable_now"]),
            "dev_header_must_disable_before_production_auth": bool(
                shutdown["must_disable_before_production_auth"]
            ),
            "customer_persistence_live": bool(
                persistence["customer_persistence_live"]
            ),
            "beta_onboarding_ready": bool(beta["ready_for_beta_onboarding"]),
            # Constants.
            "real_sessions_created": False,
            "real_users_created": False,
            "provider_called": False,
            "secrets_exposed": False,
            "tokens_exposed": False,
            "network_calls": False,
            "current_org_id_set": False,
            "cloudflare_access_is_customer_auth": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "fabricated": False,
        }
    )


def render_dependency_matrix(matrix: dict[str, Any]) -> str:
    columns = (
        "dependency_mode",
        "session_cookie_present",
        "session_cookie_valid",
        "principal_resolved",
        "authenticated",
        "authorized",
        "http_status",
        "security_scheme_required",
        "sets_rls_context",
        "blocked_reasons",
    )
    rows = [
        [
            row["dependency_mode"],
            _flag(row["session_cookie_present"]),
            _flag(row["session_cookie_valid"]),
            _flag(row["principal_resolved"]),
            _flag(row["authenticated"]),
            _flag(row["authorized"]),
            row["http_status"],
            _flag(row["security_scheme_required"]),
            _flag(row["sets_rls_context"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in matrix["rows"]
    ]
    return _csv(columns, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Customer auth route enforcement readiness (Gate 117)")
    lines.append("")
    lines.append(
        "`/api/auth/current-user` now returns **401** to an unauthenticated "
        "caller - the first refusal NativeForge has ever issued. **Customer "
        "auth is not live and login is not live.** The route refuses everybody, "
        "because nobody can authenticate."
    )
    lines.append("")
    lines.append("## Enforcement is not liveness")
    lines.append("")
    lines.append("```text")
    lines.append(
        f"route_auth_enforced                  "
        f"{_flag(declaration['route_auth_enforced'])}"
    )
    lines.append(
        f"secured_route_count                  {declaration['secured_route_count']}"
    )
    lines.append(
        f"route_org_resolution_enforced        "
        f"{_flag(declaration['route_org_resolution_enforced'])}"
    )
    lines.append(
        f"route_role_mapping_enforced          "
        f"{_flag(declaration['route_role_mapping_enforced'])}"
    )
    lines.append(
        f"ready_for_live_login                 "
        f"{_flag(declaration['ready_for_live_login'])}"
    )
    lines.append(
        f"customer_auth_live                   "
        f"{_flag(declaration['customer_auth_live'])}"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "A 401 proves the application can say no. It proves nothing about "
        "whether anyone could ever be told yes, and a 401 is not an "
        "organization - nothing resolves one, so organization-resolution and "
        "role-mapping enforcement stay false."
    )
    lines.append("")
    lines.append("## The four contracts this gate added")
    lines.append("")
    lines.append("```text")
    for name, detail in (
        ("auth dependency", "four modes: required, optional, forbid, unknown"),
        ("redirect flow", "nine steps, refusing at each one it cannot take"),
        ("state and PKCE", "real entropy, S256, constant-time comparison"),
        ("token exchange", "six conditions, one of them the network itself"),
    ):
        lines.append(f"{name:22s} {detail}")
    lines.append("```")
    lines.append("")
    lines.append("## What still blocks activation")
    lines.append("")
    lines.append("```text")
    for name in declaration["missing_auth_gates"]:
        lines.append(name)
    lines.append("```")
    lines.append("")
    lines.append(
        "Enforcement moved none of them. Not one is a route fact, which is "
        "exactly why this gate could add a refusal without moving a single "
        "activation gate."
    )
    lines.append("")
    lines.append("## No credential reaches this directory")
    lines.append("")
    lines.append(
        "The state and PKCE artifact carries fixture values prefixed "
        "`nf-demo-fixture-`, short enough to fail their own entropy checks. No "
        "real state, verifier, token or secret is written. Token exchange is "
        "behind `network_call_allowed`, which defaults to false and which "
        "nothing in this repository raises."
    )
    lines.append("")
    lines.append("## What is true")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if FIXED_CLAIMS[claim]:
            lines.append(f"{claim:44s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append("## Claims this gate does not make")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if not FIXED_CLAIMS[claim]:
            lines.append(f"{claim:44s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append(
        "No identity provider was contacted, no network call was made, no user "
        "or session was created, no token was requested, no URL was fetched, no "
        "collector ran and no source was monitored."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_enforcement_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all six artifacts. Refuses if any credential appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.customer_auth_dependency_contract_service import (
        build_dependency_contract_matrix,
    )
    from nativeforge.services.customer_auth_enforcement_demo_fixture_service import (
        build_enforcement_demo_fixture_set,
    )
    from nativeforge.services.customer_auth_redirect_flow_service import (
        build_redirect_flow_contract,
    )
    from nativeforge.services.customer_auth_state_pkce_service import (
        build_fixture_state_pkce,
    )
    from nativeforge.services.customer_auth_token_exchange_boundary_service import (
        evaluate_token_exchange_boundary,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    declaration = build_enforcement_declaration()
    dependency = build_dependency_contract_matrix()
    flow = build_redirect_flow_contract()
    # Fixture values only. A real generated state has no business in a committed
    # file: not a secret, but a file of plausible states is one somebody copies.
    state_pkce = build_fixture_state_pkce()
    boundary = evaluate_token_exchange_boundary()
    fixture = build_enforcement_demo_fixture_set()

    contents = {
        "customer_auth_dependency_contract.json": json.dumps(
            dependency, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_dependency_matrix.csv": render_dependency_matrix(dependency),
        "customer_auth_redirect_flow_contract.json": json.dumps(
            flow, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_state_pkce_contract.json": json.dumps(
            state_pkce, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_token_exchange_boundary.json": json.dumps(
            boundary, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_enforcement_demo_fixtures.json": json.dumps(
            fixture, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_route_enforcement_readiness_summary.md": (
            render_readiness_summary(declaration)
        ),
    }

    blob = "".join(contents.values())
    leaked = scan_for_secret_values(blob)
    if leaked:
        raise RuntimeError(
            "refusing to write enforcement artifacts: a configured environment "
            f"value appears in the payload for {sorted(leaked)}"
        )

    credentials = scan_for_credential_fields(
        [dependency, flow, state_pkce, boundary, fixture]
    )
    if credentials:
        raise RuntimeError(
            "refusing to write enforcement artifacts: a credential-shaped field "
            f"appears in the payload: {credentials}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Any] = {}
    for name, body in contents.items():
        path = out_dir / name
        path.write_text(body, encoding="utf-8")
        written[name] = str(path)

    written["declaration"] = declaration
    written["dependency"] = dependency
    written["flow"] = flow
    written["state_pkce"] = state_pkce
    written["boundary"] = boundary
    written["fixture"] = fixture
    return written


def enforcement_artifact_invariant_failures(
    declaration: dict[str, Any],
    *,
    summary_text: str = "",
    dependency_matrix_text: str = "",
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for claim, expected in FIXED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"artifact_missing_claim:{claim}")
        elif declaration[claim] is not expected:
            fails.append(f"artifact_claim_wrong:{claim}")

    if not isinstance(declaration.get("route_auth_enforced"), bool):
        fails.append("route_auth_enforced_is_not_a_boolean")
    if not isinstance(declaration.get("secured_route_count"), int):
        fails.append("secured_route_count_is_not_an_integer")

    for constant in (
        "tokens_exposed",
        "network_calls",
        "current_org_id_set",
        "cloudflare_access_is_customer_auth",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"enforcement_artifact_claimed:{constant}")

    # Enforcement requires a secured route, and is not liveness.
    if declaration.get("route_auth_enforced") and not declaration.get(
        "secured_route_count"
    ):
        fails.append("artifact_reports_enforcement_with_zero_secured_routes")

    # A 401 is not an organization.
    if declaration.get("route_org_resolution_enforced") and not declaration.get(
        "customer_auth_live"
    ):
        fails.append("artifact_reports_org_resolution_without_live_auth")

    if declaration.get("ready_for_live_login") and not declaration.get(
        "customer_auth_live"
    ):
        fails.append("artifact_reports_login_ready_without_live_auth")

    # The dev header boundary survives this gate.
    if declaration.get("dev_header_must_disable_before_production_auth") is not True:
        fails.append("artifact_permits_the_dev_header_into_production_auth")

    if summary_text:
        plain = summary_text.replace("**", "")
        if "Customer auth is not live and login is not live" not in plain:
            fails.append("summary_does_not_say_auth_is_not_live")
        if "Enforcement is not liveness" not in summary_text:
            fails.append("summary_does_not_separate_enforcement_from_liveness")
        if "network_call_allowed" not in summary_text:
            fails.append("summary_omits_the_network_boundary")
        for name in declaration.get("missing_auth_gates") or []:
            if name not in summary_text:
                fails.append(f"summary_omits_missing_gate:{name}")

    if dependency_matrix_text:
        parsed = list(csv.reader(io.StringIO(dependency_matrix_text)))
        header, body = parsed[0], parsed[1:]
        mode = header.index("dependency_mode")
        status = header.index("http_status")
        authorized = header.index("authorized")
        scheme = header.index("security_scheme_required")
        if not any(row[status] == "401" for row in body):
            fails.append("dependency_matrix_demonstrates_no_refusal")
        for row in body:
            if row[mode] == "required" and row[scheme] != "true":
                fails.append("dependency_matrix_required_mode_without_a_scheme")
            if row[mode] == "unknown" and row[authorized] == "true":
                fails.append("dependency_matrix_unknown_mode_authorized")
            if row[mode] == "optional" and row[status] != "200":
                fails.append("dependency_matrix_optional_mode_refused")

    return fails
