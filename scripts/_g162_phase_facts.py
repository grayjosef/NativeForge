"""Gate 162 verifier phase: the fact model and the guard input mapping.

Proves claims 1, 12-18 and 20. No database writes.

Claims 15-18 are the ones worth having: each asserts that a thing which LOOKS
like progress authorizes nothing. An adapter existing, a source being in the
registry, a job sitting in a queue and a hermetic execution proof are all real
and none of them is permission.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.services.live_network_guard_service import (  # noqa: E402
    build_live_network_decision,
)
from nativeforge.services.source_authorization_fact_model_service import (  # noqa: E402,E501
    DECISION_FACTS,
    FACT_NAMES,
    FACT_STATUSES,
    PERMITTING_FACT_STATUSES,
    describe_fact_model,
)
from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E402,E501
    AUTHORIZING_STRENGTHS,
    STRENGTH_BY_FACT,
    resolve_source_authorization_facts,
)
from nativeforge.services.source_runtime_readiness_fact_service import (  # noqa: E402,E501
    LANE_NAMES,
    REQUIRED_FOR_COLLECTION,
    build_runtime_readiness_facts,
    runtime_readiness_invariant_failures,
)

out: dict[str, object] = {}
detail: list[str] = []

model = describe_fact_model()

# ---- 1. the model covers every guard status input ---------------------
guard_params = set(inspect.signature(build_live_network_decision).parameters)
guard_status_inputs = {p for p in guard_params if p.endswith("_status")}
mapped = {spec["guard_input"] for spec in model["facts"] if spec.get("guard_input")}
out["every_guard_status_input_is_modelled"] = bool(guard_status_inputs <= mapped)
if not guard_status_inputs <= mapped:
    detail.append(f"unmapped guard inputs: {sorted(guard_status_inputs - mapped)}")

out["fact_count_is_eleven"] = bool(len(FACT_NAMES) == 11)
out["exactly_one_status_permits"] = bool(len(PERMITTING_FACT_STATUSES) == 1)
out["six_fact_statuses_exist"] = bool(len(FACT_STATUSES) == 6)

# ---- missing is not denied -------------------------------------------
out["missing_is_distinct_from_denied"] = bool(
    "missing" in FACT_STATUSES
    and "denied" in FACT_STATUSES
    and "missing" not in PERMITTING_FACT_STATUSES
    and "denied" not in PERMITTING_FACT_STATUSES
)

# ---- 12/13. runtime facts derive from Gates 156-161 -------------------
runtime = build_runtime_readiness_facts()
out["runtime_lanes_are_the_six_gates"] = bool(len(LANE_NAMES) == 6)
out["runtime_invariants_clean"] = not runtime_readiness_invariant_failures(runtime)
out["runtime_authorizes_nothing"] = bool(runtime["authorizes_nothing"])

# The repair: the derivation no longer READS Gate 98E's third-party detector.
#
# Parsed, not searched. The first version of this check asked whether the
# string appeared in the source and failed on the module's own docstring
# explaining that it no longer reads that field - matching the sentence saying
# it must not, which is this campaign's oldest defect.
#
# A field is READ when its name is a subscript key or a `.get()` argument. A
# field named in prose is prose.
runtime_module = sys.modules[build_runtime_readiness_facts.__module__]
runtime_tree = ast.parse(inspect.getsource(runtime_module))


def _field_names_read(tree: ast.AST) -> set[str]:
    """String keys this code actually looks up."""
    read: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if isinstance(node.slice.value, str):
                read.add(node.slice.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            read.add(node.args[0].value)
    return read


fields_read = _field_names_read(runtime_tree)
out["runtime_derivation_does_not_read_background_worker_available"] = bool(
    "background_worker_available" not in fields_read
)
if "background_worker_available" in fields_read:
    detail.append("the runtime derivation still reads background_worker_available")

# And the lanes it DOES name, from the declared tuple rather than from text.
out["runtime_derivation_names_its_lanes"] = bool(
    set(REQUIRED_FOR_COLLECTION) <= set(LANE_NAMES)
)

# Every not-ready lane names a reason.
bare_no = [
    name
    for name, lane in (runtime.get("lanes") or {}).items()
    if lane.get("status") != "ready"
    and not (lane.get("conditions_not_met") or lane.get("why"))
]
out["no_lane_refuses_without_saying_why"] = not bare_no
if bare_no:
    detail.append(f"bare refusals: {bare_no}")

# ---- 14-18. things that look like progress and authorize nothing ------
#
# Asserted structurally: only `recorded_decision` strength can authorize, and
# each of these is a different strength.
out["runtime_readiness_alone_does_not_authorize"] = bool(
    STRENGTH_BY_FACT["runtime_status"] not in AUTHORIZING_STRENGTHS
)
out["registry_existence_alone_does_not_authorize"] = bool(
    STRENGTH_BY_FACT["source_registered"] not in AUTHORIZING_STRENGTHS
)
out["collector_existence_alone_does_not_authorize"] = bool(
    STRENGTH_BY_FACT["collector_status"] not in AUTHORIZING_STRENGTHS
)
out["only_recorded_decisions_authorize"] = bool(
    AUTHORIZING_STRENGTHS == frozenset({"recorded_decision"})
)
out["the_three_decision_facts_are_the_authorizing_ones"] = bool(
    {
        name
        for name, strength in STRENGTH_BY_FACT.items()
        if strength in AUTHORIZING_STRENGTHS
    }
    == set(DECISION_FACTS) | {"attribution_status"}
)

# A queued job and an execution proof are not facts in this model AT ALL,
# which is the strongest possible form of "they do not authorize".
out["a_queued_job_is_not_an_authorization_fact"] = bool(
    not any("job" in name for name in FACT_NAMES)
)
out["an_execution_proof_is_not_an_authorization_fact"] = bool(
    not any("proof" in name or "execution" in name for name in FACT_NAMES)
)

# ---- 19/20. the resolver takes no fact -------------------------------
resolver_params = list(inspect.signature(resolve_source_authorization_facts).parameters)
# Named, not counted: a count passes after a rename. Gate 163 added
# `exercise_runtime`, which selects HOW `runtime_status` is measured -
# exercise the lanes, or observe them cold - and cannot change WHAT the
# measurement returns. That is proven behaviourally in
# `_g163_phase_runtime_falsifiability.py`: with `exercise_runtime=True` and a
# required table dropped, runtime_status is still not_ready. Choosing a
# measurement is not asserting a result.
out["resolver_parameters_are_the_permitted_set"] = bool(
    sorted(resolver_params)
    == [
        "connection",
        "exercise_runtime",
        "now",
        "organization_id",
        "source_id",
    ]
)
FACT_SHAPED = ("status", "approved", "allow", "permit", "override", "fact")
suspicious = [
    p for p in resolver_params if any(word in p.lower() for word in FACT_SHAPED)
]
out["no_resolver_parameter_is_fact_shaped"] = not suspicious
if suspicious:
    detail.append(f"fact-shaped resolver params: {suspicious}")

for key in (
    "every_guard_status_input_is_modelled",
    "fact_count_is_eleven",
    "exactly_one_status_permits",
    "six_fact_statuses_exist",
    "missing_is_distinct_from_denied",
    "runtime_lanes_are_the_six_gates",
    "runtime_invariants_clean",
    "runtime_authorizes_nothing",
    "runtime_derivation_does_not_read_background_worker_available",
    "runtime_derivation_names_its_lanes",
    "no_lane_refuses_without_saying_why",
    "runtime_readiness_alone_does_not_authorize",
    "registry_existence_alone_does_not_authorize",
    "collector_existence_alone_does_not_authorize",
    "only_recorded_decisions_authorize",
    "the_three_decision_facts_are_the_authorizing_ones",
    "a_queued_job_is_not_an_authorization_fact",
    "an_execution_proof_is_not_an_authorization_fact",
    "resolver_parameters_are_the_permitted_set",
    "no_resolver_parameter_is_fact_shaped",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
