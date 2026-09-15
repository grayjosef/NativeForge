"""Gate 155G: the block close, written down.

Deterministic: no database, no shell, no arguments. Lane values are the ones
each lane's verifier proved; the two production flags are constants.

Gate 153 pinned a live row count in a committed document and it went stale
within the hour. Nothing here carries a live count.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.next_activation_decision_service import (
    CANDIDATES,
    build_next_activation_decision,
)
from nativeforge.services.operational_durability_reassessment_service import (
    CONFLATIONS,
    DURABILITY_LANES,
    GATE_150_BASELINE,
    SAFE_CLAIMS,
    UNCHANGED_FALSE_LANES,
    UNSAFE_CLAIMS,
    build_durability_reassessment,
)

SCHEMA_VERSION = "nf_operational_durability_gate155_artifacts_v1"

ARTIFACT_DIR = "artifacts/operational_durability_gate155"

SURVEY_FILE = "operational_durability_reassessment_survey.json"
LANE_DELTA_FILE = "gates151_154_lane_delta.json"
DECISION_FILE = "operational_durability_decision.json"
CUSTOMER_FILE = "customer_beta_decision_after_durability.json"
PRODUCTION_FILE = "production_decision_after_durability.json"
SAFE_FILE = "safe_durability_claims.json"
UNSAFE_FILE = "unsafe_durability_claims.json"
NEXT_FILE = "next_activation_decision.json"
CLOSEOUT_FILE = "gates151_155_closeout.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    LANE_DELTA_FILE,
    DECISION_FILE,
    CUSTOMER_FILE,
    PRODUCTION_FILE,
    SAFE_FILE,
    UNSAFE_FILE,
    NEXT_FILE,
    CLOSEOUT_FILE,
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


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _decision() -> dict[str, Any]:
    return build_next_activation_decision(
        real_customer_org_exists=False,
        second_identity_available=False,
        consent_decision_available=False,
    )


def _reassessment() -> dict[str, Any]:
    return build_durability_reassessment(
        internal_demo_beta="GO",
        controlled_customer_beta="LIMITED_GO",
        tenant_digest_persistence_live=True,
        audit_replay_ready=True,
        operational_backup_restore_ready=True,
        operational_health_ready=True,
        production_backup_ready=False,
        production_monitoring_active=False,
        controlled_customer_pilot=False,
        activation_mechanism_exists=False,
        customer_auth_live=False,
        verified_operational_binding=False,
        consent_boundary_documented=False,
        customer_beta_scope_approved=False,
        source_monitoring_live=False,
        email_delivery=False,
        object_store_configured=False,
        next_block=_decision(),
    )


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "155",
        "block": "Gates 151-155, operational durability",
        "subject": "what the block moved, and what comes next",
        "how_the_lane_delta_was_measured": (
            "git grep for each lane name across src/ at commit 4d336d1, the "
            "Gate 150 commit. All four returned zero files, so the four lanes "
            "were CREATED by this block rather than flipped from false."
        ),
        "how_the_next_block_was_chosen": (
            "by counting, for each candidate, how many of its blockers are "
            "absent components rather than absent approvals. Measured from "
            "each lane's own verifier output, not estimated."
        ),
        "two_next_step_constants_have_gone_stale_in_this_repository": {
            "beta_onboarding_readiness_summary_service.NEXT_SAFE_ACTION": (
                "recommended finishing a matrix that was finished at Gate 145; "
                "found by Gate 154"
            ),
            "customer_beta_reassessment_service.NEXT_BLOCK": (
                "recommends Gates 151-155, which this gate closes. Spent."
            ),
            "why_neither_failed": "a constant cannot go stale loudly",
            "what_gate_155_does_about_it": (
                "the ranking is derived from supplied blocker counts, so a "
                "candidate whose blockers change gets a different answer with "
                "nobody editing anything"
            ),
        },
        "gate_150_predicted_this_block_and_got_two_of_five_wrong": {
            "predicted_152": "source terms review tooling",
            "actual_152": "audit replay and the evidence ledger",
            "predicted_154": "operational runbook and on-call",
            "actual_154": "observability and runbook health",
            "the_point": "a prediction is not a measurement",
        },
        "nothing_was_activated": True,
        "no_activation_mechanism_was_created": True,
    }


def _lane_delta() -> dict[str, Any]:
    reassessment = _reassessment()
    return {
        "schema_version": SCHEMA_VERSION,
        **reassessment["lane_delta"],
        "baseline": dict(GATE_150_BASELINE),
        "lanes_declared_by_this_block": [dict(e) for e in DURABILITY_LANES],
        "lanes_that_must_stay_false": list(UNCHANGED_FALSE_LANES),
    }


def _customer_decision() -> dict[str, Any]:
    reassessment = _reassessment()
    return {
        "schema_version": SCHEMA_VERSION,
        "controlled_customer_beta": reassessment["customer_beta_decision"],
        "gate_145": GATE_150_BASELINE["controlled_customer_beta"],
        "gate_150": GATE_150_BASELINE["controlled_customer_beta"],
        "changed": False,
        "why_unchanged": (
            "the four outstanding approvals are unchanged and none is "
            "technical. Gates 151-154 touched none of them, and a durability "
            "block that moved a customer decision would mean one of its gates "
            "had granted itself an approval."
        ),
        "outstanding_approvals": [
            "customer_auth_live - a real person must sign in as themselves",
            "verified_operational_binding - an approval must be signed",
            "consent_and_data_boundary_documented - the customer must consent",
            "customer_beta_scope_approved - an approver must approve the scope",
        ],
        "a_real_customer_organization_still_does_not_exist": True,
    }


def _production_decision() -> dict[str, Any]:
    reassessment = _reassessment()
    return {
        "schema_version": SCHEMA_VERSION,
        "production_rollout": reassessment["production_decision"],
        "changed": False,
        "no_branch_computes_it": True,
        **reassessment["production_durability"],
        "what_would_have_to_happen_first": [
            "a managed database instance (procurement)",
            "backup automation, which needs the instance",
            "point-in-time recovery, which needs a provider that has it",
            "an executed provider restore, which needs all three",
            "monitoring and alerting, none of which exists",
        ],
        "gate_153_did_not_move_this": True,
        "gate_154_did_not_move_this": True,
    }


def _closeout_markdown() -> str:
    decision = _decision()
    lines = [
        "# Gates 151-155 — operational durability, closed",
        "",
        "## What the block did",
        "",
        "```text",
        "151  a digest is persisted and reads back with its payload hash intact",
        "152  recorded evidence replays; legacy gaps are reported, never filled",
        "153  that state exports, restores into an isolated database, and still",
        "     passes the Gate 152 replay",
        "154  service, migration and code-freshness state is modelled; ten",
        "     failure modes are named; the next safe action is derived",
        "155  this close",
        "```",
        "",
        "Together: evidence this system writes can be re-read, re-proved, moved",
        "to another database and re-proved there, and the deployment can say",
        "what state it is in.",
        "",
        "## What the block did NOT do",
        "",
        "**Nothing that was false at Gate 150 is true now.**",
        "",
        "The four lanes above did not exist at Gate 150 - measured, zero files",
        "mentioned any of them. They were created and proved. No approval was",
        "granted, no capability activated, no decision moved.",
        "",
        "```text",
        "internal_demo_beta         GO          unchanged since Gate 145",
        "controlled_customer_beta   LIMITED_GO  unchanged since Gate 145",
        "production_rollout         NO_GO       unchanged since Gate 145",
        "```",
        "",
        "## The two claims a reader will reach for, and why both are wrong",
        "",
        "```text",
        '"NativeForge has backups"',
        "  No. Gate 153 exports controlled dev/demo state and reloads it into",
        "  an isolated database. The Gate 61/65 production harness needs a",
        "  managed instance and still returns SKIP. Different harnesses,",
        "  opposite questions.",
        "",
        '"NativeForge is monitored"',
        "  No. Gate 154 lets the deployment report its own state when asked.",
        "  Nothing watches it. No APM, no alerting, no external monitor, no",
        "  uptime record. A person runs a verifier.",
        "```",
        "",
        "## What comes next, and why",
        "",
        f"**{decision['recommended_block']}** — {decision['recommended_subject']}",
        "",
        "```text",
        "candidate                 blockers  human  engineering",
    ]
    for entry in decision["ranked_candidates"]:
        lines.append(
            f"{entry['candidate']:26s}{entry['blocker_count']:>6}"
            f"{entry['human_blocker_count']:>7}{entry['engineering_blocker_count']:>13}"
        )
    lines += [
        "```",
        "",
        "Source collection is the only candidate where engineering can clear a",
        "majority of the blockers. Five of its seven are absent components - a",
        "scheduler runtime, a background worker, a periodic trigger, a durable",
        "backend, a raw payload store. `backend_lifespan_hook_service` has",
        'described itself since Gate 102 as "the attach point a future',
        "in-process scheduler would use, and a record of the fact that nothing",
        'is attached to it."',
        "",
        "Every other candidate is blocked only by people:",
        "",
        "```text",
        "customer activation   4 approvals, 0 technical",
        "email                 a provider configuration decision",
        "object storage        a provisioning decision",
        "production            procurement",
        "more durability       nothing is blocked; it would harden the hardened",
        "```",
        "",
        "Recommending any of those would produce another readiness wrapper",
        "around a blocker only a person can clear, which is the one thing this",
        "gate is forbidden to do.",
        "",
        "## What the recommendation does not mean",
        "",
        "- **Not** that `source_monitoring_live` would become true.",
        "- **Not** that any source would be polled. 171 registry sources are",
        "  `terms_blocked`, 6 are `human_review_blocked`, and 0 are approved.",
        "- **Not** that the two human source blockers are cleared. They stay.",
        "- **Not** that a collector is activated.",
        "",
        "A scheduler with an empty allowlist polls nothing and contacts",
        "nothing, which is exactly how it should be proved before any source",
        "is approved. It removes five of the seven reasons monitoring cannot",
        "start; the remaining two stay human.",
        "",
    ]
    return "\n".join(lines)


def build_durability_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; no database, no shell."""
    reassessment = _reassessment()
    files = {
        SURVEY_FILE: _json(_survey()),
        LANE_DELTA_FILE: _json(_lane_delta()),
        DECISION_FILE: _json(reassessment),
        CUSTOMER_FILE: _json(_customer_decision()),
        PRODUCTION_FILE: _json(_production_decision()),
        SAFE_FILE: _json(
            {
                "schema_version": SCHEMA_VERSION,
                "safe_claims": list(SAFE_CLAIMS),
                "safe_claim_count": len(SAFE_CLAIMS),
                "read_with": UNSAFE_FILE,
            }
        ),
        UNSAFE_FILE: _json(
            {
                "schema_version": SCHEMA_VERSION,
                "unsafe_claims": [dict(e) for e in UNSAFE_CLAIMS],
                "unsafe_claim_count": len(UNSAFE_CLAIMS),
                "conflations": [dict(e) for e in CONFLATIONS],
                "candidates_considered": [e["candidate"] for e in CANDIDATES],
            }
        ),
        NEXT_FILE: _json(_decision()),
        CLOSEOUT_FILE: _closeout_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_durability_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_durability_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def durability_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
