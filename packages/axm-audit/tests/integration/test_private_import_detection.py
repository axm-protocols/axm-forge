from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from radon.complexity import cc_visit

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule
from axm_audit.models.results import Severity

__all__: list[str] = []


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def pkg_root(tmp_path: Path) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir()
    return tmp_path


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


def test_flags_private_function_import(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert result.passed is False
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "function"
    assert findings[0]["private_symbol"] == "_private"


def test_flags_private_class_import(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class _Base:\n    pass\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _Base\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "class"


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
    _write(pkg_root / src_file, src_content)
    _write(pkg_root / "tests" / "test_x.py", test_import)
    result = PrivateImportsRule().check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []


def test_flags_upper_case_when_include_constants(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "_REGISTRY = {}\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _REGISTRY\n",
    )
    result = PrivateImportsRule(include_constants=True).check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "constant"


def test_severity_is_error(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert result.severity == Severity.ERROR


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
    _write(pkg_root / "src" / "pkg" / "mod.py", "".join(src_lines))
    imports = (
        "\n".join(f"from pkg.mod import _fn{i}" for i in range(private_count)) + "\n"
    )
    _write(pkg_root / "tests" / "test_x.py", imports)
    result = PrivateImportsRule().check(pkg_root)
    assert result.score == expected_score


def test_message_links_to_docs(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert "docs/test_quality.md#private-imports" in result.message


def test_unknown_kind_fallback(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def other():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _ghost\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "unknown"


def test_private_module_same_package_allowed(tmp_path: Path) -> None:
    (tmp_path / "src" / "mypkg" / "sub").mkdir(parents=True)
    _write(tmp_path / "src" / "mypkg" / "__init__.py", "")
    _write(tmp_path / "src" / "mypkg" / "sub" / "__init__.py", "")
    _write(tmp_path / "src" / "mypkg" / "sub" / "_helper.py", "value = 1\n")
    _write(
        tmp_path / "tests" / "test_x.py",
        "from mypkg.sub import _helper\n",
    )

    result = PrivateImportsRule().check(tmp_path)

    assert result.details["findings"] == []
    assert result.passed is True


def test_private_module_cross_package_flagged(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg_a").mkdir(parents=True)
    (tmp_path / "src" / "pkg_b").mkdir(parents=True)
    _write(tmp_path / "src" / "pkg_a" / "__init__.py", "")
    _write(tmp_path / "src" / "pkg_a" / "_helper.py", "value = 1\n")
    _write(tmp_path / "src" / "pkg_b" / "__init__.py", "")
    _write(
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
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    def _m(self):\n        return 1\n",
    )
    _write(
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
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    def _m(self):\n        return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    fn = Cls._m\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1


def test_import_module_attribute_flagged(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "_var = 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "import pkg.mod as m\n\ndef test():\n    return m._var\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1
    assert attr[0]["import_module"] == "pkg.mod"
    assert attr[0]["private_symbol"] == "_var"


def test_import_module_via_root_flagged(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "_var = 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "import pkg.mod\n\ndef test():\n    return pkg.mod._var\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1
    assert attr[0]["import_module"] == "pkg.mod"


def test_asname_import_resolved(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    def _m(self):\n        return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls as C\n\ndef test():\n    C._m()\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1
    assert attr[0]["import_module"] == "pkg.mod"


def test_deep_attribute_chain_flagged(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    def _method(self):\n        return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "import pkg.mod as mod\n\ndef test():\n    mod.Cls._method()\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1
    assert attr[0]["private_symbol"] == "_method"


def test_inherited_3rd_party_attr_skipped(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    pass\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls._not_defined_here\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_dunder_access_skipped(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    pass\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls.__class__\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_upper_constant_access_skipped(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    _UPPER = 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls._UPPER\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_upper_constant_flagged_when_enabled(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class Cls:\n    _UPPER = 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import Cls\n\ndef test():\n    return Cls._UPPER\n",
    )
    result = PrivateImportsRule(include_constants=True).check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert len(attr) == 1


def test_namedtuple_api_skipped(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "from typing import NamedTuple\n\nclass Tup(NamedTuple):\n    x: int\n",
    )
    _write(
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
    _write(
        pkg_root / "tests" / "test_x.py",
        "import os.path\n\ndef test():\n    return os.path._foo\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    attr = [f for f in result.details["findings"] if f["access_kind"] == "attribute"]
    assert attr == []


def test_import_alias_finding_kind(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _foo():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _foo\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["access_kind"] == "import"


def test_render_distinguishes_kinds(pkg_root: Path) -> None:
    """Mixed attribute + import findings produce distinguishable text output."""
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        (
            "class Cls:\n    def _m(self):\n        return 1\n\n"
            "def _foo():\n    return 1\n"
        ),
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        ("from pkg.mod import Cls, _foo\n\ndef test():\n    Cls._m()\n    _foo()\n"),
    )
    result = PrivateImportsRule().check(pkg_root)
    text = result.text or ""
    assert "[import]" in text
    assert "[attribute]" in text


def test_render_helper_distinguishes_kinds_unit(tmp_path: Path) -> None:
    """Direct unit test of the renderer."""
    from axm_audit.core.rules.test_quality import private_imports as pi_mod

    render = pi_mod.__dict__["_render_private_imports_text"]
    findings = [
        {
            "test_file": str(tmp_path / "tests" / "test_a.py"),
            "line": 1,
            "import_module": "pkg.mod",
            "private_symbol": "_foo",
            "symbol_kind": "function",
            "access_kind": "import",
        },
        {
            "test_file": str(tmp_path / "tests" / "test_b.py"),
            "line": 5,
            "import_module": "pkg.mod",
            "private_symbol": "_m",
            "symbol_kind": "method",
            "access_kind": "attribute",
        },
    ]
    text = render(findings, tmp_path)
    assert "[import]" in text
    assert "[attribute]" in text


def test_check_complexity_within_budget() -> None:
    from axm_audit.core.rules.test_quality import private_imports

    source = Path(inspect.getfile(private_imports)).read_text()
    blocks = cc_visit(source)

    check_block = next(
        b
        for b in blocks
        if getattr(b, "classname", None) == "PrivateImportsRule" and b.name == "check"
    )
    assert check_block.complexity <= 17
