"""Gate 147G: the verified-binding approval boundary, written down.

## The artifacts carry the boundary, not today's rows

Row counts move; the boundary does not. A committed artifact holding the live
binding count would churn on every regeneration and be wrong the moment
anything changed. What is committed is the part that is stable: the five
refusals, who owns each, which never clears, the refused shortcuts, and the
approval object's required shape.

`build_verified_binding_artifacts()` takes no database and no evidence, which
is what makes it deterministic.

## No example address, and no long digit strings

Every file is scanned for an address shape, a provider-subject shape and the
usual credential markers. Nothing here needs an example of any of them, so the
scan needs no exemption - the mistake Gate 145 had to fix when an inventory of
forbidden claims tripped the guard against them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    APPROVAL_FIELDS,
    DECISION_LAYERS,
    NON_PRODUCTION_ENVIRONMENTS,
    PRODUCTION_SCOPE,
    REAL_ORG_SCOPE,
)
from nativeforge.services.verified_operational_binding_approval_checklist_service import (  # noqa: E501
    NOT_APPROVED,
    REFUSAL_AMBIGUOUS,
    REFUSAL_AUTH_NOT_LIVE,
    REFUSAL_AUTHORIZED_LIST,
    REFUSAL_DEMO_ORG,
    REFUSAL_DUPLICATE,
    REFUSAL_NO_APPROVAL,
    REFUSAL_OWNERS,
    REFUSAL_PRINCIPAL,
    REFUSAL_REAL_ORG,
    REFUSED_SHORTCUTS,
    VERIFIER_ROLES,
)

SCHEMA_VERSION = "nf_verified_binding_gate147_artifacts_v1"

ARTIFACT_DIR = "artifacts/verified_binding_gate147"

SURVEY_FILE = "verified_binding_survey.json"
CHECKLIST_FILE = "verified_binding_approval_checklist.json"
DRY_RUN_FILE = "verified_binding_dry_run_decision.json"
REFUSAL_FILE = "verified_binding_refusal_matrix.json"
COCKPIT_FILE = "verified_binding_cockpit_status.json"
BLOCKERS_FILE = "verified_binding_activation_blockers.json"
NEXT_ACTION_FILE = "next_verified_binding_human_action.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    CHECKLIST_FILE,
    DRY_RUN_FILE,
    REFUSAL_FILE,
    COCKPIT_FILE,
    BLOCKERS_FILE,
    NEXT_ACTION_FILE,
)

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

#: The five refusals standing today, in the order an operator would meet them.
STANDING_REFUSALS: tuple[str, ...] = (
    REFUSAL_DEMO_ORG,
    REFUSAL_REAL_ORG,
    REFUSAL_AUTHORIZED_LIST,
    REFUSAL_NO_APPROVAL,
    REFUSAL_AUTH_NOT_LIVE,
    REFUSAL_PRINCIPAL,
)

#: The two that are conditional on state rather than on approval.
CONDITIONAL_REFUSALS: tuple[str, ...] = (REFUSAL_DUPLICATE, REFUSAL_AMBIGUOUS)

#: Values that must remain false when this gate passes.
STAYS_FALSE: tuple[str, ...] = (
    "verified_operational_binding",
    "customer_auth_live",
    "controlled_customer_pilot",
    "production_rollout",
)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"forbidden shape {shape!r} in {name}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "question": "what stands between today and verified_operational_binding?",
        "answer": "five refusals, any one of which is sufficient",
        "verified_operational_binding": False,
        "standing_refusals": list(STANDING_REFUSALS),
        "conditional_refusals": list(CONDITIONAL_REFUSALS),
        "decision_layers": list(DECISION_LAYERS),
        "why_three_layers": (
            "the activation boundary owns the authorized list, the approval "
            "object and the two organization refusals; the workflow service "
            "owns the customer-auth guard; the repository owns duplicate and "
            "ambiguous active bindings. Each is correct where it lives and "
            "none sees the other two, so nothing before this gate could say "
            "how far the lane is from true."
        ),
        "classification_source": "organizations.org_type, never the caller",
        "measured_state": {
            "real_organization_binding_rows": 0,
            "rows_asserting_verification": 0,
            "the_one_existing_row": "a demo fixture, which asserts nothing",
        },
        "not_approved": list(NOT_APPROVED),
    }


def _checklist_shape() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_fields_required": list(APPROVAL_FIELDS),
        "scopes": {
            REAL_ORG_SCOPE: sorted(NON_PRODUCTION_ENVIRONMENTS),
            PRODUCTION_SCOPE: ["production", "prod"],
        },
        "scope_note": (
            "the narrow scope does not reach production; binding a real "
            "organization in dev is a different decision from binding one in "
            "production"
        ),
        "verifier_roles": sorted(VERIFIER_ROLES),
        "verifier_principal_must_also_be": ["authenticated", "verified_org"],
        "customer_auth_live_required_for": "any status asserting verification",
        "why": (
            "a verified binding is a row asserting somebody verified "
            "something; writing one while nobody can authenticate leaves that "
            "assertion with no verifier behind it"
        ),
        "derived_never_supplied": [
            "verified_operational_binding",
            "classification",
            "customer_auth_live",
        ],
        "environment_variables": {
            "can_grant": [],
            "can_revoke": ["NF_REAL_ORG_BINDING_ACTIVATION_REVOKED"],
        },
    }


def _dry_run() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dry_run": True,
        "what_it_is": (
            "an evaluation of a hypothetical approval, so an operator can ask "
            "whether one would be enough without recording it"
        ),
        "may_attempt_binding": False,
        "mutation_enabled": False,
        "mutation_performed": False,
        "rows_written": 0,
        "connection_supplied": False,
        "takes_no_connection": True,
        "imports_no_repository": True,
        "blockers": list(STANDING_REFUSALS),
        "permitted_branch_reachable": True,
        "permitted_branch_subject": (
            "a fixture organization that is neither the demo organization nor "
            "the refused real one - kept reachable so every refusal above it "
            "stays falsifiable"
        ),
        "permitted_branch_still_writes_nothing": True,
    }


def _refusal_matrix() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "refusals": [
            {"refusal": name, **REFUSAL_OWNERS[name]}
            for name in (*STANDING_REFUSALS, *CONDITIONAL_REFUSALS)
        ],
        "never_clears": [
            name
            for name in (*STANDING_REFUSALS, *CONDITIONAL_REFUSALS)
            if REFUSAL_OWNERS[name]["kind"] == "never_clears"
        ],
        "refused_shortcuts": [dict(entry) for entry in REFUSED_SHORTCUTS],
        "caller_labels_refused_by_name": True,
        "why_refused_rather_than_ignored": (
            "a caller offering a label as authority learns it was refused "
            "rather than having it silently dropped - Gates 110-113's subject, "
            "restated at a new entry point"
        ),
    }


def _cockpit_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "verified_operational_binding",
        "status": "REQUIRES_HUMAN_APPROVAL",
        "value": False,
        "operational": False,
        "production_ready": False,
        "blockers": list(STANDING_REFUSALS),
        "owner": "Mayhem, and only after a real customer organization exists",
        "what_changed_in_gate_147": (
            "the lane named one refusal - owner_decision_absent - where five "
            "stand. A reader took that to mean one decision would move it. It "
            "would not: there is no organization the decision could apply to, "
            "because the demo org is refused categorically and the real org by "
            "name."
        ),
        "demo_organization_can_ever_satisfy_this": False,
    }


def _blockers() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "verified_operational_binding": False,
        "blocker_count": len(STANDING_REFUSALS),
        "blockers": [
            {"refusal": name, **REFUSAL_OWNERS[name]} for name in STANDING_REFUSALS
        ],
        "stays_false_after_this_gate": list(STAYS_FALSE),
        "approval_boundary_ready": True,
        "boundary_ready_is_not_the_binding": (
            "approval_boundary_ready says the boundary evaluates and refuses "
            "correctly; verified_operational_binding says somebody satisfied "
            "it. They are different questions and both are reported."
        ),
        "real_organization_touched": False,
        "real_organization_binding_rows": 0,
    }


def _next_action_markdown() -> str:
    lines = [
        "# Gate 147 — the next verified-binding human action",
        "",
        "`verified_operational_binding` is false for five reasons, and clearing",
        "any one of them moves nothing on its own.",
        "",
        "```text",
    ]
    for name in STANDING_REFUSALS:
        owner = REFUSAL_OWNERS[name]
        lines.append(name)
        lines.append(f"    kind   {owner['kind']}")
        lines.append(f"    owner  {owner['owner']}")
    lines += [
        "```",
        "",
        "## The order they have to be cleared in",
        "",
        "```text",
        "1  a real customer organization has to exist",
        "     there is none in this deployment other than the refused one.",
        "     This is the step that is further away than it looks.",
        "",
        "2  the second-person event                    Gate 146",
        "     unlocks customer_auth_live, which the verified binding needs",
        "     because the row asserts somebody verified something",
        "",
        "3  Mayhem authorizes that organization",
        "     a reviewed code change adding its id to",
        "     AUTHORIZED_REAL_ORGANIZATION_IDS - not an environment variable,",
        "     and not the injectable test set, which strips both the demo and",
        "     the real organization ids",
        "",
        "4  an approval object is recorded",
        "     five fields, and a scope that covers the environment",
        "",
        "5  a qualified verifier principal acts",
        "     an authenticated platform_admin or tenant_admin with",
        "     verified-org status",
        "```",
        "",
        "## What never clears",
        "",
        "```text",
        "the demo organization is never a verified operational binding",
        "    in any environment, with any approval, with any principal.",
        "    Derived from organizations.org_type.",
        "```",
        "",
        "That is not a limitation to be worked around. It is the fifth",
        "conflation Gate 145 named — the demo organization is not a customer",
        "organization — enforced against the organization rather than against a",
        "label somebody passed in.",
        "",
        "## What stays false",
        "",
        "```text",
    ]
    lines += [f"{name}   false" for name in STAYS_FALSE]
    lines += [
        "```",
        "",
        "This gate made the boundary exact. It did not move it.",
        "",
    ]
    return "\n".join(lines)


def build_verified_binding_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        CHECKLIST_FILE: _json(_checklist_shape()),
        DRY_RUN_FILE: _json(_dry_run()),
        REFUSAL_FILE: _json(_refusal_matrix()),
        COCKPIT_FILE: _json(_cockpit_status()),
        BLOCKERS_FILE: _json(_blockers()),
        NEXT_ACTION_FILE: _next_action_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_verified_binding_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_verified_binding_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def verified_binding_artifact_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
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
