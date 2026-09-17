# What still blocks the first live source

Gate 162 made the live guard's permitted branch reachable only from recorded,
attributable facts. It approved nothing.

## The eleven facts, and who owns each unresolved one

```text
source_registered     the registry curator            SATISFIED (177 sources)
rate_limit_status     declared politeness policy      SATISFIED
user_agent_status     the canonical user agent        SATISFIED
credential_status     public sources need none        SATISFIED for public

terms_status          A HUMAN REVIEWER                MISSING for all 177
human_review_status   A HUMAN REVIEWER                MISSING for all 177
activation_status     an operator, with attribution   MISSING for all 177
attribution_status    derived from the terms decision MISSING for all 177
robots_status         a live robots.txt fetch         UNRESOLVABLE here
collector_status      an operator, by starting one    not_active
runtime_status        the Gates 157-161 lanes         observed per process
```

## The ordering constraint Gate 163 must honour

`robots_status` cannot be answered without an HTTP request to the source. So
Gate 163's **first live call is a robots.txt fetch, not a collection**, and its
result has to be recorded before any other request to that host is permitted.

That is the politeness requirement arriving before the traffic it governs.

## What a human has to do before any real source can be called

```text
1  read a source's actual terms and record a signed terms decision
   (reviewed_by, reviewed_at, and an evidence fingerprint of the document -
    the database refuses an approval without all three)
2  record a signed source review decision
3  record an activation with attribution, in
   nf_active_opportunity_sources
4  perform and record a robots.txt fetch
5  and only then may a collection request be permitted
```

## What is still missing in code, after all of that

```text
no live transport implementation   Gate 161 built none
live not dispatchable              DISPATCHABLE_KINDS = {hermetic}
allow_live_fetch hardcoded False   in authorize_source_for_live_access
migration 0047 CHECK constraints   refuse transport_kind='live' and
                                   live_source_call=1
```

A fully authorized source today would sit at `live_fetch_not_opted_in`.
**Authorization complete is not a permitted request**, and the two are separate
fields so that one cannot be read as the other.

## Current state

```text
sources evaluated                 179  (177 shipped + 2 synthetic fixtures)
real sources approved               0
real sources allowlisted            0
synthetic fixtures allowlisted      1  (the reachability proof)
terms-blocked                     171
human-review-blocked                6
live source calls                   0
source_monitoring_live          false
```

## The one thing worth re-reading before Gate 163

The synthetic fixture reaching `approved` is what makes every refusal here
falsifiable - without it, a boundary that refused unconditionally would pass
every check. It proves the chain can say yes.

It proves nothing about any real source. Its terms approval was signed by
`reviewer:nf162-artifact` against a fingerprint of a string in this
repository, and its host is `.invalid`. The temptation at Gate 163 will be to
treat the mechanism as the permission. The mechanism is built; the permission
is a human's to give.
