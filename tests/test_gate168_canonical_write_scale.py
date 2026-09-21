"""Gate 168: the batch write path.

Hermetic. Validation, chunking, accounting and the structural properties of
the writer need no database - which is the point, because the cases that
matter most here are the ones a healthy fixture never produces.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pathlib

import pytest

from nativeforge.repositories import (
    canonical_opportunity_batch_repository as batch,
)
from nativeforge.repositories.canonical_opportunity_batch_repository import (
    DEFAULT_BATCH_SIZE,
    FAILED,
    IDEMPOTENT,
    INSERTED,
    RECORD_OUTCOMES,
    REJECTED,
    VERSIONED,
    NormalizedSourceObservation,
    _stream_chunks,
    validate_observation,
)
from nativeforge.repositories.canonical_opportunity_repository import (
    record_observation,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (
    build_opportunity_identity,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
WRITER = (
    REPO
    / "src"
    / "nativeforge"
    / "repositories"
    / "canonical_opportunity_batch_repository.py"
)

ADAPTER = "grants_gov_search2"

VALID_RECORD = {
    "id": "777",
    "number": "O-NF168T-000001",
    "title": "Batch fixture",
    "agency": "Synthetic Agency",
    "agencyCode": "NF168-T",
    "openDate": "01/05/2027",
    "closeDate": "04/01/2027",
    "oppStatus": "posted",
    "docType": "synopsis",
    "cfdaList": ["14.001"],
}


def make(**overrides) -> NormalizedSourceObservation:
    normalized = normalize_record(record=VALID_RECORD, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    base = {
        "source_id": "nf168.test.source",
        "normalized": normalized,
        "raw_payload_sha256": "a" * 64,
        "identity": identity,
    }
    base.update(overrides)
    return NormalizedSourceObservation(**base)


# ------------------------------------------------------- validation


def test_a_valid_observation_has_no_reasons():
    assert validate_observation(make()) == []


def test_a_short_payload_hash_is_refused_before_the_database():
    """The schema CHECK would refuse it. Refusing here keeps the batch alive."""
    reasons = validate_observation(make(raw_payload_sha256="too-short"))
    assert any("64_character_digest" in r for r in reasons)


def test_an_empty_payload_hash_is_refused():
    assert validate_observation(make(raw_payload_sha256=""))


def test_a_missing_source_id_is_refused():
    assert "no_source_id" in validate_observation(make(source_id=""))


def test_an_l4_identity_that_denies_being_provisional_is_refused():
    """Migration 0053 refuses it; refusing here keeps the batch alive."""
    reasons = validate_observation(
        make(identity={"identity_layer": "L4", "is_provisional": False})
    )
    assert "l4_identity_not_marked_provisional" in reasons


def test_an_l1_identity_without_a_number_is_refused():
    reasons = validate_observation(
        make(identity={"identity_layer": "L1", "normalized_opportunity_number": ""})
    )
    assert "l1_identity_without_a_normalized_number" in reasons


def test_an_identity_layer_outside_the_vocabulary_is_refused():
    reasons = validate_observation(make(identity={"identity_layer": "L9"}))
    assert any("identity_layer_outside_the_vocabulary" in r for r in reasons)


def test_no_normalized_fields_is_refused():
    reasons = validate_observation(
        make(normalized={"fields": {}, "content_fingerprint": "x"})
    )
    assert "no_normalized_fields" in reasons


def test_a_missing_content_fingerprint_is_refused():
    normalized = normalize_record(record=VALID_RECORD, adapter_key=ADAPTER)
    normalized["content_fingerprint"] = ""
    assert "no_content_fingerprint" in validate_observation(
        make(normalized=normalized)
    )


def test_validation_never_raises_on_a_malformed_record():
    """One bad record must not take the batch down before it starts."""
    for broken in ({}, {"fields": None}, {"fields": "not a dict"}):
        assert validate_observation(make(normalized=broken))


# --------------------------------------------------------- chunking


def test_stream_chunks_bounds_the_working_set():
    chunks = list(_stream_chunks(range(10), 3))
    assert [len(c) for c in chunks] == [3, 3, 3, 1]


def test_stream_chunks_consumes_a_generator_lazily():
    """`list(observations)` would make memory a property of the input.

    The generator must not be exhausted before the first chunk is yielded.
    """
    consumed: list[int] = []

    def source():
        for index in range(10):
            consumed.append(index)
            yield index

    stream = _stream_chunks(source(), 4)
    first = next(stream)
    assert first == [0, 1, 2, 3]
    assert consumed == [0, 1, 2, 3], "the whole iterable was materialized"


def test_stream_chunks_handles_empty_and_none():
    assert list(_stream_chunks([], 5)) == []
    assert list(_stream_chunks(None, 5)) == []


def test_the_default_batch_size_is_bounded():
    assert 1 <= DEFAULT_BATCH_SIZE <= 5000


# ----------------------------------------------- structural properties


def test_the_writer_issues_no_statement_per_field():
    """The N+1 Gate 168A found, refused structurally.

    Every `connection.execute` inside the per-field loop would reintroduce it,
    so the AST is checked rather than a comment trusted.
    """
    tree = ast.parse(WRITER.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        target = getattr(node.target, "elts", None)
        names = (
            [getattr(e, "id", "") for e in target]
            if target
            else [getattr(node.target, "id", "")]
        )
        if "name" not in names or "value" not in names:
            continue
        # This is the per-field loop. Nothing in it may talk to the database.
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                func = inner.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "execute"
                    and getattr(func.value, "id", "") == "connection"
                ):
                    offenders.append(f"line {inner.lineno}")
    assert offenders == [], f"per-field database call: {offenders}"


def test_the_writer_names_no_dialect_specific_construct():
    """Gate 168K: the speedup must not be painted into SQLite."""
    tree = ast.parse(WRITER.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if ast.get_docstring(node, clean=False) is None:
                continue
            body = node.body[0]
            if isinstance(body, ast.Expr) and isinstance(body.value, ast.Constant):
                docstrings.add(id(body.value))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            lowered = node.value.lower()
            for marker in ("pragma", "insert or ignore", "on conflict", "returning"):
                assert marker not in lowered, f"{marker} at line {node.lineno}"


def test_the_single_record_path_delegates_to_the_batch_path():
    """One write path, not two encodings of the same rules."""
    source = inspect.getsource(record_observation)
    assert "persist_observations" in source
    assert "NormalizedSourceObservation" in source


def test_the_observation_dataclass_is_frozen():
    """A caller must not mutate a record after state was resolved for it."""
    observation = make()
    # A frozen dataclass raises FrozenInstanceError, which subclasses
    # AttributeError. Naming it is the point: `Exception` would also pass if
    # the attribute simply did not exist.
    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.source_id = "changed"  # type: ignore[misc]


def test_every_outcome_is_in_the_vocabulary():
    assert set(RECORD_OUTCOMES) == {
        INSERTED,
        IDEMPOTENT,
        VERSIONED,
        REJECTED,
        FAILED,
    }


def test_every_outcome_lands_in_exactly_one_metric_bucket():
    """A VERSIONED record counted in no bucket makes the totals meaningless."""
    source = inspect.getsource(batch._persist_chunk)
    for outcome_constant in ("INSERTED", "VERSIONED", "IDEMPOTENT", "REJECTED"):
        assert f"plan.outcome == {outcome_constant}" in source, outcome_constant


def test_the_batch_result_reports_every_metric_gate168l_requires():
    from nativeforge.repositories.canonical_opportunity_batch_repository import (
        persist_observations,
    )

    # An empty batch still returns the full metric shape, so a caller can rely
    # on the keys existing whether or not anything was written.
    outcome = persist_observations(connection=None, observations=[])
    metrics = outcome["metrics"]
    for name in (
        "observations_attempted",
        "observations_inserted",
        "observations_idempotent",
        "observations_rejected",
        "observations_failed",
        "versions_inserted",
        "provenance_rows_inserted",
        "canonical_created",
        "canonical_matched",
        "conflicts_recorded",
        "batches",
        "batch_failures",
    ):
        assert name in metrics, name


def test_metrics_expose_no_customer_data_or_raw_evidence():
    """168L: counts and durations only."""
    from nativeforge.repositories.canonical_opportunity_batch_repository import (
        persist_observations,
    )

    metrics = persist_observations(connection=None, observations=[])["metrics"]
    for value in metrics.values():
        assert isinstance(value, int), metrics
