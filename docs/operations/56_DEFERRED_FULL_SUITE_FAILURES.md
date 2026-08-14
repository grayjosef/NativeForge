# Deferred full-suite failures

46 failures inventoried at HEAD `a1203ba`. Primary theme: tests freeze Alembic
head at `0019` while repository head is `0021`, plus older activation/runtime
and corpus gate assertions.

**This maintenance block does not change migrations, activation, scoring, or
match logic to clear these.** Track for a dedicated test-expectation repair block.
