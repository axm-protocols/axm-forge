"""Tests for the auto-generating, dispatch-first AXM CLI."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Annotated, Any
from unittest.mock import patch

import pytest
from cyclopts import Parameter

from axm.cli import (
    _COMMANDS_GROUP,
    _TOOLS_GROUP,
    _emit,
    build_command_for_tool,
    cli_param,
    create_app,
    is_nonscalar,
    main,
    public_params,
)
from axm.tools.base import ToolResult

_EP = "axm.tools._discovery.importlib.metadata.entry_points"
_EXIT_BAD_ARGS = 2
_EXIT_TOOL_ERROR = 1


# ── fakes ─────────────────────────────────────────────────────────────────────


class _AuditTool:
    """Scalar-only tool returning dual-format output."""

    @property
    def name(self) -> str:
        return "audit"

    def execute(self, *, path: str = ".", category: str | None = None) -> ToolResult:
        """Audit a project.

        Args:
            path: Project root.
            category: Optional filter.
        """
        return ToolResult(success=True, data={"score": 90}, text=f"audit {path}: 90")


class _BatchTool:
    """Tool with a non-scalar (list) parameter."""

    @property
    def name(self) -> str:
        return "batch_edit"

    def execute(
        self, *, path: str = ".", operations: list[dict[str, object]] | None = None
    ) -> ToolResult:
        """Apply edits.

        Args:
            path: Root.
            operations: Edit ops.
        """
        n = len(operations or [])
        return ToolResult(success=True, data={"applied": n}, text=f"applied {n}")


class _FailTool:
    """Tool that returns success=False."""

    @property
    def name(self) -> str:
        return "boom"

    def execute(self, *, path: str = ".") -> ToolResult:
        """Always fails."""
        return ToolResult(success=False, error="nope", text="error: nope")


class _DispatchTool:
    """Tool with the AXM ``kwargs: object`` dispatch catch-all."""

    @property
    def name(self) -> str:
        return "dispatch"

    def execute(self, *, path: str = ".", kwargs: object = None) -> ToolResult:
        """A dispatch-style tool."""
        return ToolResult(success=True, text="ok")


class _FakeEP:
    def __init__(self, name: str, obj: object) -> None:
        self.name = name
        self._obj = obj

    def load(self) -> object:
        return self._obj


def _eps(
    *, commands: dict[str, object] | None = None, tools: dict[str, object] | None = None
) -> Callable[..., list[_FakeEP]]:
    """Return a fake entry_points(group=...) function."""
    commands = commands or {}
    tools = tools or {}

    def _fn(*, group: str | None = None, **_: Any) -> list[_FakeEP]:
        src = (
            commands
            if group == _COMMANDS_GROUP
            else tools
            if group == _TOOLS_GROUP
            else {}
        )
        return [_FakeEP(n, o) for n, o in src.items()]

    return _fn


# ── _is_nonscalar ─────────────────────────────────────────────────────────────


class TestIsNonscalar:
    @pytest.mark.parametrize(
        ("ann", "expected"),
        [
            pytest.param(str, False, id="scalar_str"),
            pytest.param(int, False, id="scalar_int"),
            pytest.param(float, False, id="scalar_float"),
            pytest.param(bool, False, id="scalar_bool"),
            pytest.param(list, True, id="container_list"),
            pytest.param(dict, True, id="container_dict"),
            pytest.param(list[str], True, id="container_list_str"),
            pytest.param(dict[str, int], True, id="container_dict_str_int"),
            pytest.param(list[str] | None, True, id="optional_list_is_nonscalar"),
            pytest.param(str | None, False, id="optional_str_is_scalar"),
            pytest.param(inspect.Parameter.empty, False, id="empty_is_scalar"),
        ],
    )
    def test_classifies_annotation(self, ann: Any, expected: bool) -> None:
        assert is_nonscalar(ann) is expected


# ── signature construction ────────────────────────────────────────────────────


class TestPublicParams:
    def test_drops_self_and_kwargs_catchall(self) -> None:
        names = [p.name for p in public_params(_DispatchTool().execute)]
        assert "kwargs" not in names
        assert names == ["path"]

    def test_resolves_annotations_to_real_types(self) -> None:
        params = {p.name: p.annotation for p in public_params(_AuditTool().execute)}
        assert params["path"] is str
        assert params["category"] == (str | None)


class TestCliParam:
    def test_scalar_unchanged(self) -> None:
        p = inspect.Parameter(
            "path", inspect.Parameter.KEYWORD_ONLY, annotation=str, default="."
        )
        assert cli_param(p).annotation is str

    def test_required_nonscalar_becomes_str(self) -> None:
        p = inspect.Parameter("ops", inspect.Parameter.KEYWORD_ONLY, annotation=list)
        assert cli_param(p).annotation is str

    def test_optional_nonscalar_becomes_optional_str(self) -> None:
        p = inspect.Parameter(
            "ops",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=list[str] | None,
            default=None,
        )
        assert cli_param(p).annotation == (str | None)


# ── build_command_for_tool ────────────────────────────────────────────────────


class TestBuildCommand:
    def test_signature_mirrors_tool(self) -> None:
        cmd = build_command_for_tool("audit", _AuditTool())
        names = list(cmd.__signature__.parameters)
        assert names == ["path", "category"]

    def test_runs_and_prints_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd = build_command_for_tool("audit", _AuditTool())
        cmd(path="/x", category=None)
        assert "audit /x: 90" in capsys.readouterr().out

    def test_nonscalar_json_decoded(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd = build_command_for_tool("batch_edit", _BatchTool())
        cmd(path=".", operations='[{"op": "replace"}, {"op": "create"}]')
        assert "applied 2" in capsys.readouterr().out

    def test_invalid_json_exits_2(self) -> None:
        cmd = build_command_for_tool("batch_edit", _BatchTool())
        with pytest.raises(SystemExit) as exc:
            cmd(path=".", operations="not-json")
        assert exc.value.code == _EXIT_BAD_ARGS

    def test_failure_exits_1(self) -> None:
        cmd = build_command_for_tool("boom", _FailTool())
        with pytest.raises(SystemExit) as exc:
            cmd(path=".")
        assert exc.value.code == _EXIT_TOOL_ERROR

    def test_exception_exits_1(self) -> None:
        class _Raises:
            @property
            def name(self) -> str:
                return "raises"

            def execute(self, *, path: str = ".") -> ToolResult:
                raise RuntimeError("kaboom")

        cmd = build_command_for_tool("raises", _Raises())
        with pytest.raises(SystemExit) as exc:
            cmd(path=".")
        assert exc.value.code == _EXIT_TOOL_ERROR


# ── create_app (eager) ────────────────────────────────────────────────────────


class TestCreateApp:
    def test_help_text_and_name(self) -> None:
        with patch(_EP, _eps()):
            app = create_app()
        assert app.help == "AXM — Protocol execution ecosystem."
        assert app.name == ("axm",)

    def test_tool_registered_as_command(self) -> None:
        with patch(_EP, _eps(tools={"audit": _AuditTool})):
            app = create_app()
        assert "audit" in list(app)

    def test_explicit_command_wins_over_tool(self) -> None:
        def custom_audit() -> None:
            """Custom audit command."""

        with patch(
            _EP, _eps(commands={"audit": custom_audit}, tools={"audit": _AuditTool})
        ):
            app = create_app()
        assert "audit" in list(app)

    def test_broken_tool_is_skipped_not_fatal(self) -> None:
        class _Broken:
            name = "broken"

            def load(self) -> Any:
                raise ImportError("missing dep")

        def _fn(*, group: str | None = None, **_: Any) -> list[Any]:
            return [_Broken()] if group == _TOOLS_GROUP else []

        with patch(_EP, _fn):
            app = create_app()  # must not raise
        assert "broken" not in list(app)


# ── main() dispatch ───────────────────────────────────────────────────────────


def _run_main_ok() -> None:
    """Run main(), tolerating the ``SystemExit(0)`` cyclopts raises on success."""
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            raise


class TestMainDispatch:
    def test_no_args_prints_catalog(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch(_EP, _eps(tools={"audit": _AuditTool})), patch("sys.argv", ["axm"]):
            main()
        out = capsys.readouterr().out
        assert "audit" in out
        assert "Commands" in out

    def test_help_flag_prints_catalog(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", "--help"]),
        ):
            main()
        assert "audit" in capsys.readouterr().out

    def test_unknown_command_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", "ghost"]),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == _EXIT_BAD_ARGS
        assert "Unknown command: ghost" in capsys.readouterr().err

    def test_dispatch_runs_tool(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", "audit", "--path", "/z"]),
        ):
            _run_main_ok()
        assert "audit /z: 90" in capsys.readouterr().out

    def test_version_flag_prints_version(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC1: ``axm --version`` prints ``axm.__version__`` to stdout, returns 0."""
        from axm import __version__

        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", "--version"]),
        ):
            main()  # early return, no SystemExit
        assert __version__ in capsys.readouterr().out

    def test_short_version_flag_prints_version(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC2: ``axm -V`` behaves identically to ``--version``."""
        from axm import __version__

        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", "-V"]),
        ):
            main()
        assert __version__ in capsys.readouterr().out

    def test_custom_command_failure_falls_back_to_tool(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A custom command that raises at mount time, with a healthy same-named tool.
        def _raising_loader() -> Any:
            raise RuntimeError("forward ref boom")

        def _fn(*, group: str | None = None, **_: Any) -> list[Any]:
            if group == _COMMANDS_GROUP:
                ep = _FakeEP("audit", None)
                ep.load = _raising_loader  # type: ignore[method-assign]
                return [ep]
            if group == _TOOLS_GROUP:
                return [_FakeEP("audit", _AuditTool)]
            return []

        with patch(_EP, _fn), patch("sys.argv", ["axm", "audit", "--path", "/fb"]):
            _run_main_ok()
        assert "audit /fb: 90" in capsys.readouterr().out


# ── constants ─────────────────────────────────────────────────────────────────


def test_group_constants() -> None:
    assert _COMMANDS_GROUP == "axm.commands"
    assert _TOOLS_GROUP == "axm.tools"


# ── is_nonscalar: Annotated unwrapping ────────────────────────────────────


def test_is_nonscalar_unwraps_annotated_container() -> None:
    """AC1: Annotated wrapping a container classifies via the wrapped type."""
    assert is_nonscalar(Annotated[list[str], Parameter()]) is True


def test_is_nonscalar_annotated_scalar_stays_scalar() -> None:
    """AC2: Annotated wrapping a scalar stays scalar."""
    assert is_nonscalar(Annotated[str, Parameter()]) is False


def test_is_nonscalar_annotated_optional_container() -> None:
    """AC1: nested Annotated[Optional[list[str]], ...] resolves to non-scalar."""
    assert is_nonscalar(Annotated[list[str] | None, Parameter()]) is True


def test_is_nonscalar_bare_scalar_unchanged() -> None:
    """AC2: bare scalars remain scalar (unchanged classification)."""
    assert is_nonscalar(str) is False
    assert is_nonscalar(int) is False


class _AnnotatedTool:
    """Tool whose execute declares an Annotated container param."""

    captured: list[str] | None = None

    @property
    def name(self) -> str:
        return "annotated"

    def execute(self, *, items: Annotated[list[str], Parameter()]) -> ToolResult:
        """Echo the decoded items."""
        type(self).captured = items
        return ToolResult(success=True, text="ok")


def test_build_command_decodes_annotated_param() -> None:
    """AC3: an Annotated[list[str], Parameter()] param is JSON-decoded end-to-end."""
    _AnnotatedTool.captured = None
    command = build_command_for_tool("annotated", _AnnotatedTool())
    command(items='["a", "b"]')
    assert _AnnotatedTool.captured == ["a", "b"]


# ── _emit: surfacing text-less failures ──────────────────────────────


class _EmitStub:
    """Minimal ToolResult-like for ``_emit`` (it reads via ``getattr``)."""

    def __init__(
        self,
        *,
        success: bool = True,
        error: str | None = None,
        text: str | None = None,
        data: dict[str, object] | None = None,
    ) -> None:
        self.success = success
        self.error = error
        self.text = text
        self.data = data


def test_emit_writes_error_to_stderr_on_textless_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC1: a text-less failure writes ``error`` to stderr, not the repr fallback."""
    result = _EmitStub(success=False, error="boom", text=None, data=None)
    _emit(result)
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "_EmitStub" not in captured.out
    assert captured.out == ""


def test_emit_success_text_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    """AC2: a successful result with text is unchanged (stdout text, no stderr)."""
    _emit(_EmitStub(success=True, text="ok"))
    captured = capsys.readouterr()
    assert captured.out == "ok\n"
    assert captured.err == ""


def test_emit_failure_with_text_prints_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC3: a failure that carries text still prints its text (text wins)."""
    _emit(_EmitStub(success=False, error="boom", text="detail"))
    captured = capsys.readouterr()
    assert "detail" in captured.out
