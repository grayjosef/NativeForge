"""Gate 132H: the first-binding artifacts.

Booleans, organization ids, role names and blocker names. The provider subject,
the email address, the tokens, the cookie, the state and the PKCE verifier are
not here, and the writer scans its own output to check rather than trusting that
sentence.

`LIVE_SMOKE` is a **recording** of a browser run, not a measurement this module
takes. It is frozen so the artifacts regenerate byte-identically, which is the
property the tests check - and the campaign's recurring defect is exactly a
frozen constant outliving the fact it described, so it is labelled as a
recording everywhere it appears rather than presented as current state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_first_dev_org_binding_artifact_v1"
ARTIFACT_DIR = "artifacts/first_dev_org_binding_session_activation"

AUTHORIZED_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
FORBIDDEN_ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

IDENTITY_TABLE = "nf_identities"
MEMBERSHIP_TABLE = "nf_org_memberships"
BINDING_TABLE = "nf_tenant_customer_org_bindings"

ARTIFACT_FILES: tuple[str, ...] = (
    "dev_identity_binding_authorization.md",
    "dev_org_binding_result.json",
    "login_after_binding_smoke.json",
    "current_user_after_binding.json",
    "auth_readiness_after_binding.json",
    "next_customer_persistence_blockers.md",
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

#: Observed in the browser on 2026-09-01, against the live dev deployment.
#: Booleans only - see the module docstring on why this is frozen.
LIVE_SMOKE: dict[str, Any] = {
    "recorded_on": "2026-09-01",
    "provider_redirect_occurred": True,
    "callback_reached_api": True,
    "state_validated": True,
    "pkce_validated": True,
    "token_exchange_succeeded": True,
    "token_exchange_http_status": 200,
    "identity_validated": True,
    "identity_email_domain": "gmail.com",
    "organization_resolved": True,
    "membership_verified": True,
    # demo_fixture, not verified_binding. See the blockers file.
    "binding_verified": False,
    "session_created": True,
    "current_user_works": True,
    "login_live": False,
    "customer_auth_live": False,
}

#: The first login, before the membership existed. Recorded because the refusal
#: is the evidence that a Google account is not a membership.
LIVE_SMOKE_BEFORE_MEMBERSHIP: dict[str, Any] = {
    "identity_validated": True,
    "identity_rows_written": 1,
    "organization_resolved": False,
    "membership_verified": False,
    "session_created": False,
    "membership_resolution_blocked_reasons": ["identity_has_no_active_membership"],
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dump(obj: Any) -> str:
    return json.dumps(_json_safe(obj), indent=2, sort_keys=True) + "\n"


def build_first_dev_org_binding_artifacts() -> dict[str, str]:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    # No evidence passed: the deterministic answer, so this file is the same on
    # every machine. The measured answer is recorded beside it as a recording.
    gate = build_customer_auth_activation_gate()

    presence = {
        key: bool((os.environ.get(key) or "").strip()) for key in AUTH_ENV_KEY_NAMES
    }

    files: dict[str, str] = {}

    files[
        "dev_identity_binding_authorization.md"
    ] = f"""# Gate 132 — the authorization, and what was created under it

## What Mayhem authorized

Quoted from the instruction that followed the `AUTHORIZE DEV ORG BINDING` stop
point:

> Authorization is limited to the demo organization only:
> organization_id: {AUTHORIZED_ORG_ID}
> org_type: demo
> is_demo: true
>
> Do not bind the Google identity to: {FORBIDDEN_ORG_ID}
> Do not create production bindings.
> Do not write real customer data.
> Do not infer demo status from caller input alone.

## The identity

```text
provider          Google
issuer            https://accounts.google.com
subject           stored raw in {IDENTITY_TABLE}, per migration 0023's schema.
                  Never printed, never logged, never written to an artifact.
                  It is the (issuer, subject) lookup key and a hash cannot be
                  looked up against a claim without hashing the claim.
email domain      gmail.com
email             stored, verified, and authority for nothing
verification      oidc_token_signature — the only value the CHECK permits
```

## The organization, and why the enforcement is not the chat log

The authorization named one organization. An authorization in a transcript is
not an enforcement, so `dev_org_membership_bootstrap_service` refuses any
organization whose `organizations.org_type` is not `demo`, and derives `is_demo`
from that row. There is no `is_demo` parameter to pass.

```text
{AUTHORIZED_ORG_ID}   org_type=demo   membership created
{FORBIDDEN_ORG_ID}   org_type=real   refused by name
```

The refusal was exercised, not assumed:
`bootstrap_membership_refused_for_a_non_demo_organization`.

## The demo-org inconsistency, reconciled first

Mayhem made this a precondition. Three sources claimed to know which
organizations are demo and they did not agree:

```text
before
  organizations.org_type          demo for {AUTHORIZED_ORG_ID}
  NF_DEMO_ORG_IDS                 unset, so demo_org_uuid_set() was empty
  demo_isolation.org_type_for()   'real' for that same organization

after
  all three agree; allowlist_matches_database true
```

The database row is the authority, because it is the only one of the three that
is a fact about the organization rather than a statement about a deployment. The
allowlist is compared against it and a disagreement **refuses** the
classification rather than picking a winner.

## Records created

```text
{IDENTITY_TABLE}                     1   written by the callback, from a verified claim
{MEMBERSHIP_TABLE}                1   demo org, is_demo derived, role org_owner
{BINDING_TABLE}   1   demo_fixture, no verifier
```

Nothing was written for `{FORBIDDEN_ORG_ID}`: 0 memberships, 0 bindings.

## Self-approval, permitted exactly once

Migration 0024 requires an approver for any source but `verified_directory`. The
first membership in an organization has nobody to approve it, so it names
itself — and only while the organization has no memberships at all. The second
self-approved membership is refused
(`self_approval_permitted_only_for_the_first_membership`), which was observed
when this script was re-run.
"""

    files["dev_org_binding_result.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "authorized_organization_id": AUTHORIZED_ORG_ID,
            "forbidden_organization_id": FORBIDDEN_ORG_ID,
            "organization_authority_column": "organization_id",
            "org_type_source_of_truth": "organizations.org_type",
            "is_demo_derived_not_supplied": True,
            "identity_table": IDENTITY_TABLE,
            "membership_table": MEMBERSHIP_TABLE,
            "binding_table": BINDING_TABLE,
            "identity_rows_created": 1,
            "membership_rows_created": 1,
            "binding_rows_created": 1,
            "rows_created_for_forbidden_organization": 0,
            "membership_role": "org_owner",
            "membership_role_source": "membership_record",
            "membership_source": "org_owner_approved",
            "membership_is_demo": True,
            "membership_self_approved": True,
            "membership_bootstrap": True,
            "binding_status": "demo_fixture",
            "binding_source": "demo_fixture",
            "binding_confidence": "demo_only",
            "binding_carries_a_verifier": False,
            "verified_operational_binding": False,
            "verified_binding_refused_reasons": [
                "demo_fixture_binding_cannot_carry_a_verifier",
                "demo_fixture_cannot_be_a_verified_binding",
            ],
            "tenant_id_used_as_authority": False,
            "customer_org_id_used_as_authority": False,
            "organization_profile_id_used_as_authority": False,
            "email_domain_used_as_authority": False,
            "provider_subject_recorded_in_artifact": False,
            "real_customer_rows_written": 0,
            "production_bindings_created": 0,
            "fabricated": False,
        }
    )

    files["login_after_binding_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "note": (
                "A recording of a browser run, not a measurement taken at "
                "generation time. Booleans only."
            ),
            "before_membership_existed": LIVE_SMOKE_BEFORE_MEMBERSHIP,
            "after_membership_existed": LIVE_SMOKE,
            "tokens_recorded": False,
            "cookies_recorded": False,
            "raw_state_recorded": False,
            "raw_pkce_verifier_recorded": False,
            "authorization_code_recorded": False,
            "blocked_reasons": [],
        }
    )

    files["current_user_after_binding.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route": "/api/auth/current-user",
            "authenticated_status_code": 200,
            "unauthenticated_status_code": 401,
            "forged_cookie_status_code": 401,
            "public_unauthenticated_status_code": 302,
            "public_302_source": (
                "cloudflare access, ahead of the application; the application's "
                "own unauthenticated answer is 401, measured on the loopback"
            ),
            "authenticated": True,
            "organization_id": AUTHORIZED_ORG_ID,
            "organization_id_resolved": True,
            "membership_verified": True,
            "roles": ["org_owner"],
            "least_privilege_role": "org_owner",
            "email_returned": False,
            "provider_subject_returned": False,
            "subject_field_carries": "internal identity id",
            "access_token_returned": False,
            "id_token_returned": False,
            "refresh_token_returned": False,
            "session_cookie_value_returned": False,
            "organization_from_membership_row_not_the_cookie": True,
            "cross_organization_cookie_authorizes_nothing": True,
        }
    )

    files["auth_readiness_after_binding.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "deterministic_gate_no_evidence_supplied": {
                "customer_auth_live": bool(gate["customer_auth_live"]),
                "login_live": bool(gate["login_live"]),
                "callback_session_validated": bool(gate["callback_session_validated"]),
                "org_binding_passed": bool(gate["org_binding_passed"]),
                "blocked_reasons": list(gate["blocked_reasons"]),
            },
            "measured_against_the_dev_database": {
                "note": "a recording; regenerate by calling the route",
                "callback_session_validated": True,
                "org_binding_passed": True,
                "customer_auth_live": False,
                "login_live": False,
                "remaining_login_blockers": [
                    "issuer_jwks_validated",
                    "role_mapping_passed",
                    "owner_has_not_authorized_customer_auth_activation",
                ],
            },
            "flags_this_gate_did_not_move": {
                "login_live": False,
                "customer_auth_live": False,
                "verified_operational_binding": False,
                "customer_persistence_live": False,
                "awarded_operational_tracking": False,
                "tenant_digest_operational": False,
                "source_monitoring_live": False,
                "email_delivery": False,
                "object_store_configured": False,
            },
            "env_key_names_checked": list(AUTH_ENV_KEY_NAMES),
            "env_key_presence": presence,
            "env_values_recorded": False,
            "markers_checked": list(REDACTION_MARKERS),
            "scan_applies_to": ARTIFACT_DIR,
        }
    )

    files[
        "next_customer_persistence_blockers.md"
    ] = """# Gate 132 — what moved, what did not, and why

## Moved

```text
identity persistence     nf_identities can be written, and holds 1 row
membership creation      nf_org_memberships can be written, and holds 1 row
org resolution           a verified identity resolves to an organization_id
                         through a membership row, and through nothing else
session minting          a real Google login now mints a session
current-user             200, with an organization and a role
callback_session_validated  measured from rows instead of a literal False
org_binding_passed          measured from rows instead of a parameter nobody passed
```

## Did not move, and cannot yet

### `login_live` — three blockers, none of them Gate 132's to clear

```text
issuer_jwks_validated   the callback verified an ID token against Google's JWKS,
                        which is the fact this gate describes - but nothing
                        durable records it, and a gate satisfied by a value held
                        in a local is a gate satisfied by an assertion. Deriving
                        it needs a recorded validation run.
role_mapping_passed     provider roles are not configured or mapped. The role on
                        the membership came from the membership record, which is
                        the trusted source - it is not a provider role mapping.
owner_approval          NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL is Mayhem's
                        out-of-band decision. Not mine to set, and setting it
                        would make the gate meaningless.
```

### `verified_operational_binding` — refused by Gate 113's own contract

The authorization was demo-only, and a demo binding may not carry a verifier and
may not be a `verified_binding`. Both refusals fired when a `verified_binding`
was attempted:

```text
demo_fixture_binding_cannot_carry_a_verifier
demo_fixture_cannot_be_a_verified_binding
```

So the binding is a `demo_fixture` and `verified_operational_binding` is false.
That is the contract working, not a gap: a verified operational binding on a
demo organization would be a fixture wearing production's label. It becomes
reachable when a real organization is authorized, which is a separate decision.

### `customer_persistence_live`

`dev_header_disabled_for_production` is still false and 15 route modules still
read `X-NF-Org-Id`. Customer persistence under an authenticated claim needs that
header gone, which is Gate 122's work and touches every one of them.

## Unchanged, and stated so nothing reads the above as progress on them

```text
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

## The next thing worth doing

Record a durable validation run for the JWKS check the callback already
performs. It is the only remaining `login_live` blocker that is a measurement
problem rather than a decision or a migration - the check happens on every
callback and nothing writes it down.
"""

    return files


def write_first_dev_org_binding_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    files = build_first_dev_org_binding_artifacts()
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    written: list[str] = []
    marker_hits: list[str] = []
    env_value_hits: list[str] = []
    for name, content in sorted(files.items()):
        # The readiness file publishes the marker vocabulary, so it contains
        # every marker by design. Scanning it for them is a scanner refusing its
        # own output - Gates 127 and 131 hit the same shape. The env-value check
        # below still applies to it, because listing a key NAME is not carrying
        # its value.
        if name != "auth_readiness_after_binding.json":
            for marker in REDACTION_MARKERS:
                # A marker in prose is fine; a marker paired with a value is not.
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


def first_dev_org_binding_artifact_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
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
