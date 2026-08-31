"""Awarded Grants requirements readiness (Gate 108G).

Whether NativeForge can demonstrate awarded-grant requirements tracking, and
whether a Tribe could actually run their compliance calendar on it.

## Two questions, two answers

```text
ready_for_demo_contract              can we show the contract working?
ready_for_operational_awarded_tracking can a Tribe track a real award on it?
```

The first is true after this gate. The second is not, and the gap is not small:
there is no UI, nothing persists between requests, no document store, and no
extraction pipeline reading award packages.

An operational compliance tracker is a promise that a missed deadline will be
caught. Contracts and fixtures do not make that promise; a running system with
somebody's real award in it does.

## Every component detected by import

Nothing here reads a declaration. Modules are resolved through the import system
and the frontend is checked on disk, so a component that does not exist reports
as missing rather than as planned.

`ui_available` in particular is measured by looking for an awarded-grants
surface in `frontend/src`. Gate 108 built none, and the readiness says so.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_awarded_grants_requirements_readiness_v1"

CONTRACT_COMPONENT_MODULES: dict[str, str] = {
    "awarded_grant_record_contract_available": (
        "nativeforge.services.awarded_grant_record_service"
    ),
    "award_transition_contract_available": (
        "nativeforge.services.award_transition_service"
    ),
    "requirement_model_available": (
        "nativeforge.services.award_requirement_model_service"
    ),
    "requirements_calendar_available": (
        "nativeforge.services.award_requirements_calendar_service"
    ),
    "proof_audit_contract_available": (
        "nativeforge.services.award_requirement_proof_audit_service"
    ),
    "projected_vs_active_boundary_available": (
        "nativeforge.services.pursuit_reporting_burden_projection_service"
    ),
    "demo_fixture_available": (
        "nativeforge.services.awarded_grants_demo_fixture_service"
    ),
}

# What operational tracking needs on top. None of it exists.
#
# `verified_operational_identity_binding` was added by Gate 109. An awarded
# record carries a tenant_id and a customer_org_id, row-level security keys on
# the organization, and nothing relates the two without an explicit binding.
# Tracking a real Tribe's compliance obligations across that gap is how one
# Tribe ends up reading another's awards.
# Gate 124: what storage exists, which is a different question from whether
# persistence is live. The lane now has a table, an organization_id anchor, an
# RLS policy and a repository, and still nobody can authenticate to write to it.
#
# Reported separately rather than folded into `customer_persistence_live`,
# because a single field answering both would have to pick one, and both answers
# are load-bearing: "built" tells a reader what this gate did, "live" tells them
# what a Tribe can do. Gate 114 collapsed three answers into one here for the
# opposite reason - three detectors disagreeing about the same question.
STORAGE_COMPONENT_KEYS: tuple[str, ...] = (
    "awarded_grants_schema_available",
    "awarded_grants_repository_available",
    "awarded_grants_write_path_available",
    # Gate 125. Awarded tracking is two lanes, so "what storage exists" is two
    # answers. Reported per lane rather than rolled up, because a reader who
    # sees one true and one false learns something a single flag would hide.
    "award_requirements_schema_available",
    "award_requirements_repository_available",
    "award_requirements_write_path_available",
    # Gate 126. Three lanes now: an award, what it obliges, and what was filed.
    "proof_audit_schema_available",
    "proof_audit_repository_available",
    "proof_audit_write_path_available",
)

OPERATIONAL_COMPONENT_KEYS: tuple[str, ...] = (
    "ui_available",
    "customer_persistence_live",
    "document_storage_live",
    "requirement_extraction_live",
    "verified_operational_identity_binding",
)

DEMO_SCOPE = "awarded_requirements_contract_over_labelled_demo_fixtures"

NEXT_ACTION_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "verify_a_real_tenant_customer_org_binding",
        "Gate 109 built the binding contract and Gate 110 decided its store: a "
        "new identity binding table anchored to organization_id, the column "
        "every row-level security policy enforces on. No verified non-demo "
        "binding exists yet, and the migration is not safe to apply until "
        "customer auth can supply a verifier",
    ),
    (
        "persist_award_requirements",
        "Gate 124 gave an awarded grant somewhere to live; a requirement still "
        "has none, and a requirement is the half with the due date. A "
        "compliance calendar that cannot be re-read after a missed deadline is "
        "not a calendar, and requirements are what would be re-read",
    ),
    (
        "build_the_awarded_grants_surface",
        "the workspace is mandatory in the tenant beta contract and no UI "
        "exists for it",
    ),
    (
        "attach_document_storage_under_the_existing_gates",
        "award packages have to live somewhere before requirements can be "
        "extracted from them",
    ),
    (
        "wire_requirement_extraction_to_award_documents",
        "extraction exists for notices; award packages are a different corpus "
        "and nothing reads them",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _repo_root(detect_root: Any = None) -> Path:
    return Path(detect_root) if detect_root else Path(__file__).resolve().parents[3]


def _detect_awarded_ui(detect_root: Any = None) -> bool:
    """Is there an awarded-grants surface in the frontend? Looked for, not assumed."""
    src = _repo_root(detect_root) / "frontend" / "src"
    if not src.is_dir():
        return False
    for path in src.rglob("*.tsx"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if "awarded grants" in text or "awardedgrants" in text:
            return True
    return False


def _detect_requirement_extraction_live() -> bool:
    """Extraction over *award documents*, not over notices.

    The notice extractor exists and is deliberately not counted: reading a NOFO
    produces a projected burden, which this gate spent its length insisting is
    not an active obligation.
    """
    return _module_importable(
        "nativeforge.services.award_document_requirement_extraction_service"
    )


def _detect_verified_operational_binding() -> bool:
    """Is any verified, non-demo tenant/customer-org binding available?

    Detected, not declared. A binding store would be the thing to ask; none
    exists, and demo fixtures are deliberately not counted - a demo binding is
    not production verification, and counting it here would make the whole
    Gate 109 contract decorative.
    """
    if not _module_importable(
        "nativeforge.services.tenant_customer_org_identity_binding_service"
    ):
        return False
    return _module_importable("nativeforge.repositories.identity_binding")


def _capability_persistence_live(capability: str) -> bool:
    """Is this lane's customer persistence actually live?

    Gate 114 replaced three different answers to this question with one. Before
    it, this lane asked whether a module imported - which would have reported
    "persistence live" for an empty file, with no table, no RLS policy, no
    organization anchor and nobody able to authenticate.

    The capability model requires all of those, so this moves only when
    persistence really does.
    """
    try:
        from nativeforge.services.customer_persistence_capability_service import (
            build_capability,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return False
    return bool(build_capability(capability).get("operational"))


def _awarded_grants_storage_facts() -> dict[str, bool]:
    """What each awarded-tracking lane has built, regardless of whether it is live.

    Asked of the capability model rather than the filesystem, for the reason
    Gate 114 recorded below and Gate 120 rediscovered: a module-existence proxy
    reports "available" for an empty file.
    """
    try:
        from nativeforge.services.customer_persistence_capability_service import (
            build_capability,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return dict.fromkeys(STORAGE_COMPONENT_KEYS, False)

    facts: dict[str, bool] = {}
    for prefix, capability in (
        ("awarded_grants", "awarded_grants_persistence"),
        ("award_requirements", "award_requirements_persistence"),
        ("proof_audit", "proof_audit_persistence"),
    ):
        lane = build_capability(capability)
        facts[f"{prefix}_schema_available"] = bool(lane.get("schema_available"))
        facts[f"{prefix}_repository_available"] = bool(lane.get("repository_available"))
        facts[f"{prefix}_write_path_available"] = bool(lane.get("write_path_available"))
    return facts


def _proof_audit_persistence_available() -> bool:
    """Is there anywhere to keep a proof audit trail?

    Gate 126 built one. This asks the capability model rather than naming a
    module, because the first version named one:

    ```text
    probe expected  ..._proof_repository_service
    gate 126 built  ..._proof_audit_repository_service
    ```

    Two different names for one thing, written a gate apart, and the report
    would have kept saying the store did not exist while it sat in the same
    directory. Same family as Gate 124A's two near-miss contract mappings.

    `CAPABILITY_REPOSITORY_MODULES` is now the single place a repository module
    is named, and a test asserts every name in it imports.
    """
    try:
        from nativeforge.services.customer_persistence_capability_service import (
            build_capability,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return False
    lane = build_capability("proof_audit_persistence")
    return bool(lane.get("write_path_available"))


def build_awarded_requirements_readiness(*, detect_root: Any = None) -> dict[str, Any]:
    """Readiness, every component observed rather than declared."""
    components = {
        key: _module_importable(module)
        for key, module in CONTRACT_COMPONENT_MODULES.items()
    }

    ui_available = _detect_awarded_ui(detect_root)
    # No document store is wired, detected the same way the digest lane detects
    # its own gaps: by asking whether the module that would do it exists.
    #
    # Persistence is no longer detected that way. Gate 114A found this line
    # asking whether ``nativeforge.repositories.awarded_grant`` imports, which
    # would have flipped customer_persistence_live to True for an empty file -
    # a module-existence proxy moving in the unsafe direction. It now asks the
    # capability model, which requires a table, an organization_id anchor, an
    # RLS policy, a repository, a contract and customer auth.
    customer_persistence_live = _capability_persistence_live(
        "awarded_grants_persistence"
    )
    document_storage_live = _module_importable(
        "nativeforge.services.award_document_store_service"
    )
    requirement_extraction_live = _detect_requirement_extraction_live()

    operational = {
        "ui_available": ui_available,
        "customer_persistence_live": customer_persistence_live,
        "document_storage_live": document_storage_live,
        "requirement_extraction_live": requirement_extraction_live,
        "verified_operational_identity_binding": (
            _detect_verified_operational_binding()
        ),
    }

    storage = _awarded_grants_storage_facts()

    missing_contract = sorted(k for k, v in components.items() if not v)
    missing_operational = sorted(k for k, v in operational.items() if not v)

    blocked_reasons: list[str] = []
    for key in missing_contract:
        blocked_reasons.append(f"contract_component_missing:{key}")
    for key in missing_operational:
        blocked_reasons.append(f"operational_component_missing:{key}")

    ready_for_demo_contract = not missing_contract
    ready_for_operational_awarded_tracking = (
        ready_for_demo_contract and not missing_operational
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **components,
            **operational,
            **storage,
            # Built and unusable. Both halves stated, neither implying the other.
            "awarded_grants_storage_available": all(
                storage[k]
                for k in STORAGE_COMPONENT_KEYS
                if k.startswith("awarded_grants_")
            ),
            "award_requirements_storage_available": all(
                storage[k]
                for k in STORAGE_COMPONENT_KEYS
                if k.startswith("award_requirements_")
            ),
            "proof_audit_storage_available": all(
                storage[k]
                for k in STORAGE_COMPONENT_KEYS
                if k.startswith("proof_audit_")
            ),
            # Both lanes built. Still not tracking: see the operational list.
            "awarded_tracking_storage_available": all(storage.values()),
            # Named separately from document_storage_live, because a proof audit
            # trail and a document store are different missing things.
            "proof_audit_persistence_available": (_proof_audit_persistence_available()),
            "demo_scope": DEMO_SCOPE,
            "ready_for_demo_contract": ready_for_demo_contract,
            "ready_for_operational_awarded_tracking": (
                ready_for_operational_awarded_tracking
            ),
            "missing_contract_components": missing_contract,
            "missing_operational_components": missing_operational,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": [
                {"action": action, "why": why} for action, why in NEXT_ACTION_SEQUENCE
            ],
            # Constants: a readiness report tracks nothing and collects nothing.
            "live_source_collection_available": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "fabricated": False,
        }
    )


def readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if readiness.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "live_source_collection_available",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
    ):
        if readiness.get(constant) is not False:
            fails.append(f"readiness_claimed:{constant}")

    for key in CONTRACT_COMPONENT_MODULES:
        if key not in readiness:
            fails.append(f"readiness_missing_component:{key}")
    for key in OPERATIONAL_COMPONENT_KEYS:
        if key not in readiness:
            fails.append(f"readiness_missing_component:{key}")
    for key in STORAGE_COMPONENT_KEYS:
        if key not in readiness:
            fails.append(f"readiness_missing_component:{key}")

    # The whole reason the two are separate fields. Storage existing must never
    # be readable as persistence working.
    if readiness.get("awarded_grants_storage_available") and not all(
        readiness.get(key) for key in STORAGE_COMPONENT_KEYS
    ):
        fails.append("storage_available_without_every_storage_component")

    if readiness.get("customer_persistence_live") and not readiness.get(
        "awarded_grants_storage_available"
    ):
        fails.append("persistence_live_without_storage")

    # Gate 125. Storage for both halves must never read as tracking for either.
    if readiness.get("awarded_tracking_storage_available") and not (
        readiness.get("awarded_grants_storage_available")
        and readiness.get("award_requirements_storage_available")
    ):
        fails.append("tracking_storage_claimed_without_both_lanes")

    if readiness.get("ready_for_operational_awarded_tracking") and not readiness.get(
        "proof_audit_persistence_available"
    ):
        fails.append("operational_tracking_claimed_without_proof_audit_persistence")

    if readiness.get("proof_audit_persistence_available") and not readiness.get(
        "award_requirements_storage_available"
    ):
        fails.append("proof_audit_persistence_without_a_requirement_to_attach_to")

    # Gate 126. The measured flag and the lane's own storage must agree; two
    # answers to one question is how a probe comes to name a module nobody
    # built.
    if readiness.get("proof_audit_persistence_available") is not readiness.get(
        "proof_audit_storage_available"
    ):
        fails.append("proof_audit_availability_disagrees_with_its_lane")

    # Operational readiness cannot be claimed while anything is missing.
    if readiness.get("ready_for_operational_awarded_tracking") and (
        readiness.get("missing_operational_components")
        or readiness.get("missing_contract_components")
    ):
        fails.append("operational_readiness_claimed_with_missing_components")

    # Demo readiness cannot be claimed without the demo fixtures.
    if readiness.get("ready_for_demo_contract") and not readiness.get(
        "demo_fixture_available"
    ):
        fails.append("demo_readiness_claimed_without_fixtures")

    # Both answers must agree with the measurements.
    expected_demo = not readiness.get("missing_contract_components")
    if readiness.get("ready_for_demo_contract") is not expected_demo:
        fails.append("demo_readiness_disagrees_with_the_measurements")

    expected_operational = expected_demo and not readiness.get(
        "missing_operational_components"
    )
    if readiness.get("ready_for_operational_awarded_tracking") is not (
        expected_operational
    ):
        fails.append("operational_readiness_disagrees_with_the_measurements")

    # A refusal must name itself.
    if not readiness.get("ready_for_operational_awarded_tracking") and not (
        readiness.get("blocked_reasons")
    ):
        fails.append("operational_refusal_without_a_reason")

    if readiness.get("demo_scope") != DEMO_SCOPE:
        fails.append("demo_scope_altered")

    return fails
