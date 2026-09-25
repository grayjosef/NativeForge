# Production Foundation — Sprint 1

Architecture survey and threshold definition. **No infrastructure was
provisioned, no account created, no money spent, no collector activated, no
Cloudflare setting changed.**

The finding that matters most is not about hosting.

---

## 0. The headline

> **21 tables carry `FORCE ROW LEVEL SECURITY` for PostgreSQL. None of it has
> ever executed in a verification run.**

`tests/conftest.py` forces `sqlite+pysqlite:///…`. All 14,144 tests in the
Tranche 2 authoritative suite ran on SQLite. **60 of 63 migrations contain a
Postgres-only branch**, and every one of those branches — triggers, policies,
`FORCE ROW LEVEL SECURITY` — is skipped under SQLite, which takes a separate
`_sqlite_demo_triggers` path instead.

So the database-level tenant isolation NativeForge is designed around is
**written, migrated, and unexercised**. A green suite is not evidence about
it, and Gate 61's own checklist said so in advance: *"the RLS machinery in
migration `0002` is Postgres-specific. Choosing otherwise abandons isolation
code that is already written."*

This is not a defect. It is a **measurement gap**, and it sets the sprint's
priority: the first thing the production foundation must do is run the schema
on the engine it was written for.

---

## 1. Current runtime architecture — REAL

| Layer | Fact |
|---|---|
| Backend | FastAPI + uvicorn, `nativeforge.main:app`, loopback `127.0.0.1:8000` |
| Frontend | React + Vite (`nativeforge-web`), preview on `127.0.0.1:5175` |
| ORM / migrations | SQLAlchemy 2 + Alembic, head **0065**, 63 migration files |
| DB driver | `psycopg[binary]>=3.2` — a **runtime** dependency |
| Dev database | SQLite file at repo root; **`.env.example` says PostgreSQL for local dev** |
| Auth | OIDC (`oidc_issuer / client_id / audience / callback_url / client_secret`) |
| Object storage | S3-compatible (`raw_payload_object_store_*`, incl. `force_path_style`) |
| Health | `/backend/health`, `/backend/readiness` — deliberately **not** `/health`, which the Vite preview serves statically |
| API surface | **118 routes; 109 carry `{org_id}` in the path** |
| Worker | `nativeforge-source-orchestrator.service` — **template, not installed, not enabled** |
| Edge | Cloudflare Tunnel `nativeforge-mayhem`, config outside the repo in `~/.cloudflared/` |

## 2. Current deployment architecture — REAL

**There is no deployment pipeline.** CI (`.github/workflows/ci.yml`) is
verification only: ruff, an SQL isolation gate, pytest, `alembic history`,
plus frontend typecheck and build. It deploys nothing.

Deployment today is four systemd **user** units on a WSL2 workstation, three
of which are explicitly labelled templates that no script installs. The
backend unit binds `127.0.0.1` and a test parses the file to prove it.

**No Dockerfile, no compose file, no Terraform, no Pulumi, no Vercel/Render/
Fly/Railway config exists in the repo.** A provider-name sweep of `docs/`
found AWS (4), Azure (2), Supabase (2), Neon (1) — all in decision-matrix and
survey documents, never as configuration. "Render" appeared 28 times and is
the verb.

**The WSL2 host is disqualified**, on this sprint's own evidence: `Linger=yes`,
`NRestarts=0`, and the tunnel started **10 times in 20 minutes** because the
user manager is torn down with the distro.

---

## 3. Hosting requirements, derived from the product

| Requirement | Evidence | Class |
|---|---|---|
| Persistent backend process | FastAPI app, loopback-only today | **REQUIRED_NOW** |
| Managed PostgreSQL | `psycopg` is a runtime dep; 60/63 migrations have PG branches; doc 205 rejects SQLite for production | **REQUIRED_NOW** |
| HTTPS + custom domain | `.dev` TLD forces HTTPS; target hostname approved | **REQUIRED_NOW** |
| Secrets management | 9 OIDC/session/storage secret names; none may reach the frontend bundle | **REQUIRED_NOW** |
| Health checks | `/backend/health`, `/backend/readiness` already exist | **REQUIRED_NOW** |
| Application + deployment logs | none aggregated today | **REQUIRED_NOW** |
| Known deployed commit | `/backend/health` already returns `git_sha` + `source_dirty` | **REQUIRED_NOW** |
| Rollback | no mechanism exists | **REQUIRED_NOW** |
| Backup / restore | doc 315: claims **false** | **REQUIRED_BEFORE_PILOT** |
| S3-compatible object storage | settings exist; `production_storage_approved: false` | **REQUIRED_BEFORE_PILOT** |
| Background worker / scheduler | orchestrator unit written, never enabled; zero sources approved | **REQUIRED_BEFORE_PILOT** |
| Private networking | DB must not be publicly reachable | **REQUIRED_BEFORE_PILOT** |
| Connection pooling | serverless PG needs it; depends on provider | **UNKNOWN** |
| WebSocket / SSE | no usage found | **FUTURE** |
| Horizontal scaling | single tenant-set pilot | **FUTURE** |
| Malware scanning on uploads | doc 205 requires before customer uploads | **FUTURE** (no customer uploads yet) |

---

## 4. Existing infrastructure inventory

| Thing | State | Basis |
|---|---|---|
| GitHub repo + Actions CI | **EXISTS** | `grayjosef/NativeForge`, ci.yml runs |
| Cloudflare account + DNS authority | **EXISTS** | account `7327…5469`; `mayhem-nc.dev` + `josef-gray.dev` on `jaime`/`mariah.ns.cloudflare.com` |
| Cloudflare Tunnel `nativeforge-mayhem` | **EXISTS** | running, 4 edge connections |
| Auth0 / OIDC tenant | **UNKNOWN** | doc 223 is an Auth0 runbook; live tenant not verified this sprint |
| Managed PostgreSQL | **DOES_NOT_EXIST** | Gate 61 provider checkbox still blank |
| S3-compatible object store | **DOES_NOT_EXIST** | `production_storage_approved: false` |
| AWS / Azure / GCP / Railway / Render / Fly / Vercel / Supabase / Neon | **UNKNOWN** | named only in decision docs; **no account verified, none assumed** |

I did not sign into, create, or probe any cloud account beyond Cloudflare and
GitHub, which were already authorized.

---

## 5. Recommended architecture

**Managed PostgreSQL + a single persistent container/VM running the FastAPI
app, fronted by the existing Cloudflare Tunnel, deployed from a tagged commit
by GitHub Actions.**

Rationale, from evidence rather than preference:

- Postgres is **not optional** — 60/63 migrations branch on it and 21 tables'
  isolation exists only there. Any other engine discards written isolation code.
- The Cloudflare Tunnel already works and needs **no inbound ports**, which
  suits a product handling Tribal data.
- CI already builds and verifies; it needs a deploy job, not a new system.
- One persistent process satisfies REQUIRED_NOW. Workers stay off — **zero
  sources are approved**, so a scheduler would have nothing to legitimately do.

### Alternatives considered

| Option | Why not now |
|---|---|
| Keep WSL2 + tunnel | Disqualified by measured lifecycle instability |
| Serverless (Lambda/Cloud Run/Workers) | Alembic + long-running orchestrator + pooling friction; no benefit at pilot scale |
| Kubernetes | Operational burden vastly exceeds one API + one DB |
| SQLite in production | **Explicitly rejected** by doc 205, and would abandon all RLS |
| Managed PaaS with bundled PG | Viable and simplest — **but selecting a vendor is the owner's decision**, see §11 |

**I am deliberately not naming a vendor.** The brief forbids guessing, and
Gate 61's provider line is blank by design.

---

## 6. Database plan

- **Engine:** PostgreSQL 16+ (doc 387 recommendation; `psycopg` already present).
- **Schema:** created by `alembic upgrade head` (0065). **No wholesale upload
  of the local SQLite database.**
- **Extensions:** none identified beyond core; RLS is built-in. To be
  confirmed on first real Postgres run.
- **Pooling:** UNKNOWN until provider chosen.
- **Seed:** demo-safe only. Protected demo org
  `bbbbbbbb-cccc-dddd-eeee-ffffffffffff`. The real org
  `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` remains **no-touch without explicit
  authorization**.
- **First action on real Postgres — before any deployment:** run the full
  migration chain and then the suite against Postgres, to execute the 60
  Postgres-only branches for the first time. Expect findings. That is the
  point.

---

## 7. Tenant boundary map

**Identifier:** `org_id` (UUID), in the path on **109 of 118 routes**.

Enforcement is layered, and the layers are not equally proven:

| Layer | Mechanism | Proven? |
|---|---|---|
| Route | `{org_id}` path parameter | REAL — 109/118 |
| Application | `assert_no_cross_org_access`, `assert_no_cross_org_read`, `assert_object_key_org_scoped`, `assert_demo_route_org`, `assert_real_route_org`, `require_customer_demo_org` (`lib/demo_isolation.py`) | REAL — exercised by the SQLite suite |
| Repository | 17 repository modules scope on `org_id` | REAL |
| CI | `scripts/check_nf_sql_grep.py` — blocks `nf_*` SQL outside repositories | REAL |
| **Database** | **Postgres triggers + `FORCE ROW LEVEL SECURITY` on 21 tables** | **NEVER EXECUTED** |
| Object storage | `assert_object_key_org_scoped` + prefix isolation | BUILT, not provisioned |
| Background jobs | orchestrator refuses every job | NOT ACTIVATED |
| Caches | none identified | — |

**`org_id` appearing in tables is not isolation.** The application layer is
genuinely tested; the database layer beneath it is a promise that has never
been kept in any run.

---

## 8. Adversarial tenant test plan — next sprint, executable

Each must run **against PostgreSQL with RLS active**, not SQLite:

1. Cross-org ID guessing on all 109 org-scoped routes (A's token, B's `org_id`)
2. Search leakage — A's query returning B's rows
3. Feed leakage — opportunity feed overlays
4. Pursuit-state leakage
5. Watch / dismiss leakage
6. Document leakage, including signed-URL scope and expiry
7. Export leakage
8. AI-context leakage — B's text in A's prompt context
9. Admin route rejects a normal user
10. Background job executing across tenants
11. Cache contamination
12. **RLS negative control** — disable the app-layer guard and confirm the
    *database* still refuses. If it doesn't, RLS is decorative.

Item 12 is the one that distinguishes real defence in depth from one layer
wearing two hats.

---

## 9. Cloudflare TLS — evidence preserved, no change made

**PROVEN_EDGE_TLS_FAILURE.** HTTP :80 answers (301); HTTPS fails with **TLS
alert 40**, reproduced by `openssl s_client` and Chrome;
`cloudflared_tunnel_total_requests` stays **0**; the failing hostname set
changes between runs while stable within one. Universal SSL **Active**
covering `*.mayhem-nc.dev` to 2026-12-03; AOP off at global/zone/per-hostname
with no certificates; no CAA; control zone `josef-gray.dev` returns 200.

`ROOT_CAUSE_BEYOND_EDGE_CERT_DISTRIBUTION = UNKNOWN`.

### Escalation path — prepared, not executed

1. **Evidence package:** per-hostname `openssl s_client` transcripts across
   several runs showing the moving failure set; `cf-ray` IDs from the 525
   responses; tunnel metrics showing 0 requests; the working control zone.
2. **Support path:** free plan — community/ticket. To be confirmed.
3. **Reissuance procedure:** disable/re-enable Universal SSL forces reorder.
4. **Blast radius:** the **entire zone**, including `n8n.mayhem-nc.dev`.
   Zone HTTPS is unavailable until reissuance completes — duration **not under
   our control**.
5. **Maintenance window:** required. Not to be attempted ad hoc.
6. **Rollback:** none meaningful — reissuance cannot be un-ordered. This is
   why it is a decision gate.

**Not attempted this sprint, per the brief.**

---

## 10. Domain, auth, secrets

**Target: `https://nativeforge.mayhem-nc.dev`** — unchanged.
`nf-dev.mayhem-nc.dev` is **not** the controlled-live hostname.
Registrar transfer: `DEFERRED_NOT_DEPLOYMENT_BLOCKING`.

**Secret names only** (no values anywhere in this repo or report):

```
DATABASE_URL
NF_SESSION_SIGNING_KEY
OIDC_ISSUER  OIDC_CLIENT_ID  OIDC_CLIENT_SECRET
OIDC_AUDIENCE  OIDC_CALLBACK_URL
NF_PUBLIC_ORIGIN
RAW_PAYLOAD_OBJECT_STORE_ENDPOINT / _BUCKET / _REGION
RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID / _SECRET_ACCESS_KEY
NATIVEFORGE_FEEDBACK_SLACK_WEBHOOK_URL   (alert mode defaults to dry_run)
```

Required for the target host, **to be configured only once the host exists**:

- `NF_PUBLIC_ORIGIN` = `https://nativeforge.mayhem-nc.dev`
- `OIDC_CALLBACK_URL` = `https://nativeforge.mayhem-nc.dev/api/auth/callback`
  (the tunnel routes `^/api/.*` to the backend; ordering is load-bearing —
  Gate 129E)
- Cookies `Secure`, `HttpOnly`, `SameSite=Lax`, host-scoped
- CORS: exact origin, **no wildcard**
- `NF_DEV_ORG_HEADERS=false` — the dev `X-NF-Org-Id` header must return 503

No secret may appear in the Vite bundle; only `VITE_`-prefixed values reach
the client and none of the above is so prefixed.

---

## 11. Gates

### CONTROLLED_LIVE — binary, all required

```
[ ] stable non-WSL host              [ ] health endpoint green
[ ] managed PostgreSQL, private      [ ] application + deployment logs
[ ] alembic at head on that DB       [ ] backup configured
[ ] Postgres-branch migrations RUN   [ ] rollback proven, not described
[ ] known deployed commit, clean     [ ] no debug mode
[ ] TLS valid on the target host     [ ] secrets absent from bundle & repo
[ ] auth login + logout working      [ ] tenant smoke green ON POSTGRES
```

### PRODUCTION — separate, additional

Full adversarial tenant campaign (§8, including the RLS negative control) ·
privacy and data-governance review · **Indigenous data governance
applicability review** · source activation policy · monitoring and alerting
maturity · backup/restore **proven by a real restore** · incident runbook
proven by a drill · customer onboarding · support and escalation · security
review · legal and commercial review.

**Not `PRODUCTION_READY`. Not `CUSTOMER_LAUNCH_READY`.**

---

## 12. Observability and runbooks — honest status

| Item | Status |
|---|---|
| Health endpoint | **EXISTS** — `/backend/health` returns `git_sha`, `source_dirty`, `production_ready: false` |
| Readiness endpoint | **EXISTS** |
| Structured error logging | UNKNOWN — not surveyed to a conclusion |
| Aggregated logs | **DOES NOT EXIST** — journald on a disposable host |
| Uptime checks / alerts | **DOES NOT EXIST** |
| DB health, worker health | **DOES NOT EXIST** |
| Backup / restore | doc 315 claims **false** |
| Rollback | **DOES NOT EXIST** |

Runbooks: `RUNBOOK_START`, `_STOP`, `_DEPLOY`, `_ROLLBACK`, `_DB_MIGRATION`,
`_BACKUP`, `_RESTORE`, `_INCIDENT` — **all UNKNOWN until executable against a
real host.** Doc 321 exists as narrative. Writing runbook prose for
infrastructure that does not exist would be fiction, and the brief forbids it.

---

## 13. Decisions required from MAYHEM

These block Sprint 2. Each is a purchase or an account.

1. **Hosting provider + managed PostgreSQL** — Gate 61's provider line is
   still blank. Recurring cost. *(Recommendation: choose one vendor supplying
   both a persistent app runtime and managed Postgres, to keep the DB on a
   private network.)*
2. **One environment or two** — Gate 61 recommends staging + production.
   Doubles cost.
3. **Region / data residency** — Gate 61 asks explicitly. This is data about
   Tribal organizations; if any partner expects US-only, decide before
   migrating, not after.
4. **Object storage** — S3-compatible; `production_storage_approved: false`.
   Deferrable to REQUIRED_BEFORE_PILOT.
5. **OIDC tenant** — is there a live Auth0 (or other) tenant, and may I
   configure a callback for the target host?
6. **Cloudflare TLS remediation window** — §9, zone-wide, affects n8n,
   no rollback.

---

## 14. Known unknowns

- Whether the Postgres-only migration branches apply cleanly on a real
  PostgreSQL 16 — **never executed**.
- Whether RLS actually refuses cross-tenant reads independently of the
  application layer.
- Cloudflare edge TLS mechanism beyond inconsistent per-PoP availability.
- Whether a live OIDC tenant exists.
- Connection-pooling needs, which depend on the unchosen provider.
- Structured-logging maturity.
- Gate 170's historical failure — still UNKNOWN, unchanged.

---

## 15. Next implementation sprint

Ordered so the riskiest unknown is retired first, and **none of it needs a
vendor decision except step 3**:

1. Add a **PostgreSQL service to CI** and run the existing suite against it.
   This executes the 60 Postgres-only migration branches for the first time,
   inside a disposable environment, at zero cost. **Do this before choosing a
   host.**
2. Write the §8 adversarial tenant tests, including the **RLS negative
   control**, and run them on that Postgres.
3. *(Gated on decision 1)* Provision managed Postgres + a persistent app host;
   add a deploy job to CI from a tagged commit.
4. Wire `nativeforge.mayhem-nc.dev` to the tunnel once §9 is resolved.
5. Prove rollback and restore by doing them, then write the runbooks from what
   actually happened.

Step 1 is the highest-value action available and requires **no purchase, no
account, and no approval**. It converts the sprint's headline unknown into a
measurement.
