"""Operator-script Session transaction boundaries.

Canonical batch persist calls ``connection.commit()``, which deassociates the
ORM Session transaction. A outer ``session.commit()`` then raises
``InvalidRequestError: This transaction is inactive``.

Bounded collection finalizes persistence inside the service layer; scripts must
not perform a second commit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def reset_session_transaction_if_inactive(session: Session) -> None:
    """Drop a deassociated transaction left behind by ``connection.commit()``."""
    if not session.in_transaction():
        return
    trans = session.get_transaction()
    if trans is not None and not trans.is_active:
        session.rollback()


def commit_bounded_operator_session(session: Session) -> None:
    """Commit tail ORM/SQL work for one bounded operator run.

    Canonical batch persist uses ``connection.commit()``, which deassociates the
    ORM transaction while the DBAPI connection may still hold an active
    transaction with flushed spark/stamp work. Commit at the connection layer
    when that is the case; otherwise commit through the Session.
    """
    reset_session_transaction_if_inactive(session)
    conn = session.connection()
    conn_trans = conn.get_transaction()
    if conn_trans is not None and conn_trans.is_active:
        conn.commit()
        return
    if session.in_transaction():
        trans = session.get_transaction()
        if trans is not None and trans.is_active:
            session.commit()
