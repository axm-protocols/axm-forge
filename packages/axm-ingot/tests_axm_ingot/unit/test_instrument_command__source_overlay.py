"""Target ownership precedes explicit dependency source overlays."""

import sys
from pathlib import Path

import pytest

from axm_ingot import instrument_command


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
