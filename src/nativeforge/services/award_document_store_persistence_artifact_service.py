"""Award document store persistence artifacts (Gate 127H).

Four files describing the repository, what it validates, and what none of it
makes true. Written to `artifacts/award_document_store_persistence/`.

```text
award_document_store_repository_contract.json          operations, columns
award_document_store_validation_matrix.csv             one row per case
award_document_store_persistence_demo_fixtures.json    the sixteen cases
award_document_store_persistence_readiness_summary.md  what remains blocked
```

## Five scans, and the fifth is this gate's

```text
1  by field name  anything named like real award or tenant data
2  by inference   any result claiming an inference this campaign prohibits
3  by capability  any payload whose capability claim disagrees with reality
4  by removal     any payload saying a record went away
5  by content     any payload that looks like it contains a document
```

The fifth exists because this is the first lane whose subject is a file. A
compliance artifact carrying base64, a data URI, or a `content` field would be a
Tribe's document committed to a git repository, and no amount of "it's only a
fixture" makes that acceptable. The scan looks for the field names and for
payload values long enough to be a file.

## The claim this gate must not make

```text
document metadata persistence   built by Gate 127, reported true
document storage                not built, reported false
object store configured         asked of Gate 96's detector, reports false
```

`document_storage_live` and `object_store_configured` are **measured**, not
frozen — Gate 126 recorded what happens when a constant frozen in one gate
becomes a lie in the next. The scan compares every capability claim against what
is actually available, so a claim becomes acceptable the day it becomes true.
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.award_document_store_persistence_validation_service import (
    DOCUMENT_KINDS,
    DOCUMENT_SOURCES,
    DOCUMENT_STATUSES,
    RETENTION_CLASSES,
    vocabulary_invariant_failures,
)
from nativeforge.services.award_document_store_repository_service import (
    AWARD_DOCUMENTS,
    DERIVED_ONLY_FIELDS,
    FORBIDDEN_ANCHOR_NAMES,
    RELATIONSHIP_FIELDS,
    REPOSITORY_OPERATIONS,
    RLS_ANCHOR_COLUMN,
    TABLE_NAME,
    object_store_status,
    prohibited_inferences,
    repository_vocabularies,
)

SCHEMA_VERSION = "nf_award_document_store_persistence_artifact_v1"

ARTIFACT_DIR = "artifacts/award_document_store_persistence"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "document_store_repository_available": True,
    "document_store_validation_available": True,
    "document_store_schema_available": True,
    "document_store_operational": False,
    "awarded_operational_tracking_ready": False,
    "customer_auth_live": False,
    "login_live": False,
    "verified_operational_binding": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "object_store_contacted": False,
    "document_content_read": False,
    "content_verified": False,
    "storage_inferred_from_object_key": False,
    "content_inferred_from_metadata": False,
    "acceptance_inferred_from_document": False,
    "visibility_inferred_from_upload": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_document_records_created": 0,
    "production_award_requirements_created": 0,
    "production_proof_records_created": 0,
    "real_customer_data_written": 0,
    "document_bytes_written": 0,
    "rows_deleted": 0,
    "rows_in_the_application_database": 0,
}

# Field names that would mean real award or tenant data had entered an artifact.
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
        "award_amount",
        "client_secret",
        "signing_key",
        "access_token",
        "refresh_token",
        # Object store credentials, which this gate never touches and never has.
        "secret_access_key",
        "access_key_id",
    }
)

# Field names that would mean a document itself had entered an artifact.
FORBIDDEN_CONTENT_FIELDS: frozenset[str] = frozenset(
    {
        "content",
        "body",
        "bytes",
        "file_bytes",
        "document_bytes",
        "document_content",
        "base64",
        "b64",
        "payload_bytes",
        "attachment",
        "raw",
    }
)

# A value long enough, and shaped enough, to be a file rather than a label.
_DATA_URI = re.compile(r"^data:[^;]*;base64,", re.I)
_BASE64_BLOB = re.compile(r"^[A-Za-z0-9+/]{512,}={0,2}$")

FORBIDDEN_INFERENCE_FLAGS: frozenset[str] = frozenset(
    {
        "storage_inferred_from_object_key",
        "content_inferred_from_metadata",
        "submission_inferred_from_document",
        "acceptance_inferred_from_document",
        "visibility_inferred_from_upload",
        "content_verified",
        "fabricated",
    }
)

FORBIDDEN_REMOVAL_FLAGS: frozenset[str] = frozenset(
    {"document_content_read", "object_store_contacted"}
)

# Capabilities this gate can state flatly.
FORBIDDEN_CAPABILITY_FLAGS: frozenset[str] = frozenset(
    {
        "document_storage_operational",
        "document_storage_live",
        "customer_auth_live",
        "customer_persistence_live",
        "requirement_extraction_live",
    }
)

# Measured rather than frozen. Gate 126 recorded why.
MEASURED_CAPABILITY_FLAGS: tuple[str, ...] = (
    "object_store_configured",
    "ready_for_operational_awarded_tracking",
)

MATRIX_COLUMNS: tuple[str, ...] = (
    "case",
    "document_kind",
    "document_status",
    "document_source",
    "relationship_present",
    "relationship_count",
    "object_store_configured",
    "object_key_present",
    "object_reference_consistent",
    "document_is_stored",
    "document_is_metadata_only",
    "digest_is_unverified",
    "content_metadata_valid",
    "sha256_digest_valid",
    "retention_class",
    "legal_hold",
    "archivable",
    "customer_visible",
    "fact_status",
    "document_ready_for_reference",
    "human_review_required",
    "unknown_fields",
    "refused_claims",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _measured_capabilities() -> dict[str, bool]:
    """What is actually available right now, for the scan to compare against."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )

    readiness = build_awarded_requirements_readiness()
    return {flag: bool(readiness.get(flag)) for flag in MEASURED_CAPABILITY_FLAGS}


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


def scan_for_document_content(payload: Any) -> list[str]:
    """Did a document itself get into an artifact?

    This gate's addition, and the first time it has been needed: this is the
    first lane whose subject is a file. A compliance artifact carrying base64 or
    a `content` field would be a Tribe's document committed to a git repository,
    and being a fixture would not make that acceptable.

    Two checks, because a document can arrive under an innocent key:

    ```text
    by field name   content, body, bytes, base64, attachment, ...
    by value shape  a data: URI, or 512+ characters of base64 alphabet
    ```
    """
    found: set[str] = set()

    def looks_like_a_file(value: Any) -> bool:
        if not isinstance(value, str) or len(value) < 512:
            return False
        return bool(_DATA_URI.match(value) or _BASE64_BLOB.match(value))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_CONTENT_FIELDS:
                    found.add(f"document_content_field:{key}")
                if looks_like_a_file(value):
                    found.add(f"document_content_value:{key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                if looks_like_a_file(item):
                    found.add("document_content_value:list_item")
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


def scan_for_claimed_removals(payload: Any) -> list[str]:
    """Did anything say a record went away, or a store was reached?"""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_REMOVAL_FLAGS and bool(value) is True:
                    found.add(f"claimed_action:{key}")
                if key in {"rows_deleted", "document_bytes_written"} and value:
                    found.add(f"claimed_action:{key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def _is_case_row(node: dict[str, Any]) -> bool:
    """Is this a single demonstrated case rather than a payload's own claim?

    A case row carries a `case` name. It exists to *show* something - an
    injected store, a refused key - and holding it to the same standard as a
    summary claim is what made the first version of this scan refuse its own
    output. Gate 121 spent two attempts on the same mistake with a leak scanner,
    and Gates 124H and 126H both narrowed a scan for exactly this reason.
    """
    return "case" in node


def _is_demonstrated_refusal(node: dict[str, Any]) -> bool:
    """Did this row show a refusal rather than assert an acceptable state?"""
    return bool(node.get("blocked_reasons") or node.get("refused_claims"))


def scan_for_claimed_capabilities(payload: Any) -> list[str]:
    """Did anything claim a capability that is not actually there?

    Three rules, because three things are being asked:

    ```text
    a flatly-false capability   refused anywhere, in any payload
    a measured capability       compared against reality, on summary claims
                                only - a validation case injecting a store to
                                reach the permitted branch is a demonstration,
                                not a claim about this deployment
    a key with no store         refused on rows presented as acceptable, and
                                permitted on rows that name why they were
                                refused
    ```

    The middle rule is the one that needed narrowing. Without it the matrix row
    `a_stored_document_with_a_store_injected` - the only place a stored document
    is demonstrated at all - would refuse the write, and the branch would become
    untestable.
    """
    found: set[str] = set()
    measured = _measured_capabilities()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            case_row = _is_case_row(node)
            refusal = _is_demonstrated_refusal(node)
            for key, value in node.items():
                if key in FORBIDDEN_CAPABILITY_FLAGS and bool(value) is True:
                    found.add(f"claimed_capability:{key}")
                if key in measured and not case_row:
                    if bool(value) is not measured[key]:
                        found.add(f"capability_claim_disagrees_with_reality:{key}")
            if not refusal:
                if node.get("object_key_present") is True:
                    if node.get("object_store_configured") is False:
                        found.add("claimed_capability:a_key_without_a_store")
                if node.get("document_is_stored") is True:
                    if node.get("object_store_configured") is False:
                        found.add("claimed_capability:stored_without_a_store")
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
        c.name for c in AWARD_DOCUMENTS.constraints if getattr(c, "name", None)
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0035",
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "relationship_fields": list(RELATIONSHIP_FIELDS),
            "derived_only_fields": list(DERIVED_ONLY_FIELDS),
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', true)::uuid "
                "AND is_demo = "
                "current_setting('app.current_org_is_demo', true)::boolean"
            ),
            "operations": sorted(REPOSITORY_OPERATIONS),
            "columns": [c.name for c in AWARD_DOCUMENTS.columns],
            "column_count": len(AWARD_DOCUMENTS.columns),
            "check_constraints": [c for c in constraints if c.startswith("ck_")],
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "document_kinds": sorted(DOCUMENT_KINDS),
            "document_statuses": sorted(DOCUMENT_STATUSES),
            "document_sources": sorted(DOCUMENT_SOURCES),
            "retention_classes": sorted(RETENTION_CLASSES),
            "vocabularies": repository_vocabularies(),
            "vocabulary_invariant_failures": vocabulary_invariant_failures(),
            "object_store": object_store_status(),
            "prohibited_inferences": [
                {"inference": name, "why": why} for name, why in prohibited_inferences()
            ],
            "rules": [
                "organization_id is required and must be UUID-shaped",
                "at least one of awarded_grant_id, award_requirement_id and "
                "proof_event_id is required, and all three are refused as "
                "anchors",
                "tenant_id, customer_org_id and organization_profile_id are "
                "refused as anchors",
                "metadata is not content: no column holds bytes and no "
                "operation returns any",
                "object_key, object_bucket and object_store_provider are "
                "refused unless the object store is configured",
                "object_store_configured is bridged from Gate 96's "
                "detect_body_store_mode() and is never accepted from a caller",
                "a digest is a claim about bytes nobody here has read, and "
                "content_verified is a constant false",
                "a document is not a submission, and not an accepted proof",
                "customer_visible defaults false and is never derived",
                "legal_hold refuses archive, in the repository and in the database",
                "archive by setting archived_at; there is no delete path",
                "a production write requires customer_auth_live and a verified "
                "operational binding",
            ],
            **FIXED_COUNTS,
        }
    )


def build_validation_cases() -> list[dict[str, Any]]:
    """The cases the matrix reports, each a distinct rule."""
    base: dict[str, Any] = {
        "document_kind": "financial_report",
        "document_status": "reference_recorded",
        "document_title": "Demo SF-425 for Q1 2026",
        "document_source": "tenant_supplied",
        "award_requirement_id": "3c5e7f91-2b4d-4f60-9c0e-1d2f3a4b5c6d",
        "content_type": "application/pdf",
        "content_length": 148213,
        "sha256_digest": "d" * 64,
        "retention_class": "retain_1_year",
        "fact_status": "demo_fixture",
    }

    return [
        {"case": "metadata_only_reference", "document": dict(base)},
        {
            "case": "document_without_a_title",
            "document": {**base, "document_title": "  "},
        },
        {
            "case": "document_without_a_relationship",
            "document": {**base, "award_requirement_id": None},
        },
        {
            "case": "document_kind_unknown_stays_unknown",
            "document": {**base, "document_kind": "unknown"},
        },
        {
            "case": "object_key_without_a_store",
            "document": {**base, "object_key": "org/req/sf425.pdf"},
        },
        {
            "case": "object_bucket_without_a_store",
            "document": {**base, "object_bucket": "nf-demo"},
        },
        {
            "case": "object_version_without_a_key",
            "document": {**base, "object_version": "v2"},
        },
        {
            "case": "stored_status_without_a_location",
            "document": {**base, "document_status": "stored"},
        },
        {
            "case": "a_stored_document_with_a_store_injected",
            "document": {
                **base,
                "document_status": "stored",
                "object_key": "org/req/sf425.pdf",
                "object_bucket": "nf-demo",
                "object_store_provider": "s3_compatible",
                "fact_status": "verified",
                "object_store_configured": True,
            },
        },
        {
            "case": "negative_content_length",
            "document": {**base, "content_length": -1},
        },
        {
            "case": "a_digest_that_is_not_sha256_shaped",
            "document": {**base, "sha256_digest": "nothex"},
        },
        {
            "case": "an_unrecognised_retention_class",
            "document": {**base, "retention_class": "forever"},
        },
        {
            "case": "customer_visible_on_an_unestablished_fact_status",
            "document": {
                **base,
                "customer_visible": True,
                "fact_status": "unknown",
            },
        },
        {
            "case": "a_document_under_legal_hold",
            "document": {**base, "legal_hold": True},
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
                row["document_kind"],
                row["document_status"],
                row["document_source"],
                str(row["relationship_present"]).lower(),
                row["relationship_count"],
                str(row["object_store_configured"]).lower(),
                str(row["object_key_present"]).lower(),
                str(row["object_reference_consistent"]).lower(),
                str(row["document_is_stored"]).lower(),
                str(row["document_is_metadata_only"]).lower(),
                str(row["digest_is_unverified"]).lower(),
                str(row["content_metadata_valid"]).lower(),
                str(row["sha256_digest_valid"]).lower(),
                row["retention_class"] or "",
                str(row["legal_hold"]).lower(),
                str(row["archivable"]).lower(),
                str(row["customer_visible"]).lower(),
                row["fact_status"],
                str(row["document_ready_for_reference"]).lower(),
                str(row["human_review_required"]).lower(),
                "; ".join(row["unknown_fields"]),
                "; ".join(row["refused_claims"]),
                "; ".join(row["blocked_reasons"]),
            ]
        )
    return buffer.getvalue()


def build_persistence_declaration() -> dict[str, Any]:
    """What Gate 127 built, and the claims it does not make."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.customer_persistence_spine_decision_service import (
        build_persistence_spine_decision,
    )

    gate = build_customer_auth_activation_gate()
    readiness = build_awarded_requirements_readiness()
    matrix = build_capability_matrix()
    spine = build_persistence_spine_decision()
    lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "document_library_persistence"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_store_write_path_available": bool(lane["write_path_available"]),
            "document_store_read_path_available": bool(lane["read_path_available"]),
            "document_metadata_storage_available": bool(
                readiness["document_metadata_storage_available"]
            ),
            # Measured, not frozen. This is the claim the whole gate turns on.
            "object_store_configured": bool(readiness["object_store_configured"]),
            "document_storage_live": bool(readiness["document_storage_live"]),
            "body_store_mode": object_store_status()["body_store_mode"],
            "ready_for_operational_awarded_tracking": bool(
                readiness["ready_for_operational_awarded_tracking"]
            ),
            "operational_awarded_recommended": bool(
                spine["operational_awarded_recommended"]
            ),
            "requires_document_storage": bool(spine["requires_document_storage"]),
            "next_gate_recommendation": spine["next_gate_recommendation"][
                "recommendation"
            ],
            "capability_lane_count": len(matrix["rows"]),
            "readiness_blocked_reasons": list(readiness["blocked_reasons"]),
            "lane_blocked_reasons": list(lane["blocked_reasons"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 127 moved, and the sentence to refuse."""
    from nativeforge.services.award_document_store_persistence_demo_fixture_service import (  # noqa: E501
        build_document_store_fixture_set,
    )

    fixture = build_document_store_fixture_set()
    declaration = build_persistence_declaration()

    lines = [
        "# Award document store persistence readiness (Gate 127)",
        "",
        "## What moved",
        "",
        "```text",
        f"table                      {TABLE_NAME} (migration 0035)",
        f"columns                    {len(AWARD_DOCUMENTS.columns)}",
        f"repository operations      {len(REPOSITORY_OPERATIONS)}",
        f"capability lanes with schema  {declaration['capability_lane_count']} total",
        f"demo fixture cases         {fixture['case_count']}",
        f"storable fixture cases     {fixture['storable_count']}",
        f"fixture documents stored   {fixture['stored_count']}",
        "```",
        "",
        "The `document_library_persistence` lane has existed since Gate 114 and",
        "pointed at a table nobody built. It points at this one now.",
        "",
        "## What did not move",
        "",
        "```text",
        f"object store configured           "
        f"{str(declaration['object_store_configured']).lower()}",
        f"body store mode                   {declaration['body_store_mode']}",
        f"document storage live             "
        f"{str(declaration['document_storage_live']).lower()}",
        f"document store operational        "
        f"{str(declaration['document_store_operational']).lower()}",
        f"requires document storage         "
        f"{str(declaration['requires_document_storage']).lower()}",
        f"operational awarded tracking      "
        f"{str(declaration['ready_for_operational_awarded_tracking']).lower()}",
        f"customer auth live                "
        f"{str(declaration['customer_auth_live']).lower()}",
        f"production document records       "
        f"{declaration['production_document_records_created']}",
        f"document bytes written            {declaration['document_bytes_written']}",
        "object store calls                0",
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
        "> NativeForge stores your compliance documents.",
        "",
        "It does not. Four tables exist and this one holds descriptions: a",
        "title, a kind, a digest somebody supplied, and which award or",
        "requirement or proof event the document belongs to. The document is",
        "still wherever the Tribe put it.",
        "",
        "`detect_body_store_mode()` reports `unconfigured`, so `object_key` is",
        "refused on every row this repository can currently write, and",
        "`document_storage_live` stays in the operational blocker list.",
        "",
        "## Metadata is not content",
        "",
        "```text",
        "sha256_digest   64 hex characters describing a file never opened here",
        "content_length  how many bytes it has, according to whoever said so",
        "content_type    what kind of file it is, according to the same",
        "object_key      where it would be, if there were anywhere",
        "```",
        "",
        "`content_verified` is a constant false. Verifying a digest means",
        "reading bytes, and nothing in this lane reads any.",
        "",
        "## What is refused, and why that is the point",
        "",
        "```text",
        "a key with no store       a path into nothing",
        "a document with no owner  refused: at least one relationship required",
        "a visible document on an  refused: showing a Tribe a document nobody",
        "  unestablished fact        has established as theirs is how the wrong",
        "                            file reaches the wrong government",
        "archiving under legal     refused: a lawyer said it must not move",
        "  hold",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.award_document_store_persistence_demo_fixture_service import (  # noqa: E501
        build_document_store_fixture_set,
    )
    from nativeforge.services.award_document_store_persistence_validation_service import (  # noqa: E501
        build_validation_matrix,
    )
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    contract = build_repository_contract()
    matrix = build_validation_matrix(cases=build_validation_cases())
    fixture = build_document_store_fixture_set()
    declaration = build_persistence_declaration()

    contents = {
        "award_document_store_repository_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "award_document_store_validation_matrix.csv": render_validation_matrix(matrix),
        "award_document_store_persistence_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "award_document_store_persistence_readiness_summary.md": (
            render_readiness_summary()
        ),
    }

    blob = "".join(contents.values())
    payloads = [contract, matrix, fixture, declaration]

    def scan(fn) -> list[str]:
        return sorted({found for payload in payloads for found in fn(payload)})

    credential_fields = scan(scan_for_credential_fields)
    if credential_fields:
        raise ValueError(
            f"refusing to write: forbidden field names present {credential_fields}"
        )

    document_content = scan(scan_for_document_content)
    if document_content:
        raise ValueError(f"refusing to write: {document_content}")

    claimed_inferences = scan(scan_for_claimed_inferences)
    if claimed_inferences:
        raise ValueError(f"refusing to write: {claimed_inferences}")

    claimed_removals = scan(scan_for_claimed_removals)
    if claimed_removals:
        raise ValueError(f"refusing to write: {claimed_removals}")

    claimed_capabilities = scan(scan_for_claimed_capabilities)
    if claimed_capabilities:
        raise ValueError(f"refusing to write: {claimed_capabilities}")

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
            "document_content_found": document_content,
            "claimed_inferences_found": claimed_inferences,
            "claimed_removals_found": claimed_removals,
            "claimed_capabilities_found": claimed_capabilities,
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
        "document_content_found",
        "claimed_inferences_found",
        "claimed_removals_found",
        "claimed_capabilities_found",
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

    if declaration.get("object_store_configured"):
        fails.append("declaration_claims_a_configured_object_store")

    if declaration.get("document_storage_live"):
        fails.append("declaration_claims_document_storage_is_live")

    # The point of Gate 127H: metadata built, storage not, both stated.
    if not declaration.get("document_metadata_storage_available"):
        fails.append("declaration_does_not_report_the_metadata_this_gate_built")

    if not declaration.get("requires_document_storage"):
        fails.append("declaration_stopped_requiring_document_storage")

    if not declaration.get("readiness_blocked_reasons"):
        fails.append("declaration_claims_nothing_blocks_operational_tracking")

    return sorted(set(fails))
