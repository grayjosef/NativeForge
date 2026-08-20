"""South Carolina reference-state source adapter/config (offline, curated-current).

SC is the reference state implementation — not a product fork and not live ingest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_sc_state_source_adapter_config_v1"
DEFAULT_CONFIG_PATH = Path(
    "fixtures/opportunity_engine/sc_state_source_adapter_config.json"
)

SC_ADAPTER_KEY = "state_portal_sc_curated"
STATE_CODE = "SC"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_sc_state_source_adapter_config() -> dict[str, Any]:
    """Config-only SC adapter: public listings / curated packs; activation required for live."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_key": SC_ADAPTER_KEY,
            "state_code": STATE_CODE,
            "display_name": "South Carolina (reference state)",
            "source_layer": "sc_state",
            "is_reference_state_implementation": True,
            "product_fork": False,
            "nationwide_hardcoded_in_ui": False,
            "public_listings_only": True,
            "requires_operator_activation": True,
            "no_credentials": True,
            "live_ingest_claimed": False,
            "live_ingest_implemented": False,
            "data_mode_default": "curated_current",
            "retrieval_method_default": "curated_pack_offline_normalize_v1",
            "source_health_default": "curated_offline",
            "opportunity_pack_paths": [
                "fixtures/sc_monday_demo/sc_state_curated_current_opportunity_pack.json",
                "fixtures/sc_monday_demo/sc_curated_current_opportunity_pack.json",
            ],
            "combined_with_federal_required": True,
            "organization_geography_must_not_filter_federal": True,
            "upgrade_path": (
                "Future live SC portal connector requires Mayhem approval, "
                "validated public-listings capture, and honest live_ingest labeling"
            ),
            "notes": [
                "SC is reference-state architecture for additional states",
                "UI must consume adapter/config — not hard-code nationwide behavior",
                "Curated-current only in Campaign Block 01",
            ],
        }
    )


def write_sc_state_source_adapter_config(
    config: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = config if config is not None else build_sc_state_source_adapter_config()
    out = path or DEFAULT_CONFIG_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load_sc_state_source_adapter_config(
    *, require_file: bool = False
) -> dict[str, Any]:
    if DEFAULT_CONFIG_PATH.is_file():
        return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    if require_file:
        raise FileNotFoundError(DEFAULT_CONFIG_PATH)
    return build_sc_state_source_adapter_config()


def sc_state_adapter_invariant_failures(config: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if config.get("state_code") != "SC":
        fails.append("state_code")
    if config.get("is_reference_state_implementation") is not True:
        fails.append("not_reference")
    if config.get("product_fork") is True:
        fails.append("must_not_be_product_fork")
    if config.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if config.get("live_ingest_implemented") is True:
        fails.append("live_ingest_implemented_without_validation")
    if config.get("combined_with_federal_required") is not True:
        fails.append("must_combine_federal")
    if config.get("organization_geography_must_not_filter_federal") is not True:
        fails.append("must_not_filter_federal_by_org_geo")
    if config.get("nationwide_hardcoded_in_ui") is True:
        fails.append("nationwide_hardcoded")
    if config.get("data_mode_default") != "curated_current":
        fails.append("data_mode_default")
    return fails
