"""Deterministic SF-424 preview payload (research/domain/federal-forms.md)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.db.models import (
    NfGrantPursuit,
    NfGrantSpark,
    NfNofoExtractionRun,
    NfTribalProfile,
)
from nativeforge.domain.enums import TribalEntityType

PACKAGE_ENGINE = "sf424_preview_v1"


def _json_digest(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def applicant_type_for_entity(entity_type: str) -> dict[str, Any]:
    """SF-424 field 9 — code letter + label; may require human confirmation."""
    try:
        et = TribalEntityType(entity_type)
    except ValueError:
        return {
            "code": None,
            "label": None,
            "requires_confirmation": True,
            "note": f"Unknown entity_type '{entity_type}' — map manually.",
        }
    # Letters align with GSA SF-424 applicant type codes (tribal-focused set).
    mapping: dict[TribalEntityType, tuple[str, str, bool]] = {
        TribalEntityType.federally_recognized_tribe: (
            "F",
            "Native American Tribal Government (Federally Recognized)",
            False,
        ),
        TribalEntityType.tribal_government: (
            "F",
            "Native American Tribal Government (Federally Recognized)",
            True,
        ),
        TribalEntityType.tribal_organization: (
            "F",
            "Native American Tribal Government (Federally Recognized)",
            True,
        ),
        TribalEntityType.tribal_nonprofit: (
            "M",
            "Other nonprofit",
            False,
        ),
        TribalEntityType.tribal_college: (
            "H",
            "Public/State Controlled Institution of Higher Education",
            True,
        ),
        TribalEntityType.alaska_native_corporation: (
            "I",
            "Private Institution of Higher Education (verify for ANC)",
            True,
        ),
        TribalEntityType.alaska_native_village: (
            "F",
            "Native American Tribal Government (Federally Recognized)",
            True,
        ),
        TribalEntityType.native_hawaiian_organization: (
            "M",
            "Other nonprofit",
            True,
        ),
        TribalEntityType.native_serving_nonprofit: (
            "M",
            "Other nonprofit",
            True,
        ),
        TribalEntityType.other: (
            None,
            None,
            True,
        ),
    }
    code, label, needs_confirm = mapping[et]
    return {
        "code": code,
        "label": label,
        "requires_confirmation": needs_confirm,
        "entity_type": et.value,
    }


def _physical_address_block(addr: dict[str, Any] | None) -> dict[str, Any]:
    if not addr:
        return {
            "street": None,
            "city": None,
            "state": None,
            "zip": None,
            "county": None,
            "source": "tribal_profile.physical_address",
        }
    street = (
        addr.get("line1")
        or addr.get("street")
        or addr.get("street1")
        or addr.get("address_line_1")
    )
    return {
        "street": street,
        "city": addr.get("city"),
        "state": addr.get("state"),
        "zip": addr.get("zip") or addr.get("zipcode"),
        "county": addr.get("county"),
        "source": "tribal_profile.physical_address",
    }


def _contact_block(blob: dict[str, Any] | None, *, source: str) -> dict[str, Any]:
    if not blob:
        return {"name": None, "email": None, "phone": None, "source": source}
    return {
        "name": blob.get("name") or blob.get("full_name"),
        "email": blob.get("email"),
        "phone": blob.get("phone") or blob.get("telephone"),
        "source": source,
    }


def build_input_snapshot(
    *,
    profile: NfTribalProfile,
    spark: NfGrantSpark,
    pursuit: NfGrantPursuit,
    nofo_run: NfNofoExtractionRun | None,
) -> dict[str, Any]:
    """Canonical inputs used for preview + digest (deterministic)."""
    meta: dict[str, Any] | None = None
    if nofo_run and isinstance(nofo_run.structured_requirements, dict):
        meta = nofo_run.structured_requirements.get("metadata")
        if not isinstance(meta, dict):
            meta = None
    return {
        "tribal_profile_id": str(profile.id),
        "grant_spark_id": str(spark.id),
        "grant_pursuit_id": str(pursuit.id),
        "nofo_extraction_run_id": str(nofo_run.id) if nofo_run else None,
        "nofo_source_digest": nofo_run.source_text_digest if nofo_run else None,
        "profile": {
            "legal_name": profile.legal_name,
            "entity_type": profile.entity_type,
            "ein": profile.ein,
            "uei": profile.uei,
            "sam_registration_status": profile.sam_registration_status,
            "physical_address": profile.physical_address,
            "grants_manager": profile.grants_manager,
            "authorized_representative": profile.authorized_representative,
        },
        "spark": {
            "agency": spark.agency,
            "sub_agency": spark.sub_agency,
            "opportunity_title": spark.opportunity_title,
            "opportunity_number": spark.opportunity_number,
            "cfda_assistance_listing": spark.cfda_assistance_listing,
            "program_name": spark.program_name,
        },
        "pursuit": {
            "notes": pursuit.notes,
            "status": pursuit.status,
        },
        "nofo_metadata": meta,
    }


def build_sf424_preview(
    *,
    profile: NfTribalProfile,
    spark: NfGrantSpark,
    pursuit: NfGrantPursuit,
    nofo_run: NfNofoExtractionRun | None,
) -> tuple[dict[str, Any], str]:
    """Returns (preview document, input_digest sha256 hex)."""
    snap = build_input_snapshot(
        profile=profile,
        spark=spark,
        pursuit=pursuit,
        nofo_run=nofo_run,
    )
    digest = _json_digest(snap)

    applicant = applicant_type_for_entity(profile.entity_type)
    addr = _physical_address_block(profile.physical_address)
    gm = _contact_block(profile.grants_manager, source="tribal_profile.grants_manager")
    aor = _contact_block(
        profile.authorized_representative,
        source="tribal_profile.authorized_representative",
    )

    manual: list[str] = [
        "2_type_of_application",
        "5a_federal_entity_identifier",
        "15_descriptive_title_of_project",
        "16_congressional_districts",
        "17_proposed_project_period",
        "18_estimated_funding",
    ]

    nofo_title = None
    if snap.get("nofo_metadata") and isinstance(snap["nofo_metadata"], dict):
        nofo_title = snap["nofo_metadata"].get("opportunity_title")

    preview: dict[str, Any] = {
        "engine": PACKAGE_ENGINE,
        "form": "SF-424",
        "disclaimer": (
            "Preview only — not for submission. Human review required "
            "before Grants.gov."
        ),
        "fields": {
            "1_type_of_submission": {
                "value": "Application",
                "source": "default",
                "requires_review": False,
            },
            "2_type_of_application": {
                "value": None,
                "source": "manual",
                "requires_review": True,
            },
            "8a_legal_name": {
                "value": profile.legal_name,
                "source": "tribal_profile.legal_name",
                "requires_review": False,
            },
            "8b_employer_taxpayer_id": {
                "value": profile.ein,
                "source": "tribal_profile.ein",
                "requires_review": False,
            },
            "8c_uei": {
                "value": profile.uei,
                "source": "tribal_profile.uei",
                "requires_review": False,
            },
            "8d_physical_address": {
                "value": addr,
                "source": "tribal_profile.physical_address",
                "requires_review": False,
            },
            "8f_grants_manager_contact": {
                "value": gm,
                "source": "tribal_profile.grants_manager",
                "requires_review": True,
            },
            "9_type_of_applicant": {
                "value": applicant,
                "source": "derived_from.entity_type",
                "requires_review": applicant["requires_confirmation"],
            },
            "10_federal_agency": {
                "value": spark.agency,
                "source": "grant_spark.agency",
                "requires_review": False,
            },
            "11_cfda_number": {
                "value": spark.cfda_assistance_listing,
                "source": "grant_spark.cfda_assistance_listing",
                "requires_review": False,
            },
            "12_funding_opportunity_number": {
                "value": spark.opportunity_number,
                "source": "grant_spark.opportunity_number",
                "requires_review": False,
            },
            "14_opportunity_title_context": {
                "value": spark.opportunity_title,
                "source": "grant_spark.opportunity_title",
                "requires_review": False,
            },
            "15_descriptive_title_of_project": {
                "value": None,
                "source": "manual",
                "requires_review": True,
            },
            "21_authorized_representative": {
                "value": aor,
                "source": "tribal_profile.authorized_representative",
                "requires_review": True,
            },
        },
        "context": {
            "pursuit_notes": pursuit.notes,
            "nofo_summary_title": nofo_title,
            "sub_agency": spark.sub_agency,
            "program_name": spark.program_name,
        },
        "manual_entry_required": manual,
    }
    return preview, digest
