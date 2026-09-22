from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, template_chain
from axm_init.tools.check import InitCheckTool
from axm_init.tools.scaffold import InitScaffoldTool
from tests_axm_init.conftest import (
    materialize_post_copy_artifacts,
    scaffold_without_tasks,
)

pytestmark = pytest.mark.integration

_IDENTITY = {
    "org": "test-org",
    "author": "Test Author",
    "email": "test@example.com",
}


def _generate(root: Path, *, learning: bool) -> None:
    kwargs: dict[str, object] = {"name": "contrast-project", **_IDENTITY}
    if learning:
        kwargs.update({"kind": "learning", "domain": "forecasting"})
    with scaffold_without_tasks():
        result = InitScaffoldTool().execute(path=str(root), **kwargs)
    assert result.success is True, result.error
    materialize_post_copy_artifacts(root)


def _failure_ids(result: object) -> set[str]:
    data = result.data
    assert isinstance(data, dict)
    failures = data["failures"]
    assert isinstance(failures, list)
    return {str(failure["name"]) for failure in failures}


def test_learning_and_ordinary_scaffolds_run_the_same_default_checks(
    tmp_path: Path,
) -> None:
    """AC2: both generated forms run the same non-empty default check set."""
    ordinary = tmp_path / "ordinary"
    learning = tmp_path / "learning"
    _generate(ordinary, learning=False)
    _generate(learning, learning=True)

    ordinary_check = InitCheckTool().execute(path=str(ordinary))
    learning_check = InitCheckTool().execute(path=str(learning))

    assert ordinary_check.data is not None
    assert learning_check.data is not None
    ordinary_passed = int(ordinary_check.data["passed_count"])
    learning_passed = int(learning_check.data["passed_count"])
    ordinary_failures = _failure_ids(ordinary_check)
    learning_failures = _failure_ids(learning_check)
    assert ordinary_passed + len(ordinary_failures) > 0
    assert learning_passed + len(learning_failures) > 0
    assert ordinary_passed + len(ordinary_failures) == (
        learning_passed + len(learning_failures)
    )
    assert learning_failures <= ordinary_failures


def test_learning_scaffold_inherits_repository_tooling_only_from_base_layer(
    tmp_path: Path,
) -> None:
    """AC3: repository tooling is byte-identical and absent from the overlay."""
    ordinary = tmp_path / "ordinary"
    learning = tmp_path / "learning"
    _generate(ordinary, learning=False)
    _generate(learning, learning=True)

    tooling_paths = {
        "Makefile",
        "mkdocs.yml",
        ".pre-commit-config.yaml",
        *{
            path.relative_to(ordinary).as_posix()
            for path in (ordinary / ".github").rglob("*")
            if path.is_file()
        },
    }
    assert tooling_paths
    for relative in tooling_paths:
        assert (learning / relative).read_bytes() == (ordinary / relative).read_bytes()

    learning_template = template_chain(TemplateType.LEARNING, None, member=False)[
        -1
    ].path
    rendered_overlay_paths = {
        path.relative_to(learning_template).as_posix().removesuffix(".jinja")
        for path in learning_template.rglob("*")
        if path.is_file()
    }
    assert tooling_paths.isdisjoint(rendered_overlay_paths)


def test_learning_rerun_preserves_authored_makefile_and_overlay_recipe(
    tmp_path: Path,
) -> None:
    """AC4: one rerun refreshes base tooling while preserving recipe bytes."""
    root = tmp_path / "learning"
    _generate(root, learning=True)
    makefile = root / "Makefile"
    recipe = root / "src" / "contrast_project" / "learning" / "recipe.py"
    edited_recipe = recipe.read_bytes() + b"\n# user-owned recipe body\n"
    makefile.write_bytes(b"hand-written makefile\n")
    recipe.write_bytes(edited_recipe)

    _generate(root, learning=True)

    assert makefile.read_bytes() == b"hand-written makefile\n"
    assert recipe.read_bytes() == edited_recipe
