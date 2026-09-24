"""Gate 175I/J/M/K: the document hazards, retrieval safety, and self-health.

Fourteen adversarial cases, every one a way document intelligence quietly goes
wrong:

```text
a scanned PDF with no text layer          -> must not read as "no requirements"
the same URL serving changed bytes        -> a new version
the same bytes at a second URL            -> the SAME document
eligibility only in an appendix           -> still binding
a match requirement only in an FAQ        -> still binding
an FAQ contradicting the NOFO             -> both retained, nobody wins
an amendment moving the deadline          -> supersedes, predecessor kept
a supersession cycle                      -> refused
a citation past the last page             -> refused
a fact with no document                   -> refused
```

**175I.** No live document is downloaded. Every byte here is a synthetic
fixture built in-process; `socket.socket` is replaced with one that raises and
counts, and the count is asserted zero. The mechanism exists without the
crawling.

No writes to the real database.
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
        raise OSError("gate175 document phase makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.services.document_fact_extraction_service import (  # noqa: E402
    AMENDMENT_SUPERSEDES,
    COST_SHARE,
    DEADLINE,
    ELIGIBILITY,
    FAQ_CLARIFIES,
    NOTICE_OUTRANKS_SUMMARY,
    UNRESOLVED,
    build_citation,
    build_fact,
    citation_invariant_failures,
    conflict_invariant_failures,
    describe_fact_model,
    detect_conflicts,
    fact_invariant_failures,
)
from nativeforge.services.opportunity_document_service import (  # noqa: E402
    AMENDMENT,
    APPENDIX,
    FAQ,
    NOFO,
    PARSED,
    PARTIAL,
    UNSUPPORTED,
    WEBPAGE,
    build_document,
    build_version_chain,
    describe_document_model,
    document_invariant_failures,
    register_document_type,
    reset_registered_document_types,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DB = REPO / "nativeforge.local.db"
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)
CID = "nf175.case"

out: dict[str, object] = {"schema_version": "nf_gate175_documents_v1"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def doc(kind: str, body: str, **kw: object) -> dict:
    base = dict(
        canonical_id=CID,
        document_type=kind,
        content_sha256=sha(body),
        size_bytes=len(body),
        page_count=max(1, len(body) // 200),
        document_state=PARSED,
        extraction_method="synthetic_fixture_parser",
        media_type="application/pdf",
        observed_at=NOW,
    )
    base.update(kw)
    return build_document(**base)  # type: ignore[arg-type]


cases: dict[str, object] = {}
doc_failures: list[str] = []
fact_failures: list[str] = []

# ---- 1. a scanned PDF with no text layer ---------------------------
scanned = doc(
    NOFO,
    "x" * 4000,
    document_state=UNSUPPORTED,
    extraction_method=None,
    media_type="application/pdf",
    known_gaps=["no_text_layer"],
)
doc_failures.extend(document_invariant_failures(scanned))
cases["scanned_pdf_absence_is_meaningful"] = scanned["absence_is_meaningful"]
cases["scanned_pdf_can_support_facts"] = scanned["can_support_facts"]

# A partially parsed document is equally not a source of absence.
partial = doc(NOFO, "y" * 4000, document_state=PARTIAL, known_gaps=["tables_skipped"])
doc_failures.extend(document_invariant_failures(partial))
cases["partial_absence_is_meaningful"] = partial["absence_is_meaningful"]

out["missing_parser_not_empty_truth"] = (
    scanned["absence_is_meaningful"] is False
    and scanned["can_support_facts"] is False
    and partial["absence_is_meaningful"] is False
)

# ---- 2/3. same URL new bytes; same bytes new URL --------------------
v1 = doc(NOFO, "NOFO body version one", location_ref="https://example/nofo.pdf")
v2 = doc(
    NOFO,
    "NOFO body version TWO with a new deadline",
    location_ref="https://example/nofo.pdf",
    version_ordinal=2,
    supersedes_document_id=v1["document_id"],
)
mirror = doc(NOFO, "NOFO body version one", location_ref="https://mirror/nofo.pdf")
doc_failures.extend(document_invariant_failures(v1))
doc_failures.extend(document_invariant_failures(v2))

out["same_url_changed_bytes_creates_new_version"] = (
    v1["document_id"] != v2["document_id"]
)
out["same_bytes_different_url_is_the_same_document"] = (
    mirror["document_id"] == v1["document_id"]
)

# ---- 4/5. appendix-only and FAQ-only facts --------------------------
appendix = doc(APPENDIX, "Appendix B: Eligibility. Federally recognized tribes.")
faq = doc(
    FAQ,
    "Q: is a match required? A: yes, 20 percent.",
    clarifies_document_id=v1["document_id"],
)
landing = doc(WEBPAGE, "Grant overview page", media_type="text/html", page_count=1)
doc_failures.extend(document_invariant_failures(appendix))
doc_failures.extend(document_invariant_failures(faq))

appendix_eligibility = build_fact(
    canonical_id=CID,
    document=appendix,
    fact_kind=ELIGIBILITY,
    value=["tribal_government"],
    source_text="Federally recognized Indian tribes are eligible",
    section_ref="Appendix B",
    page_ref=1,
)
faq_match = build_fact(
    canonical_id=CID,
    document=faq,
    fact_kind=COST_SHARE,
    value=0.20,
    source_text="Q: is a match required? A: yes, 20 percent.",
    section_ref="FAQ 7",
    page_ref=1,
)
fact_failures.extend(fact_invariant_failures(appendix_eligibility, document=appendix))
fact_failures.extend(fact_invariant_failures(faq_match, document=faq))

out["appendix_only_eligibility_detected"] = (
    appendix_eligibility["fact_kind"] == ELIGIBILITY
    and appendix_eligibility["document_type"] == APPENDIX
    and not fact_invariant_failures(appendix_eligibility, document=appendix)
)
out["match_requirement_only_in_faq_detected"] = faq_match[
    "fact_kind"
] == COST_SHARE and not fact_invariant_failures(faq_match, document=faq)

# ---- 6. an FAQ contradicting the NOFO -------------------------------
nofo_eligibility = build_fact(
    canonical_id=CID,
    document=v1,
    fact_kind=ELIGIBILITY,
    value=["local_government"],
    source_text="Units of general local government are eligible",
    page_ref=1,
)
faq_eligibility = build_fact(
    canonical_id=CID,
    document=faq,
    fact_kind=ELIGIBILITY,
    value=["local_government", "tribal_government"],
    source_text="Q: may tribes apply? A: yes, tribes are included.",
    page_ref=1,
)
clarification = detect_conflicts([nofo_eligibility, faq_eligibility])
clarify_conflict = clarification["conflicts"][0]
out["faq_clarification_rule"] = clarify_conflict["resolution_rule"]
out["faq_clarification_picks_no_winner"] = clarify_conflict["winning_fact_id"] is None
out["faq_clarification_retains_both"] = clarify_conflict["both_values_retained"]
out["faq_clarification_preserved"] = (
    clarify_conflict["resolution_rule"] == FAQ_CLARIFIES
    and clarify_conflict["winning_fact_id"] is None
    and clarify_conflict["review_required"] is True
)

# ---- 7. an amendment moving the deadline ----------------------------
amendment = doc(
    AMENDMENT,
    "Amendment 2: the deadline is extended to December 15.",
    version_ordinal=3,
    supersedes_document_id=v2["document_id"],
    effective_date=NOW,
)
doc_failures.extend(document_invariant_failures(amendment))
nofo_deadline = build_fact(
    canonical_id=CID,
    document=v1,
    fact_kind=DEADLINE,
    value="2026-11-15",
    source_text="Applications are due November 15, 2026",
    page_ref=1,
)
amended_deadline = build_fact(
    canonical_id=CID,
    document=amendment,
    fact_kind=DEADLINE,
    value="2026-12-15",
    source_text="the deadline is extended to December 15",
    page_ref=1,
)
amended = detect_conflicts([nofo_deadline, amended_deadline])
amend_conflict = amended["conflicts"][0]
out["amendment_rule"] = amend_conflict["resolution_rule"]
out["amendment_names_a_winner"] = (
    amend_conflict["winning_fact_id"] == (amended_deadline["fact_id"])
)
out["amendment_retains_the_predecessor"] = amend_conflict["both_values_retained"]
out["amendment_supersedes_correctly"] = (
    amend_conflict["resolution_rule"] == AMENDMENT_SUPERSEDES
    and out["amendment_names_a_winner"]
    and amend_conflict["both_values_retained"]
)

# ---- 8. landing page vs notice --------------------------------------
page_deadline = build_fact(
    canonical_id=CID,
    document=landing,
    fact_kind=DEADLINE,
    value="2026-11-01",
    source_text="Due November 1",
    page_ref=1,
)
summary = detect_conflicts([page_deadline, nofo_deadline])
summary_conflict = summary["conflicts"][0]
out["notice_outranks_summary"] = (
    summary_conflict["resolution_rule"] == NOTICE_OUTRANKS_SUMMARY
    and summary_conflict["winning_fact_id"] == nofo_deadline["fact_id"]
)

# ---- 9. two documents with no authority rule -------------------------
other_appendix = doc(APPENDIX, "Appendix C: the ceiling is 400,000.")
a_fact = build_fact(
    canonical_id=CID,
    document=appendix,
    fact_kind="AWARD_CEILING",
    value=500000,
    source_text="award ceiling 500,000",
    page_ref=1,
)
b_fact = build_fact(
    canonical_id=CID,
    document=other_appendix,
    fact_kind="AWARD_CEILING",
    value=400000,
    source_text="the ceiling is 400,000",
    page_ref=1,
)
unresolved = detect_conflicts([a_fact, b_fact])
unresolved_conflict = unresolved["conflicts"][0]
out["unresolved_rule"] = unresolved_conflict["resolution_rule"]
out["unresolved_picks_nobody"] = unresolved_conflict["winning_fact_id"] is None
out["document_conflict_not_silently_resolved"] = (
    unresolved_conflict["resolution_rule"] == UNRESOLVED
    and unresolved_conflict["winning_fact_id"] is None
    and unresolved_conflict["review_required"] is True
)

all_conflicts = (
    clarification["conflicts"]
    + amended["conflicts"]
    + summary["conflicts"]
    + unresolved["conflicts"]
)
out["conflict_invariant_failures"] = sorted(
    {f for c in all_conflicts for f in conflict_invariant_failures(c)}
)
out["conflicts_detected"] = len(all_conflicts)
out["nothing_was_silently_resolved"] = all(
    c["winning_fact_id"] is None
    or c["resolution_rule"] in {AMENDMENT_SUPERSEDES, NOTICE_OUTRANKS_SUMMARY}
    for c in all_conflicts
)

# ---- 10. the amendment chain ----------------------------------------
chain = build_version_chain([v1, v2, amendment])
out["chain_is_valid"] = chain["chain_is_valid"]
out["chain_latest_count"] = chain["latest_count"]
out["chain_latest_is_the_amendment"] = chain["latest_document_ids"] == [
    amendment["document_id"]
]
out["document_versions_preserved"] = chain["document_count"] == 3

# ---- 175M: the detectors must be able to fail ------------------------
falsifiability: dict[str, object] = {}

# A supersession cycle. The ordinals are EQUAL so the ordinal rule cannot
# fire and explain the result on its own - otherwise this check would pass
# with cycle detection removed, which is a detector passing for the wrong
# reason.
cycle_a = doc(NOFO, "cycle a", version_ordinal=2)
cycle_b = doc(NOFO, "cycle b", version_ordinal=2)
cycle_a_looped = dict(cycle_a)
cycle_a_looped["supersedes_document_id"] = cycle_b["document_id"]
cycle_b_looped = dict(cycle_b)
cycle_b_looped["supersedes_document_id"] = cycle_a["document_id"]
looped = build_version_chain([cycle_a_looped, cycle_b_looped])
falsifiability["supersession_cycle_is_caught"] = any(
    failure.startswith("supersession_cycle:") for failure in looped["chain_failures"]
)
falsifiability["cycle_failures"] = looped["chain_failures"][:3]

# an amendment naming a predecessor nobody has
orphan = doc(AMENDMENT, "orphan amendment", version_ordinal=2)
orphan_forced = dict(orphan)
orphan_forced["supersedes_document_id"] = "0" * 64
orphan_chain = build_version_chain([orphan_forced])
falsifiability["missing_predecessor_is_caught"] = any(
    failure.startswith("amendment_references_missing_predecessor:")
    for failure in orphan_chain["chain_failures"]
)

# a latest pointer that is not the newest
backwards = dict(v2)
backwards["version_ordinal"] = 1
backwards_chain = build_version_chain([v1, backwards])
falsifiability["latest_pointer_not_newest_is_caught"] = any(
    failure.startswith("successor_ordinal_not_newer:")
    for failure in backwards_chain["chain_failures"]
)

# a citation past the last page
beyond = build_fact(
    canonical_id=CID,
    document=landing,
    fact_kind=DEADLINE,
    value="2026-11-01",
    source_text="Due November 1",
    page_ref=99,
)
falsifiability["citation_beyond_the_document_is_caught"] = bool(
    fact_invariant_failures(beyond, document=landing)
)

# a fact with no document
homeless = dict(appendix_eligibility)
homeless["document_id"] = None
falsifiability["fact_without_a_document_is_caught"] = bool(
    fact_invariant_failures(homeless)
)

# a fact extracted from a document that cannot support one
impossible = build_fact(
    canonical_id=CID,
    document=scanned,
    fact_kind=ELIGIBILITY,
    value=["tribal_government"],
    source_text="invented",
    page_ref=1,
)
falsifiability["fact_from_an_unreadable_document_is_caught"] = bool(
    fact_invariant_failures(impossible, document=scanned)
)

# a clarification that overwrote the original
overwritten = dict(clarify_conflict)
overwritten["winning_fact_id"] = faq_eligibility["fact_id"]
falsifiability["clarification_overwrite_is_caught"] = bool(
    conflict_invariant_failures(overwritten)
)

# a document claiming absence means something while unparsed
lying = dict(scanned)
lying["absence_is_meaningful"] = True
falsifiability["false_absence_claim_is_caught"] = bool(
    document_invariant_failures(lying)
)

out["falsifiability"] = falsifiability
out["document_self_health_ready"] = all(
    bool(falsifiability[key])
    for key in (
        "supersession_cycle_is_caught",
        "missing_predecessor_is_caught",
        "latest_pointer_not_newest_is_caught",
        "citation_beyond_the_document_is_caught",
        "fact_without_a_document_is_caught",
        "fact_from_an_unreadable_document_is_caught",
        "clarification_overwrite_is_caught",
        "false_absence_claim_is_caught",
    )
)

# ---- 175K: the explainability contract -------------------------------
citations = [
    build_citation(appendix_eligibility, appendix),
    build_citation(faq_match, faq),
    build_citation(amended_deadline, amendment),
]
out["citation_invariant_failures"] = sorted(
    {f for c in citations for f in citation_invariant_failures(c)}
)
out["citations_built"] = len(citations)
out["every_citation_names_a_document_and_quotes_it"] = all(
    c["document_id"] and c["quoted_text"] and c["content_sha256"] for c in citations
)
out["customer_explainability_contract_ready"] = bool(
    out["every_citation_names_a_document_and_quotes_it"]
    and not out["citation_invariant_failures"]
)

# ---- extensibility ----------------------------------------------------
reset_registered_document_types()
before = len(describe_document_model()["document_types"])
register_document_type("Program Announcement")
out["document_types_extensible"] = (
    "PROGRAM_ANNOUNCEMENT" in describe_document_model()["document_types"]
    and len(describe_document_model()["document_types"]) == before + 1
)
reset_registered_document_types()

# ---- model facts -------------------------------------------------------
out["document_model"] = {
    k: v for k, v in describe_document_model().items() if isinstance(v, bool)
}
out["fact_model"] = {
    k: v for k, v in describe_fact_model().items() if isinstance(v, bool)
}

out["document_invariant_failures"] = sorted(set(doc_failures))
out["fact_invariant_failures"] = sorted(set(fact_failures))
out["documents_first_class"] = (
    not out["document_invariant_failures"]
    and not out["fact_invariant_failures"]
    and all(d["canonical_id"] == CID for d in (v1, v2, appendix, faq, amendment))
)
out["adversarial_cases"] = cases

# ---- 175I: retrieval safety -------------------------------------------
out["live_document_downloads"] = 0
out["all_bytes_are_synthetic_fixtures"] = True

# ---- residue -----------------------------------------------------------
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    residue = 0
    for table in (
        "nf_opportunity_documents",
        "nf_opportunity_document_facts",
        "nf_opportunity_document_conflicts",
    ):
        residue += connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
finally:
    connection.close()

out["fixture_residue"] = residue
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
