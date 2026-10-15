"""Explicit instruments never bootstrap or choose a local environment."""

import sys
from pathlib import Path

import pytest

from axm_ingot import instrument_command

pytestmark = pytest.mark.integration


def test_instrument_command_ignores_contaminated_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use only the declared overlay, regardless of inherited variables."""
    python = tmp_path / "principal/.venv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to("/usr/bin/python3")
    source = tmp_path / "candidate/src"
    source.mkdir(parents=True)
    monkeypatch.setenv("PYTHONPATH", "/contaminated")
    monkeypatch.setenv("VIRTUAL_ENV", "/contaminated/.venv")
    monkeypatch.setenv("PYTHONHOME", "/contaminated/python")
    monkeypatch.setenv("PYTHONNOUSERSITE", "0")
    command, env = instrument_command(
        ["pytest", "--version"],
        interpreter=str(python),
        pythonpath=(str(source),),
        package_root=str(source.parent),
    )
    assert command == [str(python), "-m", "pytest", "--version"]
    assert env["PYTHONPATH"] == str(source)
    assert "VIRTUAL_ENV" not in env
    assert "PYTHONHOME" not in env
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PATH"].split(":")[0] == str(python.parent)


def test_instrument_command_missing_binary_is_explicit(tmp_path: Path) -> None:
    """Unknown binaries must exist beside the declared interpreter."""
    python = tmp_path / "bin/python"
    python.parent.mkdir()
    python.symlink_to("/usr/bin/python3")
    with pytest.raises(ValueError, match="instrument"):
        instrument_command(
            ["not-installed"],
            interpreter=str(python),
            pythonpath=(),
            package_root=str(tmp_path),
        )


@pytest.mark.parametrize("command", ["/usr/bin/true", "../outside", "uv"])
def test_instrument_command_refuses_escape(tmp_path: Path, command: str) -> None:
    """Only named instruments in the declared runtime may run."""
    python = tmp_path / "bin/python"
    python.parent.mkdir()
    python.symlink_to("/usr/bin/python3")
    with pytest.raises(ValueError, match="instrument"):
        instrument_command(
            [command],
            interpreter=str(python),
            pythonpath=(),
            package_root=str(tmp_path),
        )


@pytest.mark.parametrize("layout", ["src", "flat"])
def test_declared_target_precedes_dependency_paths(tmp_path: Path, layout: str) -> None:
    """Always overlay the package itself, without guessing another checkout."""
    target = tmp_path / "target"
    target.mkdir()
    own = target / "src" if layout == "src" else target
    own.mkdir(exist_ok=True)
    dependency = tmp_path / "dependency"
    dependency.mkdir()
    _, environment = instrument_command(
        ["pytest", "--version"],
        interpreter=sys.executable,
        package_root=str(target),
        pythonpath=(str(dependency), str(own), str(dependency)),
    )
    assert environment["PYTHONPATH"].split(":") == [str(own), str(dependency)]
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"


def test_target_src_symlink_cannot_expand_authority(tmp_path: Path) -> None:
    """A src symlink must remain inside the target or be explicitly declared."""
    target = tmp_path / "target"
    target.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (target / "src").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="source"):
        instrument_command(
            ["pytest"],
            interpreter=sys.executable,
            package_root=str(target),
            pythonpath=(),
        )
    _, environment = instrument_command(
        ["pytest"],
        interpreter=sys.executable,
        package_root=str(target),
        pythonpath=(str(external),),
    )
    assert environment["PYTHONPATH"] == str(external)
