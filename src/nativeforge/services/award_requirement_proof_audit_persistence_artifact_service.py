"""Proof audit persistence artifacts (Gate 126H).

Four files describing the repository, what it validates, and what none of it
makes true. Written to `artifacts/award_requirement_proof_audit_persistence/`.

```text
award_requirement_proof_audit_repository_contract.json    operations, columns
award_requirement_proof_audit_validation_matrix.csv       one row per case
award_requirement_proof_audit_persistence_demo_fixtures.json  the 14 cases
award_requirement_proof_audit_persistence_readiness_summary.md  what is blocked
```

## Four scans, and the fourth is measured rather than frozen

```text
1  by field name  anything named like real award or tenant data
2  by inference   any result claiming an inference this campaign prohibits
3  by claim       any payload asserting a funder decided something the row
                  does not support, or that a record was removed
4  by capability  any payload whose capability claim disagrees with reality
```

The fourth is measured because Gate 125 froze `proof_audit_persistence_available:
False` into a constant and this gate falsified it. A frozen claim goes stale
silently — its own invariant compared the declaration against the same constant
and agreed with itself. Comparing against what is actually available means a
claim becomes acceptable the day it becomes true.

## Removal is the dangerous claim

`scan_for_claimed_removals` is this gate's addition. An audit artifact asserting
`proof_deleted` or `audit_record_deleted` would be a file saying evidence went
away, and the entire reason this table exists is that it cannot.

## No real filing appears

Every organization, award, requirement and document reference is a fixed fixture
value, every label carries the `nf-demo-fixture-` prefix, and every fact status
is `demo_fixture`.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.award_requirement_proof_audit_persistence_validation_service import (  # noqa: E501
    ADDED_EVENT_TYPES,
    BRIDGED_EVENT_TYPES,
    vocabulary_invariant_failures,
)
from nativeforge.services.award_requirement_proof_audit_repository_service import (
    CONTEXT_COLUMN,
    FORBIDDEN_ANCHOR_NAMES,
    POST_INSERT_WRITABLE_COLUMNS,
    PROOF_EVENTS,
    REPOSITORY_OPERATIONS,
    RLS_ANCHOR_COLUMN,
    ROW_RELATIONSHIP_COLUMN,
    TABLE_NAME,
    prohibited_inferences,
    repository_vocabularies,
)

SCHEMA_VERSION = "nf_award_requirement_proof_audit_persistence_artifact_v1"

ARTIFACT_DIR = "artifacts/award_requirement_proof_audit_persistence"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "proof_audit_repository_available": True,
    "proof_audit_validation_available": True,
    "proof_audit_schema_available": True,
    "proof_audit_operational": False,
    "document_storage_available": False,
    "awarded_operational_tracking_ready": False,
    "customer_auth_live": False,
    "login_live": False,
    "verified_operational_binding": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "audit_record_deleted": False,
    "proof_deleted": False,
    "submission_inferred_from_document": False,
    "acceptance_inferred_from_submission": False,
    "rejection_inferred_from_review_note": False,
    "written_back_to_requirement": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_proof_records_created": 0,
    "production_award_requirements_created": 0,
    "production_awarded_grants_created": 0,
    "real_customer_data_written": 0,
    "rows_deleted": 0,
    "rows_in_the_application_database": 0,
}

# Field names that would mean real award or tenant data had entered an artifact.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "uei",
        "ein",
        "sam_registration_status",
        "physical_address",
        "mailing_address",
        "authorized_representative",
        "finance_contact",
        "email",
        "banking_details",
        "payment_account",
        "drawdown_account",
        "award_amount",
        "client_secret",
        "signing_key",
        "access_token",
        "refresh_token",
    }
)

FORBIDDEN_INFERENCE_FLAGS: frozenset[str] = frozenset(
    {
        "submission_inferred_from_document",
        "acceptance_inferred_from_submission",
        "rejection_inferred_from_review_note",
        "storage_inferred_from_document_reference",
        "written_back_to_requirement",
        "fabricated",
    }
)

# Claims that a record went away. The whole point of this table is that none can.
FORBIDDEN_REMOVAL_FLAGS: frozenset[str] = frozenset(
    {
        "audit_record_deleted",
        "proof_deleted",
    }
)

# Capabilities this gate can state flatly.
FORBIDDEN_CAPABILITY_FLAGS: frozenset[str] = frozenset(
    {
        "document_storage_available",
        "document_storage_live",
        "document_storage_built_by_gate_126",
        "requirement_extraction_live",
        "customer_auth_live",
        "customer_persistence_live",
    }
)

# Measured rather than frozen, for the reason in the module docstring.
MEASURED_CAPABILITY_FLAGS: tuple[str, ...] = (
    "proof_audit_persistence_available",
    "ready_for_operational_awarded_tracking",
)

MATRIX_COLUMNS: tuple[str, ...] = (
    "case",
    "event_type",
    "event_type_is_bridged",
    "event_status",
    "proof_source",
    "document_reference_present",
    "submission_recorded",
    "proof_is_accepted",
    "proof_is_rejected",
    "proof_retained",
    "review_status_consistent",
    "fact_status",
    "facts_established",
    "event_ready_for_audit_trail",
    "human_review_required",
    "unknown_fields",
    "refused_claims",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _measured_capabilities() -> dict[str, bool]:
    """What is actually available right now, for the scan to compare against."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )

    readiness = build_awarded_requirements_readiness()
    return {flag: bool(readiness.get(flag)) for flag in MEASURED_CAPABILITY_FLAGS}


def scan_for_credential_fields(payload: Any) -> list[str]:
    """Which forbidden field names appear anywhere. Names, never values."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_VALUE_FIELDS:
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_claimed_inferences(payload: Any) -> list[str]:
    """Did anything claim an inference this campaign refuses to make?"""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_INFERENCE_FLAGS and bool(value) is True:
                    found.add(f"claimed_inference:{key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_claimed_removals(payload: Any) -> list[str]:
    """Did anything say a record went away?

    This gate's addition. An audit artifact asserting a proof or a record was
    deleted would be a file saying evidence disappeared, and the entire reason
    this table is append-first is that it cannot.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_REMOVAL_FLAGS and bool(value) is True:
                    found.add(f"claimed_removal:{key}")
                if key == "rows_deleted" and value:
                    found.add("claimed_removal:rows_deleted")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_claimed_decisions(payload: Any) -> list[str]:
    """Did anything assert a funder decided what the row does not support?

    Written against dictionaries rather than key/value pairs, for the reason
    Gate 124H recorded: most of these cases exist to show a claim being
    refused, so the check is about the combination rather than either field.

    ```text
    proof_is_accepted  submission_recorded  reference   verdict
    true               true                 present     supported
    true               false                any         refused
    true               any                  absent      refused
    ```
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("proof_is_accepted") is True:
                if node.get("submission_recorded") is False:
                    found.add("claimed_decision:accepted_without_a_submission")
                if node.get("document_reference_present") is False:
                    found.add("claimed_decision:accepted_without_a_reference")
            if node.get("proof_is_rejected") is True:
                if node.get("document_reference_present") is False:
                    found.add("claimed_decision:rejected_without_a_reference")
            if node.get("proof_retained") is False:
                found.add("claimed_decision:a_proof_was_not_retained")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_claimed_capabilities(payload: Any) -> list[str]:
    """Did anything claim a capability that is not actually there?"""
    found: set[str] = set()
    measured = _measured_capabilities()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_CAPABILITY_FLAGS and bool(value) is True:
                    found.add(f"claimed_capability:{key}")
                if key in measured and bool(value) is not measured[key]:
                    found.add(f"capability_claim_disagrees_with_reality:{key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def build_repository_contract() -> dict[str, Any]:
    """What the repository is, measured off the Core table rather than recited."""
    constraints = sorted(
        c.name for c in PROOF_EVENTS.constraints if getattr(c, "name", None)
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0034",
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "row_relationship_column": ROW_RELATIONSHIP_COLUMN,
            "context_column": CONTEXT_COLUMN,
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', true)::uuid "
                "AND is_demo = "
                "current_setting('app.current_org_is_demo', true)::boolean"
            ),
            "operations": sorted(REPOSITORY_OPERATIONS),
            "columns": [c.name for c in PROOF_EVENTS.columns],
            "column_count": len(PROOF_EVENTS.columns),
            "check_constraints": [c for c in constraints if c.startswith("ck_")],
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "post_insert_writable_columns": list(POST_INSERT_WRITABLE_COLUMNS),
            "event_types_bridged_from_gate_108": sorted(BRIDGED_EVENT_TYPES),
            "event_types_added_by_gate_126": sorted(ADDED_EVENT_TYPES),
            "vocabulary_invariant_failures": vocabulary_invariant_failures(),
            "vocabularies": repository_vocabularies(),
            "prohibited_inferences": [
                {"inference": name, "why": why} for name, why in prohibited_inferences()
            ],
            "rules": [
                "organization_id is required and must be UUID-shaped",
                "award_requirement_id is required, is a row relationship, and "
                "is refused as an anchor",
                "awarded_grant_id is context, and is refused as an anchor",
                "tenant_id, customer_org_id and organization_profile_id are "
                "refused as anchors",
                "an event is written once; only superseded_at and archived_at "
                "may be added afterwards, and both are one-way",
                "there is no delete path",
                "a rejection retains the proof reference",
                "a supersession writes a new event and retains the prior one",
                "an archived event stays in the audit trail",
                "a document reference is not a document, and there is no "
                "document store",
                "a submission is not an acceptance, and each has its own timestamp",
                "the requirement's current proof status is derived over the "
                "trail and never written back onto the requirement row",
                "a production write requires customer_auth_live and a verified "
                "operational binding",
            ],
            **FIXED_COUNTS,
        }
    )


def build_validation_cases() -> list[dict[str, Any]]:
    """The cases the matrix reports, each a distinct rule."""
    base: dict[str, Any] = {
        "event_type": "mark_submitted",
        "event_status": "proof_attached",
        "proof_document_ref": "nf-demo-fixture-sf425-2026-q1.pdf",
        "proof_source": "human_entered",
        "submitted_at": "2026-08-30T12:00:00+00:00",
        "fact_status": "demo_fixture",
    }

    return [
        {"case": "demo_fixture_submission", "event": dict(base)},
        {
            "case": "a_valid_acceptance",
            "event": {
                **base,
                "event_type": "mark_accepted",
                "event_status": "proof_accepted",
                "accepted_at": "2026-09-15T12:00:00+00:00",
            },
        },
        {
            "case": "accepted_without_a_submission",
            "event": {
                **base,
                "event_type": "mark_accepted",
                "event_status": "proof_accepted",
                "submitted_at": None,
                "accepted_at": "2026-09-15T12:00:00+00:00",
            },
        },
        {
            "case": "accepted_without_a_reference",
            "event": {
                **base,
                "event_type": "mark_accepted",
                "event_status": "proof_accepted",
                "proof_document_ref": None,
                "accepted_at": "2026-09-15T12:00:00+00:00",
            },
        },
        {
            "case": "a_rejection_retains_its_reference",
            "event": {
                **base,
                "event_type": "mark_rejected",
                "event_status": "proof_rejected",
                "rejected_at": "2026-09-15T12:00:00+00:00",
            },
        },
        {
            "case": "a_rejection_that_discarded_its_reference",
            "event": {
                **base,
                "event_type": "mark_rejected",
                "event_status": "proof_rejected",
                "proof_document_ref": None,
                "rejected_at": "2026-09-15T12:00:00+00:00",
            },
        },
        {
            "case": "a_storage_flag_with_no_store",
            "event": {**base, "proof_document_storage_available": True},
        },
        {
            "case": "an_audit_note_decides_nothing",
            "event": {
                **base,
                "event_type": "audit_note_added",
                "event_status": "not_submitted",
                "proof_document_ref": None,
                "proof_summary": "Demo note.",
            },
        },
        {
            "case": "a_review_needs_both_halves",
            "event": {**base, "reviewed_at": "2026-09-01T12:00:00+00:00"},
        },
        {
            "case": "a_supersede_names_its_predecessor",
            "event": {
                **base,
                "event_type": "proof_superseded",
                "supersedes_event_id": "4d6f80a2-3c5e-4071-ad1f-2e3f4a5b6c7d",
            },
        },
        {
            "case": "a_supersede_without_a_predecessor",
            "event": {**base, "event_type": "proof_superseded"},
        },
        {
            "case": "a_funder_decision_on_unknown_facts",
            "event": {
                **base,
                "event_type": "mark_accepted",
                "event_status": "proof_accepted",
                "accepted_at": "2026-09-15T12:00:00+00:00",
                "fact_status": "unknown",
            },
        },
        {
            "case": "an_unknown_event_type_stays_unknown",
            "event": {**base, "event_type": "unknown"},
        },
        {
            "case": "proof_requested_before_anything_is_filed",
            "event": {
                **base,
                "event_type": "proof_requested",
                "event_status": "not_submitted",
                "proof_document_ref": None,
                "submitted_at": None,
            },
        },
    ]


def render_validation_matrix(matrix: dict[str, Any]) -> str:
    """One row per validation case."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MATRIX_COLUMNS)
    for row in matrix["rows"]:
        writer.writerow(
            [
                row["case"],
                row["event_type"],
                str(row["event_type_is_bridged"]).lower(),
                row["event_status"],
                row["proof_source"],
                str(row["document_reference_present"]).lower(),
                str(row["submission_recorded"]).lower(),
                str(row["proof_is_accepted"]).lower(),
                str(row["proof_is_rejected"]).lower(),
                str(row["proof_retained"]).lower(),
                str(row["review_status_consistent"]).lower(),
                row["fact_status"],
                str(row["facts_established"]).lower(),
                str(row["event_ready_for_audit_trail"]).lower(),
                str(row["human_review_required"]).lower(),
                "; ".join(row["unknown_fields"]),
                "; ".join(row["refused_claims"]),
                "; ".join(row["blocked_reasons"]),
            ]
        )
    return buffer.getvalue()


def build_persistence_declaration() -> dict[str, Any]:
    """What Gate 126 built, and the claims it does not make."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.customer_persistence_spine_decision_service import (
        build_persistence_spine_decision,
    )

    gate = build_customer_auth_activation_gate()
    readiness = build_awarded_requirements_readiness()
    matrix = build_capability_matrix()
    spine = build_persistence_spine_decision()
    lane = next(
        row for row in matrix["rows"] if row["capability"] == "proof_audit_persistence"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proof_audit_write_path_available": bool(lane["write_path_available"]),
            "proof_audit_read_path_available": bool(lane["read_path_available"]),
            "proof_audit_storage_available": bool(
                readiness["proof_audit_storage_available"]
            ),
            "proof_audit_persistence_available": bool(
                readiness["proof_audit_persistence_available"]
            ),
            "awarded_tracking_storage_available": bool(
                readiness["awarded_tracking_storage_available"]
            ),
            "ready_for_operational_awarded_tracking": bool(
                readiness["ready_for_operational_awarded_tracking"]
            ),
            "operational_awarded_recommended": bool(
                spine["operational_awarded_recommended"]
            ),
            "next_gate_recommendation": spine["next_gate_recommendation"][
                "recommendation"
            ],
            "capability_lane_count": len(matrix["rows"]),
            "readiness_blocked_reasons": list(readiness["blocked_reasons"]),
            "lane_blocked_reasons": list(lane["blocked_reasons"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 126 moved, and the sentence to refuse."""
    from nativeforge.services.award_requirement_proof_audit_persistence_demo_fixture_service import (  # noqa: E501
        build_proof_audit_fixture_set,
    )

    fixture = build_proof_audit_fixture_set()
    declaration = build_persistence_declaration()

    lines = [
        "# Proof audit persistence readiness (Gate 126)",
        "",
        "## What moved",
        "",
        "```text",
        f"table                      {TABLE_NAME} (migration 0034)",
        f"columns                    {len(PROOF_EVENTS.columns)}",
        f"repository operations      {len(REPOSITORY_OPERATIONS)}",
        f"capability lanes           {declaration['capability_lane_count']}",
        f"demo fixture cases         {fixture['case_count']}",
        f"storable fixture cases     {fixture['storable_count']}",
        "```",
        "",
        "Gate 108 built the proof/audit contract and had nowhere to put an",
        "event. Gate 124 gave awards a table, Gate 125 gave requirements one,",
        "and this is the third: what was filed, and what happened to it.",
        "",
        "## What did not move",
        "",
        "```text",
        f"proof audit operational           "
        f"{str(declaration['proof_audit_operational']).lower()}",
        f"operational awarded tracking      "
        f"{str(declaration['ready_for_operational_awarded_tracking']).lower()}",
        f"operational awarded recommended   "
        f"{str(declaration['operational_awarded_recommended']).lower()}",
        f"document storage                  "
        f"{str(declaration['document_storage_available']).lower()}",
        f"customer auth live                "
        f"{str(declaration['customer_auth_live']).lower()}",
        f"verified operational binding      "
        f"{str(declaration['verified_operational_binding']).lower()}",
        f"production proof records          "
        f"{declaration['production_proof_records_created']}",
        f"rows deleted                      {declaration['rows_deleted']}",
        "```",
        "",
        "## Why the lane is still not operational",
        "",
    ]
    for reason in declaration["lane_blocked_reasons"]:
        lines.append(f"- `{reason}`")
    lines += [
        "",
        "## What operational tracking still needs",
        "",
    ]
    for reason in declaration["readiness_blocked_reasons"]:
        lines.append(f"- `{reason}`")
    lines += [
        "",
        "## The sentence to refuse",
        "",
        "> NativeForge keeps your compliance evidence.",
        "",
        "It does not. Three tables exist and every production write is refused",
        "because nobody can be authenticated as the tenant a filing would bind",
        "to. `proof_document_ref` names a document and there is no store behind",
        "it, so the evidence itself is still wherever the Tribe put it.",
        "",
        "## What is retained, and why that is the point",
        "",
        "```text",
        "rejected    the proof reference stays on the row",
        "superseded  the prior event stays, and the new one points back",
        "archived    the row stays and leaves the active view",
        "deleted     nothing. There is no delete path",
        "```",
        "",
        "A rejection that erased what was filed would make 'we rejected it'",
        "indistinguishable from 'nothing was ever filed'. A supersession that",
        "replaced the prior row would erase what was believed before the",
        "correction. Both are opposite facts about the same Tribe, and both are",
        "what a funder's auditor asks about.",
        "",
        "## The vocabulary this gate extended",
        "",
        "```text",
        f"bridged from Gate 108   {sorted(BRIDGED_EVENT_TYPES)}",
        f"added by Gate 126       {sorted(ADDED_EVENT_TYPES)}",
        "```",
        "",
        "Gate 108's six actions all still map. An invariant refuses a vocabulary",
        "that has dropped one, so the extension cannot become a replacement.",
        "",
    ]
    return "\n".join(lines)


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.award_requirement_proof_audit_persistence_demo_fixture_service import (  # noqa: E501
        build_proof_audit_fixture_set,
    )
    from nativeforge.services.award_requirement_proof_audit_persistence_validation_service import (  # noqa: E501
        build_validation_matrix,
    )
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    contract = build_repository_contract()
    matrix = build_validation_matrix(cases=build_validation_cases())
    fixture = build_proof_audit_fixture_set()
    declaration = build_persistence_declaration()

    contents = {
        "award_requirement_proof_audit_repository_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "award_requirement_proof_audit_validation_matrix.csv": (
            render_validation_matrix(matrix)
        ),
        "award_requirement_proof_audit_persistence_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "award_requirement_proof_audit_persistence_readiness_summary.md": (
            render_readiness_summary()
        ),
    }

    blob = "".join(contents.values())
    payloads = [contract, matrix, fixture, declaration]

    def scan(fn) -> list[str]:
        return sorted({found for payload in payloads for found in fn(payload)})

    credential_fields = scan(scan_for_credential_fields)
    if credential_fields:
        raise ValueError(
            f"refusing to write: forbidden field names present {credential_fields}"
        )

    claimed_inferences = scan(scan_for_claimed_inferences)
    if claimed_inferences:
        raise ValueError(f"refusing to write: {claimed_inferences}")

    claimed_removals = scan(scan_for_claimed_removals)
    if claimed_removals:
        raise ValueError(f"refusing to write: {claimed_removals}")

    claimed_decisions = scan(scan_for_claimed_decisions)
    if claimed_decisions:
        raise ValueError(f"refusing to write: {claimed_decisions}")

    claimed_capabilities = scan(scan_for_claimed_capabilities)
    if claimed_capabilities:
        raise ValueError(f"refusing to write: {claimed_capabilities}")

    env_secrets = scan_for_secret_values(blob)
    if env_secrets:
        raise ValueError(
            f"refusing to write: configured secret values present {env_secrets}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, text in contents.items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written[name] = str(path)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": str(out_dir),
            "files_written": written,
            "file_count": len(written),
            "declaration": declaration,
            "credential_fields_found": credential_fields,
            "claimed_inferences_found": claimed_inferences,
            "claimed_removals_found": claimed_removals,
            "claimed_decisions_found": claimed_decisions,
            "claimed_capabilities_found": claimed_capabilities,
            "configured_secret_values_found": env_secrets,
        }
    )


def persistence_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What a written artifact set must never be able to claim."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("file_count") != 4:
        fails.append("expected_four_artifacts")

    for field in (
        "credential_fields_found",
        "claimed_inferences_found",
        "claimed_removals_found",
        "claimed_decisions_found",
        "claimed_capabilities_found",
        "configured_secret_values_found",
    ):
        if result.get(field):
            fails.append(f"artifacts_written_with_{field}")

    declaration = dict(result.get("declaration") or {})
    for claim, expected in FIXED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"declaration_missing_claim:{claim}")
        elif bool(declaration[claim]) is not expected:
            fails.append(f"fixed_claim_changed:{claim}")

    for count, expected_count in FIXED_COUNTS.items():
        if declaration.get(count) != expected_count:
            fails.append(f"fixed_count_changed:{count}")

    if not declaration.get("missing_auth_gates"):
        fails.append("declaration_claims_every_activation_gate_is_satisfied")

    if declaration.get("ready_for_operational_awarded_tracking"):
        fails.append("declaration_claims_operational_awarded_tracking")

    if declaration.get("operational_awarded_recommended"):
        fails.append("declaration_recommends_operating_awarded_tracking")

    # The point of Gate 126H: built and unusable, both stated.
    if not declaration.get("proof_audit_storage_available"):
        fails.append("declaration_does_not_report_the_storage_this_gate_built")

    if not declaration.get("proof_audit_persistence_available"):
        fails.append("declaration_does_not_report_proof_audit_persistence")

    if not declaration.get("readiness_blocked_reasons"):
        fails.append("declaration_claims_nothing_blocks_operational_tracking")

    return sorted(set(fails))
