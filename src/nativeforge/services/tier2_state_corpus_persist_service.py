"""T2-2: Tier-2 state portal corpus persist + mixed pool merge."""

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
from nativeforge.services.scaled_federal_corpus_persist_service import (
    build_grant_dedup_key,
    load_scaled_federal_corpus,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_tier3_foundation_corpus,
)

SCHEMA_VERSION = "nf_tier2_state_corpus_persist_v1"
TIER2_CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "ta_tier2_state_grants.json"
)
MIXED_CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "ta_mixed_tier13_grants.json"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def payload_to_tier2_grant_record(
    payload: dict[str, Any],
    *,
    source: dict[str, Any],
) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or payload.get("source_seed_id") or "")
    suffix = seed_id.rsplit("-", 1)[-1]
    slug = str(payload.get("opportunity_number") or "unknown")[-12:]
    grant_id = f"ta2-real-{suffix}-{slug}"
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
            "applicant_types_include_tribal": payload.get(
                "applicant_types_include_tribal"
            ),
            "application_deadline": payload.get("application_deadline"),
            "real_fetch": payload.get("real_fetch") is True,
            "fetch_mode": payload.get("fetch_mode"),
            "fixture": payload.get("fixture") is True,
            "never_synthesized": True,
            "source_url": payload.get("source_url") or source.get("source_url"),
            "state_code": payload.get("state_code"),
            "tier": 2,
            "requires_operator_review": True,
            "ingested_at": datetime.now(tz=UTC).isoformat(),
            "provenance": {
                "batch_block": "tier2_state_pilot",
                "source_seed_id": seed_id,
                "platform_adapter_key": payload.get("platform_adapter_key"),
                "adapter_key": payload.get("adapter_key"),
            },
        }
    )


def _placeholder_for_seed(source: dict[str, Any]) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or "")
    suffix = seed_id.rsplit("-", 1)[-1]
    return {
        "grant_id": f"ta2-real-{suffix}",
        "source_seed_id": seed_id,
        "opportunity_number": f"T2-{suffix.upper()}",
        "opportunity_title": str(source.get("source_name") or ""),
        "agency": "",
        "eligibility_text": "",
        "tier": 2,
    }


def load_tier2_state_corpus(*, path: Path | None = None) -> list[dict[str, Any]]:
    corpus_path = path or TIER2_CORPUS_PATH
    if not corpus_path.is_file():
        return []
    raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    return list(raw.get("grants") or [])


def load_mixed_tier123_corpus(*, path: Path | None = None) -> list[dict[str, Any]]:
    mixed_path = path or MIXED_CORPUS_PATH
    if mixed_path.is_file():
        raw = json.loads(mixed_path.read_text(encoding="utf-8"))
        return list(raw.get("grants") or [])
    federal = load_scaled_federal_corpus()
    if not federal and NF13_CORPUS_PATH.is_file():
        raw = json.loads(NF13_CORPUS_PATH.read_text(encoding="utf-8"))
        federal = list(raw.get("grants") or [])
    return federal + load_tier3_foundation_corpus() + load_tier2_state_corpus()


def persist_tier2_batch_to_corpus(
    batch_fetch: dict[str, Any],
    *,
    corpus_path: Path | None = None,
    mixed_path: Path | None = None,
) -> dict[str, Any]:
    target = corpus_path or TIER2_CORPUS_PATH
    existing = load_tier2_state_corpus(path=target)
    by_key: dict[str, dict[str, Any]] = {
        build_grant_dedup_key(g): g for g in existing
    }
    inserted = 0
    skipped = 0
    no_live_nofo_count = 0

    payloads_by_seed: dict[str, list[dict[str, Any]]] = {}
    for payload in batch_fetch.get("raw_payloads") or []:
        sid = str(payload.get("source_seed_id") or "")
        payloads_by_seed.setdefault(sid, []).append(payload)

    for row in batch_fetch.get("per_source") or []:
        seed_id = str(row.get("seed_id") or "")
        source = load_seed_candidate(seed_id)
        payloads = payloads_by_seed.get(seed_id) or []
        if not payloads:
            placeholder = _placeholder_for_seed(source)
            nofo = build_no_live_nofo_grant(
                placeholder,
                source,
                diagnosis="no_live_nofo:tier2_liaison_or_empty_portal",
            )
            nofo["tier"] = 2
            nofo["synopsis"] = (
                "State tribal affairs portal — no public grant listing at ingest "
                "(no_live_nofo)."
            )
            nofo["provenance"] = {
                "batch_block": "tier2_state_pilot",
                "source_seed_id": seed_id,
                "platform_adapter_key": row.get("platform_adapter_key"),
                "empty_honest": True,
            }
            key = build_grant_dedup_key(nofo)
            if key in by_key:
                skipped += 1
                continue
            by_key[key] = nofo
            inserted += 1
            no_live_nofo_count += 1
            continue
        for payload in payloads:
            grant = payload_to_tier2_grant_record(payload, source=source)
            key = build_grant_dedup_key(grant)
            if key in by_key:
                skipped += 1
                continue
            by_key[key] = grant
            inserted += 1

    merged = sorted(by_key.values(), key=lambda g: str(g.get("grant_id") or ""))
    before_mixed = 0
    mixed_target = mixed_path or MIXED_CORPUS_PATH
    if mixed_target.is_file():
        raw_mixed = json.loads(mixed_target.read_text(encoding="utf-8"))
        before_mixed = len(raw_mixed.get("grants") or [])
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "grant_count": len(merged),
        "grants": merged,
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    federal = load_scaled_federal_corpus()
    if not federal and NF13_CORPUS_PATH.is_file():
        raw = json.loads(NF13_CORPUS_PATH.read_text(encoding="utf-8"))
        federal = list(raw.get("grants") or [])
    tier3 = load_tier3_foundation_corpus()
    mixed = federal + tier3 + merged
    mixed_artifact = {
        "schema_version": "nf_ta_mixed_tier123_corpus_v1",
        "grant_count": len(mixed),
        "federal_grant_count": len(federal),
        "tier3_grant_count": len(tier3),
        "tier2_grant_count": len(merged),
        "grants": mixed,
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }
    mixed_target.write_text(
        json.dumps(mixed_artifact, indent=2) + "\n", encoding="utf-8"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tier2_corpus_path": str(target),
            "mixed_corpus_path": str(mixed_target),
            "tier2_grant_count": len(merged),
            "mixed_grant_count": len(mixed),
            "federal_baseline_count": len(federal),
            "tier3_baseline_count": len(tier3),
            "before_tier2_count": len(existing),
            "inserted_count": inserted,
            "skipped_duplicate_count": skipped,
            "no_live_nofo_count": no_live_nofo_count,
            "before_mixed_count": before_mixed,
            "after_mixed_count": len(mixed),
            "delta_mixed_count": len(mixed) - before_mixed,
        }
    )
