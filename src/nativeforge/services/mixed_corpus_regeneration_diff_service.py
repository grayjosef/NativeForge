"""Mixed corpus regeneration diff (Gate 106B).

Compares the committed manifest against fresh derivation and classifies every
difference. It decides nothing about the world - it decides whether a fixture
mutation is safe to attempt, and it refuses by default.

## Why a diff needs classification at all

A fixture regeneration is a bulk overwrite. "57 rows written" tells a reviewer
nothing about whether the overwrite was correct. What matters is whether every
individual change can be attributed to a known, intended cause.

So each differing field is placed in exactly one class:

```text
gate105_tribal_bridge_correction  the canonical Tribal classifier fix landing
preexisting_fixture_drift         divergence that predates the fix
unexpected                        neither - nobody can say why this changed
unchanged                         identical on both sides
```

Anything that lands in `unexpected` blocks regeneration. That is the point: a
change nobody can explain is exactly the change that should never be written
into a corpus silently.

## Deny by default

`safe_to_regenerate` is derived affirmatively - it is true only when the
positive conditions all hold, never by subtracting known problems from a
permissive default:

```text
every changed field classified as an expected Gate 105 correction
no unexpected changes
no unresolved pre-existing drift
no positives removed
no fabricated eligibility risk
row ids and ordering identical
fresh derivation deterministic
```

A caller cannot pass a flag to make it true. Gate 98 shipped a scheduler that
permitted an unrecognised override; this refuses anything it cannot name.

## Fabricated eligibility risk

The specific hazard Gate 106A found: derivation copies a `synopsis` into
`eligibility_text` when the latter is empty. On a row recording that no NOFO
exists, that writes administrative prose into the field the Tribal classifier and
evidence derivation read.

`fabricated_eligibility_risk` is therefore not a hand-set flag. It is computed by
looking at what the change would actually do to an honest blank, and it is true
whenever a regeneration would populate an empty evidence field on a row that
marked itself `empty_honestly` or `never_synthesized`, or would narrow an unknown
into an affirmative negative.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_mixed_corpus_regeneration_diff_v1"

CHANGE_CLASSES = frozenset(
    {
        "gate105_tribal_bridge_correction",
        "preexisting_fixture_drift",
        "unexpected",
        "unchanged",
    }
)

# The only class a regeneration may consist of.
REGENERATION_PERMITTED_CLASSES = frozenset({"gate105_tribal_bridge_correction"})

EVIDENCE_STATUSES = frozenset(
    {
        "evidence_backed",
        "honest_absence_overwritten",
        "unknown_narrowed_to_negative",
        "not_applicable",
    }
)

# Rows and field the Gate 105 canonical Tribal classifier fix is expected to
# touch, and the exact transition it is expected to make. Anything else on these
# rows is still unexpected.
GATE105_EXPECTED_ROWS = frozenset(
    {
        "nf14-mixed-edge-10",
        "nf14-mixed-label_spread-14",
        "nf14-mixed-label_spread-15",
    }
)
GATE105_EXPECTED_FIELD = "applicant_types_include_tribal"
GATE105_EXPECTED_TRANSITION = (False, True)

# Fields that feed the evidence path. Writing into one of these on a row that
# recorded an honest absence is fabrication, not enrichment.
EVIDENCE_FIELDS = frozenset({"eligibility_text", "eligibility_tags", "synopsis"})

# Flags by which a row states that its emptiness is deliberate.
HONESTY_FLAGS = ("empty_honestly", "never_synthesized", "no_live_nofo")

POSITIVE_FIELDS = (
    "applicant_types_include_tribal",
    "tribal_eligible",
    "tribal_set_aside",
    "tribe_eligible_broad",
)

DIFF_ROW_FIELDS: tuple[str, ...] = (
    "row_id",
    "field",
    "cached_value",
    "fresh_value",
    "change_class",
    "expected_reason",
    "evidence_status",
    "human_review_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def manifest_hash(payload: Any) -> str:
    """Stable content hash. Sorted keys, so key order cannot move the answer."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return not value
    return False


def _row_claims_honest_emptiness(row: dict[str, Any]) -> bool:
    return any(row.get(flag) is True for flag in HONESTY_FLAGS)


def classify_field_change(
    *,
    row_id: str,
    field: str,
    cached_row: dict[str, Any],
    fresh_row: dict[str, Any],
) -> dict[str, Any]:
    """One differing field, named and attributed."""
    cached_value = cached_row.get(field)
    fresh_value = fresh_row.get(field)

    if cached_value == fresh_value:
        return _json_safe(
            {
                "row_id": row_id,
                "field": field,
                "cached_value": cached_value,
                "fresh_value": fresh_value,
                "change_class": "unchanged",
                "expected_reason": "",
                "evidence_status": "not_applicable",
                "human_review_required": False,
            }
        )

    change_class = "unexpected"
    expected_reason = ""
    evidence_status = "not_applicable"
    human_review_required = True

    is_gate105 = (
        row_id in GATE105_EXPECTED_ROWS
        and field == GATE105_EXPECTED_FIELD
        and (cached_value, fresh_value) == GATE105_EXPECTED_TRANSITION
    )

    if is_gate105:
        change_class = "gate105_tribal_bridge_correction"
        expected_reason = (
            "canonical Tribal classifier now recognises the applicant type this "
            "row already carried in its source text"
        )
        evidence_status = "evidence_backed"
        human_review_required = False
    elif field in EVIDENCE_FIELDS and _is_blank(cached_value) and not _is_blank(
        fresh_value
    ):
        # Writing into an evidence field that was empty.
        change_class = "preexisting_fixture_drift"
        if _row_claims_honest_emptiness(cached_row) or _row_claims_honest_emptiness(
            fresh_row
        ):
            evidence_status = "honest_absence_overwritten"
            expected_reason = (
                "derivation would populate an evidence field on a row that "
                "marked its own emptiness deliberate"
            )
        else:
            evidence_status = "honest_absence_overwritten"
            expected_reason = (
                "derivation would populate a previously empty evidence field"
            )
    elif cached_value is None and fresh_value is False:
        # Unknown becoming an affirmative negative.
        change_class = "preexisting_fixture_drift"
        evidence_status = "unknown_narrowed_to_negative"
        expected_reason = (
            "unknown narrowed to an affirmative negative, which asserts more "
            "than the source says"
        )

    # No catch-all. `preexisting_fixture_drift` names a divergence this service
    # can actually characterise; it is not a bucket for "not Gate 105".
    #
    # An earlier draft ended with `elif row_id not in GATE105_EXPECTED_ROWS ->
    # preexisting_fixture_drift`, which made `unexpected` unreachable on every
    # row outside the three. An unexplained corpus change would then have been
    # reported as understood drift and waved through as known. Anything this
    # service cannot name stays `unexpected` and blocks.

    return _json_safe(
        {
            "row_id": row_id,
            "field": field,
            "cached_value": cached_value,
            "fresh_value": fresh_value,
            "change_class": change_class,
            "expected_reason": expected_reason,
            "evidence_status": evidence_status,
            "human_review_required": human_review_required,
        }
    )


def build_regeneration_diff(
    *,
    cached_manifest: dict[str, Any] | None = None,
    fresh_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare committed manifest against fresh derivation. Fetches nothing."""
    from nativeforge.services.mixed_corpus_builder_service import (
        MIXED_CORPUS_PATH,
        build_mixed_real_corpus,
    )

    if cached_manifest is None:
        cached_manifest = json.loads(MIXED_CORPUS_PATH.read_text(encoding="utf-8"))
    cached_rows = list(cached_manifest.get("grants") or [])

    if fresh_rows is None:
        fresh_rows = build_mixed_real_corpus(use_cached_manifest=False)

    cached_by_id = {r.get("grant_id"): r for r in cached_rows}
    fresh_by_id = {r.get("grant_id"): r for r in fresh_rows}
    cached_ids = [r.get("grant_id") for r in cached_rows]
    fresh_ids = [r.get("grant_id") for r in fresh_rows]

    blocked_reasons: list[str] = []
    diff_rows: list[dict[str, Any]] = []

    if set(cached_ids) != set(fresh_ids):
        blocked_reasons.append("row_identity_set_differs")
    if cached_ids != fresh_ids:
        blocked_reasons.append("row_ordering_differs")

    for row_id in cached_ids:
        cached_row = cached_by_id.get(row_id) or {}
        fresh_row = fresh_by_id.get(row_id)
        if fresh_row is None:
            blocked_reasons.append(f"row_missing_from_fresh_derivation:{row_id}")
            continue
        for field in sorted(set(cached_row) | set(fresh_row)):
            if cached_row.get(field) == fresh_row.get(field):
                continue
            diff_rows.append(
                classify_field_change(
                    row_id=row_id,
                    field=field,
                    cached_row=cached_row,
                    fresh_row=fresh_row,
                )
            )

    changed_row_ids = sorted({d["row_id"] for d in diff_rows})
    gate105 = [
        d for d in diff_rows if d["change_class"] == "gate105_tribal_bridge_correction"
    ]
    preexisting = [
        d for d in diff_rows if d["change_class"] == "preexisting_fixture_drift"
    ]
    unexpected = [d for d in diff_rows if d["change_class"] == "unexpected"]

    positives_added: list[dict[str, Any]] = []
    positives_removed: list[dict[str, Any]] = []
    for row_id in cached_ids:
        cached_row = cached_by_id.get(row_id) or {}
        fresh_row = fresh_by_id.get(row_id) or {}
        for field in POSITIVE_FIELDS:
            if cached_row.get(field) is not True and fresh_row.get(field) is True:
                positives_added.append({"row_id": row_id, "field": field})
            if cached_row.get(field) is True and fresh_row.get(field) is not True:
                positives_removed.append({"row_id": row_id, "field": field})

    fabricated_risk_rows = [
        d
        for d in diff_rows
        if d["evidence_status"]
        in {"honest_absence_overwritten", "unknown_narrowed_to_negative"}
    ]
    fabricated_eligibility_risk = bool(fabricated_risk_rows)

    if unexpected:
        blocked_reasons.append(f"unexpected_changes:{len(unexpected)}")
    if preexisting:
        blocked_reasons.append(f"unresolved_preexisting_drift:{len(preexisting)}")
    if positives_removed:
        blocked_reasons.append(f"positives_removed:{len(positives_removed)}")
    if fabricated_eligibility_risk:
        blocked_reasons.append(
            f"fabricated_eligibility_risk:{len(fabricated_risk_rows)}"
        )

    # Derived affirmatively. Every condition must hold; nothing is subtracted
    # from a permissive default and no caller can assert it.
    safe_to_regenerate = (
        not blocked_reasons
        and all(
            d["change_class"] in REGENERATION_PERMITTED_CLASSES for d in diff_rows
        )
        and not positives_removed
        and not fabricated_eligibility_risk
        and cached_ids == fresh_ids
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cached_manifest_hash": manifest_hash(cached_manifest),
            "fresh_manifest_hash": manifest_hash(fresh_rows),
            "rows_total": len(cached_rows),
            "rows_changed": len(changed_row_ids),
            "changed_row_ids": changed_row_ids,
            "fields_changed": len(diff_rows),
            "gate105_expected_changes": gate105,
            "gate105_expected_change_count": len(gate105),
            "preexisting_drift_rows": sorted({d["row_id"] for d in preexisting}),
            "preexisting_drift_count": len(preexisting),
            "unexpected_changes": unexpected,
            "unexpected_change_count": len(unexpected),
            "positives_added": positives_added,
            "positives_removed": positives_removed,
            "fabricated_eligibility_risk": fabricated_eligibility_risk,
            "fabricated_risk_rows": fabricated_risk_rows,
            "safe_to_regenerate": safe_to_regenerate,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "diff_rows": diff_rows,
            # Constants: this service compares recorded data. It fetches nothing.
            "live_fetch_performed": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def diff_invariant_failures(diff: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if diff.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "fabricated",
    ):
        if diff.get(constant) is not False:
            fails.append(f"diff_claimed:{constant}")

    for row in diff.get("diff_rows") or []:
        for field in DIFF_ROW_FIELDS:
            if field not in row:
                fails.append(f"diff_row_missing_field:{field}")
        if row.get("change_class") not in CHANGE_CLASSES:
            fails.append("change_class_out_of_vocabulary")
        if row.get("evidence_status") not in EVIDENCE_STATUSES:
            fails.append("evidence_status_out_of_vocabulary")
        # A change nobody can name must not read as reviewed.
        if row.get("change_class") == "unexpected" and not row.get(
            "human_review_required"
        ):
            fails.append("unexpected_change_without_human_review")
        # An attributed change must say what attributed it.
        is_expected = (
            row.get("change_class") == "gate105_tribal_bridge_correction"
        )
        if is_expected and not row.get("expected_reason"):
            fails.append("expected_change_without_a_reason")

    # safe_to_regenerate must agree with the measurements it claims to summarise.
    expected_safe = (
        not diff.get("blocked_reasons")
        and diff.get("unexpected_change_count") == 0
        and diff.get("preexisting_drift_count") == 0
        and not diff.get("positives_removed")
        and diff.get("fabricated_eligibility_risk") is False
    )
    if diff.get("safe_to_regenerate") is not expected_safe:
        fails.append("safe_to_regenerate_disagrees_with_the_measurements")

    # A refusal must name itself.
    if diff.get("safe_to_regenerate") is False and not diff.get("blocked_reasons"):
        fails.append("regeneration_refused_without_a_reason")

    # Fabrication risk can never coexist with permission.
    if diff.get("fabricated_eligibility_risk") and diff.get("safe_to_regenerate"):
        fails.append("fabrication_risk_permitted_regeneration")

    return fails
