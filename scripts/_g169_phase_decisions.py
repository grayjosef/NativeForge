"""Gate 169D/F/G/H/I/J: the match decision table, and the hard negatives.

Pure. No database, no network - which is the point. Every identity rule is
exercised from two dicts, so the branches that matter most (the refusals) do
not need a fixture to reach.

The positive cases prove the engine can recognize a match. The NEGATIVE cases
are the gate: each one is a pair that a title-similarity matcher would merge,
and each must come back DISTINCT or RELATED with a named reason. A merge
engine that cannot be shown refusing is not a merge engine, it is a collapse.
"""

from __future__ import annotations

import json
import socket
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate169 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.services.cross_source_identity_service import (  # noqa: E402
    DISTINCT,
    EXACT_MATCH,
    FORECAST_OF,
    PROVISIONAL_MATCH,
    RECURRENCE_OF,
    REPUBLISHED_FROM,
    REVIEW_REQUIRED,
    SAME_AS,
    build_blocking_keys,
    decide_match,
    decision_invariant_failures,
    describe_identity,
)

TRIBAL = (
    "U.S. Department of Justice FY26 Coordinated Tribal Assistance Solicitation"
)
TRIBAL_27 = TRIBAL.replace("FY26", "FY27")


def ident(**kw):
    return describe_identity(**kw)


#: Each case: two records, the decision expected, and what it is testing.
#: `expect_not_same_as` is separate from the decision because several cases
#: are legitimately RELATED - the failure being guarded is the MERGE, not the
#: relationship.
CASES: list[dict] = [
    # ---------------------------------------------- positive controls
    {
        "name": "same_number_same_doc_type",
        "why": "two sources citing one federal number is the easy case",
        "left": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "right": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_name="Bureau of Justice Assistance",
            title="FY26 Coordinated Tribal Assistance Solicitation",
        ),
        "expect": EXACT_MATCH,
        "expect_not_same_as": False,
    },
    {
        "name": "forecast_then_posted",
        "why": "169H: one number, two document kinds",
        "left": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="forecast",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "right": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "expect": FORECAST_OF,
        "expect_not_same_as": True,
    },
    {
        "name": "aggregator_republished_without_the_number",
        "why": "169E: the case where a real merge is actually needed",
        "left": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "right": ident(
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title="FY26 Coordinated Tribal Assistance Solicitation",
            source_record_id="agg-9912",
            source_id="nf169.fixture.aggregator",
        ),
        "expect": REPUBLISHED_FROM,
        "expect_not_same_as": True,
    },
    {
        "name": "republished_with_only_a_funder_name",
        "why": "names span non-aligned namespaces, so a human decides",
        "left": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "right": ident(
            doc_type="synopsis",
            agency_name="U.S. Dept. of Justice",
            title="FY26 Coordinated Tribal Assistance Solicitation",
        ),
        "expect": REVIEW_REQUIRED,
        "expect_not_same_as": True,
    },
    {
        "name": "two_unnumbered_records_with_a_shared_funder_code",
        "why": "plausible, resting on weak evidence, so provisional",
        "left": ident(
            doc_type="synopsis", agency_code="NF169-AG", title="Tribal Water Program"
        ),
        "right": ident(
            doc_type="synopsis", agency_code="NF169-AG", title="Tribal Water Program"
        ),
        "expect": PROVISIONAL_MATCH,
        "expect_not_same_as": True,
    },
    # --------------------------------------- 169F hard negatives
    {
        "name": "same_title_different_year",
        "why": "169G: an annual cycle a similarity matcher would merge",
        "left": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "right": ident(
            opportunity_number="O-BJA-2027-180001",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL_27,
        ),
        "expect": RECURRENCE_OF,
        "expect_not_same_as": True,
    },
    {
        "name": "same_agency_similar_title_different_number",
        "why": "agencies do not reuse numbers across solicitations",
        "left": ident(
            opportunity_number="O-BJA-2026-172662",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "right": ident(
            opportunity_number="O-BJA-2026-199999",
            doc_type="synopsis",
            agency_code="USDOJ-OJP-BJA",
            title=TRIBAL,
        ),
        "expect": DISTINCT,
        "expect_not_same_as": True,
    },
    {
        "name": "same_program_different_number",
        "why": "a program family is not an opportunity",
        "left": ident(
            opportunity_number="O-A-2026-1",
            doc_type="synopsis",
            agency_code="NF169-AG",
            program="Tribal Justice",
            title="Tribal Justice Planning Grants",
        ),
        "right": ident(
            opportunity_number="O-A-2026-2",
            doc_type="synopsis",
            agency_code="NF169-AG",
            program="Tribal Justice",
            title="Tribal Justice Implementation Grants",
        ),
        "expect": DISTINCT,
        "expect_not_same_as": True,
    },
    {
        "name": "same_deadline_unrelated_opportunity",
        "why": "a deadline is not identity; many things close on one date",
        "left": ident(
            opportunity_number="O-A-2026-10",
            doc_type="synopsis",
            agency_code="NF169-AG",
            title="Tribal Water Infrastructure",
        ),
        "right": ident(
            opportunity_number="O-B-2026-77",
            doc_type="synopsis",
            agency_code="NF169-BG",
            title="Rural Broadband Deployment",
        ),
        "expect": DISTINCT,
        "expect_not_same_as": True,
    },
    {
        "name": "same_title_different_funder",
        "why": "two funders can run programs with one name",
        "left": ident(
            doc_type="synopsis", agency_code="NF169-AG", title="Tribal Water Program"
        ),
        "right": ident(
            doc_type="synopsis", agency_code="NF169-ZZ", title="Tribal Water Program"
        ),
        "expect": DISTINCT,
        "expect_not_same_as": True,
    },
    {
        "name": "unnumbered_recurrence",
        "why": "the year must survive even with no identifier at all",
        "left": ident(doc_type="synopsis", agency_code="NF169-AG", title="FY26 Water"),
        "right": ident(doc_type="synopsis", agency_code="NF169-AG", title="FY27 Water"),
        "expect": RECURRENCE_OF,
        "expect_not_same_as": True,
    },
    {
        "name": "nothing_in_common",
        "why": "the floor: no shared evidence means distinct",
        "left": ident(doc_type="synopsis", title="Alpha"),
        "right": ident(doc_type="synopsis", title="Beta"),
        "expect": DISTINCT,
        "expect_not_same_as": True,
    },
]

out: dict[str, object] = {}
results: list[dict] = []
mismatches: list[str] = []
silent_merges: list[str] = []
unreasoned: list[str] = []
invariant_failures: list[str] = []

for case in CASES:
    decision = decide_match(left=case["left"], right=case["right"])
    failures = decision_invariant_failures(decision)
    invariant_failures.extend(f"{case['name']}:{f}" for f in failures)

    if decision["decision"] != case["expect"]:
        mismatches.append(
            f"{case['name']}: expected {case['expect']}, got {decision['decision']}"
        )
    if case["expect_not_same_as"] and decision.get("relationship") == SAME_AS:
        if not decision.get("machine_may_settle"):
            # A provisional SAME_AS is a candidate, not a merge - allowed.
            pass
        else:
            silent_merges.append(case["name"])
    if not decision.get("reasons"):
        unreasoned.append(case["name"])

    results.append(
        {
            "case": case["name"],
            "why_it_exists": case["why"],
            "decision": decision["decision"],
            "identity_layer": decision["identity_layer"],
            "relationship": decision["relationship"],
            "confidence": decision["confidence"],
            "machine_may_settle": decision["machine_may_settle"],
            "reasons": decision["reasons"],
        }
    )

out["cases"] = results
out["case_count"] = len(CASES)
out["decision_mismatches"] = mismatches
out["all_decisions_as_expected"] = not mismatches
out["silent_merges"] = silent_merges
out["no_silent_merge"] = not silent_merges
out["cases_without_a_reason"] = unreasoned
out["every_decision_named_a_reason"] = not unreasoned
out["decision_invariant_failures"] = invariant_failures
out["all_invariants_clean"] = not invariant_failures

# ---- only exact/strong may be machine-settled ----------------------
settleable = [r["case"] for r in results if r["machine_may_settle"]]
out["machine_settleable_cases"] = settleable
out["only_exact_or_strong_is_machine_settleable"] = all(
    r["decision"] in ("EXACT_MATCH", "STRONG_MATCH")
    for r in results
    if r["machine_may_settle"]
)
out["l4_cannot_settle_automatically"] = all(
    not r["machine_may_settle"] for r in results if r["identity_layer"] == "L4"
)
out["l3_cannot_settle_automatically"] = all(
    not r["machine_may_settle"] for r in results if r["identity_layer"] == "L3"
)

# ---- recurrence and forecast are never merges ----------------------
out["recurrence_never_proposes_a_merge"] = all(
    r["relationship"] != SAME_AS
    for r in results
    if r["decision"] == RECURRENCE_OF
)
out["forecast_never_proposes_a_merge"] = all(
    r["relationship"] != SAME_AS for r in results if r["decision"] == FORECAST_OF
)

# ---- 169J: conflicting evidence lowers certainty, never forces a merge
conflicted = decide_match(
    left=ident(
        opportunity_number="O-BJA-2026-172662",
        doc_type="synopsis",
        agency_code="USDOJ-OJP-BJA",
        title=TRIBAL,
    ),
    # Same opportunity, but this source is stale: abbreviated funder, no
    # number, and a title that has since been edited.
    right=ident(
        doc_type="synopsis",
        agency_name="DOJ",
        title="Coordinated Tribal Assistance Solicitation",
    ),
)
out["conflicting_evidence_decision"] = conflicted["decision"]
out["conflicting_evidence_layer"] = conflicted["identity_layer"]
out["conflicting_evidence_did_not_force_a_merge"] = not conflicted[
    "machine_may_settle"
]
out["conflicting_evidence_reasons"] = conflicted["reasons"]

# ---- blocking keys are bounded and exact-match indexable -----------
keys = build_blocking_keys(
    ident(
        opportunity_number="O-BJA-2026-172662",
        doc_type="synopsis",
        agency_code="USDOJ-OJP-BJA",
        program="Tribal Justice",
        title=TRIBAL,
        source_record_id="363308",
        source_id="nf-seed-2026-api-grants-gov-search2",
    )
)
out["blocking_keys_for_a_full_record"] = keys
out["blocking_key_count"] = len(keys)
out["blocking_keys_are_deduplicated"] = len(
    {(k["key_kind"], k["key_value"]) for k in keys}
) == len(keys)

# A record with nothing published produces no keys - it cannot be blocked
# into anyone's bucket, which is correct: it is not a candidate for anything.
out["empty_record_produces_no_keys"] = build_blocking_keys(ident()) == []

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
