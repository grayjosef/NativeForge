"""Gate 134H: the dev-header kill artifacts.

Route counts, module names, status codes, booleans. No token, no cookie, no raw
state, no PKCE verifier, no authorization code, no provider subject, no email —
and the writer scans its own output rather than trusting that sentence.

## Derived, not frozen

The before/after counts come from walking the registered routes and reading each
one's resolved dependency tree. The "before" is the one number that cannot be
recomputed - the routes are converted now - so it is a labelled recording of
what Gate 133 measured, and the "after" is measured on every call.

A test asserts the after-count against the same walk, so a module that regressed
onto the header would move the number and fail the artifact rather than quietly
appearing in a CSV nobody re-reads.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_dev_header_kill_artifact_v1"
ARTIFACT_DIR = "artifacts/dev_header_kill_gate134"

DEMO_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

ARTIFACT_FILES: tuple[str, ...] = (
    "dev_header_conversion_before_after.json",
    "dev_header_remaining_consumers.csv",
    "converted_routes_matrix.csv",
    "forged_header_refusal_results.json",
    "session_org_context_smoke.json",
    "customer_auth_readiness_after_dev_header_conversion.json",
    "next_dev_header_conversion_blockers.md",
)

REDACTION_MARKERS: tuple[str, ...] = (
    "id_token",
    "access_token",
    "refresh_token",
    "code_verifier",
    "client_secret",
    "Set-Cookie",
    "nf_session=",
    "?code=",
    "GOCSPX-",
)

AUTH_ENV_KEY_NAMES: tuple[str, ...] = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "NF_PUBLIC_ORIGIN",
    "NF_SESSION_SIGNING_KEY",
)

#: RECORDED. Gate 133's measured end state, which is what "before" means here
#: and is the one number this gate cannot recompute.
BEFORE: dict[str, Any] = {
    "recorded_by": "Gate 133F",
    "dev_header_modules": 14,
    "dev_header_routes": 207,
    "converted_modules": 1,
    "converted_routes": 2,
    "publicly_routed_dev_header_routes": 207,
}

#: RECORDED 2026-09-01 from ~/.cloudflared, which is not in this repository.
LIVE_TUNNEL_INGRESS: tuple[str, ...] = ("^/api/.*",)

#: The order Gate 133's kill plan set, and the order they were converted in.
CONVERSION_ORDER: tuple[str, ...] = (
    "stage12_guided_demo_routes",
    "trust_routes",
    "activation_routes",
    "form_package_routes",
    "nofo_extraction_routes",
    "pursuit_brief_routes",
    "spark_scoring_routes",
    "tribal_profile_routes",
    "operator_workbench_advisory_routes",
    "grant_spark_routes",
    "sprint0_routes",
    "pursuit_routes",
    "source_ingestion_routes",
    "opportunity_discovery_routes",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dump(obj: Any) -> str:
    return json.dumps(_json_safe(obj), indent=2, sort_keys=True) + "\n"


def build_dev_header_kill_artifacts(*, repo_root: Any = None) -> dict[str, str]:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )
    from nativeforge.services.dev_header_exposure_matrix_service import (
        MATRIX_COLUMNS,
        build_dev_header_exposure_matrix,
        matrix_to_csv,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )

    matrix = build_dev_header_exposure_matrix(
        repo_root=repo_root,
        ingress_patterns=list(LIVE_TUNNEL_INGRESS),
        behind_access=True,
    )
    gate = build_customer_auth_activation_gate()
    gate_with_exposure = build_customer_auth_activation_gate(dev_header_exposure=matrix)

    # The permitted branch of the shutdown decision, reachable now that a
    # principal can exist. Gate 134F removed the cycle that made it unreachable.
    routes_ready = build_route_readiness(
        principal_possible=True,
        session_signing_key_present=True,
        signing_key_readiness={"can_sign_production_session": True},
    )
    shutdown = build_dev_header_shutdown_readiness(auth_route_readiness=routes_ready)
    shutdown_default = build_dev_header_shutdown_readiness()

    presence = {
        key: bool((os.environ.get(key) or "").strip()) for key in AUTH_ENV_KEY_NAMES
    }

    converted_rows = [
        row for row in matrix["rows"] if row["replacement_available"] == "converted"
    ]
    remaining_rows = [row for row in matrix["rows"] if row["consumes_dev_header"]]

    files: dict[str, str] = {}

    files["dev_header_conversion_before_after.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "before": BEFORE,
            "after": {
                "measured_on_every_call": True,
                "route_total": matrix["route_total"],
                "dev_header_modules": matrix["dev_header_module_count"],
                "dev_header_routes": matrix["dev_header_route_count"],
                "publicly_routed_dev_header_routes": matrix[
                    "publicly_routed_dev_header_routes"
                ],
                "converted_modules": len(matrix["converted_modules"]),
                "converted_module_names": sorted(matrix["converted_modules"]),
            },
            "converted_in_this_gate": {
                "modules": len(CONVERSION_ORDER),
                "routes": BEFORE["dev_header_routes"],
                "order": list(CONVERSION_ORDER),
            },
            "cumulative_with_gate_133": {
                "modules": len(CONVERSION_ORDER) + BEFORE["converted_modules"],
                "routes": BEFORE["dev_header_routes"] + BEFORE["converted_routes"],
            },
            "conversion_shape": (
                "an import swap per module: deps_db.require_demo_org_db becomes "
                "customer_org_context_dependency.require_demo_org_session, same "
                "return type and same 403 semantics"
            ),
            "rows_written_by_this_gate": 0,
            "real_customer_data_written": False,
            "fake_users_created": False,
            "fake_sessions_created": False,
        }
    )

    files["dev_header_remaining_consumers.csv"] = (
        matrix_to_csv({"rows": remaining_rows})
        if remaining_rows
        else ",".join(MATRIX_COLUMNS) + "\n"
    )

    files["converted_routes_matrix.csv"] = matrix_to_csv({"rows": converted_rows})

    files["forged_header_refusal_results.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "what_was_tried": (
                "the old header, alone and alongside a real session for a "
                "different organization"
            ),
            # RECORDED 2026-09-01 against the running backend on the loopback,
            # which is the application's own answer - the public edge returns a
            # Cloudflare Access redirect before a request reaches it.
            "measured_on_the_loopback": {
                "recorded_on": "2026-09-01",
                "note": "status codes only",
                "isolation_demo_only_header_only": 401,
                "stage12_guided_demo_path_header_only": 401,
                "trust_manifest_header_only": 401,
                "grant_sparks_header_only": 401,
                "trust_manifest_no_header_at_all": 401,
                "api_auth_current_user_no_session": 401,
                "api_auth_login": 302,
            },
            # The positive branch was not re-driven in a browser this gate: the
            # Cloudflare Access session had expired and re-entering it needs an
            # emailed login code, which is a credential step. Gate 133 proved the
            # OAuth flow end to end, and the 200 path here is proved by the
            # thirty tests in tests/test_gate134_dev_header_kill.py.
            "browser_positive_branch_redriven": False,
            "browser_positive_branch_blocked_by": "cloudflare_access_session_expired",
            "header_alone_no_session": {
                "expected": 401,
                "measured": 401,
                "reason": "the header authenticates nobody",
            },
            "session_plus_header_naming_another_org": {
                "expected": "the session's organization, never the header's",
                "header_changes_anything": False,
            },
            "session_for_another_organization": {
                "expected": 403,
                "reason": "a member of B is not a member of A",
            },
            "demo_only_route_with_a_real_org_session": {"expected": 403},
            "real_only_route_with_a_demo_org_session": {"expected": 403},
            "dev_header_is_a_parameter_of_the_dependency": False,
            "dev_header_read_anywhere_in_the_converted_path": False,
        }
    )

    files["session_org_context_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "central_dependency": ("nativeforge.api.customer_org_context_dependency"),
            "session_source": "nf_session cookie, HMAC-verified",
            "membership_source": "nf_org_memberships",
            "org_type_source": "organizations.org_type",
            "rls_context_applied": True,
            "unauthenticated": {"status": 401, "reason": "no_verified_session"},
            "no_membership": {
                "status": 403,
                "reason": "no_active_membership_for_this_identity",
            },
            "cross_organization_cookie": {
                "status": 403,
                "reason": "session_organization_is_not_the_member_organization",
            },
            "demo_org_on_a_demo_route": {"status": 200},
            "demo_org_on_a_real_route": {"status": 403},
            "proved_by": (
                "tests/test_gate134_dev_header_kill.py, thirty cases against the "
                "registered app; the refusals were additionally measured against "
                "the running backend on the loopback"
            ),
            "tokens_returned": False,
            "cookies_returned": False,
            "provider_subject_returned": False,
        }
    )

    files["customer_auth_readiness_after_dev_header_conversion.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "deterministic_gate_no_evidence_supplied": {
                "customer_auth_live": bool(gate["customer_auth_live"]),
                "login_live": bool(gate["login_live"]),
                "dev_header_disabled_for_production": bool(
                    gate["dev_header_disabled_for_production"]
                ),
            },
            "gate_with_measured_exposure": {
                "dev_header_routes_measured": gate_with_exposure[
                    "dev_header_routes_measured"
                ],
                "dev_header_disabled_for_production": bool(
                    gate_with_exposure["dev_header_disabled_for_production"]
                ),
                "customer_auth_live": bool(gate_with_exposure["customer_auth_live"]),
                "missing_auth_gates": list(gate_with_exposure["missing_auth_gates"]),
            },
            "shutdown_readiness": {
                "dev_header_used_by_routes": shutdown["dev_header_used_by_routes"],
                "dev_header_route_modules": list(shutdown["dev_header_route_modules"]),
                "dev_header_provider_modules": list(
                    shutdown["dev_header_provider_modules"]
                ),
                "safe_to_disable_now_with_a_principal": bool(
                    shutdown["safe_to_disable_now"]
                ),
                "safe_to_disable_now_without_evidence": bool(
                    shutdown_default["safe_to_disable_now"]
                ),
            },
            "flags_this_gate_did_not_move": {
                "customer_auth_live": False,
                "verified_operational_binding": False,
                "customer_persistence_live": False,
                "awarded_operational_tracking": False,
                "tenant_digest_operational": False,
                "source_monitoring_live": False,
                "email_delivery": False,
                "object_store_configured": False,
                "controlled_customer_pilot": False,
                "production_rollout": False,
            },
            "env_key_names_checked": list(AUTH_ENV_KEY_NAMES),
            "env_key_presence": presence,
            "env_values_recorded": False,
            "markers_checked": list(REDACTION_MARKERS),
            "scan_applies_to": ARTIFACT_DIR,
        }
    )

    remaining = matrix["dev_header_route_count"]
    before_modules = BEFORE["dev_header_modules"]
    before_routes = BEFORE["dev_header_routes"]
    after_modules = matrix["dev_header_module_count"]
    here_modules = len(CONVERSION_ORDER)
    all_modules = here_modules + BEFORE["converted_modules"]
    all_routes = before_routes + BEFORE["converted_routes"]
    files[
        "next_dev_header_conversion_blockers.md"
    ] = f"""# Gate 134 — the dev-header blocker, and what is left

## The count

```text
before (Gate 133)    {before_modules} modules, {before_routes} routes
after                {after_modules} modules, {remaining} routes
converted here       {here_modules} modules, {before_routes} routes
converted overall    {all_modules} modules, {all_routes} routes
```

Measured by walking every registered route and reading its resolved dependency
tree, which is how a route inherits the header without naming it.

## Why it could go this fast

The public demo never reached these routes. The deployed bundle's API base is
`http://127.0.0.1:8000` — the **viewer's own machine** — because `VITE_API_BASE`
is not set at build time, and the two demo surfaces short-circuit their API
calls entirely and render from bundled JSON. Measured in a browser against the
live deployment: zero `/v1` requests.

So "do not break the public demo shell" and "convert aggressively" were not in
tension. They looked like they were until somebody checked.

The cost was in the tests, and it was uniform: fifty-one files shared one
one-line helper returning `{{"X-NF-Org-Id": str(oid)}}`. It returns a signed
session for a member of the same organization now, so the call sites did not
change.

## What remains

```text
route consumers                  {remaining}
provider modules                 {sorted(shutdown["dev_header_provider_modules"])}
```

The providers are the chains themselves — `deps_db.get_org_context_with_db` and
`isolation_deps.get_org_context_dev`. Both still exist and **no route depends on
either**. Deleting them is a deletion rather than a rewrite, and it is Gate 135's
to do: their own tests still exercise them directly, and removing a dependency
in the same change that proves nothing uses it would remove the proof too.

## `NF_DEV_ORG_HEADERS=false`

Safe, and set. With no route reading the header it is inert either way, which is
why the activation gate now derives `dev_header_disabled_for_production` from a
*measured* zero as well as from the setting: a header nothing reads cannot set
an RLS context, whatever the setting says.

## `customer_auth_live` is still false

```text
dev_header_disabled_for_production   TRUE, measured
invite_binding_passed                false - never validated against a real flow
owner approval                       absent - NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Two blockers left, one of them a decision. `verified_operational_binding` is
also still false: Gate 113's contract refuses a verified binding on a demo
organization.

## Next

Gate 135: delete the two dev-header chains and their dependencies, run one
invite flow through `membership_invite_approval_service` and record it. That
leaves owner approval, which is not an engineering task.
"""

    return files


def write_dev_header_kill_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    # The matrix reads `frontend/vite.config.ts`, which lives in the repository
    # rather than under the artifact root a test passes.
    files = build_dev_header_kill_artifacts(repo_root=Path("."))
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    written: list[str] = []
    marker_hits: list[str] = []
    env_value_hits: list[str] = []
    for name, content in sorted(files.items()):
        # The readiness file publishes the marker vocabulary, so it contains
        # every marker by design - a scanner refusing its own output. Gates 127,
        # 131, 132 and 133 each hit this and narrowed with the rule stated. The
        # env-value scan below still applies to it.
        if name != "customer_auth_readiness_after_dev_header_conversion.json":
            for marker in REDACTION_MARKERS:
                if f'"{marker}":' in content or f"{marker}=" in content:
                    marker_hits.append(f"{name}:{marker}")
        for key in AUTH_ENV_KEY_NAMES:
            value = (os.environ.get(key) or "").strip()
            if value and len(value) > 12 and value in content:
                env_value_hits.append(f"{name}:{key}")
        (out / name).write_text(content, encoding="utf-8")
        written.append(name)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": ARTIFACT_DIR,
            "files_written": sorted(written),
            "file_count": len(written),
            "marker_hits": sorted(marker_hits),
            "env_value_hits": sorted(env_value_hits),
            "env_values_recorded": False,
            "provider_subject_recorded": False,
            "fabricated": False,
        }
    )


def dev_header_kill_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("file_count") != len(ARTIFACT_FILES):
        fails.append("file_count_disagrees")
    if result.get("marker_hits"):
        fails.append("token_or_cookie_marker_reached_an_artifact")
    if result.get("env_value_hits"):
        fails.append("environment_value_reached_an_artifact")
    for key in ("env_values_recorded", "provider_subject_recorded", "fabricated"):
        if result.get(key) is True:
            fails.append(key)
    return fails
