"""Corpus provenance attestation (Gate 89B).

Validates an operator's account of where the corpus came from, before anything is
allowed to act on it.

Gate 88 established that 18 of 185 records have an artefact behind them and 166
rest on assertion. The 166 cannot be resolved from committed data - that avenue
is exhausted. What remains is to ask the person who produced the corpus, and an
answer is only useful if it is held to a standard.

## What an attestation can and cannot buy

It can buy ``recorded_verified`` for specific records, and only by pointing at
raw transport that exists - an artefact carrying information the corpus row could
not have supplied. That is Gate 88's test and this module does not soften it.

It cannot buy live coverage, monitored sources, or an improvement claim. Those
are runtime facts about a system, not historical facts about data, and no
statement about the past can create them. The three flags are constants here.

## Why a human statement is held to a standard at all

Because the failure this campaign keeps finding is not dishonesty, it is
optimism recorded as fact. ``real_fetch: true``, ``never_synthesized: true``, and
a commit message reading "40 real ingested grants" were all written in good
faith. Each turned out to mean less than it appeared to.

So an attestation that says "yes it was fetched" and points at nothing gets
``valid_limited_attestation``, verifies no records, and is recorded as such. An
attestation that contradicts committed evidence gets rejected outright rather
than averaged against it.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_corpus_provenance_attestation_v1"

ATTESTATION_STATUSES = frozenset(
    {
        # Raw transport named, scope clear, limitations stated. May verify the
        # records it names.
        "valid_complete_attestation",
        # Internally sound but without raw transport, or covering only part of
        # its scope. Verifies nothing.
        "valid_limited_attestation",
        # Too little to act on at all.
        "insufficient_attestation",
        # Says something the committed evidence refutes.
        "contradictory_attestation",
        # Absent, or unrecognisable as an attestation.
        "unknown_attestation",
    }
)

# Only this status may upgrade a record.
UPGRADE_PERMITTING_STATUSES = frozenset({"valid_complete_attestation"})

# Every field the packet asks for. A missing field is reported by name rather
# than silently defaulted, because a blank answer and a "no" are different.
REQUIRED_FIELDS: tuple[str, ...] = (
    "attestation_id",
    "attested_at",
    "attested_by",
    "attestation_scope",
    "corpus_files",
    "record_id_ranges",
    "source_systems",
    "collection_method",
    "collection_window",
    "raw_transport_available",
    "raw_transport_artifact_paths",
    "source_terms_reviewed",
    "source_terms_status",
    "live_fetch_performed",
    "fetch_tool_or_script",
    "field_mapping_summary",
    "deadline_source",
    "eligibility_source",
    "provenance_limitations",
    "known_placeholders",
    "known_circular_sources",
    "records_to_exclude_from_verified",
    "records_allowed_for_verified_upgrade",
    "human_statement",
)

# Fields without which nothing can be assessed at all.
CORE_FIELDS: tuple[str, ...] = (
    "attestation_id",
    "attested_by",
    "attested_at",
    "corpus_files",
    "collection_method",
    "human_statement",
)

COLLECTION_METHODS = frozenset(
    {
        "live_fetch",
        "recorded_replay",
        "copied_from_another_corpus_row",
        "generated",
        "synthesized",
        "transformed",
        "manually_assembled",
        "mixed",
        "unknown",
    }
)

# Methods that are incompatible with calling a record a recording of an
# external source, whatever else the attestation says.
NON_RECORDING_METHODS = frozenset(
    {"generated", "synthesized", "copied_from_another_corpus_row"}
)

# Methods that affirmatively describe a recording. Deny by default: verification
# requires membership here, NOT merely absence from NON_RECORDING_METHODS.
#
# The difference matters. Subtracting the denied set means "unknown", "mixed" and
# any method nobody has thought of yet all sail through - which is how a typo in
# this field could verify a record. Gate 79B's lesson, applied to a form field.
#
# `transformed`, `manually_assembled` and `mixed` are deliberately absent: each
# may well sit on top of a real fetch, but the attestation has to say which, and
# a follow-up naming the underlying method costs one line.
RECORDING_METHODS = frozenset({"live_fetch", "recorded_replay"})

TERMS_STATUSES = frozenset(
    {
        "reviewed_cleared",
        "reviewed_blocked",
        "reviewed_unclear",
        "not_reviewed",
        "unknown",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def validate_corpus_provenance_attestation(
    *,
    attestation: dict[str, Any] | None,
    committed_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess one attestation.

    ``committed_evidence`` is what the repository already knows, so the
    attestation can be checked against it rather than believed on its own. The
    caller supplies it; this module performs no I/O.

    Expected shape (all optional)::

        {
          "circular_artifact_paths": [...],   # transports naming a corpus row
          "artifact_backed_record_ids": [...],# records Gate 88 already verified
          "suspected_placeholder_record_ids": [...],
        }
    """
    evidence = committed_evidence or {}
    findings: list[str] = []
    contradictions: list[str] = []
    limitations: list[str] = []

    if not attestation:
        return _result(
            status="unknown_attestation",
            missing_fields=list(REQUIRED_FIELDS),
            blocked_reasons=["no_attestation_supplied"],
            findings=["gate_88_classifications_remain_authoritative"],
        )

    # A blank and a "no" are different answers, and the packet promises to treat
    # them differently. An absent key, or one set to None or an empty string, is
    # unanswered. A key present with an empty list is answered: "I checked,
    # there are none" - which is exactly the right answer for
    # `known_placeholders` on a batch that has none, and counting it as a gap
    # would penalise the most careful respondent.
    def _unanswered(field: str) -> bool:
        if field not in attestation:
            return True
        value = attestation.get(field)
        return value is None or (isinstance(value, str) and not value.strip())

    missing = [f for f in REQUIRED_FIELDS if _unanswered(f)]

    # Core fields are held to the stricter reading: an attestation naming no
    # corpus files has no scope, and "none" is not a coherent answer to who
    # attested or how the data was collected.
    def _core_missing(field: str) -> bool:
        if _unanswered(field):
            return True
        value = attestation.get(field)
        return isinstance(value, (list, tuple, set, dict)) and not value

    missing_core = [f for f in CORE_FIELDS if _core_missing(f)]

    if missing_core:
        return _result(
            status="insufficient_attestation",
            missing_fields=missing,
            blocked_reasons=[f"missing_core_field:{f}" for f in missing_core],
            findings=["gate_88_classifications_remain_authoritative"],
        )

    method = str(attestation.get("collection_method") or "unknown")
    if method not in COLLECTION_METHODS:
        findings.append(f"unrecognised_collection_method:{method}")
        method = "unknown"

    raw_available = attestation.get("raw_transport_available") is True
    raw_paths = [
        str(p) for p in _as_list(attestation.get("raw_transport_artifact_paths"))
    ]
    excluded = {
        str(r)
        for r in _as_list(attestation.get("records_to_exclude_from_verified"))
    }
    requested = [
        str(r)
        for r in _as_list(attestation.get("records_allowed_for_verified_upgrade"))
    ]

    # -- contradictions against committed evidence ------------------------
    circular_paths = {
        str(p) for p in _as_list(evidence.get("circular_artifact_paths"))
    }
    circular_named = sorted(set(raw_paths) & circular_paths)
    for path in circular_named:
        # The Gate 87/88 finding: a transport that names a corpus row as its
        # source cannot corroborate that row. Offering it as raw transport is a
        # contradiction, not a weak point.
        contradictions.append(f"cites_circular_artifact_as_raw_transport:{path}")

    if raw_available and not raw_paths:
        contradictions.append("claims_raw_transport_but_names_no_path")

    if (
        attestation.get("live_fetch_performed") is True
        and method in NON_RECORDING_METHODS
    ):
        contradictions.append(f"claims_live_fetch_but_method_is:{method}")

    # A record cannot be both excluded and offered for upgrade.
    both = sorted(excluded & set(requested))
    for record_id in both:
        contradictions.append(f"record_both_excluded_and_offered:{record_id}")

    # Placeholder claims that contradict what the repository already found are
    # recorded as contradictions in one direction only. An attestation
    # *confirming* a suspicion is welcome; one denying it without evidence is
    # not enough to overturn the finding.
    suspected = {
        str(r) for r in _as_list(evidence.get("suspected_placeholder_record_ids"))
    }
    declared_placeholders = {
        str(r) for r in _as_list(attestation.get("known_placeholders"))
    }
    denied = sorted(suspected & set(requested))
    for record_id in denied:
        if record_id not in declared_placeholders:
            contradictions.append(
                f"offers_suspected_placeholder_for_upgrade:{record_id}"
            )

    if contradictions:
        return _result(
            status="contradictory_attestation",
            missing_fields=missing,
            blocked_reasons=contradictions,
            findings=[*findings, "gate_88_classifications_remain_authoritative"],
        )

    # -- what it can support ----------------------------------------------
    if not attestation.get("provenance_limitations"):
        limitations.append("attestation_states_no_limitations")

    if method in NON_RECORDING_METHODS:
        limitations.append(f"collection_method_is_not_a_recording:{method}")
    elif method not in RECORDING_METHODS:
        limitations.append(
            f"collection_method_does_not_establish_a_recording:{method}"
        )
    if not raw_available:
        limitations.append("no_raw_transport_available")
    if not attestation.get("source_terms_reviewed"):
        limitations.append("source_terms_not_reviewed")

    terms_status = str(attestation.get("source_terms_status") or "unknown")
    if terms_status not in TERMS_STATUSES:
        findings.append(f"unrecognised_terms_status:{terms_status}")

    # Verification requires raw transport, a recording method, and named
    # records. Anything short of all three is limited.
    can_upgrade = (
        raw_available
        and bool(raw_paths)
        # Affirmative membership, not absence from the denied set.
        and method in RECORDING_METHODS
        and bool(requested)
        and not missing
    )

    if can_upgrade:
        status = "valid_complete_attestation"
        findings.append("raw_transport_named_and_scope_stated")
    else:
        status = "valid_limited_attestation"
        if missing:
            limitations.append("attestation_incomplete")
        if not requested:
            limitations.append("no_records_offered_for_upgrade")

    # Records this attestation may verify. Never includes anything it excludes,
    # and never anything it did not name.
    upgradable = (
        sorted(set(requested) - excluded)
        if status in UPGRADE_PERMITTING_STATUSES
        else []
    )

    return _result(
        status=status,
        missing_fields=missing,
        findings=findings,
        limitations=limitations,
        records_eligible_for_upgrade=upgradable,
        records_excluded=sorted(excluded),
        raw_transport_paths=raw_paths,
        collection_method=method,
        terms_status=terms_status,
        attestation_id=str(attestation.get("attestation_id")),
        attested_by=str(attestation.get("attested_by")),
        attested_at=str(attestation.get("attested_at")),
    )


def _result(
    *,
    status: str,
    missing_fields: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
    findings: list[str] | None = None,
    limitations: list[str] | None = None,
    records_eligible_for_upgrade: list[str] | None = None,
    records_excluded: list[str] | None = None,
    raw_transport_paths: list[str] | None = None,
    collection_method: str = "unknown",
    terms_status: str = "unknown",
    attestation_id: str | None = None,
    attested_by: str | None = None,
    attested_at: str | None = None,
) -> dict[str, Any]:
    permits = status in UPGRADE_PERMITTING_STATUSES
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "attestation_status": status,
            "attestation_id": attestation_id,
            "attested_by": attested_by,
            "attested_at": attested_at,
            "collection_method": collection_method,
            "source_terms_status": terms_status,
            "missing_fields": list(missing_fields or []),
            "blocked_reasons": list(blocked_reasons or []),
            "findings": list(findings or []),
            "limitations": list(limitations or []),
            "permits_verified_upgrade": permits,
            "records_eligible_for_upgrade": list(records_eligible_for_upgrade or []),
            "records_excluded": list(records_excluded or []),
            "raw_transport_paths": list(raw_transport_paths or []),
            # Constants. An account of the past cannot create a runtime fact,
            # however complete it is.
            "creates_live_coverage": False,
            "creates_source_monitoring": False,
            "permits_improvement_claim": False,
            "fabricated": False,
        }
    )


def attestation_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "creates_live_coverage",
        "creates_source_monitoring",
        "permits_improvement_claim",
    ):
        if result.get(constant) is not False:
            fails.append(f"attestation_claimed:{constant}")

    status = result.get("attestation_status")
    if status not in ATTESTATION_STATUSES:
        fails.append(f"attestation_status_out_of_vocabulary:{status}")

    permits = bool(result.get("permits_verified_upgrade"))
    if permits and status not in UPGRADE_PERMITTING_STATUSES:
        fails.append(f"upgrade_permitted_under_status:{status}")
    if not permits and result.get("records_eligible_for_upgrade"):
        fails.append("records_eligible_for_upgrade_without_permission")

    # A complete attestation must have named transport to be complete at all.
    if status == "valid_complete_attestation" and not result.get(
        "raw_transport_paths"
    ):
        fails.append("complete_attestation_without_raw_transport")

    # An excluded record may never appear as upgradable.
    overlap = set(result.get("records_eligible_for_upgrade") or []) & set(
        result.get("records_excluded") or []
    )
    if overlap:
        fails.append(f"excluded_record_offered_for_upgrade:{sorted(overlap)}")

    # A rejection must say why.
    if status in {"contradictory_attestation", "insufficient_attestation"} and not (
        result.get("blocked_reasons")
    ):
        fails.append(f"{status}_without_a_stated_reason")

    return fails


def build_attestation_contract() -> dict[str, Any]:
    """The declared shape, for docs and for drift tests."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "statuses": sorted(ATTESTATION_STATUSES),
            "upgrade_permitting_statuses": sorted(UPGRADE_PERMITTING_STATUSES),
            "required_fields": list(REQUIRED_FIELDS),
            "core_fields": list(CORE_FIELDS),
            "collection_methods": sorted(COLLECTION_METHODS),
            "recording_methods": sorted(RECORDING_METHODS),
            "non_recording_methods": sorted(NON_RECORDING_METHODS),
            "terms_statuses": sorted(TERMS_STATUSES),
            "creates_live_coverage": False,
            "creates_source_monitoring": False,
            "permits_improvement_claim": False,
        }
    )
