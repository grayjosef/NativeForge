# Gate 24 — Session / Tenant Enforcement (Block 54)

## Session statuses
not_started, fixture_internal, dry_run, configured_not_validated, live_validated,
expired, invalid, blocked, unknown

## Enforced
- Expired/invalid sessions block access
- Dry-run cannot claim live access
- Customer cannot access operator-only surfaces
- Cross-org denial on evidence, policy, authority, export (audited)
- Collaboration management blocked while OFF

## Claims remain false
production multi-tenant, external users can access, controlled customer pilot GO
