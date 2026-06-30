"""LA block: idempotent scaled federal corpus persist + dedup bridge."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import (
    load_seed_candidate,
)
from nativeforge.services.no_live_nofo_state_service import build_no_live_nofo_grant
from nativeforge.services.real_grants_corpus_loader_service import (
    CORPUS_PATH as NF13_CORPUS_PATH,
)

SCHEMA_VERSION = "nf_scaled_federal_corpus_persist_v1"
SCALED_CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "la_scaled_federal_grants.json"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_grant_dedup_key(grant: dict[str, Any]) -> str:
    gg_id = grant.get("grants_gov_opportunity_id")
    if gg_id is not None and str(gg_id).strip():
        return f"grants_gov:{gg_id}"
    seed_id = str(grant.get("source_seed_id") or "")
    opp_num = str(grant.get("opportunity_number") or "")
    if seed_id and opp_num:
        return f"seed:{seed_id}|opp:{opp_num}"
    return str(grant.get("grant_id") or "")


def payload_to_grant_record(
    payload: dict[str, Any],
    *,
    source: dict[str, Any],
) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or payload.get("source_seed_id") or "")
    fed_suffix = seed_id.rsplit("-", 1)[-1] if seed_id else "unknown"
    grant_id = f"la-real-{fed_suffix}"
    return _json_safe(
        {
            "grant_id": grant_id,
            "source_seed_id": seed_id,
            "opportunity_number": payload.get("opportunity_number"),
            "opportunity_title": payload.get("opportunity_title"),
            "agency": payload.get("agency"),
            "eligibility_text": payload.get("eligibility_text"),
            "synopsis": payload.get("synopsis"),
            "tribal_eligible": payload.get("tribal_eligible"),
            "applicant_type_ids": payload.get("applicant_type_ids") or [],
            "applicant_types_json": payload.get("applicant_types_json") or [],
            "applicant_types_include_tribal": payload.get("tribal_eligible"),
            "application_deadline": payload.get("application_deadline"),
            "grants_gov_opportunity_id": payload.get("grants_gov_opportunity_id"),
            "real_fetch": payload.get("real_fetch") is True,
            "fetch_mode": payload.get("fetch_mode"),
            "fixture": payload.get("fixture") is True,
            "search_live": payload.get("search_live"),
            "detail_live": payload.get("detail_live"),
            "never_synthesized": True,
            "source_url": payload.get("source_url") or source.get("source_url"),
            "ingested_at": datetime.now(tz=UTC).isoformat(),
            "provenance": {
                "batch_block": "la_scale_federal",
                "source_seed_id": seed_id,
                "grants_gov_opportunity_id": payload.get("grants_gov_opportunity_id"),
            },
        }
    )


def _placeholder_grant_for_seed(source: dict[str, Any]) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or "")
    fed_suffix = seed_id.rsplit("-", 1)[-1]
    return {
        "grant_id": f"la-real-{fed_suffix}",
        "source_seed_id": seed_id,
        "opportunity_number": f"FED-{fed_suffix.upper()}",
        "opportunity_title": str(source.get("source_name") or ""),
        "agency": "",
        "eligibility_text": "",
    }


def load_scaled_federal_corpus(*, path: Path | None = None) -> list[dict[str, Any]]:
    corpus_path = path or SCALED_CORPUS_PATH
    if corpus_path.is_file():
        raw = json.loads(corpus_path.read_text(encoding="utf-8"))
        return list(raw.get("grants") or [])
    if NF13_CORPUS_PATH.is_file():
        raw = json.loads(NF13_CORPUS_PATH.read_text(encoding="utf-8"))
        return list(raw.get("grants") or [])
    return []


def persist_batch_fetch_to_scaled_corpus(
    batch_fetch: dict[str, Any],
    *,
    corpus_path: Path | None = None,
) -> dict[str, Any]:
    """Merge batch live fetch into scaled corpus; skip-on-reingest by dedup key."""
    target = corpus_path or SCALED_CORPUS_PATH
    existing = load_scaled_federal_corpus(path=target)
    by_key: dict[str, dict[str, Any]] = {}
    for grant in existing:
        by_key[build_grant_dedup_key(grant)] = grant

    inserted = 0
    updated = 0
    skipped = 0
    no_live_nofo_count = 0

    per_source = list(batch_fetch.get("per_source") or [])
    payloads_by_seed: dict[str, list[dict[str, Any]]] = {}
    for payload in batch_fetch.get("raw_payloads") or []:
        sid = str(payload.get("source_seed_id") or "")
        payloads_by_seed.setdefault(sid, []).append(payload)

    for row in per_source:
        seed_id = str(row.get("seed_id") or "")
        source = load_seed_candidate(seed_id)
        payloads = payloads_by_seed.get(seed_id) or []
        if not payloads:
            placeholder = _placeholder_grant_for_seed(source)
            nofo_grant = build_no_live_nofo_grant(
                placeholder,
                source,
                diagnosis="no_live_nofo:batch_empty_fetch",
            )
            key = build_grant_dedup_key(nofo_grant)
            if key in by_key:
                skipped += 1
                continue
            by_key[key] = nofo_grant
            inserted += 1
            no_live_nofo_count += 1
            continue
        for payload in payloads:
            grant = payload_to_grant_record(payload, source=source)
            key = build_grant_dedup_key(grant)
            if key in by_key:
                skipped += 1
                continue
            by_key[key] = grant
            inserted += 1

    merged = list(by_key.values())
    merged.sort(key=lambda g: str(g.get("grant_id") or ""))
    artifact = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(merged),
            "grants": merged,
            "updated_at": datetime.now(tz=UTC).isoformat(),
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "corpus_path": str(target),
            "grant_count": len(merged),
            "inserted_count": inserted,
            "updated_count": updated,
            "skipped_duplicate_count": skipped,
            "no_live_nofo_count": no_live_nofo_count,
            "dedupe_keys": len(by_key),
        }
    )
