"""Integration contracts for the generated Python project template."""

from __future__ import annotations

import ast
import fnmatch
import tomllib
from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.templates import TemplateType, get_template_path


@pytest.fixture(scope="module")
def generated_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the standalone Python template with its minimal project metadata.

    Files only (``skip_tasks=True``): these contracts read the rendered
    ``pyproject.toml`` and the seed unit test, never an artifact the post-copy
    tasks produce, so running them would resolve and install 72 packages per
    test for nothing. Module-scoped because the render is read-only here.
    """
    destination = tmp_path_factory.mktemp("generated") / "generated-project"
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.STANDALONE),
            destination=destination,
            data={
                "package_name": "generated-project",
                "description": "Generated project used by integration tests",
                "org": "example-org",
                "license": "Apache-2.0",
                "license_holder": "Example Org",
                "author_name": "Example Author",
                "author_email": "author@example.com",
            },
            trust_template=True,
            skip_tasks=True,
        )
    )
    assert result.success, result.message
    return destination


@pytest.fixture(scope="module")
def generated_workspace_member(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destination = tmp_path_factory.mktemp("generated-member") / "generated-member"
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.MEMBER),
            destination=destination,
            data={
                "member_name": "generated-member",
                "workspace_name": "generated-workspace",
                "org": "example-org",
                "author_name": "Example Author",
                "author_email": "author@example.com",
            },
            trust_template=True,
            skip_tasks=True,
        )
    )
    assert result.success, result.message
    return destination


def _classifiers(project: Path) -> list[str]:
    with (project / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    classifiers = pyproject["project"]["classifiers"]
    assert isinstance(classifiers, list)
    return classifiers


def _mirror_exemptions(project: Path) -> list[str]:
    with (project / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    exemptions = pyproject["tool"]["axm-audit"]["mirror"]["exempt_tests"]
    assert isinstance(exemptions, list)
    return exemptions


@pytest.mark.integration
def test_generated_pyproject_exempts_only_seed_version_test(
    generated_project: Path,
) -> None:
    """AC1: the mirror exemption names exactly the generated seed test."""
    exemptions = _mirror_exemptions(generated_project)

    assert len(exemptions) == 1
    assert fnmatch.fnmatch("test_version.py", exemptions[0])


@pytest.mark.integration
def test_generated_mirror_exemption_does_not_hide_other_unit_tests(
    generated_project: Path,
) -> None:
    """AC2: the narrow mirror exemption cannot conceal a later unit test."""
    (exemption,) = _mirror_exemptions(generated_project)

    assert not fnmatch.fnmatch("test_resolver.py", exemption)
    assert "**" not in exemption


@pytest.mark.integration
def test_generated_seed_version_test_documents_mirror_exemption(
    generated_project: Path,
) -> None:
    """AC3: the retained seed test documents its mirror-rule exemption."""
    seed_test = generated_project / "tests" / "unit" / "test_version.py"

    assert seed_test.is_file()
    module = ast.parse(seed_test.read_text(encoding="utf-8"))
    docstring = ast.get_docstring(module)
    assert docstring
    normalized = docstring.lower()
    assert "mirror" in normalized
    assert "exempt" in normalized


@pytest.mark.integration
def test_workspace_member_default_is_private(
    generated_workspace_member: Path,
) -> None:
    """AC1: the workspace-member default prepends the private classifier."""
    assert _classifiers(generated_workspace_member) == [
        "Private :: Do Not Upload",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    ]


@pytest.mark.integration
def test_standalone_project_default_is_private(generated_project: Path) -> None:
    """AC2: the standalone-project default prepends the private classifier."""
    assert _classifiers(generated_project) == [
        "Private :: Do Not Upload",
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Typing :: Typed",
        "License :: OSI Approved :: Apache Software License",
    ]
