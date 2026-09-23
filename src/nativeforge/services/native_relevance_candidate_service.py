"""Gate 173F: the high-recall first stage.

This stage answers one question - **could this possibly be Native-relevant?** -
and it is allowed to be wrong in one direction only.

```text
a false positive costs a reviewer a minute
a false negative costs a Tribe a funding cycle
```

So the rule is deliberately asymmetric. ANY candidate signal makes something a
candidate. Nothing is rejected for lacking Native keywords, because the
product principle is that a Native-relevant opportunity frequently has none:
a broadband program open to "units of general local government and Indian
tribes" says the word once, in a list, on page 14 of an attachment; a
Grants.gov record coded `99 - Unrestricted` says nothing at all and is open to
every Tribe in the country.

The third state is the one that makes this honest. `NOT_CANDIDATE` is a
FINDING and requires evidence to support it - specifically, enough eligibility
evidence that an absence of Native signals means something. With no evidence
at all the answer is `UNKNOWN`, never `NOT_CANDIDATE`, because "we have not
looked" and "we looked and it is not relevant" are different facts and
collapsing them is how a discovery pipeline silently stops discovering.

The applicant-code reading is delegated to
`native_eligibility_code_classification_service`, which already holds the
Grants.gov and SAM vocabularies and already knows that an absent code is not a
negative finding. This module does not restate those tables.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_eligibility_code_classification_service import (
    classify_native_eligibility,
)
from nativeforge.services.native_relevance_evidence_service import (
    APPLICANT_BEARING,
    APPLICANT_ELIGIBILITY,
    BENEFICIARY_POPULATION,
    DEFINITE_ENOUGH,
    DOCUMENT_REFERENCE,
    GEOGRAPHIC_RELEVANCE,
    PRIOR_NATIVE_AWARDS,
    PROGRAM_HISTORY,
    PROGRAM_PURPOSE,
    SECTOR_ALIGNMENT,
    SOURCE_CONTEXT,
    STATUTORY_LANGUAGE,
)

SCHEMA_VERSION = "nf_native_relevance_candidate_v1"

CANDIDATE = "CANDIDATE"
NOT_CANDIDATE = "NOT_CANDIDATE"
UNKNOWN = "UNKNOWN"

CANDIDATE_STATES: tuple[str, ...] = (CANDIDATE, NOT_CANDIDATE, UNKNOWN)

# --------------------------------------------------------------------
# the signals
# --------------------------------------------------------------------

NATIVE_TERMINOLOGY = "native_terminology_in_operative_text"
NATIVE_APPLICANT_CODE = "native_applicant_eligibility_code"
UNRESTRICTED_ELIGIBILITY = "unrestricted_or_read_the_text_eligibility"
GENERAL_GOVERNMENT_ELIGIBILITY = "general_government_eligibility"
BROAD_ENTITY_ELIGIBILITY = "broad_entity_eligibility"
NATIVE_GEOGRAPHY = "native_geography"
NATIVE_BENEFICIARY = "native_beneficiary_population"
PROGRAM_HISTORY_SIGNAL = "agency_or_program_history"
PRIOR_AWARD_SIGNAL = "prior_native_award_under_this_program"
SECTOR_COMPATIBILITY = "sector_compatibility"
PROGRAM_AUTHORITY = "program_authority_names_native_entities"
NATIVE_SERVING_SOURCE = "native_serving_source_context"
DOCUMENT_EVIDENCE = "document_evidence"

CANDIDATE_SIGNALS: tuple[str, ...] = (
    NATIVE_TERMINOLOGY,
    NATIVE_APPLICANT_CODE,
    UNRESTRICTED_ELIGIBILITY,
    GENERAL_GOVERNMENT_ELIGIBILITY,
    BROAD_ENTITY_ELIGIBILITY,
    NATIVE_GEOGRAPHY,
    NATIVE_BENEFICIARY,
    PROGRAM_HISTORY_SIGNAL,
    PRIOR_AWARD_SIGNAL,
    SECTOR_COMPATIBILITY,
    PROGRAM_AUTHORITY,
    NATIVE_SERVING_SOURCE,
    DOCUMENT_EVIDENCE,
)

#: Which evidence type each signal is read from. One owner per signal, so a
#: signal cannot fire from evidence that has nothing to do with it.
SIGNAL_EVIDENCE_TYPE: dict[str, str] = {
    NATIVE_TERMINOLOGY: PROGRAM_PURPOSE,
    NATIVE_APPLICANT_CODE: APPLICANT_ELIGIBILITY,
    UNRESTRICTED_ELIGIBILITY: APPLICANT_ELIGIBILITY,
    GENERAL_GOVERNMENT_ELIGIBILITY: APPLICANT_ELIGIBILITY,
    BROAD_ENTITY_ELIGIBILITY: APPLICANT_ELIGIBILITY,
    NATIVE_GEOGRAPHY: GEOGRAPHIC_RELEVANCE,
    NATIVE_BENEFICIARY: BENEFICIARY_POPULATION,
    PROGRAM_HISTORY_SIGNAL: PROGRAM_HISTORY,
    PRIOR_AWARD_SIGNAL: PRIOR_NATIVE_AWARDS,
    SECTOR_COMPATIBILITY: SECTOR_ALIGNMENT,
    PROGRAM_AUTHORITY: STATUTORY_LANGUAGE,
    NATIVE_SERVING_SOURCE: SOURCE_CONTEXT,
    DOCUMENT_EVIDENCE: DOCUMENT_REFERENCE,
}

#: Applicant-eligibility categories that are general rather than Native, and
#: which therefore still make something a candidate: a program open to every
#: unit of government is open to Tribes in most federal programs, and whether
#: it is in THIS one is a question for the evidence, not for this stage.
GENERAL_GOVERNMENT_TERMS: frozenset[str] = frozenset(
    {
        "state governments",
        "county governments",
        "city or township governments",
        "special district governments",
        "units of local government",
        "public and state controlled institutions of higher education",
        "nonprofits",
        "public housing authorities",
    }
)

#: A `NOT_CANDIDATE` verdict needs at least this much eligibility evidence
#: behind it. Below the bar the answer is UNKNOWN - the absence of a signal in
#: an empty record says nothing about the world.
MINIMUM_EVIDENCE_FOR_A_NEGATIVE = 1


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _norm(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    return [str(v).strip().lower() for v in values if str(v or "").strip()]


def detect_candidate(
    *,
    canonical_id: Any = None,
    eligible_applicant_codes: Any = None,
    sam_applicant_type_codes: Any = None,
    eligible_applicant_terms: Any = None,
    additional_eligibility_text: Any = None,
    native_terms_in_operative_text: Any = None,
    native_terms_in_narrative_only: Any = None,
    geography_terms: Any = None,
    beneficiary_terms: Any = None,
    sector_keys: Any = None,
    native_relevant_sectors: Any = None,
    statutory_authorities: Any = None,
    prior_native_award_count: Any = None,
    program_history_native_awards: Any = None,
    source_is_native_serving: bool = False,
    document_signal_count: Any = None,
    explicit_native_exclusion: bool = False,
    evidence_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One opportunity, one candidate verdict, with every signal that fired.

    Every input is a STRUCTURED fact somebody else extracted. Nothing here
    parses free text looking for words, because a stage that does that is the
    keyword matcher this gate exists to replace.
    """
    fired: list[dict[str, Any]] = []

    def fire(signal: str, why: str) -> None:
        fired.append(
            {
                "signal": signal,
                "evidence_type": SIGNAL_EVIDENCE_TYPE[signal],
                "why": why,
            }
        )

    # ---- applicant eligibility, read by the layer that owns codes ----
    codes = classify_native_eligibility(
        eligible_applicant_codes=eligible_applicant_codes,
        sam_applicant_type_codes=sam_applicant_type_codes,
        additional_eligibility_text=additional_eligibility_text,
        opportunity_key=canonical_id,
    )
    confidence_band = str(codes.get("confidence") or "unknown")
    if confidence_band == "direct":
        fire(
            NATIVE_APPLICANT_CODE,
            f"applicant codes name Native entities directly: {confidence_band}",
        )
    elif confidence_band == "requires_reading":
        # Unrestricted, or "see the additional eligibility text". This is the
        # case that a keyword filter throws away and that is open to every
        # Tribe in the country.
        fire(
            UNRESTRICTED_ELIGIBILITY,
            "eligibility is unrestricted or deferred to text, so Tribes are "
            "not excluded by the codes",
        )

    terms = set(_norm(eligible_applicant_terms))
    general = sorted(terms & GENERAL_GOVERNMENT_TERMS)
    if general:
        fire(
            GENERAL_GOVERNMENT_ELIGIBILITY,
            f"general government or nonprofit eligibility: {general}",
        )
    if len(terms) >= 4 and not general:
        fire(
            BROAD_ENTITY_ELIGIBILITY,
            f"{len(terms)} distinct applicant classes named",
        )

    # ---- operative vs narrative terminology --------------------------
    operative = _norm(native_terms_in_operative_text)
    narrative = _norm(native_terms_in_narrative_only)
    if operative:
        fire(NATIVE_TERMINOLOGY, f"native terms in operative text: {operative}")
    # Narrative-only terminology is recorded and does NOT fire. This is the
    # background-paragraph hard negative: a program history that mentions a
    # Tribal grantee does not make the current cycle Native-relevant.

    # ---- the non-keyword signals -------------------------------------
    if _norm(geography_terms):
        fire(NATIVE_GEOGRAPHY, f"native geography: {_norm(geography_terms)}")
    if _norm(beneficiary_terms):
        fire(NATIVE_BENEFICIARY, f"native beneficiaries: {_norm(beneficiary_terms)}")
    if int(prior_native_award_count or 0) > 0:
        fire(
            PRIOR_AWARD_SIGNAL,
            f"{int(prior_native_award_count)} prior award(s) to Native entities",
        )
    if int(program_history_native_awards or 0) > 0:
        fire(
            PROGRAM_HISTORY_SIGNAL,
            f"{int(program_history_native_awards)} Native award(s) in prior cycles",
        )
    if _norm(statutory_authorities):
        fire(
            PROGRAM_AUTHORITY,
            f"authority names Native entities: {_norm(statutory_authorities)}",
        )
    if source_is_native_serving:
        fire(NATIVE_SERVING_SOURCE, "the publisher is a Native-serving source")
    if int(document_signal_count or 0) > 0:
        fire(
            DOCUMENT_EVIDENCE,
            f"{int(document_signal_count)} signal(s) found in attached documents",
        )

    sectors = set(_norm(sector_keys))
    relevant = set(_norm(native_relevant_sectors))
    overlap = sorted(sectors & relevant) if relevant else []
    if overlap:
        fire(SECTOR_COMPATIBILITY, f"sector overlap: {overlap}")

    # ---- the verdict --------------------------------------------------
    evidence_count = len(evidence_items or [])
    # Only evidence strong enough to be believed can support a negative. An
    # INFERRED reading is a hypothesis, and a hypothesis that drops an
    # opportunity at the high-recall stage is unrecoverable - nothing
    # downstream ever sees the row again.
    eligibility_evidence = [
        item
        for item in (evidence_items or [])
        if str(item.get("evidence_type")) in APPLICANT_BEARING
        and str(item.get("confidence_class")) in DEFINITE_ENOUGH
    ]
    inferred_eligibility_evidence = [
        item
        for item in (evidence_items or [])
        if str(item.get("evidence_type")) in APPLICANT_BEARING
        and str(item.get("confidence_class")) not in DEFINITE_ENOUGH
    ]

    # What entitles us to say NO. Either typed evidence about who may apply,
    # or the source's own applicant codes coming back `negative` - codes were
    # present and named no Native class. Both are the source stating its
    # eligibility; neither is an absence.
    negative_bases: list[str] = []
    if len(eligibility_evidence) >= MINIMUM_EVIDENCE_FOR_A_NEGATIVE:
        negative_bases.append("applicant_bearing_evidence")
    if confidence_band == "negative":
        negative_bases.append("applicant_codes_named_no_native_class")

    if fired:
        state = CANDIDATE
        reason = f"{len(fired)}_signals_fired"
    elif explicit_native_exclusion:
        state = NOT_CANDIDATE
        reason = "source_explicitly_excludes_native_entities"
    elif negative_bases:
        # We read who may apply, Tribes were not among them, and nothing else
        # pointed here. That is a finding.
        state = NOT_CANDIDATE
        reason = "eligibility_stated_and_no_signal_fired"
    else:
        # Nothing fired and we never saw who may apply. That is not a finding.
        state = UNKNOWN
        reason = "no_signal_and_no_stated_eligibility_to_support_a_negative"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_id": str(canonical_id) if canonical_id else None,
            "candidate_state": state,
            "reason": reason,
            "signals": fired,
            "signal_names": sorted({str(item["signal"]) for item in fired}),
            "signal_count": len(fired),
            "narrative_only_terms": narrative,
            "applicant_code_confidence": confidence_band,
            "applicant_code_classes": codes.get("eligibility_classes"),
            "evidence_count": evidence_count,
            "eligibility_evidence_count": len(eligibility_evidence),
            "inferred_eligibility_evidence_count": len(inferred_eligibility_evidence),
            "negative_bases": negative_bases,
            "explicit_native_exclusion": bool(explicit_native_exclusion),
        }
    )


def candidate_invariant_failures(candidate: dict[str, Any]) -> list[str]:
    """Refuse a candidate verdict that the recall rule would not produce."""
    failures: list[str] = []

    state = str(candidate.get("candidate_state") or "")
    if state not in CANDIDATE_STATES:
        failures.append(f"candidate_state_outside_the_vocabulary:{state or 'missing'}")

    signals = candidate.get("signals") or []
    for item in signals:
        name = str(item.get("signal"))
        if name not in CANDIDATE_SIGNALS:
            failures.append(f"signal_outside_the_vocabulary:{name}")
        if SIGNAL_EVIDENCE_TYPE.get(name) != str(item.get("evidence_type")):
            failures.append(f"signal_cites_the_wrong_evidence_type:{name}")

    # Recall is the entire point of this stage, so its rule is enforced here
    # rather than trusted: anything that fired a signal IS a candidate.
    if signals and state != CANDIDATE:
        failures.append(f"signals_fired_but_state_is_{state}")

    # And a negative has to be earned.
    if state == NOT_CANDIDATE:
        if signals:
            failures.append("not_candidate_despite_signals")
        if not candidate.get("explicit_native_exclusion") and not (
            candidate.get("negative_bases") or []
        ):
            failures.append("not_candidate_without_evidence_to_support_it")

    return sorted(set(failures))


def describe_candidate_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_states": list(CANDIDATE_STATES),
            "candidate_signals": list(CANDIDATE_SIGNALS),
            "every_signal_has_an_evidence_type": set(SIGNAL_EVIDENCE_TYPE)
            == set(CANDIDATE_SIGNALS),
            "any_signal_makes_a_candidate": True,
            "unknown_is_not_not_candidate": UNKNOWN != NOT_CANDIDATE,
            "negative_requires_evidence": MINIMUM_EVIDENCE_FOR_A_NEGATIVE >= 1,
            "inference_cannot_support_a_negative": "INFERRED" not in DEFINITE_ENOUGH,
            "narrative_only_terms_do_not_fire": True,
            "keyword_free_signals": sorted(
                set(CANDIDATE_SIGNALS) - {NATIVE_TERMINOLOGY}
            ),
            "keyword_free_signal_count": len(CANDIDATE_SIGNALS) - 1,
        }
    )
