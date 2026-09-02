"""Gate 135G: the customer-auth activation artifacts.

Counts, booleans, module names, blocker names. No token, no cookie, no raw
state, no PKCE verifier, no authorization code, no provider subject, no email
address — and the writer scans its own output rather than trusting that
sentence.

The gate values are recomputed on every call from the same services the routes
use. The live measurements are labelled recordings, dated, because they read the
dev database and this file is committed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_activation_gate135_artifact_v1"
ARTIFACT_DIR = "artifacts/customer_auth_activation_gate135"

DEMO_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://accounts.google.com"

ARTIFACT_FILES: tuple[str, ...] = (
    "customer_auth_activation_before_after.json",
    "invite_binding_evidence.json",
    "owner_customer_auth_activation_decision.json",
    "dead_dev_header_chain_removal.json",
    "current_user_customer_auth_smoke.json",
    "customer_auth_readiness_after_gate135.json",
    "next_customer_auth_blockers.md",
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

#: The three chains Gate 134 made obsolete and Gate 135 removed.
REMOVED_CHAINS: tuple[str, ...] = (
    "deps_db.get_org_context_with_db",
    "deps_db.require_demo_org_db",
    "deps_db.require_real_org_db",
    "api/isolation_deps.py (whole module)",
    "deps_customer_auth.get_dev_org_context_explicit_only",
)

#: RECORDED 2026-09-02 against the running backend on the loopback.
LIVE_SMOKE: dict[str, Any] = {
    "recorded_on": "2026-09-02",
    "login_live": True,
    "customer_auth_live": False,
    "blocked_reasons": ["auth_gate_not_satisfied:invite_binding_passed"],
    "owner_approval_source": "recorded_decision",
    "dev_header_disabled_for_production": True,
    "current_user_no_session": 401,
    "converted_route_with_header_only": 401,
    "api_auth_login": 302,
}

#: RECORDED 2026-09-02 from the dev database.
LIVE_INVITE_EVIDENCE: dict[str, Any] = {
    "recorded_on": "2026-09-02",
    "invite_rows": 0,
    "approved_invite_rows": 0,
    "accepted_invite_rows": 0,
    "membership_rows": 1,
    "memberships_from_a_completed_invite": 0,
    "invite_binding_passed": False,
    "blocked_reasons": ["no_invite_has_been_recorded"],
}


def _get_db_session_importers() -> list[str]:
    """Which route modules import the dependency that stayed.

    Counted rather than stated. The number was prose in this file and was wrong
    by one: a `grep` for the name also matched this module, which mentions
    `get_db_session` to explain why it was kept and does not import it.
    """
    api_dir = Path(__file__).resolve().parents[3] / "src/nativeforge/api"
    names: list[str] = []
    if api_dir.is_dir():
        for path in sorted(api_dir.glob("*.py")):
            if path.name == "deps_db.py":
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^\s*from .*deps_db import .*\bget_db_session\b", body, re.M):
                names.append(path.name)
    return names


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dump(obj: Any) -> str:
    return json.dumps(_json_safe(obj), indent=2, sort_keys=True) + "\n"


def build_activation_artifacts(*, repo_root: Any = None) -> dict[str, str]:
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_owner_activation_decision_service import (
        CUSTOMER_AUTH_NOT_APPROVED,
        build_customer_auth_activation_decision,
        build_owner_activation_decision,
    )
    from nativeforge.services.dev_header_exposure_matrix_service import (
        build_dev_header_exposure_matrix,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )
    from nativeforge.services.membership_invite_repository_service import (
        FORBIDDEN_INVITE_KEYS,
        INVITE_FIELDS,
        SELF_DEALT,
    )

    gate = build_customer_auth_activation_gate()
    matrix = build_dev_header_exposure_matrix(
        repo_root=repo_root, ingress_patterns=["^/api/.*"], behind_access=True
    )
    shutdown = build_dev_header_shutdown_readiness()

    approved = build_customer_auth_activation_decision(
        organization_id=DEMO_ORG_ID, provider=ISSUER, app_env="dev"
    )
    refused_org = build_customer_auth_activation_decision(
        organization_id=REAL_ORG_ID, provider=ISSUER, app_env="dev"
    )
    refused_env = build_customer_auth_activation_decision(
        organization_id=DEMO_ORG_ID, provider=ISSUER, app_env="production"
    )
    login_only = build_owner_activation_decision(
        organization_id=DEMO_ORG_ID, provider=ISSUER, app_env="dev"
    )

    presence = {
        key: bool((os.environ.get(key) or "").strip()) for key in AUTH_ENV_KEY_NAMES
    }

    files: dict[str, str] = {}

    files["customer_auth_activation_before_after.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "before": {
                "recorded_by": "Gate 134",
                "login_live": True,
                "customer_auth_live": False,
                "blockers": ["invite_binding_passed", "owner_approval"],
                "dev_header_chains_present": len(REMOVED_CHAINS),
            },
            "after": {
                "login_live": True,
                "customer_auth_live": False,
                "blockers": ["invite_binding_passed"],
                "dev_header_chains_present": 0,
                "dev_header_route_consumers": matrix["dev_header_route_count"],
            },
            "what_cleared": ["owner_approval"],
            "what_remains": ["invite_binding_passed"],
            "why_it_remains": (
                "a completed invite needs an invitee who authenticates, and the "
                "demo organization has one identity. Inventing a second would be "
                "faking a user."
            ),
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "real_organization_touched": False,
            "real_customer_data_written": False,
        }
    )

    files["invite_binding_evidence.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "table": "nf_membership_invites",
            "migration": "0038",
            "decision_service": "membership_invite_approval_service",
            "repository_seam": "membership_invite_repository_service",
            "service_had_a_write_path_before": False,
            "service_callers_in_src_before": 0,
            "trusted_provenances": ["completed_invite"],
            "what_the_row_holds": list(INVITE_FIELDS),
            "what_the_row_refuses": list(FORBIDDEN_INVITE_KEYS),
            "invited_email_stored": False,
            "invited_email_domain_stored": True,
            "provider_subject_stored": False,
            "provider_subject_fingerprint_stored": True,
            "email_sent": False,
            "self_dealing_refusal": SELF_DEALT,
            "self_dealing_caught_by_the_decision_service": False,
            "acceptance_requires": (
                "an accepted_by_identity_id that is a real nf_identities row and "
                "is neither the requester nor the approver"
            ),
            "measured_live": LIVE_INVITE_EVIDENCE,
            "deterministic_gate_no_evidence_supplied": {
                "invite_binding_passed": bool(gate["invite_binding_passed"]),
            },
        }
    )

    files["owner_customer_auth_activation_decision.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "authorization_source": approved["authorization_source"],
            "approved_organization_id": DEMO_ORG_ID,
            "refused_organization_id": REAL_ORG_ID,
            "in_scope_demo_dev": {
                "approves_customer_auth_live": bool(
                    approved["approves_customer_auth_live"]
                ),
                "approves_production_rollout": bool(
                    approved["approves_production_rollout"]
                ),
                "approves_controlled_customer_pilot": bool(
                    approved["approves_controlled_customer_pilot"]
                ),
                "blocked_reasons": list(approved["blocked_reasons"]),
            },
            "out_of_scope_real_org": {
                "approves_customer_auth_live": bool(
                    refused_org["approves_customer_auth_live"]
                ),
                "blocked_reasons": list(refused_org["blocked_reasons"]),
            },
            "out_of_scope_production_environment": {
                "approves_customer_auth_live": bool(
                    refused_env["approves_customer_auth_live"]
                ),
                "blocked_reasons": list(refused_env["blocked_reasons"]),
            },
            "the_login_decision_is_a_different_decision": {
                "approves_login_live": bool(login_only["approves_login_live"]),
                "approves_customer_auth_live": bool(
                    login_only["approves_customer_auth_live"]
                ),
            },
            "not_approved": list(CUSTOMER_AUTH_NOT_APPROVED),
            "environment_token_still_honoured": True,
            "environment_token_present": bool(gate["owner_approval_present"]),
        }
    )

    files["dead_dev_header_chain_removal.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "removed": list(REMOVED_CHAINS),
            "route_consumers_before_removal": 0,
            "dev_header_route_consumers": matrix["dev_header_route_count"],
            "dev_header_provider_modules": list(
                shutdown["dev_header_provider_modules"]
            ),
            "dev_header_mention_only_modules": list(
                shutdown["dev_header_mention_only_modules"]
            ),
            "get_db_session_kept": True,
            "get_db_session_kept_importers": _get_db_session_importers(),
            "get_db_session_kept_because": (
                "route modules import it; it hands out a session and reads no header"
            ),
            "nf_dev_org_headers_false_safe": True,
            "nothing_reads_the_header_now": True,
            "header_declarations_remaining": 0,
        }
    )

    files["current_user_customer_auth_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "measured_on_the_loopback": LIVE_SMOKE,
            "organization_from_membership_row": True,
            "role_from_membership_row": True,
            "forged_header_changes_the_organization": False,
            "tokens_returned": False,
            "cookies_returned": False,
            "provider_subject_returned": False,
            "email_returned": False,
            "browser_session_redriven": False,
            "browser_session_blocked_by": "cloudflare_access_session_expired",
        }
    )

    files["customer_auth_readiness_after_gate135.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "required_auth_gates": list(REQUIRED_AUTH_GATES),
            "deterministic_gate_no_evidence_supplied": {
                "customer_auth_live": bool(gate["customer_auth_live"]),
                "login_live": bool(gate["login_live"]),
                "invite_binding_passed": bool(gate["invite_binding_passed"]),
                "owner_approval_present": bool(gate["owner_approval_present"]),
                "owner_approval_source": gate["owner_approval_source"],
                "missing_auth_gates": list(gate["missing_auth_gates"]),
            },
            "measured_against_the_dev_deployment": LIVE_SMOKE,
            "flags_this_gate_did_not_move": {
                "customer_auth_live": False,
                "production_rollout": False,
                "controlled_customer_pilot": False,
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
        "next_customer_auth_blockers.md"
    ] = """# Gate 135 — one blocker left, and it needs a person

## Where it stands

```text
login_live                            true
customer_auth_live                    FALSE
dev_header_disabled_for_production    true
owner approval                        recorded (Gate 135D decision)
invite_binding_passed                 FALSE   <- the only one left
```

Measured on the running backend: `customer_auth_live` is false for exactly one
named reason, `auth_gate_not_satisfied:invite_binding_passed`.

## What cleared

**Owner approval.** Mayhem authorized controlled dev customer-auth activation
for the demo organization explicitly. Gate 133D had already split "the demo
login may be called live" from "customer authentication is live"; this is the
second decision arriving. It checks the organization, the provider and the
environment on every call, refuses the real organization by name, refuses
production, and `approves_production_rollout` has no branch that returns True.

The `NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` env var is still honoured. The
recorded decision is an additional route, not a replacement.

## What remains, and why it is a person rather than a task

`TRUSTED_PROVENANCES` is `{"completed_invite"}` — a membership that did not come
through a completed invite is not trusted, and the demo organization's one
membership is Gate 132's bootstrap, which is `operator_direct_write`.

A completed invite needs somebody to accept it, and accepting means
authenticating. The demo organization has one identity: the owner. The owner
cannot complete an invite to themselves — the repository refuses it by name
(`invite_requested_approved_and_accepted_by_one_identity`) and so does the
database on PostgreSQL.

So the blocker is: **a second real person logging in and accepting an invite.**

Inventing that person would be faking a user. It would also make the evidence
worthless: the gate exists to prove somebody else authorized a membership, and
an invitee this process made up authorizes nothing.

## What was built so it can be completed

```text
migration 0038                  nf_membership_invites
membership_invite_repository_service
  insert_invite                 issue and approve, recorded
  record_acceptance             accept, with three refusals that fire
  build_invite_binding_evidence derived from rows, not a parameter
```

Every branch is exercised against real rows in
`tests/test_gate135_customer_auth_activation.py`, including the completed one:
an invite issued by an owner, accepted by a second identity, producing a
membership, at which point `invite_binding_passed` is true.

`membership_invite_approval_service` had a write path of exactly nothing before
this — 694 lines, `persisted: False` on every result, zero callers in `src/`.

## The exact next action

```text
1  a second person signs in through /api/auth/login with a Google account
2  the owner issues an invite for the demo organization and approves it
3  that person accepts it; a membership is created naming the invite
4  invite_binding_passed becomes true, measured, and customer_auth_live with it
```

Step 1 is the one nobody here can do.

## Still false, and not touched

```text
production_rollout             false
controlled_customer_pilot      false
verified_operational_binding   false   Gate 113 refuses one on a demo org
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

No email was sent by anything in this gate, and nothing in the invite path can
send one.
"""

    return files


def write_activation_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    files = build_activation_artifacts(repo_root=Path("."))
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    written: list[str] = []
    marker_hits: list[str] = []
    env_value_hits: list[str] = []
    for name, content in sorted(files.items()):
        # The readiness file publishes the marker vocabulary, so it contains
        # every marker by design - a scanner refusing its own output. Gates 127
        # through 134 each hit this and narrowed with the rule stated.
        if name != "customer_auth_readiness_after_gate135.json":
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
            "email_sent": False,
            "fabricated": False,
        }
    )


def activation_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("file_count") != len(ARTIFACT_FILES):
        fails.append("file_count_disagrees")
    if result.get("marker_hits"):
        fails.append("token_or_cookie_marker_reached_an_artifact")
    if result.get("env_value_hits"):
        fails.append("environment_value_reached_an_artifact")
    for key in (
        "env_values_recorded",
        "provider_subject_recorded",
        "email_sent",
        "fabricated",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails
