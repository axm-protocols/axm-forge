from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.hooks.quality_check import QualityCheckHook

pytestmark = pytest.mark.integration


def _make_pkg(root: Path, name: str, files: dict[str, str]) -> None:
    pkg_src = root / "packages" / name / "src" / name.replace("-", "_")
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    for fname, content in files.items():
        (pkg_src / fname).write_text(textwrap.dedent(content))
    (root / "packages" / name / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "{name}"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        )
    )


def test_quality_check_hook_multi_package_has_violations_true(tmp_path: Path) -> None:
    _make_pkg(tmp_path, "pkg-broken", {"bad.py": "def f():\n    x = 1\n    return 0\n"})
    _make_pkg(tmp_path, "pkg-clean", {"ok.py": "def f() -> int:\n    return 0\n"})

    hook = QualityCheckHook()
    result = hook.execute(
        context={"working_dir": str(tmp_path)},
        categories=["lint", "type"],
    )
    assert result.metadata["has_violations"] is True
    assert "pkg-broken" in (result.text or "")


def test_quality_check_hook_multi_package_clean_workspace(tmp_path: Path) -> None:
    clean = '__all__ = ["f"]\n\ndef f() -> int:\n    return 0\n'
    _make_pkg(tmp_path, "pkg-a", {"ok.py": clean})
    _make_pkg(tmp_path, "pkg-b", {"ok.py": clean})

    hook = QualityCheckHook()
    result = hook.execute(
        context={"working_dir": str(tmp_path)},
        categories=["lint"],
    )
    assert result.metadata["has_violations"] is False
    assert result.metadata.get("summary") == "clean"


@pytest.fixture
def hook() -> QualityCheckHook:
    return QualityCheckHook()


@pytest.fixture
def context(tmp_path: Path) -> dict[str, str]:
    return {"working_dir": str(tmp_path)}


def _make_audit_result(checks: list[MagicMock] | None = None) -> MagicMock:
    result = MagicMock()
    result.checks = checks or []
    return result


def _make_check(
    *,
    passed: bool,
    rule_id: str = "R001",
    message: str = "msg",
    text: str | None = None,
    fix_hint: str | None = None,
) -> MagicMock:
    check = MagicMock()
    check.passed = passed
    check.rule_id = rule_id
    check.message = message
    check.text = text
    check.fix_hint = fix_hint
    return check


class TestIntegrationScope:
    def test_clean_project(
        self, hook: QualityCheckHook, context: dict[str, str], mocker: Any
    ) -> None:
        audit_result = _make_audit_result(
            [_make_check(passed=True, rule_id="L001", message="ok")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["has_violations"] is False
        assert "clean" in result.metadata["summary"].lower()

    def test_text_block_includes_each_rule_and_its_formatted_text(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result(
            [
                _make_check(
                    passed=False,
                    rule_id="QUALITY_LINT",
                    message="Lint score: 98/100 (1 issues)",
                    text="• I001 tests/foo.py:1 Import block un-sorted",
                    fix_hint="Run: ruff check --fix src/ tests/",
                ),
                _make_check(
                    passed=False,
                    rule_id="QUALITY_TYPE",
                    message="Type score: 85/100 (3 errors)",
                    text=(
                        "• [type-arg] tests/foo.py:34: Missing type arguments\n"
                        "• [no-any-return] tests/foo.py:36: Returning Any\n"
                        "• [no-untyped-def] tests/foo.py:39: Missing annotation"
                    ),
                    fix_hint="Add type hints to functions and fix type errors",
                ),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["has_violations"] is True
        assert result.metadata["summary"] == "2 failing check(s)"
        assert result.text is not None
        body = result.text
        assert "QUALITY_LINT" in body
        assert "Lint score: 98/100" in body
        assert "I001 tests/foo.py:1" in body
        assert "QUALITY_TYPE" in body
        assert "[type-arg] tests/foo.py:34" in body
        assert "[no-untyped-def] tests/foo.py:39" in body
        assert "fix: Run: ruff check --fix src/ tests/" in body
        assert "fix: Add type hints" in body

    def test_failed_check_without_text_uses_message_fallback(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result(
            [
                _make_check(
                    passed=False,
                    rule_id="QUALITY_FORMAT",
                    message="3 files unformatted",
                    text=None,
                    fix_hint="Run ruff format",
                )
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["has_violations"] is True
        assert result.text is not None
        assert "QUALITY_FORMAT" in result.text
        assert "3 files unformatted" in result.text
        assert "(no detail)" in result.text
        assert "fix: Run ruff format" in result.text

    def test_only_failed_checks_appear_in_text(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result(
            [
                _make_check(
                    passed=True, rule_id="QUALITY_TYPE", message="ok", text="clean"
                ),
                _make_check(
                    passed=False,
                    rule_id="QUALITY_LINT",
                    message="1 issue",
                    text="• E501 z.py:5 long line",
                ),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["summary"] == "1 failing check(s)"
        assert result.text is not None
        assert "QUALITY_LINT" in result.text
        assert "QUALITY_TYPE" not in result.text

    def test_default_categories(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result()
        mock_audit = mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        hook.execute(context)

        assert mock_audit.call_count == 2
        cats_called = [
            call.kwargs.get("category") or call.args[1]
            for call in mock_audit.call_args_list
        ]
        assert "lint" in cats_called
        assert "type" in cats_called

    def test_custom_categories(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result()
        mock_audit = mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        hook.execute(context, categories=["lint"])

        assert mock_audit.call_count == 1

    def test_audit_crash(
        self, hook: QualityCheckHook, context: dict[str, str], mocker: Any
    ) -> None:
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            side_effect=RuntimeError("boom"),
        )

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False
