"""Unit tests for the shared ``[paths]`` roots.

The contract worth protecting is the *additive* one: with nothing configured a
consumer must observe exactly its own constant, so wiring a package up cannot
change behaviour. The rest covers precedence (``env > file > default``) and the
in-repo refusal that keeps runtime state out of a git checkout.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_config.paths import (
    PATHS_NAMESPACE,
    get_path,
    protocols_dir,
    quality_dir,
    sessions_root,
    warden_socket,
)
from axm_config.resolver import ConfigError, set_


def test_get_path_returns_default_untouched_when_unconfigured() -> None:
    """An unconfigured key yields the caller's constant, not a normalised copy."""
    default = Path("~/axm/sessions")
    assert get_path("sessions_root", default=default) == default


def test_get_path_reads_the_file_layer(tmp_path: Path) -> None:
    target = tmp_path / "configured"
    set_(PATHS_NAMESPACE, "sessions_root", str(target))
    assert get_path("sessions_root", default=Path("/unused")) == target.resolve()


def test_env_outranks_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``env > file`` -- the resolver's precedence must survive normalisation."""
    from_file = tmp_path / "from-file"
    from_env = tmp_path / "from-env"
    set_(PATHS_NAMESPACE, "sessions_root", str(from_file))
    monkeypatch.setenv("AXM_PATHS_SESSIONS_ROOT", str(from_env))
    assert get_path("sessions_root", default=Path("/unused")) == from_env.resolve()


def test_configured_tilde_is_expanded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXM_PATHS_QUALITY_DIR", "~/elsewhere/quality")
    resolved = get_path("quality_dir", default=Path("/unused"))
    assert resolved.is_absolute()
    assert "~" not in str(resolved)


def test_configured_in_repo_path_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runtime state must never be steered into a git checkout."""
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setenv("AXM_PATHS_SESSIONS_ROOT", str(checkout / "sessions"))
    with pytest.raises(ConfigError, match="in-repo"):
        get_path("sessions_root", default=Path("/unused"))


def test_in_repo_default_is_not_refused(tmp_path: Path) -> None:
    """The default is code, not user input: validating it would break installs."""
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    default = checkout / "sessions"
    assert get_path("sessions_root", default=default) == default


def test_non_string_configured_value_is_refused() -> None:
    set_(PATHS_NAMESPACE, "sessions_root", 42)
    with pytest.raises(ConfigError, match="expected a string"):
        get_path("sessions_root", default=Path("/unused"))


@pytest.mark.parametrize(
    ("getter", "suffix"),
    [
        (sessions_root, Path("axm/sessions")),
        (quality_dir, Path("axm/quality")),
        (protocols_dir, Path("axm/protocols")),
        (warden_socket, Path(".axm/warden.sock")),
    ],
)
def test_builtin_defaults_match_the_constants_they_replace(
    getter: Callable[[], Path], suffix: Path
) -> None:
    """Each getter's built-in default is the constant consumers declare today."""
    assert getter() == Path.home() / suffix


@pytest.mark.parametrize(
    ("getter", "key"),
    [
        (sessions_root, "sessions_root"),
        (quality_dir, "quality_dir"),
        (protocols_dir, "protocols_dir"),
        (warden_socket, "warden_socket"),
    ],
)
def test_each_getter_reads_its_own_key(
    getter: Callable[[], Path],
    key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / key
    monkeypatch.setenv(f"AXM_PATHS_{key.upper()}", str(target))
    assert getter() == target.resolve()


def test_caller_default_overrides_the_builtin_one(tmp_path: Path) -> None:
    """A migrating caller keeps its own constant while nothing is configured."""
    own = tmp_path / "legacy-root"
    assert sessions_root(default=own) == own
