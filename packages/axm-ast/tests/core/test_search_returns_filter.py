from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from axm_ast.core.analyzer import _search_all, _search_classes


def _make_fn(name: str, return_type: str | None = None) -> MagicMock:
    """Create a mock FunctionInfo."""
    fn = MagicMock()
    fn.name = name
    fn.return_type = return_type
    fn.kind = None
    return fn


def _make_cls(name: str, methods: list[MagicMock] | None = None) -> MagicMock:
    """Create a mock ClassInfo."""
    cls = MagicMock()
    cls.name = name
    cls.methods = methods or []
    return cls


def _make_var(name: str) -> MagicMock:
    """Create a mock VariableInfo."""
    var = MagicMock()
    var.name = name
    return var


def _make_mod(
    *, functions: list[MagicMock] | None = None, classes: list[MagicMock] | None = None
) -> MagicMock:
    """Create a mock ModuleInfo."""
    mod = MagicMock()
    mod.functions = functions or []
    mod.classes = classes or []
    return mod


@pytest.fixture
def mixed_module():
    """Module with functions, classes (with methods), and a variable."""
    fn_str = _make_fn("format_name", return_type="str")
    fn_int = _make_fn("compute_total", return_type="int")

    method_str = _make_fn("to_string", return_type="str")
    method_int = _make_fn("get_id", return_type="int")
    cls_user = _make_cls("User", methods=[method_str, method_int])

    cls_empty = _make_cls("Config", methods=[])

    var = _make_var("_TOLERANCE")

    mod = _make_mod(functions=[fn_str, fn_int], classes=[cls_user, cls_empty])
    return {
        "mod": mod,
        "var": var,
        "fn_str": fn_str,
        "fn_int": fn_int,
        "cls_user": cls_user,
        "cls_empty": cls_empty,
        "method_str": method_str,
        "method_int": method_int,
    }


# --- AC1: returns filter excludes variables ---


def test_search_returns_excludes_variables(mixed_module):
    """AC1: _search_all with returns set must not include variables."""
    mod = mixed_module["mod"]
    var = mixed_module["var"]
    fn_str = mixed_module["fn_str"]

    with patch(
        "axm_ast.core.analyzer._search_variables",
        return_value=[var],
    ) as mock_sv:
        results = _search_all(mod, name=None, returns="str")

    mock_sv.assert_not_called()
    assert var not in results
    assert fn_str in results


# --- AC2: returns filter excludes name-matched classes ---


def test_search_returns_excludes_name_matched_classes(mixed_module):
    """AC2: _search_classes with name+returns must not short-circuit."""
    mod = mixed_module["mod"]
    cls_user = mixed_module["cls_user"]
    method_int = mixed_module["method_int"]

    results = _search_classes(mod, name="User", returns="int", kind=None)

    assert cls_user not in results
    assert method_int in results


# --- AC3: no returns still includes variables (regression guard) ---


def test_search_no_returns_still_includes_variables(mixed_module):
    """AC3: _search_all without returns must still include variables."""
    mod = mixed_module["mod"]
    var = mixed_module["var"]

    with patch(
        "axm_ast.core.analyzer._search_variables",
        return_value=[var],
    ) as mock_sv:
        results = _search_all(mod, name=None, returns=None)

    mock_sv.assert_called_once_with(mod, name=None)
    assert var in results


def test_search_classes_name_match_no_returns_still_returns_class(mixed_module):
    """AC3: _search_classes with name match + no returns still returns class."""
    mod = mixed_module["mod"]
    cls_user = mixed_module["cls_user"]

    results = _search_classes(mod, name="User", returns=None, kind=None)

    assert cls_user in results


# --- Edge cases ---


def test_search_returns_name_matching_class_only_matching_methods():
    """Edge: name='User' + returns='str' returns only methods with both matches."""
    method_match = _make_fn("UserSerializer", return_type="str")
    method_no_match = _make_fn("get_id", return_type="int")
    cls = _make_cls("User", methods=[method_match, method_no_match])
    mod = _make_mod(classes=[cls])

    results = _search_classes(mod, name="User", returns="str", kind=None)

    assert cls not in results
    assert method_match in results
    assert method_no_match not in results


def test_search_returns_on_variables_only_module():
    """Edge: returns filter on module with only variables yields empty results."""
    mod = _make_mod(functions=[], classes=[])
    var = _make_var("MAX_SIZE")

    with patch(
        "axm_ast.core.analyzer._search_variables",
        return_value=[var],
    ):
        results = _search_all(mod, name=None, returns="int")

    assert results == []
