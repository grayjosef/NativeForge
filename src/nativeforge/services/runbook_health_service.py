"""Gate 154C: what an operator should do next, derived from the health model.

## Derived, because the one that was written down went stale

`beta_onboarding_readiness_summary_service.NEXT_SAFE_ACTION` is a module
constant reading `finish_the_controlled_beta_readiness_matrix`. That was true at
Gate 144. The matrix was finished at Gate 145, and Gates 146 through 154 have
happened since. Nothing failed, because a constant cannot go stale loudly.

Every action here comes from a component status in the health model. When a
component moves, the action moves with it, and when nothing is wrong the answer
is "nothing, and here is why".

## Commands are safe to paste, or they are not commands

A command is emitted only if it is non-destructive, already part of the approved
runbook, and passes `command_is_secret_safe` - Gate 121D's rule, imported rather
than reimplemented, because two copies of a secret filter is one copy that falls
behind.

Anything destructive, anything that activates a capability, and anything a human
has to decide is emitted as `HUMAN_APPROVAL_REQUIRED` with **no command at all**.
A runbook that prints the command next to the words "needs approval" has already
handed it over.

## It changes nothing

No subprocess, no socket, no file. It reads a dict and returns a dict. The
operator runs the commands, or a person approves the things that need approving.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_activation_runbook_service import (
    command_is_secret_safe,
)
from nativeforge.services.operational_health_model_service import (
    BACKEND_CODE_DIRTY,
    BACKEND_CODE_EDITED_SINCE_START,
    BACKEND_CODE_STALE,
    BACKEND_CODE_UNKNOWN,
    MIGRATION_AHEAD,
    MIGRATION_BEHIND,
    STALE_STAMP_MISSING,
    STALE_STAMP_OLDER,
)

SCHEMA_VERSION = "nf_runbook_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: An action a person must authorise. Emitted with no command.
HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"

#: An action an operator may run now.
OPERATOR_RUNNABLE = "OPERATOR_RUNNABLE"

#: Nothing to do for this one.
NO_ACTION = "NO_ACTION"

ACTION_KINDS: tuple[str, ...] = (
    OPERATOR_RUNNABLE,
    HUMAN_APPROVAL_REQUIRED,
    NO_ACTION,
)

#: Blocker -> the exact next action. Every command below is non-destructive,
#: already part of the approved runbook, and prints a word or a status.
REMEDIES: dict[str, dict[str, Any]] = {
    "backend_service_not_active": {
        "title": "the backend unit is not running",
        "kind": OPERATOR_RUNNABLE,
        "command": "systemctl --user restart nativeforge-backend.service",
        "why": "every verifier that curls the backend will report BLOCKED first",
    },
    "preview_service_not_active": {
        "title": "the preview unit is not running",
        "kind": OPERATOR_RUNNABLE,
        "command": "systemctl --user restart nativeforge-demo-preview.service",
        "why": "the SPA is not served, and strict-public cannot reach an origin",
    },
    "tunnel_service_not_active": {
        "title": "the tunnel unit is not running",
        "kind": OPERATOR_RUNNABLE,
        "command": "systemctl --user restart nativeforge-mayhem-tunnel.service",
        "why": "the public edge is down; strict-public will fail at the edge",
    },
    BACKEND_CODE_STALE: {
        "title": "the backend started before HEAD was committed",
        "kind": OPERATOR_RUNNABLE,
        "command": "systemctl --user restart nativeforge-backend.service",
        "why": (
            "the running process cannot contain HEAD, so a verifier battery "
            "would be measuring code that is no longer in the repository. This "
            "is the failure mode Gate 147 added a human carry-forward for, "
            "because nothing detected it."
        ),
    },
    BACKEND_CODE_EDITED_SINCE_START: {
        "title": "tracked code changed after the backend started",
        "kind": OPERATOR_RUNNABLE,
        "command": "systemctl --user restart nativeforge-backend.service",
        "why": (
            "the edit postdates the process, so the running code definitely "
            "does not contain it. This is the stale-code case that matters "
            "during development, when the tree is dirty most of the time."
        ),
    },
    BACKEND_CODE_DIRTY: {
        "title": "the tracked tree is dirty and its edit time is unknown",
        "kind": OPERATOR_RUNNABLE,
        "command": "git status --porcelain --untracked-files=no",
        "why": (
            "freshness cannot be established against a commit that does not "
            "exist yet. Commit or revert, then restart."
        ),
    },
    BACKEND_CODE_UNKNOWN: {
        "title": "backend code freshness was not measured",
        "kind": OPERATOR_RUNNABLE,
        "command": (
            "systemctl --user show -p ActiveEnterTimestamp nativeforge-backend.service"
        ),
        "why": "the health model needs the process start time to answer this",
    },
    STALE_STAMP_OLDER: {
        "title": "the built SPA is stamped at an older commit",
        "kind": OPERATOR_RUNNABLE,
        "command": "./scripts/build_frontend_stamped.sh",
        "why": (
            "the preview is serving JavaScript from an older commit. "
            "`--strict-public` does NOT catch this: it checks the stamp tag "
            "exists, never that its sha is current."
        ),
    },
    STALE_STAMP_MISSING: {
        "title": "the build is unstamped",
        "kind": OPERATOR_RUNNABLE,
        "command": "./scripts/build_frontend_stamped.sh",
        "why": (
            "a plain `npm run build` overwrites dist/index.html and removes the "
            "stamp. strict-public DOES catch this one, as identity_meta_present. "
            "The stamped build refuses a dirty tree, so commit first."
        ),
    },
    MIGRATION_BEHIND: {
        "title": "the dev database is behind the repository",
        "kind": OPERATOR_RUNNABLE,
        "command": "source .venv/bin/activate && alembic upgrade head",
        "why": (
            "a migration exists that the database has not applied. Gate 151 hit "
            "exactly this with the database at 0041 and the repository at 0042, "
            "and found it by hand."
        ),
    },
    MIGRATION_AHEAD: {
        "title": "the dev database is ahead of the repository",
        "kind": HUMAN_APPROVAL_REQUIRED,
        "why": (
            "the database has a revision this checkout does not contain. "
            "Downgrading destroys data, and which direction is correct depends "
            "on why the branches differ. A person decides."
        ),
    },
    "migration_state_unknown": {
        "title": "migration state was not measured",
        "kind": OPERATOR_RUNNABLE,
        "command": "source .venv/bin/activate && alembic current",
        "why": "nothing compared the repository head to the database revision",
    },
}

#: Lane blockers an operator cannot clear by running anything. Each names the
#: person and the decision, and carries no command.
HUMAN_BLOCKERS: dict[str, dict[str, Any]] = {
    "lane_false:customer_auth_live": {
        "title": "a named customer has never signed in as themselves",
        "who": "a real person at a customer organization",
        "why": "no code change can cause a second person to authenticate",
    },
    "lane_false:verified_operational_binding": {
        "title": "the operational binding approval is unsigned",
        "who": "an approver",
        "why": "Gate 147 built the boundary; the signature is the missing thing",
    },
    "lane_false:consent_boundary_ready": {
        "title": "consent has not been established",
        "who": "the customer organization",
        "why": "consent cannot be inferred, pre-supplied or defaulted",
    },
    "lane_false:customer_beta_scope_approved": {
        "title": "the customer beta scope is not approved",
        "who": "an approver",
        "why": "Gate 150 reassessed the scope; approving it is a decision",
    },
    "lane_false:controlled_customer_pilot": {
        "title": "the controlled customer pilot is not activated",
        "who": "an approver",
        "why": (
            "Gate 149 built the activation PACKAGE. No activation mechanism "
            "exists, and building one is not an operator action."
        ),
    },
    "lane_false:source_monitoring_live": {
        "title": "live source monitoring is off",
        "who": "an approver, then engineering",
        "why": "activating a collector contacts a live source",
    },
    "lane_false:email_delivery": {
        "title": "email delivery is off",
        "who": "an approver, then a provider admin",
        "why": "configuring a provider sends mail on someone's behalf",
    },
    "lane_false:object_store_configured": {
        "title": "no object store is configured",
        "who": "an approver, then engineering",
        "why": "document bytes have nowhere to go, deliberately",
    },
    "lane_false:production_backup_ready": {
        "title": "no managed database instance exists",
        "who": "procurement",
        "why": (
            "the Gate 61/65 harness cannot run without one and correctly "
            "returns SKIP. Gate 153's operational restore is a different lane "
            "and does not unblock this."
        ),
    },
}

#: Blockers that are findings to investigate rather than actions to take.
INVESTIGATE: dict[str, str] = {
    "legacy_evidence_gaps_present": (
        "delivery intents whose digest predates persistence. Gate 152 counts "
        "them and Gate 153 preserves them across a restore. They are REPORTED, "
        "never backfilled: producing a digest for them would be fabricating "
        "evidence, and a fall in the count fails the lane."
    ),
    "fixture_residue_present": (
        "readiness verifiers write fixture rows into the dev database and do "
        "not always remove them. Row counts and gap counts move between runs. "
        "Run `verify_nativeforge_fixture_cleanliness.sh`; a moving live count "
        "is residue, not drift in a lane."
    ),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _action(
    blocker: str,
    *,
    title: str,
    kind: str,
    why: str,
    command: str | None = None,
    who: str | None = None,
) -> dict[str, Any]:
    # An approval-gated action never carries a command, whatever was passed.
    emitted = None if kind == HUMAN_APPROVAL_REQUIRED else command
    if emitted is not None and not command_is_secret_safe(emitted):
        emitted = None
    return {
        "blocker": blocker,
        "title": title,
        "kind": kind,
        "why": why,
        "command": emitted,
        "who": who,
        "destructive": False,
        "activates_a_capability": False,
    }


def build_runbook_health(
    *,
    health_model: dict[str, Any] | None = None,
    legacy_evidence_gaps: Any = None,
    fixture_residue: Any = None,
) -> dict[str, Any]:
    """Turn a health model into an operator-facing runbook reading."""
    model = health_model or {}
    blockers = list(model.get("blockers") or [])
    # Lanes false BY DESIGN. Not blockers, and still worth showing: an
    # operator asking what to do next deserves to see who has to decide.
    awaiting = list(model.get("awaiting_human_decision") or [])

    actions: list[dict[str, Any]] = []
    unrecognised: list[str] = []

    for blocker in [*blockers, *awaiting]:
        remedy = REMEDIES.get(blocker)
        if remedy is not None:
            actions.append(
                _action(
                    blocker,
                    title=remedy["title"],
                    kind=remedy["kind"],
                    why=remedy["why"],
                    command=remedy.get("command"),
                )
            )
            continue

        human = HUMAN_BLOCKERS.get(blocker)
        if human is not None:
            actions.append(
                _action(
                    blocker,
                    title=human["title"],
                    kind=HUMAN_APPROVAL_REQUIRED,
                    why=human["why"],
                    who=human["who"],
                )
            )
            continue

        if blocker.startswith("verifier_result_unexpected:"):
            name = blocker.split(":", 1)[1]
            actions.append(
                _action(
                    blocker,
                    title=f"{name} did not return what it is expected to return",
                    kind=OPERATOR_RUNNABLE,
                    why=(
                        "run it alone and read its blocker line. A verifier "
                        "often fails because one it depends on failed first - "
                        "the registry records the order."
                    ),
                    command=f"bash scripts/verify_nativeforge_{name}.sh",
                )
            )
            continue

        if blocker.startswith("lane_false:"):
            actions.append(
                _action(
                    blocker,
                    title=f"{blocker.split(':', 1)[1]} is false",
                    kind=HUMAN_APPROVAL_REQUIRED,
                    why="this lane is not something an operator can turn on",
                    who="an approver",
                )
            )
            continue

        unrecognised.append(blocker)
        actions.append(
            _action(
                blocker,
                title=f"unrecognised blocker: {blocker}",
                kind=HUMAN_APPROVAL_REQUIRED,
                why=(
                    "no remedy is registered for this blocker. An unrecognised "
                    "blocker gets a human, not a guess."
                ),
                who="engineering",
            )
        )

    findings: list[dict[str, Any]] = []
    if legacy_evidence_gaps is not None:
        findings.append(
            {
                "finding": "legacy_evidence_gaps",
                "count": int(legacy_evidence_gaps or 0),
                "detail": INVESTIGATE["legacy_evidence_gaps_present"],
                "action_required": False,
                "must_not_be_backfilled": True,
            }
        )
    if fixture_residue is not None:
        findings.append(
            {
                "finding": "fixture_residue",
                "present": bool(fixture_residue),
                "detail": INVESTIGATE["fixture_residue_present"],
                "action_required": bool(fixture_residue),
            }
        )

    runnable = [a for a in actions if a["kind"] == OPERATOR_RUNNABLE]
    approvals = [a for a in actions if a["kind"] == HUMAN_APPROVAL_REQUIRED]

    if runnable:
        next_safe_action = dict(runnable[0])
    elif approvals:
        next_safe_action = {
            **approvals[0],
            "note": ("nothing an operator can run clears this. It needs a person."),
        }
    else:
        next_safe_action = {
            "blocker": None,
            "title": "nothing is blocked in controlled_dev_demo",
            "kind": NO_ACTION,
            "why": (
                "every required component is operational. The remaining lanes "
                "are false because a person has to decide something, not "
                "because anything is broken."
            ),
            "command": None,
            "who": None,
            "destructive": False,
            "activates_a_capability": False,
        }

    if not blockers and awaiting:
        next_safe_action = {
            **next_safe_action,
            "waiting_on_people": sorted(awaiting),
            "note": (
                "nothing is broken and nothing is runnable. "
                f"{len(awaiting)} lane(s) are waiting on a human decision."
            ),
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "actions": actions,
            "action_count": len(actions),
            "operator_runnable_count": len(runnable),
            "human_approval_required_count": len(approvals),
            "unrecognised_blockers": sorted(unrecognised),
            "awaiting_human_decision": sorted(awaiting),
            "blockers_and_awaiting_are_different": (
                "a blocker is something wrong that somebody can act on. An "
                "awaiting entry is a lane that is false on purpose until a "
                "person decides. Both are shown; only a blocker means a fault."
            ),
            "findings": findings,
            "next_safe_action": next_safe_action,
            "derived_not_declared": (
                "every action comes from a component status in the health "
                "model. The one that was written down as a constant went stale "
                "nine gates ago and nothing failed."
            ),
            # Constants. A runbook reading reads.
            "production_monitoring_active": False,
            "alerting_configured": False,
            "shell_executed": False,
            "external_call_made": False,
            "email_sent": False,
            "rows_written": 0,
        }
    )


def runbook_health_invariant_failures(runbook: dict[str, Any]) -> list[str]:
    """Refuse a runbook that hands over a command it should have gated."""
    fails: list[str] = []

    actions = runbook.get("actions") or []
    for action in actions:
        kind = action.get("kind")
        if kind not in ACTION_KINDS:
            fails.append(f"action_kind_outside_vocabulary:{action.get('blocker')}")
        # The one that matters: approval-gated work must carry no command.
        if kind == HUMAN_APPROVAL_REQUIRED and action.get("command"):
            fails.append(
                f"approval_gated_action_carried_a_command:{action.get('blocker')}"
            )
        if action.get("destructive"):
            fails.append(
                f"runbook_emitted_a_destructive_action:{action.get('blocker')}"
            )
        if action.get("activates_a_capability"):
            fails.append(f"runbook_emitted_an_activation:{action.get('blocker')}")
        command = action.get("command")
        if command and not command_is_secret_safe(str(command)):
            fails.append(f"command_would_print_a_secret:{action.get('blocker')}")

    runnable = sum(1 for a in actions if a.get("kind") == OPERATOR_RUNNABLE)
    approvals = sum(1 for a in actions if a.get("kind") == HUMAN_APPROVAL_REQUIRED)
    if runnable != runbook.get("operator_runnable_count"):
        fails.append("operator_runnable_count_disagrees")
    if approvals != runbook.get("human_approval_required_count"):
        fails.append("human_approval_required_count_disagrees")
    if len(actions) != runbook.get("action_count"):
        fails.append("action_count_disagrees")

    nxt = runbook.get("next_safe_action") or {}
    if nxt.get("kind") == HUMAN_APPROVAL_REQUIRED and nxt.get("command"):
        fails.append("next_safe_action_is_gated_but_carries_a_command")
    if not nxt.get("title"):
        fails.append("next_safe_action_has_no_title")

    for finding in runbook.get("findings") or []:
        if finding.get("finding") == "legacy_evidence_gaps" and not finding.get(
            "must_not_be_backfilled"
        ):
            fails.append("legacy_gap_finding_lost_its_do_not_backfill_rule")

    for flag in (
        "production_monitoring_active",
        "alerting_configured",
        "shell_executed",
        "external_call_made",
        "email_sent",
    ):
        if runbook.get(flag):
            fails.append(f"runbook_claimed:{flag}")

    if runbook.get("rows_written"):
        fails.append("runbook_wrote_rows")

    return sorted(set(fails))
