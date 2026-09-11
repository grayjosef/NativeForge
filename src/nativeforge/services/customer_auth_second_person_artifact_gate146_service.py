"""Gate 146E: the second-person event readiness, written down.

## These artifacts carry the path, not today's counts

A committed artifact that embedded the live invite counts would be wrong the
moment the event happens, and would churn on every regeneration in between. The
counts belong in the verifier's output, which is read at the moment somebody
asks. What is committed here is the part that does not move: the stages, who
owns each, what proves each, which shortcuts are refused and why, and what must
never be printed.

So `build_second_person_artifacts()` takes no database and no evidence. It is a
pure function of the module constants, which is what makes it deterministic.

## No example address appears anywhere in them

Every command is written with an `<address>` placeholder. That is not
squeamishness: the scan below refuses anything shaped like an address, and an
example one would trip it. Gate 145 spent a fix on exactly this class of
problem — an inventory of forbidden things tripping the guard against them — so
this module avoids needing the exemption rather than granting one.

## What is not in them

No address, provider subject, token, cookie, state, PKCE verifier, API key or
real customer data. Every file is scanned for those shapes before it is
returned, and the builder raises rather than writes if one appears.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.customer_auth_second_person_event_checklist_service import (
    DEMO_ORGANIZATION_ID,
    GOOGLE_TEST_USER_ENROLMENT,
    REFUSED_ORGANIZATION_ID,
    REFUSED_SHORTCUTS,
    STAGE_INVITE_ACCEPTED,
    STAGE_INVITE_ISSUED,
    STAGE_OWNERS,
    STAGE_SECOND_IDENTITY,
    STAGES,
)

SCHEMA_VERSION = "nf_customer_auth_second_person_artifacts_v1"

ARTIFACT_DIR = "artifacts/customer_auth_second_person_gate146"

SURVEY_FILE = "customer_auth_second_person_survey.json"
ISSUE_FILE = "invite_issue_readiness.json"
ACCEPT_FILE = "invite_accept_readiness.json"
BLOCKERS_FILE = "customer_auth_live_blockers.json"
CHECKLIST_FILE = "second_person_event_checklist.json"
NEXT_ACTION_FILE = "next_human_action.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    ISSUE_FILE,
    ACCEPT_FILE,
    BLOCKERS_FILE,
    CHECKLIST_FILE,
    NEXT_ACTION_FILE,
)

#: Shapes no artifact may contain. The provider subject is matched as a shape
#: rather than by field name, because the leak that matters is the value.
FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
    ("provider_subject", r"\b\d{18,}\b"),
)

#: What each stage's completion is proved by. Named so an operator can check a
#: claim rather than take one.
STAGE_PROOF: dict[str, str] = {
    STAGE_SECOND_IDENTITY: (
        "nf_identities gains a row for a subject the provider verified. "
        "Counted, never selected."
    ),
    STAGE_INVITE_ISSUED: (
        "nf_membership_invites gains a row for the demo organization, holding "
        "the domain half and two fingerprints and no address."
    ),
    STAGE_INVITE_ACCEPTED: (
        "the invite is accepted AND an active membership names that invite "
        "AND the member is the accepter. A join, not a coincidence."
    ),
}

#: Values that must remain false when this gate passes. A readiness gate that
#: moved any of them would not be a readiness gate.
STAYS_FALSE: tuple[str, ...] = (
    "customer_auth_live",
    "invite_binding_passed",
    "verified_operational_binding",
    "controlled_customer_pilot",
    "production_rollout",
)

#: Things that must never be printed, stored, or committed by this path.
NEVER_PRINTED: tuple[dict[str, str], ...] = (
    {
        "value": "the invited address",
        "where_it_lives": "nf_identities.email",
        "instead": "the domain half and a fingerprint, on the invite row",
    },
    {
        "value": "the provider subject",
        "where_it_lives": "nf_identities.subject",
        "instead": "a fingerprint, on the invite row",
    },
    {
        "value": "the session cookie",
        "where_it_lives": "the browser",
        "instead": "a boolean saying whether a session was issued",
    },
    {
        "value": "the OAuth state and PKCE verifier",
        "where_it_lives": "the redirect state store",
        "instead": "nothing; no readout needs them",
    },
)

#: The one identifier that is safe to print, and why.
SAFE_TO_PRINT = {
    "value": "the invite id",
    "why": (
        "the operator needs it for the accept command and it identifies no "
        "person; the issue script prints it on purpose"
    ),
}


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"forbidden shape {shape!r} in {name}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "question": "what is left before customer_auth_live can be true?",
        "answer": "one blocker, which is an event rather than a decision",
        "blocker": "invite_binding_passed",
        "blocker_is_a_conjunction_of": list(STAGES),
        "why_the_name_does_not_locate_it": (
            "an operator told invite_binding_passed is false looks for an "
            "invite to accept; the checklist reports which of the three "
            "stages is actually outstanding"
        ),
        "owner_activation_decision": "already approves customer_auth_live",
        "gates_passing": 16,
        "gates_total": 17,
        "organization": DEMO_ORGANIZATION_ID,
        "refused_organization": REFUSED_ORGANIZATION_ID,
        "stage_proof": dict(STAGE_PROOF),
        "never_printed": list(NEVER_PRINTED),
        "safe_to_print": dict(SAFE_TO_PRINT),
    }


def _issue_readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE_INVITE_ISSUED,
        "command": "./scripts/nativeforge_demo_invite_issue.py --email <address>",
        "who": STAGE_OWNERS[STAGE_INVITE_ISSUED]["who"],
        "safe_to_run": True,
        "safeguards": [
            "demo organization only; the real organization is refused by name",
            "production environment exits 2",
            "is_demo derived from organizations.org_type, not from a flag",
            "the issuer is read from the org's active org_owner row, never "
            "supplied, so an operator cannot forge who authorized a membership",
            "the address is read at runtime, never printed, never stored",
            "no email is sent; the table has no column for an address to send to",
        ],
        "writes": "one nf_membership_invites row",
        "records": [
            "invited_email_domain",
            "invited_email_fingerprint",
            "invited_subject_fingerprint",
        ],
        "does_not_record": ["the address", "the provider subject"],
        "prints": "the invite id, on purpose",
        "email_sent": False,
        "prerequisite": (
            "none technically; the runbook orders it after the second person "
            "has signed in so the accept step can follow immediately"
        ),
    }


def _accept_readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE_INVITE_ACCEPTED,
        "command": (
            "./scripts/nativeforge_demo_invite_accept.py "
            "--invite-id <from the issue step> --email <the same address>"
        ),
        "who": STAGE_OWNERS[STAGE_INVITE_ACCEPTED]["who"],
        "safe_to_run": True,
        "refuses_when_the_person_has_not_signed_in": True,
        "refusal": "no_identity_has_signed_in_with_that_address",
        "refusal_is_the_honest_answer": True,
        "has_a_bypass_flag": False,
        "safeguards": [
            "the accepter is resolved from nf_identities and must then match "
            "the invite's own fingerprint, so a different address refuses "
            "rather than redirecting the membership",
            "the owner cannot accept their own invite",
            "both writes are one transaction; a membership failure rolls the "
            "acceptance back, because an invite marked accepted with nobody "
            "behind it reads as consumed and its id cannot be reused",
        ],
        "writes": ["the acceptance on the invite row", "one membership row"],
        "clears": "invite_binding_passed",
    }


def _blockers() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "customer_auth_live": False,
        "blocker": "invite_binding_passed",
        "blocker_kind": "an event, not a decision",
        "stages": [
            {
                "stage": name,
                "proved_by": STAGE_PROOF[name],
                **{k: v for k, v in STAGE_OWNERS[name].items()},
            }
            for name in STAGES
        ],
        "not_observable_from_here": [dict(GOOGLE_TEST_USER_ENROLMENT)],
        "refused_shortcuts": [dict(s) for s in REFUSED_SHORTCUTS],
        "stays_false_after_this_gate": list(STAYS_FALSE),
        "readiness_is_not_the_event": (
            "readiness_passed says the path is correct and runnable; "
            "customer_auth_live says somebody walked it"
        ),
    }


def _checklist() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "organization": DEMO_ORGANIZATION_ID,
        "stage_order": list(STAGES),
        "stages": [
            {
                "stage": name,
                "position": index + 1,
                "proved_by": STAGE_PROOF[name],
                **{k: v for k, v in STAGE_OWNERS[name].items()},
            }
            for index, name in enumerate(STAGES)
        ],
        "unobservable_prerequisite": dict(GOOGLE_TEST_USER_ENROLMENT),
        "second_identity_required": True,
        "second_identity_must_be_distinct_from_owner": True,
        "verifier": "scripts/verify_nativeforge_customer_auth_second_person_event.sh",
        "verifier_passes_on_readiness_not_on_the_event": True,
        "never_printed": list(NEVER_PRINTED),
        "safe_to_print": dict(SAFE_TO_PRINT),
        "issued_by_this_gate": False,
        "accepted_by_this_gate": False,
        "activated_by_this_gate": False,
    }


def _next_action_markdown() -> str:
    lines = [
        "# Gate 146 — the next human action",
        "",
        "`customer_auth_live` is false for one reason, and it is not a decision",
        "anybody has withheld. It is an event that has not happened.",
        "",
        "```text",
        "blocker                     invite_binding_passed",
        "owner_activation_decision   already approves customer_auth_live",
        "```",
        "",
        "## The steps, in order",
        "",
        "```text",
        "0  enrol the second Google account as an OAuth test user",
        "     console.cloud.google.com -> APIs & Services",
        "     -> OAuth consent screen -> Audience -> ADD USERS -> SAVE",
        "     not a command, and not observable from this repository",
        "",
        "1  that account signs in once, in a clean browser profile",
        "     expect NO session. An identity row is written; the membership",
        "     does not exist yet, so no cookie is issued. That is correct.",
        "",
        "2  ./scripts/nativeforge_demo_invite_issue.py --email <address>",
        "     copy the invite id it prints",
        "",
        "3  ./scripts/nativeforge_demo_invite_accept.py \\",
        "       --invite-id <from step 2> --email <the same address>",
        "",
        "4  that account signs in again; now a session is issued",
        "",
        "5  ./scripts/verify_nativeforge_customer_auth_second_person_event.sh",
        "```",
        "",
        "Steps 2 and 3 are the operator's. Steps 0, 1 and 4 need the second",
        "person, and step 0 needs the Google console.",
        "",
        "## Why none of this can be done from here",
        "",
        "```text",
    ]
    for shortcut in REFUSED_SHORTCUTS:
        lines.append(f"{shortcut['shortcut']}")
        lines.append(f"    {shortcut['refused_because']}")
    lines += [
        "```",
        "",
        "## What must not be printed",
        "",
        "```text",
    ]
    for item in NEVER_PRINTED:
        lines.append(f"{item['value']:34s} lives in {item['where_it_lives']}")
        lines.append(f"{'':34s} report instead: {item['instead']}")
    lines += [
        "```",
        "",
        f"Safe to print: {SAFE_TO_PRINT['value']} — {SAFE_TO_PRINT['why']}.",
        "",
        "## What stays false when this gate passes",
        "",
        "```text",
    ]
    lines += [f"{name}   false" for name in STAYS_FALSE]
    lines += [
        "```",
        "",
        "This gate proves the path. It does not walk it.",
        "",
    ]
    return "\n".join(lines)


def build_second_person_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        ISSUE_FILE: _json(_issue_readiness()),
        ACCEPT_FILE: _json(_accept_readiness()),
        BLOCKERS_FILE: _json(_blockers()),
        CHECKLIST_FILE: _json(_checklist()),
        NEXT_ACTION_FILE: _next_action_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_second_person_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_second_person_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def second_person_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
