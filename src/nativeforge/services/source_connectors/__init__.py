"""Source connector shells (offline-only in Sprint 22)."""

from nativeforge.services.source_connectors.base import (
    ConnectorDryRunResult,
    ConnectorRunContext,
    ConnectorSourceConfig,
    NormalizedOpportunityCandidate,
    RawOpportunityPayload,
)
from nativeforge.services.source_connectors.intake_bridge import (
    IntakeBridgeFixtureError,
    static_fixture_connector_intake_dry_run,
)
from nativeforge.services.source_connectors.native_relevance import (
    NativeRelevanceInput,
    assess_native_relevance,
)
from nativeforge.services.source_connectors.normalization import (
    build_native_relevance_input,
    normalize_raw_dict,
    to_discovery_intake_candidate_payload,
)
from nativeforge.services.source_connectors.static_fixture_connector import (
    dry_run_fixture_rows,
)

__all__ = [
    "ConnectorDryRunResult",
    "ConnectorRunContext",
    "ConnectorSourceConfig",
    "NormalizedOpportunityCandidate",
    "RawOpportunityPayload",
    "NativeRelevanceInput",
    "assess_native_relevance",
    "build_native_relevance_input",
    "dry_run_fixture_rows",
    "IntakeBridgeFixtureError",
    "normalize_raw_dict",
    "static_fixture_connector_intake_dry_run",
    "to_discovery_intake_candidate_payload",
]
