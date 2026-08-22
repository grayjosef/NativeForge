# Gate 36B — Cloudflare operator steps (Mayhem, outside repo)

**Status:** placeholder for Mayhem. This gate does **not** configure DNS,
does **not** start `cloudflared`, and does **not** store credentials.

This is **local loopback deployment machinery only**.
Public cutover is **not** performed by this gate.

**Target local listener:** `127.0.0.1:5175`

**Recommended hostname:** `nf-dev.mayhem-nc.dev` (Mayhem domain family).

Do not assume ordinary Cloudflare DNS alone can reach WSL. Prefer Cloudflare
Tunnel from MAYHEM to `http://127.0.0.1:5175` (no router port-forward, no
public bind of 5175). Alternatives (not Monday default): public IP/NAT, or
host the app on Google Cloud later.

## Ingress snippet (placeholder only)

Do not copy ContractForge hostnames or tunnel UUIDs.
Do not commit credential JSON.

```yaml
ingress:
  - hostname: nf-dev.mayhem-nc.dev
    service: http://127.0.0.1:5175
  - service: http_status:404
```

Cloudflare ingress should map `nf-dev.mayhem-nc.dev` to
`http://127.0.0.1:5175`.

TLS terminates at the Cloudflare edge.

## Access / password

Configure Cloudflare Access or an equivalent password gate **outside**
this repository.

Do not store Cloudflare secrets in the repo.
Do not expose 5175 publicly.
Do not bind the preview listener to `0.0.0.0`.

Vite preview `allowedHosts` includes `nf-dev.mayhem-nc.dev` so the Cloudflare
`Host` header is accepted. Bind remains `127.0.0.1:5175`.

## After Mayhem enables tunnel + DNS + Access

Run:

```bash
NF_VERIFY_BASE_URL='https://nf-dev.mayhem-nc.dev' \
  ./scripts/verify_nativeforge_demo_deployment.sh
```

Use `/?view=sc_customer_demo` for the Monday demo.

## Future customer auth (not Monday)

Real customer login is intentionally deferred from the Monday demo gate.

Future customer-auth lane:

- Auth0 tenant/application
- callback/logout URLs for `mayhem-nc.dev`
- Google Cloud deployment/storage decisions
- production secrets stored outside repo
- customer RBAC validation
- audit logging
- controlled customer pilot gate rerun

Do not implement Auth0 for Monday unless Mayhem switches from a
password-gated demo to real customer-login.

## Allowed claims

- After public verifier PASS plus Access: **limited external demo** only.

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
