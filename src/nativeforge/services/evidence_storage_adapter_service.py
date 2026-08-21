"""Evidence storage adapters (Campaign Block 23). validated_persistent gated off."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from nativeforge.services.persistence_approval_gate_contract_service import (
    OWNER_APPROVED_MIGRATIONS,
    build_persistence_approval_gate_contract,
)

SCHEMA_VERSION = "nf_evidence_storage_adapter_v1"

ADAPTER_KINDS = frozenset(
    {
        "fixture_backed",
        "local_dev_only",
        "planned_external",
        "validated_persistent",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


class EvidenceStorageAdapter(Protocol):
    kind: str

    def put_placeholder(
        self, *, evidence_label: str, org_id: str
    ) -> dict[str, Any]: ...

    def available(self) -> bool: ...


class FixtureBackedAdapter:
    kind = "fixture_backed"

    def available(self) -> bool:
        return True

    def put_placeholder(self, *, evidence_label: str, org_id: str) -> dict[str, Any]:
        digest = hashlib.sha256(f"{org_id}:{evidence_label}".encode()).hexdigest()[:16]
        ref = f"fixtures/evidence_intake_pilot/{org_id}/{digest}.placeholder"
        return {
            "adapter_kind": self.kind,
            "storage_reference": ref,
            "hash_or_digest": digest,
            "bytes_written": False,
            "upload_persistence_claimed": False,
            "validated_persistent": False,
        }


class LocalDevOnlyAdapter:
    kind = "local_dev_only"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("artifacts/local_dev_evidence_placeholders")

    def available(self) -> bool:
        return True

    def put_placeholder(self, *, evidence_label: str, org_id: str) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(f"{org_id}:{evidence_label}".encode()).hexdigest()[:16]
        path = self.root / org_id / f"{digest}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Metadata-only placeholder file — not customer binary upload
        path.write_text(
            f"PLACEHOLDER ONLY\norg={org_id}\nlabel={evidence_label}\n"
            "upload_persistence_claimed=false\n",
            encoding="utf-8",
        )
        return {
            "adapter_kind": self.kind,
            "storage_reference": str(path),
            "hash_or_digest": digest,
            "bytes_written": True,
            "bytes_are_customer_upload": False,
            "upload_persistence_claimed": False,
            "validated_persistent": False,
            "note": "local_dev placeholder text only — not durable customer storage",
        }


class PlannedExternalAdapter:
    kind = "planned_external"

    def available(self) -> bool:
        return True

    def put_placeholder(self, *, evidence_label: str, org_id: str) -> dict[str, Any]:
        return {
            "adapter_kind": self.kind,
            "storage_reference": None,
            "hash_or_digest": None,
            "bytes_written": False,
            "upload_persistence_claimed": False,
            "validated_persistent": False,
            "note": "external object storage required; not configured",
        }


class ValidatedPersistentAdapter:
    """Unavailable unless owner approvals and infrastructure are true."""

    kind = "validated_persistent"

    def available(self) -> bool:
        return False

    def put_placeholder(self, *, evidence_label: str, org_id: str) -> dict[str, Any]:
        raise RuntimeError(
            "validated_persistent adapter unavailable — OWNER_APPROVED_MIGRATIONS=false"
        )


def get_available_adapters(
    *,
    owner_approved_migrations: bool = OWNER_APPROVED_MIGRATIONS,
) -> list[str]:
    available = ["fixture_backed", "local_dev_only", "planned_external"]
    if owner_approved_migrations:
        # Still do not claim validated_persistent without separate validation
        pass
    return available


def run_storage_adapter_dry_run(
    *,
    owner_approved_migrations: bool = OWNER_APPROVED_MIGRATIONS,
) -> dict[str, Any]:
    gate = build_persistence_approval_gate_contract(
        owner_approved_migrations=owner_approved_migrations
    )
    results = []
    for adapter in (
        FixtureBackedAdapter(),
        LocalDevOnlyAdapter(),
        PlannedExternalAdapter(),
    ):
        results.append(
            adapter.put_placeholder(
                evidence_label="dry_run_placeholder",
                org_id="sc_pilot_catawba_indian_nation",
            )
        )
    validated = ValidatedPersistentAdapter()
    validated_result = {
        "adapter_kind": validated.kind,
        "available": validated.available(),
        "upload_persistence_claimed": False,
        "validated_persistent": False,
        "error": None
        if validated.available()
        else "unavailable_without_owner_approval_and_validation",
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "owner_approved_migrations": bool(owner_approved_migrations),
            "gate_id": gate.get("persistence_approval_gate_id"),
            "available_adapters": get_available_adapters(
                owner_approved_migrations=owner_approved_migrations
            ),
            "adapter_results": results,
            "validated_persistent_result": validated_result,
            "validated_persistent_adapter_claimed": False,
            "upload_persistence_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "migration_applied": False,
            "dry_run_status": gate.get("dry_run_status"),
        }
    )


def storage_adapter_dry_run_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "validated_persistent_adapter_claimed",
        "upload_persistence_claimed",
        "customer_data_persistence_claimed",
        "production_storage_claimed",
        "migration_applied",
    ):
        if report.get(key) is True:
            fails.append(key)
    if "validated_persistent" in (report.get("available_adapters") or []):
        fails.append("validated_persistent_listed_available")
    if (report.get("validated_persistent_result") or {}).get("available") is True:
        fails.append("validated_persistent_available")
    return fails
