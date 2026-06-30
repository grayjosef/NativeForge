"""TA-3/4: Tier-3 foundation batch live pull orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.db.models import is_demo_for_org_type
from nativeforge.repositories import activation_state as activation_repo
from nativeforge.services.activation_publish_gate_service import (
    assert_live_publish_permitted,
)
from nativeforge.services.corrected_catalog_posture_report_service import (
    build_corrected_catalog_posture_report,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.source_fetch_adapter_contract_service import FetchMode
from nativeforge.services.tier3_foundation_batch_activation_service import (
    Tier3BatchConfirmationBody,
    activate_tier3_foundation_batch_human_gate,
    parse_tier3_batch_confirmation,
    select_tier3_foundation_batch_seed_ids,
)
from nativeforge.services.tier3_foundation_batch_live_fetch_service import (
    run_tier3_foundation_batch_live_fetch,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    persist_tier3_batch_to_corpus,
)
from nativeforge.services.tier3_org_cluster_config_service import TA3_COHORT_SEED_IDS

SCHEMA_VERSION = "nf_tier3_batch_live_pull_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_tier3_batch_publish_permitted(session: Any, *, org: Any) -> None:
    row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
    )
    assert_live_publish_permitted(row)


def run_tier3_foundation_batch_live_pull_block(
    session: Any,
    *,
    org: Any,
    org_id: uuid.UUID | None = None,
    operator_confirmation: dict[str, Any] | Tier3BatchConfirmationBody,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    fetch_mode: FetchMode = "live",
    fixture_by_domain: dict[str, str] | None = None,
    persist_corpus: bool = True,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    confirmation = parse_tier3_batch_confirmation(operator_confirmation)
    assert_tier3_batch_publish_permitted(session, org=org)
    posture = build_corrected_catalog_posture_report()
    seed_ids = select_tier3_foundation_batch_seed_ids(
        posture.get("posture_candidates")
    )
    activation = activate_tier3_foundation_batch_human_gate(
        session,
        org=org,
        operator_confirmation=confirmation,
        seed_ids=seed_ids,
    )
    batch_fetch = run_tier3_foundation_batch_live_fetch(
        seed_ids,
        fetch_mode=fetch_mode,
        fixture_by_domain=fixture_by_domain,
    )
    persist = (
        persist_tier3_batch_to_corpus(batch_fetch)
        if persist_corpus
        else {"persist_skipped": True}
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id or org.id),
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "cohort_seed_ids": list(TA3_COHORT_SEED_IDS),
            "activation": activation,
            "batch_fetch": batch_fetch,
            "persist": persist,
            "honest_labeling": True,
        }
    )
