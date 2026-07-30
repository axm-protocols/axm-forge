"""Static fixture catalog — literal credential groups for tests.

These groups never touch real ``axm.credentials`` entry-points; they are
built directly from :class:`CredentialGroup`/:class:`CredentialSpec` literals
so that tests stay independent of the (empty-by-design) galaxy catalog.
"""

from __future__ import annotations

from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity

__all__ = ["BROKER_GROUP", "MAIL_GROUP", "SAMPLE_GROUPS", "provide_sample_groups"]

BROKER_GROUP = CredentialGroup(
    id="broker",
    package="axm-broker",
    title="Broker API",
    specs=(
        CredentialSpec(
            name="api_key",
            env="BROKER_API_KEY",
            kind="token",
            sensitivity=Sensitivity.SECRET,
        ),
        CredentialSpec(
            name="account_id",
            env="BROKER_ACCOUNT_ID",
            kind="id",
            sensitivity=Sensitivity.NONSENSITIVE,
            required=False,
        ),
    ),
)

MAIL_GROUP = CredentialGroup(
    id="mail",
    package="axm-mail",
    title="Mail SMTP",
    specs=(
        CredentialSpec(
            name="password",
            env="MAIL_PASSWORD",
            kind="password",
            sensitivity=Sensitivity.SECRET,
        ),
    ),
)

SAMPLE_GROUPS = (BROKER_GROUP, MAIL_GROUP)


def provide_sample_groups() -> list[CredentialGroup]:
    """Entry-point-style callable returning the sample groups."""
    return list(SAMPLE_GROUPS)
