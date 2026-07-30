from __future__ import annotations

from pydantic import BaseModel, SecretStr

from axm_vault.secrets import MASK, as_secret, redact


def test_as_secret_wraps() -> None:
    """AC1: coerces a raw string into a pydantic SecretStr."""
    secret = as_secret("tok")
    assert isinstance(secret, SecretStr)
    assert secret.get_secret_value() == "tok"


def test_repr_str_never_leak() -> None:
    """AC2, AC5: repr/str/f-string never leak; only get_secret_value reveals."""
    secret = as_secret("PLAINTEXT")
    assert "PLAINTEXT" not in repr(secret)
    assert "PLAINTEXT" not in str(secret)
    assert "PLAINTEXT" not in f"{secret}"
    assert secret.get_secret_value() == "PLAINTEXT"


def test_model_dump_never_leaks() -> None:
    """AC3: a model with a SecretStr field never leaks the value in model_dump()."""

    class Config(BaseModel):
        token: SecretStr

    model = Config(token=as_secret("PLAINTEXT"))
    dumped = model.model_dump()
    assert "PLAINTEXT" not in str(dumped)
    assert "PLAINTEXT" not in model.model_dump_json()


def test_redact_masks_secret() -> None:
    """AC4: redact masks occurrences of a known secret substring with ********."""
    result = redact("auth=PLAINTEXT now", "PLAINTEXT")
    assert "PLAINTEXT" not in result
    assert "********" in result


def test_redact_empty_secrets_noop() -> None:
    """AC4: redact with no secrets returns the text unchanged."""
    assert redact("text") == "text"


def test_redact_length_sorted_and_secretstr() -> None:
    """AC3: redact is length-sorted, skips very short secrets, accepts SecretStr.

    Length-sort: when a short secret is a prefix of a longer one, masking the
    longer one first prevents a partial-mask artifact leaking the tail. A
    very-short secret (below the minimum length) is ignored so common
    substrings are not over-masked. A :class:`SecretStr` argument is unwrapped
    via ``get_secret_value()`` and masked like a raw string.
    """
    # Longest-first masking: "abcdef" must be masked before its prefix "abc",
    # otherwise the tail "def" would leak. Order of args is shortest-first on
    # purpose to prove the function sorts internally.
    result = redact("X=abcdef", "abc", "abcdef")
    assert "abcdef" not in result
    assert "def" not in result
    assert MASK in result

    # Very-short secret is ignored (would otherwise mask every "a").
    short = redact("a banana", "a")
    assert short == "a banana"

    # SecretStr input is unwrapped and masked.
    wrapped = redact("auth=PLAINTEXT now", SecretStr("PLAINTEXT"))
    assert "PLAINTEXT" not in wrapped
    assert MASK in wrapped
