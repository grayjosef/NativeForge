"""Award requirements persistence artifacts (Gate 125H).

Four files describing the repository, what it validates, and what none of it
makes true. Written to `artifacts/award_requirements_persistence/`.

```text
award_requirements_repository_contract.json          operations, columns, rules
award_requirements_validation_matrix.csv             one row per case
award_requirements_persistence_demo_fixtures.json    the fourteen cases
award_requirements_persistence_readiness_summary.md  what remains blocked
```

## Four scans, and the fourth is this gate's

```text
1  by field name     anything named like real award or tenant data
2  by inference      any result claiming an inference this campaign prohibits
3  by promotion      any payload asserting a projection became an obligation
4  by capability     any payload claiming a document store or a proof audit
                     trail, neither of which exists
```

The fourth is new because this gate builds a column that *names* a document and
a vocabulary that *describes* proof actions, without building either store. A
file asserting `document_storage_available` would be read as "the evidence is
filed somewhere" by everything downstream, and the evidence is nowhere.

## A countdown is the dangerous claim

`date_is_calculable` is scanned alongside the obligation flags. A compliance
artifact saying a date is calculable is a artifact saying somebody can be told
"14 days remaining", and the campaign's whole position on estimates is that a
number nobody verified must not appear next to a deadline.

## No real requirement appears

Every organization id and award id is a fixed fixture UUID, every label carries
the `nf-demo-fixture-` prefix, and every fact status is `demo_fixture`.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.award_requirements_persistence_validation_service import (
    PROJECTED_SOURCE,
    SUBMISSION_STATUSES,
    UNSUPPORTED_SOURCE,
)
from nativeforge.services.award_requirements_repository_service import (
    AWARD_REQUIREMENTS,
    DERIVED_ONLY_FIELDS,
    FORBIDDEN_ANCHOR_NAMES,
    REPOSITORY_OPERATIONS,
    RLS_ANCHOR_COLUMN,
    ROW_RELATIONSHIP_COLUMN,
    TABLE_NAME,
    prohibited_inferences,
    repository_vocabularies,
)

SCHEMA_VERSION = "nf_award_requirements_persistence_artifact_v1"

ARTIFACT_DIR = "artifacts/award_requirements_persistence"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "award_requirements_repository_available": True,
    "award_requirements_validation_available": True,
    "award_requirements_schema_available": True,
    "award_requirements_operational": False,
    "awarded_grants_operational_tracking_ready": False,
    "document_storage_available": False,
    "customer_auth_live": False,
    "login_live": False,
    "verified_operational_binding": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "projected_burden_promoted_to_obligation": False,
    "obligation_inferred_from_title": False,
    "due_date_inferred": False,
    "acceptance_inferred_from_submission": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_award_requirements_created": 0,
    "production_proof_records_created": 0,
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
        "obligation_inferred_from_title",
        "due_date_inferred",
        "due_date_inferred_from_recurrence",
        "submission_inferred_from_document",
        "acceptance_inferred_from_submission",
        "projected_burden_promoted",
        "fabricated",
    }
)

# Claims that assert a Tribe owes something, or that somebody can be told how
# many days remain.
FORBIDDEN_PROMOTION_FLAGS: frozenset[str] = frozenset(
    {
        "awarded_grants_operational_tracking_live",
        "production_write_allowed",
    }
)

# Capabilities a file may not claim while they are not actually available.
#
# Gate 125 froze `proof_audit_persistence_available: False` here and in
# FIXED_CLAIMS. Gate 126 built the store, which left this gate's artifacts with
# a choice between telling a stale `false` - one its own invariants could not
# catch, since they compared the declaration against the same frozen constant -
# and refusing to write at all.
#
# A check that agrees with itself is worse than none. So the scan measures: a
# payload may claim a capability exactly when that capability is available, and
# the set below is only the ones this gate can be sure about.
FORBIDDEN_CAPABILITY_FLAGS: frozenset[str] = frozenset(
    {
        "document_storage_available",
        "document_storage_live",
        "requirement_extraction_live",
    }
)

# Measured rather than frozen. Each moves on its own as a store lands.
MEASURED_CAPABILITY_FLAGS: tuple[str, ...] = ("proof_audit_persistence_available",)


def _measured_capabilities() -> dict[str, bool]:
    """What is actually available right now, for the scan to compare against."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )

    readiness = build_awarded_requirements_readiness()
    return {flag: bool(readiness.get(flag)) for flag in MEASURED_CAPABILITY_FLAGS}


MATRIX_COLUMNS: tuple[str, ...] = (
    "case",
    "requirement_title_present",
    "requirement_type",
    "requirement_status",
    "requirement_source",
    "active_obligation",
    "projected_burden",
    "unsupported_requirement",
    "due_date_status",
    "due_date_consistent",
    "date_is_calculable",
    "proof_status",
    "submission_status",
    "document_reference_present",
    "fact_status",
    "facts_established",
    "requirement_ready_for_calendar",
    "human_review_required",
    "unknown_fields",
    "refused_claims",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


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


def scan_for_claimed_obligations(payload: Any) -> list[str]:
    """Did anything assert an obligation the provenance does not support?

    Written against dictionaries rather than key/value pairs for the reason
    Gate 124H recorded: most of these cases exist to show a claim being
    *refused*, so the check is about the pair rather than either field alone.

    ```text
    active_obligation  requirement_source                    verdict
    true               human_entered / evidence_extracted    supported
    true               anything else                         refused
    true               alongside projected_burden true       refused
    ```
    """
    found: set[str] = set()
    capable = set(repository_vocabularies()["active_capable_sources"])

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_PROMOTION_FLAGS and bool(value) is True:
                    found.add(f"claimed_obligation:{key}")
            if node.get("active_obligation") is True:
                source = node.get("requirement_source")
                if source is not None and str(source) not in capable:
                    found.add(f"claimed_obligation:from_source:{source}")
                if node.get("projected_burden") is True:
                    found.add("claimed_obligation:while_projected")
                if node.get("unsupported_requirement") is True:
                    found.add("claimed_obligation:while_unsupported")
            # A countdown on a date nobody verified.
            if node.get("date_is_calculable") is True:
                if node.get("due_date_is_estimate_only") is True:
                    found.add("claimed_countdown:on_an_estimate")
                if node.get("unsupported_requirement") is True:
                    found.add("claimed_countdown:on_an_unreadable_document")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_claimed_capabilities(payload: Any) -> list[str]:
    """Did anything claim a store that is not actually there?

    Two sets, because two questions. `FORBIDDEN_CAPABILITY_FLAGS` are the ones
    this gate can state flatly: there is no document store and no extraction
    pipeline. `MEASURED_CAPABILITY_FLAGS` are compared against what is really
    available, so a claim becomes acceptable the day it becomes true rather
    than the day somebody remembers to edit this file.
    """
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
        c.name for c in AWARD_REQUIREMENTS.constraints if getattr(c, "name", None)
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0033",
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "row_relationship_column": ROW_RELATIONSHIP_COLUMN,
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', true)::uuid "
                "AND is_demo = "
                "current_setting('app.current_org_is_demo', true)::boolean"
            ),
            "operations": sorted(REPOSITORY_OPERATIONS),
            "columns": [c.name for c in AWARD_REQUIREMENTS.columns],
            "column_count": len(AWARD_REQUIREMENTS.columns),
            "check_constraints": [c for c in constraints if c.startswith("ck_")],
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "derived_only_fields": list(DERIVED_ONLY_FIELDS),
            "projected_source": PROJECTED_SOURCE,
            "unsupported_source": UNSUPPORTED_SOURCE,
            "submission_statuses": sorted(SUBMISSION_STATUSES),
            "vocabularies": repository_vocabularies(),
            "prohibited_inferences": [
                {"inference": name, "why": why} for name, why in prohibited_inferences()
            ],
            "rules": [
                "organization_id is required and must be UUID-shaped",
                "awarded_grant_id is required, is a row relationship, and is "
                "refused as an anchor",
                "tenant_id, customer_org_id and organization_profile_id are "
                "refused as anchors",
                "active_obligation, projected_burden and unsupported_requirement "
                "are derived from requirement_source and are never inputs",
                "a projected burden is stored and is never an active obligation",
                "an unsupported document is stored, obliges nobody, and cannot "
                "carry a verified or calculated date",
                "an estimated due date is recorded, reported as estimated, and "
                "never counted down to",
                "nothing derives a due date from a recurrence rule",
                "a document reference is not a document, and there is no "
                "document store",
                "a submission is not an acceptance, and each has its own timestamp",
                "a production write requires customer_auth_live and a verified "
                "operational binding",
                "archive by setting archived_at; there is no delete path",
            ],
            **FIXED_COUNTS,
        }
    )


def build_validation_cases() -> list[dict[str, Any]]:
    """The cases the matrix reports, each a distinct rule."""
    base: dict[str, Any] = {
        "requirement_title": "Quarterly federal financial report (SF-425)",
        "requirement_type": "financial_report",
        "requirement_status": "not_started",
        "requirement_source": "human_entered",
        "requirement_due_date": "2026-04-30",
        "due_date_status": "verified",
        "recurrence_rule": "quarterly",
        "proof_required": True,
        "proof_status": "not_submitted",
        "submission_status": "not_submitted",
        "fact_status": "demo_fixture",
    }

    return [
        {"case": "demo_fixture_requirement", "requirement": dict(base)},
        {
            "case": "requirement_without_a_title",
            "requirement": {**base, "requirement_title": "  "},
        },
        {
            "case": "requirement_type_unknown_stays_unknown",
            "requirement": {**base, "requirement_type": "unknown"},
        },
        {
            "case": "projected_from_nofo_is_not_an_obligation",
            "requirement": {
                **base,
                "requirement_source": "projected_from_nofo",
                "requirement_due_date": None,
                "due_date_status": "unknown",
            },
        },
        {
            "case": "unsupported_document_is_not_an_obligation",
            "requirement": {
                **base,
                "requirement_source": "unsupported_document_type",
            },
        },
        {
            "case": "evidence_extracted_without_a_reference",
            "requirement": {**base, "requirement_source": "evidence_extracted"},
        },
        {
            "case": "evidence_extracted_with_a_reference",
            "requirement": {
                **base,
                "requirement_source": "evidence_extracted",
                "requirement_source_ref": "nf-demo-fixture-award-packet#4.2",
            },
        },
        {
            "case": "estimated_date_is_not_calculable",
            "requirement": {**base, "due_date_status": "estimated"},
        },
        {
            "case": "unknown_due_date_stays_unknown",
            "requirement": {
                **base,
                "requirement_due_date": None,
                "due_date_status": "unknown",
            },
        },
        {
            "case": "calculable_status_without_a_date",
            "requirement": {**base, "requirement_due_date": None},
        },
        {
            "case": "document_reference_without_a_document_store",
            "requirement": {
                **base,
                "proof_document_ref": "nf-demo-fixture-sf425-2026-q1.pdf",
            },
        },
        {
            "case": "proof_accepted_without_a_reference",
            "requirement": {**base, "proof_status": "proof_accepted"},
        },
        {
            "case": "submitted_is_not_accepted",
            "requirement": {
                **base,
                "requirement_status": "submitted",
                "submission_status": "submitted",
                "submitted_at": "2026-04-28T12:00:00+00:00",
                "proof_status": "proof_missing",
            },
        },
        {
            "case": "accepted_without_a_submission",
            "requirement": {
                **base,
                "accepted_at": "2026-05-02T12:00:00+00:00",
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
                str(row["requirement_title_present"]).lower(),
                row["requirement_type"],
                row["requirement_status"],
                row["requirement_source"],
                str(row["active_obligation"]).lower(),
                str(row["projected_burden"]).lower(),
                str(row["unsupported_requirement"]).lower(),
                row["due_date_status"],
                str(row["due_date_consistent"]).lower(),
                str(row["date_is_calculable"]).lower(),
                row["proof_status"],
                row["submission_status"],
                str(row["document_reference_present"]).lower(),
                row["fact_status"],
                str(row["facts_established"]).lower(),
                str(row["requirement_ready_for_calendar"]).lower(),
                str(row["human_review_required"]).lower(),
                "; ".join(row["unknown_fields"]),
                "; ".join(row["refused_claims"]),
                "; ".join(row["blocked_reasons"]),
            ]
        )
    return buffer.getvalue()


def build_persistence_declaration() -> dict[str, Any]:
    """What Gate 125 built, and the claims it does not make."""
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
        row
        for row in matrix["rows"]
        if row["capability"] == "award_requirements_persistence"
    )
    awards_lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "awarded_grants_persistence"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "award_requirements_write_path_available": bool(
                lane["write_path_available"]
            ),
            "award_requirements_read_path_available": bool(lane["read_path_available"]),
            "award_requirements_storage_available": bool(
                readiness["award_requirements_storage_available"]
            ),
            "awarded_grants_write_path_available": bool(
                awards_lane["write_path_available"]
            ),
            "awarded_tracking_storage_available": bool(
                readiness["awarded_tracking_storage_available"]
            ),
            "ready_for_operational_awarded_tracking": bool(
                readiness["ready_for_operational_awarded_tracking"]
            ),
            # Measured, not frozen. Gate 126 built this and the frozen `false`
            # would have gone stale silently.
            "proof_audit_persistence_available": bool(
                readiness["proof_audit_persistence_available"]
            ),
            "operational_awarded_recommended": bool(
                spine["operational_awarded_recommended"]
            ),
            "next_gate_recommendation": spine["next_gate_recommendation"][
                "recommendation"
            ],
            "readiness_blocked_reasons": list(readiness["blocked_reasons"]),
            "lane_blocked_reasons": list(lane["blocked_reasons"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 125 moved, and the sentence to refuse."""
    from nativeforge.services.award_requirements_persistence_demo_fixture_service import (  # noqa: E501
        build_award_requirements_fixture_set,
    )

    fixture = build_award_requirements_fixture_set()
    declaration = build_persistence_declaration()

    lines = [
        "# Award requirements persistence readiness (Gate 125)",
        "",
        "## What moved",
        "",
        "```text",
        f"table                      {TABLE_NAME} (migration 0033)",
        f"columns                    {len(AWARD_REQUIREMENTS.columns)}",
        f"repository operations      {len(REPOSITORY_OPERATIONS)}",
        f"demo fixture cases         {fixture['case_count']}",
        f"storable fixture cases     {fixture['storable_count']}",
        f"cases a calendar could use {fixture['calendarable_count']}",
        "```",
        "",
        "Gate 108 built the requirement model, the calendar and the proof audit",
        "and had nowhere to put a row. Gate 124 gave awards a table. This is the",
        "other half.",
        "",
        "## What did not move",
        "",
        "```text",
        f"award requirements operational    "
        f"{str(declaration['award_requirements_operational']).lower()}",
        f"operational awarded tracking      "
        f"{str(declaration['ready_for_operational_awarded_tracking']).lower()}",
        f"operational awarded recommended   "
        f"{str(declaration['operational_awarded_recommended']).lower()}",
        f"document storage                  "
        f"{str(declaration['document_storage_available']).lower()}",
        f"proof audit persistence           "
        f"{str(declaration['proof_audit_persistence_available']).lower()}",
        "proof audit built by                gate 126",
        f"customer auth live                "
        f"{str(declaration['customer_auth_live']).lower()}",
        f"verified operational binding      "
        f"{str(declaration['verified_operational_binding']).lower()}",
        f"production award requirements     "
        f"{declaration['production_award_requirements_created']}",
        f"production proof records          "
        f"{declaration['production_proof_records_created']}",
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
        "> NativeForge tracks your reporting deadlines.",
        "",
        "It does not. Two tables exist, two repositories address them, and every",
        "production write is refused because nobody can be authenticated as the",
        "tenant a requirement would bind to. A deadline is the half somebody is",
        "actually held to, and the promise that a missed one will be caught",
        "needs a running system with a real award in it.",
        "",
        "## The three boundaries this gate had to preserve",
        "",
        "```text",
        "projected burden   what a NOFO suggests will be required if you win",
        "active obligation  what this award requires, now",
        "unsupported        what a document nobody could read appeared to say",
        "```",
        "",
        "All three derive from `requirement_source` and none is an input. Gate",
        "108 wrote that derivation; this gate persists it and refuses the",
        "contradiction in the database.",
        "",
        f"Fixture cases recording a projection: {fixture['projected_burden_count']}.",
        "Fixture cases that became an obligation: 0.",
        "",
        "## An estimate is not a deadline",
        "",
        "`DATE_CALCULABLE_STATUSES` is `verified` and `calculated`. An estimated",
        "date is stored, shown as estimated, and never counted down to — and",
        "neither is a date claimed by a document nobody could read.",
        "",
        "## A reference is not a document",
        "",
        "`proof_document_ref` holds a reference and there is no store behind it.",
        "`document_storage_available` is false, `proof_audit_persistence_available`",
        "is false, and a reference supplied without a store is refused by name.",
        "",
    ]
    return "\n".join(lines)


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.award_requirements_persistence_demo_fixture_service import (  # noqa: E501
        build_award_requirements_fixture_set,
    )
    from nativeforge.services.award_requirements_persistence_validation_service import (
        build_validation_matrix,
    )
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    contract = build_repository_contract()
    matrix = build_validation_matrix(cases=build_validation_cases())
    fixture = build_award_requirements_fixture_set()
    declaration = build_persistence_declaration()

    contents = {
        "award_requirements_repository_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "award_requirements_validation_matrix.csv": render_validation_matrix(matrix),
        "award_requirements_persistence_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "award_requirements_persistence_readiness_summary.md": (
            render_readiness_summary()
        ),
    }

    blob = "".join(contents.values())
    payloads = [contract, matrix, fixture, declaration]

    credential_fields = sorted(
        {field for payload in payloads for field in scan_for_credential_fields(payload)}
    )
    if credential_fields:
        raise ValueError(
            f"refusing to write: forbidden field names present {credential_fields}"
        )

    claimed_inferences = sorted(
        {
            found
            for payload in payloads
            for found in scan_for_claimed_inferences(payload)
        }
    )
    if claimed_inferences:
        raise ValueError(f"refusing to write: {claimed_inferences}")

    claimed_obligations = sorted(
        {
            found
            for payload in payloads
            for found in scan_for_claimed_obligations(payload)
        }
    )
    if claimed_obligations:
        raise ValueError(f"refusing to write: {claimed_obligations}")

    claimed_capabilities = sorted(
        {
            found
            for payload in payloads
            for found in scan_for_claimed_capabilities(payload)
        }
    )
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
            "claimed_obligations_found": claimed_obligations,
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
        "claimed_obligations_found",
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

    # The point of Gate 125H: built and unusable, both stated.
    if not declaration.get("award_requirements_storage_available"):
        fails.append("declaration_does_not_report_the_storage_this_gate_built")

    if not declaration.get("awarded_tracking_storage_available"):
        fails.append("declaration_does_not_report_both_lanes_built")

    if not declaration.get("readiness_blocked_reasons"):
        fails.append("declaration_claims_nothing_blocks_operational_tracking")

    return sorted(set(fails))
