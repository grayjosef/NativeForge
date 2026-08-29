"""Customer auth route artifacts (Gate 116H).

Five files describing the route spine this gate added and what it does not make
true. Written to `artifacts/customer_auth_routes/`.

```text
customer_session_cookie_policy.json          the cookie contract
customer_auth_route_contract.json            five routes, what each may do
customer_auth_route_readiness_matrix.csv     exists vs enforced, per route
customer_auth_route_demo_fixtures.json       the fixture set entire
customer_auth_route_readiness_summary.md     what none of it permits yet
```

## The summary's job

Gate 116 is the gate most likely to be misread as progress, because it is the
first one that adds something a person can visit. Five endpoints appear, a
security scheme appears in the API documentation, and none of it authenticates
anybody.

So the summary opens with both halves — the routes exist, and auth is not live —
and states the distinction the whole gate turns on: a scheme in a document is
documentation, and enforcement is a refusal.

## No secret reaches a file

Every value written here is a boolean, a count, a route path, a cookie attribute
or a blocked reason. Before writing, this service scans the assembled payload
for every configured `OIDC_*` environment value and raises rather than writing
if one appears — reusing Gate 115's scanner rather than writing a second one.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_route_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_auth_routes"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "auth_routes_contract_available": True,
    "session_cookie_policy_available": True,
    "customer_auth_live": False,
    "login_live": False,
    "real_sessions_created": False,
    "real_users_created": False,
    "provider_called": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
}

# Claims whose value is whatever the application actually serves.
MEASURED_CLAIMS: tuple[str, ...] = (
    "login_route_available",
    "callback_route_available",
    "session_route_available",
    "current_user_route_available",
    "logout_route_available",
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


def build_route_declaration() -> dict[str, Any]:
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
    from nativeforge.services.customer_session_cookie_policy_service import (
        build_session_cookie_policy,
        policy_invariant_failures,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    gate = build_customer_auth_activation_gate()
    routes = build_route_readiness()
    policy = build_session_cookie_policy()
    shutdown = build_dev_header_shutdown_readiness()
    persistence = build_capability_matrix()
    beta = build_tenant_beta_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_routes_contract_available": True,
            "session_cookie_policy_available": not policy_invariant_failures(policy),
            # Measured from the application's own route table.
            "login_route_available": bool(routes["login_route_available"]),
            "logout_route_available": bool(routes["logout_route_available"]),
            "callback_route_available": bool(routes["callback_route_available"]),
            "session_route_available": bool(routes["session_route_available"]),
            "current_user_route_available": bool(
                routes["current_user_route_available"]
            ),
            "application_route_count": routes["application_route_count"],
            # The distinction this gate turns on.
            "security_scheme_declared": bool(routes["security_scheme_declared"]),
            "secured_route_count": routes["secured_route_count"],
            "route_auth_enforced": bool(routes["route_auth_enforced"]),
            "ready_for_live_login": bool(routes["ready_for_live_login"]),
            # Unchanged by this gate.
            "customer_auth_live": bool(gate["customer_auth_live"]),
            "login_live": bool(gate["login_live"]),
            "missing_auth_gate_count": len(gate["missing_auth_gates"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "dev_header_used_by_routes": shutdown["dev_header_used_by_routes"],
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
            "cloudflare_access_is_customer_auth": False,
            "dev_header_is_production_safe": False,
            "secret_value_emitted": False,
            "network_calls": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "fabricated": False,
        }
    )


def render_route_matrix(
    contract: dict[str, Any], readiness: dict[str, Any]
) -> str:
    columns = (
        "route",
        "method",
        "route_path",
        "route_available",
        "route_enforced",
        "security_required",
        "provider_call_allowed",
        "creates_real_session",
        "requires_state",
        "requires_pkce",
        "requires_organization_id_resolution",
        "requires_membership_verification",
        "safe_without_provider",
        "blocked_reasons",
    )
    # Gate 117: enforcement is per route, not per application.
    #
    # Gate 116 rendered one value for every row, which was accurate while the
    # answer was "none of them". Now /current-user refuses and the other four do
    # not, and a single column repeating `true` five times would say four things
    # that are false.
    application_enforces = bool(readiness["route_auth_enforced"])
    rows = [
        [
            row["route"],
            row["method"],
            row["route_path"],
            _flag(row["route_available"]),
            _flag(application_enforces and row["security_required"]),
            _flag(row["security_required"]),
            _flag(row["provider_call_allowed"]),
            _flag(row["creates_real_session"]),
            _flag(row["requires_state"]),
            _flag(row["requires_pkce"]),
            _flag(row["requires_organization_id_resolution"]),
            _flag(row["requires_membership_verification"]),
            _flag(row["safe_without_provider"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in contract["rows"]
    ]
    return _csv(columns, rows)


def render_readiness_summary(
    declaration: dict[str, Any], policy: dict[str, Any]
) -> str:
    lines: list[str] = []
    lines.append("# Customer auth route readiness (Gate 116)")
    lines.append("")
    lines.append(
        "NativeForge now has five customer auth routes and a session cookie "
        "policy. **Customer auth is not live and login is not live.** Nothing "
        "on these routes authenticates anybody, and no session has been created."
    )
    lines.append("")
    lines.append("## The routes")
    lines.append("")
    lines.append("```text")
    for claim in MEASURED_CLAIMS:
        lines.append(f"{claim:36s} {_flag(declaration[claim])}")
    lines.append("")
    lines.append(
        f"application routes                   "
        f"{declaration['application_route_count']}"
    )
    lines.append("```")
    lines.append("")
    lines.append("## Declared is not enforced")
    lines.append("")
    lines.append("```text")
    lines.append(
        f"security_scheme_declared             "
        f"{_flag(declaration['security_scheme_declared'])}"
    )
    lines.append(
        f"secured_route_count                  "
        f"{declaration['secured_route_count']}"
    )
    lines.append(
        f"route_auth_enforced                  "
        f"{_flag(declaration['route_auth_enforced'])}"
    )
    lines.append(
        f"ready_for_live_login                 "
        f"{_flag(declaration['ready_for_live_login'])}"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "A security scheme is advertised in the OpenAPI document and attached "
        "to no operation. That is deliberate: a scheme in a document is "
        "documentation, and enforcement is a refusal. Nothing refuses yet."
    )
    lines.append("")
    lines.append("## The session cookie policy")
    lines.append("")
    lines.append("```text")
    for key in (
        "cookie_name",
        "http_only",
        "secure",
        "same_site",
        "path",
        "max_age_seconds",
        "csrf_required",
        "state_required",
        "pkce_required",
        "rotation_required",
        "logout_clears_cookie",
        "production_safe",
    ):
        lines.append(f"{key:24s} {policy[key]!r}")
    lines.append("```")
    lines.append("")
    lines.append(
        "`secure` follows the environment, so a local development policy is "
        "honestly not production-safe rather than pretending to be. PKCE is "
        "required because nothing in this repository proves it unnecessary - "
        "there is no authorization-url builder, no token exchange and no code "
        "verifier anywhere, and an absent flow is not evidence."
    )
    lines.append("")
    lines.append("## What still blocks activation")
    lines.append("")
    lines.append("```text")
    for name in declaration["missing_auth_gates"]:
        lines.append(name)
    lines.append("```")
    lines.append("")
    lines.append(
        "This gate satisfied the two gates a route spine can satisfy. The "
        "remainder are provider configuration, secrets, validation of a real "
        "flow, and removing the dev org header - none of which a route supplies."
    )
    lines.append("")
    lines.append("## The dev org header")
    lines.append("")
    lines.append("```text")
    lines.append(
        f"route modules using it               "
        f"{declaration['dev_header_used_by_routes']}"
    )
    lines.append(
        f"safe to disable now                  "
        f"{_flag(declaration['dev_header_safe_to_disable_now'])}"
    )
    lines.append(
        f"must disable before production auth  "
        f"{_flag(declaration['dev_header_must_disable_before_production_auth'])}"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "The auth routes existing does not make the header removable. A "
        "replacement is a route that can actually authenticate somebody, and "
        "none of these can yet. **Cloudflare Access is not customer app auth.**"
    )
    lines.append("")
    lines.append("## What is true")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if FIXED_CLAIMS[claim]:
            lines.append(f"{claim:40s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append("## Claims this gate does not make")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if not FIXED_CLAIMS[claim]:
            lines.append(f"{claim:40s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append(
        "No identity provider was contacted, no network call was made, no user "
        "or session was created, no cookie carrying a session value was set, "
        "no URL was fetched, no collector ran and no source was monitored."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_route_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Refuses outright if any secret value appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.customer_auth_route_contract_service import (
        build_auth_route_contract_set,
    )
    from nativeforge.services.customer_auth_route_demo_fixture_service import (
        build_route_demo_fixture_set,
    )
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )
    from nativeforge.services.customer_session_cookie_policy_service import (
        build_session_cookie_policy,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    declaration = build_route_declaration()
    policy = build_session_cookie_policy()
    readiness = build_route_readiness()
    contract = build_auth_route_contract_set()
    fixture = build_route_demo_fixture_set()

    contents = {
        "customer_session_cookie_policy.json": json.dumps(
            policy, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_route_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_route_readiness_matrix.csv": render_route_matrix(
            contract, readiness
        ),
        "customer_auth_route_demo_fixtures.json": json.dumps(
            fixture, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_route_readiness_summary.md": render_readiness_summary(
            declaration, policy
        ),
    }

    # Reuses Gate 115's scanner rather than writing a second one. A committed
    # artifact is the worst place for a client secret: it survives in history
    # after the file is deleted.
    leaked = scan_for_secret_values("".join(contents.values()))
    if leaked:
        raise RuntimeError(
            "refusing to write auth route artifacts: a configured environment "
            f"value appears in the payload for {sorted(leaked)}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Any] = {}
    for name, body in contents.items():
        path = out_dir / name
        path.write_text(body, encoding="utf-8")
        written[name] = str(path)

    written["declaration"] = declaration
    written["policy"] = policy
    written["contract"] = contract
    written["fixture"] = fixture
    return written


def route_artifact_invariant_failures(
    declaration: dict[str, Any],
    *,
    summary_text: str = "",
    matrix_text: str = "",
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

    for constant in (
        "cloudflare_access_is_customer_auth",
        "dev_header_is_production_safe",
        "secret_value_emitted",
        "network_calls",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"route_artifact_claimed:{constant}")

    # The rule this gate turns on: declared is not enforced.
    if declaration.get("route_auth_enforced") and not declaration.get(
        "secured_route_count"
    ):
        fails.append("artifact_reports_enforcement_with_zero_secured_routes")

    if declaration.get("ready_for_live_login") and not declaration.get(
        "route_auth_enforced"
    ):
        fails.append("artifact_reports_login_ready_without_enforcement")

    # The dev header boundary survives this gate.
    if declaration.get("dev_header_must_disable_before_production_auth") is not True:
        fails.append("artifact_permits_the_dev_header_into_production_auth")

    if summary_text:
        plain = summary_text.replace("**", "")
        if "Customer auth is not live and login is not live" not in plain:
            fails.append("summary_does_not_say_auth_is_not_live")
        if "documentation, and enforcement is a refusal" not in summary_text:
            fails.append("summary_does_not_separate_declared_from_enforced")
        if "Cloudflare Access is not customer app auth" not in plain:
            fails.append("summary_omits_that_cloudflare_access_is_not_auth")
        for name in declaration.get("missing_auth_gates") or []:
            if name not in summary_text:
                fails.append(f"summary_omits_missing_gate:{name}")

    if matrix_text:
        parsed = list(csv.reader(io.StringIO(matrix_text)))
        header, body = parsed[0], parsed[1:]
        available = header.index("route_available")
        enforced = header.index("route_enforced")
        security = header.index("security_required")
        session = header.index("creates_real_session")
        route = header.index("route")
        if not any(row[available] == "true" for row in body):
            fails.append("matrix_shows_no_available_route")
        # Gate 117: a route may report enforcement only if it requires a
        # credential. Gate 116 asserted no route was enforced at all, which was
        # right then and would now hide the four that still are not.
        for row in body:
            if row[enforced] == "true" and row[security] != "true":
                fails.append(f"matrix_enforces_a_route_that_requires_nothing:{row[route]}")
            if row[session] == "true":
                fails.append(f"matrix_reports_a_session_creating_route:{row[route]}")

    return fails
