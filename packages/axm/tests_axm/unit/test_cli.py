"""Tests for the auto-generating, dispatch-first AXM CLI."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Annotated, Any
from unittest.mock import patch

import pytest
from cyclopts import Parameter

from axm.cli import (
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
_COMMANDS_GROUP = "axm.commands"
_TOOLS_GROUP = "axm.tools"


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


class _LocalJsonOutputTool:
    """Model the output contract shared by the three tools with a local flag."""

    label = ""

    def execute(self, *, path: str = ".", json_output: bool = False) -> ToolResult:
        mode = "json" if json_output else "human"
        return ToolResult(success=True, text=f"{self.label}:{mode}")


class _ScaffoldLocalJsonTool(_LocalJsonOutputTool):
    label = "scaffold"


class _ReserveLocalJsonTool(_LocalJsonOutputTool):
    label = "reserve"


class _CheckLocalJsonTool(_LocalJsonOutputTool):
    label = "check"


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


class _CanonicalFailTool:
    """Fails the canonical MCP way: ``success=False`` + ``error``, default data.

    ``data`` is left to its ``default_factory=dict`` (an empty ``{}``) — the exact
    shape ``ToolResult(success=False, error=...)`` produces.  The empty dict must
    not shadow the error (the false-green this guards).
    """

    @property
    def name(self) -> str:
        return "boom"

    def execute(self, *, path: str = ".") -> ToolResult:
        """Fail with only an ``error`` set (``data`` defaults to ``{}``)."""
        return ToolResult(success=False, error="canonical MCP error")


class _DispatchTool:
    """Tool with the AXM ``kwargs: object`` dispatch catch-all."""

    @property
    def name(self) -> str:
        return "dispatch"

    def execute(self, *, path: str = ".", kwargs: object = None) -> ToolResult:
        """A dispatch-style tool."""
        return ToolResult(success=True, text="ok")


def _wrapped_execute_signature(
    self: object, *, cadence: dict[str, object]
) -> ToolResult:
    """Typed signature exposed by a ``**kwargs`` dispatch tool."""
    raise NotImplementedError


class _WrappedDispatchTool:
    """Dispatch tool whose public signature is carried by ``__wrapped__``."""

    captured: object = None

    def execute(self, **kwargs: object) -> ToolResult:
        self.captured = kwargs["cadence"]
        return ToolResult(success=True, text="ok")


_WrappedDispatchTool.execute.__wrapped__ = _wrapped_execute_signature


type JsonValue = (
    str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
)


type TextAlias = str | list[str]
type RecursiveTextAlias = str | list[RecursiveTextAlias] | dict[str, RecursiveTextAlias]


class _RecursiveAliasTool:
    """Tool whose sole parameter uses a recursive PEP 695 JSON alias."""

    captured: JsonValue = None

    def execute(self, *, data: JsonValue) -> ToolResult:
        """Echo a recursively typed JSON value."""
        type(self).captured = data
        return ToolResult(success=True, text=str(data))


class _TextUnionTool:
    captured: object = None

    def execute(self, *, data: str | list[str]) -> ToolResult:
        type(self).captured = data
        return ToolResult(success=True, text=str(data))


class _TextAliasTool:
    captured: object = None

    def execute(self, *, data: TextAlias) -> ToolResult:
        type(self).captured = data
        return ToolResult(success=True, text=str(data))


class _RecursiveTextAliasTool:
    captured: object = None

    def execute(self, *, data: RecursiveTextAlias) -> ToolResult:
        type(self).captured = data
        return ToolResult(success=True, text=str(data))


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


def test_recursive_type_alias_is_nonscalar() -> None:
    """AC1: recursive PEP 695 aliases are non-scalar without recursion."""
    parameter = inspect.Parameter(
        "data", inspect.Parameter.KEYWORD_ONLY, annotation=JsonValue
    )
    _RecursiveAliasTool.captured = None
    command = build_command_for_tool("recursive", _RecursiveAliasTool())

    assert is_nonscalar(JsonValue) is True
    assert cli_param(parameter).annotation is str
    command(data='{"items": [1, "é", null]}')
    assert _RecursiveAliasTool.captured == {"items": [1, "é", None]}


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
        assert names == ["path", "category", "json_output"]

    def test_signature_params_are_positional_or_keyword(self) -> None:
        """Keyword-only tool params relax to POSITIONAL_OR_KEYWORD for ``axm t .``."""
        cmd = build_command_for_tool("audit", _AuditTool())
        kinds = {p.kind for p in cmd.__signature__.parameters.values()}
        assert kinds == {inspect.Parameter.POSITIONAL_OR_KEYWORD}

    def test_runs_and_prints_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd = build_command_for_tool("audit", _AuditTool())
        cmd(path="/x", category=None)
        assert "audit /x: 90" in capsys.readouterr().out

    def test_shared_structured_mode_preserves_default_and_local_output_modes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC1: shared JSON is additive and local JSON flags keep their contract."""
        audit = build_command_for_tool("audit", _AuditTool())

        audit(path="/x", category=None)
        assert capsys.readouterr().out.strip() == "audit /x: 90"

        audit(path="/x", category=None, json_output=True)
        assert json.loads(capsys.readouterr().out) == {"score": 90}

        local_tools = (
            ("scaffold", _ScaffoldLocalJsonTool()),
            ("reserve", _ReserveLocalJsonTool()),
            ("check", _CheckLocalJsonTool()),
        )
        for name, tool in local_tools:
            command = build_command_for_tool(name, tool)
            assert list(command.__signature__.parameters).count("json_output") == 1
            command(path="/x", json_output=False)
            assert capsys.readouterr().out.strip() == f"{name}:human"
            command(path="/x", json_output=True)
            assert capsys.readouterr().out.strip() == f"{name}:json"

    def test_positional_args_bind_to_params(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Positional tokens map back onto param names (the ``axm audit .`` form)."""
        cmd = build_command_for_tool("audit", _AuditTool())
        cmd("/pos", "lint")
        assert "audit /pos: 90" in capsys.readouterr().out

    def test_nonscalar_json_decoded(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd = build_command_for_tool("batch_edit", _BatchTool())
        cmd(path=".", operations='[{"op": "replace"}, {"op": "create"}]')
        assert "applied 2" in capsys.readouterr().out

    def test_nonscalar_json_decoded_from_wrapped_signature(self) -> None:
        tool = _WrappedDispatchTool()
        cmd = build_command_for_tool("wrapped", tool)

        cmd(cadence='{"kind": "weekly", "at": "04:30", "weekday": "mon"}')

        assert tool.captured == {
            "kind": "weekly",
            "at": "04:30",
            "weekday": "mon",
        }

    def test_recursive_alias_decodes_unicode_scalar(self) -> None:
        """AC1: the recursive alias binds JSON and preserves decoded Unicode."""
        tool = _RecursiveAliasTool()
        command = build_command_for_tool("recursive", tool)
        value = "café naïve résumé 漢字 こんにちは"

        command(json.dumps(value, ensure_ascii=False))

        assert tool.captured == value
        assert isinstance(tool.captured, str)

    def test_recursive_alias_decodes_nested_object(self) -> None:
        """AC2: the recursive alias decodes nested objects, lists, and null."""
        tool = _RecursiveAliasTool()
        command = build_command_for_tool("recursive", tool)

        command('{"items": [1, "é", {"k": null}]}')

        assert tool.captured == {"items": [1, "é", {"k": None}]}

    def test_str_admitting_union_preserves_non_json_free_text(self) -> None:
        """AC1: a str-admitting union delivers non-JSON Unicode text verbatim."""
        tool = _TextUnionTool()
        command = build_command_for_tool("text-union", tool)
        value = "résumé  long"

        command(data=value)

        assert tool.captured == value

    def test_pep695_aliases_preserve_non_json_free_text(self) -> None:
        """AC2: plain and recursive PEP 695 aliases preserve free text."""
        plain_tool = _TextAliasTool()
        recursive_tool = _RecursiveTextAliasTool()
        plain_command = build_command_for_tool("text-alias", plain_tool)
        recursive_command = build_command_for_tool(
            "recursive-text-alias", recursive_tool
        )
        plain_value = "café   brut"
        recursive_value = "élan  récursif"

        recursive_command(data=recursive_value)
        plain_command(data=plain_value)

        assert recursive_tool.captured == recursive_value
        assert plain_tool.captured == plain_value

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

    def test_canonical_failure_surfaces_error_on_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Canonical ``ToolResult(success=False, error=...)`` surfaces on stderr.

        The default ``data`` is an empty ``{}`` — it must NOT be printed to
        stdout in place of the error (the false-green this guards). The error
        reaches stderr and the command exits 1.
        """
        cmd = build_command_for_tool("boom", _CanonicalFailTool())
        with pytest.raises(SystemExit) as exc:
            cmd(path=".")
        assert exc.value.code == _EXIT_TOOL_ERROR
        captured = capsys.readouterr()
        assert "canonical MCP error" in captured.err
        assert captured.out.strip() != "{}"
        assert "canonical MCP error" not in captured.out

    def test_failure_with_text_prints_text(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AXM-2017: a failure carrying text still prints its text (text wins)."""
        cmd = build_command_for_tool("boom", _FailTool())
        with pytest.raises(SystemExit):
            cmd(path=".")
        assert "error: nope" in capsys.readouterr().out

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

    @pytest.mark.parametrize("flag", ["--version", "-V"])
    def test_version_flag_prints_version(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC1/AC2: ``axm --version`` and ``axm -V`` print ``__version__``, return 0."""
        from axm import __version__

        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", flag]),
        ):
            main()  # early return, no SystemExit
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

    def test_broken_tool_load_exits_1_without_traceback(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A tool entry point that fails to import exits 1 with a clean message.

        The lazy dispatch path must surface a readable error on stderr, not a raw
        ``ModuleNotFoundError`` traceback (``axm echo_code`` without its dep).
        """

        def _fn(*, group: str | None = None, **_: Any) -> list[Any]:
            if group == _TOOLS_GROUP:
                ep = _FakeEP("echo_code", None)
                ep.load = _raising_import  # type: ignore[method-assign]
                return [ep]
            return []

        with (
            patch(_EP, _fn),
            patch("sys.argv", ["axm", "echo_code", "--path", "."]),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == _EXIT_TOOL_ERROR
        captured = capsys.readouterr()
        assert "echo_code" in captured.err
        assert "failed to load" in captured.err.lower()
        assert "Traceback (most recent call last)" not in captured.err


def _raising_import() -> Any:
    """A loader that fails like a missing optional dependency."""
    raise ModuleNotFoundError("No module named 'torch'")


# ── positional / keyword dispatch through main() ──────────────────────────────


class TestPositionalDispatch:
    def test_positional_path_dispatches_through_main(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The documented ergonomic form ``axm audit .`` dispatches end-to-end."""
        with (
            patch(_EP, _eps(tools={"audit": _AuditTool})),
            patch("sys.argv", ["axm", "audit", "/pos"]),
        ):
            _run_main_ok()
        assert "audit /pos: 90" in capsys.readouterr().out


# ── is_nonscalar: Annotated unwrapping ────────────────────────────────────


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        pytest.param(Annotated[list[str], Parameter()], True, id="annotated_container"),
        pytest.param(Annotated[str, Parameter()], False, id="annotated_scalar"),
        pytest.param(
            Annotated[list[str] | None, Parameter()],
            True,
            id="annotated_optional_container",
        ),
    ],
)
def test_is_nonscalar_unwraps_annotated(annotation: Any, expected: bool) -> None:
    """AC1/AC2: is_nonscalar unwraps Annotated and classifies the wrapped type."""
    assert is_nonscalar(annotation) is expected


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
