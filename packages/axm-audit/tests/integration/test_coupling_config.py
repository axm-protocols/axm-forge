from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture import CouplingMetricRule
from axm_audit.core.rules.architecture.coupling import (
    read_coupling_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pyproject(tmp_path: Path, content: str) -> None:
    """Write a pyproject.toml into *tmp_path*."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(content),
        encoding="utf-8",
    )


def _make_src_module(
    tmp_path: Path,
    pkg: str,
    module: str,
    n_imports: int,
) -> None:
    """Create a source module that imports *n_imports* stdlib modules."""
    src = tmp_path / "src" / pkg
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")

    # Generate unique stdlib imports so fan-out == n_imports
    stdlib_modules = [
        "os",
        "sys",
        "json",
        "re",
        "math",
        "io",
        "csv",
        "ast",
        "copy",
        "time",
        "uuid",
        "enum",
        "types",
        "shutil",
        "string",
        "random",
        "hashlib",
        "logging",
        "pathlib",
        "textwrap",
        "functools",
        "itertools",
        "collections",
        "contextlib",
        "dataclasses",
    ]
    lines = [f"import {m}" for m in stdlib_modules[:n_imports]]
    lines.append("\nx = 1\n")
    (src / f"{module}.py").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit tests — read_coupling_config
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "raw", "expected_threshold", "expected_overrides"),
    [
        pytest.param(None, False, 10, {}, id="defaults"),
        pytest.param(
            """\
            [tool.axm-audit.coupling]
            fan_out_threshold = 15
        """,
            False,
            15,
            {},
            id="custom_threshold",
        ),
        pytest.param(
            """\
            [tool.axm-audit.coupling]
            fan_out_threshold = "not_a_number"
        """,
            False,
            10,
            {},
            id="invalid_threshold",
        ),
        pytest.param(
            """\
            [tool.axm-audit.coupling]
            fan_out_threshold = -5
        """,
            False,
            10,
            {},
            id="negative_threshold",
        ),
        pytest.param(
            """\
            [tool.axm-audit.coupling]
            [tool.axm-audit.coupling.overrides]
            "mod" = "bad"
        """,
            False,
            10,
            {},
            id="invalid_override_value",
        ),
        pytest.param(
            """\
            [project]
            name = "somepkg"
        """,
            False,
            10,
            {},
            id="missing_audit_section",
        ),
        pytest.param(
            "[invalid toml\nno closing bracket",
            True,
            10,
            {},
            id="malformed_toml",
        ),
        pytest.param(
            """\
            [tool.axm-audit.coupling]
            fan_out_threshold = 12
            [tool.axm-audit.coupling.overrides]
        """,
            False,
            12,
            {},
            id="empty_overrides",
        ),
    ],
)
def test_read_coupling_config_returns_threshold_and_overrides(
    tmp_path: Path,
    content: str | None,
    raw: bool,
    expected_threshold: int,
    expected_overrides: dict[str, int],
) -> None:
    """read_coupling_config returns (threshold, overrides) per pyproject content."""
    if content is not None:
        if raw:
            (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        else:
            _write_pyproject(tmp_path, content)
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == expected_threshold
    assert overrides == expected_overrides


def test_read_coupling_config_with_overrides(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        [tool.axm-audit.coupling.overrides]
        "rules.quality" = 20
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {"rules.quality": 20}


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_coupling_rule_reads_pyproject_config(tmp_path: Path) -> None:
    """Module with fan-out=15 passes when pyproject sets threshold=20."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 20
    """,
    )
    _make_src_module(tmp_path, "fakepkg", "heavy", n_imports=15)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is True


def test_coupling_rule_per_module_override(tmp_path: Path) -> None:
    """Per-module override lets a specific module exceed base threshold."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 5
        [tool.axm-audit.coupling.overrides]
        "rules.quality" = 15
    """,
    )
    # Create the overridden module at the dotted path rules/quality.py
    src = tmp_path / "src" / "fakepkg" / "rules"
    src.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "fakepkg" / "__init__.py").write_text("", encoding="utf-8")
    (src / "__init__.py").write_text("", encoding="utf-8")

    stdlib_modules = [
        "os",
        "sys",
        "json",
        "re",
        "math",
        "io",
        "csv",
        "ast",
        "copy",
        "time",
        "uuid",
    ]
    lines = [f"import {m}" for m in stdlib_modules]  # 11 imports
    lines.append("\nx = 1\n")
    (src / "quality.py").write_text("\n".join(lines), encoding="utf-8")

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    # fan-out=11, base threshold=5 would fail, but override=15 lets it pass
    assert result.passed is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_read_coupling_config_override_nonexistent_module(tmp_path: Path) -> None:
    """Override for a module that doesn't exist is silently kept in dict."""
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        [tool.axm-audit.coupling.overrides]
        "no.such.module" = 25
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {"no.such.module": 25}
