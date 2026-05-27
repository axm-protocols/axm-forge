"""Integration tests for AuditFixTool (AXM-1750).

Real filesystem + git + libcst. Each test seeds a minimal package on
disk, optionally git-initialises it (required for ``apply=True``), and
exercises ``AuditFixTool().execute(...)`` end-to-end.
"""

from __future__ import annotations

import importlib.metadata
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.tools.audit_fix import AuditFixTool

pytestmark = pytest.mark.integration


_PYPROJECT = (
    '[project]\nname = "mypkg"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
)

_MISTIERED_IO_TEST = (
    "from pathlib import Path\n"
    "\n"
    "from mypkg import touch\n"
    "\n"
    "\n"
    "def test_writes_a_file(tmp_path: Path) -> None:\n"
    "    p = tmp_path / 'x.txt'\n"
    "    p.write_text('hello')\n"
    "    assert p.read_text() == 'hello'\n"
    "    touch()\n"
)

_CANONICAL_UNIT_TEST = (
    "from mypkg import greet\n"
    "\n"
    "\n"
    "def test_greet_returns_hello() -> None:\n"
    "    assert greet() == 'hello'\n"
)

_PKG_INIT = (
    "def greet() -> str:\n"
    "    return 'hello'\n"
    "\n"
    "\n"
    "def touch() -> None:\n"
    "    return None\n"
)


@pytest.fixture
def make_pkg_git(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Build a minimal git-initialised package with the given source files."""

    def _make(sources: dict[str, str]) -> Path:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text(_PYPROJECT)
        (pkg / "src" / "mypkg").mkdir(parents=True)
        (pkg / "src" / "mypkg" / "__init__.py").write_text(_PKG_INIT)
        (pkg / "tests").mkdir()
        for rel, content in sources.items():
            f = pkg / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        subprocess.run(["git", "init", "-q"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "config", "user.name", "t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "add", "-A"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"],  # noqa: S607
            cwd=pkg,
            check=True,
            capture_output=True,
        )
        return pkg

    return _make


def test_execute_dry_run_returns_data_and_text(
    make_pkg_git: Callable[[dict[str, str]], Path],
) -> None:
    """AC2: dry-run on a canonical clean pkg → success, no ops, text rendered."""
    pkg = make_pkg_git({"tests/unit/test_greet.py": _CANONICAL_UNIT_TEST})

    result = AuditFixTool().execute(path=str(pkg), apply=False)

    assert result.success is True
    assert result.data is not None
    assert result.data["ops"] == []
    assert result.text is not None
    assert "(no deterministic ops planned)" in result.text


def test_execute_apply_then_dry_run_converges(
    make_pkg_git: Callable[[dict[str, str]], Path],
) -> None:
    """AC3: apply mutates the tree; the next dry-run reports zero ops."""
    pkg = make_pkg_git({"tests/unit/test_writes.py": _MISTIERED_IO_TEST})

    applied = AuditFixTool().execute(path=str(pkg), apply=True)

    assert applied.success is True
    assert applied.data is not None
    assert len(applied.data["ops"]) > 0

    follow_up = AuditFixTool().execute(path=str(pkg), apply=False)

    assert follow_up.success is True
    assert follow_up.data is not None
    assert follow_up.data["ops"] == []


def test_execute_rules_filter_passes_through(
    make_pkg_git: Callable[[dict[str, str]], Path],
) -> None:
    """AC5: rules filter restricts the pipeline to the named rule(s)."""
    pkg = make_pkg_git(
        {
            "tests/unit/test_writes.py": _MISTIERED_IO_TEST,
            "tests/integration/test_x.py": _CANONICAL_UNIT_TEST,
        }
    )

    result = AuditFixTool().execute(
        path=str(pkg),
        apply=False,
        rules=["TEST_QUALITY_FILE_NAMING"],
    )

    assert result.success is True
    assert result.data is not None
    relocate_ops = [op for op in result.data["ops"] if op["kind"] == "relocate"]
    assert relocate_ops == []


def test_axm_tools_entry_point_resolves_audit_fix() -> None:
    """AC7: 'audit_fix' is registered in the axm.tools entry-point group."""
    eps = importlib.metadata.entry_points(group="axm.tools")
    names = {ep.name for ep in eps}

    assert "audit_fix" in names, (
        "audit_fix entry point not registered; re-run `uv sync` or "
        "`uv pip install -e .` after editing pyproject.toml"
    )

    audit_fix_ep = next(ep for ep in eps if ep.name == "audit_fix")
    loaded = audit_fix_ep.load()
    assert loaded is AuditFixTool


def test_audit_fix_dry_run_on_self_is_clean(tmp_path: Path) -> None:
    """AC9: audit_fix dry-run plans zero ops on an empty project.

    Sanity check that the dispatcher (AuditFixTool.execute →
    core.fix.pipeline.run → format_report) wires up correctly and returns
    a ``data["ops"] == []`` empty plan when the input tree has no test
    files to relocate / rename / split.
    """
    tool = AuditFixTool()
    result = tool.execute(path=str(tmp_path), apply=False)

    assert result.success, result.error
    assert result.data is not None
    assert result.data["ops"] == []
