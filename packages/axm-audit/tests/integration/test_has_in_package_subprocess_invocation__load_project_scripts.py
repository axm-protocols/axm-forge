"""Split from ``test_pyramid_level_in_package_scripts.py``."""

import ast
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality._shared import (
    has_in_package_subprocess_invocation,
    load_project_scripts,
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
