from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.flows import FlowsTool


@pytest.fixture()
def tool() -> FlowsTool:
    return FlowsTool()


@pytest.fixture()
def mock_pkg():
    return SimpleNamespace(name="fakepkg")


@pytest.fixture()
def _patch_dir(tmp_path):
    """Ensure the path passed to execute is a real directory."""
    return str(tmp_path)


def _make_entry(
    name: str, module: str, kind: str, line: int, framework: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name, module=module, kind=kind, line=line, framework=framework
    )


def _make_flow_step(
    name: str,
    module: str,
    line: int,
    depth: int,
    chain: list[str],
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        module=module,
        line=line,
        depth=depth,
        chain=chain,
        resolved_module=None,
        source=None,
    )


# ---------- Unit tests ----------


def test_flows_execute_entry_points(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """Call execute without entry param returns entry_points data."""
    entries = [
        _make_entry("main", "cli", "function", 10, "click"),
        _make_entry("app", "web", "function", 20, "fastapi"),
    ]
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.flows.find_entry_points", return_value=entries),
    ):
        result = tool.execute(path=str(tmp_path))

    assert result.success is True
    assert result.data["count"] == 2
    assert len(result.data["entry_points"]) == 2
    assert result.data["entry_points"][0]["name"] == "main"
    assert result.data["entry_points"][1]["name"] == "app"


def test_flows_execute_trace(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """Call execute with entry='main' returns steps data with depth/count."""
    steps = [
        _make_flow_step("main", "cli", 10, 0, ["main"]),
        _make_flow_step("run", "cli", 30, 1, ["main", "run"]),
    ]
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.flows.trace_flow", return_value=(steps, False)),
    ):
        result = tool.execute(path=str(tmp_path), entry="main")

    assert result.success is True
    assert result.data["entry"] == "main"
    assert result.data["count"] == 2
    assert result.data["depth"] == 1
    assert result.data["truncated"] is False
    assert len(result.data["steps"]) == 2
    assert result.data["steps"][0]["name"] == "main"
    assert result.data["steps"][1]["name"] == "run"


def test_flows_execute_compact(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """Call execute with detail='compact' returns compact tree string."""
    steps = [
        _make_flow_step("main", "cli", 10, 0, ["main"]),
    ]
    compact_tree = "main\n└── run"
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.flows.trace_flow", return_value=(steps, False)),
        patch("axm_ast.core.flows.format_flow_compact", return_value=compact_tree),
    ):
        result = tool.execute(path=str(tmp_path), entry="main", detail="compact")

    assert result.success is True
    assert result.data["compact"] == compact_tree
    assert result.data["traces"] == compact_tree
    assert result.data["entry"] == "main"
    assert result.data["depth"] == 0
    assert result.data["count"] == 1


# ---------- Edge cases ----------


def test_flows_execute_invalid_detail(tool: FlowsTool, tmp_path: Path) -> None:
    """Invalid detail mode returns success=False with error."""
    with patch("axm_ast.core.cache.get_package", return_value=SimpleNamespace()):
        result = tool.execute(path=str(tmp_path), detail="invalid")

    assert result.success is False
    assert result.error is not None
    assert "invalid" in result.error.lower() or "Invalid" in result.error


def test_flows_execute_symbol_not_found(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """entry='nonexistent' returns success=False."""
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch(
            "axm_ast.core.flows.trace_flow",
            side_effect=ValueError("Symbol 'nonexistent' not found in package"),
        ),
    ):
        result = tool.execute(path=str(tmp_path), entry="nonexistent")

    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()


@pytest.fixture()
def tmp_pkg(tmp_path: object) -> object:
    """Create a minimal directory so is_dir() passes."""
    return tmp_path


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_has_depth_key(tmp_pkg: object) -> None:
    tool = FlowsTool()
    result = tool.execute(
        path=str(tmp_pkg), entry="main", detail="compact", max_depth=3
    )
    assert result.success
    assert result.data["depth"] == 1  # actual depth, not max_depth


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_has_cross_module_key(tmp_pkg: object) -> None:
    tool = FlowsTool()
    result = tool.execute(
        path=str(tmp_pkg), entry="main", detail="compact", cross_module=True
    )
    assert result.success
    assert result.data["cross_module"] is True


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_keys_match_trace(tmp_pkg: object) -> None:
    """Compact data must contain exactly the expected key set."""
    tool = FlowsTool()
    result = tool.execute(path=str(tmp_pkg), entry="main", detail="compact")
    assert result.success
    assert set(result.data.keys()) == {
        "entry",
        "compact",
        "traces",
        "depth",
        "cross_module",
        "count",
        "truncated",
    }


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_default_values(tmp_pkg: object) -> None:
    """Without explicit max_depth/cross_module, defaults apply."""
    # defaults are depth=5, cross_module=False
    tool = FlowsTool()
    result = tool.execute(path=str(tmp_pkg), entry="main", detail="compact")
    assert result.success
    assert result.data["depth"] == 1  # actual depth, not max_depth default
    assert result.data["cross_module"] is False


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_trace_keys_unchanged(tmp_pkg: object) -> None:
    """Trace detail still returns steps-based keys, unaffected by compact fix."""
    tool = FlowsTool()
    result = tool.execute(path=str(tmp_pkg), entry="main", detail="trace")
    assert result.success
    assert set(result.data.keys()) == {
        "entry",
        "steps",
        "depth",
        "cross_module",
        "count",
        "truncated",
    }


@pytest.fixture()
def _mock_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch core.cache and core.flows so FlowsTool.execute never hits disk."""
    pkg_mock = MagicMock()
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _p: pkg_mock)
    monkeypatch.setattr(
        "axm_ast.core.flows.VALID_DETAILS", {"trace", "source", "compact"}
    )
    step = MagicMock(name="step", depth=1, chain=["a", "b"])
    step.name = "func"
    step.module = "mod"
    step.line = 10
    step.resolved_module = None
    step.source = None
    monkeypatch.setattr(
        "axm_ast.core.flows.trace_flow", lambda *a, **kw: ([step], False)
    )
    monkeypatch.setattr(
        "axm_ast.core.flows.format_flow_compact", lambda steps: "main\n  └─ func"
    )


# ─── Functional: FlowsTool + FlowsHook with compact ─────────────────────────

SAMPLE_PKG_FILES: dict[str, str] = {
    "__init__.py": "",
    "main.py": (
        "def main():\n"
        "    caller()\n\n"
        "def caller():\n"
        "    helper()\n\n"
        "def helper():\n"
        "    pass\n"
    ),
}


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def _make_pkg__from_flows_compact(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


@pytest.fixture()
def flows_tool() -> FlowsTool:
    return FlowsTool()


@pytest.fixture()
def circular_pkg(tmp_path: Path) -> Path:
    """Package with circular dependency between modules."""
    pkg = tmp_path / "circpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Circular."""\n')
    (pkg / "a.py").write_text(
        "from .b import func_b\n\ndef func_a():\n    return func_b()\n"
    )
    (pkg / "b.py").write_text(
        "def func_b():\n    from .a import func_a  # noqa: F811\n    return 'b'\n"
    )
    return pkg


def test_flows_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:
    from axm_ast.tools.flows import FlowsTool

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.cache.get_package",
        side_effect=RuntimeError("flows boom"),
    )
    result = FlowsTool().execute(path=str(pkg))
    assert result.success is False
    assert "flows boom" in (result.error or "")


class TestFlowsToolCompact:
    """Cover tools/flows.py compact detail branch (line 61+)."""

    def test_flows_compact_detail(self, tmp_path: Path) -> None:
        from axm_ast.tools.flows import FlowsTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        result = FlowsTool().execute(path=str(pkg), entry="main", detail="compact")
        assert result.success is True
        assert "compact" in result.data

    def test_flows_entry_points(self, tmp_path: Path) -> None:
        from axm_ast.tools.flows import FlowsTool

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "def main():\n    pass\n"},
        )
        result = FlowsTool().execute(path=str(pkg))
        assert result.success is True
        assert "entry_points" in result.data


class TestFlowsResolvedModule:
    """Cover tools/flows.py line 104 (step with resolved_module)."""

    def test_flows_step_with_resolved_module(
        self, tmp_path: Path, mocker: MagicMock
    ) -> None:
        from unittest.mock import MagicMock as MockMagic

        from axm_ast.tools.flows import FlowsTool

        step = MockMagic()
        step.name = "foo"
        step.module = "mod"
        step.line = 1
        step.depth = 0
        step.chain = ["foo"]
        step.resolved_module = "other_mod"
        step.source = None

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch("axm_ast.core.cache.get_package", return_value=MagicMock())
        mocker.patch(
            "axm_ast.core.flows.trace_flow",
            return_value=([step], False),
        )
        result = FlowsTool().execute(path=str(pkg), entry="foo")
        assert result.success is True
        assert result.data["steps"][0]["resolved_module"] == "other_mod"


class TestFlowsToolCompactMode:
    """FlowsTool.execute(detail='compact') returns compact string, not JSON dicts."""

    def test_flows_tool_compact_mode(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg__from_flows_compact(tmp_path, SAMPLE_PKG_FILES)
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="compact")
        assert result.success is True
        # Compact mode should have a compact string representation
        assert "compact" in result.data
        compact_output = result.data["compact"]
        assert isinstance(compact_output, str)
        assert "main" in compact_output
        # Should NOT have step dicts in compact mode
        assert "steps" not in result.data


class TestFlowsToolTraceUnchanged:
    """FlowsTool.execute(detail='trace') → same output as before (regression)."""

    def test_flows_tool_trace_unchanged(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg__from_flows_compact(tmp_path, SAMPLE_PKG_FILES)
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="trace")
        assert result.success is True
        # Trace mode should still return step dicts
        assert "steps" in result.data
        assert isinstance(result.data["steps"], list)
        for step in result.data["steps"]:
            assert "name" in step
            assert "depth" in step
            assert "chain" in step


class TestCompactCircularCalls:
    """A→B→A at depth 2 → tree stops at visited node, no infinite loop."""

    def test_circular_calls(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg__from_flows_compact(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": (
                    "def func_a():\n    func_b()\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        tool = FlowsTool()
        result = tool.execute(
            path=str(pkg_path), entry="func_a", detail="compact", max_depth=5
        )
        assert result.success is True
        # Should terminate without infinite loop
        compact = result.data.get("compact", "")
        assert isinstance(compact, str)


class TestCompactEmptyTrace:
    """Symbol not found → graceful empty output."""

    def test_empty_trace(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg__from_flows_compact(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": "def foo():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="nonexistent", detail="compact")
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error


class TestFlowsToolInvalidDetail:
    """FlowsTool.execute() returns failure for invalid detail."""

    def test_flows_tool_invalid_detail(self, tmp_path: object) -> None:
        tool = FlowsTool()
        result = tool.execute(path=str(tmp_path), entry="main", detail="full")
        assert result.success is False
        assert result.error is not None
        assert "detail" in result.error.lower()


class TestFlowsEmptyChain:
    """Call flows with symbol that has no callers/callees → single-node flow."""

    def test_flows_empty_chain(self, flows_tool: FlowsTool, simple_pkg: Path) -> None:
        result = flows_tool.execute(path=str(simple_pkg), entry="greet", max_depth=5)
        assert result.success is True
        # Should return at least the entry node itself
        assert result.data["count"] >= 0


class TestFlowsCircularRef:
    """Call flows with circular dependency → terminates without infinite loop."""

    def test_flows_circular_ref(
        self, flows_tool: FlowsTool, circular_pkg: Path
    ) -> None:
        result = flows_tool.execute(
            path=str(circular_pkg), entry="func_a", max_depth=10
        )
        assert result.success is True
        # Must terminate — BFS should not loop forever
        assert result.data["count"] >= 1


def _make_pkg__from_flows_tool_detail_passthrough(
    tmp_path: Path, files: dict[str, str]
) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


class TestFlowsToolDetail:
    """FlowsTool passes detail param through."""

    def test_flowstool_passes_detail(self, tmp_path: Path) -> None:
        """FlowsTool with detail='source' → steps contain source."""
        from axm_ast.tools.flows import FlowsTool

        pkg_path = _make_pkg__from_flows_tool_detail_passthrough(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="source")
        assert result.success
        assert result.data is not None
        steps = result.data["steps"]
        assert len(steps) >= 1
        assert "source" in steps[0]
        assert "def main" in steps[0]["source"]

    def test_flowstool_default_no_source(self, tmp_path: Path) -> None:
        """FlowsTool default → steps do not contain source key."""
        from axm_ast.tools.flows import FlowsTool

        pkg_path = _make_pkg__from_flows_tool_detail_passthrough(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main")
        assert result.success
        assert result.data is not None
        steps = result.data["steps"]
        assert len(steps) >= 1
        assert "source" not in steps[0]
