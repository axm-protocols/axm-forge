from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import (
    has_in_package_subprocess_invocation,
    load_project_scripts,
    scan_package,
)


@pytest.mark.integration
def test_project_scripts_are_loaded_from_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project.scripts]\naxm-audit = 'axm_audit.cli:app'\n",
        encoding="utf-8",
    )
    source = 'subprocess.run(["uv", "run", "axm-audit", "audit"])'
    module_ast = ast.parse(source)
    call = next(node for node in ast.walk(module_ast) if isinstance(node, ast.Call))

    assert has_in_package_subprocess_invocation(
        call=call,
        module_ast=module_ast,
        project_scripts=load_project_scripts(tmp_path),
    )


@pytest.mark.integration
def test_plumbing_subprocess_public_import_classifies_unit(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        test_body="""
            import subprocess

            from sample_pkg import add


            def test_add() -> None:
                result = subprocess.run(["python", "-c", "print(1)"], check=True)
                assert result.returncode == 0
                assert add(1, 2) == 3
        """,
    )

    finding = _single_finding(scan_package(package))

    assert finding.level == "unit"
    assert finding.has_subprocess is True


@pytest.mark.integration
def test_plumbing_subprocess_real_io_classifies_integration(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        test_body="""
            import subprocess

            from sample_pkg import add


            def test_add(tmp_path) -> None:
                result = subprocess.run(["python", "-c", "print(1)"], check=True)
                assert result.returncode == 0
                marker = tmp_path / "marker.txt"
                marker.write_text(str(add(1, 2)))
                assert marker.read_text() == "3"
        """,
    )

    finding = _single_finding(scan_package(package))

    assert finding.level == "integration"
    assert finding.has_subprocess is True


@pytest.mark.integration
def test_uv_run_declared_script_classifies_e2e(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        pyproject_extra="""
            [project.scripts]
            axm-audit = "axm_audit.cli:main"
        """,
        test_body="""
            import subprocess


            def test_audit_cli() -> None:
                cmd = ["uv", "run", "axm-audit", "audit"]
                result = subprocess.run(cmd, check=False)
                assert result.returncode in {0, 1}
        """,
    )

    finding = _single_finding(scan_package(package))

    assert finding.level == "e2e"
    assert finding.has_subprocess is True


def _write_package(
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
