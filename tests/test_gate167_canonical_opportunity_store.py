"""Gate 167: the canonical opportunity graph.

Mostly hermetic - the normalizer, identity wiring and health judgement need no
database at all, which is the point: a graph whose rules can only be exercised
by writing rows is a graph nobody can test the edges of.

The schema tests read the migration file rather than a live database, so they
assert what will be created anywhere rather than what happens to exist here.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from nativeforge.repositories.canonical_opportunity_repository import (
    CANONICAL_COLUMN_FOR_FIELD,
    IDENTITY_OUTCOMES,
    SOURCE_SCOPED_FIELDS,
    build_canonical_id,
)
from nativeforge.services.canonical_opportunity_graph_service import (
    GRAPH_TABLES,
    HEALTH_CONDITIONS,
    TENANT_COLUMNS,
    graph_health_invariant_failures,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (
    CANONICAL_FIELDS,
    OPPORTUNITY_PARSERS,
    PARSER_VERSION,
    content_fingerprint,
    extract_records,
    lifecycle_for_status,
    normalize_record,
    normalizer_invariant_failures,
    parser_for_adapter,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = (
    REPO / "alembic" / "versions" / "0053_canonical_opportunity_graph.py"
)

WRITER = (
    REPO
    / "src"
    / "nativeforge"
    / "repositories"
    / "canonical_opportunity_repository.py"
)

ADAPTER = "grants_gov_search2"


def _non_docstring_literals(path: pathlib.Path) -> list[str]:
    """Every string literal in a module EXCEPT its docstrings.

    A docstring that explains a rule contains the rule's own words. Scanning
    raw literals makes the explanation indistinguishable from a violation.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if ast.get_docstring(node, clean=False) is None:
                continue
            body = node.body[0]
            if isinstance(body, ast.Expr) and isinstance(body.value, ast.Constant):
                docstrings.add(id(body.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]

#: The Gate 163 opportunity, exactly as the stored payload carries it.
REAL_HIT = {
    "id": "363308",
    "number": "O-BJA-2026-172662",
    "title": "U.S. Department of Justice FY26 Coordinated Tribal Assistance "
    "Solicitation Notice of Funding Opportunity",
    "agency": "Bureau of Justice Assistance",
    "agencyCode": "USDOJ-OJP-BJA",
    "openDate": "07/24/2026",
    "closeDate": "10/15/2026",
    "oppStatus": "posted",
    "docType": "synopsis",
    "cfdaList": ["16.731", "16.596", "16.585", "16.710", "16.043", "16.583"],
}


# ------------------------------------------------- the schema itself


def test_no_graph_table_carries_a_tenant_column():
    """The property Gate 167L exists to protect, read from the migration.

    Every other opportunity-shaped table in this database is scoped by
    organization_id. One of these growing such a column would start storing
    the world once per customer.
    """
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", "") != "create_table":
            continue
        literals = [
            n.value
            for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        for column in TENANT_COLUMNS:
            assert column not in literals, f"{column} in a graph table"


def _check_constraint_expressions(path: pathlib.Path) -> list[str]:
    """The CHECK expressions a migration actually creates.

    From the AST, not from the file text. The migration's docstring contains a
    ```sql block quoting these constraints, and counting them by string search
    counts the explanation alongside the thing explained - which is the defect
    this campaign keeps finding in its own instruments.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
        if name not in ("CheckConstraint", "create_check_constraint"):
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(
                argument.value, str
            ):
                found.append(argument.value)
    return found


def test_the_migration_requires_evidence_on_observations_and_provenance():
    expressions = _check_constraint_expressions(MIGRATION)
    evidence = [e for e in expressions if "length(raw_payload_sha256) = 64" in e]
    assert len(evidence) == 2, expressions


def test_fuzzy_identity_cannot_present_itself_as_settled():
    # `is_provisional = true`, not `= 1`. The column is declared Boolean, and
    # SQLite accepted the integer comparison because it has no boolean type -
    # PostgreSQL refuses it outright with `operator does not exist: boolean =
    # integer`, so every such comparison was repaired for portability. The rule
    # the constraint enforces is unchanged: an L4 identity may not claim to be
    # settled.
    expressions = _check_constraint_expressions(MIGRATION)
    assert any(
        "identity_layer <> 'L4' OR is_provisional = true" in e for e in expressions
    ), expressions


def test_four_tables_not_one():
    assert len(GRAPH_TABLES) == 4
    assert len(set(GRAPH_TABLES)) == 4


# ------------------------------------------------------ the normalizer


def test_the_real_record_normalizes_to_every_supported_field():
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    assert normalized["parseable"] is True
    assert normalized["fields_absent"] == []
    assert normalizer_invariant_failures(normalized) == []
    assert normalized["provenance_fields_missing"] == []


def test_fields_the_payload_cannot_supply_are_named_not_invented():
    """A search result is not a detail record. Saying so is the whole point."""
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    assert set(normalized["fields_not_supported"]) == {
        "eligibility_text",
        "funding_amount_min",
        "funding_amount_max",
        "source_url",
    }
    for name in normalized["fields_not_supported"]:
        assert name not in normalized["fields"]


def test_every_normalized_field_maps_to_a_real_key_in_the_record():
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    field_map = OPPORTUNITY_PARSERS[ADAPTER]["field_map"]
    for name in normalized["fields"]:
        assert field_map[name] in REAL_HIT, name


def test_an_empty_string_is_absence_not_a_value():
    """An agency publishing "" for a close date has not published one."""
    normalized = normalize_record(
        record=dict(REAL_HIT, closeDate="   "), adapter_key=ADAPTER
    )
    assert "close_date" not in normalized["fields"]
    assert "close_date" in normalized["fields_absent"]


def test_an_unknown_adapter_parses_nothing_and_says_so():
    normalized = normalize_record(record=REAL_HIT, adapter_key="nf167.unknown")
    assert normalized["parseable"] is False
    assert normalized["reason"] == "no_parser_declared_for_this_adapter"
    assert normalized["fields"] == {}


def test_parser_for_an_unknown_adapter_is_none():
    assert parser_for_adapter("nf167.nope") is None
    assert parser_for_adapter(ADAPTER) is not None


def test_a_status_outside_the_vocabulary_is_unknown_not_guessed():
    assert lifecycle_for_status("posted") == "posted"
    assert lifecycle_for_status("forecasted") == "forecasted"
    assert lifecycle_for_status("something_new") == "unknown"
    assert lifecycle_for_status(None) == "unknown"


def test_the_fingerprint_follows_the_fields():
    a = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    b = normalize_record(record=dict(REAL_HIT), adapter_key=ADAPTER)
    assert a["content_fingerprint"] == b["content_fingerprint"]

    changed = normalize_record(
        record=dict(REAL_HIT, closeDate="11/01/2026"), adapter_key=ADAPTER
    )
    assert changed["content_fingerprint"] != a["content_fingerprint"]


def test_the_fingerprint_does_not_depend_on_field_order():
    assert content_fingerprint({"a": "1", "b": "2"}) == content_fingerprint(
        {"b": "2", "a": "1"}
    )


def test_a_parser_version_is_always_recorded():
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    assert normalized["parser_version"] == PARSER_VERSION
    assert PARSER_VERSION


def test_extract_records_survives_a_payload_of_the_wrong_shape():
    for payload in (None, {}, {"data": None}, {"data": {"oppHits": None}}, 7):
        assert extract_records(payload=payload, adapter_key=ADAPTER) == []


def test_the_invariant_catches_an_invented_field():
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    normalized["fields"]["funding_amount_min"] = "1000000"
    failures = normalizer_invariant_failures(normalized)
    assert any("present_and_missing" in f for f in failures)


def test_the_invariant_catches_a_field_outside_the_vocabulary():
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    normalized["fields"]["invented_column"] = "x"
    failures = normalizer_invariant_failures(normalized)
    assert any("outside_the_canonical_vocabulary" in f for f in failures)


# ------------------------------------------------------ identity


def test_canonical_ids_are_derived_and_stable():
    first = build_canonical_id(identity_layer="L1", composite_key="ABC|synopsis")
    second = build_canonical_id(identity_layer="L1", composite_key="ABC|synopsis")
    assert first == second == "L1:ABC|synopsis"


def test_forecast_and_synopsis_get_different_canonical_ids():
    """Merging them destroys the transition a Tribe is waiting for."""
    forecast = build_canonical_id(identity_layer="L1", composite_key="ABC|forecast")
    synopsis = build_canonical_id(identity_layer="L1", composite_key="ABC|synopsis")
    assert forecast != synopsis


def test_a_promoted_fuzzy_identity_changes_its_canonical_id():
    """Promotion is a change of identity basis, not a rename."""
    fuzzy = build_canonical_id(identity_layer="L4", fuzzy_key="deadbeef")
    settled = build_canonical_id(identity_layer="L1", composite_key="ABC|synopsis")
    assert fuzzy.startswith("L4:")
    assert settled.startswith("L1:")
    assert fuzzy != settled


def test_the_identity_outcome_vocabulary_is_complete():
    assert set(IDENTITY_OUTCOMES) == {
        "same_source_same_record",
        "same_opportunity_different_source",
        "amendment_or_version",
        "recurring_program",
        "new_opportunity",
        "uncertain_identity",
    }


def test_a_source_scoped_field_never_reaches_a_canonical_column():
    """Two sources' internal record keys are not a disagreement."""
    for name in SOURCE_SCOPED_FIELDS:
        assert name not in CANONICAL_COLUMN_FOR_FIELD


def test_every_canonical_column_field_is_in_the_vocabulary():
    for name in CANONICAL_COLUMN_FOR_FIELD:
        assert name in CANONICAL_FIELDS


# ------------------------------------------------------ health


def test_health_refuses_to_be_ready_with_an_unmet_condition():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True)
        | {"raw_evidence_linked": False},
        "canonical_graph_ready": True,
        "named_gaps": [],
    }
    failures = graph_health_invariant_failures(health)
    assert any("ready_with_unmet_conditions" in f for f in failures)


def test_health_refuses_to_be_ready_while_naming_a_gap():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True),
        "canonical_graph_ready": True,
        "named_gaps": ["observations_without_a_payload_row:3"],
    }
    failures = graph_health_invariant_failures(health)
    assert any("ready_with_named_gaps" in f for f in failures)


def test_health_refuses_a_condition_it_did_not_measure():
    health = {
        "conditions": {"canonical_opportunity_present": True},
        "canonical_graph_ready": False,
        "named_gaps": ["x"],
    }
    failures = graph_health_invariant_failures(health)
    assert any("condition_not_measured" in f for f in failures)


def test_health_refuses_to_be_unready_without_saying_why():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True),
        "canonical_graph_ready": False,
        "named_gaps": [],
    }
    failures = graph_health_invariant_failures(health)
    assert "not_ready_without_naming_anything" in failures


@pytest.mark.parametrize("condition", HEALTH_CONDITIONS)
def test_every_health_condition_is_named_in_the_vocabulary(condition):
    assert isinstance(condition, str) and condition


# -------------------------------------------- the writer's own shape


def test_the_writer_never_touches_the_payload_store():
    """The payload store is the evidence ledger. This graph references it."""
    # Docstrings excluded. The module docstring says the writer "never updates
    # a version in place, never deletes an observation" and names the payload
    # table - so a plain literal scan reads the sentence stating the rule as a
    # breach of it, which is exactly the failure mode this campaign hunts.
    writes = [
        text
        for text in _non_docstring_literals(WRITER)
        if "nf_source_collection_raw_payloads" in text
        and any(verb in text.upper() for verb in ("INSERT", "UPDATE", "DELETE"))
    ]
    assert writes == []


def test_the_writer_declares_no_source_specific_parser():
    """Parsing belongs to the adapter layer, keyed by adapter_key."""
    for text in _non_docstring_literals(WRITER):
        assert "grants.gov" not in text.lower()
        assert "oppHits" not in text


def test_normalized_fields_serialize_deterministically():
    normalized = normalize_record(record=REAL_HIT, adapter_key=ADAPTER)
    first = json.dumps(normalized["fields"], sort_keys=True)
    second = json.dumps(
        normalize_record(record=REAL_HIT, adapter_key=ADAPTER)["fields"],
        sort_keys=True,
    )
    assert first == second
