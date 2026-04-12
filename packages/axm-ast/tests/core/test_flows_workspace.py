from __future__ import annotations

from unittest.mock import MagicMock, patch

from axm_ast.core.flows import find_callees_workspace


def test_find_callees_workspace_iterates_all_packages():
    """Workspace-level callees returns results from all packages.

    Results include pkg_name:: prefix.
    """
    call_a = MagicMock(
        module="mod_a",
        symbol="func_x",
        line=10,
        context="x()",
        call_expression="func_x()",
    )
    call_b = MagicMock(
        module="mod_b",
        symbol="func_y",
        line=20,
        context="y()",
        call_expression="func_y()",
    )

    pkg1 = MagicMock()
    pkg1.name = "pkg_alpha"
    pkg2 = MagicMock()
    pkg2.name = "pkg_beta"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.side_effect = [
            [call_a],
            [call_b],
        ]

        result = find_callees_workspace(ws, "some_symbol")

    assert len(result) == 2
    assert result[0].module == "pkg_alpha::mod_a"
    assert result[1].module == "pkg_beta::mod_b"


def test_find_callees_workspace_shares_parse_cache():
    """A single cache dict is passed to all find_callees calls across packages."""
    pkg1 = MagicMock()
    pkg1.name = "pkg1"
    pkg2 = MagicMock()
    pkg2.name = "pkg2"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.return_value = []

        find_callees_workspace(ws, "sym")

        assert mock_find.call_count == 2
        cache1 = mock_find.call_args_list[0][1]["_parse_cache"]
        cache2 = mock_find.call_args_list[1][1]["_parse_cache"]
        assert cache1 is cache2
        assert isinstance(cache1, dict)


def test_find_callees_workspace_symbol_in_one_package():
    """Symbol found in only one of three packages.

    Returns prefixed callees from that one.
    """
    call_site = MagicMock(
        module="helpers",
        symbol="do_thing",
        line=5,
        context="..",
        call_expression="do_thing()",
    )

    pkg1 = MagicMock()
    pkg1.name = "alpha"
    pkg2 = MagicMock()
    pkg2.name = "beta"
    pkg3 = MagicMock()
    pkg3.name = "gamma"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2, pkg3]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.side_effect = [
            [],
            [call_site],
            [],
        ]

        result = find_callees_workspace(ws, "do_thing")

    assert len(result) == 1
    assert result[0].module == "beta::helpers"


def test_find_callees_workspace_symbol_not_found():
    """Non-existent symbol across workspace returns empty list."""
    pkg1 = MagicMock()
    pkg1.name = "a"
    pkg2 = MagicMock()
    pkg2.name = "b"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.return_value = []

        result = find_callees_workspace(ws, "nonexistent")

    assert result == []
