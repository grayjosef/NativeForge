"""Project Gate 167 canonical graph into Gates 173–175 persisted intelligence."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.eligibility_intelligence_repository_service import (
    load_current_requirements,
    write_matches,
    write_requirements,
)
from nativeforge.services.eligibility_match_engine_service import match_eligibility
from nativeforge.services.eligibility_requirement_model_service import (
    APPLICANT_TYPE,
    EXCLUSION,
    INCLUSION,
    build_requirement,
    expand_class_group,
)
from nativeforge.services.intelligence_sql_dialect_service import is_current_active_sql
from nativeforge.services.native_eligibility_code_classification_service import (
    DIRECT_TRIBAL_CODES,
    _clean_codes,
    classify_native_eligibility,
)
from nativeforge.services.native_relevance_candidate_service import (
    detect_candidate,
)
from nativeforge.services.native_relevance_classifier_service import (
    classify_relevance,
)
from nativeforge.services.native_relevance_evidence_service import (
    AGENCY_CONTEXT,
    APPLICANT_ELIGIBILITY,
    DERIVED,
    OBSERVED,
    SECTOR_ALIGNMENT,
    SOURCE_CONTEXT,
    build_evidence,
    evidence_invariant_failures,
)
from nativeforge.services.native_relevance_ontology_service import (
    BROADLY_ELIGIBLE_NATIVE_RELEVANT,
    NATIVE_ELIGIBLE,
    NATIVE_PRIORITY,
    NATIVE_SPECIFIC,
    ONTOLOGY_VERSION,
)
from nativeforge.services.native_relevance_repository_service import (
    ASSESSMENTS,
    write_assessments,
    write_evidence,
)
from nativeforge.services.organization_capability_profile_service import build_profile

SCHEMA_VERSION = "nf_canonical_intelligence_projection_v1"

GRANTS_GOV_SOURCE = "nf-seed-2026-api-grants-gov-search2"
NATIVE_SERVING_SOURCES: frozenset[str] = frozenset({GRANTS_GOV_SOURCE})

FIELD_TO_EVIDENCE: dict[str, str] = {
    "funder_agency_name": AGENCY_CONTEXT,
    "funder_agency_code": AGENCY_CONTEXT,
    "assistance_listings": SECTOR_ALIGNMENT,
    "eligibility_text": APPLICANT_ELIGIBILITY,
    "eligible_applicant_codes": APPLICANT_ELIGIBILITY,
}

PROVENANCE = "nf_opportunity_field_provenance"
CANONICAL = "nf_canonical_opportunities"


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def resolve_canonical_id_for_spark(
    connection: sa.engine.Connection,
    *,
    source_record_id: str,
    opportunity_number: str | None,
    source_id: str = GRANTS_GOV_SOURCE,
) -> str | None:
    rid = str(source_record_id or "").strip()
    if rid:
        row = connection.execute(
            sa.text(
                f"""
                SELECT DISTINCT p.canonical_id FROM {PROVENANCE} p
                JOIN nf_opportunity_source_observations o
                  ON o.observation_id = p.observation_id
                WHERE o.source_id = :sid AND p.field_name = 'source_record_id'
                  AND p.field_value = :rid
                LIMIT 1
                """
            ),
            {"sid": source_id, "rid": rid},
        ).fetchone()
        if row:
            return str(row[0])
    num = str(opportunity_number or "").strip()
    if num:
        row = connection.execute(
            sa.text(
                f"""
                SELECT DISTINCT p.canonical_id FROM {PROVENANCE} p
                WHERE p.field_name = 'opportunity_number' AND p.field_value = :num
                LIMIT 1
                """
            ),
            {"num": num},
        ).fetchone()
        if row:
            return str(row[0])
    return None


def _load_provenance_rows(
    connection: sa.engine.Connection, *, canonical_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        sa.text(
            f"""
            SELECT field_name, field_value, source_id, raw_payload_sha256,
                   observation_id, version_id, is_current_canonical
            FROM {PROVENANCE}
            WHERE canonical_id = :cid
            """
        ),
        {"cid": canonical_id},
    ).fetchall()
    return [
        {
            "field_name": str(r[0]),
            "field_value": r[1],
            "source_id": str(r[2] or ""),
            "raw_payload_sha256": r[3],
            "observation_id": r[4],
            "version_id": r[5],
            "is_current_canonical": r[6],
        }
        for r in rows
    ]


def _current_field_map(provenance_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer current canonical provenance values for structured candidate inputs."""
    current: dict[str, Any] = {}
    fallback: dict[str, Any] = {}
    for row in provenance_rows:
        name = str(row.get("field_name") or "")
        if not name:
            continue
        fallback[name] = row.get("field_value")
        if row.get("is_current_canonical") in (True, 1, "1", "true"):
            current[name] = row.get("field_value")
    return current or fallback


def _supports_classes_for_applicant_codes(raw: Any) -> list[str]:
    codes = _clean_codes(raw)
    if not codes:
        return []
    band = str(
        classify_native_eligibility(eligible_applicant_codes=codes).get("confidence")
        or ""
    )
    if band == "direct":
        return [NATIVE_ELIGIBLE, NATIVE_SPECIFIC, NATIVE_PRIORITY]
    if band == "requires_reading":
        return [BROADLY_ELIGIBLE_NATIVE_RELEVANT]
    return []


def _is_current_provenance(row: dict[str, Any]) -> bool:
    return row.get("is_current_canonical") in (True, 1, "1", "true")


def _provenance_rows_for_projection(
    provenance_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One row per field_name, preferring current canonical provenance."""
    by_field: dict[str, dict[str, Any]] = {}
    for row in provenance_rows:
        name = str(row.get("field_name") or "")
        if not name:
            continue
        if _is_current_provenance(row):
            by_field[name] = row
        elif name not in by_field:
            by_field[name] = row
    return list(by_field.values())


def _build_evidence_items(
    *,
    canonical_id: str,
    provenance_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    items: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    failures: list[str] = []
    active_rows = _provenance_rows_for_projection(provenance_rows)
    for row in active_rows:
        source_ids.add(row["source_id"])
        kind = FIELD_TO_EVIDENCE.get(row["field_name"])
        if not kind or not row["field_value"]:
            continue
        confidence = OBSERVED if kind == APPLICANT_ELIGIBILITY else DERIVED
        supports: list[str] = []
        if row["field_name"] == "eligible_applicant_codes":
            supports = _supports_classes_for_applicant_codes(row["field_value"])
        item = build_evidence(
            canonical_id=canonical_id,
            evidence_type=kind,
            source_id=row["source_id"],
            raw_payload_sha256=row["raw_payload_sha256"],
            evidence_value=row["field_value"],
            confidence_class=confidence,
            field_name=row["field_name"],
            observation_id=row["observation_id"],
            version_id=row["version_id"],
            ontology_version=ONTOLOGY_VERSION,
            supports_classes=supports or None,
        )
        failures.extend(evidence_invariant_failures(item))
        items.append(item)
    native_serving = bool(source_ids & NATIVE_SERVING_SOURCES)
    if native_serving:
        payload = next(
            (
                r["raw_payload_sha256"]
                for r in provenance_rows
                if r["raw_payload_sha256"]
            ),
            None,
        )
        item = build_evidence(
            canonical_id=canonical_id,
            evidence_type=SOURCE_CONTEXT,
            source_id=sorted(source_ids & NATIVE_SERVING_SOURCES)[0],
            raw_payload_sha256=payload,
            evidence_value="publisher is a Native-serving federal source",
            confidence_class=DERIVED,
            ontology_version=ONTOLOGY_VERSION,
        )
        failures.extend(evidence_invariant_failures(item))
        items.append(item)
    return items, failures


def _requirements_from_evidence(
    *,
    canonical_id: str,
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for item in evidence_items:
        if str(item.get("evidence_type")) != APPLICANT_ELIGIBILITY:
            continue
        value = item.get("evidence_value")
        field_name = str(item.get("field_name") or "")
        codes = (
            _clean_codes(value)
            if field_name == "eligible_applicant_codes"
            else []
        )
        classification = (
            classify_native_eligibility(eligible_applicant_codes=codes)
            if codes
            else None
        )
        if classification and classification.get("grants_gov_direct_codes"):
            for code in classification["grants_gov_direct_codes"]:
                label = DIRECT_TRIBAL_CODES.get(code, code)
                classes = expand_class_group("indian_tribes") or ["tribal_government"]
                requirements.append(
                    build_requirement(
                        canonical_id=canonical_id,
                        requirement_kind=APPLICANT_TYPE,
                        normalized_value=classes,
                        original_text=label,
                        polarity=INCLUSION,
                        applies_to_entity_classes=classes,
                        evidence_ids=[str(item["evidence_id"])],
                        source_id=item.get("source_id"),
                        raw_payload_sha256=item.get("raw_payload_sha256"),
                    )
                )
        text = str(value or "").strip()
        if text and len(text) > 40 and not codes:
            if "not eligible" in text.lower() and "trib" in text.lower():
                requirements.append(
                    build_requirement(
                        canonical_id=canonical_id,
                        requirement_kind=APPLICANT_TYPE,
                        normalized_value=["tribal_government"],
                        original_text=text[:2000],
                        polarity=EXCLUSION,
                        applies_to_entity_classes=["tribal_government"],
                        evidence_ids=[str(item["evidence_id"])],
                        source_id=item.get("source_id"),
                        raw_payload_sha256=item.get("raw_payload_sha256"),
                    )
                )
    return requirements


def _projection_fingerprint(
    *,
    assessment: dict[str, Any],
    evidence_ids: list[str],
) -> str:
    payload = {
        "ontology": assessment.get("ontology_version") or ONTOLOGY_VERSION,
        "class": assessment.get("relevance_class"),
        "confidence": assessment.get("confidence"),
        "candidate": assessment.get("candidate_state"),
        "evidence_ids": sorted(evidence_ids),
    }
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _evidence_material_key(item: dict[str, Any]) -> str:
    value = item.get("evidence_value")
    if isinstance(value, (list, dict)):
        val_digest = hashlib.sha256(_json(value).encode()).hexdigest()[:16]
    else:
        val_digest = hashlib.sha256(str(value or "").encode()).hexdigest()[:16]
    supports = ",".join(sorted(str(s) for s in (item.get("supports_classes") or [])))
    return "|".join(
        [
            str(item.get("field_name") or ""),
            str(item.get("evidence_type") or ""),
            str(item.get("confidence_class") or ""),
            val_digest,
            str(item.get("observation_id") or ""),
            str(item.get("version_id") or ""),
            supports,
        ]
    )


def _gate173_material_input_fingerprint(
    *,
    field_map: dict[str, Any],
    candidate: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> str:
    """Hash Gate 173 inputs only — outputs must not suppress reassessment."""
    elig = str(field_map.get("eligibility_text") or "")
    payload = {
        "ontology": ONTOLOGY_VERSION,
        "eligible_applicant_codes": sorted(_clean_codes(field_map.get("eligible_applicant_codes"))),
        "eligibility_text_sha256": hashlib.sha256(elig.encode()).hexdigest(),
        "candidate_signals": sorted(candidate.get("signal_names") or []),
        "evidence_material": sorted(_evidence_material_key(i) for i in evidence_items),
    }
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _current_assessment_fingerprint(
    connection: sa.engine.Connection, *, canonical_id: str
) -> str | None:
    row = connection.execute(
        sa.text(
            f"SELECT reasons_json FROM {ASSESSMENTS} "
            f"WHERE canonical_id = :cid AND {is_current_active_sql(connection)}"
        ),
        {"cid": canonical_id},
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        reasons = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    if isinstance(reasons, dict):
        stored = str(reasons.get("input_fingerprint") or "").strip()
        if stored:
            return stored
        # Legacy rows used output-only fingerprints; treat as stale once.
        return None
    return None


def project_canonical_opportunity(
    connection: sa.engine.Connection,
    *,
    canonical_id: str,
    now: dt.datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    stamp = now or dt.datetime.now(dt.UTC)
    provenance_rows = _load_provenance_rows(connection, canonical_id=canonical_id)
    field_map = _current_field_map(provenance_rows)
    evidence_items, ev_failures = _build_evidence_items(
        canonical_id=canonical_id, provenance_rows=provenance_rows
    )
    source_ids = {r["source_id"] for r in provenance_rows if r.get("source_id")}
    candidate = detect_candidate(
        canonical_id=canonical_id,
        eligible_applicant_codes=_clean_codes(field_map.get("eligible_applicant_codes"))
        or field_map.get("eligible_applicant_codes"),
        additional_eligibility_text=field_map.get("eligibility_text"),
        source_is_native_serving=bool(source_ids & NATIVE_SERVING_SOURCES),
        evidence_items=evidence_items,
    )
    assessment = classify_relevance(
        canonical_id=canonical_id,
        candidate=candidate,
        evidence_items=evidence_items,
        computed_at=stamp,
    )
    evidence_ids = [str(i["evidence_id"]) for i in evidence_items]
    input_fingerprint = _gate173_material_input_fingerprint(
        field_map=field_map,
        candidate=candidate,
        evidence_items=evidence_items,
    )
    output_fingerprint = _projection_fingerprint(
        assessment=assessment, evidence_ids=evidence_ids
    )
    prior = _current_assessment_fingerprint(connection, canonical_id=canonical_id)
    skipped = prior == input_fingerprint and bool(prior)
    human_reasons = assessment.get("reasons") or []
    assessment["reasons"] = {
        "input_fingerprint": input_fingerprint,
        "projection_fingerprint": output_fingerprint,
        "items": human_reasons,
    }
    assessment["candidate_state"] = candidate.get("candidate_state")
    requirements = _requirements_from_evidence(
        canonical_id=canonical_id, evidence_items=evidence_items
    )
    if not dry_run and not skipped:
        write_evidence(connection, items=evidence_items, now=stamp)
        write_assessments(connection, assessments=[assessment], now=stamp)
        if requirements:
            write_requirements(connection, requirements=requirements, now=stamp)
    return {
        "canonical_id": canonical_id,
        "skipped_unchanged": skipped,
        "evidence_count": len(evidence_items),
        "relevance_class": assessment.get("relevance_class"),
        "confidence": assessment.get("confidence"),
        "review_required": assessment.get("review_required"),
        "requirement_count": len(requirements),
        "evidence_invariant_failures": sorted(set(ev_failures)),
        "dry_run": dry_run,
    }


def project_all_canonical_opportunities(
    connection: sa.engine.Connection,
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    sql = f"SELECT canonical_id FROM {CANONICAL} ORDER BY canonical_id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = connection.execute(sa.text(sql)).fetchall()
    results = [
        project_canonical_opportunity(
            connection, canonical_id=str(r[0]), dry_run=dry_run
        )
        for r in rows
        if str(r[0]) != "L1:"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "projected_count": len(results),
        "skipped_count": sum(1 for r in results if r["skipped_unchanged"]),
        "dry_run": dry_run,
        "results_sample": results[:5],
    }


def match_tenant_for_canonical(
    connection: sa.engine.Connection,
    *,
    canonical_id: str,
    organization_id: str,
    tenant_id: str,
    profile_facts: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    requirements = load_current_requirements(connection, canonical_id=canonical_id)
    profile = build_profile(
        organization_id=organization_id,
        facts=profile_facts or {"entity_class": "tribal_government"},
    )
    match = match_eligibility(
        canonical_id=canonical_id,
        requirements=requirements,
        profile=profile,
        tenant_id=tenant_id,
    )
    if not dry_run:
        from nativeforge.services.eligibility_intelligence_repository_service import (
            write_capability_profile,
        )

        profile_row = {
            **profile,
            "profile_id": hashlib.sha256(
                f"{organization_id}|{profile['profile_version']}".encode()
            ).hexdigest(),
            "fields": profile.get("fields") or {},
        }
        write_capability_profile(connection, profile=profile_row)
        match_id = hashlib.sha256(
            f"{canonical_id}|{tenant_id}|{profile['profile_version']}|{match['evaluated_at']}".encode()
        ).hexdigest()
        write_matches(
            connection,
            matches=[
                {
                    "match_id": match_id,
                    "canonical_id": canonical_id,
                    "tenant_id": tenant_id,
                    "organization_id": organization_id,
                    "profile_version": profile["profile_version"],
                    "eligibility_result": match["eligibility_result"],
                    "reason": match["reason"],
                    "satisfied_count": len(match.get("satisfied_requirements") or []),
                    "unsatisfied_count": len(
                        match.get("unsatisfied_requirements") or []
                    ),
                    "unknown_count": len(match.get("unknown_requirements") or []),
                    "review_count": len(match.get("review_required_items") or []),
                    "applied_exclusion_count": len(
                        match.get("applied_exclusions") or []
                    ),
                    "requirement_count": match.get("requirement_count") or 0,
                    "conditions_to_obtain": match.get("conditions_to_obtain") or [],
                    "review_required": bool(match.get("review_reasons")),
                    "evaluated_at": match.get("evaluated_at"),
                }
            ],
        )
    return match


def reevaluate_tenant_matches_for_organization(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    tenant_id: str,
    profile_facts: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    rows = connection.execute(
        sa.text(
            "SELECT DISTINCT canonical_id FROM nf_tenant_eligibility_matches "
            f"WHERE organization_id = :oid AND {is_current_active_sql(connection)}"
        ),
        {"oid": organization_id},
    ).fetchall()
    if not rows:
        canon = connection.execute(
            sa.text(f"SELECT canonical_id FROM {CANONICAL} LIMIT 3")
        ).fetchall()
        rows = canon
    outcomes = [
        match_tenant_for_canonical(
            connection,
            canonical_id=str(r[0]),
            organization_id=organization_id,
            tenant_id=tenant_id,
            profile_facts=profile_facts,
            dry_run=dry_run,
        )
        for r in rows
        if str(r[0]) != "L1:"
    ]
    return {
        "organization_id": organization_id,
        "reevaluated": len(outcomes),
        "results": [
            {
                "canonical_id": o.get("canonical_id"),
                "eligibility_result": o.get("eligibility_result"),
            }
            for o in outcomes[:10]
        ],
    }
