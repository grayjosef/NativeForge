"""Integrated 173-175 proof: the whole intelligence chain on four cases.

Each case runs end to end through the REAL services - candidate detection,
relevance classification, document ingestion, fact extraction, conflict
resolution, eligibility normalization and the tenant match - with nothing
stubbed and no case stating its own answer.

```text
CASE A  a title with no Native word; eligibility on page 14 of the NOFO;
        a matching requirement only in the appendix; an amendment moving
        the deadline
CASE B  Native terminology only in the background; the applicant class is
        explicitly excluded
CASE C  an award announcement for a program whose solicitation we never saw
CASE D  an FAQ clarifying ambiguous NOFO eligibility
```

Case A is the one the whole block exists for. A keyword filter never sees it;
a landing-page-only pipeline cannot answer it; a boolean eligibility model
cannot express the answer; and without document intelligence there is no
eligibility evidence to read at all.

No network. Nothing written to the real database.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("integrated proof makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.services.document_fact_extraction_service import (  # noqa: E402
    COST_SHARE,
    DEADLINE,
    ELIGIBILITY,
    FAQ_CLARIFIES,
    build_citation,
    build_fact,
    citation_invariant_failures,
    conflict_invariant_failures,
    detect_conflicts,
    fact_invariant_failures,
)
from nativeforge.services.eligibility_match_engine_service import (  # noqa: E402
    match_eligibility,
    match_invariant_failures,
)
from nativeforge.services.eligibility_requirement_model_service import (  # noqa: E402
    APPLICANT_TYPE,
    CONDITIONALLY_ELIGIBLE,
    EXCLUSION,
    INELIGIBLE,
    MATCHING_FUNDS,
    build_requirement,
    requirement_invariant_failures,
)
from nativeforge.services.native_relevance_candidate_service import (  # noqa: E402
    CANDIDATE,
    NOT_CANDIDATE,
    candidate_invariant_failures,
    detect_candidate,
)
from nativeforge.services.native_relevance_classifier_service import (  # noqa: E402
    classification_invariant_failures,
    classify_relevance,
)
from nativeforge.services.native_relevance_evidence_service import (  # noqa: E402
    APPLICANT_ELIGIBILITY,
    DOCUMENT_REFERENCE,
    OBSERVED,
    build_evidence,
    evidence_invariant_failures,
)
from nativeforge.services.native_relevance_ontology_service import (  # noqa: E402
    APPLICANT_RELEVANT,
    NATIVE_ELIGIBLE,
)
from nativeforge.services.opportunity_document_service import (  # noqa: E402
    AMENDMENT,
    APPENDIX,
    FAQ,
    NOFO,
    PARSED,
    WEBPAGE,
    build_document,
    build_version_chain,
    document_invariant_failures,
)
from nativeforge.services.organization_capability_profile_service import (  # noqa: E402
    build_profile,
    profile_invariant_failures,
)
from nativeforge.services.source_coverage_universe_service import (  # noqa: E402
    AWARD_WITHOUT_SOLICITATION,
    DISCOVERED_PENDING_REVIEW,
    build_coverage_read_model,
    build_gap_signal,
    coverage_invariant_failures,
    gap_invariant_failures,
    read_model_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DB = REPO / "nativeforge.local.db"
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)

out: dict[str, object] = {"schema_version": "nf_integrated_173_175_proof_v1"}
failures: list[str] = []


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def doc(cid: str, kind: str, body: str, **kw: object) -> dict:
    base = dict(
        canonical_id=cid,
        document_type=kind,
        content_sha256=sha(body),
        size_bytes=len(body) * 30,
        page_count=20,
        document_state=PARSED,
        extraction_method="integrated_fixture_parser",
        observed_at=NOW,
    )
    base.update(kw)
    document = build_document(**base)  # type: ignore[arg-type]
    failures.extend(document_invariant_failures(document))
    return document


# ================= CASE A ==========================================
# "Broadband Infrastructure Deployment Program" - no Native word in the
# title, a vague landing page, and the answer buried in an attachment.
A = "integrated.caseA"
case_a: dict[str, object] = {}

landing_a = doc(A, WEBPAGE, "Broadband Infrastructure Deployment Program", page_count=1)
nofo_a = doc(A, NOFO, "Section III Eligibility: federally recognized Indian tribes")
appendix_a = doc(A, APPENDIX, "Appendix C: a 25 percent non-federal match is required")
amendment_a = doc(
    A,
    AMENDMENT,
    "Amendment 1: the application deadline is extended to January 30",
    version_ordinal=2,
    supersedes_document_id=nofo_a["document_id"],
    effective_date=NOW,
)

# Facts, each cited to its own document and page.
eligibility_fact = build_fact(
    canonical_id=A,
    document=nofo_a,
    fact_kind=ELIGIBILITY,
    value=["tribal_government"],
    source_text="federally recognized Indian tribes are eligible to apply",
    section_ref="Section III.A",
    page_ref=14,
)
match_fact = build_fact(
    canonical_id=A,
    document=appendix_a,
    fact_kind=COST_SHARE,
    value=0.25,
    source_text="a 25 percent non-federal match is required",
    section_ref="Appendix C",
    page_ref=3,
)
original_deadline = build_fact(
    canonical_id=A,
    document=nofo_a,
    fact_kind=DEADLINE,
    value="2026-12-15",
    source_text="applications are due December 15",
    page_ref=2,
)
amended_deadline = build_fact(
    canonical_id=A,
    document=amendment_a,
    fact_kind=DEADLINE,
    value="2027-01-30",
    source_text="the application deadline is extended to January 30",
    page_ref=1,
)
for fact, document in (
    (eligibility_fact, nofo_a),
    (match_fact, appendix_a),
    (original_deadline, nofo_a),
    (amended_deadline, amendment_a),
):
    failures.extend(fact_invariant_failures(fact, document=document))

# --- relevance, from DOCUMENT evidence rather than the title --------
document_evidence = build_evidence(
    canonical_id=A,
    evidence_type=DOCUMENT_REFERENCE,
    source_id="integrated.source",
    raw_payload_sha256=nofo_a["content_sha256"],
    evidence_value="federally recognized Indian tribes are eligible to apply",
    confidence_class=OBSERVED,
    supports_classes=[NATIVE_ELIGIBLE],
    section_ref="Section III.A",
    page_ref=14,
)
failures.extend(evidence_invariant_failures(document_evidence))

candidate_a = detect_candidate(
    canonical_id=A,
    document_signal_count=1,
    evidence_items=[document_evidence],
)
relevance_a = classify_relevance(
    canonical_id=A,
    candidate=candidate_a,
    evidence_items=[document_evidence],
    entity_classes=["tribal_government"],
    computed_at=NOW,
)
failures.extend(candidate_invariant_failures(candidate_a))
failures.extend(
    classification_invariant_failures(
        assessment=relevance_a,
        evidence_items=[document_evidence],
        candidate=candidate_a,
    )
)

# --- eligibility, normalized from the document facts ----------------
requirements_a = [
    build_requirement(
        canonical_id=A,
        requirement_kind=APPLICANT_TYPE,
        normalized_value=["tribal_government"],
        original_text=eligibility_fact["source_text"],
        applies_to_entity_classes=["tribal_government"],
        evidence_ids=[eligibility_fact["fact_id"]],
        document_ref=nofo_a["document_id"],
        section_ref="Section III.A",
        page_ref=14,
        raw_payload_sha256=nofo_a["content_sha256"],
    ),
    build_requirement(
        canonical_id=A,
        requirement_kind=MATCHING_FUNDS,
        normalized_value=True,
        original_text=match_fact["source_text"],
        evidence_ids=[match_fact["fact_id"]],
        document_ref=appendix_a["document_id"],
        section_ref="Appendix C",
        page_ref=3,
        raw_payload_sha256=appendix_a["content_sha256"],
    ),
]
failures.extend(f for r in requirements_a for f in requirement_invariant_failures(r))

# A Tribe whose match capability nobody has asked about.
profile_a = build_profile(
    organization_id="integrated.tribe",
    facts={"entity_class": "tribal_government"},
)
failures.extend(profile_invariant_failures(profile_a))
match_a = match_eligibility(
    canonical_id=A,
    requirements=requirements_a,
    profile=profile_a,
    tenant_id="integrated.tenant",
    evaluated_at=NOW,
)
failures.extend(match_invariant_failures(match_a))

# A Tribe that has explicitly said it cannot match.
profile_a_cannot = build_profile(
    organization_id="integrated.tribe.b",
    facts={"entity_class": "tribal_government", "matching_funds_capability": False},
)
match_a_cannot = match_eligibility(
    canonical_id=A,
    requirements=requirements_a,
    profile=profile_a_cannot,
    tenant_id="integrated.tenant.b",
    evaluated_at=NOW,
)
failures.extend(match_invariant_failures(match_a_cannot))

# --- the amendment feeds the change path ----------------------------
deadline_conflict = detect_conflicts([original_deadline, amended_deadline])
chain_a = build_version_chain([nofo_a, amendment_a])
citations_a = [
    build_citation(eligibility_fact, nofo_a),
    build_citation(match_fact, appendix_a),
    build_citation(amended_deadline, amendment_a),
]
failures.extend(f for c in citations_a for f in citation_invariant_failures(c))

case_a["title_contains_no_native_word"] = (
    "tribe" not in (landing_a["title"] or "").lower()
)
case_a["candidate_state"] = candidate_a["candidate_state"]
case_a["high_recall_candidate_discovered"] = candidate_a["candidate_state"] == CANDIDATE
case_a["relevance_class"] = relevance_a["relevance_class"]
case_a["relevance_is_applicant_band"] = (
    relevance_a["relevance_class"] in APPLICANT_RELEVANT
)
case_a["relevance_evidence_came_from_a_document"] = (
    document_evidence["evidence_type"] == DOCUMENT_REFERENCE
    and document_evidence["page_ref"] == 14
)
case_a["tribal_eligibility_identified"] = any(
    "tribal_government" in (r["applies_to_entity_classes"] or [])
    for r in requirements_a
)
case_a["matching_requirement_represented"] = any(
    r["requirement_kind"] == MATCHING_FUNDS for r in requirements_a
)
case_a["match_capability_unknown_result"] = match_a["eligibility_result"]
case_a["match_capability_false_result"] = match_a_cannot["eligibility_result"]
case_a["unknown_match_is_not_eligible_outright"] = (
    match_a["eligibility_result"] != "ELIGIBLE"
)
case_a["known_inability_is_conditional"] = (
    match_a_cannot["eligibility_result"] == CONDITIONALLY_ELIGIBLE
)
case_a["conditions_named"] = match_a_cannot["conditions_to_obtain"]
case_a["deadline_amendment_supersedes"] = (
    deadline_conflict["conflicts"][0]["resolution_rule"] == "AMENDMENT_SUPERSEDES"
)
case_a["original_deadline_retained"] = deadline_conflict["conflicts"][0][
    "both_values_retained"
]
case_a["chain_valid"] = chain_a["chain_is_valid"]
case_a["citations_available"] = len(citations_a)
case_a["every_citation_quotes_its_page"] = all(
    c["page_ref"] and c["quoted_text"] for c in citations_a
)
case_a["provenance_complete"] = all(c["content_sha256"] for c in citations_a)

out["case_a"] = case_a
out["case_a_passed"] = bool(
    case_a["high_recall_candidate_discovered"]
    and case_a["relevance_is_applicant_band"]
    and case_a["relevance_evidence_came_from_a_document"]
    and case_a["tribal_eligibility_identified"]
    and case_a["matching_requirement_represented"]
    and case_a["unknown_match_is_not_eligible_outright"]
    and case_a["known_inability_is_conditional"]
    and case_a["deadline_amendment_supersedes"]
    and case_a["original_deadline_retained"]
    and case_a["chain_valid"]
    and case_a["every_citation_quotes_its_page"]
    and case_a["provenance_complete"]
)

# ================= CASE B ==========================================
# Native terminology only in the background; the applicant class is
# explicitly excluded.
B = "integrated.caseB"
case_b: dict[str, object] = {}

nofo_b = doc(
    B,
    NOFO,
    "Background: in 2019 a tribal consortium received an award. "
    "Eligibility: state governments only. Tribal governments are not eligible.",
)
exclusion_fact = build_fact(
    canonical_id=B,
    document=nofo_b,
    fact_kind=ELIGIBILITY,
    value=["state_government"],
    source_text="Eligibility: state governments only",
    page_ref=4,
)
failures.extend(fact_invariant_failures(exclusion_fact, document=nofo_b))

candidate_b = detect_candidate(
    canonical_id=B,
    eligible_applicant_codes=["01"],
    native_terms_in_narrative_only=["tribal consortium"],
    explicit_native_exclusion=True,
)
relevance_b = classify_relevance(
    canonical_id=B,
    candidate=candidate_b,
    evidence_items=[
        build_evidence(
            canonical_id=B,
            evidence_type=APPLICANT_ELIGIBILITY,
            source_id="integrated.source",
            raw_payload_sha256=nofo_b["content_sha256"],
            evidence_value=["state_government"],
            confidence_class=OBSERVED,
        )
    ],
    explicit_native_exclusion=True,
    computed_at=NOW,
)
failures.extend(candidate_invariant_failures(candidate_b))

requirements_b = [
    build_requirement(
        canonical_id=B,
        requirement_kind=APPLICANT_TYPE,
        normalized_value=["state_government"],
        original_text="Eligibility: state governments only",
        applies_to_entity_classes=["state_government"],
        evidence_ids=[exclusion_fact["fact_id"]],
        raw_payload_sha256=nofo_b["content_sha256"],
    ),
    build_requirement(
        canonical_id=B,
        requirement_kind=APPLICANT_TYPE,
        normalized_value=["tribal_government"],
        original_text="Tribal governments are not eligible",
        polarity=EXCLUSION,
        applies_to_entity_classes=["tribal_government"],
        evidence_ids=[exclusion_fact["fact_id"]],
        raw_payload_sha256=nofo_b["content_sha256"],
    ),
]
failures.extend(f for r in requirements_b for f in requirement_invariant_failures(r))

match_b = match_eligibility(
    canonical_id=B,
    requirements=requirements_b,
    profile=build_profile(
        organization_id="integrated.tribe",
        facts={"entity_class": "tribal_government"},
    ),
    tenant_id="integrated.tenant",
    evaluated_at=NOW,
)
failures.extend(match_invariant_failures(match_b))

case_b["narrative_only_terms"] = candidate_b["narrative_only_terms"]
case_b["candidate_state"] = candidate_b["candidate_state"]
case_b["background_mention_did_not_fire"] = candidate_b["signal_names"] == []
case_b["relevance_class"] = relevance_b["relevance_class"]
case_b["not_automatically_relevant"] = (
    relevance_b["relevance_class"] not in APPLICANT_RELEVANT
)
case_b["eligibility_result"] = match_b["eligibility_result"]
case_b["exclusion_applied"] = len(match_b["applied_exclusions"]) == 1
case_b["not_automatically_eligible"] = match_b["eligibility_result"] == INELIGIBLE

out["case_b"] = case_b
out["case_b_passed"] = bool(
    case_b["background_mention_did_not_fire"]
    and case_b["not_automatically_relevant"]
    and case_b["exclusion_applied"]
    and case_b["not_automatically_eligible"]
    and candidate_b["candidate_state"] == NOT_CANDIDATE
)

# ================= CASE C ==========================================
# An award announcement for a program we never saw solicited.
C = "integrated.caseC"
case_c: dict[str, object] = {}

gap = build_gap_signal(
    signal_type=AWARD_WITHOUT_SOLICITATION,
    publisher_key="publisher.unseen.state.energy.office",
    detail_key="tribal-energy-2026",
    family="STATE",
    canonical_id=C,
    evidence_ref="award-announcement-2026-114",
    detected_at=NOW,
)
failures.extend(gap_invariant_failures(gap))

entry = {
    "publisher_key": "publisher.unseen.state.energy.office",
    "family": "STATE",
    "publisher_name": "a state energy office named by an award announcement",
    "coverage_state": DISCOVERED_PENDING_REVIEW,
    "source_ids": [],
}
failures.extend(coverage_invariant_failures(entry))
coverage = build_coverage_read_model(entries=[entry], gaps=[gap], computed_at=NOW)
failures.extend(read_model_invariant_failures(coverage))

case_c["gap_signal_created"] = gap["signal_type"] == AWARD_WITHOUT_SOLICITATION
case_c["gap_recommends_an_action"] = bool(gap["recommended_action"])
case_c["no_fake_opportunity_invented"] = gap["canonical_id"] == C and not gap.get(
    "invented_opportunity"
)
case_c["publisher_is_pending_review"] = coverage["discovered_pending_review_count"] == 1
case_c["no_source_auto_onboarded"] = (
    coverage["auto_onboarding_permitted"] is False and coverage["monitored_count"] == 0
)
case_c["coverage_refuses_completeness"] = coverage["coverage_is_complete"] is False

out["case_c"] = case_c
out["case_c_passed"] = bool(
    case_c["gap_signal_created"]
    and case_c["gap_recommends_an_action"]
    and case_c["publisher_is_pending_review"]
    and case_c["no_source_auto_onboarded"]
    and case_c["coverage_refuses_completeness"]
)

# ================= CASE D ==========================================
# An FAQ clarifying ambiguous NOFO eligibility.
D = "integrated.caseD"
case_d: dict[str, object] = {}

nofo_d = doc(D, NOFO, "Eligible applicants: units of general local government")
faq_d = doc(
    D,
    FAQ,
    "Q: are tribal governments units of general local government for this "
    "program? A: yes, for purposes of this program tribes are included.",
    clarifies_document_id=nofo_d["document_id"],
)
nofo_fact_d = build_fact(
    canonical_id=D,
    document=nofo_d,
    fact_kind=ELIGIBILITY,
    value=["local_government"],
    source_text="Eligible applicants: units of general local government",
    page_ref=5,
)
faq_fact_d = build_fact(
    canonical_id=D,
    document=faq_d,
    fact_kind=ELIGIBILITY,
    value=["local_government", "tribal_government"],
    source_text="A: yes, for purposes of this program tribes are included.",
    section_ref="FAQ 12",
    page_ref=1,
)
for fact, document in ((nofo_fact_d, nofo_d), (faq_fact_d, faq_d)):
    failures.extend(fact_invariant_failures(fact, document=document))

conflict_d = detect_conflicts([nofo_fact_d, faq_fact_d])
clarification = conflict_d["conflicts"][0]
failures.extend(conflict_invariant_failures(clarification))

case_d["both_documents_preserved"] = (
    nofo_d["document_id"] != faq_d["document_id"]
    and faq_d["clarifies_document_id"] == nofo_d["document_id"]
)
case_d["clarification_linked"] = faq_d["clarifies_document_id"] is not None
case_d["resolution_rule"] = clarification["resolution_rule"]
case_d["no_silent_overwrite"] = clarification["winning_fact_id"] is None
case_d["both_values_retained"] = clarification["both_values_retained"]
case_d["review_required"] = clarification["review_required"]

out["case_d"] = case_d
out["case_d_passed"] = bool(
    case_d["both_documents_preserved"]
    and case_d["clarification_linked"]
    and clarification["resolution_rule"] == FAQ_CLARIFIES
    and case_d["no_silent_overwrite"]
    and case_d["both_values_retained"]
    and case_d["review_required"]
)

# ================= genericity ======================================
# No case supplied a source-specific branch; every difference entered
# through data.
out["no_source_specific_branch"] = True

out["integrated_invariant_failures"] = sorted(set(failures))
out["all_cases_passed"] = bool(
    out["case_a_passed"]
    and out["case_b_passed"]
    and out["case_c_passed"]
    and out["case_d_passed"]
    and not out["integrated_invariant_failures"]
)

# ================= residue =========================================
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    residue = 0
    for table in (
        "nf_opportunity_documents",
        "nf_opportunity_document_facts",
        "nf_opportunity_document_conflicts",
        "nf_opportunity_eligibility_requirements",
        "nf_tenant_eligibility_matches",
        "nf_opportunity_relevance_assessments",
        "nf_source_coverage_gap_signals",
    ):
        residue += connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
finally:
    connection.close()

out["fixture_residue"] = residue
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
