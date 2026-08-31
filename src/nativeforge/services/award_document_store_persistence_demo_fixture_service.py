"""Award document store persistence demo fixtures (Gate 127G).

Sixteen labelled cases exercised against a database that lives for the length of
one case, so the refusals are observed rather than asserted.

## What a fixture is allowed to be

```text
every identifier prefixed         nf-demo-fixture-
every fact_status                 demo_fixture
every production write            refused
rows in the application database  0
document bytes                    0
object store calls                0
```

No case has document contents, because no code path in this lane accepts any.
`prepare_document_write` has no `content` parameter, no file handle, and no path
it reads — the separation expressed as a signature.

## The three cases this set exists for

```text
object_key_refused_when_object_store_unconfigured  a key is a path into nothing
object_metadata_does_not_imply_content             a digest is a claim
customer_visible_false_by_default                  somebody decides that
```

The last is the quiet one. `customer_visible` is never derived — not from a
document being uploaded, not from a digest matching, not from the document being
the Tribe's own. A default of true shows a draft to the wrong person exactly
once, and there is no path in this repository that sets it without a caller
saying so.

## The store that does not exist

`object_key_refused_when_object_store_unconfigured` supplies a key and is
refused. The same case runs again with a store injected, so the refusal is a
measurement rather than a constant — and the injected branch is where a stored
document is demonstrated at all.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.award_document_store_persistence_validation_service import (
    detect_object_store_configured,
    validate_award_document,
    validation_invariant_failures,
    vocabulary_invariant_failures,
)
from nativeforge.services.award_document_store_repository_service import (
    AWARD_DOCUMENTS,
    archive_award_document,
    create_award_document,
    document_store_repository_invariant_failures,
    list_documents_for_organization,
    object_store_status,
    prepare_document_write,
)

SCHEMA_VERSION = "nf_award_document_store_persistence_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Fixed so the fixture set is reproducible. Not a real organization, not a real
# award, not a real document.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
DEMO_AWARDED_GRANT_ID = "2b4d6f80-1a3c-4e5f-8b9d-0c1e2f3a4b5c"
DEMO_REQUIREMENT_ID = "3c5e7f91-2b4d-4f60-9c0e-1d2f3a4b5c6d"
DEMO_PROOF_EVENT_ID = "4d6f80a2-3c5e-4071-ad1f-2e3f4a5b6c7d"
DEMO_IDENTITY_ID = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"
DEMO_HELD_DOCUMENT_ID = uuid.UUID("7a02c4d6-6f81-43a4-9042-5b6c7d8e9f01")

DEMO_TENANT_LABEL = FIXTURE_PREFIX + "sc-tenant"
DEMO_CUSTOMER_ORG_LABEL = FIXTURE_PREFIX + "sc-customer-org"
DEMO_PROFILE_ID_LABEL = FIXTURE_PREFIX + "org-profile"
DEMO_SOURCE_REF = FIXTURE_PREFIX + "intake-2026-q1"
DEMO_OBJECT_KEY = FIXTURE_PREFIX + "org/req/sf425-2026-q1.pdf"
DEMO_BUCKET = FIXTURE_PREFIX + "documents"

# 64 hex characters. A digest of nothing this module has ever read.
DEMO_DIGEST = "d" * 64

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)

# One document reference, every field supplied, every fact marked as a fixture.
DEMO_DOCUMENT: dict[str, Any] = {
    "organization_id": DEMO_ORGANIZATION_ID,
    "award_requirement_id": DEMO_REQUIREMENT_ID,
    "document_kind": "financial_report",
    "document_status": "reference_recorded",
    "document_title": "Demo SF-425 for Q1 2026",
    "document_description": "Demo metadata. No document exists behind it.",
    "document_source": "tenant_supplied",
    "document_source_ref": DEMO_SOURCE_REF,
    "content_type": "application/pdf",
    "content_length": 148213,
    "sha256_digest": DEMO_DIGEST,
    "retention_class": "retain_1_year",
    "fact_status": FIXTURE_LABEL,
    "created_by_identity_id": DEMO_IDENTITY_ID,
    "is_demo": True,
}

REQUIRED_CASES: tuple[str, ...] = (
    "valid_metadata_only_requirement_document",
    "valid_metadata_only_proof_event_document",
    "missing_document_title_refused",
    "no_relationship_refused",
    "object_key_refused_when_object_store_unconfigured",
    "object_metadata_does_not_imply_content",
    "document_reference_does_not_imply_proof_accepted",
    "customer_visible_false_by_default",
    "legal_hold_prevents_archive",
    "award_requirement_id_cannot_substitute_for_organization_id",
    "proof_event_id_cannot_substitute_for_organization_id",
    "awarded_grant_id_cannot_substitute_for_organization_id",
    "tenant_id_refused_as_anchor",
    "customer_org_id_refused_as_anchor",
    "organization_profile_id_refused_as_anchor",
    "customer_auth_live_false_blocks_production_write",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    AWARD_DOCUMENTS.create(engine)
    return engine


def build_demo_document_cases() -> list[dict[str, Any]]:
    """Sixteen labelled cases. Five storable, eleven refused."""
    cases: list[dict[str, Any]] = []

    def case(
        name: str,
        why: str,
        *,
        expect_storage_allowed: bool,
        expect_production_write: bool,
        result: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> None:
        cases.append(
            {
                "case": name,
                "fixture_label": FIXTURE_LABEL,
                "why": why,
                "expect_storage_allowed": expect_storage_allowed,
                "expect_production_write": expect_production_write,
                "result": result,
                "extra": extra or {},
            }
        )

    case(
        "valid_metadata_only_requirement_document",
        (
            "a reference attached to a requirement, with a digest and a length "
            "somebody supplied. Storable, and nothing behind it: no bytes, no "
            "key, no store"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_document_write(**DEMO_DOCUMENT),
    )

    case(
        "valid_metadata_only_proof_event_document",
        (
            "the same reference attached to a proof event instead. Any one of "
            "the three relationships is enough, because an award-level document "
            "no requirement has claimed yet is ordinary"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_document_write(
            **{
                **DEMO_DOCUMENT,
                "award_requirement_id": None,
                "proof_event_id": DEMO_PROOF_EVENT_ID,
                "document_kind": "narrative_report",
                "document_title": "Demo narrative report filed as proof",
            }
        ),
    )

    case(
        "missing_document_title_refused",
        (
            "the one field that cannot be unknown. A document nobody can name "
            "is a document nobody can find, and the database agrees"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_document_write(**{**DEMO_DOCUMENT, "document_title": "   "}),
    )

    case(
        "no_relationship_refused",
        (
            "no award, no requirement, no proof event. A document attached to "
            "nothing is a file in a drawer nobody can find, and the CHECK "
            "requires at least one"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_document_write(
            **{**DEMO_DOCUMENT, "award_requirement_id": None}
        ),
    )

    # The permitted branch, run only to prove the refusal below is falsifiable.
    with_store = validate_award_document(
        document_kind="financial_report",
        document_status="stored",
        document_title="Demo SF-425 for Q1 2026",
        document_source="tenant_supplied",
        award_requirement_id=DEMO_REQUIREMENT_ID,
        object_key=DEMO_OBJECT_KEY,
        object_bucket=DEMO_BUCKET,
        object_store_provider="s3_compatible",
        sha256_digest=DEMO_DIGEST,
        content_length=148213,
        retention_class="retain_1_year",
        fact_status=FIXTURE_LABEL,
        object_store_configured=True,
    )
    case(
        "object_key_refused_when_object_store_unconfigured",
        (
            "a key with no store behind it is a path into nothing, and "
            "downstream it reads as 'the file is at this location'. The same "
            "document with a store injected is permitted, so the refusal is a "
            "measurement rather than a constant"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_document_write(
            **{**DEMO_DOCUMENT, "object_key": DEMO_OBJECT_KEY}
        ),
        extra={
            "with_store_blocked": with_store["blocked_reasons"],
            "with_store_is_stored": with_store["document_is_stored"],
            "with_store_configured": with_store["object_store_configured"],
        },
    )

    metadata = prepare_document_write(**DEMO_DOCUMENT)
    case(
        "object_metadata_does_not_imply_content",
        (
            "a digest, a length and a content type, and no document. All three "
            "are claims somebody made; none is evidence the file exists, and "
            "content_verified is a constant False because verifying a digest "
            "means reading bytes"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=metadata,
        extra={
            "digest_is_unverified": metadata["validation"]["digest_is_unverified"],
            "content_verified": metadata["validation"]["content_verified"],
            "document_is_metadata_only": metadata["document_is_metadata_only"],
        },
    )

    proof_doc = prepare_document_write(
        **{
            **DEMO_DOCUMENT,
            "award_requirement_id": None,
            "proof_event_id": DEMO_PROOF_EVENT_ID,
        }
    )
    case(
        "document_reference_does_not_imply_proof_accepted",
        (
            "a document attached to a proof event, and the event's own status "
            "is untouched. Gate 126 owns whether a funder accepted anything; "
            "this lane records what was attached and nothing more"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=proof_doc,
        extra={
            "acceptance_inferred_from_document": proof_doc[
                "acceptance_inferred_from_document"
            ]
        },
    )

    default_visibility = prepare_document_write(**DEMO_DOCUMENT)
    case(
        "customer_visible_false_by_default",
        (
            "nobody asked for it, so it is false. Never derived from upload "
            "status, from a digest, or from the document being the Tribe's "
            "own: a default of true shows a draft to the wrong person exactly "
            "once"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=default_visibility,
        extra={
            "customer_visible": default_visibility["customer_visible"],
            "visibility_inferred_from_upload": default_visibility[
                "visibility_inferred_from_upload"
            ],
        },
    )

    # -- legal hold refuses archive ------------------------------------------
    engine = _memory_engine()
    with engine.begin() as connection:
        create_award_document(
            connection=connection,
            document_id=DEMO_HELD_DOCUMENT_ID,
            now=NOW,
            **{
                **DEMO_DOCUMENT,
                "legal_hold": True,
                "document_kind": "audit_report",
                "document_title": "Demo audit workpapers under legal hold",
            },
        )
        held = archive_award_document(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            document_id=str(DEMO_HELD_DOCUMENT_ID),
            archived_by_identity_id=DEMO_IDENTITY_ID,
            now=NOW,
        )
        after_hold = list_documents_for_organization(
            connection=connection, organization_id=DEMO_ORGANIZATION_ID
        )
        rows_after_hold = connection.execute(
            sa.select(sa.func.count()).select_from(AWARD_DOCUMENTS)
        ).scalar()
    engine.dispose()

    case(
        "legal_hold_prevents_archive",
        (
            "a lawyer said this must not move. Archiving is the only lifecycle "
            "operation this table has, and legal hold refuses it - in the "
            "repository and again in the database"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=held,
        extra={
            "rows_after_hold": int(rows_after_hold or 0),
            "archived_count": int(after_hold["archived_count"]),
            "legal_hold_count": int(after_hold["legal_hold_count"]),
            "still_listed": int(after_hold["rows_read"]),
        },
    )

    for label, field, value in (
        (
            "award_requirement_id_cannot_substitute_for_organization_id",
            "award_requirement_id",
            DEMO_REQUIREMENT_ID,
        ),
        (
            "proof_event_id_cannot_substitute_for_organization_id",
            "proof_event_id",
            DEMO_PROOF_EVENT_ID,
        ),
        (
            "awarded_grant_id_cannot_substitute_for_organization_id",
            "awarded_grant_id",
            DEMO_AWARDED_GRANT_ID,
        ),
    ):
        case(
            label,
            (
                "the relationship is supplied and the organization is not. "
                "Refused under its own name: the RLS predicate reads "
                "organization_id, and reaching it through whichever of three "
                "joins happened to be populated would make this table's policy "
                "depend on three other tables' policies"
            ),
            expect_storage_allowed=False,
            expect_production_write=False,
            result=prepare_document_write(
                **{
                    **DEMO_DOCUMENT,
                    "organization_id": None,
                    "award_requirement_id": None,
                    field: value,
                }
            ),
        )

    for label, kwargs in (
        ("tenant_id_refused_as_anchor", {"tenant_id": DEMO_TENANT_LABEL}),
        (
            "customer_org_id_refused_as_anchor",
            {"customer_org_id": DEMO_CUSTOMER_ORG_LABEL},
        ),
        (
            "organization_profile_id_refused_as_anchor",
            {"organization_profile_id": DEMO_PROFILE_ID_LABEL},
        ),
    ):
        case(
            label,
            (
                "refused by name rather than ignored, so a caller who sent one "
                "is told which identity space it was in"
            ),
            expect_storage_allowed=False,
            expect_production_write=False,
            result=prepare_document_write(**DEMO_DOCUMENT, **kwargs),
        )

    case(
        "customer_auth_live_false_blocks_production_write",
        (
            "the same reference with fact_status verified instead of "
            "demo_fixture, which makes it a production write. Both gates are "
            "named separately, because auth arriving without a verified "
            "binding would still not be enough"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_document_write(
            **{**DEMO_DOCUMENT, "fact_status": "verified", "is_demo": False}
        ),
    )

    return cases


def measure_document_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def _agrees(case: dict[str, Any]) -> bool:
    result = case["result"]
    return bool(
        bool(result["storage_allowed"]) is bool(case["expect_storage_allowed"])
        and bool(result["production_write_allowed"])
        is bool(case["expect_production_write"])
    )


def build_document_store_fixture_set() -> dict[str, Any]:
    """The sixteen cases, measured."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )

    cases = build_demo_document_cases()
    covered = measure_document_cases(cases)

    # Measured once, from the real environment, so the set can state plainly
    # that no fixture moved any of them.
    gate = build_customer_auth_activation_gate()
    binding = build_binding_store_readiness()
    store = object_store_status()

    rows: list[dict[str, Any]] = []
    for case in cases:
        result = case["result"]
        extra = case["extra"]
        validation = result.get("validation") or {}
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "why": case["why"],
                "operation": result["operation"],
                "storage_allowed": bool(result["storage_allowed"]),
                "production_write_allowed": bool(result["production_write_allowed"]),
                "write_performed": bool(result["write_performed"]),
                "rows_written": int(result["rows_written"]),
                "document_kind": result.get("document_kind"),
                "document_status": result.get("document_status"),
                "document_source": result.get("document_source"),
                "relationship_present": bool(result.get("relationship_present")),
                "relationship_count": int(result.get("relationship_count") or 0),
                "object_store_configured": bool(result.get("object_store_configured")),
                "object_key_present": bool(result.get("object_key")),
                "document_is_stored": bool(result.get("document_is_stored")),
                "document_is_metadata_only": bool(
                    result.get("document_is_metadata_only", True)
                ),
                "legal_hold": bool(result.get("legal_hold")),
                "archivable": bool(result.get("archivable", True)),
                "customer_visible": bool(result.get("customer_visible")),
                "retention_class": result.get("retention_class"),
                "fact_status": result.get("fact_status"),
                "human_review_required": bool(result["human_review_required"]),
                "rows_deleted": int(result["rows_deleted"]),
                "agrees_with_expectation": _agrees(case),
                "refused_claims": list(result.get("refused_claims") or []),
                "blocked_reasons": list(result["blocked_reasons"]),
                "invariant_failures": document_store_repository_invariant_failures(
                    result
                ),
                "validation_invariant_failures": (
                    validation_invariant_failures(validation) if validation else []
                ),
                # Per-case extras, present only where the case demonstrates one.
                "with_store_blocked": extra.get("with_store_blocked"),
                "with_store_is_stored": extra.get("with_store_is_stored"),
                "with_store_configured": extra.get("with_store_configured"),
                "digest_is_unverified": extra.get("digest_is_unverified"),
                "content_verified": extra.get("content_verified"),
                "rows_after_hold": extra.get("rows_after_hold"),
                "legal_hold_count": extra.get("legal_hold_count"),
                "still_listed": extra.get("still_listed"),
                "archived_count": extra.get("archived_count"),
                # Constant across every case.
                "customer_auth_live": False,
                "production_document_records_created": 0,
                "document_bytes_written": 0,
                "object_store_contacted": False,
                "document_content_read": False,
            }
        )

    missing = [name for name in REQUIRED_CASES if name not in covered]
    disagreeing = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "case_count": len(rows),
            "cases": rows,
            "document_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "storable_count": sum(1 for r in rows if r["storage_allowed"]),
            "production_write_count": sum(
                1 for r in rows if r["production_write_allowed"]
            ),
            "stored_count": sum(1 for r in rows if r["document_is_stored"]),
            "metadata_only_count": sum(
                1 for r in rows if r["document_is_metadata_only"]
            ),
            "customer_visible_count": sum(1 for r in rows if r["customer_visible"]),
            "legal_hold_count": sum(1 for r in rows if r["legal_hold"]),
            "invariant_failures": sorted(
                {
                    f
                    for r in rows
                    for f in (
                        *r["invariant_failures"],
                        *r["validation_invariant_failures"],
                    )
                }
            ),
            "vocabulary_invariant_failures": vocabulary_invariant_failures(),
            # The real environment, measured once and unmoved by any of this.
            "actual_customer_auth_live": bool(gate["customer_auth_live"]),
            "actual_verified_operational_binding": bool(
                binding["operational_verified_binding"]
            ),
            "actual_object_store_configured": bool(store["object_store_configured"]),
            "actual_body_store_mode": store["body_store_mode"],
            # Constants. A fixture set demonstrates; it stores nothing real and
            # opens nothing at all.
            "customer_auth_live": False,
            "login_live": False,
            "customer_persistence_live": False,
            "awarded_grants_operational_tracking_live": False,
            "document_storage_operational": False,
            "object_store_configured": detect_object_store_configured(),
            "object_store_contacted": False,
            "document_content_read": False,
            "document_bytes_written": 0,
            "beta_onboarding_ready": False,
            "production_document_records_created": 0,
            "production_proof_records_created": 0,
            "production_award_requirements_created": 0,
            "real_customer_data_written": 0,
            "application_database_touched": False,
            "rows_deleted": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def document_store_fixture_invariant_failures(
    fixture: dict[str, Any],
) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("document_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_its_own_service_invariants")

    if fixture.get("vocabulary_invariant_failures"):
        fails.append("a_bridged_vocabulary_drifted")

    for constant in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "awarded_grants_operational_tracking_live",
        "document_storage_operational",
        "object_store_configured",
        "object_store_contacted",
        "document_content_read",
        "beta_onboarding_ready",
        "application_database_touched",
        "persisted",
        "fabricated",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"fixture_set_claimed:{constant}")

    if fixture.get("document_bytes_written"):
        fails.append("a_fixture_set_wrote_document_bytes")

    for row in rows:
        label = row.get("case")
        if row.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"case_not_labelled_as_a_fixture:{label}")
        if row.get("production_write_allowed"):
            fails.append(f"a_fixture_permitted_a_production_write:{label}")
        if row.get("customer_auth_live"):
            fails.append(f"a_fixture_claimed_auth_is_live:{label}")
        if row.get("rows_deleted"):
            fails.append(f"a_fixture_deleted_a_row:{label}")
        if row.get("production_document_records_created"):
            fails.append(f"a_fixture_created_a_production_document:{label}")
        if row.get("object_store_contacted"):
            fails.append(f"a_fixture_contacted_an_object_store:{label}")
        if row.get("document_content_read"):
            fails.append(f"a_fixture_read_a_document:{label}")
        if row.get("document_bytes_written"):
            fails.append(f"a_fixture_wrote_document_bytes:{label}")
        # A key with no store never survives into a row.
        if row.get("object_key_present") and not row.get("object_store_configured"):
            if row.get("storage_allowed"):
                fails.append(f"a_storable_key_without_a_store:{label}")
        if row.get("legal_hold") and row.get("archivable"):
            fails.append(f"a_held_document_was_archivable:{label}")

    # Nothing in this set is stored, because there is nowhere to store it.
    if fixture.get("stored_count"):
        fails.append("a_fixture_document_was_reported_as_stored")

    # A key is a path into nothing.
    document = [
        r
        for r in rows
        if r["case"] == "object_key_refused_when_object_store_unconfigured"
    ]
    if not document:
        fails.append("the_object_key_case_is_missing")
    else:
        row = document[0]
        if row.get("storage_allowed"):
            fails.append("an_object_key_was_stored_without_a_store")
        if row.get("with_store_blocked"):
            fails.append("the_object_key_refusal_is_not_falsifiable")
        if row.get("with_store_configured") is not True:
            fails.append("the_injected_object_store_was_not_observed")
        if row.get("with_store_is_stored") is not True:
            fails.append("the_injected_store_did_not_produce_a_stored_document")

    # A digest is a claim.
    metadata = [
        r for r in rows if r["case"] == "object_metadata_does_not_imply_content"
    ]
    if not metadata:
        fails.append("the_object_metadata_case_is_missing")
    else:
        row = metadata[0]
        if row.get("content_verified"):
            fails.append("a_fixture_claimed_it_verified_content")
        if not row.get("digest_is_unverified"):
            fails.append("a_digest_with_no_bytes_was_not_named_unverified")
        if not row.get("document_is_metadata_only"):
            fails.append("the_metadata_case_was_not_metadata_only")

    # Visibility is decided.
    visible = [r for r in rows if r["case"] == "customer_visible_false_by_default"]
    if not visible:
        fails.append("the_customer_visible_case_is_missing")
    elif visible[0].get("customer_visible"):
        fails.append("customer_visible_defaulted_to_true")
    if fixture.get("customer_visible_count"):
        fails.append("a_fixture_document_was_customer_visible")

    # Legal hold refuses archive.
    held = [r for r in rows if r["case"] == "legal_hold_prevents_archive"]
    if not held:
        fails.append("the_legal_hold_case_is_missing")
    else:
        row = held[0]
        if row.get("storage_allowed"):
            fails.append("a_held_document_was_archived")
        if row.get("rows_after_hold") != 1:
            fails.append("the_held_document_left_the_table")
        if row.get("archived_count"):
            fails.append("a_held_document_was_reported_as_archived")
        if row.get("still_listed") != 1:
            fails.append("the_held_document_left_the_listing")

    return sorted(set(fails))
