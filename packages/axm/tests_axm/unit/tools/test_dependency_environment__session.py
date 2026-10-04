"""Declared runtimes confer no extra execution roots."""

from pathlib import Path

import pytest

import axm
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract


def test_session_environment_preserves_venv_python(tmp_path: Path) -> None:
    """Preserve the lexical venv interpreter path."""
    interpreter = tmp_path / "venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to("/usr/bin/python3")
    env = axm.DependencyEnvironment(str(interpreter), str(tmp_path), ())
    contract = WriteContract(str(tmp_path), dependency_environment=env)
    with dependency_read_context(contract):
        assert axm.session_dependency_environment(tmp_path) == env
        assert axm.session_dependency_environment(tmp_path / "tests") == env


@pytest.mark.parametrize("missing", [False, True])
def test_session_environment_refuses_undeclared_runtime(
    tmp_path: Path, missing: bool
) -> None:
    """Read roots do not grant execution runtimes."""
    env = (
        None
        if missing
        else axm.DependencyEnvironment("/usr/bin/python3", str(tmp_path))
    )
    contract = WriteContract(
        str(tmp_path), dependency_environment=env, read_roots=(str(tmp_path.parent),)
    )
    with dependency_read_context(contract), pytest.raises(ValueError, match="runtime"):
        axm.session_dependency_environment(tmp_path.parent)


def test_session_environment_unbound_is_legacy(tmp_path: Path) -> None:
    """Unbound transport retains legacy lookup."""
    with dependency_read_context(None):
        assert axm.session_dependency_environment(tmp_path) is None


def test_session_environment_refuses_conflicting_runtime(tmp_path: Path) -> None:
    """Equal roots with different interpreters cannot depend on list order."""
    first = axm.DependencyEnvironment("/usr/bin/python3", str(tmp_path))
    second = axm.DependencyEnvironment("/other/python", str(tmp_path))
    contract = WriteContract(
        str(tmp_path), dependency_environment=first, dependency_environments=(second,)
    )
    with (
        dependency_read_context(contract),
        pytest.raises(ValueError, match="ambiguous"),
    ):
        axm.session_dependency_environment(tmp_path)
