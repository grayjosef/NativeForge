"""Database engine and session factory.

## Every transaction starts with a castable tenant anchor

`set_config(..., is_local => true)` lasts exactly one transaction. Writing the
no-tenant sentinel once when a request picks up its session therefore protects
only that request's FIRST transaction: the moment anything commits or rolls
back - which the OAuth callback does, twice - the anchor reverts to the empty
string, and the next statement that casts it raises.

That is not hypothetical. It is what controlled-live did after the sentinel was
added at request granularity:

```text
ERROR: invalid input syntax for type uuid: ""
ERROR: invalid input syntax for type boolean: ""
ERROR: current transaction is aborted, commands ignored ...
```

So the sentinel is written on `after_begin` instead, where "every transaction"
is the actual unit. A route that has resolved a real organization still calls
`apply_org_rls_gucs` and overwrites it, exactly as before; this only guarantees
that the value is never the empty string.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nativeforge.lib.settings import get_settings

settings = get_settings()

_sqlite_memory = settings.database_url.startswith("sqlite+pysqlite:///:memory:")

_engine_kwargs: dict = {"pool_pre_ping": True}
if _sqlite_memory:
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

engine = create_engine(settings.database_url, **_engine_kwargs)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ARG001
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Session, "after_begin")
def _anchor_every_transaction(session, transaction, connection) -> None:  # noqa: ARG001
    """Write the no-tenant sentinel at the start of every transaction.

    Imported late and called defensively: this runs inside SQLAlchemy's own
    event dispatch, and an exception here would surface as a failure of
    whatever statement happened to open the transaction. A tenant anchor that
    could not be written must not become a 500 on an unrelated route - the
    policies still deny on an unset anchor, which is the safe direction.
    """
    if connection.dialect.name != "postgresql":
        return
    from nativeforge.db.rls import set_no_tenant_anchor

    try:
        set_no_tenant_anchor(connection)
    except Exception:  # pragma: no cover - defensive, see docstring
        pass
