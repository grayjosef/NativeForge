"""Pytest configuration — file-backed SQLite plus Alembic before collection."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

_tmp = Path(tempfile.mkdtemp(prefix="nf_pytest_"))
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(_tmp / 'nf.sqlite3').as_posix()}"

# NF_DEMO_ORG_IDS is deliberately NOT defaulted here.
#
# A suite-wide default was added for the Gate 178 M0 demo bypass, and it cost
# 273 failures in files that have nothing to do with entitlements. The reason
# is in `demo_org_classification_service`: an EMPTY allowlist is silence, but a
# CONFIGURED one that omits an organization is a disagreement -
# `settings_says_real_database_says_demo` - so every older test that builds a
# demo organization under some other UUID started refusing itself.
#
# It bought nothing. Every test that needs the allowlist already sets it with
# `monkeypatch.setenv`, scoped to itself: gate178's firewall, gate132's
# classification, mission control, and isolation routes. All of them pass with
# no default here, and so do gates 178 and 179 entire.
#
# Empty is also what the deployment actually runs with, which `test_isolation_
# routes` states in so many words. A suite that configures an allowlist the
# product does not have is testing a machine nobody is running.

# Gate 130. The suite must not read whoever's provider happens to be configured
# on the machine running it.
#
# Gate 129C gave every auth detector one resolution order - os.environ wins,
# Settings fills the gaps - and Settings reads `.env`. That was invisible while
# `.env` held no auth keys. The moment Gate 130 configured a real Google client,
# 25 tests failed: gates 115 through 118 assert unconfigured-provider behaviour
# and were reading live credentials.
#
# A suite whose result depends on the developer's `.env` is not testing the code.
#
# Blanking these in `os.environ` is NOT enough and was the first attempt here:
# the overlay falls through to Settings when an environment value is empty, and
# Settings reads `.env`, so the credentials came back. The file itself has to go.
#
# `os.environ` still outranks `.env` in pydantic-settings, so the DATABASE_URL
# override above keeps working, and a test that wants a configured provider
# injects one explicitly.
for _auth_key in (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "NF_PUBLIC_ORIGIN",
    "NF_SESSION_SIGNING_KEY",
    "NF_OIDC_DISCOVERY_ENABLED",
    "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL",
):
    os.environ.pop(_auth_key, None)

from nativeforge.lib.settings import Settings as _Settings  # noqa: E402

_Settings.model_config["env_file"] = None


def pytest_configure(config: pytest.Config) -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    from nativeforge.lib.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


#: Environment a test may legitimately set for itself, and must not leave set.
#:
#: Gate 134: `tests/session_org_helper` sets NF_SESSION_SIGNING_KEY so it can
#: sign a session for a converted route - the verifier reads the variable, so
#: passing a key explicitly would not work. It set it process-wide and never
#: removed it, so once one converted test ran, every later test in the process
#: saw a configured signing key. Gates 118 and 119 assert the environment has
#: none, and thirteen of them failed on a variable a neighbour had set.
#:
#: Restored per test rather than blanked: a test that sets it deliberately keeps
#: it for its own duration, and nobody inherits it.
_TEST_SCOPED_ENV: tuple[str, ...] = ("NF_SESSION_SIGNING_KEY",)


@pytest.fixture(autouse=True)
def _restore_test_scoped_env() -> None:
    before = {name: os.environ.get(name) for name in _TEST_SCOPED_ENV}
    yield
    for name, value in before.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(autouse=True)
def _truncate_nf_tables() -> None:
    yield
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as s:
        s.execute(text("DELETE FROM nf_auto_publish_config"))
        s.execute(text("DELETE FROM nf_activation_state"))
        s.execute(text("DELETE FROM nf_audit_events"))
        s.execute(text("DELETE FROM nf_form_packages"))
        s.execute(text("DELETE FROM nf_pursuit_briefs"))
        s.execute(text("DELETE FROM nf_pursuit_calendar_events"))
        s.execute(text("DELETE FROM nf_pursuit_tasks"))
        s.execute(text("DELETE FROM nf_grant_pursuits"))
        s.execute(text("DELETE FROM nf_spark_requirements"))
        s.execute(text("DELETE FROM nf_spark_scores"))
        s.execute(text("DELETE FROM nf_nofo_extraction_runs"))
        s.execute(text("DELETE FROM nf_tribal_profiles"))
        s.execute(text("DELETE FROM nf_operator_actions"))
        s.execute(text("DELETE FROM nf_discovery_review_items"))
        s.execute(text("DELETE FROM nf_discovery_intake_candidates"))
        s.execute(text("DELETE FROM nf_discovery_intake_runs"))
        s.execute(text("DELETE FROM nf_grant_sparks"))
        s.execute(text("DELETE FROM nf_source_check_runs"))
        s.execute(text("DELETE FROM nf_opportunity_sources"))
        s.execute(text("DELETE FROM nf_active_opportunity_sources"))
        s.execute(text("DELETE FROM nf_review_artifacts"))
        s.execute(text("DELETE FROM organizations"))
        s.commit()
