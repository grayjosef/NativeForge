"""Sprint 272: staging environment guard — dry-run paths fail closed outside staging."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.lib.settings import get_settings

SCHEMA_VERSION = "nf_staging_environment_guard_v1"

PRODUCTION_ENVS: frozenset[str] = frozenset({"production", "prod"})
STAGING_ENV = "staging"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def current_app_env() -> str:
    return get_settings().app_env.strip().lower()


def is_staging_environment() -> bool:
    return current_app_env() == STAGING_ENV


def is_production_environment() -> bool:
    return current_app_env() in PRODUCTION_ENVS


def require_staging_not_production() -> None:
    if is_production_environment():
        raise PermissionError(
            "staging activation dry-run blocked in production environment"
        )
    if not is_staging_environment():
        raise PermissionError(
            f"staging activation dry-run requires NF_APP_ENV={STAGING_ENV!r}"
        )


def build_staging_environment_contract() -> dict[str, Any]:
    env = current_app_env()
    dry_run_allowed = is_staging_environment() and not is_production_environment()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "app_env": env,
            "is_staging": is_staging_environment(),
            "is_production": is_production_environment(),
            "dry_run_allowed": dry_run_allowed,
            "staging_only": True,
            "never_production": not is_production_environment(),
        }
    )
