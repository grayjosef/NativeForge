"""Sprint 351: ingested opportunities must belong to the source's own program/agency."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_source_program_ownership_guard_v1"


class CrossProgramProxyError(ValueError):
    """Raised when an ingested opportunity belongs to a different program than its source."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalize_agency(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def _seed_parts(source: dict[str, Any]) -> tuple[str, str]:
    name = str(source.get("source_name") or "")
    if "—" in name:
        agency, program = name.split("—", 1)
    elif " - " in name:
        agency, program = name.split(" - ", 1)
    else:
        agency, program = name, ""
    return agency.strip(), program.strip()


def _agencies_align(seed_agency: str, grant_agency: str) -> bool:
    a = _normalize_agency(seed_agency)
    b = _normalize_agency(grant_agency)
    if not a or not b:
        return True
    return a in b or b in a or a.split("/")[0].strip() in b


def resolve_ingested_agency(*, source: dict[str, Any], payload_agency: str) -> str:
    """Prefer seed agency when Grants.gov detail returns a contact name."""
    seed_agency, _ = _seed_parts(source)
    agency = str(payload_agency or "").strip()
    if not agency:
        return seed_agency
    if seed_agency and not _agencies_align(seed_agency, agency):
        if "\n" in agency or not re.search(
            r"department|administration|service|bureau|agency|epa|bia|ihs|samhsa|hhs|interior",
            agency,
            re.IGNORECASE,
        ):
            return seed_agency
    return agency


def _program_tokens(program: str) -> set[str]:
    low = program.lower()
    tokens: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", low):
        if len(word) >= 3:
            tokens.add(word)
    if "gap" in low:
        tokens.add("gap")
    if "general assistance" in low:
        tokens.update({"general", "assistance", "gap"})
    return tokens


def assert_source_program_ownership(
    *,
    source: dict[str, Any],
    grant: dict[str, Any],
) -> None:
    """Fail closed on cross-program proxy substitution."""
    if grant.get("no_live_nofo") or grant.get("source_ingestion_state") == "no_live_nofo":
        return
    if grant.get("reingest_program_proxy"):
        raise CrossProgramProxyError(
            f"grant {grant.get('grant_id')!r} marked reingest_program_proxy"
        )

    seed_agency, seed_program = _seed_parts(source)
    grant_agency = str(grant.get("agency") or "")
    if not _agencies_align(seed_agency, grant_agency):
        raise CrossProgramProxyError(
            f"grant {grant.get('grant_id')!r} agency {grant_agency!r} "
            f"does not match source agency {seed_agency!r}"
        )

    title = str(grant.get("opportunity_title") or "").lower()
    program_tokens = _program_tokens(seed_program)
    if program_tokens:
        overlap = sum(1 for t in program_tokens if t in title)
        # SAMHSA AI/AN seed vs Tribal Behavioral Health Suicide — shared tribal/suicide domain
        tribal_behavioral_bridge = (
            "suicide" in program_tokens or "zero" in program_tokens or "ai/an" in seed_program.lower()
        ) and ("suicide" in title or "behavioral health" in title)
        gap_bridge = "gap" in program_tokens and "gap" in title
        if overlap == 0 and not tribal_behavioral_bridge and not gap_bridge:
            raise CrossProgramProxyError(
                f"grant {grant.get('grant_id')!r} title does not match source program "
                f"{seed_program!r}"
            )

    opp = str(grant.get("opportunity_number") or "")
    if "gap" in seed_program.lower() and opp.startswith("EPA-OW"):
        raise CrossProgramProxyError(
            f"grant {grant.get('grant_id')!r} holds EPA-OW NOFO under GAP source"
        )


def apply_source_program_ownership_guard(
    *,
    source: dict[str, Any],
    grant: dict[str, Any],
) -> dict[str, Any]:
    blocked = False
    reason: str | None = None
    try:
        assert_source_program_ownership(source=source, grant=grant)
    except CrossProgramProxyError as exc:
        blocked = True
        reason = str(exc)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_id": grant.get("grant_id"),
            "source_seed_id": source.get("seed_id"),
            "cross_program_proxy_blocked": blocked,
            "guard_reason": reason,
        }
    )


def build_source_program_ownership_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "no_cross_program_proxy": True,
            "no_live_nofo_exempt": True,
            "preview_only": True,
        }
    )
