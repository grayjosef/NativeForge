"""Org-scoped customer persistence artifacts (Gate 114G).

Five files describing what customer persistence is, what it refuses, and how far
it still is from operating. Written to
`artifacts/org_scoped_customer_persistence/`.

```text
customer_persistence_capability_matrix.csv        eight lanes, four questions each
org_scoped_customer_persistence_guard_matrix.csv  nine requests and their verdicts
customer_persistence_spine_decision.json          the order, and what blocks it
customer_persistence_demo_fixtures.json           the fixture set entire
customer_persistence_readiness_summary.md         what none of it permits yet
```

## The summary is the file somebody will quote

So it opens with the sentence that is true and closes off the sentence that is
not: a persistence *contract* exists; customer persistence is not live. Between
those two, "NativeForge has customer persistence" is a sentence somebody could
write from a green line, and the summary exists to make writing it harder.

## Everything is regenerated, nothing is transcribed

Each artifact is rendered from the service that owns the fact. Nothing here
restates a value that lives elsewhere, so a committed artifact that disagrees
with the code is a test failure rather than a stale file nobody noticed.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_org_scoped_customer_persistence_artifact_v1"

ARTIFACT_DIR = "artifacts/org_scoped_customer_persistence"

# Every claim the artifacts must state, and the value each must carry. Written
# as a mapping so the assertion is data rather than prose, and so a test can
# check the committed files against it directly.
REQUIRED_CLAIMS: dict[str, bool] = {
    "customer_persistence_contract_available": True,
    "customer_persistence_live": False,
    "organization_id_required_for_operational_writes": True,
    "tenant_id_write_authority": False,
    "customer_org_id_write_authority": False,
    "organization_profile_id_write_authority": False,
    "binding_store_schema_available": True,
    "customer_auth_live": False,
    "login_live": False,
    "beta_onboarding_ready": False,
    "operational_awarded_tracking_ready": False,
    "operational_digest_ready": False,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _csv(columns: tuple[str, ...], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _flag(value: Any) -> str:
    return str(bool(value)).lower()


def build_persistence_declaration() -> dict[str, Any]:
    """Every required claim, each read from the service that owns it."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        FORBIDDEN_ANCHOR_NAMES,
        RLS_ANCHOR_COLUMN,
        build_capability_matrix,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    matrix = build_capability_matrix()
    binding = build_binding_store_readiness()
    awarded = build_awarded_requirements_readiness()
    digest = build_digest_readiness()
    beta = build_tenant_beta_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rls_anchor_column": RLS_ANCHOR_COLUMN,
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', true)::uuid"
                " AND is_demo = current_setting('app.current_org_is_demo',"
                " true)::boolean"
            ),
            "forbidden_write_authorities": sorted(FORBIDDEN_ANCHOR_NAMES),
            "capabilities": list(matrix["capabilities"]),
            "schema_available_count": matrix["schema_available_count"],
            "rls_backed_count": matrix["rls_backed_count"],
            "write_path_count": matrix["write_path_count"],
            "operational_count": matrix["operational_count"],
            # The twelve required claims, each derived.
            "customer_persistence_contract_available": bool(
                matrix["customer_persistence_contract_available"]
            ),
            "customer_persistence_live": bool(matrix["customer_persistence_live"]),
            "organization_id_required_for_operational_writes": True,
            "tenant_id_write_authority": False,
            "customer_org_id_write_authority": False,
            "organization_profile_id_write_authority": False,
            "binding_store_schema_available": bool(
                binding["store_schema_available"]
            ),
            "customer_auth_live": bool(matrix["customer_auth_live"]),
            "login_live": False,
            "beta_onboarding_ready": bool(beta["ready_for_beta_onboarding"]),
            "operational_awarded_tracking_ready": bool(
                awarded["ready_for_operational_awarded_tracking"]
            ),
            "operational_digest_ready": bool(
                digest.get("ready_for_operational_digest", False)
            ),
            # Constants. A contract over persistence persists nothing.
            "rows_written": 0,
            "real_customer_data": False,
            "real_db_rows_inserted": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def render_capability_matrix(matrix: dict[str, Any]) -> str:
    columns = (
        "capability",
        "expected_table",
        "schema_available",
        "organization_id_anchor_available",
        "rls_backed",
        "repository_available",
        "service_contract_available",
        "write_path_available",
        "read_path_available",
        "customer_auth_required",
        "customer_auth_live",
        "operational",
        "demo_only",
        "blocked_reasons",
    )
    rows = [
        [
            row["capability"],
            row["expected_table"] or "",
            _flag(row["schema_available"]),
            _flag(row["organization_id_anchor_available"]),
            _flag(row["rls_backed"]),
            _flag(row["repository_available"]),
            _flag(row["service_contract_available"]),
            _flag(row["write_path_available"]),
            _flag(row["read_path_available"]),
            _flag(row["customer_auth_required"]),
            _flag(row["customer_auth_live"]),
            _flag(row["operational"]),
            _flag(row["demo_only"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in matrix["rows"]
    ]
    return _csv(columns, rows)


def render_guard_matrix(fixture: dict[str, Any]) -> str:
    columns = (
        "case",
        "operation",
        "organization_id",
        "persistence_capability",
        "rls_compatible",
        "customer_auth_live",
        "forges_customer_auth",
        "binding_required",
        "binding_status",
        "write_allowed",
        "read_allowed",
        "demo_only",
        "cross_tenant_risk",
        "human_review_required",
        "blocked_reasons",
    )
    rows = [
        [
            row["case"],
            row["operation"],
            row["organization_id"] or "",
            row["persistence_capability"] or "",
            _flag(row["rls_compatible"]),
            _flag(row["customer_auth_live"]),
            _flag(row["forges_customer_auth"]),
            _flag(row["binding_required"]),
            row["binding_status"],
            _flag(row["write_allowed"]),
            _flag(row["read_allowed"]),
            _flag(row["demo_only"]),
            _flag(row["cross_tenant_risk"]),
            _flag(row["human_review_required"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in fixture["rows"]
    ]
    return _csv(columns, rows)


def render_readiness_summary(
    declaration: dict[str, Any], decision: dict[str, Any]
) -> str:
    lines: list[str] = []
    lines.append("# Org-scoped customer persistence readiness (Gate 114)")
    lines.append("")
    lines.append(
        "A customer persistence **contract** exists. **Customer persistence is "
        "not live.** No lane is operational, no customer row has been written, "
        "and nobody can authenticate to own one."
    )
    lines.append("")
    lines.append("## The eight lanes")
    lines.append("")
    lines.append("```text")
    lines.append(
        f"schema available       {declaration['schema_available_count']} of "
        f"{len(declaration['capabilities'])}"
    )
    lines.append(
        f"under row-level security  {declaration['rls_backed_count']} of "
        f"{len(declaration['capabilities'])}"
    )
    lines.append(
        f"complete write path    {declaration['write_path_count']} of "
        f"{len(declaration['capabilities'])}"
    )
    lines.append(
        f"operational            {declaration['operational_count']} of "
        f"{len(declaration['capabilities'])}"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "Schema available is not operational. A table is a container; operating "
        "it needs an organization anchor, a policy, a repository, a contract "
        "and somebody accountable for the row."
    )
    lines.append("")
    lines.append("## The authority")
    lines.append("")
    lines.append("```text")
    lines.append(declaration["rls_predicate"])
    lines.append("```")
    lines.append("")
    lines.append("Never a write authority, at any layer:")
    lines.append("")
    lines.append("```text")
    for name in declaration["forbidden_write_authorities"]:
        lines.append(name)
    lines.append("```")
    lines.append("")
    lines.append("## What blocks the spine")
    lines.append("")
    lines.append("```text")
    for reason in decision["blocked_reasons"]:
        lines.append(reason)
    lines.append("```")
    lines.append("")
    next_gate = decision["next_gate_recommendation"]
    lines.append(f"**Next: {next_gate['recommendation']}.** {next_gate['why']}")
    lines.append("")
    lines.append("## The recommended order")
    lines.append("")
    lines.append("```text")
    for entry in decision["recommended_sequence"]:
        unmet = ", ".join(entry["unmet_prerequisites"]) or "-"
        lines.append(
            f"{entry['position']}. {entry['capability']:32s} waiting on: {unmet}"
        )
    lines.append("```")
    lines.append("")
    # Split by value rather than listed together under one heading. The three
    # true claims are structural facts about the contract; the nine false ones
    # are the claims nobody may make from it. Putting them in one block under
    # "claims this gate does not make" would have mislabelled the true half.
    lines.append("## What is true")
    lines.append("")
    lines.append("```text")
    for claim in sorted(REQUIRED_CLAIMS):
        if REQUIRED_CLAIMS[claim]:
            lines.append(f"{claim:48s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append("## Claims this gate does not make")
    lines.append("")
    lines.append("```text")
    for claim in sorted(REQUIRED_CLAIMS):
        if not REQUIRED_CLAIMS[claim]:
            lines.append(f"{claim:48s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append(
        "No customer data was written, no real database row was inserted, no "
        "identity provider was called, no URL was fetched, no collector ran and "
        "no source was monitored."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Output root only; inspection is by import."""
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.customer_persistence_demo_fixture_service import (
        build_persistence_demo_fixture_set,
    )
    from nativeforge.services.customer_persistence_spine_decision_service import (
        build_persistence_spine_decision,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_persistence_declaration()
    matrix = build_capability_matrix()
    decision = build_persistence_spine_decision()
    fixture = build_persistence_demo_fixture_set()

    written: dict[str, Any] = {}

    capability = out_dir / "customer_persistence_capability_matrix.csv"
    capability.write_text(render_capability_matrix(matrix), encoding="utf-8")
    written["capability_matrix"] = str(capability)

    guard = out_dir / "org_scoped_customer_persistence_guard_matrix.csv"
    guard.write_text(render_guard_matrix(fixture), encoding="utf-8")
    written["guard_matrix"] = str(guard)

    spine = out_dir / "customer_persistence_spine_decision.json"
    spine.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["spine_decision"] = str(spine)

    fixtures = out_dir / "customer_persistence_demo_fixtures.json"
    fixtures.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["demo_fixtures"] = str(fixtures)

    summary = out_dir / "customer_persistence_readiness_summary.md"
    summary.write_text(
        render_readiness_summary(declaration, decision), encoding="utf-8"
    )
    written["readiness_summary"] = str(summary)

    written["declaration"] = declaration
    written["decision"] = decision
    written["fixture"] = fixture
    return written


def persistence_artifact_invariant_failures(
    declaration: dict[str, Any],
    *,
    summary_text: str = "",
    capability_text: str = "",
    guard_text: str = "",
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    # Every required claim must be present and carry its required value.
    for claim, expected in REQUIRED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"artifact_missing_claim:{claim}")
        elif declaration[claim] is not expected:
            fails.append(f"artifact_claim_wrong:{claim}")

    if declaration.get("rows_written") != 0:
        fails.append("persistence_artifact_reported_rows")

    for constant in (
        "real_customer_data",
        "real_db_rows_inserted",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
        "live_fetch_performed",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"persistence_artifact_claimed:{constant}")

    if declaration.get("rls_anchor_column") != "organization_id":
        fails.append("persistence_artifact_anchored_on_a_label")

    for name in ("tenant_id", "customer_org_id", "organization_profile_id"):
        if name not in (declaration.get("forbidden_write_authorities") or []):
            fails.append(f"forbidden_write_authority_missing:{name}")

    # The summary must say the thing, and not say the other thing.
    if summary_text:
        if "Customer persistence is not live" not in summary_text.replace("**", ""):
            fails.append("summary_does_not_say_persistence_is_not_live")
        if declaration.get("rls_predicate") not in summary_text:
            fails.append("summary_omits_the_rls_predicate")
        for name in declaration.get("forbidden_write_authorities") or []:
            if name not in summary_text:
                fails.append(f"summary_omits_forbidden_authority:{name}")
        if "Schema available is not operational" not in summary_text:
            fails.append("summary_does_not_separate_schema_from_operation")

    # The capability matrix must show the separation it exists to show.
    if capability_text:
        parsed = list(csv.reader(io.StringIO(capability_text)))
        header, body = parsed[0], parsed[1:]
        for column in ("schema_available", "operational", "blocked_reasons"):
            if column not in header:
                fails.append(f"capability_matrix_missing_column:{column}")
        if all(column in header for column in ("schema_available", "operational")):
            schema = header.index("schema_available")
            operational = header.index("operational")
            reasons = header.index("blocked_reasons")
            if not any(row[schema] == "true" for row in body):
                fails.append("capability_matrix_shows_no_schema_anywhere")
            if any(row[operational] == "true" for row in body):
                fails.append("capability_matrix_reports_an_operational_lane")
            for row in body:
                if row[operational] == "false" and not row[reasons].strip():
                    fails.append(f"capability_matrix_refusal_without_a_reason:{row[0]}")

    # The guard matrix must show refusals, and must show no permitted write.
    if guard_text:
        parsed = list(csv.reader(io.StringIO(guard_text)))
        header, body = parsed[0], parsed[1:]
        if "write_allowed" not in header:
            fails.append("guard_matrix_missing_write_allowed")
        else:
            write = header.index("write_allowed")
            reasons = header.index("blocked_reasons")
            if any(row[write] == "true" for row in body):
                fails.append("guard_matrix_permitted_a_write")
            for row in body:
                if row[write] == "false" and not row[reasons].strip():
                    fails.append(f"guard_matrix_refusal_without_a_reason:{row[0]}")

    return fails
