"""Filesystem fixtures for SDK dependency-authority contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from axm.tools.dependency_reads import DependencyEnvironment


@pytest.fixture
def dependency_project(tmp_path: Path) -> tuple[DependencyEnvironment, Path]:
    """Declare two dependency distributions without executing their modules."""
    project = tmp_path / "consumer"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname="consumer"\nversion="0"\n'
        'dependencies=["fixture-api", "fixture-single"]\n'
    )
    site = tmp_path / "site"
    api = site / "fixture_api"
    api.mkdir(parents=True)
    sources = {
        "__init__.py": (
            'raise RuntimeError("dependency imports are forbidden")\n'
            "from .types import Public as Exported\n"
            "from fixture_api.types import Public as Absolute\n"
            "from . import types as module_alias\n"
        ),
        "types.py": 'class Public:\n    def load(self):\n        return "loaded"\n',
        "cycle_a.py": "from .cycle_b import Item\n",
        "cycle_b.py": "from .cycle_a import Item\n",
    }
    for name, source in sources.items():
        (api / name).write_text(source)
    (site / "single.py").write_text("class Single:\n    pass\n")
    for name, records in {
        "fixture_api": [f"fixture_api/{name}" for name in sources],
        "fixture_single": ["single.py"],
    }.items():
        dist = site / f"{name}-1.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text(f"Name: {name}\nVersion: 1\n")
        (dist / "RECORD").write_text("".join(f"{item},,\n" for item in records))
    rogue = site / "rogue"
    rogue.mkdir()
    (rogue / "__init__.py").write_text("SECRET = 42\n")
    return DependencyEnvironment(sys.executable, str(project), (str(site),)), api
