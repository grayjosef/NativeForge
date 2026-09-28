"""A structured event nobody can read is not instrumentation.

Gate 176 shipped `nativeforge.auth.demo_bootstrap_decision` to controlled-live,
the callback ran it on every login, and the logs contained none of it. The
event was correct. Nothing was listening.

These tests pin both halves: that an unconfigured logger really does drop an
INFO record - the mechanism, reproduced rather than asserted about - and that
after configuration the real emitter's line arrives intact and exactly once.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from nativeforge.services.application_logging_service import (
    APP_LOGGER_NAME,
    HANDLER_NAME,
    configure_application_logging,
)
from nativeforge.services.demo_bootstrap_decision_log_service import EVENT
from nativeforge.services.demo_bootstrap_decision_log_service import emit as emit_event


@pytest.fixture(autouse=True)
def restore_app_logger():
    """This module reconfigures a process-global logger. Put it back."""
    logger = logging.getLogger(APP_LOGGER_NAME)
    before = (list(logger.handlers), logger.level, logger.propagate)
    yield
    logger.handlers = before[0]
    logger.setLevel(before[1])
    logger.propagate = before[2]


# ------------------------------------------------- the failure, reproduced


def test_an_unconfigured_logger_drops_info():
    """Why the deployed event printed nothing.

    No handler anywhere in the chain means `logging.lastResort` handles the
    record, and lastResort is fixed at WARNING. INFO never survives that.
    """
    probe = logging.getLogger("nativeforge_audibility_probe")
    probe.handlers = []
    probe.setLevel(logging.NOTSET)
    # No ancestor to fall back to, which is the state a bare getLogger() call
    # leaves the application in when nobody has configured logging.
    probe.propagate = False

    assert probe.handlers == []
    assert logging.lastResort is not None
    assert logging.lastResort.level == logging.WARNING
    assert not probe.isEnabledFor(logging.INFO)


def test_lastresort_would_have_passed_a_warning():
    """The counterpart: the same logger is not silent, it is silent at INFO.

    Stated so the diagnosis cannot be misread as "logging was broken"."""
    probe = logging.getLogger("nativeforge_audibility_probe")
    probe.handlers = []
    probe.setLevel(logging.NOTSET)
    probe.propagate = False
    assert probe.isEnabledFor(logging.WARNING)


# ------------------------------------------------------------- the fix


def test_configuring_makes_an_info_record_arrive():
    buffer = io.StringIO()
    configure_application_logging(stream=buffer)

    logging.getLogger(f"{APP_LOGGER_NAME}.auth.something").info("hello")

    assert "hello" in buffer.getvalue()


def test_the_real_decision_event_arrives_and_is_still_json():
    """End to end through the actual emitter, not a stand-in."""
    buffer = io.StringIO()
    configure_application_logging(stream=buffer)

    emit_event(
        bootstrap_attempted=True,
        organization_id_resolved=False,
    )

    written = buffer.getvalue().strip()
    assert written, "the decision event produced no output"
    parsed = json.loads(written)
    assert parsed["event"] == EVENT


def test_the_event_is_written_once():
    """A duplicated decision line invites a reader to believe there were two."""
    buffer = io.StringIO()
    configure_application_logging(stream=buffer)
    configure_application_logging(stream=buffer)

    emit_event(bootstrap_attempted=False)

    assert buffer.getvalue().strip().count(EVENT) == 1


def test_repeated_configuration_leaves_one_handler():
    buffer = io.StringIO()
    for _ in range(4):
        logger = configure_application_logging(stream=buffer)
    ours = [h for h in logger.handlers if getattr(h, "name", None) == HANDLER_NAME]
    assert len(ours) == 1


def test_records_do_not_propagate_to_root():
    """Left propagating, a root handler would write a second copy."""
    logger = configure_application_logging(stream=io.StringIO())
    assert logger.propagate is False


def test_it_does_not_adopt_other_libraries():
    """Configuring root would have taken every dependency's INFO with it,
    including ones that log URLs and connection strings."""
    configure_application_logging(stream=io.StringIO())
    stranger = logging.getLogger("some_third_party_library")
    assert not [
        h for h in stranger.handlers if getattr(h, "name", None) == HANDLER_NAME
    ]


def test_the_handler_writes_to_stdout_by_default():
    """stderr would let a platform read a successful login as a failure."""
    import sys

    from nativeforge.services import application_logging_service as svc

    assert svc.DEFAULT_STREAM is sys.stdout


def test_the_formatter_adds_no_prefix():
    """A structured event has to survive as parseable JSON."""
    from nativeforge.services import application_logging_service as svc

    assert svc.FORMAT == "%(message)s"


# ------------------------------------------------ wired into the application


def test_create_app_configures_logging():
    """The fix is worthless if the application never calls it."""
    source = Path("src/nativeforge/main.py").read_text(encoding="utf-8")
    assert "configure_application_logging()" in source
