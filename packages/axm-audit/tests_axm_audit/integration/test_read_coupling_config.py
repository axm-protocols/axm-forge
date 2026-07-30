from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture.coupling import (
    read_coupling_config,
)


class TestCouplingHelpersIntegration:
    @pytest.mark.parametrize(
        ("toml_content",),
        [
            pytest.param(None, id="no_pyproject"),
            pytest.param("{{not valid toml", id="malformed_toml"),
            pytest.param('[project]\nname = "demo"\n', id="missing_coupling_section"),
        ],
    )
    def test_defaults_returned(self, tmp_path: Path, toml_content: str | None) -> None:
        """No/malformed/missing-section pyproject.toml -> 4-tuple of defaults."""
        if toml_content is not None:
            (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")
        result = read_coupling_config(tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_zero_threshold(self, tmp_path: Path) -> None:
        """fan_out_threshold = 0 is valid (not negative)."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.axm-audit.coupling]
            fan_out_threshold = 0
            """),
            encoding="utf-8",
        )
        threshold, _overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
        assert threshold == 0


def _write_pyproject(tmp_path: Path, content: str) -> None:
    """Write a pyproject.toml into *tmp_path*."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(content),
        encoding="utf-8",
    )


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


class TestReadCouplingConfigOrchestratorBonus:
    """Verify orchestrator_bonus is parsed from pyproject.toml."""

    @pytest.mark.parametrize(
        ("extra_lines", "expected_bonus"),
        [
            pytest.param("orchestrator_bonus = 8\n", 8, id="explicit_value"),
            pytest.param("orchestrator_bonus = 0\n", 0, id="explicit_zero"),
            pytest.param("", 5, id="missing_uses_default"),
        ],
    )
    def test_read_coupling_config_orchestrator_bonus(
        self, tmp_path: Path, extra_lines: str, expected_bonus: int
    ) -> None:
        """orchestrator_bonus is parsed from pyproject, defaults to 5 when missing."""
        from axm_audit.core.rules.architecture.coupling import read_coupling_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            f"[tool.axm-audit.coupling]\nthreshold = 10\n{extra_lines}"
        )
        _, _, bonus, _ = read_coupling_config(tmp_path)
        assert bonus == expected_bonus


def test_multiplier_from_config(tmp_path: Path) -> None:
    """severity_error_multiplier=3 from pyproject.toml."""
    _write_pyproject(
        tmp_path,
        """\
            [tool.axm-audit.coupling]
            fan_out_threshold = 10
            severity_error_multiplier = 3
        """,
    )
    _threshold, _overrides, _bonus, multiplier = read_coupling_config(tmp_path)
    assert multiplier == 3


def test_multiplier_default(tmp_path: Path) -> None:
    """No config → default multiplier=2."""
    _threshold, _overrides, _bonus, multiplier = read_coupling_config(tmp_path)
    assert multiplier == 2


def test_multiplier_minimum_1(tmp_path: Path) -> None:
    """severity_error_multiplier=0 → falls back to 1 (same as no tiers)."""
    _write_pyproject(
        tmp_path,
        """\
            [tool.axm-audit.coupling]
            severity_error_multiplier = 0
        """,
    )
    _threshold, _overrides, _bonus, multiplier = read_coupling_config(tmp_path)
    assert multiplier == 1
