"""Gate 136F: what was built, what it refuses, and what is still missing.

Deterministic. Nothing here reads the clock, the network, or the dev database -
the counts that belong to a moment live in the verifier's output, and an
artifact that changed every time it was written would fail its own regeneration
test and stop being evidence.

No secrets, no tokens, no cookies, no state, no PKCE verifier, no provider
subject, no email addresses. A scan asserts it rather than the docstring.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.customer_auth_owner_activation_decision_service import (
    APPROVED_ENVIRONMENTS,
    APPROVED_ORGANIZATION_ID,
    REFUSED_ORGANIZATION_ID,
)
from nativeforge.services.membership_invite_activation_service import (
    ALREADY_A_MEMBER,
    IDENTITY_AMBIGUOUS,
    IDENTITY_NOT_FOUND,
    MEMBERSHIP_SOURCE,
    NOT_DEMO,
    PROVENANCE,
    SEAT_CAP_REACHED,
)
from nativeforge.services.membership_invite_repository_service import (
    ACCEPTER_NOT_INVITED,
    ALREADY_ACCEPTED,
    FORBIDDEN_INVITE_KEYS,
    INVITE_EXPIRED,
    SELF_DEALT,
    TRUSTED_PROVENANCES,
)

SCHEMA_VERSION = "nf_invite_activation_gate136_artifact_v1"

ARTIFACT_DIR = "artifacts/invite_activation_gate136"

ARTIFACT_FILES: tuple[str, ...] = (
    "invite_activation_readiness.json",
    "operator_invite_command_status.json",
    "invite_acceptance_path_status.json",
    "customer_auth_live_verifier_status.json",
    "second_account_execution_steps.md",
    "next_blocker_if_not_live.md",
)

ISSUE_SCRIPT = "scripts/nativeforge_demo_invite_issue.py"
ACCEPT_SCRIPT = "scripts/nativeforge_demo_invite_accept.py"
VERIFIER_SCRIPT = "scripts/verify_nativeforge_customer_auth_live.sh"
EXECUTION_GUIDE = "docs/operations/717_GATE136_SECOND_ACCOUNT_INVITE_EXECUTION.md"

PUBLIC_LOGIN = "https://nf-dev.mayhem-nc.dev/api/auth/login"

#: Field names that must never appear here carrying a VALUE.
#:
#: The first scan looked for these as substrings and fired immediately - on
#: `FORBIDDEN_INVITE_KEYS`, which lists `id_token` and `access_token` *as the
#: things the invite table refuses to store*. Naming a refusal is the opposite
#: of leaking it, and a scan that cannot tell the difference reports the
#: safeguard as the breach.
#:
#: Eleventh substring-for-meaning defect in this campaign, and the first in
#: code written to catch them. So: a key with something after it, not a word.
CREDENTIAL_FIELDS: tuple[str, ...] = (
    "id_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "code_verifier",
    "pkce_verifier",
    "session_cookie_value",
    "provider_subject",
)

#: Values that are credential-shaped whatever surrounds them. No exception for
#: these: there is no honest reason for one to appear in a status file.
FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "@gmail.com",
    "eyJ",
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def build_activation_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    files: dict[str, str] = {}

    files["invite_activation_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "136",
            "what_gate_135_left": {
                "customer_auth_live": False,
                "blockers": ["invite_binding_passed"],
                "why": "a completed invite needs a second real authenticated identity",
            },
            "what_gate_136_built": [
                "migration 0039: invited_email_fingerprint, memberships.invite_id",
                "record_acceptance: expiry, re-acceptance and identity-match refusals",
                "insert_membership: invited_by and invite_id, both previously None",
                "membership_invite_activation_service: the accept path",
                ISSUE_SCRIPT,
                ACCEPT_SCRIPT,
                VERIFIER_SCRIPT,
                EXECUTION_GUIDE,
            ],
            "executable_now": True,
            "remaining_human_step": (
                "a second Google account, on the OAuth test-user list, signs in"
            ),
            "second_account_must_be_an_oauth_test_user": True,
            "oauth_app_publishing_status": "external_testing",
            # Still false, and nothing here changes any of them.
            "customer_auth_live": False,
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "verified_operational_binding": False,
            "real_organization_touched": False,
            "real_customer_data_written": False,
            "fake_users_created": 0,
            "fake_sessions_created": 0,
            "fake_invite_acceptances": 0,
            "invites_written_to_the_dev_database": 0,
            "email_sent": False,
            "object_store_contacted": False,
            "live_grant_sources_called": False,
            "collectors_activated": False,
        }
    )

    files["operator_invite_command_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "command": ISSUE_SCRIPT,
            "argument": "--email <the invited person's address>",
            "address_printed": False,
            "address_stored": False,
            "address_written_to_an_artifact": False,
            "what_reaches_the_database": [
                "invited_email_domain",
                "invited_email_fingerprint",
            ],
            "what_the_row_refuses": list(FORBIDDEN_INVITE_KEYS),
            "issuer_is_read_not_supplied": (
                "the organization's active org_owner membership row"
            ),
            "organization_scope": {
                "approved": APPROVED_ORGANIZATION_ID,
                "refused_by_name": REFUSED_ORGANIZATION_ID,
                "environments": sorted(APPROVED_ENVIRONMENTS),
            },
            "refusals": [
                "organization_is_the_explicitly_refused_real_org",
                "organization_outside_the_approved_scope",
                "environment_outside_the_approved_scope",
                "organization_has_no_active_owner_to_invite_by",
            ],
            "issues_and_approves_in_one_write": True,
            "issues_and_approves_in_one_write_because": (
                "an owner inviting somebody into their own organization is both, "
                "which is why the self-dealing refusal exists"
            ),
            "email_sent": False,
            "email_can_be_sent": False,
        }
    )

    files["invite_acceptance_path_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "command": ACCEPT_SCRIPT,
            "service": "membership_invite_activation_service",
            "shape": "operator script",
            "shape_chosen_because": (
                "the callback issues a session cookie only when the identity "
                "already resolves to an organization through a membership row, so "
                "an invited person cannot hold a session and an authenticated "
                "accept route has nobody to authenticate"
            ),
            "api_route_rejected": True,
            "unauthenticated_route_rejected_because": (
                "it would have to trust an invite id in a URL, an email in a body, "
                "or a header - the authority Gates 111 through 135 removed"
            ),
            "operator_can_choose_the_accepter": False,
            "operator_cannot_choose_because": (
                "the identity is resolved from nf_identities by address and the "
                "acceptance then requires it to match the invite's own fingerprint"
            ),
            "second_identity_must_have_authenticated": True,
            "one_transaction": True,
            "one_transaction_because": (
                "an invite marked accepted with no membership behind it reads as "
                "consumed, and its id cannot be reused"
            ),
            "provenance_written": PROVENANCE,
            "membership_source_written": MEMBERSHIP_SOURCE,
            "trusted_provenances": sorted(TRUSTED_PROVENANCES),
            "membership_names_its_invite": True,
            "refusals": sorted(
                {
                    IDENTITY_NOT_FOUND,
                    IDENTITY_AMBIGUOUS,
                    ACCEPTER_NOT_INVITED,
                    ALREADY_ACCEPTED,
                    INVITE_EXPIRED,
                    SELF_DEALT,
                    NOT_DEMO,
                    SEAT_CAP_REACHED,
                    ALREADY_A_MEMBER,
                    "accepting_identity_does_not_exist",
                    "invite_not_found",
                    "invite_revoked",
                }
            ),
            "refusals_added_by_gate_136": sorted(
                {ACCEPTER_NOT_INVITED, ALREADY_ACCEPTED, INVITE_EXPIRED}
            ),
            "no_override_bypasses_the_identity_match": True,
            "email_sent": False,
        }
    )

    files["customer_auth_live_verifier_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "command": VERIFIER_SCRIPT,
            "result_pass_only_when": "customer_auth_live is true",
            "otherwise": "RESULT=BLOCKED with the exact blocker named",
            "checks": [
                "backend_running",
                "session_route_answered",
                "measurement_available",
                "login_live",
                "dev_header_consumers_zero",
                "dev_header_provider_modules",
                "nf_dev_org_headers_false_safe",
                "current_user_refuses_unauthenticated",
                "invite_binding_passed",
                "owner_activation_decision",
            ],
            "counts_reported": [
                "invite_rows",
                "approved_invite_rows",
                "accepted_invite_rows",
                "membership_rows",
                "memberships_from_a_completed_invite",
                "memberships_matching_an_accepter_by_identity_only",
            ],
            "reads_the_same_services_the_gate_reads": True,
            "refuses_to_agree_when_the_gate_and_the_rows_disagree": True,
            "result_pass_is_reachable": True,
            "result_pass_proved_in": (
                "tests/test_gate136_invite_activation_readiness.py"
                "::test_the_verifier_can_report_pass"
            ),
            "prints_secrets": False,
            "prints_tokens": False,
            "prints_cookies": False,
            "prints_state": False,
            "prints_pkce_verifier": False,
            "prints_provider_subject": False,
            "prints_email_addresses": False,
        }
    )

    files["second_account_execution_steps.md"] = _steps()
    files["next_blocker_if_not_live.md"] = _next_blocker()

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            # A key with a value after it. `"id_token"` inside a list of keys
            # the table refuses is the safeguard being documented.
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")
            if re.search(rf"\b{re.escape(field)}\s*=\s*\S", lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def _steps() -> str:
    return f"""# Gate 136 — the second account, in order

Full version with the console screens in `{EXECUTION_GUIDE}`.

## Before anything

The Google OAuth app is **External / Testing** with one test user. Google
refuses an account that is not on that list *before NativeForge sees the
request*, so this is first and nothing in the repository can do it:

```text
Google Cloud console -> APIs & Services -> OAuth consent screen
  -> Audience / Test users -> ADD USERS -> the second account
```

## Then, four steps

```text
1  the second account signs in once
     {PUBLIC_LOGIN}
   an nf_identities row is written. NO session yet - the callback needs a
   membership before it sets a cookie, and that is what step 3 creates.
   This is correct and is not an error.

2  the owner issues the invite
     ./{ISSUE_SCRIPT} --email <that account's address>
   prints an invite id. The address is not printed and is not stored.

3  accept it for them
     ./{ACCEPT_SCRIPT} \\
         --invite-id <the id from step 2> --email <the same address>
   the invite is accepted and a membership is written, naming the invite,
   in one transaction.

4  the second account signs in again
     {PUBLIC_LOGIN}
   now there is a membership, so now there is a session.
```

## Then verify

```text
./{VERIFIER_SCRIPT}
```

```text
RESULT=PASS      customer_auth_live=true. Done.
RESULT=BLOCKED   the blocker is named on the next line.
```

## What not to do

```text
do not accept an invite for somebody who has not signed in
     it refuses: {IDENTITY_NOT_FOUND}
     there is no flag that overrides this, deliberately

do not run step 3 with a different address to redirect the membership
     it refuses: {ACCEPTER_NOT_INVITED}

do not issue an invite against {REFUSED_ORGANIZATION_ID}
     it refuses by name and exits 2

do not add rows by hand to make the verifier pass
     a membership that does not name an accepted invite does not count, and
     the verifier reports the near-miss separately
```
"""


def _next_blocker() -> str:
    return f"""# Gate 136 — the blocker, if the verifier still says BLOCKED

## `invite_binding_passed`

Which of the counts is zero says which step has not happened:

```text
invite_rows                          0   step 2 has not run
accepted_invite_rows                 0   step 3 has not run, or it refused
memberships_from_a_completed_invite  0   step 3 refused after accepting,
                                         which cannot persist - it rolls back
```

And one that is not zero:

```text
memberships_matching_an_accepter_by_identity_only  >0
```

means somebody holds a membership *and* accepted an invite, and the membership
does not name it. That is the exact state migration 0039 exists to stop passing
as evidence. It is reported rather than counted, so the near-miss is visible.

## `owner_activation_decision`

Blocked means the recorded decision does not cover this call. It is checked per
call against the organization, the provider and the environment, so:

```text
organization_outside_the_approved_scope   not {APPROVED_ORGANIZATION_ID}
provider_outside_the_approved_scope       OIDC_ISSUER is not Google
environment_outside_the_approved_scope    NF_APP_ENV is not one of
                                          {sorted(APPROVED_ENVIRONMENTS)}
decision_revoked_by_environment           the revocation variable is set
```

## `login_live`

If this is blocked, Gate 133's work has regressed and the invite is not the
problem. Run `./scripts/verify_nativeforge_demo_live_stack.sh` first.

## `gate_says_live_while_measurements_say:...`

The gate claims `customer_auth_live` and the rows do not agree. Worse news than
a blocker: one of the two is wrong. The verifier will not pick which, and this
is the one output that should stop everything.

## What is NOT the blocker

```text
production rollout            not authorized, and not what this gate is
controlled customer pilot     not authorized, and not what this gate is
verified_operational_binding  false by Gate 113's contract on a demo org,
                              and not in REQUIRED_AUTH_GATES
email delivery                nothing can send one; the invite table has
                              no column for an address to send to
```
"""


def write_activation_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_activation_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def activation_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")

    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")

    return fails
