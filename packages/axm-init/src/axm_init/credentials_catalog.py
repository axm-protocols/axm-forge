"""Credential declarations owned by axm-init."""

from __future__ import annotations

from axm_vault import CredentialGroup, CredentialSpec, Sensitivity

__all__ = ["pypi_credentials"]


def pypi_credentials() -> list[CredentialGroup]:
    """Declare the PyPI token consumed by axm-init."""
    token = CredentialSpec(
        name="token",
        env="PYPI_API_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=True,
        default=None,
        prompt="PyPI API token: ",
        aliases=(),
    )
    group = CredentialGroup(
        id="pypi",
        package="axm-init",
        title="PyPI",
        specs=(token,),
        multi=False,
    )
    return [group]
