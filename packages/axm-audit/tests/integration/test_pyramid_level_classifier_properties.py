from __future__ import annotations

import itertools
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import scan_package

pytestmark = pytest.mark.integration

__all__: list[str] = []


PYPROJECT_BASE = """\
[project]
name = "sample_pkg"
version = "0.0.0"
requires-python = ">=3.12"
"""

PYPROJECT_WITH_SCRIPT = PYPROJECT_BASE + textwrap.dedent(
    """
    [project.scripts]
    sample-cli = "sample_pkg.cli:main"
    """
)


def _write_package(
    root: Path,
    *,
    pyproject: str,
    test_body: str,
    test_subdir: str = "e2e",
) -> None:
    (root / "pyproject.toml").write_text(pyproject)
    src = root / "src" / "sample_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "cli.py").write_text("def main() -> None:\n    pass\n")
    tests_dir = root / "tests" / test_subdir
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("")
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_sample.py").write_text(test_body)


def _in_memory_calls(n: int) -> str:
    return "\n".join(f"    x{i} = 1 + {i}" for i in range(n)) or "    pass"


def _subprocess_call(flavor: str, target: str) -> str:
    if flavor == "python_m":
        return f'    subprocess.run(["python", "-m", "{target}"])'
    if flavor == "python_c":
        return '    subprocess.run(["python", "-c", "print(1)"])'
    if flavor == "uv_run":
        return f'    subprocess.run(["uv", "run", "{target}"])'
    raise ValueError(flavor)


def _real_io_block() -> str:
    return (
        "    p = tmp_path / 'x.txt'\n"
        "    p.write_text('hi')\n"
        "    assert p.read_text() == 'hi'\n"
    )


def _build_test_body(
    *,
    n_in_memory: int,
    m_subprocess: int,
    subprocess_flavor: str,
    subprocess_target: str,
    real_io: bool,
) -> str:
    lines: list[str] = []
    if m_subprocess > 0:
        lines.append("import subprocess")
        lines.append("")
    sig = "tmp_path" if real_io else ""
    lines.append(f"def test_scenario({sig}):")
    lines.append(_in_memory_calls(n_in_memory))
    for _ in range(m_subprocess):
        lines.append(_subprocess_call(subprocess_flavor, subprocess_target))
    if real_io:
        lines.append(_real_io_block())
    lines.append("    assert True")
    return "\n".join(lines) + "\n"


UNDECLARED_GRID = list(
    itertools.product(
        [1, 5, 50],
        [0, 1, 3],
        ["python_m", "python_c", "uv_run"],
        [False, True],
    )
)


@pytest.mark.parametrize(
    ("n_in_memory", "m_subprocess", "flavor", "real_io"),
    UNDECLARED_GRID,
)
def test_undeclared_subprocess_never_promotes_to_e2e(
    tmp_path: Path,
    n_in_memory: int,
    m_subprocess: int,
    flavor: str,
    real_io: bool,
) -> None:
    body = _build_test_body(
        n_in_memory=n_in_memory,
        m_subprocess=m_subprocess,
        subprocess_flavor=flavor,
        subprocess_target="some_other_tool",
        real_io=real_io,
    )
    _write_package(tmp_path, pyproject=PYPROJECT_WITH_SCRIPT, test_body=body)

    findings = scan_package(tmp_path)
    levels = {f.level for f in findings if f.function == "test_scenario"}

    assert "e2e" not in levels, f"unexpected e2e promotion: {findings}"
    expected = "integration" if real_io else "unit"
    assert levels == {expected}, f"expected {expected!r}, got {levels!r}"


DECLARED_GRID = list(
    itertools.product(
        [0, 5, 50],
        [1, 3],
        [False, True],
    )
)


@pytest.mark.parametrize(
    ("n_in_memory", "m_subprocess", "real_io"),
    DECLARED_GRID,
)
def test_declared_script_subprocess_always_promotes_to_e2e(
    tmp_path: Path,
    n_in_memory: int,
    m_subprocess: int,
    real_io: bool,
) -> None:
    body = _build_test_body(
        n_in_memory=n_in_memory,
        m_subprocess=m_subprocess,
        subprocess_flavor="uv_run",
        subprocess_target="sample-cli",
        real_io=real_io,
    )
    _write_package(tmp_path, pyproject=PYPROJECT_WITH_SCRIPT, test_body=body)

    findings = scan_package(tmp_path)
    scenario = [f for f in findings if f.function == "test_scenario"]

    assert scenario, "classifier produced no finding for test_scenario"
    assert all(f.level == "e2e" for f in scenario), (
        f"expected e2e for declared-script subprocess, got "
        f"{[f.level for f in scenario]}"
    )
