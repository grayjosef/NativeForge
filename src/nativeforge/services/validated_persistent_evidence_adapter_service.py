"""Validated persistent evidence adapter — local/dev only (Campaign Block 25)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nativeforge.db.models import NfEvidenceIntakeRecord
from nativeforge.services.evidence_intake_contract_service import (
    build_evidence_intake_record,
    evidence_intake_invariant_failures,
    evidence_may_contribute_to_unlock,
    make_evidence_intake_id,
)
from nativeforge.services.persistence_approval_resolver_service import (
    resolve_persistence_approval_lane,
)

SCHEMA_VERSION = "nf_validated_persistent_evidence_adapter_v1"
ALLOWED_MIME = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "text/plain"}
)
MAX_SIZE_BYTES = 25 * 1024 * 1024
DEFAULT_BLOB_ROOT = Path("artifacts/local_dev_evidence_store")
DEFAULT_DB_PATH = Path("artifacts/local_dev_evidence.sqlite3")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _make_local_dev_session_factory(db_path: Path) -> sessionmaker:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+pysqlite:///{db_path.resolve().as_posix()}"
    engine = create_engine(url, future=True)
    NfEvidenceIntakeRecord.__table__.create(bind=engine, checkfirst=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _row_to_dict(row: NfEvidenceIntakeRecord) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "evidence_intake_id": row.evidence_intake_id,
        "organization_profile_id": row.organization_profile_id,
        "application_workspace_id": row.application_workspace_id,
        "pursuit_workspace_id": row.pursuit_workspace_id,
        "checklist_item_id": row.checklist_item_id,
        "binder_item_id": row.binder_item_id,
        "forms_attachment_map_id": row.forms_attachment_map_id,
        "package_export_preview_id": row.package_export_preview_id,
        "evidence_type": row.evidence_type,
        "evidence_label": row.evidence_label,
        "source_context": row.source_context,
        "storage_mode": row.storage_mode,
        "storage_reference": row.storage_reference,
        "hash_or_digest": row.hash_or_digest,
        "file_name": row.file_name,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "review_status": row.review_status,
        "human_review_required": row.human_review_required,
        "package_unlock_claimed": row.package_unlock_claimed,
        "upload_persistence_claimed": row.upload_persistence_claimed,
        "persistence_scope": row.persistence_scope,
        "customer_data_persistence_claimed": row.customer_data_persistence_claimed,
        "production_storage_claimed": row.production_storage_claimed,
        "archived": row.archived,
        "payload_json": row.payload_json,
        "schema_version": SCHEMA_VERSION,
        "validated_persistent": True,
        "validated_persistent_scope": "local_dev_only",
        "submission_ready_claimed": False,
        "final_export_claimed": False,
        "live_ingest_claimed": False,
    }


class ValidatedPersistentAdapter:
    """Local/dev validated persistent evidence storage."""

    kind = "validated_persistent"

    def __init__(
        self,
        *,
        blob_root: Path | None = None,
        db_path: Path | None = None,
        session_factory: sessionmaker | None = None,
    ) -> None:
        self.blob_root = blob_root or DEFAULT_BLOB_ROOT
        self.db_path = db_path or DEFAULT_DB_PATH
        self.session_factory = session_factory or _make_local_dev_session_factory(
            self.db_path
        )
        self._lane = resolve_persistence_approval_lane()

    def available(self) -> bool:
        return bool(self._lane.get("gate10_local_dev_lane"))

    def _require_available(self) -> None:
        if not self.available():
            raise RuntimeError(
                "validated_persistent unavailable — local_dev approval lane closed"
            )

    def _validate_mime_size(
        self, *, mime_type: str | None, size_bytes: int | None
    ) -> list[str]:
        fails: list[str] = []
        if mime_type is not None and mime_type not in ALLOWED_MIME:
            fails.append(f"mime_not_allowed:{mime_type}")
        if size_bytes is not None and size_bytes > MAX_SIZE_BYTES:
            fails.append(f"size_exceeds_limit:{size_bytes}")
        if size_bytes is not None and size_bytes < 0:
            fails.append("size_negative")
        return fails

    def create_evidence(
        self,
        *,
        organization_profile_id: str,
        evidence_label: str,
        evidence_type: str = "attachment_needed",
        content: bytes | None = None,
        file_name: str | None = None,
        mime_type: str | None = "text/plain",
        application_workspace_id: str | None = None,
        pursuit_workspace_id: str | None = None,
        checklist_item_id: str | None = None,
        binder_item_id: str | None = None,
        forms_attachment_map_id: str | None = None,
        package_export_preview_id: str | None = None,
        session: Session | None = None,
    ) -> dict[str, Any]:
        self._require_available()
        raw = (
            content
            if content is not None
            else (
                f"local_dev_evidence\norg={organization_profile_id}\n"
                f"label={evidence_label}\n"
            ).encode()
        )
        size_bytes = len(raw)
        mime_fails = self._validate_mime_size(
            mime_type=mime_type, size_bytes=size_bytes
        )
        if mime_fails:
            raise ValueError(f"evidence_validation_failed:{mime_fails}")

        digest = hashlib.sha256(raw).hexdigest()
        ei_id = make_evidence_intake_id(organization_profile_id, evidence_label)
        self.blob_root.mkdir(parents=True, exist_ok=True)
        org_dir = self.blob_root / organization_profile_id
        org_dir.mkdir(parents=True, exist_ok=True)
        safe_name = (file_name or f"{digest[:16]}.bin").replace("/", "_")
        path = org_dir / safe_name
        path.write_bytes(raw)

        contract = build_evidence_intake_record(
            organization_profile_id=organization_profile_id,
            evidence_label=evidence_label,
            evidence_type=evidence_type,
            application_workspace_id=application_workspace_id,
            pursuit_workspace_id=pursuit_workspace_id,
            checklist_item_id=checklist_item_id,
            binder_item_id=binder_item_id,
            forms_attachment_map_id=forms_attachment_map_id,
            package_export_preview_id=package_export_preview_id,
            storage_mode="validated_persistent",
            storage_reference=str(path),
            hash_or_digest=digest,
            file_name=safe_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            review_status="needs_review",
            human_review_required=True,
        )
        contract["upload_persistence_claimed"] = True
        contract["persistence_scope"] = "local_dev_only"
        contract["customer_data_persistence_claimed"] = False
        contract["production_storage_claimed"] = False
        contract["package_unlock_claimed"] = False
        inv = evidence_intake_invariant_failures(contract)
        if inv:
            raise ValueError(f"contract_invariant_failures:{inv}")

        own_session = session is None
        db = session or self.session_factory()
        try:
            existing = (
                db.query(NfEvidenceIntakeRecord)
                .filter(NfEvidenceIntakeRecord.evidence_intake_id == ei_id)
                .one_or_none()
            )
            if existing and not existing.archived:
                raise ValueError(f"evidence_already_exists:{ei_id}")
            row = NfEvidenceIntakeRecord(
                id=uuid.uuid4(),
                evidence_intake_id=ei_id,
                organization_profile_id=organization_profile_id,
                application_workspace_id=application_workspace_id,
                pursuit_workspace_id=pursuit_workspace_id,
                checklist_item_id=checklist_item_id,
                binder_item_id=binder_item_id,
                forms_attachment_map_id=forms_attachment_map_id,
                package_export_preview_id=package_export_preview_id,
                evidence_type=evidence_type,
                evidence_label=evidence_label,
                source_context="validated_persistent_local_dev",
                storage_mode="validated_persistent",
                storage_reference=str(path),
                hash_or_digest=digest,
                file_name=safe_name,
                mime_type=mime_type,
                size_bytes=size_bytes,
                review_status="needs_review",
                human_review_required=True,
                package_unlock_claimed=False,
                upload_persistence_claimed=True,
                persistence_scope="local_dev_only",
                customer_data_persistence_claimed=False,
                production_storage_claimed=False,
                archived=False,
                payload_json={
                    "created_at": datetime.now(UTC).isoformat(),
                    "adapter": self.kind,
                },
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _json_safe(_row_to_dict(row))
        finally:
            if own_session:
                db.close()

    def read_evidence(
        self,
        *,
        evidence_intake_id: str,
        organization_profile_id: str,
        session: Session | None = None,
    ) -> dict[str, Any] | None:
        self._require_available()
        own_session = session is None
        db = session or self.session_factory()
        try:
            row = (
                db.query(NfEvidenceIntakeRecord)
                .filter(
                    NfEvidenceIntakeRecord.evidence_intake_id == evidence_intake_id,
                    NfEvidenceIntakeRecord.organization_profile_id
                    == organization_profile_id,
                    NfEvidenceIntakeRecord.archived.is_(False),
                )
                .one_or_none()
            )
            return _json_safe(_row_to_dict(row)) if row else None
        finally:
            if own_session:
                db.close()

    def link_evidence(
        self,
        *,
        evidence_intake_id: str,
        organization_profile_id: str,
        checklist_item_id: str | None = None,
        binder_item_id: str | None = None,
        forms_attachment_map_id: str | None = None,
        package_export_preview_id: str | None = None,
        application_workspace_id: str | None = None,
        session: Session | None = None,
    ) -> dict[str, Any]:
        self._require_available()
        own_session = session is None
        db = session or self.session_factory()
        try:
            row = (
                db.query(NfEvidenceIntakeRecord)
                .filter(
                    NfEvidenceIntakeRecord.evidence_intake_id == evidence_intake_id,
                    NfEvidenceIntakeRecord.organization_profile_id
                    == organization_profile_id,
                    NfEvidenceIntakeRecord.archived.is_(False),
                )
                .one_or_none()
            )
            if row is None:
                raise ValueError(f"evidence_not_found:{evidence_intake_id}")
            if checklist_item_id is not None:
                row.checklist_item_id = checklist_item_id
            if binder_item_id is not None:
                row.binder_item_id = binder_item_id
            if forms_attachment_map_id is not None:
                row.forms_attachment_map_id = forms_attachment_map_id
            if package_export_preview_id is not None:
                row.package_export_preview_id = package_export_preview_id
            if application_workspace_id is not None:
                row.application_workspace_id = application_workspace_id
            db.commit()
            db.refresh(row)
            return _json_safe(_row_to_dict(row))
        finally:
            if own_session:
                db.close()

    def set_review_status(
        self,
        *,
        evidence_intake_id: str,
        organization_profile_id: str,
        review_status: str,
        session: Session | None = None,
    ) -> dict[str, Any]:
        self._require_available()
        if review_status not in {
            "needs_review",
            "approved",
            "rejected",
            "needs_more_information",
            "blocked",
            "archived",
        }:
            raise ValueError(f"bad_review_status:{review_status}")
        own_session = session is None
        db = session or self.session_factory()
        try:
            row = (
                db.query(NfEvidenceIntakeRecord)
                .filter(
                    NfEvidenceIntakeRecord.evidence_intake_id == evidence_intake_id,
                    NfEvidenceIntakeRecord.organization_profile_id
                    == organization_profile_id,
                    NfEvidenceIntakeRecord.archived.is_(False),
                )
                .one_or_none()
            )
            if row is None:
                raise ValueError(f"evidence_not_found:{evidence_intake_id}")
            row.review_status = review_status
            row.package_unlock_claimed = False
            if review_status == "archived":
                row.archived = True
            db.commit()
            db.refresh(row)
            out = _row_to_dict(row)
            out["may_contribute_to_unlock"] = evidence_may_contribute_to_unlock(
                {
                    **out,
                    "human_review_required": row.human_review_required,
                }
            )
            if out["may_contribute_to_unlock"] and review_status == "approved":
                out["package_unlock_note"] = (
                    "may_contribute_to_unlock=true but package_unlock_claimed remains "
                    "false until separate human package-gate workflow"
                )
            return _json_safe(out)
        finally:
            if own_session:
                db.close()

    def reject_evidence(
        self,
        *,
        evidence_intake_id: str,
        organization_profile_id: str,
        session: Session | None = None,
    ) -> dict[str, Any]:
        return self.set_review_status(
            evidence_intake_id=evidence_intake_id,
            organization_profile_id=organization_profile_id,
            review_status="rejected",
            session=session,
        )

    def archive_evidence(
        self,
        *,
        evidence_intake_id: str,
        organization_profile_id: str,
        session: Session | None = None,
    ) -> dict[str, Any]:
        return self.set_review_status(
            evidence_intake_id=evidence_intake_id,
            organization_profile_id=organization_profile_id,
            review_status="archived",
            session=session,
        )

    def assert_no_cross_org_read(
        self,
        *,
        evidence_intake_id: str,
        owner_org_id: str,
        other_org_id: str,
        session: Session | None = None,
    ) -> list[str]:
        leaked = self.read_evidence(
            evidence_intake_id=evidence_intake_id,
            organization_profile_id=other_org_id,
            session=session,
        )
        fails: list[str] = []
        if leaked is not None:
            fails.append(f"cross_org_leak:{owner_org_id}->{other_org_id}")
        return fails


def run_validated_persistent_lifecycle_smoke(
    *,
    organization_profile_id: str = "sc_pilot_catawba_indian_nation",
    other_org_id: str = "sc_pilot_eastern_band_of_cherokee",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Create → link → review reject/approve → archive; prove unlock + isolation."""
    adapter = ValidatedPersistentAdapter(db_path=db_path)
    if not adapter.available():
        return {
            "schema_version": SCHEMA_VERSION,
            "overall_status": "FAIL",
            "fails": ["adapter_unavailable"],
            "validated_persistent_adapter_claimed": False,
            "upload_persistence_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
        }

    label = f"gate10_lifecycle_{uuid.uuid4().hex[:8]}"
    fails: list[str] = []
    created = adapter.create_evidence(
        organization_profile_id=organization_profile_id,
        evidence_label=label,
        evidence_type="local_dev_validation",
        content=b"Gate 10 local/dev evidence validation bytes\n",
        file_name=f"{label}.txt",
        mime_type="text/plain",
        checklist_item_id=None,
    )
    ei_id = created["evidence_intake_id"]
    linked = adapter.link_evidence(
        evidence_intake_id=ei_id,
        organization_profile_id=organization_profile_id,
        checklist_item_id="checklist:gate10",
        binder_item_id="binder:gate10",
        forms_attachment_map_id="fam:gate10",
    )
    if linked.get("checklist_item_id") != "checklist:gate10":
        fails.append("link_failed")

    if evidence_may_contribute_to_unlock(created):
        fails.append("unlock_before_review")

    rejected = adapter.reject_evidence(
        evidence_intake_id=ei_id,
        organization_profile_id=organization_profile_id,
    )
    if rejected.get("package_unlock_claimed") is True:
        fails.append("unlock_on_reject")
    if evidence_may_contribute_to_unlock(rejected):
        fails.append("may_unlock_on_reject")

    adapter.archive_evidence(
        evidence_intake_id=ei_id,
        organization_profile_id=organization_profile_id,
    )

    label2 = f"gate10_approve_{uuid.uuid4().hex[:8]}"
    created2 = adapter.create_evidence(
        organization_profile_id=organization_profile_id,
        evidence_label=label2,
        content=b"approve path\n",
        mime_type="text/plain",
        file_name=f"{label2}.txt",
    )
    approved = adapter.set_review_status(
        evidence_intake_id=created2["evidence_intake_id"],
        organization_profile_id=organization_profile_id,
        review_status="approved",
    )
    if approved.get("package_unlock_claimed") is True:
        fails.append("unlock_claimed_on_approve")
    if not evidence_may_contribute_to_unlock(approved):
        fails.append("approved_should_may_contribute")

    fails.extend(
        adapter.assert_no_cross_org_read(
            evidence_intake_id=created2["evidence_intake_id"],
            owner_org_id=organization_profile_id,
            other_org_id=other_org_id,
        )
    )

    mime_ok = False
    try:
        adapter.create_evidence(
            organization_profile_id=organization_profile_id,
            evidence_label=f"bad_mime_{uuid.uuid4().hex[:6]}",
            content=b"x",
            mime_type="application/x-msdownload",
        )
    except ValueError:
        mime_ok = True
    if not mime_ok:
        fails.append("mime_guard_failed")

    status = "PASS" if not fails else "FAIL"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "overall_status": status,
            "fails": fails,
            "validated_persistent_adapter_claimed": True,
            "validated_persistent_scope": "local_dev_only",
            "upload_persistence_claimed": True,
            "upload_persistence_scope": "local_dev_only",
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "migration_environment": "local_dev_only",
            "sample_evidence_intake_id": created2["evidence_intake_id"],
            "package_unlock_claimed": False,
            "local_dev_db_path": str(adapter.db_path),
        }
    )
