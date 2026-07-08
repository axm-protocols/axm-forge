from __future__ import annotations

import pytest
from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec
from pytest_mock import MockerFixture

from axm_doctor.orchestrate import (
    MissingSecret,
    ProvisionResult,
    missing_secrets,
    provision_missing,
)


def _group() -> CredentialGroup:
    """A one-spec fixture group (research.fred.api_key)."""
    return CredentialGroup(
        id="research.fred",
        package="axm-research",
        title="FRED",
        specs=(CredentialSpec(name="api_key", env="FRED_API_KEY", kind="token"),),
    )


def test_missing_secrets_empty_catalog(mocker: MockerFixture) -> None:
    """AC5: an empty vault catalog yields [] gracefully (no crash)."""
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=Catalog(groups=()))
    # doctor_data must not even be needed, but stub it to a value-free empty map.
    mocker.patch("axm_doctor.orchestrate.doctor_data", return_value={})
    assert missing_secrets() == []


def test_missing_secrets_filters_missing(mocker: MockerFixture) -> None:
    """AC1, AC2: a spec whose provenance is 'missing' is returned, value-free."""
    catalog = Catalog(groups=(_group(),))
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=catalog)
    mocker.patch(
        "axm_doctor.orchestrate.doctor_data",
        return_value={"research.fred.api_key": {"layer": "missing", "present": False}},
    )

    result = missing_secrets()

    assert len(result) == 1
    secret = result[0]
    assert isinstance(secret, MissingSecret)
    assert secret.group == "research.fred"
    assert secret.name == "api_key"
    assert secret.package == "axm-research"
    # AC2: a copy-pasteable recovery hint, no value field anywhere.
    assert "axm-vault set" in secret.setup_hint
    assert "research.fred.api_key" in secret.setup_hint
    assert not hasattr(secret, "value")
    assert "value" not in secret.model_dump()


def test_missing_secrets_keeps_present_out(mocker: MockerFixture) -> None:
    """AC1: a spec resolved by a real layer is NOT reported as missing."""
    catalog = Catalog(groups=(_group(),))
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=catalog)
    mocker.patch(
        "axm_doctor.orchestrate.doctor_data",
        return_value={"research.fred.api_key": {"layer": "env", "present": True}},
    )
    assert missing_secrets() == []


def test_provision_dry_run_no_prompt(mocker: MockerFixture) -> None:
    """AC3: confirm=False returns the plan WITHOUT prompting or storing."""
    catalog = Catalog(groups=(_group(),))
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=catalog)
    mocker.patch(
        "axm_doctor.orchestrate.doctor_data",
        return_value={"research.fred.api_key": {"layer": "missing", "present": False}},
    )
    spy = mocker.patch("axm_doctor.orchestrate.run_setup")

    result = provision_missing(confirm=False)

    assert isinstance(result, ProvisionResult)
    spy.assert_not_called()
    assert result.provisioned is False
    # The groups it WOULD prompt for are surfaced in the plan.
    assert "research.fred" in result.groups


def test_provision_confirm_resolved_is_provisioned(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3, AC4: confirm=True delegates to run_setup; provisioned only after re-scan.

    The post-setup re-scan resolves the spec (its provenance flips off
    ``missing``), so ``provisioned`` is True and ``still_missing`` is empty.
    doctor never writes the secret itself (SRP).
    """
    catalog = Catalog(groups=(_group(),))
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=catalog)
    # First scan (plan) -> missing; second scan (post-setup) -> resolved.
    mocker.patch(
        "axm_doctor.orchestrate.doctor_data",
        side_effect=[
            {"research.fred.api_key": {"layer": "missing", "present": False}},
            {"research.fred.api_key": {"layer": "keyring", "present": True}},
        ],
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    setup_spy = mocker.patch("axm_doctor.orchestrate.run_setup")
    # AC4 SRP invariant: doctor must NEVER store a secret itself.
    store_spy = mocker.patch("axm_vault.store.KeyringStore.set")

    result = provision_missing(confirm=True)

    setup_spy.assert_called_once_with(only="research.fred")
    store_spy.assert_not_called()
    assert result.provisioned is True
    assert result.still_missing == []
    assert "research.fred" in result.groups


def test_provision_confirm_still_missing_is_not_provisioned(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: run_setup returning is NOT proof the secret was supplied.

    If the user skips/empties the prompt, ``run_setup`` returns normally yet the
    spec still resolves to ``missing`` on a re-scan. The old code inferred
    ``provisioned=True`` from the bare fact that setup ran (a false green); the
    re-check must report ``provisioned=False`` with the unresolved spec listed
    in ``still_missing``.
    """
    catalog = Catalog(groups=(_group(),))
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=catalog)
    # Both scans (plan + post-setup) still report the spec missing.
    mocker.patch(
        "axm_doctor.orchestrate.doctor_data",
        return_value={"research.fred.api_key": {"layer": "missing", "present": False}},
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    setup_spy = mocker.patch("axm_doctor.orchestrate.run_setup")

    result = provision_missing(confirm=True)

    setup_spy.assert_called_once_with(only="research.fred")
    assert result.provisioned is False
    assert result.still_missing == ["research.fred.api_key"]
    assert result.reason is not None


def test_provision_non_tty_no_systemexit(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC2: in a non-TTY context provision_missing(confirm=True) returns a
    clean ProvisionResult(provisioned=False) WITHOUT calling vault run_setup and
    WITHOUT letting a SystemExit escape."""
    catalog = Catalog(groups=(_group(),))
    mocker.patch("axm_doctor.orchestrate.load_catalog", return_value=catalog)
    mocker.patch(
        "axm_doctor.orchestrate.doctor_data",
        return_value={"research.fred.api_key": {"layer": "missing", "present": False}},
    )
    setup_spy = mocker.patch("axm_doctor.orchestrate.run_setup")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    result = provision_missing(confirm=True)

    assert isinstance(result, ProvisionResult)
    # AC2: nothing provisioned because it could not prompt.
    assert result.provisioned is False
    # AC1: vault's setup driver was never reached, so no SystemExit could escape.
    setup_spy.assert_not_called()
