"""SecretStr coercion helpers and log redaction.

A secret must never surface in ``repr``, ``str``, ``f"{x}"`` or
:meth:`pydantic.BaseModel.model_dump`. The plaintext is reachable only
through an explicit :meth:`pydantic.SecretStr.get_secret_value` call,
which is the single deliberate reveal surface (an explicit opt-in, not an
audited/logged one — no audit trail is emitted).
"""

from __future__ import annotations

from pydantic import SecretStr

__all__ = ["MASK", "MIN_REDACT_LEN", "as_secret", "redact"]

MASK = "********"

MIN_REDACT_LEN = 4
"""Secrets shorter than this are too short to mask without over-redacting logs."""


def as_secret(value: str | SecretStr | None) -> SecretStr | None:
    """Coerce a raw secret string into a :class:`~pydantic.SecretStr`.

    ``None`` passes through unchanged (for optional secrets), and an
    existing :class:`~pydantic.SecretStr` is returned as-is (idempotent).
    """
    if value is None or isinstance(value, SecretStr):
        return value
    return SecretStr(value)


def redact(text: str, *secrets: str | SecretStr) -> str:
    """Mask occurrences of known secret substrings for log scrubbing.

    Each qualifying secret found in ``text`` is replaced by :data:`MASK`. A
    :class:`~pydantic.SecretStr` argument is accepted and unwrapped via
    :meth:`~pydantic.SecretStr.get_secret_value`. Secrets are masked
    longest-first so a short secret that is a prefix of a longer one cannot
    leave the longer one's tail unmasked. Secrets shorter than
    :data:`MIN_REDACT_LEN` (and empty ones) are ignored, since masking a tiny
    substring over-redacts surrounding text without protecting anything.

    This is **best-effort** log scrubbing, not a security boundary: it only
    masks the exact substrings it is given, in the casing they are given, and
    cannot catch transformed or partial echoes. The authoritative never-leak
    surface is :class:`~pydantic.SecretStr`.
    """
    plain = [s.get_secret_value() if isinstance(s, SecretStr) else s for s in secrets]
    for secret in sorted(plain, key=len, reverse=True):
        if len(secret) >= MIN_REDACT_LEN:
            text = text.replace(secret, MASK)
    return text
