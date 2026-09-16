# 825 — Gate 158: what a persisted job does not mean

Five defects, all of them mine, all found by measuring rather than reading. Each
one is a way this gate could have shipped something that looked right.

## 1. The worker erased the backlog it existed to preserve

Measured:

```text
as enqueued by the scheduler:
  status=queued  terminal_reason=none
  blocked_reasons=["no_collector_is_registered_for_this_source",
                   "source_activation_not_approved",
                   "source_requires_human_review",
                   "source_terms_not_approved"]

after the worker recorded its outcome:
  status=refused terminal_reason=unknown
  blocked_reasons=["executable_is_not_a_persisted_fact_in_gate_158"]
```

Four real reasons replaced by one runtime note, and a classifiable class
downgraded to `unknown`, on the **first** worker pass.

The entire argument for option A in the survey — give blocked sources durable
rows rather than leaving them as scheduler findings — was that somebody could
later ask *how long have these 171 sources been terms-blocked*. One worker pass
made that unanswerable. The store was durable; what it durably held had been
emptied of meaning.

The fix: a store-loaded job carries the persisted reasons, the worker **appends**
its own rather than substituting, and a transition unions with what the row
already held. After:

```text
status=refused  terminal_reason=terms_blocked
blocked_reasons=["executable_is_not_a_persisted_fact_in_gate_158",
                 "no_collector_is_registered_for_this_source",
                 "source_activation_not_approved",
                 "source_requires_human_review",
                 "source_terms_not_approved"]
```

`terms_blocked`, not `unknown`. The backlog is countable again.

**The lesson**: durability is not preservation. A row that survives while its
contents are overwritten is worse than no row, because it looks like evidence.

## 2. My identity service digested a word Gate 99B does not have

Measured, before anything was written to the store:

```text
model    job_id : 445b6522b9e3861a2d7f...
identity job_id : abe2a3504231cc61ecc5...
AGREE           : False      (in all four cases)
```

`"scheduled_check"` is not in Gate 99B's `JOB_TYPES`, so
`_norm(job_type, JOB_TYPES, fallback=DEFAULT_JOB_TYPE)` silently returns
`"source_check"` and digests that. Gate 156 has been passing a word outside the
vocabulary since it was written; the id it produced was stable, so nothing
surfaced it.

Had I trusted my own default, the store would have held ids the scheduler does
not report, and "idempotent enqueue" would have been true of the table and false
of the system.

The fix: normalize through the **imported** vocabulary. A duplicated vocabulary
is how the same drift happens twice. Gate 156 now passes the real word, which
changes no id — the fallback was already producing it — and removes a silent
coercion.

## 3. And then I stripped the source_id, which Gate 99B does not

After fixing the vocabulary, three of four cases agreed:

```text
--- whitespace in the source id
    AGREE : False
```

I called `.strip()` on the source_id before digesting. Gate 99B does not. That
is a second normalization of the same fact — the very "second source of truth"
the module's own docstring warns against. I wrote the warning and then did it
anyway; the probe caught it, not the reasoning.

**The lesson**: a docstring that states a principle is not a check that the
module follows it.

## 4. Five route guards would have refused every request

I wrote:

```python
if not same_org(ctx, org_id):
    raise HTTPException(status_code=403, detail="organization_mismatch")
```

`same_org(path_org, ctx)` takes the path org **first**, and returns None while
raising a 404 itself. So the arguments were backwards — which blew up inside the
guard — and had the order been right, `not None` is always True, so every single
request would have been refused with a 403.

Worse than the crash: the convention is 404 and not 403 on purpose, because a
403 confirms the organization exists to somebody who is not in it.

A route that refuses everyone looks identical to a route that is strict. The
TestClient found it; reading the diff would not have.

## 5. The health route claimed a restart proof it cannot produce

`survives_restart` came back True from the health route, measured by writing
inside a SAVEPOINT and reading back through **the same connection**. That green
check has two possible causes — a durable row, or a session that remembers its
own uncommitted write — and the campaign's rule is that such a check has only
been half-tested.

A route cannot fix this by trying harder. Proving a row survives a restart needs
a commit and a reconnect, and a GET that commits fixture rows into the demo org
is worse than a GET that admits what it cannot measure.

So the route supplies no restart evidence, reports that condition red, and names
the verifier. `restart_evidence_supplied: false` distinguishes *unmeasured here*
from *broken*. The verifier proves it in separate processes:

```text
phase A  writes three rows, commits, exits
phase B  a new process finds six rows it did not write, unchanged
```

## The substring-vs-meaning defect, for the fifth and sixth times

While writing the tests for defect 1, I wrote:

```python
assert "WHERE job_id LIKE" not in cleanup
```

The cleanup script's docstring **explains Gate 157's defect**, quoting the very
pattern it must not use. My scan matched the explanation and failed a correct
file. I then rewrote it to scan line by line, which split the SQL — its adjacent
string literals span two lines, so the verb and its WHERE clause were never seen
together.

The running tally in this campaign:

```text
Gate 153  a table classifier matched a name
Gate 154  a subprocess scan matched the word in a docstring saying it
          starts none
Gate 156  an allowlist_empty scan matched the docstring ruling the branch out
Gate 157  a cleanup LIKE pattern matched a digest column, not a prefix
Gate 158  a scan matched a docstring explaining Gate 157's bug
Gate 158  and then a line-scan split the statement it was checking
```

Six times, one shape. The fix is the same every time — check meaning, not
spelling — and the tool is usually the AST:

```python
deletes = [
    node.value
    for node in ast.walk(tree)
    if isinstance(node, ast.Constant)
    and isinstance(node.value, str)
    and "DELETE FROM" in node.value
]
assert len(deletes) == 2          # falsifiable: finding none must not pass
```

Python joins adjacent literals into one constant at parse time, so the AST hands
over whole statements. Gate 154 reached for this after its subprocess scan; this
is that lesson applied one layer deeper.

## What a green Gate 158 does not license

```text
a source was contacted        no
a collector ran               no
a source is approved          no. Zero are.
source terms were accepted    no. 171 are still blocked, on a human.
a job was completed           no, and the database refuses one
monitoring is live            no. source_monitoring_live is false.
```

The lane is `collection_job_store_ready`, and it means exactly one thing: queued
collection work survives. `READY_DOES_NOT_MEAN` is in the health payload for
anyone tempted to read it as more.

**A persisted job is not proof a collection occurred. A claimed job is not proof
a source was contacted.** Both sentences are in the code as values that
`job_store_invariant_failures` would catch if either flipped.
