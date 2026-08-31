# Post-demo talk track v2

For the follow-up conversation. Plain, short, no defensiveness.

## What NativeForge is

A grant compliance system for Tribal governments. It tracks the whole life of an
award, not just the application:

```text
who the Tribe is and what that makes them eligible for
which funding sources are watched
a weekly digest of new and changed notices, matched to that profile
the pursuit pipeline
awarded grants, and the obligations that came with them
what each award requires, and when it is due
proof and audit trail: what was submitted, when, backed by what
document metadata: which file, for what, filed when, with what digest
```

The distinguishing thing is that it refuses to guess. Where it does not know, it
says so and names what is missing. For a government answering to a federal
auditor, a system that invents a plausible answer is worse than no system.

## What went wrong in the demo

The page showed a Cloudflare error. It was a dev-host tunnel dropping for about
fifteen seconds — the machine hosting it goes idle and shuts down, taking the
tunnel with it.

It was not the product, and it was not authentication. It was the demo rig, and
it was avoidable.

Being straight about it: the rig was never hardened for a live audience. That is
on us and it is fixed.

## What is fixed now

```text
restart policy      all three services now restart on a clean exit, not only
                    on a crash. The tunnel exits cleanly when it loses its
                    connections, which is exactly what happened, and the old
                    policy ignored it.

preflight verifier  one command, checked from outside, that answers "will a
                    browser see this right now" rather than "is a process
                    running". It refuses to pass on the specific error the
                    demo hit.

runbook             a 10-minute checklist, plus how to tell a normal sign-in
                    screen from a real failure.

Google sign-in      the provider is configured and the full public path is
                    proven: Google accepts the app, redirects to us, and our
                    API answers. Verified end to end in a browser.
```

## What is still not live

Said plainly, because it will be asked:

```text
login              not live. The path is proven; the session is not built yet.
source monitoring  not active. Nothing is being collected live.
email digests      not sending.
document storage   not configured. The system holds descriptions of documents,
                   not the documents.
customer data      none. Zero rows in any customer table.
```

Everything on the demo screen is controlled demo data, and the page says so in
six labels that are computed from the system rather than typed in. When one of
those becomes live, its label disappears on its own.

## Why the product is still strong

The hard part is done and it is the part nobody enjoys building.

```text
six persistence lanes with schema, row-level security anchored on a single
organization id, and a write path
a compliance spine that will not mark anything operational until a real
customer identity owns the row
about 10,300 tests, including ones whose whole job is to catch the system
claiming more than it can prove
```

What is missing is a login and some configuration. What is present is the
compliance model — and that is the part that takes months and that a competitor
cannot fake in a sprint. A demo that stumbles on a tunnel is a bad afternoon. A
system that quietly overstates what it knows is a lost contract and possibly a
failed audit.

We built it in the order that keeps the second one from happening.

## Next 48 hours

```text
1  Finish sign-in: persist the login state, issue the redirect, exchange the
   code, mint the session. The path is proven; this is the remaining build.
2  Bind a signed-in identity to an organization, so a real person owns a real
   row for the first time.
3  Re-run the demo on the hardened rig, with the preflight checklist, and
   record it so a tunnel can never take the story down again.
```

Then the first operational lane goes live and the demo stops being demo data.
