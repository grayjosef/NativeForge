"""Sprint 293: plan gate for real-resolver validation + first tier-1 activation."""

from __future__ import annotations

import json
import os
from typing import Any

from nativeforge.services.source_ingestion_plan_gate_service import (
    build_plan_gate_contract,
    is_live_source_ingestion_plan_approved,
    require_plan_gate,
)
from nativeforge.services.staging_environment_guard_service import (
    build_staging_environment_contract,
    is_staging_environment,
    require_staging_not_production,
)

SCHEMA_VERSION = "nf_real_resolver_validation_gate_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_real_resolver_validation_plan_approved() -> bool:
    return os.environ.get(
        "NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", ""
    ).lower() in {"1", "true", "yes"}


def is_real_resolver_validation_approved(
    *,
    nf_live_source_ingestion: bool,
    nf_real_resolver_validation: bool,
) -> bool:
    return (
        is_staging_environment()
        and nf_live_source_ingestion
        and nf_real_resolver_validation
        and is_live_source_ingestion_plan_approved()
        and is_real_resolver_validation_plan_approved()
    )


def require_real_resolver_validation_gate(
    *,
    nf_live_source_ingestion: bool,
    nf_real_resolver_validation: bool,
) -> None:
    require_staging_not_production()
    require_plan_gate()
    if not is_real_resolver_validation_plan_approved():
        raise PermissionError(
            "NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED must be set"
        )
    if not nf_live_source_ingestion or not nf_real_resolver_validation:
        raise PermissionError(
            "nf_live_source_ingestion and nf_real_resolver_validation "
            "query flags required"
        )


def build_real_resolver_validation_gate_contract(
    *,
    nf_live_source_ingestion: bool = False,
    nf_real_resolver_validation: bool = False,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "staging_environment": build_staging_environment_contract(),
            "live_source_ingestion_plan_gate": build_plan_gate_contract(),
            "real_resolver_plan_approved": is_real_resolver_validation_plan_approved(),
            "env_flag": "NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED",
            "query_flags": {
                "nf_live_source_ingestion": nf_live_source_ingestion,
                "nf_real_resolver_validation": nf_real_resolver_validation,
            },
            "validation_approved": is_real_resolver_validation_approved(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "authorized_activation_seed_id": "nf-seed-2026-fed-001",
            "exactly_one_activation": True,
            "no_captcha_login_bypass": True,
            "no_credentials": True,
        }
    )
