"""Gate 150F: the customer beta reassessment, written down.

Deterministic: reads no database and takes no arguments. What is committed is
the part that does not move — the baseline, what each gate clarified, the
conflations, the claim lists and the next block. Live values belong in the
verifier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.customer_beta_reassessment_service import (
    CLARIFICATIONS,
    CONFLATIONS,
    CUSTOMER_BETA_APPROVALS,
    GATE_145_BASELINE,
    NEXT_BLOCK,
    NOT_APPROVED,
    SAFE_CLAIMS,
    THE_THROUGHLINE,
    UNSAFE_CLAIMS,
)

SCHEMA_VERSION = "nf_customer_beta_reassessment_gate150_artifacts_v1"

ARTIFACT_DIR = "artifacts/customer_beta_reassessment_gate150"

SURVEY_FILE = "customer_beta_reassessment_survey.json"
DELTA_FILE = "gate145_to_gate150_decision_delta.json"
DECISION_FILE = "current_customer_beta_decision.json"
BLOCKERS_FILE = "clarified_blockers.json"
SAFE_FILE = "safe_customer_facing_claims.json"
UNSAFE_FILE = "unsafe_customer_facing_claims.json"
NEXT_BLOCK_FILE = "next_block_recommendation.json"
CLOSEOUT_FILE = "gates146_150_closeout.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    DELTA_FILE,
    DECISION_FILE,
    BLOCKERS_FILE,
    SAFE_FILE,
    UNSAFE_FILE,
    NEXT_BLOCK_FILE,
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
            raise AssertionError(f"forbidden shape {shape!r} in {name}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "question": "did the customer beta decision change?",
        "answer": "no, and that is the correct answer",
        "why": (
            "Gates 146-149 were boundary gates, built to make refusals exact "
            "rather than to clear them. A block of four gates that moved a lane "
            "without a new external approval would mean one of them had "
            "granted itself something."
        ),
        "lanes_moved_by_this_block": 0,
        "what_changed": "what is understood, not what is true",
        "clarifications": [dict(entry) for entry in CLARIFICATIONS],
        "throughline": dict(THE_THROUGHLINE),
        "conflations": [dict(entry) for entry in CONFLATIONS],
        "not_approved": list(NOT_APPROVED),
    }


def _delta() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_145_baseline": dict(GATE_145_BASELINE),
        "expected_now": dict(GATE_145_BASELINE),
        "expected_change": "none",
        "a_change_would_require": (
            "a new external approval - a second person signing in, an owner "
            "authorizing an organization, a consent document, or a scope "
            "approval. No gate can grant any of them."
        ),
        "distrust_a_report_of": (
            "controlled_customer_beta GO without all four approvals recorded"
        ),
    }


def _decision() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "internal_demo_beta": GATE_145_BASELINE["internal_demo_beta"],
        "controlled_customer_beta": GATE_145_BASELINE["controlled_customer_beta"],
        "production_rollout": GATE_145_BASELINE["production_rollout"],
        "production_is_never_computed": True,
        "customer_beta_approvals": list(CUSTOMER_BETA_APPROVALS),
        "customer_beta_approvals_outstanding": list(CUSTOMER_BETA_APPROVALS),
        "no_outstanding_customer_blocker_is_technical": True,
        "controlled_customer_pilot": False,
        "activation_mechanism_exists": False,
    }


def _blockers() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "clarified": [dict(entry) for entry in CLARIFICATIONS],
        "external_or_human": [
            "a real customer organization",
            "the second person signing in",
            "Google OAuth test-user enrolment",
            "the consent document, then a record",
            "the customer beta scope approval",
            "the verified binding authorization",
            "a support and rollback owner",
            "171 source terms reviews",
        ],
        "technical": [
            "source_monitoring_live: robots.txt per source, an activation "
            "approval per source, five scheduler components",
            "email_delivery: a provider, a verified sender domain, unsubscribe "
            "and bounce handling",
            "object_store_configured: five settings, an injected client, an "
            "external verification",
            "digest persistence: delivery intents name a digest nobody kept",
        ],
        "note": (
            "nothing blocking the customer beta is technical - all four of its "
            "approvals are human"
        ),
    }


def _safe_claims() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "safe_claims": list(SAFE_CLAIMS),
        "count": len(SAFE_CLAIMS),
        "scope": "controlled_dev_demo",
        "each_is": "true as measured today",
        "the_most_useful_one": (
            "we can show you exactly what would have to be true before your "
            "organization could use this, and who has to decide each part"
        ),
    }


def _unsafe_claims() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "unsafe_claims": [dict(entry) for entry in UNSAFE_CLAIMS],
        "count": len(UNSAFE_CLAIMS),
        "each_has_a_true_alternative": True,
        "the_dangerous_one": {
            "claim": "the binding is in place, we just need an approval",
            "why": (
                "nearly true and entirely wrong - the approval is not what is "
                "missing, a customer organization is"
            ),
        },
        "an_inventory_is_not_a_saying": True,
    }


def _next_block() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **NEXT_BLOCK}


def _closeout_markdown() -> str:
    lines = [
        "# Gates 146–150 — closeout",
        "",
        "## The decision",
        "",
        "```text",
        f"internal_demo_beta         {GATE_145_BASELINE['internal_demo_beta']}",
        "controlled_customer_beta   "
        f"{GATE_145_BASELINE['controlled_customer_beta']}",
        f"production_rollout         {GATE_145_BASELINE['production_rollout']}",
        "```",
        "",
        "Unchanged from Gate 145. Four gates, zero lanes moved, and that is the",
        "correct outcome: these were boundary gates.",
        "",
        "## What each gate established",
        "",
        "```text",
    ]
    for entry in CLARIFICATIONS:
        lines.append(f"{entry['gate']}  {entry['subject']}")
        lines.append(f"      was reported as   {entry['was_reported_as']}")
        lines.append(f"      is actually       {entry['is_actually']}")
        lines.append(f"      lane moved        {entry['lane_moved']}")
        lines.append("")
    lines += [
        "```",
        "",
        "## The throughline",
        "",
        f"**{THE_THROUGHLINE['finding']}**",
        "",
        f"Found independently by Gates {', '.join(THE_THROUGHLINE['found_by'])}.",
        "",
        THE_THROUGHLINE["why_it_matters"],
        "",
        "## The conflations this block named",
        "",
        "```text",
    ]
    for entry in CONFLATIONS:
        lines.append(f"{entry['readiness']}")
        lines.append(f"    is not  {entry['capability']}")
        lines.append(f"    because {entry['difference']}   (gate {entry['gate']})")
    lines += [
        "```",
        "",
        "## The four approvals still outstanding",
        "",
        "```text",
    ]
    lines += [f"- {name}" for name in CUSTOMER_BETA_APPROVALS]
    lines += [
        "```",
        "",
        "None is technical. All four are a person deciding, a person signing in,",
        "or a document nobody has written.",
        "",
        "## What may be said today",
        "",
        "```text",
    ]
    lines += [f"- {claim}" for claim in SAFE_CLAIMS]
    lines += [
        "```",
        "",
        "## What may not",
        "",
        "```text",
    ]
    for entry in UNSAFE_CLAIMS:
        lines.append(f"not  {entry['claim']}")
        lines.append(f"say  {entry['true_statement']}")
    lines += [
        "```",
        "",
        "## Next",
        "",
        f"**{NEXT_BLOCK['block']}**, starting at {NEXT_BLOCK['first_gate']}.",
        "",
        NEXT_BLOCK["why"],
        "",
    ]
    return "\n".join(lines)


def build_reassessment_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        DELTA_FILE: _json(_delta()),
        DECISION_FILE: _json(_decision()),
        BLOCKERS_FILE: _json(_blockers()),
        SAFE_FILE: _json(_safe_claims()),
        UNSAFE_FILE: _json(_unsafe_claims()),
        NEXT_BLOCK_FILE: _json(_next_block()),
        CLOSEOUT_FILE: _closeout_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_reassessment_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_reassessment_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def reassessment_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
