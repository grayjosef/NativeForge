"""Gate 141E: document storage readiness, measured instead of declared.

## The three constants this replaces

```text
awarded_operational_tracking_readiness_service.py:320
    "document_body_storage_ready": False        a literal

award_document_routes.py:155, :183, :212
    object_store_configured=False               a literal, three times

post_award_common.refuse_body_storage
    "object_store_configured": False            a literal in the refusal
```

Every one is correct today and none is measured. Configure a bucket tomorrow and
the routes would keep telling callers the store is unconfigured while the
readiness roll-up kept saying body storage is not ready. Same family Gate 114A
removed for `customer_persistence_live`, 139A for `awarded_operational_tracking`
and 140F for `tenant_digest_operational`.

## Two questions, kept apart

```text
document_metadata_operational   can a tenant record and read a document
                                REFERENCE? Yes, since Gate 139.
document_body_storage_ready     can its BYTES be stored? No, and this module
                                says why rather than saying false.
```

Metadata does not need the object store and does not ask for it. Requiring one
would make the metadata lane unreachable and every "not ready" above it
unfalsifiable — Gate 134F's lesson, and the reason
`object_store_required_for_metadata` is a field here rather than an assumption.

## Scope, because a fake is not a bucket

```text
none              nothing is ready
hermetic_fake     the ADAPTER is proved. Nothing about durability, a bucket,
                  a credential or any external service.
production        an external check was explicitly allowed AND passed. This
                  module cannot produce it from configuration alone.
```

`object_store_configured` is true only in `production` scope. A hermetic proof
that could flip it would make every refusal above it unfalsifiable, which is the
whole failure mode this separation exists to prevent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_document_storage_readiness_v1"

METADATA_ROUTE_MODULE = "src/nativeforge/api/award_document_routes.py"

REQUIRED_DEPENDENCY = "require_demo_org_session"

SCOPE_NONE = "none"
SCOPE_HERMETIC_FAKE = "hermetic_fake"
SCOPE_PRODUCTION = "production"

READINESS_SCOPES: tuple[str, ...] = (SCOPE_NONE, SCOPE_HERMETIC_FAKE, SCOPE_PRODUCTION)

#: The only scope in which a real store exists.
CONFIGURED_SCOPES: frozenset[str] = frozenset({SCOPE_PRODUCTION})

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "production_storage",
    "external_object_storage_activation",
    "document_body_upload_in_runtime",
    "customer_file_ingestion",
    "signed_url_issuance",
)

#: Markers that must never appear in a readiness result. A credential reaching a
#: readiness roll-up is how one reaches an artifact.
CREDENTIAL_SHAPED_MARKERS: tuple[str, ...] = (
    "http://",
    "https://",
    "AKIA",
    "aws_secret",
    "-----BEGIN",
    "s3://",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def detect_metadata_route_module(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Does the metadata route module exist, and is it session-wired?

    ``repo_root`` is injectable so `route_module_available: False` is reachable
    without deleting a file. Parsed for `Depends(require_demo_org_session)`
    rather than searched as a substring: this campaign has found twelve probes
    reporting on a name instead of a capability.
    """
    root = repo_root if repo_root is not None else _repo_root()
    path = root / METADATA_ROUTE_MODULE
    if not path.is_file():
        return {
            "route_module": METADATA_ROUTE_MODULE,
            "route_module_available": False,
            "session_wired": False,
            "refuses_body_storage": False,
            "derives_object_store_configured": False,
            "blocked_reasons": ["route_module_does_not_exist"],
        }

    body = path.read_text(encoding="utf-8", errors="replace")
    blocked: list[str] = []

    session_wired = bool(re.search(rf"Depends\(\s*{REQUIRED_DEPENDENCY}\s*\)", body))
    if not session_wired:
        blocked.append("route_module_does_not_depend_on_a_session_org_context")

    refuses = bool(re.search(r"refuse_body_storage\(\s*body\s*\)", body))
    if not refuses:
        blocked.append("route_module_does_not_refuse_body_storage")

    # The literal this gate removed. If it comes back, the routes have stopped
    # measuring and started asserting again.
    derives = not re.search(r"object_store_configured\s*=\s*False", body)
    if not derives:
        blocked.append("route_module_hardcodes_object_store_configured_false")

    return _json_safe(
        {
            "route_module": METADATA_ROUTE_MODULE,
            "route_module_available": True,
            "session_wired": session_wired,
            "refuses_body_storage": refuses,
            "derives_object_store_configured": derives,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def build_document_storage_readiness(
    *,
    preflight: dict[str, Any] | None = None,
    adapter_proof: dict[str, Any] | None = None,
    metadata_route_smoke: dict[str, Any] | None = None,
    body_route_smoke: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    measure: bool = True,
) -> dict[str, Any]:
    """Is document storage ready, and in which scope? Contacts nothing.

    ``measure`` exists so a caller that has already run the preflight and the
    adapter proof can hand them in, and so a caller with neither gets them
    measured rather than assumed. Absent evidence is absent - false, never
    optimistic.
    """
    from nativeforge.services.object_storage_adapter_service import (
        MAX_BODY_BYTES,
        adapter_proof_invariant_failures,
        run_hermetic_adapter_proof,
    )
    from nativeforge.services.object_storage_configuration_preflight_service import (
        HERMETIC_FAKE_VERIFIED,
        PRODUCTION_VERIFIED,
        build_object_storage_preflight,
        preflight_invariant_failures,
    )

    proof = (
        adapter_proof
        if adapter_proof is not None
        else (run_hermetic_adapter_proof() if measure else {})
    )
    fake_passed = bool(proof.get("hermetic_fake_passed"))

    flight = (
        preflight
        if preflight is not None
        else (
            build_object_storage_preflight(hermetic_fake_passed=fake_passed)
            if measure
            else {}
        )
    )

    metadata = metadata_route_smoke or {}
    body = body_route_smoke or {}

    module = detect_metadata_route_module(repo_root=repo_root)

    blocked: list[str] = []
    blocked.extend(f"metadata_route:{r}" for r in module["blocked_reasons"])
    blocked.extend(f"preflight:{r}" for r in preflight_invariant_failures(flight))
    if proof:
        blocked.extend(f"adapter:{r}" for r in adapter_proof_invariant_failures(proof))

    # -- metadata, which needs no object store ------------------------------
    metadata_proved = bool(metadata.get("metadata_route_operational"))
    metadata_org_scoped = bool(metadata.get("org_scoped_read_write_proved"))
    metadata_needs_no_body = bool(metadata.get("body_bytes_not_required", True))

    if metadata:
        for name, value in (
            ("metadata_route_operational", metadata_proved),
            ("org_scoped_read_write_proved", metadata_org_scoped),
        ):
            if not value:
                blocked.append(f"metadata_smoke_did_not_prove:{name}")
        blocked.extend(
            f"metadata_smoke:{r}" for r in metadata.get("blocked_reasons") or []
        )
    else:
        blocked.append("no_metadata_route_smoke_was_supplied")

    metadata_operational = bool(
        module["route_module_available"]
        and module["session_wired"]
        and module["refuses_body_storage"]
        and metadata_proved
        and metadata_org_scoped
        and metadata_needs_no_body
    )

    # -- the body, which needs all of it ------------------------------------
    body_route_proved = bool(body.get("body_route_operational"))
    body_blocker_correct = bool(body.get("unconfigured_blocker_correct"))
    secrets_exposed = bool(body.get("secrets_exposed")) or bool(
        flight.get("credential_values_reported")
    )

    state = str(flight.get("state") or "")
    preflight_passes = state in {PRODUCTION_VERIFIED, HERMETIC_FAKE_VERIFIED}

    if state == PRODUCTION_VERIFIED and fake_passed and body_route_proved:
        scope = SCOPE_PRODUCTION
    elif state == HERMETIC_FAKE_VERIFIED and fake_passed and body_route_proved:
        scope = SCOPE_HERMETIC_FAKE
    else:
        scope = SCOPE_NONE

    body_ready = bool(
        preflight_passes
        and fake_passed
        and body_route_proved
        and not secrets_exposed
        and scope != SCOPE_NONE
    )

    if not preflight_passes:
        blocked.append(f"object_storage_preflight_state:{state or 'absent'}")
    if not fake_passed:
        blocked.append("adapter_proof_did_not_pass")
    if not body_route_proved:
        blocked.append("no_body_route_proof_was_supplied")
    if secrets_exposed:
        blocked.append("credential_values_were_exposed")

    # `object_store_configured` comes from the preflight and nowhere else. A
    # second answer to one question is the shape Gate 114 collapsed.
    configured = bool(flight.get("object_store_configured")) and scope in (
        CONFIGURED_SCOPES
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_metadata_operational": metadata_operational,
            "document_body_storage_ready": body_ready,
            "object_store_configured": configured,
            "scope": scope,
            "scopes": list(READINESS_SCOPES),
            "preflight_state": state or None,
            "preflight_passes": preflight_passes,
            "hermetic_fake_passed": fake_passed,
            "metadata_route": module,
            "metadata_route_operational": metadata_proved,
            "org_scoped_read_write_proved": metadata_org_scoped,
            "body_route_operational": body_route_proved,
            "unconfigured_blocker_correct": body_blocker_correct,
            "max_body_bytes": MAX_BODY_BYTES,
            # Named as a field, not implied. Requiring a store for metadata
            # would make the metadata lane permanently unreachable.
            "object_store_required_for_metadata": False,
            "body_bytes_required_for_metadata": False,
            # Constants. No branch sets any of them.
            "production_storage": False,
            "external_object_store_contacted": False,
            "network_calls": 0,
            "body_bytes_written_externally": 0,
            "real_customer_files_read": 0,
            "real_customer_files_hashed": 0,
            "credential_values_reported": False,
            "customer_auth_live": False,
            "real_organization_touched": False,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def document_storage_readiness_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    """What must never be true of a document storage readiness result."""
    fails: list[str] = []

    scope = result.get("scope")
    if scope not in READINESS_SCOPES:
        fails.append(f"scope_not_recognised:{scope}")

    if result.get("document_metadata_operational"):
        for field in ("metadata_route_operational", "org_scoped_read_write_proved"):
            if not result.get(field):
                fails.append(f"metadata_operational_without:{field}")
        module = result.get("metadata_route") or {}
        if not module.get("refuses_body_storage"):
            fails.append("metadata_operational_without_a_body_refusal")
        if not module.get("session_wired"):
            fails.append("metadata_operational_without_a_session")
        if not module.get("derives_object_store_configured"):
            fails.append("metadata_route_hardcodes_object_store_configured")

    if result.get("document_body_storage_ready"):
        if scope == SCOPE_NONE:
            fails.append("body_ready_in_no_scope")
        if not result.get("hermetic_fake_passed"):
            fails.append("body_ready_without_an_adapter_proof")
        if not result.get("preflight_passes"):
            fails.append("body_ready_without_a_passing_preflight")
        if not result.get("body_route_operational"):
            fails.append("body_ready_without_a_body_route_proof")

    # The load-bearing separation.
    if result.get("object_store_configured") and scope != SCOPE_PRODUCTION:
        fails.append(f"configured_in_scope:{scope}")
    if scope == SCOPE_HERMETIC_FAKE and result.get("object_store_configured"):
        fails.append("a_fake_adapter_configured_the_object_store")

    for field in (
        "production_storage",
        "external_object_store_contacted",
        "credential_values_reported",
        "customer_auth_live",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in (
        "network_calls",
        "body_bytes_written_externally",
        "real_customer_files_read",
        "real_customer_files_hashed",
    ):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    if result.get("object_store_required_for_metadata"):
        fails.append("an_object_store_was_required_for_metadata")
    if result.get("body_bytes_required_for_metadata"):
        fails.append("body_bytes_were_required_for_metadata")

    missing = set(NOT_APPROVED) - set(result.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    rendered = json.dumps(result)
    for marker in CREDENTIAL_SHAPED_MARKERS:
        if marker in rendered:
            fails.append(f"readiness_carries_a_value_shaped_marker:{marker}")

    if not result.get("document_body_storage_ready") and not result.get(
        "blocked_reasons"
    ):
        fails.append("body_not_ready_and_nothing_blocked_it")

    return fails
