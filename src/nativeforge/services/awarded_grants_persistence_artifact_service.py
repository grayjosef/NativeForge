"""Awarded grants persistence artifacts (Gate 124H).

Four files describing the repository, what it validates, and what none of it
makes true. Written to `artifacts/awarded_grants_persistence/`.

```text
awarded_grants_repository_contract.json          operations, columns, rules
awarded_grants_validation_matrix.csv             one row per validation case
awarded_grants_persistence_demo_fixtures.json    the eleven cases
awarded_grants_persistence_readiness_summary.md  what remains blocked
```

## Three scans, and the third is this gate's

```text
1  by field name    a nested walk for anything named like real award data
2  by inference     any result claiming an inference this campaign prohibits
3  by promotion     any payload claiming a projected burden became an
                    obligation, or an award was created from lineage
```

The third exists because the danger here is neither a leaked credential nor a
fabricated tenant fact. It is an artifact asserting that a Tribe *owes* somebody
something. A file saying `obligations_established` about an award nobody has
verified is a compliance calendar built on a guess, and it looks exactly as
authoritative as one that is not.

`award_amount` is in the forbidden-field scan for a related reason. A real award
amount is the number an auditor reconciles against, and an artifact is the wrong
place for it — the fixture amounts here are reported as counts and statuses, not
as money.

## No real award appears

Every organization id is a fixed fixture UUID, every label carries the
`nf-demo-fixture-` prefix, and every fact status is `demo_fixture` — which is
deliberately outside `ACTIONABLE_FACT_STATUSES`, so nothing in these files can
establish an obligation even if something read them.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.awarded_grants_persistence_validation_service import (
    ACTIVE_OBLIGATION_STATUSES,
    OBLIGATING_STATUSES,
)
from nativeforge.services.awarded_grants_repository_service import (
    AWARDED_GRANTS,
    FORBIDDEN_ANCHOR_NAMES,
    LINEAGE_FIELDS,
    REPOSITORY_OPERATIONS,
    RLS_ANCHOR_COLUMN,
    TABLE_NAME,
    repository_vocabularies,
)

SCHEMA_VERSION = "nf_awarded_grants_persistence_artifact_v1"

ARTIFACT_DIR = "artifacts/awarded_grants_persistence"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "awarded_grants_repository_available": True,
    "awarded_grants_validation_available": True,
    "awarded_grants_schema_available": True,
    "awarded_grants_lane_operational": False,
    "awarded_grants_operational_tracking_live": False,
    "award_requirements_schema_available": False,
    "customer_auth_live": False,
    "login_live": False,
    "verified_operational_binding": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "projected_burden_promoted_to_obligation": False,
    "award_created_from_pursuit_lineage": False,
    "award_status_inferred_from_pursuit": False,
    "award_amount_inferred": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_awarded_grants_created": 0,
    "production_award_requirements_created": 0,
    "real_customer_data_written": 0,
    "rows_deleted": 0,
    "rows_in_the_application_database": 0,
}

# Field names that would mean real award data had entered an artifact.
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
        # An award amount is the number an auditor reconciles against. Counts
        # and statuses belong in an artifact; money does not.
        "award_amount",
        "client_secret",
        "signing_key",
        "access_token",
        "refresh_token",
    }
)

FORBIDDEN_INFERENCE_FLAGS: frozenset[str] = frozenset(
    {
        "award_status_inferred_from_pursuit",
        "award_amount_inferred",
        "obligations_inferred",
        "award_created_from_lineage",
        "projected_burden_considered",
        "projected_burden_promoted",
        "fabricated",
    }
)

# Claims that assert a Tribe owes somebody something. Scanned separately from
# the inference flags because these are not inferences - they are assertions
# that would be entirely correct on a real, verified award, and entirely wrong
# in a file made of fixtures.
FORBIDDEN_PROMOTION_FLAGS: frozenset[str] = frozenset(
    {
        "obligations_established",
        "award_ready_for_obligation_tracking",
        "awarded_grants_operational_tracking_live",
        "production_write_allowed",
    }
)

MATRIX_COLUMNS: tuple[str, ...] = (
    "case",
    "award_title_present",
    "award_status",
    "award_is_live",
    "active_obligation_status",
    "obligations_claimed",
    "obligations_established",
    "obligation_capable_extraction",
    "fact_status",
    "facts_established",
    "award_amount_known",
    "period_dates_valid",
    "award_ready_for_obligation_tracking",
    "human_review_required",
    "unknown_fields",
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
    """Did anything in these files assert that somebody owes something?

    The check this gate needed. An artifact asserting an established obligation
    reads exactly as authoritative as one that is true, and every award in these
    files is a fixture.

    ``active_obligation_status`` is the awkward one, and the reason this scan is
    written against dictionaries rather than key/value pairs. Most of these
    cases exist to show a claim being *refused*, so a row carrying
    ``obligations_established`` in that column is doing its job - but only while
    the derived answer sits beside it saying no:

    ```text
    active_obligation_status  obligations_established  verdict
    obligations_established   present and False        a refused claim, allowed
    obligations_established   absent, or True          an assertion, refused
    ```

    Gate 121 spent two attempts on the opposite mistake, a leak scanner firing
    on its own intended output. The fix there and here is the same: say exactly
    what makes the output acceptable, rather than dropping the check.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_PROMOTION_FLAGS and bool(value) is True:
                    found.add(f"claimed_obligation:{key}")
            status = node.get("active_obligation_status")
            if status is not None and str(status) in OBLIGATING_STATUSES:
                refused = node.get("obligations_established")
                if refused is None or bool(refused) is True:
                    found.add("claimed_obligation:active_obligation_status")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def build_repository_contract() -> dict[str, Any]:
    """What the repository is, measured off the Core table rather than recited."""
    constraints = sorted(
        c.name for c in AWARDED_GRANTS.constraints if getattr(c, "name", None)
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0032",
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', true)::uuid "
                "AND is_demo = "
                "current_setting('app.current_org_is_demo', true)::boolean"
            ),
            "operations": sorted(REPOSITORY_OPERATIONS),
            "columns": [c.name for c in AWARDED_GRANTS.columns],
            "column_count": len(AWARDED_GRANTS.columns),
            "check_constraints": [c for c in constraints if c.startswith("ck_")],
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "lineage_fields": list(LINEAGE_FIELDS),
            "active_obligation_statuses": sorted(ACTIVE_OBLIGATION_STATUSES),
            "vocabularies": repository_vocabularies(),
            "rules": [
                "organization_id is required and must be UUID-shaped",
                "tenant_id, customer_org_id and organization_profile_id are "
                "refused as anchors",
                "source_pursuit_id and source_opportunity_id are lineage text "
                "with no foreign key, and never a reason to create an award",
                "an awarded grant is never created from a pursuit automatically",
                "active_obligation_status is never derived from a projected burden",
                "obligations_established requires established facts, a capable "
                "extraction and a live award - every conjunct, or False",
                "an unknown award amount stays unknown and is never defaulted to zero",
                "a reversed period is refused, not swapped or clamped",
                "a production write requires customer_auth_live and a verified "
                "operational binding",
                "archive by setting archived_at; there is no delete path, and "
                "mistaken_award is a status rather than a deletion",
            ],
            **FIXED_COUNTS,
        }
    )


def build_validation_cases() -> list[dict[str, Any]]:
    """The cases the matrix reports, each a distinct rule."""
    base: dict[str, Any] = {
        "award_title": "Demo Tribal Housing Infrastructure Award",
        "award_status": "active_award",
        "active_obligation_status": "no_obligations_established",
        "fact_status": "demo_fixture",
        "award_amount": "250000.00",
        "award_currency": "USD",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "requirements_extraction_status": "not_attempted",
    }

    return [
        {"case": "demo_fixture_award", "award": dict(base)},
        {
            "case": "award_without_a_title",
            "award": {**base, "award_title": "  "},
        },
        {
            "case": "award_status_unknown_stays_unknown",
            "award": {**base, "award_status": "unknown"},
        },
        {
            "case": "unknown_amount_on_an_unestablished_fact",
            "award": {**base, "award_amount": None, "award_currency": None},
        },
        {
            "case": "amount_without_a_currency",
            "award": {**base, "award_currency": None},
        },
        {
            "case": "reversed_period",
            "award": {
                **base,
                "period_start": "2026-12-31",
                "period_end": "2026-01-01",
            },
        },
        {
            "case": "obligation_claimed_on_a_fixture",
            "award": {
                **base,
                "active_obligation_status": "obligations_established",
            },
        },
        {
            "case": "obligation_claimed_without_a_capable_extraction",
            "award": {
                **base,
                "active_obligation_status": "obligations_established",
                "fact_status": "verified",
                "requirements_extraction_status": "not_attempted",
            },
        },
        {
            "case": "obligation_claimed_on_a_closed_award",
            "award": {
                **base,
                "award_status": "closed",
                "active_obligation_status": "obligations_established",
                "fact_status": "verified",
                "requirements_extraction_status": "human_entered",
            },
        },
        {
            "case": "lineage_recorded_and_not_acted_on",
            "award": {
                **base,
                "source_pursuit_id": "nf-demo-fixture-pursuit-1",
                "source_opportunity_id": "nf-demo-fixture-opportunity-1",
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
                str(row["award_title_present"]).lower(),
                row["award_status"],
                str(row["award_is_live"]).lower(),
                row["active_obligation_status"],
                str(row["obligations_claimed"]).lower(),
                str(row["obligations_established"]).lower(),
                str(row["obligation_capable_extraction"]).lower(),
                row["fact_status"],
                str(row["facts_established"]).lower(),
                str(row["award_amount_known"]).lower(),
                str(row["period_dates_valid"]).lower(),
                str(row["award_ready_for_obligation_tracking"]).lower(),
                str(row["human_review_required"]).lower(),
                "; ".join(row["unknown_fields"]),
                "; ".join(row["blocked_reasons"]),
            ]
        )
    return buffer.getvalue()


def build_persistence_declaration() -> dict[str, Any]:
    """What Gate 124 built, and the claims it does not make."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )

    gate = build_customer_auth_activation_gate()
    readiness = build_awarded_requirements_readiness()
    matrix = build_capability_matrix()
    lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "awarded_grants_persistence"
    )
    requirements_lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "award_requirements_persistence"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "awarded_grants_write_path_available": bool(lane["write_path_available"]),
            "awarded_grants_read_path_available": bool(lane["read_path_available"]),
            "awarded_grants_storage_available": bool(
                readiness["awarded_grants_storage_available"]
            ),
            "award_requirements_write_path_available": bool(
                requirements_lane["write_path_available"]
            ),
            "ready_for_operational_awarded_tracking": bool(
                readiness["ready_for_operational_awarded_tracking"]
            ),
            "readiness_blocked_reasons": list(readiness["blocked_reasons"]),
            "lane_blocked_reasons": list(lane["blocked_reasons"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 124 moved, and the sentence to refuse."""
    from nativeforge.services.awarded_grants_persistence_demo_fixture_service import (
        build_awarded_grants_fixture_set,
    )

    fixture = build_awarded_grants_fixture_set()
    declaration = build_persistence_declaration()

    lines = [
        "# Awarded grants persistence readiness (Gate 124)",
        "",
        "## What moved",
        "",
        "```text",
        f"table                      {TABLE_NAME} (migration 0032)",
        f"columns                    {len(AWARDED_GRANTS.columns)}",
        f"repository operations      {len(REPOSITORY_OPERATIONS)}",
        f"demo fixture cases         {fixture['case_count']}",
        f"storable fixture cases     {fixture['storable_count']}",
        "```",
        "",
        "Nine award services and roughly 3,800 lines of contract had nowhere to",
        "put a row. They have one now.",
        "",
        "## What did not move",
        "",
        "```text",
        f"awarded grants lane operational   "
        f"{str(declaration['awarded_grants_lane_operational']).lower()}",
        f"operational awarded tracking      "
        f"{str(declaration['ready_for_operational_awarded_tracking']).lower()}",
        f"customer auth live                "
        f"{str(declaration['customer_auth_live']).lower()}",
        f"verified operational binding      "
        f"{str(declaration['verified_operational_binding']).lower()}",
        f"award requirements write path     "
        f"{str(declaration['award_requirements_write_path_available']).lower()}",
        f"production awarded grants created "
        f"{declaration['production_awarded_grants_created']}",
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
        "> NativeForge tracks your awarded grants.",
        "",
        "It does not. A table exists, a repository addresses it, and every",
        "production write is refused because nobody can be authenticated as the",
        "tenant an award would bind to. An award is a real obligation to a real",
        "funder; the gap between storing one and tracking one is a promise that",
        "a missed deadline will be caught, and nothing here makes that promise.",
        "",
        "## The separation this gate had to preserve",
        "",
        "```text",
        "projected burden   what a NOFO suggests will be required if you win",
        "active obligation  what this award requires, now",
        "```",
        "",
        "Gate 91 stamped every projection `is_active_obligation: False`. Gate",
        "124 keeps `active_obligation_status` in its own column, derives it from",
        "this award's own extraction status, and establishes it only when the",
        "claim, established facts, a capable extraction and a live award all",
        f"hold. Fixture cases establishing an obligation: "
        f"{fixture['obligations_established_count']}.",
        "",
    ]
    return "\n".join(lines)


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.awarded_grants_persistence_demo_fixture_service import (
        build_awarded_grants_fixture_set,
    )
    from nativeforge.services.awarded_grants_persistence_validation_service import (
        build_validation_matrix,
    )
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    contract = build_repository_contract()
    matrix = build_validation_matrix(cases=build_validation_cases())
    fixture = build_awarded_grants_fixture_set()
    declaration = build_persistence_declaration()

    contents = {
        "awarded_grants_repository_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "awarded_grants_validation_matrix.csv": render_validation_matrix(matrix),
        "awarded_grants_persistence_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "awarded_grants_persistence_readiness_summary.md": (render_readiness_summary()),
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

    # The whole point of Gate 124H: built and unusable, both stated.
    if not declaration.get("awarded_grants_storage_available"):
        fails.append("declaration_does_not_report_the_storage_this_gate_built")

    if not declaration.get("readiness_blocked_reasons"):
        fails.append("declaration_claims_nothing_blocks_operational_tracking")

    return sorted(set(fails))
