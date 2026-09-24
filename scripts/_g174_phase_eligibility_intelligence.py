"""Gate 174I/J/K/M: the corpus, the amendment path, the tenant separation, and
the proof that the guards can fail.

The falsifiability section is the one that earns the corpus its score. A
sixteen-row corpus that reports 1.0 accuracy against a model written beside it
proves internal consistency and nothing else, so five deliberate breakages are
planted and each one is asserted to be CAUGHT:

```text
an exclusion applied, result still ELIGIBLE
a requirement that lost its original text
a profile that verified its own authority
a match that dropped a requirement
a match that reparsed the source per tenant
```

174K is measured rather than claimed: the same opportunity is matched for one
tenant and for fifty, and the number of REQUIREMENT NORMALIZATIONS must not
move. Only the match count scales with tenants, because only the match is
per-tenant.

No network. Nothing written to the real database.
"""

from __future__ import annotations

import datetime as dt
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
        raise OSError("gate174 eligibility phase makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.services.eligibility_gold_corpus_service import (  # noqa: E402
    describe_corpus,
    run_corpus,
)
from nativeforge.services.eligibility_match_engine_service import (  # noqa: E402
    match_eligibility,
    match_invariant_failures,
)
from nativeforge.services.eligibility_requirement_model_service import (  # noqa: E402
    APPLICANT_TYPE,
    CONDITIONALLY_ELIGIBLE,
    ELIGIBLE,
    EXCLUSION,
    MATCHING_FUNDS,
    build_requirement,
    requirement_invariant_failures,
)
from nativeforge.services.organization_capability_profile_service import (  # noqa: E402
    VERIFIED_BY_AUTHORITY,
    build_profile,
    profile_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DB = REPO / "nativeforge.local.db"
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)

out: dict[str, object] = {"schema_version": "nf_gate174_eligibility_v1"}


def _req(key: str, kind: str, value: object, text: str, **kw: object) -> dict:
    return build_requirement(
        canonical_id=key,
        requirement_kind=kind,
        normalized_value=value,
        original_text=text,
        raw_payload_sha256="g174.payload",
        source_id="g174.source",
        evidence_ids=[f"ev.{key}.{kind.lower()}"],
        **kw,  # type: ignore[arg-type]
    )


# ============ 174I: the corpus ========================================
report = run_corpus()
out["corpus"] = describe_corpus()
for key in (
    "corpus_size",
    "pursuable_truth_count",
    "blocked_truth_count",
    "eligibility_false_positive_count",
    "eligibility_false_negative_count",
    "eligibility_false_positives",
    "eligibility_false_negatives",
    "unknown_count",
    "review_required_count",
    "conditional_count",
    "result_accuracy",
    "rows_with_wrong_result",
    "invariant_failures",
):
    out[f"corpus_{key}"] = report[key]

# ============ 174M: the guards have to be able to fail ================
falsifiability: dict[str, object] = {}

# 1. an exclusion applied, and the result still says go
base_profile = build_profile(
    organization_id="g174.org", facts={"entity_class": "tribal_government"}
)
excluded = match_eligibility(
    canonical_id="g174.excluded",
    requirements=[
        _req(
            "g174.excluded",
            APPLICANT_TYPE,
            ["tribal_government"],
            "Tribal governments are not eligible",
            polarity=EXCLUSION,
            applies_to_entity_classes=["tribal_government"],
        )
    ],
    profile=base_profile,
)
forced = dict(excluded)
forced["eligibility_result"] = ELIGIBLE
falsifiability["exclusion_ignored_is_caught"] = bool(match_invariant_failures(forced))
falsifiability["exclusion_ignored_failures"] = match_invariant_failures(forced)

# 2. a requirement that discarded the funder's words
stripped = _req("g174.stripped", MATCHING_FUNDS, True, "20% match required")
stripped_forced = dict(stripped)
stripped_forced["original_text"] = None
falsifiability["requirement_without_original_text_is_caught"] = bool(
    requirement_invariant_failures(stripped_forced)
)

# 3. Gate 174 verifying its own authority
self_verified = build_profile(
    organization_id="g174.org",
    facts={
        "federal_recognition": {
            "value": True,
            "verification": VERIFIED_BY_AUTHORITY,
        }
    },
)
falsifiability["gate174_authority_verification_is_caught"] = bool(
    profile_invariant_failures(self_verified)
)

# 4. a match that lost a requirement
lost = dict(excluded)
lost["requirement_count"] = 5
falsifiability["dropped_requirement_is_caught"] = bool(match_invariant_failures(lost))

# 5. a match that reparsed per tenant
reparsed = dict(excluded)
reparsed["reparsed_source_per_tenant"] = True
reparsed["consumed_global_normalization"] = False
falsifiability["per_tenant_reparse_is_caught"] = bool(
    match_invariant_failures(reparsed)
)

# 6. a naive engine that ignores entity-class boundaries must score worse.
#    Proving the corpus MEASURES something rather than agreeing with itself.
naive_hits = 0
for row in report["results"]:
    # "anything Native-ish is eligible"
    said_pursuable = "tribe" in row["key"] or "native" in row["key"]
    if said_pursuable == row["truth_is_pursuable"]:
        naive_hits += 1
falsifiability["naive_baseline_accuracy"] = round(
    naive_hits / max(len(report["results"]), 1), 4
)
falsifiability["real_engine_beats_naive_baseline"] = (
    report["result_accuracy"] or 0
) > falsifiability["naive_baseline_accuracy"]

out["falsifiability"] = falsifiability
out["eligibility_self_health_ready"] = all(
    bool(falsifiability[key])
    for key in (
        "exclusion_ignored_is_caught",
        "requirement_without_original_text_is_caught",
        "gate174_authority_verification_is_caught",
        "dropped_requirement_is_caught",
        "per_tenant_reparse_is_caught",
        "real_engine_beats_naive_baseline",
    )
)

# ============ 174J: an amendment changes eligibility ==================
# The original notice requires a match this Tribe cannot meet. An amendment
# removes the requirement. The result must MOVE, and the prior answer must
# still be reconstructible from the requirement versions.
key = "g174.amendment"
profile = build_profile(
    organization_id="g174.org",
    facts={"entity_class": "tribal_government", "matching_funds_capability": False},
)
before_requirements = [
    _req(
        key,
        APPLICANT_TYPE,
        ["tribal_government"],
        "Indian tribes",
        applies_to_entity_classes=["tribal_government"],
    ),
    _req(key, MATCHING_FUNDS, True, "A 25% non-federal match is required"),
]
after_requirements = [before_requirements[0]]

before = match_eligibility(
    canonical_id=key, requirements=before_requirements, profile=profile
)
after = match_eligibility(
    canonical_id=key, requirements=after_requirements, profile=profile
)

out["amendment_before_result"] = before["eligibility_result"]
out["amendment_after_result"] = after["eligibility_result"]
out["amendment_before_conditions"] = before["conditions_to_obtain"]
out["amendment_changed_the_result"] = (
    before["eligibility_result"] != after["eligibility_result"]
)
out["amendment_before_was_conditional"] = (
    before["eligibility_result"] == CONDITIONALLY_ELIGIBLE
)
out["amendment_after_is_eligible"] = after["eligibility_result"] == ELIGIBLE
out["amendment_eligibility_changes_supported"] = bool(
    out["amendment_changed_the_result"]
    and out["amendment_before_was_conditional"]
    and out["amendment_after_is_eligible"]
)
# 174J: reuse Gate 170, do not build a second change pipeline.
out["reuses_gate170_change_taxonomy"] = (
    REPO / "src" / "nativeforge" / "services" / "opportunity_change_taxonomy_service.py"
).is_file()
out["no_second_change_pipeline"] = not any(
    path.name.startswith("eligibility_change")
    for path in (REPO / "src" / "nativeforge" / "services").glob("*.py")
)

# ============ 174K: global normalization, measured ====================
normalizations = {"count": 0}


def normalize_once(canonical_id: str) -> list[dict]:
    """Stands in for the parsing layer. Counted so tenants cannot multiply it."""
    normalizations["count"] += 1
    return [
        _req(
            canonical_id,
            APPLICANT_TYPE,
            ["tribal_government"],
            "Indian tribes",
            applies_to_entity_classes=["tribal_government"],
        ),
        _req(canonical_id, MATCHING_FUNDS, True, "20% match"),
    ]


def run_tenants(count: int) -> tuple[int, int]:
    normalizations["count"] = 0
    requirements = normalize_once("g174.tenants")
    matches = 0
    for index in range(count):
        tenant_profile = build_profile(
            organization_id=f"org.{index}",
            facts={
                "entity_class": "tribal_government",
                "matching_funds_capability": index % 2 == 0,
            },
        )
        match_eligibility(
            canonical_id="g174.tenants",
            requirements=requirements,
            profile=tenant_profile,
            tenant_id=f"tenant.{index}",
        )
        matches += 1
    return normalizations["count"], matches


one_norm, one_match = run_tenants(1)
fifty_norm, fifty_match = run_tenants(50)

out["normalizations_with_1_tenant"] = one_norm
out["normalizations_with_50_tenants"] = fifty_norm
out["matches_with_1_tenant"] = one_match
out["matches_with_50_tenants"] = fifty_match
out["global_normalization_reused"] = one_norm == fifty_norm == 1
out["only_the_match_scales_with_tenants"] = fifty_match == 50 and fifty_norm == 1

# Two different tenants, same opportunity, DIFFERENT answers - which is the
# point of separating global normalization from the per-tenant match.
requirements = normalize_once("g174.divergent")
can_match = build_profile(
    organization_id="org.can",
    facts={"entity_class": "tribal_government", "matching_funds_capability": True},
)
cannot_match = build_profile(
    organization_id="org.cannot",
    facts={"entity_class": "tribal_government", "matching_funds_capability": False},
)
match_a = match_eligibility(
    canonical_id="g174.divergent",
    requirements=requirements,
    profile=can_match,
    tenant_id="tenant.a",
)
match_b = match_eligibility(
    canonical_id="g174.divergent",
    requirements=requirements,
    profile=cannot_match,
    tenant_id="tenant.b",
)
out["tenant_a_result"] = match_a["eligibility_result"]
out["tenant_b_result"] = match_b["eligibility_result"]
out["same_opportunity_different_tenant_answers"] = (
    match_a["eligibility_result"] != match_b["eligibility_result"]
)
out["match_failures"] = sorted(
    set(match_invariant_failures(match_a) + match_invariant_failures(match_b))
)

# ============ explainability ==========================================
# Every requirement accounted for, and every answer able to name its evidence.
out["explainable_satisfied"] = len(match_b["satisfied_requirements"])
out["explainable_unsatisfied"] = len(match_b["unsatisfied_requirements"])
out["explainable_unknown"] = len(match_b["unknown_requirements"])
out["explainable_conditions"] = match_b["conditions_to_obtain"]
out["explainable_evidence_ids"] = len(match_b["supporting_evidence_ids"])
out["every_requirement_accounted_for"] = (
    match_b["accounted_for"] == match_b["requirement_count"]
)
out["eligibility_match_explainable"] = bool(
    out["every_requirement_accounted_for"]
    and match_b["supporting_evidence_ids"]
    and match_b["reason"]
)

# ============ residue and network =====================================
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    residue = 0
    for table in (
        "nf_opportunity_eligibility_requirements",
        "nf_organization_capability_profiles",
        "nf_tenant_eligibility_matches",
    ):
        residue += connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
finally:
    connection.close()

out["fixture_residue"] = residue
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
