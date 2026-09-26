"""Gate 169: cross-source opportunity identity.

Hermetic. The identity rules are pure functions over two dicts, which is the
point: the branches that matter most here are the REFUSALS, and a refusal that
needs a fixture to reach is a refusal nobody has tested the edges of.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from nativeforge.repositories.opportunity_identity_repository import (
    ACTION_APPROVE_MERGE,
    ACTION_DEFER,
    ACTION_MARK_RELATED,
    ACTION_REJECT_MERGE,
    CANDIDATE_CAP,
    REVIEW_ACTIONS,
    REVIEW_STATES,
    IdentityWriteRefused,
    record_relationship,
    revoke_relationship,
)
from nativeforge.services.cross_source_identity_service import (
    BLOCKING_KEY_KINDS,
    CONFIDENCE_BY_DECISION,
    DISTINCT,
    EXACT_MATCH,
    FORECAST_OF,
    GENERATIVE_KEY_KINDS,
    MACHINE_SETTLEABLE,
    MATCH_DECISIONS,
    PROVISIONAL_MATCH,
    RECURRENCE_OF,
    RELATIONSHIP_FOR_DECISION,
    RELATIONSHIPS,
    REPORTING_ONLY_KEY_KINDS,
    REPUBLISHED_FROM,
    REVIEW_REQUIRED,
    SAME_AS,
    STRONG_MATCH,
    TITLE_EQUAL,
    TITLE_SUBSET,
    build_blocking_keys,
    compare_titles,
    decide_match,
    decision_invariant_failures,
    describe_identity,
)
from nativeforge.services.identity_resolution_health_service import (
    HEALTH_CONDITIONS,
    identity_health_invariant_failures,
)
from nativeforge.services.opportunity_entity_normalization_service import (
    AUTHORITATIVE,
    CORROBORATING,
    WEAK,
    extract_period,
    normalization_invariant_failures,
    normalize_funder,
    normalize_opportunity_number,
    normalize_program,
    normalize_source_url,
    normalize_title,
    title_band,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = REPO / "alembic" / "versions" / "0054_cross_source_identity.py"

TRIBAL = "U.S. Department of Justice FY26 Coordinated Tribal Assistance Solicitation"


def ident(**kw):
    return describe_identity(**kw)


# ------------------------------------------------- normalization


def test_the_year_is_removed_from_the_title_and_carried_separately():
    """The single most important normalization rule in this gate.

    Leaving the year in makes FY26 and FY27 differ by one token - close enough
    for a similarity threshold to merge them.
    """
    fy26 = normalize_title(TRIBAL)
    fy27 = normalize_title(TRIBAL.replace("FY26", "FY27"))
    assert fy26["normalized"] == fy27["normalized"]
    assert fy26["year_removed_and_carried_separately"] is True
    assert extract_period(TRIBAL)["fiscal_year"] == 2026
    assert extract_period(TRIBAL.replace("FY26", "FY27"))["fiscal_year"] == 2027


def test_a_missing_year_is_absent_not_guessed():
    period = extract_period("Tribal Assistance Solicitation")
    assert period["fiscal_year"] is None
    assert period["basis"] == "no_year_found"


def test_an_explicit_fiscal_marker_beats_a_bare_year():
    period = extract_period("FY26 program published in 2025")
    assert period["fiscal_year"] == 2026
    assert period["basis"] == "explicit_fiscal_year_marker"
    assert period["strength"] == CORROBORATING


def test_a_bare_year_is_weaker_than_a_fiscal_marker():
    assert extract_period("Program 2027")["strength"] == WEAK


def test_a_published_number_is_authoritative_and_only_reshaped():
    result = normalize_opportunity_number("O-BJA-2026-172662")
    assert result["normalized"] == "OBJA2026172662"
    assert result["strength"] == AUTHORITATIVE
    assert normalization_invariant_failures(result) == []


def test_a_funder_code_corroborates_but_a_name_never_settles():
    """The identity service refuses to match agencies by name. So does this."""
    with_code = normalize_funder(
        agency_code="USDOJ-OJP-BJA", agency_name="Bureau of Justice Assistance"
    )
    name_only = normalize_funder(agency_name="U.S. Dept. of Justice")
    assert with_code["strength"] == CORROBORATING
    assert name_only["strength"] == WEAK
    assert with_code["name_alone_can_settle_identity"] is False
    assert name_only["name_alone_can_settle_identity"] is False
    assert with_code["crosswalk_required"] is True


def test_unicode_variants_of_one_funder_compare_equal():
    assert (
        normalize_funder(agency_name="Peña Foundation")["normalized_name_key"]
        == normalize_funder(agency_name="Pena Foundation")["normalized_name_key"]
    )


def test_a_program_name_is_always_weak():
    result = normalize_program("Coordinated Tribal Assistance")
    assert result["strength"] == WEAK
    assert normalization_invariant_failures(result) == []


def test_tracking_parameters_are_stripped_and_named():
    result = normalize_source_url("https://x.gov/opp/1/?utm_source=n&id=7&gclid=z")
    assert result["normalized"] == "https://x.gov/opp/1?id=7"
    assert set(result["removed_parameters"]) == {"utm_source", "gclid"}


def test_the_invariant_catches_a_title_claiming_authority():
    result = normalize_title(TRIBAL)
    result["strength"] = AUTHORITATIVE
    assert any(
        "claimed_more_than_weak" in f
        for f in normalization_invariant_failures(result)
    )


def test_the_invariant_catches_a_funder_name_claiming_to_settle():
    result = normalize_funder(agency_name="X")
    result["name_alone_can_settle_identity"] = True
    assert "funder_name_claimed_to_settle_identity" in (
        normalization_invariant_failures(result)
    )


def test_a_title_band_groups_the_same_text_across_years():
    assert title_band("FY26 Tribal Water Program") == title_band(
        "FY27 Tribal Water Program"
    )


def test_an_empty_title_has_no_band():
    assert title_band("") is None
    assert title_band(None) is None


# ------------------------------------------------- title comparison


def test_a_dropped_agency_prefix_still_counts_as_title_agreement():
    """The aggregator case. Equality alone produced a false NEGATIVE here."""
    result = compare_titles(
        "justice coordinated tribal assistance solicitation",
        "coordinated tribal assistance solicitation",
    )
    assert result["relation"] == TITLE_SUBSET


def test_identical_titles_are_equal_not_subset():
    assert compare_titles("a b c", "a b c")["relation"] == TITLE_EQUAL


def test_a_two_token_overlap_is_not_a_subset_relation():
    """Below three tokens a subset is coincidence, not evidence."""
    assert compare_titles("a b", "a b c d")["relation"] != TITLE_SUBSET


def test_an_empty_title_relates_to_nothing():
    assert compare_titles("", "a b c")["relation"] == "unknown"


# ------------------------------------------------- match decisions


def test_identical_numbers_are_an_exact_match():
    decision = decide_match(
        left=ident(opportunity_number="O-A-1", doc_type="synopsis"),
        right=ident(opportunity_number="O-A-1", doc_type="synopsis"),
    )
    assert decision["decision"] == EXACT_MATCH
    assert decision["identity_layer"] == "L1"
    assert decision["machine_may_settle"] is True


def test_one_number_two_doc_types_is_a_forecast_link_not_a_merge():
    decision = decide_match(
        left=ident(opportunity_number="O-A-1", doc_type="forecast"),
        right=ident(opportunity_number="O-A-1", doc_type="synopsis"),
    )
    assert decision["decision"] == FORECAST_OF
    assert decision["relationship"] != SAME_AS
    assert decision["machine_may_settle"] is False


@pytest.mark.parametrize(
    ("left_title", "right_title"),
    [
        (TRIBAL, TRIBAL),
        ("Tribal Water Program", "Tribal Water Program"),
    ],
)
def test_two_different_numbers_are_distinct_whatever_the_titles_say(
    left_title, right_title
):
    """The strongest false-positive guard, and the simplest."""
    decision = decide_match(
        left=ident(
            opportunity_number="O-A-1",
            doc_type="synopsis",
            agency_code="AG-1",
            title=left_title,
        ),
        right=ident(
            opportunity_number="O-A-2",
            doc_type="synopsis",
            agency_code="AG-1",
            title=right_title,
        ),
    )
    assert decision["decision"] == DISTINCT
    assert decision["relationship"] is None
    assert any("different_published" in r for r in decision["reasons"])


def test_same_title_different_year_is_a_recurrence_never_a_merge():
    decision = decide_match(
        left=ident(
            opportunity_number="O-A-2026-1",
            doc_type="synopsis",
            agency_code="AG-1",
            title=TRIBAL,
        ),
        right=ident(
            opportunity_number="O-A-2027-1",
            doc_type="synopsis",
            agency_code="AG-1",
            title=TRIBAL.replace("FY26", "FY27"),
        ),
    )
    assert decision["decision"] == RECURRENCE_OF
    assert decision["relationship"] == RECURRENCE_OF
    assert decision["relationship"] != SAME_AS
    assert decision["machine_may_settle"] is False


def test_conflicting_funder_codes_make_records_distinct():
    decision = decide_match(
        left=ident(doc_type="synopsis", agency_code="AG-1", title="Water Program"),
        right=ident(doc_type="synopsis", agency_code="AG-2", title="Water Program"),
    )
    assert decision["decision"] == DISTINCT
    assert any("funder_codes_disagree" in r for r in decision["reasons"])


def test_an_unnumbered_republish_needs_review_or_stays_provisional():
    decision = decide_match(
        left=ident(
            opportunity_number="O-A-1",
            doc_type="synopsis",
            agency_code="AG-1",
            title=TRIBAL,
        ),
        right=ident(
            doc_type="synopsis",
            agency_code="AG-1",
            title="FY26 Coordinated Tribal Assistance Solicitation",
        ),
    )
    assert decision["decision"] in (
        REPUBLISHED_FROM,
        PROVISIONAL_MATCH,
        REVIEW_REQUIRED,
    )
    assert decision["machine_may_settle"] is False


def test_nothing_in_common_is_distinct():
    decision = decide_match(
        left=ident(doc_type="synopsis", title="Alpha"),
        right=ident(doc_type="synopsis", title="Beta"),
    )
    assert decision["decision"] == DISTINCT


def test_every_decision_names_a_reason():
    """A refusal nobody can argue with is a refusal nobody can review."""
    pairs = [
        (ident(), ident()),
        (ident(opportunity_number="A"), ident(opportunity_number="B")),
        (ident(title="X Y Z"), ident(title="X Y Z")),
    ]
    for left, right in pairs:
        decision = decide_match(left=left, right=right)
        assert decision["reasons"], decision


def test_only_exact_or_strong_may_be_machine_settled():
    assert MACHINE_SETTLEABLE == frozenset({EXACT_MATCH, STRONG_MATCH})


def test_recurrence_and_forecast_never_map_to_a_merge():
    assert RELATIONSHIP_FOR_DECISION[RECURRENCE_OF] != SAME_AS
    assert RELATIONSHIP_FOR_DECISION[FORECAST_OF] != SAME_AS


def test_distinct_and_review_propose_no_relationship():
    assert RELATIONSHIP_FOR_DECISION[DISTINCT] is None
    assert RELATIONSHIP_FOR_DECISION[REVIEW_REQUIRED] is None


def test_every_decision_has_a_declared_confidence():
    for name in MATCH_DECISIONS:
        assert name in CONFIDENCE_BY_DECISION, name
        assert 0.0 <= CONFIDENCE_BY_DECISION[name] <= 1.0


def test_confidence_is_declared_as_a_policy_not_a_probability():
    decision = decide_match(
        left=ident(opportunity_number="O-A-1", doc_type="synopsis"),
        right=ident(opportunity_number="O-A-1", doc_type="synopsis"),
    )
    assert decision["confidence_is_a_declared_policy_not_a_probability"] is True


def test_the_invariant_catches_a_fuzzy_decision_claiming_settleability():
    decision = decide_match(
        left=ident(title="X Y Z"), right=ident(title="X Y Z")
    )
    decision["machine_may_settle"] = True
    assert any(
        "machine_settleable_at_a_probabilistic_layer" in f
        for f in decision_invariant_failures(decision)
    )


def test_the_invariant_catches_a_recurrence_proposed_as_a_merge():
    decision = decide_match(
        left=ident(
            opportunity_number="O-A-2026-1", doc_type="synopsis", title=TRIBAL
        ),
        right=ident(
            opportunity_number="O-A-2027-1",
            doc_type="synopsis",
            title=TRIBAL.replace("FY26", "FY27"),
        ),
    )
    decision["relationship"] = SAME_AS
    assert "recurrence_proposed_as_a_merge" in decision_invariant_failures(decision)


def test_the_invariant_catches_a_decision_with_no_reason():
    decision = decide_match(left=ident(), right=ident())
    decision["reasons"] = []
    assert "decision_named_no_reason" in decision_invariant_failures(decision)


# ------------------------------------------------- blocking


def test_only_selective_keys_generate_candidates():
    """Measured, not assumed: both excluded kinds grew with the graph."""
    assert GENERATIVE_KEY_KINDS.isdisjoint(REPORTING_ONLY_KEY_KINDS)
    assert "funder_and_period" in REPORTING_ONLY_KEY_KINDS
    assert "title_band" in REPORTING_ONLY_KEY_KINDS
    assert "opportunity_number" in GENERATIVE_KEY_KINDS
    assert "funder_period_title" in GENERATIVE_KEY_KINDS


def test_every_generative_key_is_in_the_schema_vocabulary():
    for kind in GENERATIVE_KEY_KINDS | REPORTING_ONLY_KEY_KINDS:
        assert kind in BLOCKING_KEY_KINDS, kind


def test_a_record_with_nothing_published_produces_no_keys():
    assert build_blocking_keys(ident()) == []


def test_blocking_keys_are_deduplicated():
    keys = build_blocking_keys(
        ident(
            opportunity_number="O-A-1",
            doc_type="synopsis",
            agency_code="AG-1",
            title=TRIBAL,
            source_record_id="1",
            source_id="s",
        )
    )
    pairs = [(k["key_kind"], k["key_value"]) for k in keys]
    assert len(pairs) == len(set(pairs))


def test_the_candidate_cap_is_bounded():
    assert 1 <= CANDIDATE_CAP <= 10000


# ------------------------------------------------- the schema rules


def _literal_text(node: ast.AST) -> str:
    """Reconstruct a string argument that may be an f-string concatenation.

    The migration builds several CHECK expressions as implicit concatenations
    that include an f-string calling a helper - so the argument node is a
    `JoinedStr`, not a `Constant`. A helper that only read `Constant` args
    silently saw none of those constraints and reported them absent.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_literal_text(part) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        # The interpolated helper call is opaque here; its SHAPE is what the
        # assertions below care about, so a placeholder keeps the surrounding
        # literal text intact.
        return "<interpolated>"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal_text(node.left) + _literal_text(node.right)
    return ""


def _check_expressions() -> list[str]:
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
        if name not in ("CheckConstraint", "create_check_constraint"):
            continue
        for argument in node.args:
            text = _literal_text(argument)
            if text:
                found.append(text)
    return found


def test_a_fuzzy_same_as_without_review_is_unrepresentable():
    """THE constraint of this gate, read from the migration."""
    expressions = _check_expressions()
    assert any(
        "SAME_AS" in e and "human_review" in e for e in expressions
    ), expressions


def test_probabilistic_layers_must_be_provisional():
    """The layer list is interpolated, so the assertion checks the shape."""
    expressions = _check_expressions()
    assert any(
        "is_provisional = true" in e and "identity_layer" in e for e in expressions
    ), expressions
    # And the layers themselves come from the migration's own constant.
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'PROVISIONAL_LAYERS = ("L3", "L4")' in source


def test_a_resolution_needs_a_signature():
    expressions = _check_expressions()
    assert any(
        "approved_merge" in e and "reviewed_by" in e for e in expressions
    ), expressions


def test_a_revocation_is_attributed():
    expressions = _check_expressions()
    assert any(
        "revoked_at" in e and "revoked_by" in e for e in expressions
    ), expressions


def test_an_opportunity_cannot_relate_to_itself():
    expressions = _check_expressions()
    assert any(
        "from_canonical_id <> to_canonical_id" in e for e in expressions
    ), expressions


# ------------------------------------------------- write refusals


def test_the_repository_refuses_a_fuzzy_automatic_merge():
    with pytest.raises(IdentityWriteRefused) as caught:
        record_relationship(
            connection=None,
            from_canonical_id="L1:A|synopsis",
            to_canonical_id="L4:beef",
            relationship=SAME_AS,
            match_decision=REVIEW_REQUIRED,
            identity_layer="L4",
            decided_by="derived",
        )
    assert any("human_decision" in r for r in caught.value.reasons)


def test_the_repository_refuses_a_self_relationship():
    with pytest.raises(IdentityWriteRefused) as caught:
        record_relationship(
            connection=None,
            from_canonical_id="L1:A|synopsis",
            to_canonical_id="L1:A|synopsis",
            relationship=SAME_AS,
            match_decision=EXACT_MATCH,
            identity_layer="L1",
        )
    assert "an_opportunity_is_not_related_to_itself" in caught.value.reasons


def test_the_repository_refuses_an_unnamed_human_decision():
    with pytest.raises(IdentityWriteRefused) as caught:
        record_relationship(
            connection=None,
            from_canonical_id="A",
            to_canonical_id="B",
            relationship=SAME_AS,
            match_decision=REVIEW_REQUIRED,
            identity_layer="L4",
            decided_by="human_review",
            reviewer="",
        )
    assert any("name_the_human" in r for r in caught.value.reasons)


def test_the_repository_refuses_an_unsigned_revocation():
    with pytest.raises(IdentityWriteRefused) as caught:
        revoke_relationship(
            connection=None, relationship_id="x", revoked_by="", reason=""
        )
    assert "a_revocation_must_name_who_and_why" in caught.value.reasons


def test_every_review_action_maps_to_a_state():
    for action in (
        ACTION_APPROVE_MERGE,
        ACTION_REJECT_MERGE,
        ACTION_MARK_RELATED,
        ACTION_DEFER,
    ):
        assert action in REVIEW_ACTIONS
        assert REVIEW_ACTIONS[action] in REVIEW_STATES


def test_every_relationship_kind_is_in_the_vocabulary():
    for decision, relationship in RELATIONSHIP_FOR_DECISION.items():
        if relationship is not None:
            assert relationship in RELATIONSHIPS, decision


# ------------------------------------------------- health


def test_health_refuses_readiness_with_an_unmet_condition():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True)
        | {"no_illegal_l4_settled_merges": False},
        "identity_resolution_ready": True,
        "named_gaps": [],
    }
    assert any(
        "ready_with_unmet_conditions" in f
        for f in identity_health_invariant_failures(health)
    )


def test_health_refuses_readiness_while_naming_a_gap():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True),
        "identity_resolution_ready": True,
        "named_gaps": ["two_published_numbers_merged_as_one:1"],
    }
    assert any(
        "ready_with_named_gaps" in f
        for f in identity_health_invariant_failures(health)
    )


def test_health_refuses_a_condition_it_did_not_measure():
    health = {
        "conditions": {"identity_layers_valid": True},
        "identity_resolution_ready": False,
        "named_gaps": ["x"],
    }
    assert any(
        "condition_not_measured" in f
        for f in identity_health_invariant_failures(health)
    )


def test_all_ten_health_conditions_are_declared():
    assert len(HEALTH_CONDITIONS) == 10
    assert len(set(HEALTH_CONDITIONS)) == 10
