"""Integration test: AC9 — TEST_QUALITY_PRIVATE_IMPORTS count drops by
≥ 18 vs. post-T2 baseline once the auditor / security / quality / score /
coverage / hook tests no longer reach past public APIs."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

_PKG_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_FILE = _PKG_ROOT / "tests" / ".private_imports_baseline"
_DROP_REQUIRED = 18


@pytest.mark.integration
def test_private_imports_count_dropped_further():
    if not _BASELINE_FILE.exists():
        pytest.skip(
            "Post-T2 baseline file missing; build phase must persist it at "
            f"{_BASELINE_FILE.relative_to(_PKG_ROOT)}"
        )

    baseline = int(_BASELINE_FILE.read_text().strip())

    result = PrivateImportsRule().check(_PKG_ROOT)

    details = result.details or {}
    total = details.get("total")
    if total is None:
        # Fallback: derive from violation list if present.
        violations = details.get("violations") or details.get("items") or []
        total = len(violations)

    assert total <= baseline - _DROP_REQUIRED, (
        f"Expected private-imports count ≤ {baseline - _DROP_REQUIRED} "
        f"(post-T2 baseline {baseline} - {_DROP_REQUIRED}), got {total}."
    )


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip())


@pytest.fixture
def private_imports_project(tmp_path: Path) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    _write(tmp_path / "src" / "pkg" / "__init__.py", "")
    _write(tmp_path / "src" / "pkg" / "mod.py", "def _private():\n    return 1\n")
    _write(
        tmp_path / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    return tmp_path


def _write__from_private_import_detection(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_project(tmp_path: Path, files: dict[str, str]) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir(exist_ok=True)
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dedent(content))
    return tmp_path


def test_private_imports_failed_populates_actionable_fields(
    private_imports_project: Path,
) -> None:
    result = PrivateImportsRule().check(private_imports_project)
    assert result.passed is False
    assert result.text and "_private" in result.text
    assert result.fix_hint and "public" in result.fix_hint.lower()
    assert result.details is not None
    assert "findings" in result.details


def test_private_imports_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    _write(tmp_path / "src" / "pkg" / "__init__.py", "")
    (tmp_path / "tests").mkdir()
    result = PrivateImportsRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


@pytest.mark.parametrize(
    ("setup_dir",),
    [
        pytest.param("src", id="empty_tests_dir"),
        pytest.param("tests", id="no_src"),
    ],
)
def test_check_missing_counterpart_passes(tmp_path: Path, setup_dir: str) -> None:
    (tmp_path / setup_dir).mkdir()
    result = PrivateImportsRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100


@pytest.mark.parametrize(
    ("src_content", "test_import", "include_constants", "expected_kind"),
    [
        pytest.param(
            "def _private():\n    return 1\n",
            "from pkg.mod import _private\n",
            False,
            "function",
            id="private_function",
        ),
        pytest.param(
            "class _Base:\n    pass\n",
            "from pkg.mod import _Base\n",
            False,
            "class",
            id="private_class",
        ),
        pytest.param(
            "_REGISTRY = {}\n",
            "from pkg.mod import _REGISTRY\n",
            True,
            "constant",
            id="upper_case_when_include_constants",
        ),
        pytest.param(
            "def other():\n    return 1\n",
            "from pkg.mod import _ghost\n",
            False,
            "unknown",
            id="unknown_kind_fallback",
        ),
    ],
)
def test_flags_private_import_kind(
    pkg_root: Path,
    src_content: str,
    test_import: str,
    include_constants: bool,
    expected_kind: str,
) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py", src_content
    )
    _write__from_private_import_detection(pkg_root / "tests" / "test_x.py", test_import)
    rule = PrivateImportsRule(include_constants=include_constants)
    result = rule.check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == expected_kind


@pytest.mark.parametrize(
    ("src_file", "src_content", "test_import"),
    [
        pytest.param(
            "src/pkg/__init__.py",
            "__version__ = '1.0'\n",
            "from pkg import __version__\n",
            id="skips_dunder_imports",
        ),
        pytest.param(
            "src/pkg/mod.py",
            "_REGISTRY = {}\n",
            "from pkg.mod import _REGISTRY\n",
            id="skips_upper_case_constants_by_default",
        ),
    ],
)
def test_skips_non_flagged_symbols(
    pkg_root: Path, src_file: str, src_content: str, test_import: str
) -> None:
    _write__from_private_import_detection(pkg_root / src_file, src_content)
    _write__from_private_import_detection(pkg_root / "tests" / "test_x.py", test_import)
    result = PrivateImportsRule().check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []


@pytest.mark.parametrize(
    ("private_count", "expected_score"),
    [
        pytest.param(10, 50, id="linear_midrange"),
        pytest.param(25, 0, id="floors_at_zero"),
    ],
)
def test_score_scales_with_violation_count(
    pkg_root: Path, private_count: int, expected_score: int
) -> None:
    src_lines = [f"def _fn{i}():\n    return {i}\n" for i in range(private_count)]
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py", "".join(src_lines)
    )
    imports = (
        "\n".join(f"from pkg.mod import _fn{i}" for i in range(private_count)) + "\n"
    )
    _write__from_private_import_detection(pkg_root / "tests" / "test_x.py", imports)
    result = PrivateImportsRule().check(pkg_root)
    assert result.score == expected_score


def test_message_links_to_docs(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert "docs/test_quality.md#private-imports" in result.message


def test_private_module_same_package_allowed(tmp_path: Path) -> None:
    (tmp_path / "src" / "mypkg" / "sub").mkdir(parents=True)
    _write__from_private_import_detection(
        tmp_path / "src" / "mypkg" / "__init__.py", ""
    )
    _write__from_private_import_detection(
        tmp_path / "src" / "mypkg" / "sub" / "__init__.py", ""
    )
    _write__from_private_import_detection(
        tmp_path / "src" / "mypkg" / "sub" / "_helper.py", "value = 1\n"
    )
    _write__from_private_import_detection(
        tmp_path / "tests" / "test_x.py",
        "from mypkg.sub import _helper\n",
    )

    result = PrivateImportsRule().check(tmp_path)

    assert result.details["findings"] == []
    assert result.passed is True


def test_private_module_cross_package_flagged(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg_a").mkdir(parents=True)
    (tmp_path / "src" / "pkg_b").mkdir(parents=True)
    _write__from_private_import_detection(
        tmp_path / "src" / "pkg_a" / "__init__.py", ""
    )
    _write__from_private_import_detection(
        tmp_path / "src" / "pkg_a" / "_helper.py", "value = 1\n"
    )
    _write__from_private_import_detection(
        tmp_path / "src" / "pkg_b" / "__init__.py", ""
    )
    _write__from_private_import_detection(
        tmp_path / "tests" / "pkg_b" / "test_x.py",
        "from pkg_a import _helper\n",
    )

    result = PrivateImportsRule().check(tmp_path)

    findings = result.details["findings"]
    assert len(findings) >= 1
    assert any(f["private_symbol"] == "_helper" for f in findings)


def test_class_method_call_flagged(pkg_root: Path) -> None:
    """Calling a private class method via attribute access is flagged.

    Asserts the full finding shape: count, access_kind, private_symbol,
    and import_module. Subsumes the former test_attribute_finding_kind.
    """
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    def _m(self):\n        return 1\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    Cls._m()\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["access_kind"] == "attribute"
    assert findings[0]["private_symbol"] == "_m"
    assert findings[0]["import_module"] == "pkg.mod"


def test_class_method_no_call_flagged(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    def _m(self):\n        return 1\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    fn = Cls._m\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1


@pytest.mark.parametrize(
    ("src_content", "test_content", "expected_symbol"),
    [
        pytest.param(
            "_var = 1\n",
            "import pkg.mod as m\n\ndef test():\n    return m._var\n",
            "_var",
            id="import_module_as_alias",
        ),
        pytest.param(
            "_var = 1\n",
            "import pkg.mod\n\ndef test():\n    return pkg.mod._var\n",
            "_var",
            id="import_module_via_root",
        ),
        pytest.param(
            "class Cls:\n    def _m(self):\n        return 1\n",
            "from pkg.mod import Cls as C\n\ndef test():\n    C._m()\n",
            "_m",
            id="asname_import_resolved",
        ),
        pytest.param(
            "class Cls:\n    def _method(self):\n        return 1\n",
            "import pkg.mod as mod\n\ndef test():\n    mod.Cls._method()\n",
            "_method",
            id="deep_attribute_chain",
        ),
    ],
)
def test_attribute_access_resolved_to_pkg_mod(
    pkg_root: Path,
    src_content: str,
    test_content: str,
    expected_symbol: str,
) -> None:
    """Various import styles all resolve attribute access to ``pkg.mod``."""
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py", src_content
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py", test_content
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1
    assert attr[0]["import_module"] == "pkg.mod"
    assert attr[0]["private_symbol"] == expected_symbol


def test_inherited_3rd_party_attr_skipped(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    pass\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls._not_defined_here\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_dunder_access_skipped(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    pass\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls.__class__\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_upper_constant_access_skipped(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    _UPPER = 1\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls._UPPER\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_upper_constant_flagged_when_enabled(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    _UPPER = 1\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls._UPPER\n",
    )
    result = PrivateImportsRule(include_constants=True).check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1


def test_namedtuple_api_skipped(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "from typing import NamedTuple\n\nclass Tup(NamedTuple):\n    x: int\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        (
            "from pkg.mod import Tup\n\n"
            "def test():\n"
            "    Tup._asdict\n"
            "    Tup._replace\n"
            "    Tup._fields\n"
            "    Tup._make\n"
            "    Tup._field_defaults\n"
        ),
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_third_party_root_skipped(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "import os.path\n\ndef test():\n    return os.path._foo\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_import_alias_finding_kind(pkg_root: Path) -> None:
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _foo():\n    return 1\n",
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _foo\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["access_kind"] == "import"


def test_render_distinguishes_kinds(pkg_root: Path) -> None:
    """Mixed attribute + import findings produce distinguishable text output."""
    _write__from_private_import_detection(
        pkg_root / "src" / "pkg" / "mod.py",
        (
            "class Cls:\n    def _m(self):\n        return 1\n\n"
            "def _foo():\n    return 1\n"
        ),
    )
    _write__from_private_import_detection(
        pkg_root / "tests" / "test_x.py",
        ("from pkg.mod import Cls, _foo\n\ndef test():\n    Cls._m()\n    _foo()\n"),
    )
    result = PrivateImportsRule().check(pkg_root)
    text = result.text or ""
    assert "[import]" in text
    assert "[attribute]" in text


def test_marker_does_not_suppress_other_test_quality_rules(tmp_path: Path) -> None:
    """AC2: marker is tautology-scoped — other rules still fire."""
    project = _make_project(
        tmp_path,
        {
            "src/pkg/_internal.py": "def _secret():\n    return 42\n",
            "tests/unit/test_x.py": """
                import pytest
                from pkg._internal import _secret

                @pytest.mark.tautology_ok
                def test_x():
                    assert _secret() == 42
            """,
        },
    )

    result = PrivateImportsRule().check(project)

    assert result.passed is False
