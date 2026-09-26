"""Gate 180: the unauthenticated org header fails closed by default.

`X-NF-Org-Id` names the tenant that every row-level security policy reads, and
nothing authenticates it. While `nf_dev_org_headers` defaulted to True, a
deployment that simply forgot to set the variable accepted an attacker-chosen
tenant. The default is now False.

Flipping it moved a second thing, which is why that is tested here too. The
activation gate used to let the setting clear
`dev_header_disabled_for_production` on its own. That was conservative only
while the default was True - an unconfigured process read as "enabled" and held
the blocker shut. With the default False the same branch would have cleared the
blocker for any process that never set the variable, so a developer laptop
would have asserted a fact about production. Only a measurement clears it now.
"""

from __future__ import annotations

from nativeforge.lib.settings import Settings
from nativeforge.services import customer_auth_activation_gate_service as gate_svc

DEV_HEADER_FIELD = "nf_dev_org_headers"


def test_the_declared_default_is_false() -> None:
    """Read from the model, not from memory of what it says."""
    field = Settings.model_fields[DEV_HEADER_FIELD]
    assert field.default is False


def test_an_unconfigured_settings_object_refuses_the_header() -> None:
    """No environment, no .env: the header is not honoured."""
    settings = Settings(_env_file=None)
    assert settings.nf_dev_org_headers is False


def test_the_variable_still_turns_it_on_explicitly(monkeypatch) -> None:
    """Dev and demo lanes must keep working when they ask for it."""
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    assert Settings(_env_file=None).nf_dev_org_headers is True


def test_the_default_alone_does_not_clear_the_production_blocker() -> None:
    """Absence of configuration is not evidence about production."""
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["dev_header_disabled_for_production"] is False
    assert gate["customer_auth_live"] is False


def test_only_a_measured_zero_clears_it() -> None:
    gate = gate_svc.build_customer_auth_activation_gate(
        dev_header_exposure={"route_total": 217, "dev_header_route_count": 0}
    )
    assert gate["dev_header_disabled_for_production"] is True


def test_a_measurement_that_still_finds_routes_holds_it_shut() -> None:
    """The permitted branch is not the only reachable one."""
    gate = gate_svc.build_customer_auth_activation_gate(
        dev_header_exposure={"route_total": 217, "dev_header_route_count": 3}
    )
    assert gate["dev_header_disabled_for_production"] is False


def test_an_empty_measurement_is_not_a_measurement() -> None:
    """A zero count with no route total means the scan found nothing at all."""
    gate = gate_svc.build_customer_auth_activation_gate(
        dev_header_exposure={"route_total": 0, "dev_header_route_count": 0}
    )
    assert gate["dev_header_disabled_for_production"] is False


def test_turning_the_header_on_does_not_by_itself_block_a_measured_zero(
    monkeypatch,
) -> None:
    """A header that no route reads cannot set the RLS context, whatever the
    setting says. This records that the clearing condition is the measurement
    and nothing else, so the test fails if the setting is wired back in."""
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    gate = gate_svc.build_customer_auth_activation_gate(
        dev_header_exposure={"route_total": 217, "dev_header_route_count": 0}
    )
    assert gate["dev_header_disabled_for_production"] is True
