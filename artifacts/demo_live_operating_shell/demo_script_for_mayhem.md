# Demo script — https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo

Ten minutes. The order below is the order on the page.

## Before you start

Open the URL and sign in through Cloudflare Access. The page is behind Access,
so an unauthenticated visitor gets a login screen rather than the demo — that is
deliberate and it is what you want on a dev domain.

## Open with the boundary, not the product

Say this first, in your own words:

> Everything on this screen is controlled demo data. The workflow is real, the
> schema is real, the refusals are real. No Tribe's data is in here and nothing
> is being collected live.

The page says the same thing in the labels at the top. Point at them.

## The labels, and why they are there

- CONTROLLED DEMO DATA
- AUTH NOT LIVE
- LIVE SOURCE MONITORING NOT ACTIVE
- EMAIL DELIVERY NOT ACTIVE
- OBJECT STORE NOT CONFIGURED
- PROVIDER CONFIG REQUIRED FOR LOGIN

These are computed from the system, not typed into the page. When
authentication goes live, the auth label disappears on its own. That is the
honest version of a status badge.

## Walk the ten sections in order

1. **Tribal tenant profile & eligibility** — who the Tribe is, recognition status, and resulting eligibility
2. **Source watchlist** — which funding sources are watched for this Tribe
3. **Weekly matched NOFO digest** — new and changed notices matched to this Tribe's profile
4. **Pursuit pipeline** — opportunities being worked, with stage and owner
5. **Awarded grants workspace** — grants actually won, and the obligations that came with them
6. **Award requirements & reporting deadlines** — what each award requires and when it is due
7. **Proof & audit trail** — what was submitted, when, and what evidence supports it
8. **Document metadata** — which compliance documents exist, filed when, with what digest
9. **Readiness & blockers** — what is built, what is live, and what is blocking the rest
10. **Next actions** — the specific next step for each blocked capability

Each one carries its own status chip:

- **Operational** — live, with real rows
- **Built — not operational** — schema, repository and write path all exist; no
  one owns the rows yet because customer authentication is not live
- **Not built** — no table declares it

Right now nothing is Operational, six are Built, and the reason is the same for
all six: `no_customer_auth_so_nobody_owns_the_row`.

## The question you will be asked

> So what actually works?

The answer, and it is a strong one:

> The compliance spine is built and provably empty. Six persistence lanes have
> schema, row-level security anchored on organization_id, and a write path.
> What they do not have is a customer identity to own a row. That is the next
> gate, and it is a provider configuration away rather than a rebuild.

## What not to say

Do not say NativeForge is monitoring sources, sending digests, storing
documents, or logging anyone in. None of those is true today, all four are
labelled on the screen, and every one of them is one configuration step from
being demonstrable.

## If someone asks to log in

They cannot yet. Login returns a named refusal rather than a broken page — you
can show that if it helps: it lists exactly which provider settings are missing.
