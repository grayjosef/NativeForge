# 779 — Gate 149: what a pilot may never carry with it

## The failure this prevents

A pilot activation that also turned on email, because a pilot obviously needs
notifications. Or source monitoring, because what is a grant tool that watches
no sources. Or object storage, because customers upload award letters. Each
sounds like a detail of the pilot and each is four gates of careful work undone
in one sentence.

**Being allowed to start a pilot is not being allowed to start anything else.**

## The ten refused keys

Each names the capability it would have switched on:

```text
source_monitoring_live          -> source_monitoring_live
activate_source_monitoring      -> source_monitoring_live
email_delivery                  -> email_delivery
activate_email                  -> email_delivery
send_email                      -> email_delivery
object_store_configured         -> object_store_configured
activate_object_storage         -> object_store_configured
production_rollout              -> production_rollout
activate_production             -> production_rollout
go_live                         -> production_rollout
```

Refused **even when every prerequisite and the activation approval are
satisfied**, and each of the ten is tested individually with everything else
granted. A bundled request that did not name its target would fail its own
invariant, because a reader has to be able to see what would have been switched
on.

## Why each stays separately gated

### `source_monitoring_live` — Gate 143

```text
171 sources need a human terms review
robots.txt checked per source
an activation approval per source
five scheduler components that do not exist
```

The terms reviews are weeks of human work. They are worth starting in parallel
with the customer identity block, and they are not a pilot prerequisite.

### `email_delivery` — Gate 142

```text
a provider
a service module
an explicit activation
a verified sender domain
unsubscribe and bounce handling
```

The delivery table has a recipient fingerprint and a domain half and no column
for an address, so a dry run cannot quietly become a send. That protection is
the capability being off — not a boundary — and it disappears the moment the
capability is on.

### `object_store_configured` — Gate 141

```text
five settings
an injected client
an owner decision
an external verification
secret scanning
```

### `production_rollout` — Gate 145

```text
always NO_GO, and not a computation
```

No branch anywhere returns anything else for this scope. Production is not the
sum of the technical gates; it is those gates **and** somebody saying yes. A
service that could compute its way to GO would have mistaken one for the other.

## `go_live` is refused twice

Once as a bundle, and once by its own name:

```text
activation_request_bundled_other_capabilities
production_requested_alongside_a_pilot
```

Two blockers for one request, deliberately. A pilot request carrying production
is a different mistake from one carrying email, and collapsing them into a
single refusal would lose that.

## What a pilot does unlock, for contrast

```text
a real customer organization using the product, with their own data
customer identifying and operational data writes, under a recorded consent
  and an approved scope
the awarded-grants workspace, requirements, proof events and audit trail
a weekly digest preview - rendered and read in the product, not sent
```

The last line is the one to read carefully. A digest **preview** is a rendered
page somebody opens. It is not a delivery, and it does not need email delivery
to be true — which is precisely why email is not a pilot prerequisite.

## What to say when somebody asks for "just email, for the pilot"

```text
say     "that is a separate activation with its own five requirements"
say     "the pilot gives them the digest in the product; it does not send it"

avoid   "we can turn that on as part of the pilot"
```

The middle line is the useful one: the thing being asked for usually already
exists in a form that needs no new activation.
