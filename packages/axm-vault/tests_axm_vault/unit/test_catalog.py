"""Unit tests for :mod:`axm_vault.catalog` — in-memory, no I/O."""

from __future__ import annotations

import pytest

from axm_vault import catalog as catalog_module
from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from tests_axm_vault.fixtures.sample_groups import (
    BROKER_GROUP,
    MAIL_GROUP,
    SAMPLE_GROUPS,
)


def test_group_lookup() -> None:
    """AC2: ``Catalog.group(id)`` returns the matching group."""
    catalog = Catalog(groups=SAMPLE_GROUPS)

    assert catalog.group("broker") is BROKER_GROUP
    assert catalog.group("mail") is MAIL_GROUP
    assert catalog.groups() == list(SAMPLE_GROUPS)


def test_group_unknown_raises() -> None:
    """AC2: ``Catalog.group`` raises ``KeyError`` on an unknown id."""
    catalog = Catalog(groups=SAMPLE_GROUPS)

    with pytest.raises(KeyError, match="nope"):
        catalog.group("nope")


def test_for_package_filters() -> None:
    """AC3: ``Catalog.for_package`` returns only groups of that package."""
    catalog = Catalog(groups=SAMPLE_GROUPS)

    assert catalog.for_package("axm-broker") == [BROKER_GROUP]
    assert catalog.for_package("axm-mail") == [MAIL_GROUP]
    assert catalog.for_package("axm-unknown") == []


def test_all_specs_flattens() -> None:
    """AC3: ``Catalog.all_specs`` returns ``(group_id, spec)`` pairs."""
    catalog = Catalog(groups=SAMPLE_GROUPS)

    pairs = catalog.all_specs()

    expected = [(group.id, spec) for group in SAMPLE_GROUPS for spec in group.specs]
    assert pairs == expected
    assert all(gid in {"broker", "mail"} for gid, _ in pairs)


def _group_with(
    name: str, sensitivity: Sensitivity, *, gid: str = "svc"
) -> CredentialGroup:
    return CredentialGroup(
        id=gid,
        package="pkg",
        title="Service",
        specs=(
            CredentialSpec(
                name=name,
                env="SVC_X",
                kind="token",
                sensitivity=sensitivity,
                required=False,
            ),
        ),
    )


# ``.``/``-`` were already rejected by the old ``^[A-Za-z0-9_]+$`` mirror;
# ``API_Key`` (upper-case) and ``api__key`` (doubled ``_``) are the names that
# the old, diverged mirror WRONGLY accepted — they slip past ``[A-Za-z0-9_]+``
# but violate axm-config's real key charset ``^[a-z0-9]+(_[a-z0-9]+)*$`` and so
# would blow up mid-``run_setup``. They are the regression guard for the
# "validator that lied" bug (mirror re-aligned to ``axm_config.validate_segment``).
@pytest.mark.parametrize(
    "bad_name", ["api.key", "api-key", "spec.set", "API_Key", "api__key", "_key"]
)
@pytest.mark.parametrize("sensitivity", [Sensitivity.SECRET, Sensitivity.CONFIG])
def test_config_spec_name_charset(bad_name: str, sensitivity: Sensitivity) -> None:
    """AC3: a SECRET/CONFIG spec name outside axm-config's key charset is rejected.

    A SECRET/CONFIG spec routes its name through ``axm_config.set_`` as a key,
    validated against axm-config's ``^[a-z0-9]+(_[a-z0-9]+)*$``. Any name that
    could never round-trip — path chars, upper-case, doubled/edge underscore —
    is rejected at construction (the same path ``load_catalog`` takes) via the
    canonical ``axm_config.validate_segment`` rather than a hand-mirrored regex.
    """
    with pytest.raises(ValueError, match=bad_name):
        Catalog(groups=(_group_with(bad_name, sensitivity),))


def test_config_spec_name_charset_valid() -> None:
    """AC3: an axm-config-valid spec name (lowercase alnum + single _) is accepted."""
    catalog = Catalog(groups=(_group_with("api_key", Sensitivity.SECRET),))

    assert catalog.group("svc").specs[0].name == "api_key"


def test_config_spec_name_charset_nonsensitive_exempt() -> None:
    """AC3: NONSENSITIVE specs are env-only, so the key charset rule does not apply."""
    catalog = Catalog(groups=(_group_with("account.id", Sensitivity.NONSENSITIVE),))

    assert catalog.group("svc").specs[0].name == "account.id"


@pytest.mark.parametrize("bad_id", ["axm_broker", "Broker", "api-key", "svc..x"])
def test_group_id_namespace_charset(bad_id: str) -> None:
    """AC3: a group id outside axm-config's namespace charset is rejected at load.

    ``group.id`` is used verbatim as the axm-config namespace of every CONFIG
    write (``set_(group.id, ...)``), so it must match
    ``^[a-z0-9]+(\\.[a-z0-9]+)*$``.
    An id with ``_``, upper-case, ``-`` or a doubled dot would raise a
    ``ConfigError`` at the first ``set_`` mid-setup; the catalog rejects it up
    front. Checked even for a NONSENSITIVE-only group (the id namespaces the
    whole group).
    """
    with pytest.raises(ValueError, match="namespace"):
        Catalog(groups=(_group_with("token", Sensitivity.NONSENSITIVE, gid=bad_id),))


def _mixed_catalog() -> tuple[Catalog, object]:
    from axm_vault import auth

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    credential = CredentialSpec(name="api_key", env="API_KEY", kind="token")
    dependency = auth.AuthDependencySpec(
        name="claude-session", source=ConnectedSource()
    )
    group = CredentialGroup(
        id="agent",
        package="axm-agent",
        title="Agent",
        specs=(credential,),
        auth_dependencies=(dependency,),
    )
    return Catalog(groups=(group,)), dependency


def test_auth_dependencies_flattens_only_auth_dependencies() -> None:
    """AC1: the dedicated accessor returns every declared auth dependency exactly."""
    from axm_vault import auth

    catalog, dependency = _mixed_catalog()

    observed = catalog.auth_dependencies()

    assert observed == [dependency]
    assert {item.name for item in observed} == {"claude-session"}
    assert all(isinstance(item, auth.AuthDependencySpec) for item in observed)


def test_all_specs_excludes_auth_dependencies() -> None:
    """AC2: credential traversal never includes an authentication dependency."""
    catalog, _dependency = _mixed_catalog()

    credential_names = {spec.name for _group_id, spec in catalog.all_specs()}

    assert credential_names == {"api_key"}
    assert "claude-session" not in credential_names


def test_non_callable_provider_is_rejected() -> None:
    """AC1: a non-callable contribution is rejected without yielding groups."""
    groups, rejection = catalog_module.groups_from_provider("axm-git", object())

    assert groups == ()
    assert isinstance(rejection, catalog_module.CatalogRejection)
    assert rejection.entry_point == "axm-git"
    assert "not callable" in rejection.reason


def test_provider_returning_non_group_item_is_rejected() -> None:
    """AC2: a contribution item must be a CredentialGroup."""
    groups, rejection = catalog_module.groups_from_provider(
        "wrong-item", lambda: ["not-a-group"]
    )

    assert groups == ()
    assert rejection is not None
    assert "str" in rejection.reason


def test_raising_provider_is_rejected_without_propagation() -> None:
    """AC3: a provider exception becomes a rejection instead of escaping."""

    def raise_kaput() -> list[CredentialGroup]:
        raise RuntimeError("kaput")

    groups, rejection = catalog_module.groups_from_provider("raising", raise_kaput)

    assert groups == ()
    assert rejection is not None
    assert "kaput" in rejection.reason
