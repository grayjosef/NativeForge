"""Gate 153H: the backup manifest, the round trip and the lane, written down.

Deterministic: reads no database and takes no arguments. Live row counts belong
in the verifier, which measures them; what is committed here is the manifest and
its reasons, the shape of the round trip, the two refusals, the defect this gate
found in its own first draft, and the blockers that stay open afterwards.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.operational_backup_manifest_service import (
    EXCLUDED_TABLES,
    INCLUDED_TABLES,
    MANIFEST_MIGRATION_HEAD,
    REVIEW_HINT_COLUMNS,
    build_backup_manifest,
)
from nativeforge.services.operational_backup_restore_readiness_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    MUST_STAY_FALSE,
)
from nativeforge.services.operational_restore_service import (
    FORBIDDEN_FIELDS,
    ISOLATED_TARGET,
    RESTORE_LIMITATIONS,
)
from nativeforge.services.operational_restore_verification_service import (
    ORDERED_CHECKS,
)

SCHEMA_VERSION = "nf_backup_restore_gate153_artifacts_v1"

ARTIFACT_DIR = "artifacts/backup_restore_gate153"

SURVEY_FILE = "backup_restore_survey.json"
MANIFEST_FILE = "operational_backup_manifest.json"
EXCLUSIONS_FILE = "backup_table_exclusions.json"
EXPORT_SHAPE_FILE = "backup_export_shape.json"
RESTORE_RULES_FILE = "restore_refusal_rules.json"
VERIFICATION_FILE = "restore_verification_checks.json"
READINESS_FILE = "backup_restore_readiness.json"
BLOCKERS_FILE = "next_backup_restore_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    MANIFEST_FILE,
    EXCLUSIONS_FILE,
    EXPORT_SHAPE_FILE,
    RESTORE_RULES_FILE,
    VERIFICATION_FILE,
    READINESS_FILE,
    BLOCKERS_FILE,
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


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "153",
        "subject": "operational backup and restore readiness",
        "scope": "controlled_dev_demo",
        "two_different_harnesses": {
            "infrastructure_path": {
                "verifier": "scripts/verify_nativeforge_backup_restore.sh",
                "gate": "61/65",
                "question": "can the provider dump and restore a database?",
                "result": "SKIP",
                "why": (
                    "no managed instance exists. Every substantive check is "
                    "SKIP and has been since it was written."
                ),
                "unblocked_by_gate_153": False,
            },
            "data_path": {
                "verifier": ("scripts/verify_nativeforge_backup_restore_readiness.sh"),
                "gate": "153",
                "question": (
                    "can this system export its own controlled dev/demo "
                    "operational state, load it into an isolated database, and "
                    "still pass the Gate 152 replay?"
                ),
                "result": "runnable today, on the dev database, with no provider",
            },
        },
        "why_the_data_path_is_worth_having_on_its_own": (
            "a provider dump proves bytes survive a round trip. It proves "
            "nothing about whether a digest still hashes, an intent still "
            "resolves, or an archived row still reads - which is what a "
            "restore has to be good for."
        ),
        "the_defect_this_gate_found_in_its_own_first_draft": {
            "what": (
                "the table classifier matched column NAMES against a list of "
                "unsafe words including `state`"
            ),
            "what_it_flagged": [
                "nf_org_memberships.state - VARCHAR(32), holds 'active'",
                "nf_authority_proof_records.state - VARCHAR(32), Gate 52 lifecycle",
            ],
            "why_both_are_false_positives": (
                "both are row lifecycle states. The word also names an OAuth "
                "state, and a name-matching scan cannot tell them apart."
            ),
            "the_shape_of_the_mistake": (
                "substring versus meaning - the defect class this campaign has "
                "now hit about eighteen times, committed here by the tool "
                "built to prevent an information leak"
            ),
            "the_fix": (
                "classify by meaning with a declared reason per table. The "
                "name matcher survives only as review_hint_columns, "
                "documented as a review aid and never a gate."
            ),
        },
        "a_second_defect_found_while_building": {
            "what": (
                "the restore verification read the digest primary key `id` and "
                "asked the replay about it, but `replay_digest` resolves the "
                "separate tenant-facing `digest_id` column"
            ),
            "what_it_looked_like": (
                "missing_record for a digest sitting in the table - a lookup "
                "key mistake wearing the costume of a data integrity failure"
            ),
            "a_third": (
                "the same check then measured the whole chain's "
                "evidence_status, which is the WEAKEST link. On the one "
                "persisted fixture digest that link is not_replayable, because "
                "no delivery intent names it - an honest Gate 152 finding "
                "about queueing that says nothing about whether the payload "
                "hashes. It does. The check now reads the payload_hash link."
            ),
        },
        "migration_head": MANIFEST_MIGRATION_HEAD,
        "production_backup_ready": False,
    }


def _exclusions() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "excluded_tables": [dict(entry) for entry in EXCLUDED_TABLES],
        "excluded_count": len(EXCLUDED_TABLES),
        "review_hint_columns": list(REVIEW_HINT_COLUMNS),
        "review_hints_are_not_a_gate": (
            "`state` matches both an OAuth state and a row lifecycle state. "
            "Every exclusion here is a reason a person wrote, not a word a "
            "scanner matched."
        ),
        "the_three_that_must_never_be_exported": [
            "nf_identities",
            "nf_auth_redirect_states",
            "organizations",
        ],
        "organizations_is_a_precondition_not_a_payload": (
            "a restore target must already hold the organization row. "
            "Recreating it from a backup is how the real organization would "
            "arrive somewhere nobody authorized it."
        ),
    }


def _export_shape() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "controlled_dev_demo",
        "organization_scoped": True,
        "included_tables": [entry["table"] for entry in INCLUDED_TABLES],
        "included_count": len(INCLUDED_TABLES),
        "per_table_fields": [
            "rows",
            "row_count",
            "payload_sha256",
            "columns",
            "excluded_fields",
            "hash_fields",
            "archive_field",
        ],
        "hash_is_order_independent": (
            "rows are sorted by their serialised form before hashing, so two "
            "exports of the same data hash the same whatever order the "
            "database returned them in. An unordered SELECT is not a "
            "guarantee, and a hash that changed with row order would fail a "
            "restore for no reason."
        ),
        "the_gate_is_the_value_scan_not_the_column_name": (
            "every exported payload is scanned for the SHAPES that must never "
            "leave: an address, a provider subject, a token, an OAuth state, a "
            "PKCE verifier"
        ),
        "every_row_must_be_a_fixture": (
            "is_demo true or fact_status demo_fixture. A row that is neither "
            "is counted as skipped_non_fixture_rows rather than silently "
            "dropped, because a non-fixture row in a controlled export is a "
            "finding."
        ),
        "an_export_writes_nothing": True,
        "no_route_returns_the_rows": (
            "the four GET routes return counts, columns, exclusions and "
            "hashes. An export exists to be handed to a restore, not to a "
            "browser."
        ),
    }


def _restore_rules() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "only_target_kind_accepted": ISOLATED_TARGET,
        "refusals": [
            {
                "blocker": "restore_target_is_not_isolated",
                "means": "the target was not declared an isolated database",
                "exercised_by": "the verifier runs this call and asserts the block",
            },
            {
                "blocker": "restore_target_is_the_source_database",
                "means": "the target URL equals the source URL",
                "exercised_by": "the verifier runs this call and asserts the block",
            },
            {
                "blocker": "payload_hash_mismatch",
                "means": "a table does not hash to what the payload claims",
                "checked": "BEFORE any row is written, never after",
            },
            {
                "blocker": "payload_contains_a_forbidden_field",
                "means": "a field arrived that no manifest table carries",
            },
            {
                "blocker": "payload_contains_a_non_fixture_row",
                "means": (
                    "refused as a whole rather than filtered. A mixed payload "
                    "means the export that produced it was wrong, and loading "
                    "half of it would hide that."
                ),
            },
            {
                "blocker": "real_organization_refused_by_name",
                "means": "the payload names the real organization",
            },
            {
                "blocker": "migration_head_mismatch",
                "means": "the payload and the target disagree on schema version",
            },
        ],
        "why_a_refusal_is_run_not_asserted": (
            "Gate 134F: a permitted branch nobody can reach makes a refusal "
            "unfalsifiable. Both target refusals are called by the verifier "
            "and by a test, and each must refuse AND write zero rows."
        ),
        "forbidden_fields": sorted(FORBIDDEN_FIELDS),
        "nothing_is_invented": (
            "a row whose link points outside the payload is restored with the "
            "dangling link intact. A restore that filled in the missing end "
            "would be manufacturing evidence; the verification reports it."
        ),
        "restore_limitations": list(RESTORE_LIMITATIONS),
        "production_backup_ready": False,
    }


def _verification() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "checks": list(ORDERED_CHECKS),
        "check_count": len(ORDERED_CHECKS),
        "runs_the_gate_152_code_unmodified": (
            "audit_replay_service and evidence_ledger_service, against the "
            "restored connection and against the source, compared. If restored "
            "state needed its own special replay to pass, the restore would "
            "not have restored anything worth having."
        ),
        "unknown_is_not_a_pass": (
            "a check that could not run is UNKNOWN, and `verified` is false "
            "while any check is UNKNOWN"
        ),
        "equal_is_not_the_same_as_good": (
            "the comparison is source versus restored, not restored versus "
            "healthy. A source holding a missing_record must restore to a "
            "missing_record: that is a pass here and a finding in the ledger."
        ),
        "a_gap_is_supposed_to_survive": (
            "legacy delivery intents whose digest predates persistence must "
            "still be legacy_gap afterwards. A restore that reduced the count "
            "invented a digest, and fails the lane rather than passing it."
        ),
        "a_hash_check_with_nothing_to_check_is_not_a_pass": (
            "the verifier requires at least one digest to be hash-proven. "
            "Nothing to preserve is not the same as preserved."
        ),
    }


def _readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "operational_backup_restore_ready",
        "scope": "controlled_dev_demo",
        "conditions": list(CONDITIONS),
        "condition_count": len(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "must_stay_false": list(MUST_STAY_FALSE),
        "derived_never_supplied": True,
        "production_backup_ready": False,
        "production_is_never_computed": True,
        "what_this_lane_does_not_mean": [
            "that production is backed up",
            "that any customer data was backed up; none exists",
            "that object storage was backed up; none is configured",
            "that an RPO or RTO is enforced by anything",
            "that a real organization was exported, restored or touched",
        ],
    }


def _blockers_markdown() -> str:
    lines = [
        "# Gate 153 — what is still blocked after this gate",
        "",
        "`operational_backup_restore_ready` is true for `controlled_dev_demo`.",
        "That means this system can export its own operational state for one",
        "organization,",
        "load it into an isolated database, and still pass the Gate 152 replay.",
        "",
        "It does not mean production is backed up. Nothing below moved.",
        "",
        "## Still blocked, and by what",
        "",
        "```text",
        "a managed database instance   procurement. Unblocks the Gate 61/65",
        "                              harness, which is still RESULT=SKIP.",
        "backup automation             needs the instance first",
        "point-in-time recovery        needs a provider that supports it",
        "an executed provider restore  needs all three",
        "```",
        "",
        "None of those is engineering work, and none of them is what Gate 153",
        "built. `scripts/verify_nativeforge_backup_restore.sh` measures them and",
        "continues to return SKIP.",
        "",
        "## Not applicable rather than blocked",
        "",
        "```text",
        "customer data backup    no customer data exists to back up",
        "object store backup     no object store is configured",
        "RPO / RTO in force      documented, enforced by nothing",
        "```",
        "",
        "## What must not be read into the lane",
        "",
        "- The export is fixture data for one demo organization.",
        "- The real organization is refused by name and was never read.",
        "- No identity, redirect state or organization row is ever exported.",
        "- The restore target is a temporary database, deleted by the verifier.",
        "- Legacy gaps survive the round trip as legacy gaps. A restore that",
        "  closed one would have invented a digest for an intent that never",
        "  had one.",
        "",
        "## The honest summary",
        "",
        "The data path is proven and the infrastructure path is untouched. A",
        "reader who takes `operational_backup_restore_ready=true` to mean the",
        "product has backups has read it wrong, and the lane says so in four",
        "places.",
        "",
    ]
    return "\n".join(lines)


def build_backup_restore_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        MANIFEST_FILE: _json(build_backup_manifest()),
        EXCLUSIONS_FILE: _json(_exclusions()),
        EXPORT_SHAPE_FILE: _json(_export_shape()),
        RESTORE_RULES_FILE: _json(_restore_rules()),
        VERIFICATION_FILE: _json(_verification()),
        READINESS_FILE: _json(_readiness()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_backup_restore_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_backup_restore_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def backup_restore_artifact_invariant_failures(
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
