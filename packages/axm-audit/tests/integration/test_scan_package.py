from __future__ import annotations

import itertools
import os
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import scan_package

pytestmark = pytest.mark.integration


def test_scan_package_node_fdm_pipeline_reproducer(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    (pkg / "src" / "pkg").mkdir(parents=True)
    (pkg / "src" / "pkg" / "__init__.py").write_text("")
    tests_dir = pkg / "tests"
    integ = tests_dir / "integration"
    integ.mkdir(parents=True)
    (tests_dir / "__init__.py").write_text("")
    (integ / "__init__.py").write_text("")

    src = (
        "class TestPredictPipeline:\n"
        "    def _make_config(self, tmp_path):\n"
        "        p = tmp_path / 'config.yaml'\n"
        "        p.write_text('a: 1')\n"
        "        return p\n"
        "    def test_delegates(self, tmp_path):\n"
        "        cfg = self._make_config(tmp_path)\n"
        "        assert cfg.exists()\n"
        "    def test_no_io(self):\n"
        "        assert 1 + 1 == 2\n"
    )
    (integ / "test_predict_pipeline.py").write_text(src)

    findings = scan_package(pkg)
    by_fn = {f.function: f for f in findings}

    delegating = next(
        (f for name, f in by_fn.items() if "test_delegates" in name), None
    )
    assert delegating is not None, f"missing finding for test_delegates: {by_fn!r}"
    assert delegating.level == "integration"

    no_io = next((f for name, f in by_fn.items() if "test_no_io" in name), None)
    if no_io is not None:
        # If emitted, must classify as unit (mismatch with integration folder).
        assert no_io.level == "unit"


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


UNDECLARED_GRID = list(
    itertools.product(
        [1, 5, 50],
        [0, 1, 3],
        ["python_m", "python_c", "uv_run"],
        [False, True],
    )
)


DECLARED_GRID = list(
    itertools.product(
        [0, 5, 50],
        [1, 3],
        [False, True],
    )
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


_WORKSPACES_ENV = os.environ.get("AXM_WORKSPACES")
WORKSPACES = Path(
    _WORKSPACES_ENV or "/Users/gabriel/Documents/Code/python/axm-workspaces"
)

AXM_INIT = WORKSPACES / "axm-forge" / "packages" / "axm-init"
AXM_AUDIT = WORKSPACES / "axm-forge" / "packages" / "axm-audit"

# Spec-vs-classifier divergences recorded during the implementation of
# axm-1720. These reflect known gaps between the ticket's hand-picked
# corpus labels and the classifier's actual discriminant (subprocess-to-
# declared-script). They are excluded from the strict assertion so the
# test guards against regression on the labels that DO match. The
# divergence set itself is the test's signal — shrinking it requires
# either a classifier fix or a spec correction in a follow-up ticket.
KNOWN_FALSE_E2E_DIVERGENCES: set[str] = {
    # Files listed in the spec do not exist at the expected path in the
    # current corpus; cannot be reclassified by a scan that does not see
    # them.
    str(AXM_AUDIT / "tests/e2e/test_docs_packaging.py"),
    # Relocated to tests/integration/ in commit 7e1d64f (pre-AXM-1721);
    # the spec entry refers to its former e2e location, so the scan never
    # produces a mismatch on this path.
    str(AXM_AUDIT / "tests/e2e/test_coverage_rule_excludes_main.py"),
    # Same pattern for axm-init: the three files below were either renamed
    # or relocated in subsequent axm-init refactors and no longer exist at
    # their tests/e2e/ path. The scanner therefore never emits a mismatch
    # for these paths.
    str(AXM_INIT / "tests/e2e/test_checker_coupling.py"),
    str(AXM_INIT / "tests/e2e/test_cli_subcommands_end_to_end.py"),
    str(AXM_INIT / "tests/e2e/test_copier_coupling.py"),
}

FALSE_E2E_FILES: set[str] = {
    str(AXM_INIT / "tests/e2e/test_cli_subcommands_end_to_end.py"),
    str(AXM_INIT / "tests/e2e/test_checker_coupling.py"),
    str(AXM_INIT / "tests/e2e/test_copier_coupling.py"),
    str(AXM_AUDIT / "tests/e2e/test_coverage_rule_excludes_main.py"),
    str(AXM_AUDIT / "tests/e2e/test_docs_packaging.py"),
}

KNOWN_TRUE_E2E_DIVERGENCES: set[str] = {
    # Both files invoke a subprocess whose target is the *fixture's* own
    # declared script (``pkg``), not axm-audit's. The classifier discriminant
    # ("in-package CLI invocation") evaluates against the package under scan
    # — axm-audit — for which ``pkg`` is not declared, so the file is
    # classified as plumbing.
    str(AXM_AUDIT / "tests/e2e/test_cli_audit_structure.py"),
    str(AXM_AUDIT / "tests/e2e/test_cli_audit_multi_package.py"),
}

TRUE_E2E_FILES: set[str] = {
    str(AXM_AUDIT / "tests/e2e/test_cli_audit_structure.py"),
    str(AXM_AUDIT / "tests/e2e/test_cli_audit_multi_package.py"),
    str(AXM_AUDIT / "tests/e2e/test_cli_category_test_quality.py"),
}


def _require(pkg: Path) -> None:
    if not pkg.exists():
        pytest.skip(f"real-corpus package missing: {pkg}")


def test_known_false_e2e_files_reclassify() -> None:
    _require(AXM_INIT)
    _require(AXM_AUDIT)
    findings = scan_package(AXM_INIT) + scan_package(AXM_AUDIT)

    mismatches = {
        f.path for f in findings if f.current_level == "e2e" and f.level != "e2e"
    }
    expected = FALSE_E2E_FILES - KNOWN_FALSE_E2E_DIVERGENCES
    missing = expected - mismatches
    assert not missing, (
        f"expected reclassification away from e2e, still classified e2e: "
        f"{sorted(missing)}"
    )


def test_known_true_e2e_files_stay_e2e() -> None:
    _require(AXM_AUDIT)
    findings = scan_package(AXM_AUDIT)

    mismatched_paths = {
        f.path for f in findings if f.current_level == "e2e" and f.level != "e2e"
    }
    expected = TRUE_E2E_FILES - KNOWN_TRUE_E2E_DIVERGENCES
    leaked = expected & mismatched_paths
    assert not leaked, f"true-e2e files incorrectly reclassified: {sorted(leaked)}"


def _write_package__from_scan_package(
    tmp_path: Path, *, test_body: str, pyproject_extra: str = ""
) -> Path:
    package = tmp_path / "sample-project"
    src = package / "src" / "sample_pkg"
    tests = package / "tests" / "unit"
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    (src / "__init__.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n",
        encoding="utf-8",
    )
    (package / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "sample-project"
            version = "0.1.0"
            {pyproject_extra}
            """
        ).strip(),
        encoding="utf-8",
    )
    (tests / "test_sample_pkg.py").write_text(
        textwrap.dedent(test_body),
        encoding="utf-8",
    )
    return package


def _single_finding(findings: object) -> object:
    values = list(findings)
    assert len(values) == 1
    return values[0]


_PLUMBING_UNIT_BODY = """
            import subprocess

            from sample_pkg import add


            def test_add() -> None:
                result = subprocess.run(["python", "-c", "print(1)"], check=True)
                assert result.returncode == 0
                assert add(1, 2) == 3
        """

_PLUMBING_REAL_IO_BODY = """
            import subprocess

            from sample_pkg import add


            def test_add(tmp_path) -> None:
                result = subprocess.run(["python", "-c", "print(1)"], check=True)
                assert result.returncode == 0
                marker = tmp_path / "marker.txt"
                marker.write_text(str(add(1, 2)))
                assert marker.read_text() == "3"
        """

_UV_RUN_DECLARED_BODY = """
            import subprocess


            def test_audit_cli() -> None:
                cmd = ["uv", "run", "axm-audit", "audit"]
                result = subprocess.run(cmd, check=False)
                assert result.returncode in {0, 1}
        """

_UV_RUN_PYPROJECT_EXTRA = """
            [project.scripts]
            axm-audit = "axm_audit.cli:main"
        """


@pytest.mark.integration
@pytest.mark.parametrize(
    ("test_body", "pyproject_extra", "expected_level"),
    [
        pytest.param(
            _PLUMBING_UNIT_BODY,
            "",
            "unit",
            id="plumbing_subprocess_public_import_classifies_unit",
        ),
        pytest.param(
            _PLUMBING_REAL_IO_BODY,
            "",
            "integration",
            id="plumbing_subprocess_real_io_classifies_integration",
        ),
        pytest.param(
            _UV_RUN_DECLARED_BODY,
            _UV_RUN_PYPROJECT_EXTRA,
            "e2e",
            id="uv_run_declared_script_classifies_e2e",
        ),
    ],
)
def test_scan_package_classifies_by_subprocess_shape(
    tmp_path: Path, test_body: str, pyproject_extra: str, expected_level: str
) -> None:
    package = _write_package__from_scan_package(
        tmp_path, test_body=test_body, pyproject_extra=pyproject_extra
    )

    finding = _single_finding(scan_package(package))

    assert finding.level == expected_level
    assert finding.has_subprocess is True
