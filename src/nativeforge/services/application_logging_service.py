"""Make the application's own structured events audible.

## The events were being built and thrown away

Gate 176 added `nativeforge.auth.demo_bootstrap_decision`: one JSON line per
OAuth callback saying exactly which half of the demo bootstrap refused. It was
deployed, it ran, and controlled-live produced not one line of it.

Nothing was wrong with the event. `logging.getLogger(...)` returns a logger
with no level and no handler, so a record walks up to the root logger, and a
root logger that nobody configured has no handler either. Python then falls
back to `logging.lastResort`, which is fixed at WARNING. An `INFO` record with
no configured ancestor is dropped on the floor.

Uvicorn's own lines kept appearing throughout, which is what made this so easy
to miss: uvicorn configures `uvicorn`, `uvicorn.error` and `uvicorn.access`
explicitly, with their own handlers. Those loggers were never the application's
loggers. Seeing request lines in Railway said nothing about whether the app's
own events were reaching anybody, and for weeks they were not.

## Why this attaches to `nativeforge` and not to root

Configuring root would work and would also adopt every library that logs, at a
level this application did not choose - including libraries that log request
URLs and connection strings at INFO. Attaching one handler to the `nativeforge`
hierarchy takes responsibility for this application's records only.

`propagate` is then turned off so a record is written once. Left on, a record
would be handled here and again by any handler installed on root, and the
duplicate is worse than noise: two copies of a decision event invite a reader
to believe two decisions were made.

## Idempotent on purpose

`create_app()` is called per process normally, but tests build applications
repeatedly in one interpreter. Adding a handler per call would multiply every
line by the number of applications ever constructed, so the handler is tagged
and a second call replaces rather than appends.

This changes what is written, never what is decided. No caller's behaviour
depends on it, and the emitters already redact their own fields - this module
is deliberately not the place where that is enforced.
"""

from __future__ import annotations

import logging
import sys

#: The hierarchy this application owns. Everything the app logs is below it.
APP_LOGGER_NAME = "nativeforge"

#: Marks the handler as ours, so repeated configuration replaces one handler
#: instead of stacking copies of it.
HANDLER_NAME = "nativeforge.stdout"

#: stdout, not stderr. These are events, not failures, and a platform that
#: reads stderr as an error signal should not be told a successful login was
#: one.
DEFAULT_STREAM = sys.stdout

#: One line, already JSON where it matters. No prefix is added, so a structured
#: event stays parseable by whatever reads the log.
FORMAT = "%(message)s"


def configure_application_logging(
    *, level: int = logging.INFO, stream: object | None = None
) -> logging.Logger:
    """Attach exactly one stdout handler to the `nativeforge` hierarchy.

    Returns the configured logger so a caller - in practice a test - can assert
    on it rather than reaching into the logging module's globals.
    """
    logger = logging.getLogger(APP_LOGGER_NAME)

    for existing in list(logger.handlers):
        if getattr(existing, "name", None) == HANDLER_NAME:
            logger.removeHandler(existing)

    handler = logging.StreamHandler(stream if stream is not None else DEFAULT_STREAM)
    handler.name = HANDLER_NAME
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(FORMAT))

    logger.addHandler(handler)
    logger.setLevel(level)
    # Written once. See the module docstring.
    logger.propagate = False
    return logger
