from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from axm_audit.core.rules.quality import TypeCheckRule


def _mypy_json_line(
    file: str, line: int, message: str, code: str, severity: str = "error"
) -> str:
    return json.dumps(
        {
            "file": file,
            "line": line,
            "message": message,
            "code": code,
            "severity": severity,
        }
    )


@pytest.fixture()
def rule() -> TypeCheckRule:
    return TypeCheckRule()


@pytest.fixture()
def _patch_infra(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Patch run_in_project and _get_audit_targets so check() doesn't run mypy."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    monkeypatch.setattr(
        "axm_audit.core.rules.quality._get_audit_targets",
        lambda p: (["src"], ["src"]),
    )
    return tmp_path


def _mock_mypy(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    proc = MagicMock(stdout=stdout, returncode=1)
    monkeypatch.setattr(
        "axm_audit.core.rules.quality.run_in_project",
        lambda *a, **kw: proc,
    )


def _patch_check_src_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TypeCheckRule, "check_src", lambda self, p: None)


# ── Unit tests ──────────────────────────────────────────────────────


def test_type_check_text_no_padding(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """text lines start with '\u2022' not '     \u2022'."""
    _patch_check_src_ok(monkeypatch)
    stdout = "\n".join(
        [
            _mypy_json_line("pkg/mod.py", 10, "Incompatible types", "assignment"),
            _mypy_json_line("pkg/mod.py", 20, "Missing return", "return"),
        ]
    )
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    for line in result.text.splitlines():
        assert line.startswith("\u2022"), f"Line has unexpected padding: {line!r}"
        assert not line.startswith("     "), f"Line has 5-space padding: {line!r}"


def test_type_check_text_strips_src_prefix(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Paths under src/ have the prefix stripped in text."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line("src/pkg/mod.py", 5, "Bad type", "arg-type")
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    assert "pkg/mod.py:" in result.text
    assert "src/pkg/mod.py:" not in result.text


# ── Edge cases ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "expected_substring"),
    [
        pytest.param(
            "tests/test_x.py",
            "tests/test_x.py:",
            id="tests_path_unchanged",
        ),
        pytest.param(
            "scripts/deploy.py",
            "scripts/deploy.py:",
            id="path_outside_src_tests_unchanged",
        ),
    ],
)
def test_type_check_path_unchanged(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
    path: str,
    expected_substring: str,
) -> None:
    """Paths not under src/ are preserved as-is in rendered text."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line(path, 3, "Bad arg", "arg-type")
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    assert expected_substring in result.text


def test_type_check_empty_stdout(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Empty mypy stdout produces text=None and empty errors."""
    _patch_check_src_ok(monkeypatch)
    _mock_mypy(monkeypatch, "")

    result = rule.check(_patch_infra)

    assert result.text is None
    assert result.details is not None
    assert result.details["errors"] == []


def test_type_check_zero_errors(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Zero errors means text=None and passed=True."""
    _patch_check_src_ok(monkeypatch)
    _mock_mypy(monkeypatch, "")

    result = rule.check(_patch_infra)

    assert result.text is None
    assert result.passed is True


class TestTypeCheckVenvAlignment:
    """Tests for AXM-796: gate mypy env must match pre-commit hooks."""

    def test_type_check_uses_project_venv(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """TypeCheckRule must NOT inject mypy via --with when project has a venv.

        Pre-commit hooks run mypy from the project's own venv, so the gate
        must do the same to see identical type errors and honour the same
        type-stub availability.
        """
        from axm_audit.core.rules.quality import TypeCheckRule

        # Minimal project layout
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text("def greet(name: str) -> str:\n    return name\n")

        # Simulate a project venv with mypy already installed
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch(mode=0o755)

        # Patch run_in_project to capture the call
        mock_run = mocker.patch(
            "axm_audit.core.rules.quality.run_in_project",
            return_value=mocker.MagicMock(stdout="", returncode=0),
        )

        rule = TypeCheckRule()
        rule.check(tmp_path)

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        # Gate must NOT inject mypy — it should use the project's own copy
        with_pkgs = kwargs.get("with_packages") or []
        assert "mypy" not in with_pkgs, (
            "TypeCheckRule must use the project venv's mypy, "
            "not inject via --with; got with_packages={with_pkgs!r}"
        )

    def test_no_unused_ignore_contradiction(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """A `# type: ignore` accepted by pre-commit must not become
        an 'unused-ignore' error in the gate.

        When the gate uses the same venv as pre-commit, mypy sees
        identical missing-stub / import errors, so a valid type-ignore
        comment stays valid.  This test verifies the gate passes when
        mypy reports zero errors (i.e. the ignore suppressed a real error).
        """
        from axm_audit.core.rules.quality import TypeCheckRule

        # Minimal project layout
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # File with type: ignore that suppresses a real import error
        (src / "client.py").write_text(
            "import somelib  # type: ignore[import-untyped]\n\n"
            "def call() -> str:\n"
            "    return somelib.run()\n"
        )

        # Simulate project venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch(mode=0o755)

        # Simulate mypy output: zero errors (type: ignore suppressed the
        # real error, just like pre-commit would see).  If the gate used
        # a different env, mypy might report "unused-ignore" instead.
        mocker.patch(
            "axm_audit.core.rules.quality.run_in_project",
            return_value=mocker.MagicMock(stdout="", returncode=0),
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["error_count"] == 0, (
            "Gate must not produce unused-ignore errors for comments "
            "that pre-commit accepts"
        )


@pytest.mark.parametrize(
    ("filename", "source"),
    [
        pytest.param(
            "main.py",
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n',
            id="typed_greet",
        ),
        pytest.param(
            "clean.py",
            "def double(x: int) -> int:\n    return x * 2\n",
            id="typed_double",
        ),
    ],
)
def test_typed_project_high_score(tmp_path: Path, filename: str, source: str) -> None:
    """Fully typed project (zero mypy errors) → passed=True, score=100."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / filename).write_text(source)

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.passed is True
    assert result.score == 100


def test_type_errors_reduce_score(tmp_path: Path) -> None:
    """Type errors should fail with zero tolerance."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    # Create file with type error
    (src / "bad.py").write_text(
        'def add(a: int, b: int) -> int:\n    return "not an int"\n'
    )

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.details["error_count"] > 0
    assert result.passed is False


def test_typecheck_includes_tests_dir(tmp_path: Path) -> None:
    """TypeCheckRule should include tests/ in checked dirs when present."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_main.py").write_text("def test_greet() -> None:\n    assert True\n")

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert "tests/" in result.details.get("checked", "")


def test_typecheck_no_tests_dir(tmp_path: Path) -> None:
    """TypeCheckRule should work fine without tests/ directory."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )
    # No tests/ directory

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.details.get("checked") == "src/"


def test_typecheck_details_has_errors_key(tmp_path: Path) -> None:
    """details must contain an 'errors' key with a list."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert "errors" in result.details
    assert isinstance(result.details["errors"], list)


def test_typecheck_errors_match_count(tmp_path: Path) -> None:
    """len(details['errors']) must equal error_count."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.py").write_text(
        'def add(a: int, b: int) -> int:\n    return "not an int"\n'
    )

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert len(result.details["errors"]) == result.details["error_count"]


def test_typecheck_no_errors_empty_list(tmp_path: Path) -> None:
    """When no errors, details['errors'] should be []."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.details["errors"] == []


@pytest.mark.parametrize(
    ("source", "expected_error_count"),
    [
        pytest.param(
            'def add(a: int, b: int) -> int:\n    return "wrong"\n',
            1,
            id="one_error",
        ),
        pytest.param(
            'def add(a: int, b: int) -> int:\n    return "wrong"\n\n'
            'def sub(a: int, b: int) -> int:\n    return "also wrong"\n',
            2,
            id="two_errors",
        ),
    ],
)
def test_type_check_n_errors_fails(
    tmp_path: Path, source: str, expected_error_count: int
) -> None:
    """N mypy errors → passed=False (zero tolerance)."""
    from axm_audit.core.rules.quality import TypeCheckRule

    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.py").write_text(source)

    rule = TypeCheckRule()
    result = rule.check(tmp_path)
    assert result.passed is False
    assert result.details is not None
    assert result.details["error_count"] == expected_error_count


def test_typecheck_uses_run_in_project(tmp_path: Path) -> None:
    """TypeCheckRule should call run_in_project."""
    from axm_audit.core.rules.quality import TypeCheckRule

    (tmp_path / "src").mkdir()

    with patch("axm_audit.core.rules.quality.run_in_project") as mock:
        mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
        TypeCheckRule().check(tmp_path)
        mock.assert_called_once()
        assert mock.call_args[0][0][0] == "mypy"


class TestNoSysExecutable:
    """Ensure sys.executable is not used in any rule files."""

    def test_no_sys_executable_in_rules(self) -> None:
        """Rule files should not reference sys.executable."""
        rules_dir = Path("src/axm_audit/core/rules")
        for py_file in rules_dir.glob("*.py"):
            content = py_file.read_text()
            assert "sys.executable" not in content, (
                f"{py_file.name} still uses sys.executable"
            )


def test_typecheck_uses_project_mypy(tmp_path: Path) -> None:
    """TypeCheckRule does NOT inject mypy — uses the project venv's copy."""
    from axm_audit.core.rules.quality import TypeCheckRule

    (tmp_path / "src").mkdir()

    with patch("axm_audit.core.rules.quality.run_in_project") as mock:
        mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
        TypeCheckRule().check(tmp_path)
        with_pkgs = mock.call_args[1].get("with_packages") or []
        assert "mypy" not in with_pkgs
