"""Unit tests for :mod:`axm_vault.catalog` — in-memory, no I/O."""

from __future__ import annotations

import pytest

from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from tests.fixtures.sample_groups import BROKER_GROUP, MAIL_GROUP, SAMPLE_GROUPS


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


def _group_with(name: str, sensitivity: Sensitivity) -> CredentialGroup:
    return CredentialGroup(
        id="svc",
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


@pytest.mark.parametrize("bad_name", ["api.key", "api-key", "spec.set"])
@pytest.mark.parametrize("sensitivity", [Sensitivity.SECRET, Sensitivity.CONFIG])
def test_config_spec_name_charset(bad_name: str, sensitivity: Sensitivity) -> None:
    """AC3: a SECRET/CONFIG spec name with '.' or '-' is rejected at load.

    A SECRET/CONFIG spec routes its name through ``axm_config.set_`` (the
    sentinel ``<name>_set`` for SECRET, the value keyed by ``<name>`` for
    CONFIG), which validates keys against ``_KEY_RE`` = ``^[A-Za-z0-9_]+$``.
    A name carrying ``.`` or ``-`` could never round-trip, so the ``Catalog``
    rejects it at construction (the same path ``load_catalog`` takes).
    """
    with pytest.raises(ValueError, match=bad_name):
        Catalog(groups=(_group_with(bad_name, sensitivity),))


def test_config_spec_name_charset_valid() -> None:
    """AC3: an axm-config-valid spec name (alnum + underscore) is accepted."""
    catalog = Catalog(groups=(_group_with("api_key", Sensitivity.SECRET),))

    assert catalog.group("svc").specs[0].name == "api_key"


def test_config_spec_name_charset_nonsensitive_exempt() -> None:
    """AC3: NONSENSITIVE specs are env-only, so the charset rule does not apply."""
    catalog = Catalog(groups=(_group_with("account.id", Sensitivity.NONSENSITIVE),))

    assert catalog.group("svc").specs[0].name == "account.id"
