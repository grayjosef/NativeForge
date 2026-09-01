"""Gate 133H: the login-live and dev-header-kill artifacts.

Booleans, route counts, module names, blocker names. No token, no cookie, no
raw state, no PKCE verifier, no authorization code, no provider subject, no
email address — and the writer scans its own output rather than trusting that
sentence.

## Two kinds of number in here, labelled

```text
derived     recomputed from the code and the committed configs on every call.
            The activation gate with no evidence supplied, the route matrix, the
            preview proxy prefixes, the owner decision's scope.
recorded    measured once against the live deployment and frozen so the files
            regenerate byte-identically. The browser smoke, and the cloudflared
            ingress patterns - which live in the operator's home directory and
            would otherwise make these artifacts machine-specific.
```

Every recorded value carries the date it was measured. Gate 132 established the
labelling convention for exactly this reason: the campaign's recurring defect is
a frozen constant outliving the fact it described.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_login_live_dev_header_kill_artifact_v1"
ARTIFACT_DIR = "artifacts/login_live_dev_header_kill"

DEMO_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://accounts.google.com"

VALIDATION_TABLE = "nf_auth_validation_events"
MEMBERSHIP_TABLE = "nf_org_memberships"

ARTIFACT_FILES: tuple[str, ...] = (
    "jwks_validation_evidence.json",
    "role_mapping_evidence.json",
    "owner_activation_decision.json",
    "login_live_readiness_after_gate133.json",
    "dev_header_exposure_matrix.csv",
    "dev_header_kill_plan.md",
    "current_user_login_live_smoke.json",
    "next_customer_auth_blockers.md",
)

#: Anything matching these in an artifact would be a leak.
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

#: RECORDED 2026-09-01 from ~/.cloudflared. See the module docstring: the
#: cloudflared config is not in this repository, so a matrix built from the
#: machine's copy could not regenerate anywhere else.
LIVE_TUNNEL_INGRESS: tuple[str, ...] = ("^/api/.*",)

#: RECORDED 2026-09-01, in a browser, against the live dev deployment.
#: Booleans and status codes only.
LIVE_SMOKE: dict[str, Any] = {
    "recorded_on": "2026-09-01",
    "login_redirect_to_google": True,
    "callback_reached_api": True,
    "state_validated": True,
    "pkce_validated": True,
    "token_exchange_succeeded": True,
    "token_exchange_http_status": 200,
    "identity_validated": True,
    "identity_verification_state": "verified",
    "identity_email_domain": "gmail.com",
    "validation_evidence_recorded": True,
    "organization_resolved": True,
    "membership_verified": True,
    "session_created": True,
    "current_user_status_code": 200,
    "current_user_authenticated": True,
    "current_user_organization_id": DEMO_ORG_ID,
    "current_user_roles": ["org_owner"],
    "current_user_email_returned": False,
    # The gate on the callback's own response still read false: it is computed
    # at the start of the request, and the validation event is written during
    # it. The next request saw it.
    "login_live_on_the_callback_response": False,
    "login_live_on_the_next_request": True,
    "customer_auth_live": False,
    # The converted routes, through the same session.
    "isolation_demo_only_status_code": 200,
    "isolation_real_only_status_code": 403,
}

#: RECORDED 2026-09-01. The application's own unauthenticated answer, measured
#: on the loopback - the public edge returns 302 from Cloudflare Access before
#: a request reaches the app.
LIVE_REFUSALS: dict[str, Any] = {
    "current_user_no_cookie_loopback": 401,
    "current_user_forged_cookie_loopback": 401,
    "current_user_public_no_access_session": 302,
    "public_302_source": "cloudflare_access",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dump(obj: Any) -> str:
    return json.dumps(_json_safe(obj), indent=2, sort_keys=True) + "\n"


def build_login_live_artifacts(*, repo_root: Any = None) -> dict[str, str]:
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        REQUIRED_LOGIN_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_jwks_validation_evidence_service import (
        EVENT_FIELDS,
        FORBIDDEN_EVENT_KEYS,
        VERIFICATION_STATES,
    )
    from nativeforge.services.customer_auth_owner_activation_decision_service import (
        NOT_APPROVED,
        build_owner_activation_decision,
    )
    from nativeforge.services.customer_auth_role_mapping_evidence_service import (
        ROLE_MAPPING_SOURCE,
        UNTRUSTED_ROLE_SOURCES,
    )
    from nativeforge.services.dev_header_exposure_matrix_service import (
        build_dev_header_exposure_matrix,
        matrix_to_csv,
    )
    from nativeforge.services.membership_directory_service import (
        TRUSTED_MEMBERSHIP_SOURCES,
        TRUSTED_ROLE_SOURCES,
    )

    # No evidence supplied: the deterministic answer, so this file is the same
    # on every machine. The measured answer is recorded beside it.
    gate = build_customer_auth_activation_gate()

    decision = build_owner_activation_decision(
        organization_id=DEMO_ORG_ID, provider=ISSUER, app_env="dev"
    )
    refused = build_owner_activation_decision(
        organization_id=REAL_ORG_ID, provider=ISSUER, app_env="dev"
    )
    production = build_owner_activation_decision(
        organization_id=DEMO_ORG_ID, provider=ISSUER, app_env="production"
    )

    matrix = build_dev_header_exposure_matrix(
        repo_root=repo_root,
        ingress_patterns=list(LIVE_TUNNEL_INGRESS),
        behind_access=True,
    )

    presence = {
        key: bool((os.environ.get(key) or "").strip()) for key in AUTH_ENV_KEY_NAMES
    }

    files: dict[str, str] = {}

    files["jwks_validation_evidence.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "table": VALIDATION_TABLE,
            "migration": "0037",
            "evidence_source": "oauth_callback",
            "recorded_from": "the real callback, on every login",
            "what_the_row_holds": list(EVENT_FIELDS),
            "what_the_row_refuses": list(FORBIDDEN_EVENT_KEYS),
            "verification_states_recognised": sorted(VERIFICATION_STATES),
            "token_stored": False,
            "jwks_document_stored": False,
            "key_material_stored": False,
            "audience_value_stored": False,
            "provider_subject_stored": False,
            "email_stored": False,
            "raw_claims_stored": False,
            "key_id_stored_as": "sha256(kid) truncated to 32 hex characters",
            "issuer_stored_plaintext": True,
            "issuer_stored_rationale": (
                "public, and the gate has to know WHICH issuer passed; "
                "migration 0030 stores it in plaintext already"
            ),
            "organization_id_column": False,
            "rls_policy": False,
            "no_rls_rationale": (
                "written before any organization is known, the same reason "
                "migration 0030 gives for nf_auth_redirect_states; an invented "
                "anchor would make the RLS predicate pass on a value nobody chose"
            ),
            "append_only": True,
            "database_checks": [
                "evidence_source IN ('oauth_callback')",
                "verification_state IN (fifteen named states)",
                "id_token_signature_validated = false OR jwks_validated = true",
                "verification_state <> 'verified' OR every validation true",
            ],
            "measured_live": {
                "note": "a recording; regenerate by running a login",
                "recorded_on": "2026-09-01",
                "event_rows": 1,
                "verified_event_rows": 1,
                "issuers_validated": [ISSUER],
                "provider_called": True,
                "issuer_jwks_validated": True,
                "algorithm_observed": "RS256",
            },
            "deterministic_gate_no_evidence_supplied": {
                "issuer_jwks_validated": bool(gate["issuer_jwks_validated"]),
            },
        }
    )

    files["role_mapping_evidence.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "role_mapping_source": ROLE_MAPPING_SOURCE,
            "membership_table": MEMBERSHIP_TABLE,
            "new_storage_required": False,
            "new_storage_rationale": (
                "a membership row is the thing itself rather than a report about "
                "an event, so it survives the process without being written down "
                "again; role_mapping_passed needed a query, not a migration"
            ),
            "trusted_role_sources": sorted(TRUSTED_ROLE_SOURCES),
            "trusted_membership_sources": sorted(TRUSTED_MEMBERSHIP_SOURCES),
            "refused_role_sources": sorted(UNTRUSTED_ROLE_SOURCES),
            "cookie_claim_can_override_membership": False,
            "cookie_override_checked_by": (
                "offering the resolver a claim and asserting it refuses; the "
                "resolver takes no organization parameter, so the call raises "
                "TypeError"
            ),
            "email_domain_can_map_a_role": False,
            "email_domain_can_map_an_organization": False,
            "header_can_map_a_role": False,
            "token_claim_can_map_a_role": False,
            "measured_live": {
                "note": "a recording; regenerate by querying the dev database",
                "recorded_on": "2026-09-01",
                "mapped_identities": 1,
                "mapped_organizations": [DEMO_ORG_ID],
                "roles_observed": ["org_owner"],
                "membership_sources_observed": ["org_owner_approved"],
                "role_sources_observed": ["membership_record"],
                "role_mapping_passed": True,
            },
            "deterministic_gate_no_evidence_supplied": {
                "role_mapping_passed": bool(gate["role_mapping_passed"]),
            },
        }
    )

    files["owner_activation_decision.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "authorization_source": decision["authorization_source"],
            "approved_organization_id": DEMO_ORG_ID,
            "refused_organization_id": REAL_ORG_ID,
            "approved_provider": "google",
            "approved_environments": ["local", "dev", "test"],
            "revocation_env": "NF_DEMO_LOGIN_ACTIVATION_REVOKED",
            "no_env_var_can_grant_it": True,
            "in_scope_demo_org": {
                "approves_login_live": bool(decision["approves_login_live"]),
                "approves_customer_auth_live": bool(
                    decision["approves_customer_auth_live"]
                ),
                "blocked_reasons": list(decision["blocked_reasons"]),
            },
            "out_of_scope_real_org": {
                "approves_login_live": bool(refused["approves_login_live"]),
                "blocked_reasons": list(refused["blocked_reasons"]),
            },
            "out_of_scope_production_environment": {
                "approves_login_live": bool(production["approves_login_live"]),
                "blocked_reasons": list(production["blocked_reasons"]),
            },
            "not_approved": list(NOT_APPROVED),
            "customer_auth_approval_still_lives_in": (
                "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL"
            ),
            "customer_auth_approval_present": bool(gate["owner_approval_present"]),
        }
    )

    files["login_live_readiness_after_gate133.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "required_login_gates": list(REQUIRED_LOGIN_GATES),
            "required_auth_gates": list(REQUIRED_AUTH_GATES),
            "deterministic_gate_no_evidence_supplied": {
                "login_live": bool(gate["login_live"]),
                "customer_auth_live": bool(gate["customer_auth_live"]),
                "login_activation_approved": bool(gate["login_activation_approved"]),
                "missing_login_gates": list(gate["missing_login_gates"]),
                "blocked_reasons": list(gate["blocked_reasons"]),
            },
            "measured_against_the_dev_deployment": {
                "note": "a recording; regenerate by calling /api/auth/current-user",
                "recorded_on": "2026-09-01",
                "login_live": True,
                "customer_auth_live": False,
                "issuer_jwks_validated": True,
                "role_mapping_passed": True,
                "callback_session_validated": True,
                "org_binding_passed": True,
                "session_signing_key_ready": True,
                "remaining_customer_auth_blockers": [
                    "dev_header_disabled_for_production",
                    "invite_binding_passed",
                    "owner_has_not_authorized_customer_auth_activation",
                ],
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

    files["dev_header_exposure_matrix.csv"] = matrix_to_csv(matrix)

    files["current_user_login_live_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route": "/api/auth/current-user",
            "authenticated": LIVE_SMOKE,
            "unauthenticated": LIVE_REFUSALS,
            "tokens_returned": False,
            "cookies_returned": False,
            "raw_state_returned": False,
            "raw_pkce_verifier_returned": False,
            "authorization_code_returned": False,
            "provider_subject_returned": False,
            "email_returned": False,
            "subject_field_carries": "internal identity id",
            "organization_from_membership_row_not_the_cookie": True,
        }
    )

    kill_plan_rows = "\n".join(
        f"| {row['recommended_order']} | `{row['module']}` | {row['routes']} | "
        f"{row['conversion_risk']} | {row['conversion_note']} |"
        for row in sorted(
            (r for r in matrix["rows"] if r["consumes_dev_header"]),
            key=lambda r: r["recommended_order"],
        )
    )

    files["dev_header_kill_plan.md"] = f"""# Gate 133F — the dev-header kill plan

## Where it stands

```text
routes total                     {matrix["route_total"]}
routes reading X-NF-Org-Id       {matrix["dev_header_route_count"]}
modules reading it               {matrix["dev_header_module_count"]}
converted in Gate 133F           isolation_routes (2 routes)
publicly routed of those         {matrix["publicly_routed_dev_header_routes"]}
behind Cloudflare Access         {matrix["behind_access"]}
```

## How they are reachable, which was not what the detector said

```text
cloudflared ingress   {list(LIVE_TUNNEL_INGRESS)}  -> 127.0.0.1:8000
cloudflared catch-all (hostname)   -> 127.0.0.1:5175   the Vite preview
vite preview proxy    {matrix["preview_proxy_prefixes"]}  -> 127.0.0.1:8000
```

Every dev-header route is under `/v1`, so **none is reached by the ingress rule
`dev_org_header_containment_service` inspects.** They are reached by the preview
proxy, one hop further in, which that detector does not model. Its conclusion
(`backend_publicly_exposed: true`) is right today because of the `/api/*` rule —
which covers the five auth routes and no dev-header route. Delete that ingress
line and it would report the backend contained while all
{matrix["dev_header_route_count"]} stayed exposed.

Third instance of this shape in three gates: Gate 130's detector read the wrong
cloudflared file, Gate 131's migration reader hardcoded one filename for a table
defined by two, this one models one hop of two.

## The order, least risky first

| # | module | routes | risk | why |
|---|---|---:|---|---|
{kill_plan_rows}

Within a risk band the smaller surface goes first. The order is derived from the
risk classification and the measured route counts, not written out by hand.

## Why the rest cannot go in this gate

The demo shell sends `X-NF-Org-Id` and no cookie. Converting a module it calls
returns 401 to the demo, and the demo is what the deployment exists to show.
Exactly one identity has a membership, so a session exists for one person.

`isolation_routes` went first because it is the only module nothing calls — no
frontend code, no script, no e2e spec — and because it ran on the weaker
`isolation_deps` chain, which resolves `org_type` from the settings allowlist
rather than from the `organizations` row. That chain now has **zero route
consumers**, which makes deleting it a deletion rather than a rewrite.

## What each conversion has to do

```text
1  depend on deps_customer_auth.get_customer_org_context_required (or the
   demo/real guards beside it) instead of deps_db.get_org_context_with_db
2  return 401 when there is no verified session, rather than falling back to
   the header
3  keep organization_id as the authority: the membership row supplies it, and a
   cookie claiming a different organization gets nothing
```

Gate 133F made two upgrades that any conversion needs and that Gate 122 could
not make when it wrote the replacement:

```text
membership_verified   was hardcoded False; Gate 132 built the read path
org_type              was hardcoded "real"; it reads organizations.org_type now
```

## Then, and only then

`NF_DEV_ORG_HEADERS=false`, and `dev_header_disabled_for_production` becomes
true — the last `customer_auth_live` blocker that is engineering rather than a
decision. Flipping it before the conversions would 401
{matrix["dev_header_route_count"]} routes at once.
"""

    files[
        "next_customer_auth_blockers.md"
    ] = f"""# Gate 133 — what moved, and what `customer_auth_live` still waits on

## `login_live` is true

```text
issuer_jwks_validated       now measured from {VALIDATION_TABLE} (migration 0037)
role_mapping_passed         now measured from {MEMBERSHIP_TABLE}
login activation decision   recorded, demo-scoped, cannot approve customer auth
+ the nine gates that already held
```

Measured on the deployment: `login_live: true`, `customer_auth_live: false`.

Two of those three were literals. `callback_session_validated = False` was
assigned once and never again; `org_binding_passed` and `role_mapping_passed`
were parameters of `run_auth0_live_validation` that no caller passed. Gate 132
fixed the first two the same way. A constant frozen in one gate becomes a lie in
the next, and this is the fourth time this campaign has found that exact shape.

## `customer_auth_live` is false, for three reasons

### `dev_header_disabled_for_production`

{matrix["dev_header_route_count"]} routes across
{matrix["dev_header_module_count"]} modules still read `X-NF-Org-Id`, and
every one of them is publicly routed through the preview proxy behind
Cloudflare Access.
Access gates *who reaches the app*; it does nothing about which organization a
header names once somebody is through. Anybody in the Access policy can read any
organization's rows.

Gate 133F converted `isolation_routes` and wrote the order for the rest. This is
the blocker that is engineering rather than a decision, and it is Gate 134's.

### `invite_binding_passed`

Never validated against a real flow. There is an invite/approval service
(`membership_invite_approval_service`) and no flow has run through it, so this
is unvalidated rather than failed — the same distinction the JWKS gate needed,
and the same fix: run one and record it.

### owner approval

`NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is unset. Gate 133D deliberately did not
touch it: the demo login decision is a different decision, and
`approves_customer_auth_live()` has no branch that returns True. Claiming
customer auth is live for real Tribal governments is Mayhem's to decide
out-of-band.

## And `verified_operational_binding` is still false

Gate 113's contract refuses a verified binding on a demo organization — a demo
binding may not carry a verifier. The binding is a `demo_fixture`. It becomes
reachable when a real organization is authorized, which is a separate decision
and was explicitly out of scope here.

## Unchanged, stated so nothing above reads as progress on them

```text
controlled_customer_pilot      false
production_rollout             false
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

## Next

Gate 134: convert the dev-header modules in the order in
`dev_header_kill_plan.md`, starting with `stage12_guided_demo_routes` and
`trust_routes`, then flip `NF_DEV_ORG_HEADERS=false`. That clears the only
`customer_auth_live` blocker nobody has to decide.
"""

    return files


def write_login_live_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    # The matrix reads `frontend/vite.config.ts`, which lives in the repository
    # rather than under the artifact root a test passes.
    files = build_login_live_artifacts(repo_root=Path("."))
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    written: list[str] = []
    marker_hits: list[str] = []
    env_value_hits: list[str] = []
    for name, content in sorted(files.items()):
        # The readiness file publishes the marker vocabulary, so it contains
        # every marker by design. Scanning it for them is a scanner refusing its
        # own output - Gates 127, 131 and 132 each hit this and narrowed with the
        # rule stated rather than dropping the check. The env-value scan below
        # still applies to it, because listing a key NAME is not carrying a value.
        if name != "login_live_readiness_after_gate133.json":
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


def login_live_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
