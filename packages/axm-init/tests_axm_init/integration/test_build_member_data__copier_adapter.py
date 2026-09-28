from __future__ import annotations

import ast
import tomllib
from fnmatch import fnmatch
from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core import build_member_data
from axm_init.core.templates import TemplateType, get_template_path


@pytest.fixture
def generated_member(tmp_path: Path) -> Path:
    """Generate one workspace member through the real Copier boundary."""
    destination = tmp_path / "axm-sample"
    data = build_member_data(
        member_name="axm-sample",
        workspace_name="axm-sample-workspace",
        scaffold_data={
            "org": "axm-protocols",
            "author_name": "AXM Maintainer",
            "author_email": "maintainer@example.com",
            "license": "MIT",
            "description": "Generated member used by integration tests.",
        },
    )
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.MEMBER),
            destination=destination,
            data=data,
            trust_template=True,
        )
    )
    assert result.success, result.message
    return destination


def _mirror_exemptions(destination: Path) -> list[str]:
    with (destination / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    exemptions = pyproject["tool"]["axm-audit"]["mirror"]["exempt_tests"]
    assert isinstance(exemptions, list)
    return exemptions


@pytest.mark.integration
def test_generated_member_exempts_only_seed_test(generated_member: Path) -> None:
    """AC1: the generated mirror config exempts exactly the seed test."""
    exemptions = _mirror_exemptions(generated_member)

    assert len(exemptions) == 1
    assert fnmatch("test_version.py", exemptions[0])


@pytest.mark.integration
def test_generated_member_exemption_stays_narrow(generated_member: Path) -> None:
    """AC2: the seed exemption cannot hide another orphan unit test."""
    [exemption] = _mirror_exemptions(generated_member)

    assert not fnmatch("test_resolver.py", exemption)
    assert "**" not in exemption


@pytest.mark.integration
def test_generated_seed_test_documents_mirror_exemption(
    generated_member: Path,
) -> None:
    """AC3: the retained seed test documents its mirror-rule exemption."""
    seed_tests = list(generated_member.glob("tests_*/unit/test_version.py"))

    assert len(seed_tests) == 1
    docstring = ast.get_docstring(ast.parse(seed_tests[0].read_text()))
    assert docstring
    assert "mirror" in docstring.casefold()
    assert "exempt" in docstring.casefold()


_LONG_SUMMARY = (
    "Judged-phase composition on axm-dag: typed verdicts, classified evaluators,"
    " one feedback turn, waivers on replayed proof."
)


def _render_member(tmp_path: Path, description: str) -> tuple[bool, str, Path]:
    destination = tmp_path / "axm-long"
    data = build_member_data(
        member_name="axm-long",
        workspace_name="axm-long-workspace",
        scaffold_data={
            "org": "axm-protocols",
            "author_name": "AXM Maintainer",
            "author_email": "maintainer@example.com",
            "license": "MIT",
            "description": description,
        },
    )
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.MEMBER),
            destination=destination,
            data=data,
            trust_template=True,
        )
    )
    return result.success, result.message, destination


@pytest.mark.integration
def test_member_accepts_a_pep621_summary_longer_than_80_chars(
    tmp_path: Path,
) -> None:
    """A one-line summary beyond 80 chars is kept whole and wrapped in the docstring."""
    assert len(_LONG_SUMMARY) > 88
    success, message, destination = _render_member(tmp_path, _LONG_SUMMARY)

    assert success, message
    with (destination / "pyproject.toml").open("rb") as stream:
        assert tomllib.load(stream)["project"]["description"] == _LONG_SUMMARY
    init = (destination / "src/axm_long/__init__.py").read_text()
    docstring = ast.get_docstring(ast.parse(init))
    assert docstring is not None
    assert " ".join(docstring.split()) == f"axm-long. {_LONG_SUMMARY}"
    assert max(len(line) for line in init.splitlines()) <= 88


@pytest.mark.integration
@pytest.mark.parametrize("description", ["two\nlines", "x" * 513])
def test_member_refuses_a_summary_pypi_would_refuse(
    tmp_path: Path, description: str
) -> None:
    """Multi-line or over-512-char summaries are invalid core-metadata Summaries."""
    success, message, _ = _render_member(tmp_path, description)

    assert not success
    assert "Validation error for question 'description'" in message
