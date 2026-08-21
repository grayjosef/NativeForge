# Auth0/OIDC Validation Run Support (Gate 18 / Block 41)

## Purpose

Define the exact validation sequence and claim resolver that prove (or refuse)
`login_live` for Auth0/OIDC.

## Validation run contract fields

`auth_validation_run_id`, `provider_type`, `environment_scope`,
`config_present`, `secret_present`, `issuer_validated`, `jwks_validated`,
`callback_url_validated`, `logout_url_validated`, `allowed_origins_validated`,
`token_validation_passed`, `session_validation_passed`, `invite_binding_passed`,
`org_binding_passed`, `role_mapping_passed`, `rbac_handoff_passed`,
`tenant_boundary_passed`, `audit_event_emitted`, `login_live_claimed=false`,
`production_auth_claimed=false`, `validated_at`, `validation_errors`.

## Login claim rules

- Dry-run cannot unlock login live.
- Fixture/internal cannot unlock login live.
- Partial config cannot unlock login live.
- Secret-present alone cannot unlock login live.
- Provider + invite + org + role + RBAC + tenant + audit gates must all pass.
- Gate 18 keeps `login_live_claimed=false` until real Auth0 config + owner
  authorization exist.

## Smoke

```bash
source .venv/bin/activate
python scripts/nativeforge_auth0_validation_smoke.py
bash scripts/campaign_block41_smoke_verify.sh
```

Never prints secrets. Never fabricates credentials.
