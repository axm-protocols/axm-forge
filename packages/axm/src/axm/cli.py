"""AXM CLI — one command per tool, auto-generated and lazily dispatched.

Every ``axm.tools`` entry point becomes a CLI command (``axm audit``,
``axm git_commit``, …) with the *same* typed signature as the tool's
``execute`` — so a tool's CLI and its MCP schema never drift.  Explicit
``axm.commands`` entry points keep priority over the auto-generated ones.

Dispatch is **lazy**: a CLI process lives for one invocation, so we resolve
the requested command from ``sys.argv`` and import only that one entry point.
``axm --help`` (or no command) lists every name from entry-point metadata
without importing a single tool module.

Output is the tool's ``ToolResult.text`` (token-optimised), falling back to a
JSON rendering of ``data`` when there is no text.  Non-scalar parameters
(``list`` / ``dict`` / pydantic models) are passed as a single JSON string and
decoded before the call — the one convention that keeps tool-signature ==
CLI-signature without CLI-only flags.

Exit codes: ``0`` success, ``1`` tool error, ``2`` bad args (cyclopts).
"""

from __future__ import annotations

import importlib.metadata
import inspect
import json
import logging
import sys
import types
import typing
from typing import Annotated, Any, Union

import cyclopts

__all__ = ["build_command_for_tool", "create_app", "main"]

logger = logging.getLogger(__name__)

_COMMANDS_GROUP = "axm.commands"
_TOOLS_GROUP = "axm.tools"

# Parameter annotations passed verbatim as a single CLI token (scalars).
# Anything else is treated as non-scalar and round-tripped through JSON.
_SCALARS = (str, int, float, bool)


# ── entry-point discovery (metadata only — no module import) ──────────────────


def _entry_points(group: str) -> dict[str, importlib.metadata.EntryPoint]:
    """Map name -> entry point for *group* (no ``.load()`` — pure metadata)."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=group)}


def _load(ep: importlib.metadata.EntryPoint) -> Any:
    """Load an entry point and instantiate it when it is a class."""
    obj = ep.load()
    return obj() if isinstance(obj, type) else obj


# ── signature / wrapper construction ──────────────────────────────────────────


def is_nonscalar(annotation: Any) -> bool:
    """Whether *annotation* should be passed as JSON (not a plain scalar).

    Unwraps ``Optional`` / ``X | None`` and inspects the non-``None`` member:
    container types (``list``/``dict``/``tuple``/``set``) and arbitrary classes
    that are not ``str``/``int``/``float``/``bool`` count as non-scalar.
    """
    if annotation is inspect.Parameter.empty:
        return False
    origin = typing.get_origin(annotation)
    if origin is Annotated:
        return is_nonscalar(typing.get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        members = [a for a in typing.get_args(annotation) if a is not type(None)]
        return any(is_nonscalar(m) for m in members)
    if origin in (list, dict, tuple, set):
        return True
    return isinstance(annotation, type) and not issubclass(annotation, _SCALARS)


def _exec_callable(tool_obj: Any) -> Any:
    """Return the tool's executable (``.execute`` or the object if plain)."""
    if callable(tool_obj) and not hasattr(tool_obj, "execute"):
        return tool_obj
    return tool_obj.execute


def _resolve_hints(fn: Any) -> dict[str, Any]:
    """Best-effort resolved type hints for *fn* (empty on failure)."""
    try:
        return typing.get_type_hints(fn)
    except Exception:  # noqa: BLE001 — unresolved forward refs must not crash the CLI
        return {}


def public_params(fn: Any) -> list[inspect.Parameter]:
    """Typed params of *fn* with annotations resolved to real types.

    Drops ``self``, ``**kwargs`` and a dispatch ``kwargs: object`` catch-all
    (AXM tools accept the latter for forward-compat).  Annotations are resolved
    via ``get_type_hints`` so cyclopts never has to evaluate string forward
    references (which may name symbols absent from this process).
    """
    sig = inspect.signature(fn)
    hints = _resolve_hints(fn)
    params: list[inspect.Parameter] = []
    for p in sig.parameters.values():
        if p.name in ("self", "kwargs") or p.kind is inspect.Parameter.VAR_KEYWORD:
            continue
        resolved = hints.get(p.name, p.annotation)
        # If a hint is still an unresolved string, fall back to Any (str-like).
        if isinstance(resolved, str):
            resolved = inspect.Parameter.empty
        params.append(p.replace(annotation=resolved))
    return params


def cli_param(p: inspect.Parameter) -> inspect.Parameter:
    """Map a tool param to its CLI form.

    Non-scalar params become a JSON string (``str`` when required, ``str | None``
    when optional so cyclopts accepts the ``None`` default without a strict
    string validation error).
    """
    if not is_nonscalar(p.annotation):
        return p
    if p.default is inspect.Parameter.empty:
        return p.replace(annotation=str)
    return p.replace(annotation=str | None, default=p.default)


def _nonscalar_names(params: list[inspect.Parameter]) -> frozenset[str]:
    """Names of params that arrive as JSON strings and must be decoded."""
    return frozenset(p.name for p in params if is_nonscalar(p.annotation))


def _emit(result: Any) -> None:
    """Render a ToolResult-like: text to stdout first, else JSON of data.

    A text-less failure (``success is False`` with a non-empty ``error``)
    writes the error to stderr instead of falling through to the ``repr``.
    """
    text = getattr(result, "text", None)
    if isinstance(text, str):
        sys.stdout.write(text + "\n")
        return
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return
    error = getattr(result, "error", None)
    if getattr(result, "success", True) is False and isinstance(error, str) and error:
        sys.stderr.write(error + "\n")
        return
    sys.stdout.write(str(result) + "\n")


def build_command_for_tool(tool_name: str, tool_obj: Any) -> Any:
    """Build a cyclopts command callable from an AXMTool (or plain callable).

    The returned function carries the tool's typed ``__signature__`` (non-scalar
    params reshaped to JSON strings) and its docstring, runs ``execute`` /
    the callable, prints ``result.text``, and exits non-zero on failure.

    Args:
        tool_name: The command name.
        tool_obj: The tool instance (or plain callable).

    Returns:
        A function suitable for ``cyclopts.App.command``.
    """
    exec_fn = _exec_callable(tool_obj)
    params = public_params(exec_fn)
    json_params = _nonscalar_names(params)

    def _command(**kwargs: Any) -> None:
        for key in json_params & kwargs.keys():
            value = kwargs[key]
            if isinstance(value, str):
                try:
                    kwargs[key] = json.loads(value)
                except json.JSONDecodeError as exc:
                    sys.stderr.write(f"{key}: invalid JSON: {exc}\n")
                    raise SystemExit(2) from exc
        try:
            result = exec_fn(**kwargs)
        except Exception as exc:  # surface any tool error on stderr
            sys.stderr.write(f"{exc}\n")
            raise SystemExit(1) from exc
        _emit(result)
        if getattr(result, "success", True) is False:
            raise SystemExit(1)

    cli_params = [cli_param(p) for p in params]
    _command.__name__ = tool_name
    _command.__doc__ = exec_fn.__doc__ or f"Run the {tool_name} tool."
    _command.__signature__ = inspect.Signature(cli_params)  # type: ignore[attr-defined]
    # Mirror the resolved annotations onto __annotations__ as real types (not
    # strings): cyclopts calls get_type_hints() on the command, which reads
    # __annotations__ and would otherwise try to eval our closure's stringised
    # ``**kwargs``/forward refs against this module's globals.
    _command.__annotations__ = {
        p.name: p.annotation
        for p in cli_params
        if p.annotation is not inspect.Parameter.empty
    }
    _command.__annotations__["return"] = None
    return _command


# ── app assembly ──────────────────────────────────────────────────────────────


def _new_app() -> cyclopts.App:
    return cyclopts.App(
        name="axm", help="AXM — Protocol execution ecosystem.", version_flags=[]
    )


def create_app() -> cyclopts.App:
    """Create an app with *every* command registered (eager).

    This loads all entry points — convenient for tests and introspection, but
    NOT the path used by ``main`` (which dispatches lazily).  Explicit
    ``axm.commands`` win over auto-generated tool commands of the same name.

    Returns:
        A fully-populated cyclopts App.
    """
    app = _new_app()
    commands = _entry_points(_COMMANDS_GROUP)
    tools = _entry_points(_TOOLS_GROUP)

    for name, ep in commands.items():
        try:
            app.command(_load(ep), name=name)
        except Exception:  # noqa: BLE001 — a broken package must not sink the CLI
            logger.warning("Failed to load command '%s'", name, exc_info=True)

    for name, ep in tools.items():
        if name in commands:
            continue
        try:
            app.command(build_command_for_tool(name, _load(ep)), name=name)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to auto-register tool '%s'", name, exc_info=True)

    return app


def _print_catalog(commands: dict[str, Any], tools: dict[str, Any]) -> None:
    """List available commands from metadata alone (no tool import)."""
    names = sorted(set(commands) | set(tools))
    out = sys.stdout
    out.write("AXM — Protocol execution ecosystem.\n\n")
    out.write("Usage: axm COMMAND [ARGS]...\n\n")
    if not names:
        out.write(
            "No commands available. Install AXM packages to add commands.\n"
            "  uv pip install axm[all]\n"
        )
        return
    out.write(f"Commands ({len(names)}):\n")
    for name in names:
        out.write(f"  {name}\n")
    out.write("\nRun 'axm COMMAND --help' for command details.\n")


def _resolve_command(argv: list[str]) -> str | None:
    """First non-flag token in *argv* — the command name, if any."""
    return next((a for a in argv if not a.startswith("-")), None)


def main() -> None:
    """CLI entry point with lazy, dispatch-first command resolution.

    Resolves the command from ``sys.argv`` and imports only that entry point.
    ``axm`` / ``axm --help`` / an unknown command print the catalog (built from
    metadata, no tool import).
    """
    argv = sys.argv[1:]
    commands = _entry_points(_COMMANDS_GROUP)
    tools = _entry_points(_TOOLS_GROUP)
    cmd = _resolve_command(argv)

    if cmd is None or (cmd not in commands and cmd not in tools):
        if cmd is None or cmd in ("-h", "--help"):
            _print_catalog(commands, tools)
            return
        # Unknown command: show catalog on stderr, exit 2 (bad usage).
        sys.stderr.write(f"Unknown command: {cmd}\n\n")
        _print_catalog(commands, tools)
        raise SystemExit(2)

    app = _build_single_app(cmd, commands, tools)
    app(argv)


def _build_single_app(
    cmd: str,
    commands: dict[str, importlib.metadata.EntryPoint],
    tools: dict[str, importlib.metadata.EntryPoint],
) -> cyclopts.App:
    """Build a one-command app, preferring an explicit ``axm.commands`` entry.

    If the explicit command fails to mount (e.g. a fragile custom cyclopts
    sub-app with an unresolved forward reference) and a same-named tool exists,
    fall back to the auto-generated tool command on a *fresh* app — the
    resilient path the migration ultimately standardises on.  ``app.command``
    mutates the app even when it raises, so the fallback must start clean.
    """
    if cmd in commands:
        app = _new_app()
        try:
            app.command(_load(commands[cmd]), name=cmd)
            return app
        except Exception as exc:  # fall back to the tool when possible
            if cmd not in tools:
                raise
            logger.warning(
                "Custom command '%s' failed to mount (%s); using "
                "auto-generated tool command instead.",
                cmd,
                exc,
            )
    app = _new_app()
    app.command(build_command_for_tool(cmd, _load(tools[cmd])), name=cmd)
    return app


if __name__ == "__main__":
    main()
