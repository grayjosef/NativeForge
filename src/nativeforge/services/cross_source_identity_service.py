"""Deciding whether two canonical opportunities are the same thing (Gate 169D-J).

Gate 167 gives one opportunity many observations, keyed on the L1 composite
`(normalized_opportunity_number, doc_type)`. That already unifies two sources
that both cite the federal number - and it is the easy half.

This module handles the hard half: sources that describe one opportunity
WITHOUT agreeing on an identifier, and sources whose records look identical
but are not the same opportunity at all.

## The decision is never a boolean

```text
EXACT_MATCH        the same published identifier
STRONG_MATCH       different identifiers, corroborated by declared codes
FORECAST_OF        one number, a forecast and the posting it became
RECURRENCE_OF      the same program in a different fiscal year
REPUBLISHED_FROM   an aggregator carrying somebody else's opportunity
PROVISIONAL_MATCH  plausible, resting on weak evidence
REVIEW_REQUIRED    plausible, and not decidable without a human
DISTINCT           and the reason it is distinct, named
```

`is_duplicate` as a boolean would collapse six of these into one, and the one
it would collapse them into is the wrong answer for five.

## The strongest false-positive guard is the simplest

**Two different published opportunity numbers mean two different
solicitations.** Not similar, not probably-related: distinct. Agencies do not
reuse numbers across programs, and every hard negative in Gate 169F that
involves two numbered records is refused on that single rule before any title
comparison runs.

The dangerous cases are the ones where that rule cannot fire - where one side
has no number at all. Those reach the weak evidence, and weak evidence
produces a CANDIDATE, never a merge.

## Annual recurrences are the trap

An FY26 and an FY27 solicitation from one agency share their title almost
word for word. A title-similarity matcher merges them, and a Tribe is then
shown a closed opportunity as though it were open, or an open one dated last
year. So the fiscal year is extracted BEFORE comparison and a year difference
converts any same-title finding into `RECURRENCE_OF` - a real relationship,
and explicitly not a merge.

## Confidence is a declared policy, not a learned score

`CONFIDENCE_BY_DECISION` is a table in this file. It is not a probability and
does not pretend to be calibrated - inventing 0.83 would be fabrication
wearing a decimal point. It orders candidates for review, and nothing else
reads it to decide anything.

Nothing here writes. Nothing here fetches.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.opportunity_entity_normalization_service import (
    extract_period,
    normalize_funder,
    normalize_opportunity_number,
    normalize_program,
    normalize_title,
    title_band,
)

SCHEMA_VERSION = "nf_cross_source_identity_v1"

# ------------------------------------------------------- decisions

EXACT_MATCH = "EXACT_MATCH"
STRONG_MATCH = "STRONG_MATCH"
PROVISIONAL_MATCH = "PROVISIONAL_MATCH"
DISTINCT = "DISTINCT"
VERSION_OF = "VERSION_OF"
RECURRENCE_OF = "RECURRENCE_OF"
FORECAST_OF = "FORECAST_OF"
REPUBLISHED_FROM = "REPUBLISHED_FROM"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

MATCH_DECISIONS: tuple[str, ...] = (
    EXACT_MATCH,
    STRONG_MATCH,
    PROVISIONAL_MATCH,
    DISTINCT,
    VERSION_OF,
    RECURRENCE_OF,
    FORECAST_OF,
    REPUBLISHED_FROM,
    REVIEW_REQUIRED,
)

# ---------------------------------------------------- relationships

SAME_AS = "SAME_AS"
RELATED_TO = "RELATED_TO"

RELATIONSHIPS: tuple[str, ...] = (
    SAME_AS,
    VERSION_OF,
    RECURRENCE_OF,
    FORECAST_OF,
    REPUBLISHED_FROM,
    RELATED_TO,
)

#: Which relationship each decision proposes. `DISTINCT` and `REVIEW_REQUIRED`
#: propose none - the first because there is nothing to record, the second
#: because proposing one would be the decision it is deferring.
RELATIONSHIP_FOR_DECISION: dict[str, str | None] = {
    EXACT_MATCH: SAME_AS,
    STRONG_MATCH: SAME_AS,
    REPUBLISHED_FROM: REPUBLISHED_FROM,
    FORECAST_OF: FORECAST_OF,
    RECURRENCE_OF: RECURRENCE_OF,
    VERSION_OF: VERSION_OF,
    PROVISIONAL_MATCH: SAME_AS,
    REVIEW_REQUIRED: None,
    DISTINCT: None,
}

#: A declared ordering for review queues. NOT a calibrated probability.
CONFIDENCE_BY_DECISION: dict[str, float] = {
    EXACT_MATCH: 1.0,
    FORECAST_OF: 0.95,
    # A version of one opportunity is as certain as the number it shares.
    VERSION_OF: 0.95,
    STRONG_MATCH: 0.9,
    RECURRENCE_OF: 0.7,
    REPUBLISHED_FROM: 0.7,
    PROVISIONAL_MATCH: 0.5,
    REVIEW_REQUIRED: 0.4,
    DISTINCT: 0.0,
}

#: Decisions a machine may write as a settled SAME_AS. Everything else needs
#: a human, and migration 0054 refuses the alternative at rest.
MACHINE_SETTLEABLE: frozenset[str] = frozenset({EXACT_MATCH, STRONG_MATCH})

# ------------------------------------------------------ blocking

KEY_OPPORTUNITY_NUMBER = "opportunity_number"
KEY_FUNDER_AND_PERIOD = "funder_and_period"
KEY_FUNDER_PERIOD_TITLE = "funder_period_title"
KEY_TITLE_BAND = "title_band"
KEY_PROGRAM_FAMILY = "program_family"
KEY_SOURCE_RECORD_ALIAS = "source_record_alias"

BLOCKING_KEY_KINDS: tuple[str, ...] = (
    KEY_OPPORTUNITY_NUMBER,
    KEY_FUNDER_AND_PERIOD,
    KEY_FUNDER_PERIOD_TITLE,
    KEY_TITLE_BAND,
    KEY_PROGRAM_FAMILY,
    KEY_SOURCE_RECORD_ALIAS,
)

#: Keys selective enough to GENERATE candidates from, per observation.
#:
#: Two kinds are deliberately excluded, both measured rather than assumed:
#:
#: ```text
#: funder_and_period   25 -> 125 -> 201 candidates at 1k -> 5k -> 10k
#: title_band           4 ->  20 ->  40 candidates at 1k -> 5k -> 10k
#: ```
#:
#: Both grow with the corpus, for the same reason: a fleet has a bounded
#: number of funders, and title bands collide heavily because a band is a few
#: sorted tokens. Walking either per observation is the fleet scan this design
#: exists to replace.
#:
#: **This is a trade, and it costs recall.** Two records with the same title,
#: no shared funder CODE and no published number will not become candidates
#: here. That case is L4 - the weakest, highest-risk match in the model, the
#: one that could never settle automatically anyway - so the cost falls where
#: it should. Recovering it needs a deliberate, rate-limited review sweep,
#: which is a different operation with a different budget and is NOT built in
#: this gate.
#:
#: The excluded keys are still WRITTEN: they are useful for reporting, for a
#: human browsing one funder's year, and for exactly that future sweep.
GENERATIVE_KEY_KINDS: frozenset[str] = frozenset(
    {
        KEY_OPPORTUNITY_NUMBER,
        KEY_FUNDER_PERIOD_TITLE,
        KEY_SOURCE_RECORD_ALIAS,
    }
)

#: Written and indexed, but never walked per observation. Named so the
#: distinction is inspectable rather than implied by an absence.
REPORTING_ONLY_KEY_KINDS: frozenset[str] = frozenset(
    {KEY_FUNDER_AND_PERIOD, KEY_TITLE_BAND, KEY_PROGRAM_FAMILY}
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def describe_identity(
    *,
    opportunity_number: Any = None,
    doc_type: Any = None,
    agency_code: Any = None,
    agency_name: Any = None,
    program: Any = None,
    title: Any = None,
    source_record_id: Any = None,
    source_id: Any = None,
) -> dict[str, Any]:
    """Everything identity comparison needs about one record, normalized.

    Built once per record and reused, because normalizing inside a comparison
    loop is how an O(candidates) decision becomes an O(candidates x fields)
    one.
    """
    number = normalize_opportunity_number(opportunity_number)
    funder = normalize_funder(agency_code=agency_code, agency_name=agency_name)
    title_normalized = normalize_title(title)
    period = extract_period(title, opportunity_number)
    program_normalized = normalize_program(program)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "number": number["normalized"],
            "number_strength": number["strength"],
            "has_published_number": bool(number["normalized"]),
            "doc_type": str(doc_type or "").strip().lower() or None,
            "funder_code": funder["normalized_code"],
            "funder_name_key": funder["normalized_name_key"],
            "funder_strength": funder["strength"],
            "program_key": program_normalized["normalized"],
            "title_key": title_normalized["normalized"],
            "title_tokens": title_normalized["token_count"],
            "title_band": title_band(title),
            "fiscal_year": period["fiscal_year"],
            "fiscal_year_basis": period["basis"],
            "source_record_id": (
                str(source_record_id) if source_record_id is not None else None
            ),
            "source_id": str(source_id) if source_id is not None else None,
        }
    )


def build_blocking_keys(identity: dict[str, Any]) -> list[dict[str, str]]:
    """The deterministic buckets this record belongs in.

    Candidate generation looks these up. Every key here is exact-match
    indexable, which is what keeps the candidate set bounded relative to the
    graph rather than proportional to it - there is deliberately no key whose
    lookup is a scan, a LIKE or a range.
    """
    keys: list[dict[str, str]] = []

    number = identity.get("number")
    if number:
        keys.append({"key_kind": KEY_OPPORTUNITY_NUMBER, "key_value": number})

    funder = identity.get("funder_code") or identity.get("funder_name_key")
    year = identity.get("fiscal_year")
    band = identity.get("title_band")

    if funder and year:
        keys.append(
            {"key_kind": KEY_FUNDER_AND_PERIOD, "key_value": f"{funder}|{year}"}
        )

    # The workhorse: selective enough to generate candidates from, and still
    # exactly the shape that catches a republished opportunity - same funder,
    # same fiscal year, same title. Funder-and-year alone is not.
    if funder and year and band:
        keys.append(
            {
                "key_kind": KEY_FUNDER_PERIOD_TITLE,
                "key_value": f"{funder}|{year}|{band}",
            }
        )

    if band:
        keys.append({"key_kind": KEY_TITLE_BAND, "key_value": band})

    program = identity.get("program_key")
    if program:
        keys.append({"key_kind": KEY_PROGRAM_FAMILY, "key_value": program})

    source_id = identity.get("source_id")
    record_id = identity.get("source_record_id")
    if source_id and record_id:
        keys.append(
            {
                "key_kind": KEY_SOURCE_RECORD_ALIAS,
                "key_value": f"{source_id}|{record_id}",
            }
        )

    # De-duplicated, because the same value can arrive from two fields and a
    # duplicate key would inflate the measured candidate count.
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for key in keys:
        pair = (key["key_kind"], key["key_value"])
        if pair in seen:
            continue
        seen.add(pair)
        unique.append(key)
    return unique


TITLE_EQUAL = "equal"
TITLE_SUBSET = "one_is_a_subset_of_the_other"
TITLE_DISJOINT = "disjoint"
TITLE_UNKNOWN = "unknown"

TITLE_RELATIONS: tuple[str, ...] = (
    TITLE_EQUAL,
    TITLE_SUBSET,
    TITLE_DISJOINT,
    TITLE_UNKNOWN,
)


def compare_titles(left: Any, right: Any) -> dict[str, Any]:
    """How two normalized title keys relate. Structural, no threshold.

    Exact equality alone is too brittle for the case this gate exists to
    handle. An aggregator republishing a federal opportunity routinely drops
    the agency prefix - "Justice FY26 Coordinated Tribal Assistance" becomes
    "FY26 Coordinated Tribal Assistance" - and under equality the republish
    rule never fires. The system then answers DISTINCT, which is a false
    NEGATIVE: safer than a false merge, but it defeats the purpose.

    So a STRICT SUBSET also counts as title agreement, and is reported as
    weaker than equality. Subset is deterministic - no similarity score, no
    tuned cutoff, nothing that drifts when somebody adjusts a constant.

    A single shared token is not a subset relation worth acting on, so a
    minimum length applies to the smaller side; below it the answer is
    `disjoint` rather than a subset nobody should trust.
    """
    left_tokens = {t for t in str(left or "").split() if t}
    right_tokens = {t for t in str(right or "").split() if t}

    if not left_tokens or not right_tokens:
        return {"relation": TITLE_UNKNOWN, "shared_tokens": 0}

    if left_tokens == right_tokens:
        return {"relation": TITLE_EQUAL, "shared_tokens": len(left_tokens)}

    smaller, larger = sorted((left_tokens, right_tokens), key=len)
    #: Below three meaningful tokens a subset is coincidence, not evidence.
    if smaller < larger and len(smaller) >= 3:
        return {
            "relation": TITLE_SUBSET,
            "shared_tokens": len(smaller),
            "dropped_tokens": sorted(larger - smaller),
        }

    return {
        "relation": TITLE_DISJOINT,
        "shared_tokens": len(left_tokens & right_tokens),
    }


def decide_match(
    *, left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """Compare two records. Returns a decision, a layer, evidence and reasons.

    Pure. Every branch is reachable from two dicts, which matters more here
    than anywhere else in this campaign: an identity rule that can only be
    exercised by writing rows is a rule whose edges nobody has tested.
    """
    reasons: list[str] = []
    evidence: dict[str, Any] = {}

    left_number = left.get("number")
    right_number = right.get("number")
    left_year = left.get("fiscal_year")
    right_year = right.get("fiscal_year")
    titles = compare_titles(left.get("title_key"), right.get("title_key"))
    title_relation = titles["relation"]
    # Equality OR a strict subset counts as title agreement; the difference in
    # strength is carried into the evidence rather than flattened.
    same_title = title_relation in (TITLE_EQUAL, TITLE_SUBSET)
    titles_exactly_equal = title_relation == TITLE_EQUAL

    same_funder_code = bool(
        left.get("funder_code") and left.get("funder_code") == right.get("funder_code")
    )
    # Two DECLARED codes that disagree is positive evidence of difference, not
    # merely absent evidence of sameness. Without this the engine treated
    # "different funders, same title" as something to review.
    funder_codes_conflict = bool(
        left.get("funder_code")
        and right.get("funder_code")
        and left.get("funder_code") != right.get("funder_code")
    )
    same_funder_name = bool(
        left.get("funder_name_key")
        and left.get("funder_name_key") == right.get("funder_name_key")
    )
    same_program = bool(
        left.get("program_key")
        and left.get("program_key") == right.get("program_key")
    )
    years_known = left_year is not None and right_year is not None
    years_differ = years_known and left_year != right_year

    evidence.update(
        {
            "numbers": [left_number, right_number],
            "doc_types": [left.get("doc_type"), right.get("doc_type")],
            "fiscal_years": [left_year, right_year],
            "same_title_key": same_title,
            "title_relation": title_relation,
            "title_shared_tokens": titles.get("shared_tokens"),
            "same_funder_code": same_funder_code,
            "funder_codes_conflict": funder_codes_conflict,
            "same_funder_name_key": same_funder_name,
            "same_program_key": same_program,
        }
    )

    def result(decision: str, layer: str) -> dict[str, Any]:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "decision": decision,
                "identity_layer": layer,
                "relationship": RELATIONSHIP_FOR_DECISION.get(decision),
                "confidence": CONFIDENCE_BY_DECISION.get(decision),
                "confidence_is_a_declared_policy_not_a_probability": True,
                "machine_may_settle": decision in MACHINE_SETTLEABLE,
                "evidence": evidence,
                "reasons": sorted(set(reasons)),
            }
        )

    # ---- 1. both published a number ---------------------------------
    if left_number and right_number:
        if left_number == right_number:
            left_doc = left.get("doc_type")
            right_doc = right.get("doc_type")
            if left_doc and right_doc and left_doc != right_doc:
                # One number, two document kinds: the forecast and the posting
                # it became. Deterministic, and NOT a merge - merging would
                # destroy the transition.
                reasons.append(
                    "one_published_number_with_two_document_types_"
                    f"{left_doc}_and_{right_doc}"
                )
                return result(FORECAST_OF, "L1")
            reasons.append("identical_published_opportunity_numbers")
            return result(EXACT_MATCH, "L1")

        # THE false-positive guard. Two numbers that differ are two
        # solicitations, whatever their titles say.
        reasons.append(
            f"different_published_opportunity_numbers:{left_number}!={right_number}"
        )
        if same_title and years_differ:
            reasons.append(
                f"same_title_in_different_fiscal_years:{left_year}!={right_year}"
            )
            # A real relationship, deliberately not a merge.
            return result(RECURRENCE_OF, "L2" if same_funder_code else "L3")
        if same_title and same_funder_code and not years_differ:
            reasons.append(
                "same_title_and_funder_but_distinct_numbers_"
                "which_agencies_do_not_reuse_across_solicitations"
            )
            return result(DISTINCT, "L1")
        if same_program:
            reasons.append("same_program_family_but_distinct_numbers")
        return result(DISTINCT, "L1")

    # ---- 2. exactly one published a number ---------------------------
    #
    # The aggregator case: somebody republished an opportunity without citing
    # its number. This is where real merges are needed and where false merges
    # are cheapest, so nothing here settles.
    if bool(left_number) != bool(right_number):
        reasons.append("only_one_side_published_an_opportunity_number")
        if years_differ:
            reasons.append(
                f"fiscal_years_differ:{left_year}!={right_year}"
            )
            return result(RECURRENCE_OF, "L3")
        if funder_codes_conflict:
            # Two declared codes that disagree. Whatever the titles say, these
            # are different funders.
            reasons.append(
                "declared_funder_codes_disagree:"
                f"{left.get('funder_code')}!={right.get('funder_code')}"
            )
            return result(DISTINCT, "L2")
        if same_title and (same_funder_code or same_funder_name):
            reasons.append("same_title_key_and_same_funder")
            if same_funder_code:
                reasons.append(
                    "funder_matched_on_a_declared_code_which_corroborates_"
                    "but_does_not_settle"
                )
                return result(REPUBLISHED_FROM, "L3")
            reasons.append(
                "funder_matched_on_name_only_and_names_span_"
                "non_aligned_namespaces"
            )
            return result(REVIEW_REQUIRED, "L4")
        if same_title:
            reasons.append("same_title_key_but_no_funder_agreement")
            return result(REVIEW_REQUIRED, "L4")
        reasons.append("no_corroborating_identity_evidence")
        return result(DISTINCT, "L4")

    # ---- 3. neither published a number -------------------------------
    reasons.append("neither_side_published_an_opportunity_number")
    if years_differ:
        reasons.append(f"fiscal_years_differ:{left_year}!={right_year}")
        if same_title:
            return result(RECURRENCE_OF, "L3")
        return result(DISTINCT, "L3")

    if funder_codes_conflict:
        reasons.append(
            "declared_funder_codes_disagree:"
            f"{left.get('funder_code')}!={right.get('funder_code')}"
        )
        return result(DISTINCT, "L2")

    if same_title and same_funder_code:
        reasons.append("same_title_key_and_same_declared_funder_code")
        if not titles_exactly_equal:
            reasons.append(
                f"titles_agree_by_subset_not_equality:{title_relation}"
            )
        return result(PROVISIONAL_MATCH, "L3")
    if same_title and same_funder_name:
        reasons.append("same_title_key_and_same_funder_name_only")
        return result(REVIEW_REQUIRED, "L4")
    if same_title:
        reasons.append("same_title_key_alone")
        return result(REVIEW_REQUIRED, "L4")

    reasons.append("no_shared_identity_evidence")
    return result(DISTINCT, "L4")


def decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a decision that grants more than its evidence supports."""
    fails: list[str] = []

    name = decision.get("decision")
    if name not in MATCH_DECISIONS:
        fails.append(f"decision_outside_the_vocabulary:{name}")

    layer = decision.get("identity_layer")
    if layer not in ("L1", "L2", "L3", "L4"):
        fails.append(f"identity_layer_outside_the_vocabulary:{layer}")

    relationship = decision.get("relationship")
    if relationship is not None and relationship not in RELATIONSHIPS:
        fails.append(f"relationship_outside_the_vocabulary:{relationship}")

    # THE rule of this gate. A machine-settleable SAME_AS may only come from
    # a layer strong enough to support it.
    if decision.get("machine_may_settle") and layer not in ("L1", "L2"):
        fails.append(f"machine_settleable_at_a_probabilistic_layer:{layer}")

    if name in MACHINE_SETTLEABLE and not decision.get("machine_may_settle"):
        fails.append(f"settleable_decision_not_marked_settleable:{name}")

    if name not in MACHINE_SETTLEABLE and decision.get("machine_may_settle"):
        fails.append(f"unsettleable_decision_marked_settleable:{name}")

    # A refusal that names nothing cannot be reviewed or argued with.
    if not decision.get("reasons"):
        fails.append("decision_named_no_reason")

    # A recurrence must never be proposed as a merge.
    if name == RECURRENCE_OF and relationship == SAME_AS:
        fails.append("recurrence_proposed_as_a_merge")

    # A forecast must never be proposed as a merge either.
    if name == FORECAST_OF and relationship == SAME_AS:
        fails.append("forecast_proposed_as_a_merge")

    if name == DISTINCT and relationship is not None:
        fails.append("distinct_proposed_a_relationship")

    if name == REVIEW_REQUIRED and relationship is not None:
        fails.append("review_required_proposed_a_relationship")

    return sorted(set(fails))
