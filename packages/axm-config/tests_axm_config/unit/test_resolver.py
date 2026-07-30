from __future__ import annotations

import pytest
from pydantic import BaseModel

from axm_config import ConfigError, UnsafeHomeError, load, set_
from axm_config.resolver import get


class _FakeStore:
    """In-memory stand-in for ``NamespaceStore`` (no real I/O)."""

    def __init__(self, data: dict[str, dict[str, object]] | None = None) -> None:
        self._data = data or {}

    def read(self, ns: str) -> dict[str, object]:
        return dict(self._data.get(ns, {}))

    def write(self, ns: str, key: str, value: object) -> None:
        self._data.setdefault(ns, {})[key] = value

    def delete(self, ns: str, key: str) -> None:
        self._data.get(ns, {}).pop(key, None)


def test_unsafe_home_error_is_config_error() -> None:
    """P0-3: ``UnsafeHomeError`` is a ``ConfigError`` so consumers catch it.

    A HOME resolving inside a git repo surfaces as ``UnsafeHomeError`` from the
    store; being a ``ConfigError`` subclass lets the CLI and :func:`load`
    degrade cleanly (their ``except ConfigError`` already covers it) instead of
    leaking the raw ``ValueError`` from ``resolve_safe``.
    """
    assert issubclass(UnsafeHomeError, ConfigError)


def test_env_wins_over_file_and_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: env value wins over the file store and the default."""
    monkeypatch.setattr(
        "axm_config.resolver._store",
        _FakeStore({"demo": {"key": "from-file"}}),
    )
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")
    assert get("demo", "key", default="from-default") == "from-env"


def test_file_wins_over_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: with no env, the file value wins over the default."""
    monkeypatch.setattr(
        "axm_config.resolver._store",
        _FakeStore({"demo": {"key": "from-file"}}),
    )
    monkeypatch.delenv("AXM_DEMO_KEY", raising=False)
    assert get("demo", "key", default="from-default") == "from-file"


def test_default_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: with neither env nor file value, the default is returned."""
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())
    monkeypatch.delenv("AXM_DEMO_KEY", raising=False)
    assert get("demo", "key", default="from-default") == "from-default"


def test_env_name_derivation(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: env name is AXM_<NS upper, dots->underscores>_<KEY upper>.

    Tested through the public ``get`` boundary: only the deterministically
    derived name ``AXM_RESEARCH_FRED_API_KEY`` resolves the value.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())
    monkeypatch.setenv("AXM_RESEARCH__FRED_API_KEY", "the-key")
    assert get("research.fred", "api_key", default=None) == "the-key"


def test_load_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC4: a required model field with no resolved value raises ConfigError."""
    from pydantic import BaseModel

    class _Cfg(BaseModel):
        api_key: str

    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())
    monkeypatch.delenv("AXM_DEMO_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        load("demo", _Cfg)


def test_set_then_get_via_file() -> None:
    """AC2, AC3: set_ persists to ~/.axm/<ns>.toml and get reads it back."""
    set_("demo", "key", "persisted")
    assert get("demo", "key", default=None) == "persisted"


def test_set_none_does_not_raise_typeerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: ``set_(ns, key, None)`` routes to delete, never a raw TypeError.

    A ``None`` value must not reach the TOML serialiser (which cannot encode
    ``None``). The preferred contract is that it deletes the key; here, via an
    in-memory store, we assert no exception is raised and the key is gone.
    """
    store = _FakeStore({"demo": {"key": "present"}})
    monkeypatch.setattr("axm_config.resolver._store", store)

    set_("demo", "key", None)

    assert store.read("demo") == {}


def test_load_populates_model_from_file() -> None:
    """AC4: load returns a model instance with fields read from the file."""

    class _Cfg(BaseModel):
        api_key: str
        retries: int

    set_("demo", "api_key", "abc123")
    set_("demo", "retries", 3)
    cfg = load("demo", _Cfg)
    assert cfg.api_key == "abc123"
    assert cfg.retries == 3


def test_env_name_no_residual_collisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AXM-2269 AC1: no two distinct (ns, key) pairs map to the same env var.

    The new scheme tightens the namespace pattern to alnum segments joined by
    dots (no ``_``, no ``-``), which structurally removes both residual
    AXM-2260 collisions:

    * literal ``__`` in a namespace vs a folded dot: ``"a__b"`` collided with
      the dotted ``"a.b"`` (both -> ``AXM_A__B_*``). ``"a__b"`` is now rejected,
      so the dotted form keeps ``AXM_A__B_C`` to itself.
    * the ns/key boundary on a single ``_``: ``("a_b", "c")`` collided with
      ``("a", "b_c")`` (both -> ``AXM_A_B_C``). ``"a_b"`` is now rejected, so
      only ``("a", "b_c")`` -> ``AXM_A_B_C`` remains.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())

    # Pair 1 collision is gone: the underscore-bearing namespace is rejected,
    # leaving the dotted form the sole owner of AXM_A__B_C.
    with pytest.raises(ConfigError):
        get("a__b", "c")
    monkeypatch.setenv("AXM_A__B_C", "dotted-only")
    assert get("a.b", "c", default=None) == "dotted-only"

    # Pair 2 collision is gone: the underscore namespace is rejected, leaving
    # only ("a", "b_c") to own AXM_A_B_C.
    with pytest.raises(ConfigError):
        get("a_b", "c")
    monkeypatch.setenv("AXM_A_B_C", "key-underscore-only")
    assert get("a", "b_c", default=None) == "key-underscore-only"


def test_env_name_always_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AXM-2269 AC2: a dash in the namespace never yields a non-POSIX env name.

    A ``-`` in the namespace would otherwise produce ``AXM_MY-NS_KEY``, which
    is not a valid POSIX identifier (``^[A-Z_][A-Z0-9_]*$``). The contract is a
    clean rejection at the public boundary rather than emitting a stray ``-``.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())
    with pytest.raises(ConfigError) as exc:
        get("my-ns", "key")
    assert "my-ns" in str(exc.value)


def test_key_with_dot_rejected_or_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AXM-2260 AC2: a key containing a dot is rejected with a clear error.

    A dot in the key would otherwise yield a non-POSIX env name
    (``AXM_A_B.C``) and an ambiguous ns/key boundary. The contract is to
    reject it at the public boundary rather than emit a raw ``.``.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())
    with pytest.raises(ConfigError) as exc:
        get("a", "b.c")
    # The error names the offending key, not a stray TypeError/KeyError.
    assert "b.c" in str(exc.value)


def test_dotted_namespace_still_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AXM-2260 AC4: dotted namespaces stay legal (only keys forbid dots).

    The chosen scheme (b) keeps namespaces permissive (dots/dashes) so
    dotted namespaces resolve normally; only the key segment is tightened.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())
    monkeypatch.setenv("AXM_A__B_C", "ok")
    assert get("a.b", "c", default=None) == "ok"


def test_env_name_injective_key_double_underscore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1, AC4: ``("a", "_b_c")`` no longer collides with ``("a.b", "c")``.

    AXM-2284 (3rd recurrence): the old ``_KEY_RE`` allowed leading/embedded
    ``__`` in a key, so the key ``"_b_c"`` forged the folded-dot ``__`` and
    ``("a", "_b_c")`` mapped to ``AXM_A__B_C`` — exactly the env name owned by
    the dotted ``("a.b", "c")``. The tightened key rule (no edge/embedded
    ``__``) rejects ``"_b_c"`` at the boundary, so the dotted form keeps
    ``AXM_A__B_C`` to itself: the two pairs are now provably distinct.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())

    # The underscore-bearing key is rejected, so it can never reach the env map.
    with pytest.raises(ConfigError):
        get("a", "_b_c")

    # The dotted pair is the sole owner of AXM_A__B_C.
    monkeypatch.setenv("AXM_A__B_C", "dotted-only")
    assert get("a.b", "c", default=None) == "dotted-only"


def test_env_name_case_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1, AC2: ``("Demo", "key")`` cannot collide with ``("demo", "key")``.

    AXM-2284: ``_env_name`` upper-cases its inputs, so ``"Demo"`` and ``"demo"``
    both folded to ``AXM_DEMO_KEY`` while the namespace pattern accepted both
    as distinct namespaces — two distinct pairs, one env name. The lowercase
    segment rule rejects the upper-cased ``"Demo"`` at the boundary, so the
    case-collision pair is unrepresentable; only the lowercase ``("demo",
    "key")`` owns ``AXM_DEMO_KEY``.
    """
    monkeypatch.setattr("axm_config.resolver._store", _FakeStore())

    # An upper-cased namespace is rejected: it can never express AXM_DEMO_KEY.
    with pytest.raises(ConfigError):
        get("Demo", "key")

    # The lowercase pair is the sole owner of AXM_DEMO_KEY.
    monkeypatch.setenv("AXM_DEMO_KEY", "lowercase-only")
    assert get("demo", "key", default=None) == "lowercase-only"
