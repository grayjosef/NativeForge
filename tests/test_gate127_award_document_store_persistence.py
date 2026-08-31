"""Gate 127: award document store persistence.

Metadata about a Tribe's compliance documents. Not the documents.

One thing must stay true: **no document ever enters this repository.**

The tests are grouped by what they would catch:

```text
anchor       a relationship column treated as an RLS authority
storage      a key without a store, or metadata read as content
visibility   a document shown to a Tribe nobody established it belongs to
retention    an archive under legal hold
liveness     a metadata table being read as a document store
```
"""

from __future__ import annotations

import ast
import inspect
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import (
    award_document_store_persistence_artifact_service as art,
)
from nativeforge.services import (
    award_document_store_persistence_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    award_document_store_persistence_validation_service as val_svc,
)
from nativeforge.services import award_document_store_repository_service as repo_svc
from nativeforge.services import (
    awarded_grants_requirements_readiness_service as readiness_svc,
)
from nativeforge.services import customer_persistence_capability_service as cap_svc
from nativeforge.services import (
    customer_persistence_spine_decision_service as spine_svc,
)
from nativeforge.services import (
    org_scoped_customer_persistence_guard_service as guard_svc,
)
from nativeforge.services import (
    raw_payload_body_store_contract_service as bodystore,
)
from nativeforge.services import raw_payload_store_contract_service as payload_svc
from nativeforge.services import tenant_beta_profile_service as beta_svc

ORG = fixtures.DEMO_ORGANIZATION_ID
AWARD = fixtures.DEMO_AWARDED_GRANT_ID
REQ = fixtures.DEMO_REQUIREMENT_ID
EVENT = fixtures.DEMO_PROOF_EVENT_ID
IDENTITY = fixtures.DEMO_IDENTITY_ID
KEY = fixtures.DEMO_OBJECT_KEY
DIGEST = fixtures.DEMO_DIGEST
NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)

MIGRATION = "alembic/versions/0035_nf_award_documents.py"


@pytest.fixture
def documents_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.AWARD_DOCUMENTS.create(engine)
    with engine.begin() as conn:
        yield conn
    engine.dispose()


def _document(**overrides):
    kwargs = dict(fixtures.DEMO_DOCUMENT)
    kwargs.update(overrides)
    return kwargs


# ------------------------------------------------- anchor


def test_organization_id_is_the_only_anchor():
    result = repo_svc.prepare_document_write(**_document())
    assert result["rls_anchor"] == "organization_id"
    assert result["organization_id"] == ORG
    assert repo_svc.document_store_repository_invariant_failures(result) == []


def test_a_document_without_an_organization_id_is_refused():
    result = repo_svc.prepare_document_write(**_document(organization_id=None))
    assert result["storage_allowed"] is False
    assert "document_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_an_anchor_that_is_not_uuid_shaped_is_refused():
    """The RLS predicate casts to ::uuid. A label would raise, not deny."""
    result = repo_svc.prepare_document_write(**_document(organization_id="tribe-sc"))
    assert result["storage_allowed"] is False
    assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("awarded_grant_id", AWARD),
        ("award_requirement_id", REQ),
        ("proof_event_id", EVENT),
    ],
)
def test_a_relationship_cannot_substitute_for_organization_id(field, value):
    result = repo_svc.prepare_document_write(
        **{
            **_document(),
            "organization_id": None,
            "award_requirement_id": None,
            field: value,
        }
    )
    assert result["storage_allowed"] is False
    assert f"{field}_is_not_an_organization_id_anchor" in result["blocked_reasons"]


@pytest.mark.parametrize(
    "label", ["tenant_id", "customer_org_id", "organization_profile_id"]
)
def test_a_label_is_refused_as_an_anchor_by_name(label):
    result = repo_svc.prepare_document_write(
        **_document(), **{label: "nf-demo-fixture-value"}
    )
    assert result["storage_allowed"] is False
    assert f"{label}_is_not_an_organization_id_anchor" in result["blocked_reasons"]


def test_all_six_names_are_forbidden_anchors():
    assert repo_svc.FORBIDDEN_ANCHOR_NAMES == frozenset(
        {
            "tenant_id",
            "customer_org_id",
            "organization_profile_id",
            "awarded_grant_id",
            "award_requirement_id",
            "proof_event_id",
        }
    )


# ------------------------------------------------- relationships


def test_at_least_one_relationship_is_required():
    result = repo_svc.prepare_document_write(**_document(award_requirement_id=None))
    assert result["storage_allowed"] is False
    assert "document_without_any_relationship" in result["blocked_reasons"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("awarded_grant_id", AWARD),
        ("award_requirement_id", REQ),
        ("proof_event_id", EVENT),
    ],
)
def test_any_single_relationship_is_enough(field, value):
    result = repo_svc.prepare_document_write(
        **{**_document(), "award_requirement_id": None, field: value}
    )
    assert result["storage_allowed"] is True
    assert result["relationship_present"] is True
    assert result["relationship_count"] == 1


def test_all_three_relationships_together_are_allowed():
    result = repo_svc.prepare_document_write(
        **_document(awarded_grant_id=AWARD, proof_event_id=EVENT)
    )
    assert result["storage_allowed"] is True
    assert result["relationship_count"] == 3


# ------------------------------------------------- the object store boundary


def test_the_object_store_answer_comes_from_gate_96s_detector():
    """One detector for one question, not a second one written here."""
    status = repo_svc.object_store_status()
    assert status["object_store_configured"] is False
    assert status["body_store_mode"] == bodystore.detect_body_store_mode()
    assert status["built_by_gate_127"] is False
    assert status["detector"].endswith("detect_body_store_mode")
    assert val_svc.detect_object_store_configured() is (
        bodystore.detect_body_store_mode() in bodystore.PRODUCTION_CAPABLE_MODES
    )


def test_the_object_store_is_unconfigured_today():
    assert bodystore.detect_body_store_mode() == "unconfigured"
    assert val_svc.detect_object_store_configured() is False


def test_an_object_key_is_refused_when_the_store_is_unconfigured():
    result = repo_svc.prepare_document_write(**_document(object_key=KEY))
    assert result["storage_allowed"] is False
    assert "object_key_without_a_configured_object_store" in result["blocked_reasons"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("object_bucket", "nf-demo", "object_bucket_without_a_configured_object_store"),
        (
            "object_store_provider",
            "s3_compatible",
            "object_store_provider_without_a_configured_store",
        ),
    ],
)
def test_the_rest_of_the_object_reference_needs_a_store_too(field, value, reason):
    result = repo_svc.prepare_document_write(**_document(**{field: value}))
    assert result["storage_allowed"] is False
    assert reason in result["blocked_reasons"]


def test_a_version_without_a_key_is_refused():
    result = repo_svc.prepare_document_write(**_document(object_version="v2"))
    assert result["storage_allowed"] is False
    assert "object_version_without_an_object_key" in result["blocked_reasons"]


def test_a_stored_status_without_a_location_is_refused():
    result = repo_svc.prepare_document_write(**_document(document_status="stored"))
    assert result["storage_allowed"] is False
    assert "stored_status_without_a_location" in result["blocked_reasons"]


def test_the_object_key_refusal_is_falsifiable():
    """Injectable, so the refusal is a measurement rather than a constant."""
    result = repo_svc.prepare_document_write(
        **_document(
            document_status="stored",
            object_key=KEY,
            object_bucket="nf-demo",
            object_store_provider="s3_compatible",
        ),
        object_store_configured=True,
    )
    assert result["storage_allowed"] is True
    assert result["object_store_configured"] is True
    assert result["document_is_stored"] is True
    assert result["document_is_metadata_only"] is False
    assert repo_svc.document_store_repository_invariant_failures(result) == []


def test_the_real_environment_still_reports_no_store():
    """The injection above changes one call, not the deployment."""
    assert val_svc.detect_object_store_configured() is False
    result = repo_svc.prepare_document_write(**_document())
    assert result["object_store_configured"] is False
    assert result["document_is_metadata_only"] is True


# ------------------------------------------------- metadata is not content


def test_the_repository_cannot_be_handed_a_document():
    """The separation expressed as a signature, not as a runtime check."""
    names = set(inspect.signature(repo_svc.prepare_document_write).parameters)
    for forbidden in (
        "content",
        "body",
        "bytes",
        "file",
        "file_path",
        "document_bytes",
        "document_content",
        "upload",
        "stream",
    ):
        assert forbidden not in names, forbidden
    # And the same for the create path.
    create = set(inspect.signature(repo_svc.create_award_document).parameters)
    assert "content" not in create
    assert "body" not in create


def test_no_column_holds_document_bytes():
    columns = {c.name for c in repo_svc.AWARD_DOCUMENTS.columns}
    for forbidden in ("content", "body", "bytes", "document_content", "blob"):
        assert forbidden not in columns, forbidden
    # What is there instead: claims about a file, and where it would be.
    for present in ("sha256_digest", "content_length", "content_type", "object_key"):
        assert present in columns


def test_object_metadata_does_not_imply_content():
    result = val_svc.validate_award_document(
        document_kind="financial_report",
        document_status="reference_recorded",
        document_title="Demo SF-425",
        document_source="tenant_supplied",
        award_requirement_id=REQ,
        sha256_digest=DIGEST,
        content_length=148213,
        content_type="application/pdf",
        retention_class="retain_1_year",
        fact_status="demo_fixture",
    )
    assert result["sha256_digest"] == DIGEST
    assert result["content_length"] == 148213
    # And none of it is evidence the document exists.
    assert result["content_verified"] is False
    assert result["document_is_metadata_only"] is True
    assert result["digest_is_unverified"] is True
    assert result["content_inferred_from_metadata"] is False


def test_a_digest_on_a_metadata_only_row_is_recorded_not_refused():
    """A Tribe handing over a file and its digest is the ordinary case."""
    result = repo_svc.prepare_document_write(**_document())
    assert result["storage_allowed"] is True
    assert result["sha256_digest"] == DIGEST
    assert result["validation"]["digest_is_unverified"] is True


def test_content_length_and_digest_are_shape_checked():
    negative = val_svc.validate_award_document(
        document_title="Demo", award_requirement_id=REQ, content_length=-1
    )
    assert "content_length_is_negative" in negative["blocked_reasons"]
    bad_digest = val_svc.validate_award_document(
        document_title="Demo", award_requirement_id=REQ, sha256_digest="nothex"
    )
    assert "sha256_digest_is_not_sha256_shaped" in bad_digest["blocked_reasons"]


def test_a_document_does_not_imply_an_accepted_proof():
    result = repo_svc.prepare_document_write(
        **_document(award_requirement_id=None, proof_event_id=EVENT)
    )
    assert result["storage_allowed"] is True
    assert result["acceptance_inferred_from_document"] is False


# ------------------------------------------------- visibility


def test_customer_visible_is_false_by_default():
    result = repo_svc.prepare_document_write(**_document())
    assert result["customer_visible"] is False
    assert result["visibility_inferred_from_upload"] is False
    assert repo_svc.AWARD_DOCUMENTS.c.customer_visible.nullable is False


def test_customer_visible_is_refused_on_an_unestablished_fact_status():
    result = repo_svc.prepare_document_write(
        **_document(customer_visible=True, fact_status="unknown")
    )
    assert result["storage_allowed"] is False
    assert (
        "customer_visible_on_an_unestablished_fact_status" in result["blocked_reasons"]
    )


def test_customer_visible_is_reachable_on_an_established_one():
    result = repo_svc.prepare_document_write(**_document(customer_visible=True))
    assert result["storage_allowed"] is True
    assert result["customer_visible"] is True


# ------------------------------------------------- retention and legal hold


def test_the_retention_vocabulary_is_bridged_from_gate_96():
    assert set(val_svc.RETENTION_CLASSES) == set(payload_svc.RETENTION_POLICIES)
    assert val_svc.vocabulary_invariant_failures() == []


def test_an_unrecognised_retention_class_is_refused():
    result = repo_svc.prepare_document_write(**_document(retention_class="forever"))
    assert result["storage_allowed"] is False
    assert any(
        r.startswith("retention_class_not_recognised")
        for r in result["blocked_reasons"]
    )


def test_legal_hold_prevents_archive(documents_db):
    document_id = uuid.uuid4()
    repo_svc.create_award_document(
        connection=documents_db,
        document_id=document_id,
        now=NOW,
        **_document(legal_hold=True),
    )
    archived = repo_svc.archive_award_document(
        connection=documents_db,
        organization_id=ORG,
        document_id=str(document_id),
        now=NOW,
    )
    assert archived["rows_written"] == 0
    assert "legal_hold_refuses_archive" in archived["blocked_reasons"]

    listed = repo_svc.list_documents_for_organization(
        connection=documents_db, organization_id=ORG
    )
    assert listed["rows_read"] == 1
    assert listed["archived_count"] == 0
    assert listed["legal_hold_count"] == 1


def test_a_document_under_legal_hold_is_never_archivable():
    result = repo_svc.prepare_document_write(**_document(legal_hold=True))
    assert result["legal_hold"] is True
    assert result["archivable"] is False
    assert repo_svc.document_store_repository_invariant_failures(result) == []


# ------------------------------------------------- lifecycle


def test_a_row_is_written_and_read_back(documents_db):
    document_id = uuid.uuid4()
    created = repo_svc.create_award_document(
        connection=documents_db, document_id=document_id, now=NOW, **_document()
    )
    assert created["rows_written"] == 1
    read = repo_svc.get_award_document(
        connection=documents_db, organization_id=ORG, document_id=str(document_id)
    )
    assert read["rows_read"] == 1
    assert read["document_title"] == fixtures.DEMO_DOCUMENT["document_title"]
    assert read["object_key"] is None
    assert read["document_is_metadata_only"] is True
    assert repo_svc.document_store_repository_invariant_failures(read) == []


def test_a_read_is_scoped_to_one_organization(documents_db):
    repo_svc.create_award_document(connection=documents_db, now=NOW, **_document())
    other = repo_svc.get_award_document(
        connection=documents_db, organization_id=str(uuid.uuid4())
    )
    assert other["rows_read"] == 0
    assert "no_award_document_for_this_organization" in other["blocked_reasons"]


def test_each_listing_narrows_without_scoping(documents_db):
    other_requirement = str(uuid.uuid4())
    repo_svc.create_award_document(connection=documents_db, now=NOW, **_document())
    repo_svc.create_award_document(
        connection=documents_db,
        now=NOW,
        **_document(
            award_requirement_id=other_requirement,
            document_title="Demo narrative report",
        ),
    )
    for_org = repo_svc.list_documents_for_organization(
        connection=documents_db, organization_id=ORG
    )
    assert for_org["rows_read"] == 2
    for_one = repo_svc.list_documents_for_requirement(
        connection=documents_db, organization_id=ORG, award_requirement_id=REQ
    )
    assert for_one["rows_read"] == 1
    # The requirement narrows; it does not scope.
    unscoped = repo_svc.list_documents_for_requirement(
        connection=documents_db,
        organization_id=str(uuid.uuid4()),
        award_requirement_id=REQ,
    )
    assert unscoped["rows_read"] == 0


def test_archiving_retains_the_document(documents_db):
    document_id = uuid.uuid4()
    repo_svc.create_award_document(
        connection=documents_db, document_id=document_id, now=NOW, **_document()
    )
    archived = repo_svc.archive_award_document(
        connection=documents_db,
        organization_id=ORG,
        document_id=str(document_id),
        archived_by_identity_id=IDENTITY,
        now=NOW,
    )
    assert archived["rows_written"] == 1
    assert archived["rows_deleted"] == 0

    remaining = documents_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.AWARD_DOCUMENTS)
    ).scalar()
    assert remaining == 1

    listed = repo_svc.list_documents_for_organization(
        connection=documents_db, organization_id=ORG
    )
    assert listed["rows_read"] == 1
    assert listed["archived_count"] == 1


def test_nothing_in_the_repository_deletes():
    """Gate 123's lesson: parse the module, do not grep it."""
    source = Path(repo_svc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"delete", "drop"}
    ]
    assert calls == []
    assert "no DELETE path" in source


def test_nothing_in_the_repository_opens_a_file_or_reaches_a_store():
    """The claim this whole gate turns on, asserted structurally."""
    source = Path(repo_svc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    # `get` is deliberately absent from this list: it is `dict.get`, which
    # this module calls constantly. A name that generic proves nothing, and a
    # test that fails on it is testing its own list rather than the module.
    for forbidden in (
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "urlopen",
        "urlretrieve",
        "put_object",
        "get_object",
        "upload_file",
        "upload_fileobj",
        "download_file",
        "download_fileobj",
        "generate_presigned_url",
    ):
        assert forbidden not in called, forbidden

    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    for forbidden in ("boto3", "botocore", "minio", "httpx", "requests", "urllib"):
        assert forbidden not in imported, forbidden


# ------------------------------------------------- production write gates


def test_a_production_write_is_reachable_and_needs_both_gates():
    settled = _document(fact_status="verified", is_demo=False)
    assert (
        repo_svc.prepare_document_write(
            **settled, customer_auth_live=True, verified_operational_binding=True
        )["production_write_allowed"]
        is True
    )
    for kwargs, reason in (
        (
            {"customer_auth_live": False, "verified_operational_binding": True},
            "production_document_write_requires_live_customer_auth",
        ),
        (
            {"customer_auth_live": True, "verified_operational_binding": False},
            "production_document_write_requires_a_verified_operational_binding",
        ),
    ):
        result = repo_svc.prepare_document_write(**settled, **kwargs)
        assert result["production_write_allowed"] is False
        assert reason in result["blocked_reasons"]


def test_both_gates_are_false_in_this_repository():
    result = repo_svc.prepare_document_write(
        **_document(fact_status="verified", is_demo=False)
    )
    assert result["production_write_allowed"] is False
    assert set(result["blocked_reasons"]) == {
        "production_document_write_requires_live_customer_auth",
        "production_document_write_requires_a_verified_operational_binding",
    }


def test_a_document_write_needs_a_verified_binding():
    assert "write_document_library_item" in guard_svc.LABEL_BOUND_OPERATIONS
    result = guard_svc.evaluate_persistence_write(
        operation="write_document_library_item",
        organization_id=ORG,
        persistence_capability=cap_svc.build_capability(
            "document_library_persistence", customer_auth_live=True
        ),
    )
    assert result["write_allowed"] is False
    assert any("verified_binding_required" in r for r in result["blocked_reasons"])
    assert guard_svc.persistence_guard_invariant_failures(result) == []


# ------------------------------------------------- schema parity


def test_the_core_table_matches_the_migration_columns():
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.AWARD_DOCUMENTS.columns}
    assert mapped == declared


def test_the_core_table_matches_the_migration_check_constraints():
    """Gate 119C's defect: a Core table weaker than the migrated one."""
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'name="(ck_nf_award_documents_\w+)"', migration))
    mapped = {
        c.name
        for c in repo_svc.AWARD_DOCUMENTS.constraints
        if c.name and str(c.name).startswith("ck_nf_award_documents")
    }
    assert mapped == declared
    assert len(mapped) == 16


def test_the_migration_restates_the_vocabularies_exactly():
    """A CHECK constraint cannot import Python, so a test holds them together."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig0035", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.DOCUMENT_KINDS) == set(val_svc.DOCUMENT_KINDS)
    assert set(module.DOCUMENT_STATUSES) == set(val_svc.DOCUMENT_STATUSES)
    assert set(module.DOCUMENT_SOURCES) == set(val_svc.DOCUMENT_SOURCES)
    assert set(module.RETENTION_CLASSES) == set(payload_svc.RETENTION_POLICIES)
    assert set(module.FACT_STATUSES) == set(beta_svc.FACT_STATUSES)
    assert set(module.STORED_STATUSES) == set(val_svc.STORED_STATUSES)


def test_the_database_refuses_what_the_module_would_have_missed(documents_db):
    """The CHECK constraints, exercised past the service that also refuses."""
    base = dict(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(ORG),
        awarded_grant_id=None,
        award_requirement_id=uuid.UUID(REQ),
        proof_event_id=None,
        document_kind="financial_report",
        document_status="reference_recorded",
        document_title="Demo SF-425",
        document_source="tenant_supplied",
        object_store_configured=False,
        retention_class="retain_1_year",
        legal_hold=False,
        customer_visible=False,
        fact_status="demo_fixture",
        human_review_required=True,
        is_demo=True,
        blocked_reasons=[],
        created_at=NOW,
        updated_at=NOW,
    )
    for values in (
        {"award_requirement_id": None},
        {"object_key": "k/1"},
        {"object_bucket": "b"},
        {"object_store_provider": "s3"},
        {"object_version": "v2", "object_store_configured": True},
        {"document_status": "stored"},
        {"document_title": "   "},
        {"content_length": -1},
        {"sha256_digest": "abc"},
        {"legal_hold": True, "archived_at": NOW},
        {"customer_visible": True, "fact_status": "unknown"},
        {"document_kind": "invented"},
        {"document_status": "invented"},
        {"document_source": "invented"},
        {"retention_class": "forever"},
        {"fact_status": "invented"},
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with documents_db.begin_nested():
                documents_db.execute(
                    sa.insert(repo_svc.AWARD_DOCUMENTS).values(
                        **{**base, "id": uuid.uuid4(), **values}
                    )
                )


def test_the_rls_policy_scopes_on_organization_and_demo():
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    assert (
        "organization_id = current_setting('app.current_org_id', true)::uuid"
        in migration
    )
    assert (
        "is_demo = current_setting('app.current_org_is_demo', true)::boolean"
        in migration
    )
    for forbidden in (
        "tenant_id",
        "customer_org_id",
        "organization_profile_id",
        "awarded_grant_id",
        "award_requirement_id",
        "proof_event_id",
    ):
        assert f"{forbidden} = current_setting" not in migration


# ------------------------------------------------- invariants


def test_a_refused_input_never_trips_the_services_own_invariants():
    """An invariant ordinary bad input can fire is a validation rule misnamed."""
    for case in (
        {"document_kind": "invented"},
        {"document_status": "invented"},
        {"document_title": None},
        {"award_requirement_id": None},
        {"object_key": "k/1"},
        {"object_bucket": "b"},
        {"object_version": "v2"},
        {"document_status": "stored"},
        {"content_length": -5},
        {"sha256_digest": "nothex"},
        {"retention_class": "forever"},
        {"customer_visible": True, "fact_status": "unknown"},
        {"legal_hold": True},
        {"document_source": "invented"},
        {"fact_status": "invented"},
    ):
        result = val_svc.validate_award_document(
            **{
                "document_kind": "financial_report",
                "document_status": "reference_recorded",
                "document_title": "Demo SF-425",
                "document_source": "tenant_supplied",
                "award_requirement_id": REQ,
                "retention_class": "retain_1_year",
                "fact_status": "demo_fixture",
                **case,
            }
        )
        assert val_svc.validation_invariant_failures(result) == [], case


def test_no_invariant_reads_an_unguarded_echoed_input():
    """The rule Gate 125 adopted and Gate 126 refined with the storable guard."""
    source = Path(val_svc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "validation_invariant_failures"
    )
    read = {
        node.args[0].value
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    for echoed in (
        "content_length",
        "sha256_digest",
        "document_kind",
        "retention_class",
    ):
        assert echoed not in read, echoed
    assert "storable" in source
    for derived in (
        "document_is_stored",
        "document_is_metadata_only",
        "digest_is_unverified",
        "customer_visible_consistent",
    ):
        assert derived in read, derived


def test_the_permitted_branch_of_readiness_is_reachable():
    result = val_svc.validate_award_document(
        document_kind="financial_report",
        document_status="reference_recorded",
        document_title="Demo SF-425",
        document_source="tenant_supplied",
        award_requirement_id=REQ,
        retention_class="retain_1_year",
        fact_status="verified",
    )
    assert result["document_ready_for_reference"] is True
    assert val_svc.validation_invariant_failures(result) == []


# ------------------------------------------------- fixtures


def test_the_fixture_set_has_sixteen_cases_and_they_all_agree():
    fixture = fixtures.build_document_store_fixture_set()
    assert fixture["case_count"] == 16
    assert fixture["document_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixture["vocabulary_invariant_failures"] == []
    assert fixtures.document_store_fixture_invariant_failures(fixture) == []


def test_no_fixture_writes_a_document_or_reaches_a_store():
    fixture = fixtures.build_document_store_fixture_set()
    assert fixture["production_write_count"] == 0
    assert fixture["production_document_records_created"] == 0
    assert fixture["document_bytes_written"] == 0
    assert fixture["object_store_contacted"] is False
    assert fixture["document_content_read"] is False
    assert fixture["object_store_configured"] is False
    assert fixture["stored_count"] == 0
    assert fixture["customer_visible_count"] == 0
    assert fixture["rows_deleted"] == 0


def test_every_fixture_identifier_is_labelled_as_a_fixture():
    for value in (
        fixtures.DEMO_TENANT_LABEL,
        fixtures.DEMO_CUSTOMER_ORG_LABEL,
        fixtures.DEMO_PROFILE_ID_LABEL,
        fixtures.DEMO_SOURCE_REF,
        fixtures.DEMO_OBJECT_KEY,
        fixtures.DEMO_BUCKET,
    ):
        assert value.startswith(fixtures.FIXTURE_PREFIX)
    assert fixtures.DEMO_DOCUMENT["fact_status"] == "demo_fixture"


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_document_cases(
        [{"case": "valid_metadata_only_requirement_document"}]
    )
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 15


def test_the_fixture_set_reports_the_real_environment_unchanged():
    fixture = fixtures.build_document_store_fixture_set()
    assert fixture["actual_customer_auth_live"] is False
    assert fixture["actual_verified_operational_binding"] is False
    assert fixture["actual_object_store_configured"] is False
    assert fixture["actual_body_store_mode"] == "unconfigured"


# ------------------------------------------------- artifacts


def test_the_artifacts_write_four_files():
    with tempfile.TemporaryDirectory() as root:
        result = art.write_persistence_artifacts(repo_root=root)
        assert result["file_count"] == 4
        assert art.persistence_artifact_invariant_failures(result) == []
        for path in result["files_written"].values():
            assert Path(path).is_file()


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        art.write_persistence_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            committed = (repo_root / art.ARTIFACT_DIR / path.name).read_text(
                encoding="utf-8"
            )
            assert fresh == committed, f"stale artifact: {path.name}"


def test_the_artifacts_report_metadata_built_and_storage_not():
    declaration = art.build_persistence_declaration()
    assert declaration["document_metadata_storage_available"] is True
    assert declaration["document_store_write_path_available"] is True
    assert declaration["document_store_operational"] is False
    # The claim this gate turns on.
    assert declaration["object_store_configured"] is False
    assert declaration["document_storage_live"] is False
    assert declaration["body_store_mode"] == "unconfigured"
    assert declaration["requires_document_storage"] is True
    assert declaration["ready_for_operational_awarded_tracking"] is False
    assert declaration["readiness_blocked_reasons"]


def test_the_content_scan_refuses_a_document_in_an_artifact():
    assert art.scan_for_document_content({"content": "x"}) == [
        "document_content_field:content"
    ]
    assert art.scan_for_document_content({"note": "A" * 600}) == [
        "document_content_value:note"
    ]
    assert art.scan_for_document_content(
        {"note": "data:application/pdf;base64," + "A" * 600}
    ) == ["document_content_value:note"]
    assert art.scan_for_document_content({"note": "Demo SF-425"}) == []


def test_the_capability_scan_tells_a_claim_from_a_demonstration():
    """Gate 121's lesson: narrow the scanner, do not drop it."""
    # A summary claiming a store that is not there is refused...
    assert art.scan_for_claimed_capabilities({"object_store_configured": True}) == [
        "capability_claim_disagrees_with_reality:object_store_configured"
    ]
    # ...and so is a key presented as acceptable with no store.
    assert art.scan_for_claimed_capabilities(
        {"object_key_present": True, "object_store_configured": False}
    ) == ["claimed_capability:a_key_without_a_store"]
    # A case row showing that refusal is permitted.
    assert (
        art.scan_for_claimed_capabilities(
            {
                "case": "object_key_without_a_store",
                "blocked_reasons": ["object_key_without_a_configured_object_store"],
                "object_key_present": True,
                "object_store_configured": False,
            }
        )
        == []
    )
    # And so is a case row injecting a store to reach the permitted branch.
    assert (
        art.scan_for_claimed_capabilities(
            {
                "case": "a_stored_document_with_a_store_injected",
                "object_store_configured": True,
                "object_key_present": True,
            }
        )
        == []
    )


def test_the_artifact_write_refuses_a_payload_carrying_a_document(monkeypatch):
    monkeypatch.setattr(
        art, "build_repository_contract", lambda: {"document_content": "x"}
    )
    with tempfile.TemporaryDirectory() as root:
        with pytest.raises(ValueError, match="document_content"):
            art.write_persistence_artifacts(repo_root=root)


# ------------------------------------------------- the capability lane


def test_the_document_lane_has_a_write_path_and_is_not_operational():
    lane = cap_svc.build_capability("document_library_persistence")
    assert lane["schema_available"] is True
    assert lane["repository_available"] is True
    assert lane["write_path_available"] is True
    assert lane["operational"] is False
    assert lane["blocked_reasons"] == ["no_customer_auth_so_nobody_owns_the_row"]


def test_the_lane_points_at_the_table_this_gate_built():
    assert (
        cap_svc.CAPABILITY_TABLES["document_library_persistence"]
        == "nf_award_documents"
    )
    assert (
        cap_svc.CAPABILITY_REPOSITORY_MODULES["document_library_persistence"]
        == "nativeforge.services.award_document_store_repository_service"
    )


def test_the_repository_is_not_named_award_document_store_service():
    """The name two module-existence probes used to watch for.

    Creating a file called `award_document_store_service` - even an empty one -
    would have flipped `DOCUMENT_STORAGE` and `document_storage_live` true, told
    two lanes their evidence had a home, and let
    `operational_awarded_recommended` go true. With zero bytes stored anywhere.
    """
    import importlib.util

    try:
        found = (
            importlib.util.find_spec(
                "nativeforge.services.award_document_store_service"
            )
            is not None
        )
    except (ImportError, ValueError):
        found = False
    assert not found, "the trap module name was created"


def test_no_probe_names_that_module_any_more():
    """One place answers 'is there a document store', and it is not a filename.

    Parsed rather than grepped. The first version was a substring check and it
    matched the docstring that *explains* the removal - the seventh time this
    campaign has produced a substring-versus-meaning false positive, and the
    third time in a test written to catch exactly that class of defect.

    What matters is whether any string literal in a call argument still names
    the trap module, not whether the prose mentions it. The prose assertion
    below keeps the explanation in place, so a future reader learns why.
    """
    trap = "nativeforge.services.award_document_store_service"

    for module in (spine_svc, readiness_svc):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        literals_in_calls = {
            arg.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for arg in [*node.args, *(kw.value for kw in node.keywords)]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        }
        assert trap not in literals_in_calls, module.__name__

        # And the explanation is still there, so this would catch a real
        # reintroduction rather than the account of one.
        assert "module-existence proxy" in source, module.__name__


def test_every_mapped_repository_module_imports():
    """Gate 126's guard, which this gate's new mapping must also satisfy."""
    import importlib.util

    for lane, module in cap_svc.CAPABILITY_REPOSITORY_MODULES.items():
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        assert found, f"{lane} names a repository module that does not import: {module}"


# ------------------------------------------------- the spine


def test_document_storage_is_derived_from_two_conditions():
    """Metadata has a home. Bytes do not. Only the second is the prerequisite."""
    decision = spine_svc.build_persistence_spine_decision()
    assert decision["requires_document_storage"] is True
    lane = cap_svc.build_capability("document_library_persistence")
    assert lane["write_path_available"] is True
    assert val_svc.detect_object_store_configured() is False
    # So the prerequisite stays unmet, correctly.
    assert spine_svc.spine_decision_invariant_failures(decision) == []


def test_the_spine_still_recommends_customer_authentication():
    decision = spine_svc.build_persistence_spine_decision()
    assert (
        decision["next_gate_recommendation"]["recommendation"]
        == "customer_authentication"
    )
    assert decision["operational_awarded_recommended"] is False
    assert decision["customer_persistence_live"] is False


def test_the_document_lane_left_the_requires_migrations_set():
    decision = spine_svc.build_persistence_spine_decision()
    assert "document_library_persistence" not in decision["requires_migrations"]


def test_the_document_lane_is_operable_and_not_yet_due():
    """Its own prerequisite is the store it does not have."""
    decision = spine_svc.build_persistence_spine_decision(
        capability_matrix=cap_svc.build_capability_matrix(customer_auth_live=True),
        preconditions={
            "customer_auth": True,
            "document_storage": False,
            "email_delivery": False,
            "live_source_collection": False,
        },
    )
    by_name = {e["capability"]: e for e in decision["recommended_sequence"]}
    lane = by_name["document_library_persistence"]
    assert lane["operational"] is True
    assert lane["unmet_prerequisites"] == ["document_storage"]
    assert lane["operational_out_of_sequence"] is True
    assert decision["operational_awarded_recommended"] is False


# ------------------------------------------------- readiness


def test_readiness_reports_metadata_built_and_storage_still_false():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    for key in readiness_svc.STORAGE_COMPONENT_KEYS:
        assert readiness[key] is True, key
    assert readiness["document_metadata_storage_available"] is True
    # And the two that matter did not move.
    assert readiness["object_store_configured"] is False
    assert readiness["document_storage_live"] is False
    assert readiness["ready_for_operational_awarded_tracking"] is False
    assert readiness_svc.readiness_invariant_failures(readiness) == []


def test_document_storage_live_cannot_be_claimed_without_a_store():
    readiness = dict(readiness_svc.build_awarded_requirements_readiness())
    readiness["document_storage_live"] = True
    assert (
        "document_storage_live_without_a_configured_object_store"
        in readiness_svc.readiness_invariant_failures(readiness)
    )


def test_document_storage_live_cannot_be_claimed_without_metadata():
    readiness = dict(readiness_svc.build_awarded_requirements_readiness())
    readiness["document_storage_live"] = True
    readiness["object_store_configured"] = True
    readiness["document_metadata_storage_available"] = False
    assert (
        "document_storage_live_without_metadata_persistence"
        in readiness_svc.readiness_invariant_failures(readiness)
    )


def test_document_storage_remains_an_operational_blocker():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    assert "document_storage_live" in readiness["missing_operational_components"]
    assert (
        "operational_component_missing:document_storage_live"
        in readiness["blocked_reasons"]
    )


# ------------------------------------------------- liveness


def test_no_row_is_written_to_the_application_database():
    for result in (
        repo_svc.prepare_document_write(**_document()),
        repo_svc.create_award_document(**_document()),
    ):
        assert result["rows_written"] == 0
        assert result["production_document_records_created"] == 0
        assert result["real_customer_rows_written"] == 0
        assert result["document_bytes_written"] == 0
        assert result["object_store_contacted"] is False


def test_nothing_claims_a_document_store_or_awarded_tracking_is_live():
    fixture = fixtures.build_document_store_fixture_set()
    declaration = art.build_persistence_declaration()
    assert fixture["document_storage_operational"] is False
    assert fixture["awarded_grants_operational_tracking_live"] is False
    assert declaration["document_store_operational"] is False
    assert declaration["awarded_operational_tracking_ready"] is False
    assert declaration["customer_auth_live"] is False
    assert declaration["login_live"] is False
    assert declaration["customer_persistence_live"] is False
    assert declaration["beta_onboarding_ready"] is False
    assert declaration["production_rollout_ready"] is False


def test_no_api_route_serves_a_document():
    """Gate 127F: skipped, and the survey records why."""
    assert not Path("src/nativeforge/api/award_documents.py").exists()
    survey = Path(
        "docs/operations/680_GATE127_AWARD_DOCUMENT_STORE_SURVEY.md"
    ).read_text(encoding="utf-8")
    assert "## 10. No API route" in survey
