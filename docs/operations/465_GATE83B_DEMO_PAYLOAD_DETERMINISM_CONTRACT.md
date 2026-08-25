# 465 — Gate 83B: Demo payload determinism contract

`src/nativeforge/services/demo_payload_determinism_service.py`
(`nf_demo_payload_determinism_v1`), enforced by
`scripts/verify_nativeforge_demo_payload_determinism.sh`.

**Two generations of `frontend/src/demo/sc_customer_demo.json` from the same
HEAD are now byte-identical**, in the same process and across processes.

## What made the payload nondeterministic

Five causes, each found only after fixing the one before it. The count of
differing leaves between two builds went `94 → 44 → 387 → 3 → 0`.

### 1. Wall clock — 13 `created_at`, 8 `timestamp`, plus embedded id stamps

Leaf services call `datetime.now(UTC)` directly; there is no shared `now()`
helper. 41 loaded modules expose the class. Timestamps also appear *inside*
generated ids (`nf_auth0_live_val_20260825T103058Z_...`).

### 2. Randomness — nonces, event ids, id suffixes

`uuid.uuid4().hex[:8]` across 37 loaded modules. (`secrets`, `random` and
`time` are not used on this path at all.)

### 3. Module-global accumulators — thirty `_AUDIT` lists

```python
_AUDIT: list[dict[str, Any]] = []
...
"audit_refs": [a["event"] for a in _AUDIT[-3:]],
```

Every one of the thirty **doubled per build**. The payload depended on how many
times the process had already generated one, and the lists grow without bound in
any long-running process. Freezing the clock would not have touched this.

### 4. On-disk side effects — generation wrote into `artifacts/`

Generation wrote a no-secret unlock log, an auth0 smoke record, an evidence blob
and a placeholder on **every run**. One directory,
`artifacts/auth0_mode_b_no_secret_logs/`, had accumulated **4,379 files**.

Output depended on what previous runs had left on disk, so three separate
processes produced three different payloads even with clock and identity frozen.

### 5. `hash()` — an id that changed on every interpreter start

```python
item_id=f"{oid}:{pid}:approval:{hash(gate) & 0xFFFF:x}"   # before
item_id=f"{oid}:{pid}:approval:{_stable_suffix(gate)}"    # after
```

Python randomises string hashing per process. This id was different on every
run — not just in the demo. An id built from `hash()` cannot be used as a
cross-process key, so this was a latent bug that the determinism work surfaced.
Exactly one such site existed in the codebase; a test now fails if another
appears.

A sibling of the same problem: `list({...})` over a set literal, whose string
iteration order is also per-process randomised, reordered `next_safe_actions`.
Replaced with an order-preserving `dict.fromkeys` dedupe.

## How deterministic generation works

`deterministic_demo_generation()` is a context manager entered **only** by the
generator and the verifier. For the duration of one generation it:

1. **Freezes the clock** — replaces `mod.datetime` with a fixed-`now()` subclass
   on every loaded `nativeforge.` module where that attribute is the real class.
2. **Seeds identity** — replaces `mod.uuid` with a shim whose `uuid4()` is
   counter-derived from the seed. Everything else falls through to the real
   module, so `uuid.UUID` is still the real class.
3. **Resets accumulators** — clears every module-level `_AUDIT` list, in place,
   so a generation depends on its inputs and not on process history.
4. **Redirects write paths** — points the four `artifacts/` write targets and
   the demo lifecycle SQLite database at a scratch directory.
5. **Restores everything on exit**, including on exception.

```text
seed          nativeforge-sc-customer-demo
generated_at  2026-01-01T00:00:00+00:00
id_namespace  demo-id
nonce_namespace demo-nonce
```

Changing `DEFAULT_GENERATED_AT` changes every timestamp in the artifact, so it
is a deliberate, reviewable edit.

### Why patch module attributes instead of threading a parameter

Threading a seed/clock through the services was the obvious reading of "patch
the assemblers" and is the wrong trade: it would touch 40+ services, put a
demo-only concern into the runtime API of services used elsewhere, and fail
*silently* if one were missed — the payload would simply keep churning in a
field nobody notices. The scoped context cannot miss a module.

### The self-patching trap

This module is itself a `nativeforge.` module exposing `datetime`. An earlier
version patched **itself** partway through the scan, which rebound the global
the loop was comparing against, so every module visited afterwards failed the
identity check. Only a handful were frozen and the payload kept churning.

Fixed by capturing `_REAL_DATETIME` / `_REAL_UUID_MODULE` at import and
excluding this module from the scan. A test pins both.

### Why the scratch directory has a fixed name

One redirected path is embedded in the payload (`no_secret_log_path`), so a
`mkdtemp()` name would have reintroduced exactly the churn being removed.

**Corrected in Gate 84B.** This originally read "generation is sequential, so a
stable shared name is safe". That assumption was wrong. Running the determinism
verifier while a full test suite was in progress put two processes in the same
scratch directory, and one wiping it at context entry surfaced as a UNIQUE
constraint failure in the lifecycle SQLite database.

The directory name is still fixed — it has to be — but the context now takes an
exclusive `flock` for its duration, so concurrent generations serialise rather
than corrupt each other. Stable name and concurrency safety, at the cost of one
waiting on the other.

## Which dynamic mode remains opt-in

`write_sc_customer_demo_bridge_json(deterministic=False)` builds against the
real clock and real entropy. It exists for a live snapshot and **must not**
produce the committed JSON — the verifier's
`committed_matches_regeneration` check would fail if it did.

`build_sc_customer_demo_bridge_payload()` is unchanged and still dynamic when
called directly; only the committed-artifact path is deterministic by default.

## Runtime impact

**None, by construction.** Nothing at runtime enters the context. Tests assert
that the real `datetime` and `uuid` are restored afterwards, that the clock
moves again, that restoration survives an exception, and that accumulator
contents are put back exactly.

The build stamp is untouched: `nativeforge-build-sha` and `source_dirty` still
pin which commit produced the deployed bundle.

## Why this matters for eligibility content review

Before Gate 83 the payload was diagnostic scaffolding and churn was cosmetic.
It now carries the applicant-class exclusion, its evidence quote and the hash of
the artifact that quote came from.

A reviewer asking "what changed in this commit?" could not answer it from a
diff: regenerating for Gate 83 produced 567 insertions and 476 deletions almost
entirely unrelated to the change. A wording change to a customer-facing
exclusion would have been indistinguishable from timestamp noise.

Now the diff is the change, and the verifier fails if the committed artifact is
not what the generator currently produces.

## The one legitimate input that cannot be frozen: git HEAD

The payload embeds the current commit:

```text
operator_readiness.contract.current_head        "881fdfc"
operator_readiness.contract.operator_readiness_id   derived from it
```

This is not churn — it is a real input, and the readiness contract is more
useful for naming the commit it describes.

But it makes byte equality between the committed artifact and a later
regeneration **impossible by construction**: committing the payload changes
HEAD, which changes the payload. Demanding that they match would require a
fixed point that cannot exist. The first version of the verifier demanded
exactly that and failed the moment the gate was committed.

The check is therefore two checks:

```text
committed_matches_regeneration   equal once the HEAD-derived fields are blanked
head_dependence_isolated         *only* those fields differ
```

The second is the stronger property. It proves nothing else has quietly become
HEAD-dependent, and it would fail if a future change made another field vary
with the commit. The same pair is asserted by
`tests/test_gate83b_demo_payload_determinism.py`.

## What the verifier checks

```text
payload_byte_identical            two generations, byte for byte
negative_intelligence_present     the Gate 83 surface survived regeneration
negative_intelligence_rows        both applicant classes still present
synthetic_demo_true               the demo still declares itself synthetic
no_live_coverage_claimed          live_coverage_claimed is false
no_source_monitoring_claimed      source_monitored is false
no_freshness_claimed              freshness_claimed is false
payload_live_ingestion_false      the payload-wide boundary holds
committed_payload_present         the artifact exists
committed_matches_regeneration    equals current generator output, HEAD fields aside
head_dependence_isolated          only the declared HEAD fields vary with the commit
```

It writes only to a scratch directory, so running it can never dirty the tree.
