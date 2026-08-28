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
        "Gate 109 built the binding contract; no verified non-demo binding "
        "exists yet, and row-level security keys on the organization while the "
        "awarded lane is tenant-scoped",
    ),
    (
        "persist_awarded_records_and_requirements",
        "nothing survives a request today, so a compliance calendar cannot be "
        "re-read after a missed deadline",
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


def build_awarded_requirements_readiness(
    *, detect_root: Any = None
) -> dict[str, Any]:
    """Readiness, every component observed rather than declared."""
    components = {
        key: _module_importable(module)
        for key, module in CONTRACT_COMPONENT_MODULES.items()
    }

    ui_available = _detect_awarded_ui(detect_root)
    # Nothing persists and no document store is wired. Both are detected the
    # same way the digest lane detects its own gaps: by asking whether the
    # module that would do it exists.
    customer_persistence_live = _module_importable(
        "nativeforge.repositories.awarded_grant"
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
