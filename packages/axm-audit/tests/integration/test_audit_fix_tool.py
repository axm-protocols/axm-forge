"""Integration tests for AuditFixTool (AXM-1750).

Real filesystem + git + libcst. Each test seeds a minimal package on
disk, optionally git-initialises it (required for ``apply=True``), and
exercises ``AuditFixTool().execute(...)`` end-to-end.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


def test_execute_catches_internal_exception(tmp_path: Path, mocker: Any) -> None:
    """AC6: a RuntimeError from the pipeline becomes ToolResult.error."""
    mocker.patch(
        "axm_audit.core.fix.run",
        side_effect=RuntimeError("boom"),
    )

    result = AuditFixTool().execute(path=str(tmp_path))

    assert result.success is False
    assert result.error == "boom"


# ---------------------------------------------------------------------------
# Atomic apply — structured error + clean tree on failure (AXM-1768)
# ---------------------------------------------------------------------------


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def test_apply_failure_returns_structured_error_and_clean_tree(
    make_pkg_git: Callable[[dict[str, str]], Path], mocker: Any
) -> None:
    """AC2, AC4: a forced apply failure makes the tool return success=False
    with an actionable message (not a bare 'test_basic'), tree restored.
    """
    pkg = make_pkg_git({"tests/unit/test_writes.py": _MISTIERED_IO_TEST})
    before = _tree_hash(pkg / "tests")

    # Simulate the historical unguarded dict access crashing mid-apply.
    mocker.patch(
        "axm_audit.core.fix.pipeline._run_iterations",
        side_effect=KeyError("test_basic"),
    )

    result = AuditFixTool().execute(path=str(pkg), apply=True)

    assert result.success is False
    assert result.error is not None
    # The opaque bare-token error must not surface verbatim.
    assert result.error.strip() not in {"test_basic", "'test_basic'"}
    assert _tree_hash(pkg / "tests") == before
