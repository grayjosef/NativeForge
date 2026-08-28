"""Tenant beta contract artifacts (Gate 103H).

Six files under `artifacts/tenant_beta_feature_contract/` describing the tenant
beta contract, the four demo tenants, source priority, and the allowability
review.

## Seven declarations, on every file and every CSV row

```text
tenant_beta_contract_available    true
ready_for_demo_contract           true
ready_for_beta_onboarding         false
live_source_collection_available  false
email_delivery_available          false
source_monitoring_live            false
live_source_coverage              false
```

The first two are true and both are narrow. `ready_for_demo_contract` means the
**contract demo against demo-safe fixtures** — the scope is in the field name so
it cannot be quoted as "the demo is ready" without the qualifier.

## The source priority matrix is per tier, not per source

Four tenants against 360 in-scope sources would be 1,440 rows of mostly
identical content. The matrix is tenant × priority tier, which is 20 rows and
says the thing that matters: *this tenant gets 57 SC sources first, that one gets
none, and every tier has zero active collectors.*

The full per-source ranking stays available from the service; it does not belong
in a committed file that a person is meant to read.

## No real Tribe is named

The demo profiles artifact carries generic identities only. The writer refuses to
emit a bundle whose fixtures name a real Tribe, checked against the same token
list the fixture service uses.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.software_capacity_allowability_review_service import (
    AFFIRMATIVE_LABELS,
    ALLOWABILITY_LABELS,
    COST_TYPES,
    PERMITTED_PHRASING,
    PROHIBITED_CLAIMS,
    SELF_ASSESSMENT_CAP,
    SOURCE_CLASS_TO_REVIEW_LABEL,
    allowability_review_invariant_failures,
    build_allowability_review,
)
from nativeforge.services.tenant_beta_demo_fixture_service import (
    DEMO_TENANT_COUNT,
    build_demo_tenant_fixture_set,
    demo_fixture_invariant_failures,
)
from nativeforge.services.tenant_beta_feature_entitlement_service import (
    BETA_FEATURES,
    build_tenant_feature_entitlement,
    entitlement_invariant_failures,
)
from nativeforge.services.tenant_beta_profile_service import (
    FACT_STATUSES,
    RECOGNITION_STATUSES,
)
from nativeforge.services.tenant_beta_readiness_service import (
    DEMO_SCOPE,
    build_tenant_beta_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.tenant_source_priority_service import (
    PRIORITY_TIERS,
    build_tenant_source_priority,
    source_priority_invariant_failures,
)

SCHEMA_VERSION = "nf_tenant_beta_contract_artifact_v1"

ARTIFACT_DIR = "artifacts/tenant_beta_feature_contract"

CONTRACT_JSON_NAME = "tenant_beta_feature_contract.json"
FEATURE_CSV_NAME = "tenant_beta_feature_matrix.csv"
SOURCE_CSV_NAME = "tenant_source_priority_matrix.csv"
PROFILES_JSON_NAME = "tenant_beta_demo_profiles.json"
ALLOWABILITY_JSON_NAME = "software_capacity_allowability_contract.json"
SUMMARY_NAME = "tenant_beta_readiness_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    CONTRACT_JSON_NAME,
    FEATURE_CSV_NAME,
    SOURCE_CSV_NAME,
    PROFILES_JSON_NAME,
    ALLOWABILITY_JSON_NAME,
    SUMMARY_NAME,
)

DECLARATION_KEYS: tuple[str, ...] = (
    "tenant_beta_contract_available",
    "ready_for_demo_contract",
    "ready_for_beta_onboarding",
    "live_source_collection_available",
    "email_delivery_available",
    "source_monitoring_live",
    "live_source_coverage",
)

FALSE_DECLARATION_KEYS: tuple[str, ...] = (
    "ready_for_beta_onboarding",
    "live_source_collection_available",
    "email_delivery_available",
    "source_monitoring_live",
    "live_source_coverage",
)

FEATURE_CSV_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "feature",
    "enabled",
    "implemented",
    "configuration_required",
    *DECLARATION_KEYS,
)

SOURCE_CSV_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "priority_tier",
    "source_count",
    "sources_active",
    "sources_monitored",
    *DECLARATION_KEYS,
)


class TenantBetaArtifactError(RuntimeError):
    """Raised rather than write an artifact whose declarations are wrong."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _rows_to_csv(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buffer.getvalue()


def build_allowability_contract_shape() -> dict[str, Any]:
    """The review contract's rules, plus worked examples including the cap."""
    with_evidence = build_allowability_review(
        opportunity_id="example-opportunity",
        assessed_cost_type="grant_administration",
        evidence_quotes=["Allowable costs include grant administration."],
        proposed_label="clearly_allowable",
    )
    self_assessed = build_allowability_review(
        opportunity_id="example-opportunity",
        assessed_cost_type="software_license",
        evidence_quotes=["Allowable costs include grant management software."],
        proposed_label="clearly_allowable",
        is_nativeforge_itself=True,
    )
    without_evidence = build_allowability_review(
        opportunity_id="example-opportunity",
        assessed_cost_type="capacity_development",
        proposed_label="likely_allowable",
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "labels": sorted(ALLOWABILITY_LABELS),
            "affirmative_labels": sorted(AFFIRMATIVE_LABELS),
            "cost_types": sorted(COST_TYPES),
            "permitted_phrasing": dict(PERMITTED_PHRASING),
            "prohibited_claims": list(PROHIBITED_CLAIMS),
            "source_class_bridge": dict(SOURCE_CLASS_TO_REVIEW_LABEL),
            "self_assessment_cap": SELF_ASSESSMENT_CAP,
            "evidence_required_for_affirmative_labels": True,
            "example_only": True,
            "examples": {
                "with_evidence": with_evidence,
                "nativeforge_self_assessed": self_assessed,
                "without_evidence": without_evidence,
            },
            "fabricated": False,
        }
    )


def build_tenant_beta_bundle(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Everything the six artifacts are rendered from."""
    fixtures = build_demo_tenant_fixture_set()
    profiles = fixtures["tenant_profiles"]
    readiness = build_tenant_beta_readiness()
    allowability = build_allowability_contract_shape()

    entitlements = [
        build_tenant_feature_entitlement(tenant_id=p["tenant_id"], profile=p)
        for p in profiles
    ]
    priorities = [
        build_tenant_source_priority(
            tenant_id=p["tenant_id"], profile=p, repo_root=repo_root
        )
        for p in profiles
    ]

    # Validate the priority results *before* their rows are stripped for the
    # summary. Checking them afterwards would fail on the missing rows and tell
    # us nothing, which is why this runs here rather than in
    # `artifact_claim_failures`.
    priority_failures = [
        f"priority_invariant:{p['tenant_id']}:{failure}"
        for p in priorities
        for failure in source_priority_invariant_failures(p)
    ]

    declarations = {
        "tenant_beta_contract_available": bool(
            readiness["tenant_beta_contract_available"]
        ),
        "ready_for_demo_contract": bool(readiness["ready_for_demo"]),
        "ready_for_beta_onboarding": bool(readiness["ready_for_beta_onboarding"]),
        "live_source_collection_available": bool(
            readiness["live_source_collection_available"]
        ),
        "email_delivery_available": bool(readiness["email_delivery_available"]),
        "source_monitoring_live": bool(readiness["source_monitoring_live"]),
        "live_source_coverage": bool(readiness["live_source_coverage"]),
    }

    feature_rows = []
    for entitlement in entitlements:
        enabled = set(entitlement["enabled_features"])
        config = {c["feature"] for c in entitlement["configuration_required"]}
        for feature in BETA_FEATURES:
            feature_rows.append(
                {
                    "tenant_id": entitlement["tenant_id"],
                    "feature": feature,
                    "enabled": feature in enabled,
                    "implemented": bool(
                        entitlement["feature_implementation"].get(feature)
                    ),
                    "configuration_required": feature in config,
                    **declarations,
                }
            )

    source_rows = []
    for priority in priorities:
        counts = {tier: 0 for tier in PRIORITY_TIERS}
        for row in priority["source_priority_rows"]:
            counts[row["priority_tier"]] += 1
        for tier in PRIORITY_TIERS:
            source_rows.append(
                {
                    "tenant_id": priority["tenant_id"],
                    "priority_tier": tier,
                    "source_count": counts[tier],
                    "sources_active": 0,
                    "sources_monitored": 0,
                    **declarations,
                }
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures": fixtures,
            "readiness": readiness,
            "allowability": allowability,
            "entitlements": entitlements,
            # Priority summaries only - the per-source rows are 1,440 lines of
            # mostly identical content and belong in the service, not a file.
            "priority_summaries": [
                {
                    k: v
                    for k, v in priority.items()
                    if k != "source_priority_rows"
                }
                for priority in priorities
            ],
            "feature_rows": feature_rows,
            "source_rows": source_rows,
            "priority_invariant_failures": priority_failures,
            "declarations": declarations,
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    fails: list[str] = []

    readiness = bundle.get("readiness") or {}
    fixtures = bundle.get("fixtures") or {}
    allowability = bundle.get("allowability") or {}
    declarations = bundle.get("declarations") or {}

    fails.extend(
        f"readiness_invariant:{f}" for f in readiness_invariant_failures(readiness)
    )
    fails.extend(
        f"fixture_invariant:{f}" for f in demo_fixture_invariant_failures(fixtures)
    )
    for entitlement in bundle.get("entitlements") or []:
        fails.extend(
            f"entitlement_invariant:{f}"
            for f in entitlement_invariant_failures(entitlement)
        )
    # Computed in the bundle, where the priority rows still existed.
    fails.extend(bundle.get("priority_invariant_failures") or [])
    for example in (allowability.get("examples") or {}).values():
        fails.extend(
            f"allowability_invariant:{f}"
            for f in allowability_review_invariant_failures(example)
        )

    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")
    for key in FALSE_DECLARATION_KEYS:
        if declarations.get(key) is not False:
            fails.append(f"declaration_not_false:{key}")

    # The self-assessment cap must survive into the artifact.
    self_example = (allowability.get("examples") or {}).get("nativeforge_self_assessed")
    if not self_example:
        fails.append("allowability_contract_missing_the_self_assessed_example")
    elif self_example.get("allowability_label") != SELF_ASSESSMENT_CAP:
        fails.append("self_assessed_example_escaped_the_cap")

    # No real Tribe may be named anywhere.
    if fixtures.get("real_tribe_named"):
        fails.append("fixture_named_a_real_tribe")
    if fixtures.get("facts_verified_count"):
        fails.append("fixture_reported_a_verified_fact")
    if fixtures.get("tenant_count") != DEMO_TENANT_COUNT:
        fails.append("expected_four_demo_tenants")

    # Demo readiness must carry its scope.
    if declarations.get("ready_for_demo_contract") and readiness.get(
        "demo_scope"
    ) != DEMO_SCOPE:
        fails.append("demo_readiness_without_its_scope")

    # No secret, and no prohibited allowability claim, in any rendered body.
    rendered = json.dumps(bundle, sort_keys=True).lower() + summary_text.lower()
    for marker in ("-----begin", "postgresql://", "bearer ", "api_key=", "password="):
        if marker in rendered:
            fails.append(f"artifact_carries_a_secret_marker:{marker.strip()}")

    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")

    return sorted(set(fails))


def render_summary(bundle: dict[str, Any]) -> str:
    declarations = bundle["declarations"]
    readiness = bundle["readiness"]
    fixtures = bundle["fixtures"]

    lines: list[str] = []
    lines.append("# Tenant beta readiness")
    lines.append("")
    lines.append(
        "Generated by `tenant_beta_contract_artifact_service`. No collector "
        "ran, no source was checked, no message was sent, and no tenant fact "
        "was invented."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        lines.append(f"{key:<36}{str(declarations[key]).lower()}")
    lines.append(f"{'demo_scope':<36}{readiness['demo_scope']}")
    lines.append("```")
    lines.append("")
    lines.append(
        "`ready_for_demo_contract` is true and narrow: it means the **contract "
        "demo against demo-safe fixtures**. It is not a claim that live "
        "matching, live digests, or real tenant data work, because none of "
        "those exists."
    )
    lines.append("")
    lines.append("## What is missing before a tenant could be onboarded")
    lines.append("")
    for key in readiness["onboarding_components_missing"]:
        lines.append(f"- `{key}`")
    lines.append("")
    lines.append("## Demo tenants")
    lines.append("")
    lines.append(
        f"{fixtures['tenant_count']} generic demo tenants. No real Tribe is "
        f"named. {fixtures['facts_verified_count']} facts are verified, "
        f"{fixtures['facts_demo_fixture_count']} are demo fixtures, and "
        f"{fixtures['facts_unknown_count']} are unknown."
    )
    lines.append("")
    lines.append(
        "Recognition status, applicant classes and service area are `unknown` "
        "for every demo tenant, deliberately. Fabricating them is the specific "
        "harm the fixture service exists to avoid, and a demo that shows "
        "`unknown` is showing how the product behaves when it does not know — "
        "which is most of the time."
    )
    lines.append("")
    lines.append("| Tenant | Kind | Operating states | SC priority | Fact status |")
    lines.append("| --- | --- | --- | --- | --- |")
    for profile in fixtures["tenant_profiles"]:
        states = (profile["operating_states"].get("value") or []) or ["—"]
        lines.append(
            f"| `{profile['tenant_id']}` "
            f"| {profile['tenant_kind'].get('value') or 'unknown'} "
            f"| {', '.join(states)} "
            f"| {str(profile['sc_priority']).lower()} "
            f"| {profile['profile_fact_status']} |"
        )
    lines.append("")
    lines.append("## Source priority")
    lines.append("")
    lines.append("| Tenant | SC | Federal | Active | Monitored |")
    lines.append("| --- | --- | --- | --- | --- |")
    for priority in bundle["priority_summaries"]:
        lines.append(
            f"| `{priority['tenant_id']}` | {priority['sc_source_count']} "
            f"| {priority['federal_source_count']} | {priority['sources_active']} "
            f"| {priority['sources_monitored']} |"
        )
    lines.append("")
    lines.append(
        "South Carolina priority is **tenant-specific**. The two SC demo "
        "tenants get 57 SC sources ranked first; the tenant operating in "
        "another state gets none, and the tenant with no operating state gets "
        "none. Every tier has zero active collectors."
    )
    lines.append("")
    lines.append("## Allowability review")
    lines.append("")
    lines.append(
        "Evidence-backed only: no affirmative label without a quote or "
        "reference from the opportunity's own text. **When the assessed cost is "
        "NativeForge itself, the label is capped at "
        f"`{SELF_ASSESSMENT_CAP}` regardless of evidence strength** — a tool "
        "telling a customer that buying the tool is grant-allowable has an "
        "obvious incentive problem, and a self-assessment that can only ever "
        "say \"ask a human\" is the defensible version."
    )
    lines.append("")
    lines.append("## What must happen next")
    lines.append("")
    for index, action in enumerate(readiness["next_required_actions"], 1):
        lines.append(f"{index}. `{action['action']}` — {action['why']}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_tenant_beta_artifacts(
    *,
    repo_root: Any = None,
    detect_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all six files, or refuse and write none."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    inspect_root = (
        Path(detect_root) if detect_root else Path(__file__).resolve().parents[3]
    )
    bundle = build_tenant_beta_bundle(repo_root=inspect_root)
    summary_text = render_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise TenantBetaArtifactError(
            "refusing to write tenant beta artifacts: " + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]

    (out_dir / CONTRACT_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "demo_scope": bundle["readiness"]["demo_scope"],
                "beta_features": list(BETA_FEATURES),
                "fact_statuses": sorted(FACT_STATUSES),
                "recognition_statuses": sorted(RECOGNITION_STATUSES),
                "priority_tiers": list(PRIORITY_TIERS),
                "readiness": bundle["readiness"],
                "priority_summaries": bundle["priority_summaries"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / FEATURE_CSV_NAME).write_text(
        _rows_to_csv(bundle["feature_rows"], FEATURE_CSV_COLUMNS), encoding="utf-8"
    )
    (out_dir / SOURCE_CSV_NAME).write_text(
        _rows_to_csv(bundle["source_rows"], SOURCE_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / PROFILES_JSON_NAME).write_text(
        json.dumps(
            {**declarations, **bundle["fixtures"]}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / ALLOWABILITY_JSON_NAME).write_text(
        json.dumps(
            {**declarations, **bundle["allowability"]}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": list(ARTIFACT_NAMES),
            **declarations,
            "tenant_count": bundle["fixtures"]["tenant_count"],
            "real_tribe_named": False,
            "claim_failures": [],
            "fabricated": False,
        }
    )
