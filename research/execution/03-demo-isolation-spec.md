# 03 — Demo Isolation Spec (Sprint 0)

This is the first code that gets written. Sprint 0 builds the walls around the launchpad before any feature work starts.

## The standard

> A bad frontend query cannot leak demo data into a real customer account. A bad backend query cannot either. A developer making a mistake cannot either. Demo data is isolated at every layer below the UI.

Every layer below assumes the layer above might have a bug. The UI is not trusted. The application is partially trusted. The database is the last line of defense.

## The layers

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Org type — the schema-level distinction                  │
├─────────────────────────────────────────────────────────────┤
│ 2. is_demo flag on every NativeForge record                 │
├─────────────────────────────────────────────────────────────┤
│ 3. Server middleware — enforces context on every request    │
├─────────────────────────────────────────────────────────────┤
│ 4. Query-layer filters — default scope on every query       │
├─────────────────────────────────────────────────────────────┤
│ 5. Database constraints — FK + CHECK + RLS                  │
├─────────────────────────────────────────────────────────────┤
│ 6. CI tests — prove the rule, every commit                  │
└─────────────────────────────────────────────────────────────┘
```

A flag alone is not enough. Middleware alone is not enough. RLS alone is not enough. Defense in depth.

---

## Layer 1 — Org type

The `organizations` table gets a column:

```
org_type  TEXT NOT NULL CHECK (org_type IN ('real', 'demo'))
```

Or, if `organizations` already has a similar column from ContractForge, extend its allowed values rather than add a new column.

**Rule:** an organization is either real or demo. There is no third state. There is no "real but with some demo data" state.

This column is **immutable after creation**. Application logic refuses to update it. A migration to flip it requires a multi-party human approval process (out of scope for code; document it in operations).

---

## Layer 2 — `is_demo` flag

Every NativeForge table includes an `is_demo BOOLEAN NOT NULL` column. Default `FALSE`.

Why both `org_type` and `is_demo`? Because the layers protect against different failure modes.

- `org_type` protects against a real org accidentally getting attached to demo data.
- `is_demo` protects against a single record being created without an org context (e.g., a background job creating an orphan row) and ending up visible to real-org queries.

The two must agree:

```
CHECK (
  (is_demo = TRUE  AND org_type = 'demo')
  OR
  (is_demo = FALSE AND org_type = 'real')
)
```

This is enforced via a foreign-key-aware constraint or a trigger; see Layer 5.

---

## Layer 3 — Server middleware

Every request lands in middleware that establishes a `request.context`:

```python
request.context = {
    "user_id": <from auth>,
    "org_id": <user's current org>,
    "org_type": <looked up from organizations table>,
    "is_demo_route": <from URL: /api/nativeforge/demo/* sets True>,
}
```

The middleware enforces these invariants on every request, before the handler runs:

1. If `is_demo_route` is True, then `org_type` MUST be `demo`. Reject with 403 otherwise.
2. If `is_demo_route` is False, then `org_type` MUST be `real`. Reject with 403 otherwise.
3. The user must be a member of `org_id`. Reject with 403 otherwise.
4. The handler receives `request.context` as an argument; it cannot bypass it.

Demo routes are explicit:

```
/api/nativeforge/demo/sparks       ← demo only, requires demo org
/api/nativeforge/sparks            ← real only, refuses demo org
```

There is no "shared" route that serves both.

---

## Layer 4 — Query-layer filters

Every query on a NativeForge table goes through a repository / data-access layer that applies a default scope based on `request.context`.

```python
def get_sparks(ctx, **filters):
    return (
        db.nf_grant_sparks
          .where(organization_id == ctx.org_id)
          .where(is_demo == (ctx.org_type == 'demo'))
          .where(**filters)
    )
```

**Rule:** raw SQL is forbidden in handler code. All NativeForge data access goes through the repository layer. CI grep-checks for `SELECT ... FROM nf_` outside the data-access module and fails the build if it finds any.

Lint rule equivalent: any function that imports the database client directly (rather than through the repository) fails review.

---

## Layer 5 — Database constraints

The database is the last line of defense. It must reject impossible states even if every layer above is wrong.

### Foreign keys

Every `nf_*` table's `organization_id` is `NOT NULL` and `REFERENCES organizations(id)`. No orphan rows.

### CHECK constraints

The `is_demo`/`org_type` agreement is checked via trigger or generated column:

```sql
CREATE OR REPLACE FUNCTION nf_check_demo_alignment()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.is_demo != (
    SELECT (org_type = 'demo')
    FROM organizations
    WHERE id = NEW.organization_id
  ) THEN
    RAISE EXCEPTION 'is_demo on % does not match org_type for organization %',
      TG_TABLE_NAME, NEW.organization_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

Apply via `BEFORE INSERT OR UPDATE` trigger on every `nf_*` table.

### Row-level security (Postgres)

If the database is Postgres, RLS is the strongest guarantee. Apply RLS policies to every `nf_*` table:

```sql
ALTER TABLE nf_grant_sparks ENABLE ROW LEVEL SECURITY;

CREATE POLICY nf_grant_sparks_org_scope ON nf_grant_sparks
  FOR ALL
  USING (organization_id = current_setting('app.current_org_id')::uuid)
  WITH CHECK (organization_id = current_setting('app.current_org_id')::uuid);

CREATE POLICY nf_grant_sparks_demo_scope ON nf_grant_sparks
  FOR ALL
  USING (is_demo = current_setting('app.current_org_is_demo')::boolean)
  WITH CHECK (is_demo = current_setting('app.current_org_is_demo')::boolean);
```

The middleware sets `app.current_org_id` and `app.current_org_is_demo` on every request via `SET LOCAL`. RLS does the rest.

If the database is not Postgres, the trigger-based approach in the previous subsection plus repository-layer filtering becomes the strongest available. Document the gap in the audit.

---

## Layer 6 — CI tests

The rule is not real until CI proves it on every commit. Tests required to ship Sprint 0:

### Test 1 — Real org cannot read demo records

```python
def test_real_org_cannot_read_demo_records():
    real_org = make_organization(org_type='real')
    demo_org = make_organization(org_type='demo')
    make_grant_spark(organization_id=demo_org.id, is_demo=True)

    with request_context(org_id=real_org.id, org_type='real'):
        sparks = get_sparks()
        assert len(sparks) == 0
```

### Test 2 — Demo org cannot read real records

```python
def test_demo_org_cannot_read_real_records():
    real_org = make_organization(org_type='real')
    demo_org = make_organization(org_type='demo')
    make_grant_spark(organization_id=real_org.id, is_demo=False)

    with request_context(org_id=demo_org.id, org_type='demo'):
        sparks = get_sparks()
        assert len(sparks) == 0
```

### Test 3 — Cannot insert mismatched record

```python
def test_cannot_insert_demo_record_into_real_org():
    real_org = make_organization(org_type='real')
    with pytest.raises(IntegrityError):
        db.execute(
            "INSERT INTO nf_grant_sparks (organization_id, is_demo, ...) "
            "VALUES (%s, TRUE, ...)",
            (real_org.id,)
        )
```

### Test 4 — Demo route refuses real org

```python
def test_demo_route_refuses_real_org():
    real_org = make_organization(org_type='real')
    user = make_user(orgs=[real_org])
    response = client.get('/api/nativeforge/demo/sparks', user=user)
    assert response.status_code == 403
```

### Test 5 — Real route refuses demo org

```python
def test_real_route_refuses_demo_org():
    demo_org = make_organization(org_type='demo')
    user = make_user(orgs=[demo_org])
    response = client.get('/api/nativeforge/sparks', user=user)
    assert response.status_code == 403
```

### Test 6 — Raw SQL grep

CI runs:

```bash
grep -rn 'FROM nf_' --include='*.py' src/ \
  | grep -v 'src/db/repositories/' \
  && exit 1 || exit 0
```

If raw SQL queries on `nf_*` tables exist outside the repository module, CI fails.

### Test 7 — Cross-tenant fuzz

A property-based test that creates N orgs (mix of real and demo), inserts records into each, and verifies that for any pair of orgs (A, B), records visible to A's context never include records owned by B.

```python
@hypothesis.given(orgs=org_fixtures(min_size=2, max_size=10))
def test_no_cross_tenant_leakage(orgs):
    for org in orgs:
        make_grant_spark(organization_id=org.id, is_demo=(org.org_type == 'demo'))

    for org in orgs:
        with request_context(org_id=org.id, org_type=org.org_type):
            sparks = get_sparks()
            for spark in sparks:
                assert spark.organization_id == org.id
                assert spark.is_demo == (org.org_type == 'demo')
```

---

## Section 4 — Server-enforced human review gate

Sprint 0 also ships the review-gate state machine. The gate prevents AI-generated content from being marked "final" without human review, and prevents form packages from being submitted without explicit approval.

### State machine

States, in order:

```
draft  →  review_requested  →  reviewed  →  approved  →  submitted
```

Transitions allowed:

| From | To | Required actor |
|---|---|---|
| draft | review_requested | record owner |
| review_requested | reviewed | user with `reviewer` or `admin` role |
| reviewed | approved | user with `admin` role, distinct from reviewer when possible |
| approved | submitted | user with `admin` role |
| any state | draft | record owner (resets the chain) |

Transitions explicitly forbidden:

- `draft` → `approved` (skipping review)
- `draft` → `submitted` (skipping everything)
- `review_requested` → `approved` (skipping reviewed)
- `reviewed` → `submitted` (skipping approved)
- Any state → `submitted` without an `approved` predecessor

### Enforcement

The state machine is enforced server-side. The frontend can hide buttons but cannot grant transitions. Every transition writes to `review_state_history`:

```json
{
  "from": "review_requested",
  "to": "reviewed",
  "user_id": "...",
  "user_role": "reviewer",
  "at": "2026-05-04T12:34:56Z",
  "note": "Optional reviewer comment"
}
```

The history is append-only. Mutations to past entries are forbidden at the database level (consider a separate `review_state_log` table if append-only-ness is hard to enforce on a JSONB column).

### Test coverage required

For every reviewable record type (`nf_form_packages`, AI-drafted narratives later in M1):

- Test that every forbidden transition is rejected with 422.
- Test that allowed transitions write a history entry with the correct actor.
- Test that the admin-distinct-from-reviewer rule holds when both roles are required (warn, don't block, in M0; harden in M1).

---

## Section 5 — Sprint 0 acceptance criteria

Sprint 0 is done when all of the following are true:

- [ ] `organizations.org_type` column exists with CHECK constraint.
- [ ] All M0 `nf_*` tables exist with `is_demo` column and FK to `organizations`.
- [ ] BEFORE INSERT/UPDATE trigger enforces `is_demo`/`org_type` agreement on every `nf_*` table.
- [ ] (Postgres only) RLS policies enabled and active on every `nf_*` table.
- [ ] Server middleware sets `request.context` on every request and rejects mismatched routes/orgs with 403.
- [ ] Repository layer is the only place `nf_*` tables are queried; CI grep enforces this.
- [ ] All 7 CI tests above pass.
- [ ] State machine for `review_status` enforced and tested.
- [ ] No feature code beyond the above has been merged.

Only after all boxes are checked does work move to `04-m0-implementation-plan.md`.

---

## What this spec does not cover

- The seed-data process for creating demo orgs and demo records. That gets a small `seed_demo_data.py` script in M0; it must use the same write paths real users do, so it gets the same enforcement.
- Authorization beyond demo/real and org membership. RBAC for grant-manager / reviewer / admin / finance roles is sketched in `04` and built in M1.
- Audit log for non-`nf_*` actions. Existing ContractForge audit log is reused; extend if the audit shows gaps.
- Private deployment data residency. M3 concern; out of scope.
