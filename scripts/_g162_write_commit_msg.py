"""Write the Gate 162 commit message to .git/COMMIT_MSG_G162.

Exists because the message contains apostrophes, and every shell path to
`git commit -F -` in this environment mangles them: a single-quoted
`bash -lc '...'` terminates on `guard's`, and the escaped-quote form has
already truncated one commit body to three lines.

A Python file carries the text with no shell in the loop. Kept in `scripts/`
rather than `.git/` because UNC writes into `.git/` began failing.
"""

from __future__ import annotations

import pathlib

MESSAGE = """Add recorded source authorization boundary

Gate 162. The live network guard's permitted branch is now reachable only from
recorded, attributable facts. Before this gate it was reachable only by
fabricating them.

The survey found the real problem. Fed only what the registry could actually
answer, the guard satisfied 2 of its 10 status requirements: the other eight
had no record anywhere to come from. Gate 134F's rule was that an unreachable
permitted branch makes a refusal unfalsifiable; the converse is worse, because
a permitted branch reachable only by fabrication makes an approval
unaccountable. Nobody had written the caller that knows.

What this does NOT add matters more than what it does. 149 service modules
already match activation/approval terminology, and exactly one of them could
decide source permission:

- no second activation system - three human activation gates already exist
- no second approval store - nf_active_opportunity_sources is composed
- no second review workflow - terms and source review share one table
- no stored allowlist - it is a projection, and the tests assert that no
  column anywhere holds one

What this adds:

- source_authorization_fact_model_service: eleven facts, six statuses, every
  vocabulary READ from the guard rather than restated
- alembic 0048 + source_authorization_decision_repository: one table for terms
  and source review, discriminated by decision_kind, where the database
  refuses an approval with no signer, no time or no evidence fingerprint
- source_authorization_fact_resolver_service: four parameters, no kwargs
  escape hatch, and none of them able to assert a fact
- source_runtime_readiness_fact_service: composes the six Gates 156-161 health
  lanes, repairing a derivation that read Gate 98E's third-party scheduler
  detector and so reported the in-process runtime as absent
- source_live_authorization_service: the only runtime path to a live-network
  decision
- source_allowlist_projection_service, source_activation_packet_service
- four GET routes, zero mutation endpoints

A fact fails in five distinguishable ways - denied, needs_review, missing,
unknown, stale - because nobody decided and somebody decided against are
opposite problems with the same effect on permission. Only a signed decision
authorizes: a ready runtime, a registered source, an available adapter, a
queued job and an execution proof are prerequisites, and the last two are not
facts in this model at all.

A synthetic fixture under a reserved prefix reaches authorized=true with all
eleven facts recorded, which is what makes every refusal falsifiable. It still
sits at live_fetch_not_opted_in: authorization complete is not a permitted
request, and the two are separate fields.

Four defects found and fixed in this gate's own work: a verb list containing
"grant" that matched the noun in grants_gov (101 hits, 1 real); attribution
refusing for every source via a swallowed TypeError; a reachability probe that
printed success while the fully decided fixture still refused, which also
exposed that robots_status had been made unresolvable for every source and left
the permitted branch dead code; and a check for background_worker_available
that matched the docstring explaining it is no longer read.

sources_evaluated=179 real_approved=0 real_allowlisted=0 terms_blocked=171
human_review_blocked=6 caller_supplied_facts_accepted=0 mutation_endpoints=0
live_transport_enabled=false live_source_calls=0 source_monitoring_live=false

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
"""

target = pathlib.Path(".git/COMMIT_MSG_G162")
target.write_text(MESSAGE, encoding="utf-8")
print(f"wrote {len(MESSAGE.splitlines())} lines to {target}")
