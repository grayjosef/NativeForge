"""Gate 83B — deterministic demo payload generation.

The committed SC demo payload now carries customer-facing eligibility content,
so it has to be reproducible from its inputs: a diff of that file must show what
a change actually did.
"""

from __future__ import annotations

import json
import subprocess
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nativeforge.services.demo_payload_determinism_service import (
    ACCUMULATOR_ATTRS,
    DEFAULT_GENERATED_AT,
    DEFAULT_SEED,
    REDIRECTED_PATH_ATTRS,
    SCHEMA_VERSION,
    DeterministicContext,
    determinism_invariant_failures,
    deterministic_demo_generation,
    stable_sorted,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DEMO_JSON = ROOT / "frontend" / "src" / "demo" / "sc_customer_demo.json"
VERIFIER = ROOT / "scripts" / "verify_nativeforge_demo_payload_determinism.sh"


# --------------------------------------------------------------------------
# Fixed clock
# --------------------------------------------------------------------------


def test_context_has_a_fixed_clock() -> None:
    ctx = DeterministicContext()
    first = ctx.now(UTC)
    second = ctx.now(UTC)
    assert first == second
    assert first.isoformat() == DEFAULT_GENERATED_AT


def test_clock_is_frozen_inside_the_context() -> None:
    import nativeforge.services.unified_audit_event_service as target

    with deterministic_demo_generation():
        a = target.datetime.now(UTC)
        b = target.datetime.now(UTC)
        assert a == b
        assert a.isoformat() == DEFAULT_GENERATED_AT


def test_a_custom_instant_is_honoured() -> None:
    ctx = DeterministicContext(generated_at="2030-06-05T12:00:00+00:00")
    assert ctx.now(UTC).year == 2030


def test_naive_instants_are_treated_as_utc() -> None:
    ctx = DeterministicContext(generated_at="2030-06-05T12:00:00")
    assert ctx.now(UTC).tzinfo is not None


# --------------------------------------------------------------------------
# Deterministic identity
# --------------------------------------------------------------------------


def test_ids_are_stable_for_the_same_seed_and_call_order() -> None:
    a = DeterministicContext(seed="s")
    b = DeterministicContext(seed="s")
    assert [a.next_id() for _ in range(5)] == [b.next_id() for _ in range(5)]


def test_a_different_seed_gives_different_ids() -> None:
    a = DeterministicContext(seed="one")
    b = DeterministicContext(seed="two")
    assert a.next_id() != b.next_id()


def test_successive_ids_do_not_collide() -> None:
    ctx = DeterministicContext()
    issued = [ctx.next_id() for _ in range(200)]
    assert len(set(issued)) == 200


def test_different_namespaces_do_not_collide() -> None:
    """Same counter value under two namespaces must not produce the same id."""
    a = DeterministicContext(seed="s")
    b = DeterministicContext(seed="s")
    assert a.next_id("alpha") != b.next_id("beta")


def test_stable_key_is_content_derived_and_order_independent() -> None:
    ctx = DeterministicContext(seed="s")
    first = ctx.stable_key("org", "opportunity")
    ctx.next_id()
    ctx.next_id()
    assert ctx.stable_key("org", "opportunity") == first
    assert ctx.stable_key("org", "other") != first


def test_uuid_is_deterministic_inside_the_context() -> None:
    import nativeforge.services.unified_audit_event_service as target

    with deterministic_demo_generation(seed="s"):
        first = [target.uuid.uuid4().hex for _ in range(3)]
    with deterministic_demo_generation(seed="s"):
        second = [target.uuid.uuid4().hex for _ in range(3)]
    assert first == second
    assert len(set(first)) == 3


def test_uuid_shim_still_exposes_the_real_module_surface() -> None:
    import uuid as real_uuid

    import nativeforge.services.unified_audit_event_service as target

    with deterministic_demo_generation():
        assert target.uuid.UUID is real_uuid.UUID


def test_stable_sorted_orders_deterministically() -> None:
    assert stable_sorted(["b", "a", "c"]) == ["a", "b", "c"]
    assert stable_sorted([3, 1, 2], key=lambda v: v) == [1, 2, 3]


def test_context_describes_itself_and_passes_invariants() -> None:
    ctx = DeterministicContext()
    described = ctx.describe()
    assert described["schema_version"] == SCHEMA_VERSION
    assert described["seed"] == DEFAULT_SEED
    assert described["deterministic"] is True
    assert determinism_invariant_failures(described) == []


def test_invariants_reject_a_broken_description() -> None:
    assert "missing_seed" in determinism_invariant_failures({
        "schema_version": SCHEMA_VERSION,
        "seed": "",
        "generated_at": DEFAULT_GENERATED_AT,
        "deterministic": True,
    })
    assert "context_not_marked_deterministic" in determinism_invariant_failures({
        "schema_version": SCHEMA_VERSION,
        "seed": "s",
        "generated_at": DEFAULT_GENERATED_AT,
        "deterministic": False,
    })
    assert "generated_at_is_not_an_instant" in determinism_invariant_failures({
        "schema_version": SCHEMA_VERSION,
        "seed": "s",
        "generated_at": "not-a-date",
        "deterministic": True,
    })


# --------------------------------------------------------------------------
# Restoration — the context must not leak into runtime
# --------------------------------------------------------------------------


def test_primitives_are_restored_after_the_context() -> None:
    import uuid as real_uuid

    import nativeforge.services.unified_audit_event_service as target

    with deterministic_demo_generation():
        assert target.datetime is not datetime
    assert target.datetime is datetime
    assert target.uuid is real_uuid


def test_the_clock_moves_again_after_the_context() -> None:
    import nativeforge.services.unified_audit_event_service as target

    with deterministic_demo_generation():
        pass
    now = target.datetime.now(UTC)
    assert now.isoformat() != DEFAULT_GENERATED_AT


def test_primitives_are_restored_even_on_exception() -> None:
    import nativeforge.services.unified_audit_event_service as target

    with pytest.raises(RuntimeError):
        with deterministic_demo_generation():
            raise RuntimeError("boom")
    assert target.datetime is datetime


def test_this_module_is_not_patched_by_itself() -> None:
    """An earlier version patched its own `datetime`, which rebound the
    reference the patch loop compared against and silently left most modules
    unfrozen."""
    import nativeforge.services.demo_payload_determinism_service as det

    with deterministic_demo_generation():
        assert det.datetime is datetime
        assert det._REAL_DATETIME is datetime


def test_accumulator_reset_mechanism_still_works(monkeypatch) -> None:
    """Gate 84 removed the `_AUDIT` lists, so nothing is reset today.

    The mechanism is kept as the seam that catches the next module-level
    accumulator, so it is exercised against a stand-in rather than deleted
    along with its last real user.
    """
    import nativeforge.services.demo_payload_determinism_service as det
    import nativeforge.services.gate32_backup_restore_service as target

    monkeypatch.setattr(det, "ACCUMULATOR_ATTRS", ("_STANDIN",), raising=False)
    monkeypatch.setattr(target, "_STANDIN", [{"event": "sentinel"}], raising=False)

    with deterministic_demo_generation():
        assert target._STANDIN == []
        target._STANDIN.append({"event": "inside"})
    assert target._STANDIN == [{"event": "sentinel"}]


def test_no_service_still_keeps_a_module_level_audit_list() -> None:
    """The reason the reset tuple is now empty."""
    import re

    services = ROOT / "src" / "nativeforge" / "services"
    offenders = [
        p.name
        for p in services.glob("*.py")
        if re.search(r"^_AUDIT\s*:?[^=]*=\s*\[\]", p.read_text(encoding="utf-8"), re.M)
    ]
    assert offenders == [], offenders


def test_accumulator_attrs_and_redirects_are_declared() -> None:
    # Gate 84 retired the _AUDIT lists, so nothing needs resetting any more.
    assert ACCUMULATOR_ATTRS == ()
    assert REDIRECTED_PATH_ATTRS
    for module_name, attr in REDIRECTED_PATH_ATTRS:
        assert module_name.startswith("nativeforge.services.")
        assert attr


# --------------------------------------------------------------------------
# Payload determinism
# --------------------------------------------------------------------------


def test_two_payloads_are_equal_in_memory() -> None:
    from nativeforge.services.sc_monday_demo_bridge_service import (
        build_sc_customer_demo_bridge_payload,
    )

    with deterministic_demo_generation():
        a = build_sc_customer_demo_bridge_payload()
    with deterministic_demo_generation():
        b = build_sc_customer_demo_bridge_payload()
    assert a == b


def test_generator_output_is_byte_stable(tmp_path: Path) -> None:
    from nativeforge.services.sc_monday_demo_bridge_service import (
        write_sc_customer_demo_bridge_json,
    )

    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    write_sc_customer_demo_bridge_json(path=first)
    write_sc_customer_demo_bridge_json(path=second)
    assert first.read_bytes() == second.read_bytes()


def test_generation_does_not_write_into_artifacts(tmp_path: Path) -> None:
    """Generation used to leave a file in artifacts/ on every run - one such
    directory had accumulated thousands."""
    from nativeforge.services.sc_monday_demo_bridge_service import (
        write_sc_customer_demo_bridge_json,
    )

    artifacts = ROOT / "artifacts"
    watched = [
        artifacts / "auth0_mode_b_no_secret_logs",
        artifacts / "auth0_validation_smoke",
    ]
    before = {d: len(list(d.glob("*"))) if d.is_dir() else 0 for d in watched}
    write_sc_customer_demo_bridge_json(path=tmp_path / "out.json")
    after = {d: len(list(d.glob("*"))) if d.is_dir() else 0 for d in watched}
    assert before == after


# The payload embeds the current git HEAD. Committing it changes HEAD, which
# changes the payload, so byte equality with a later regeneration is impossible
# by construction - it would require a fixed point that cannot exist. HEAD is a
# legitimate input; what matters is that its influence stays confined.
HEAD_DERIVED_PATHS = (
    ("operator_readiness", "contract", "current_head"),
    ("operator_readiness", "contract", "operator_readiness_id"),
)


def _differing_paths(a: object, b: object, path: tuple[str, ...] = ()) -> list:
    out: list = []
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        assert isinstance(b, dict)
        for key in sorted(set(a) | set(b)):
            out.extend(_differing_paths(a.get(key), b.get(key), path + (key,)))
    elif isinstance(a, list):
        assert isinstance(b, list)
        if len(a) != len(b):
            return [path]
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out.extend(_differing_paths(x, y, path + (str(i),)))
    elif a != b:
        out.append(path)
    return out


def test_committed_json_is_the_generator_output(tmp_path: Path) -> None:
    from nativeforge.services.sc_monday_demo_bridge_service import (
        write_sc_customer_demo_bridge_json,
    )

    fresh = tmp_path / "fresh.json"
    write_sc_customer_demo_bridge_json(path=fresh)
    differing = _differing_paths(
        json.loads(DEMO_JSON.read_text(encoding="utf-8")),
        json.loads(fresh.read_text(encoding="utf-8")),
    )
    unexpected = [p for p in differing if p not in HEAD_DERIVED_PATHS]
    assert unexpected == [], (
        "regenerate frontend/src/demo/sc_customer_demo.json; "
        f"unexpected differences: {unexpected[:5]}"
    )


def test_head_dependence_is_confined_to_declared_fields(tmp_path: Path) -> None:
    """The stronger property: only the declared HEAD-derived fields may depend
    on the commit, so nothing else can drift in behind them."""
    from nativeforge.services.sc_monday_demo_bridge_service import (
        write_sc_customer_demo_bridge_json,
    )

    fresh = tmp_path / "fresh.json"
    write_sc_customer_demo_bridge_json(path=fresh)
    differing = _differing_paths(
        json.loads(DEMO_JSON.read_text(encoding="utf-8")),
        json.loads(fresh.read_text(encoding="utf-8")),
    )
    assert all(p in HEAD_DERIVED_PATHS for p in differing), differing[:5]


def test_ids_built_from_hash_are_stable_across_processes() -> None:
    """`hash()` on a string is randomised per process, so an id derived from it
    changed on every run. One such id existed and is now digest-derived."""
    code = (
        "from nativeforge.services.application_checklist_section_builder_service "
        "import _stable_suffix; print(_stable_suffix('Operator review'))"
    )
    outs = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=True,
        ).stdout.strip()
        for _ in range(3)
    }
    assert len(outs) == 1


def test_no_service_builds_an_id_from_builtin_hash() -> None:
    services = ROOT / "src" / "nativeforge" / "services"
    offenders = []
    for path in services.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "hash(" in line and "hashlib" not in line and "_id" in line:
                offenders.append(f"{path.name}: {line.strip()}")
    assert offenders == [], f"unstable id(s) built from builtin hash: {offenders}"


# --------------------------------------------------------------------------
# Committed payload claim boundaries
# --------------------------------------------------------------------------


def test_committed_json_contains_negative_intelligence() -> None:
    payload = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    assert payload.get("negative_intelligence")
    assert len(payload["negative_intelligence"]["rows"]) == 2


def test_committed_json_is_marked_synthetic() -> None:
    payload = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    assert payload["negative_intelligence"]["synthetic_demo"] is True


def test_committed_json_claims_no_live_coverage() -> None:
    payload = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    ni = payload["negative_intelligence"]
    assert ni["live_coverage_claimed"] is False
    assert ni["source_monitored"] is False
    assert ni["freshness_claimed"] is False
    assert payload["live_ingestion"] is False


# --------------------------------------------------------------------------
# Verifier script
# --------------------------------------------------------------------------


def _run_verifier(
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", str(VERIFIER)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


def test_verifier_script_exists_and_is_executable() -> None:
    assert VERIFIER.is_file()
    body = VERIFIER.read_text(encoding="utf-8")
    assert "set -euo pipefail" in body


def test_verifier_checks_the_things_that_matter() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    # Byte-for-byte comparison of two generations.
    assert "byte_identical" in body
    # Rejects a missing negative_intelligence surface.
    assert "negative_intelligence_present" in body
    # Rejects a live coverage claim.
    assert "no_live_coverage_claimed" in body
    assert "live_coverage_claimed" in body
    # Never writes the committed JSON.
    assert "mktemp -d" in body


def test_verifier_passes() -> None:
    result = _run_verifier()
    assert "RESULT=PASS" in result.stdout, result.stdout[-2000:]
    assert result.returncode == 0


def test_verifier_rejects_a_missing_negative_intelligence_surface() -> None:
    """Simulated against the check logic: a payload without the surface must
    fail, and the script must say which check failed."""
    body = VERIFIER.read_text(encoding="utf-8")
    assert 'check negative_intelligence_present 0' in body
    assert "missing negative_intelligence surface" in body


def test_verifier_rejects_a_live_coverage_claim() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    assert 'check no_live_coverage_claimed 0' in body
    assert "RESULT=FAIL" in body
    assert 'exit "$FAIL"' in body


def test_readiness_doc_still_claims_no_coverage() -> None:
    doc = ROOT / "docs" / "operations" / "467_GATE83B_PRODUCTION_READINESS_DELTA.md"
    body = doc.read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in body
    assert "65% improvement:           NOT CLAIMED" in body
    assert "Controlled customer pilot: NO_GO" in body
