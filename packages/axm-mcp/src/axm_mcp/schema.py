from __future__ import annotations

import inspect
import re
from types import ModuleType
from typing import Protocol, cast

__all__ = [
    "IntrospectableFn",
    "apply_signature",
    "collect_dispatcher_params",
    "extract_docstring_params",
    "signature_params",
]


class IntrospectableFn(Protocol):
    """Structural protocol for any callable that supports ``inspect.signature``."""

    __doc__: str | None

    def __call__(self, **kwargs: object) -> object: ...


class _SignatureTarget(Protocol):
    """Anything onto which a typed ``__signature__`` can be set."""

    __doc__: str | None


def _find_actions_dict(
    module: ModuleType | None,
) -> dict[str, IntrospectableFn] | None:
    """Find a ``_*_ACTIONS`` dict on *module*."""
    if module is None:
        return None
    for attr_name in dir(module):
        if attr_name.endswith("_ACTIONS"):
            candidate = getattr(module, attr_name, None)
            if isinstance(candidate, dict):
                # Runtime guarantee: ``_*_ACTIONS`` always maps str → callable.
                return cast("dict[str, IntrospectableFn]", candidate)
    return None


def _safe_signature(fn: IntrospectableFn) -> inspect.Signature | None:
    """Resolve a signature, falling back to non-evaluated annotations."""
    try:
        return inspect.signature(fn, eval_str=True)
    except (ValueError, TypeError, NameError):
        try:
            return inspect.signature(fn)
        except (ValueError, TypeError):
            return None


def _accumulate_optional_params(
    sig: inspect.Signature,
    seen: dict[str, inspect.Parameter],
) -> None:
    """Add new typed params from *sig* into *seen*, made optional."""
    for p in sig.parameters.values():
        skip = p.name == "self" or p.kind == inspect.Parameter.VAR_KEYWORD
        if skip or p.name in seen:
            continue
        default = p.default if p.default is not inspect.Parameter.empty else None
        seen[p.name] = p.replace(default=default)


def _union_subfn_params(
    actions_dict: dict[str, IntrospectableFn],
) -> dict[str, inspect.Parameter]:
    """Collect all typed params from sub-functions, made optional."""
    seen: dict[str, inspect.Parameter] = {}
    for sub_fn in actions_dict.values():
        sub_sig = _safe_signature(sub_fn)
        if sub_sig is not None:
            _accumulate_optional_params(sub_sig, seen)
    return seen


# Regex: matches "    param_name (optional type): description" or
#        "    param_name: description" in Google-style Args blocks.
_ARG_LINE_RE = re.compile(
    r"^\s{4,}(\w+)"  # param name (indented 4+ spaces)
    r"(?:\s*\(([^)]+)\))?"  # optional (type) in parens
    r"\s*:"  # colon separator
    r"\s*(.*)$",  # description (captured but unused)
)

# Map common docstring type hints to Python annotations.
_TYPE_MAP: dict[str, type[object]] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "Path": str,  # paths come as str over MCP
}


_SECTION_END_RE = re.compile(r"^[A-Z]\w*:\s*$")


def _is_section_end(stripped: str) -> bool:
    return (
        bool(stripped)
        and not stripped.startswith("**")
        and ":" in stripped
        and bool(_SECTION_END_RE.match(stripped))
    )


def _resolve_annotation(type_hint: str | None) -> type[object]:
    if not type_hint:
        return inspect.Parameter.empty
    clean_type = type_hint.split(",")[0].strip()
    return _TYPE_MAP.get(clean_type, inspect.Parameter.empty)


def _parse_arg_line(line: str) -> inspect.Parameter | None:
    match = _ARG_LINE_RE.match(line)
    if not match:
        return None
    return inspect.Parameter(
        match.group(1),
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=None,
        annotation=_resolve_annotation(match.group(2)),
    )


def extract_docstring_params(
    docstring: str | None,
) -> list[inspect.Parameter]:
    """Parse Google-style ``Args:`` section into ``inspect.Parameter`` objects.

    This is the fallback for non-dispatcher tools whose ``execute(**kwargs)``
    has no typed parameters in the signature but documents them in the
    docstring.

    Args:
        docstring: The docstring to parse.

    Returns:
        List of keyword-only ``inspect.Parameter`` with default ``None``.
        Empty list if no ``Args:`` section found.
    """
    if not docstring:
        return []

    in_args = False
    params: list[inspect.Parameter] = []

    for line in docstring.splitlines():
        stripped = line.strip()

        if stripped in ("Args:", "Keyword Args:"):
            in_args = True
            continue

        if not in_args:
            continue

        if _is_section_end(stripped):
            break

        if stripped.startswith("**"):
            continue

        param = _parse_arg_line(line)
        if param is not None:
            params.append(param)

    return params


def collect_dispatcher_params(
    fn: IntrospectableFn,
    *,
    override_module: ModuleType | None = None,
) -> list[inspect.Parameter] | None:
    """Collect union of typed params from dispatcher sub-functions.

    A *dispatcher* is a function with ``action: str`` + ``**kwargs``
    that routes to sub-functions stored in a module-level ``_*_ACTIONS``
    dict.  This helper introspects all sub-functions and returns the
    union of their parameters (all made optional).

    Args:
        fn: The dispatcher function to introspect.
        override_module: Module to search for ``_*_ACTIONS`` dict.
            If *None*, uses ``inspect.getmodule(fn)``.

    Returns:
        List of ``inspect.Parameter`` if *fn* is a dispatcher, else *None*.
    """
    sig = _safe_signature(fn)
    if sig is None:
        return None

    params = list(sig.parameters.values())

    # Detect dispatcher pattern: has 'action' param + VAR_KEYWORD
    has_action = any(p.name == "action" for p in params)
    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    if not (has_action and has_varkw):
        return None

    # Find the _ACTIONS dict by convention
    module = override_module or inspect.getmodule(fn)
    actions_dict = _find_actions_dict(module)
    if not actions_dict:
        return None

    # Collect + build final: action (required) + sub-fn params (optional)
    seen = _union_subfn_params(actions_dict)
    action_param = next(p for p in params if p.name == "action")
    return [action_param, *sorted(seen.values(), key=lambda p: p.name)]


def signature_params(exec_fn: IntrospectableFn) -> list[inspect.Parameter]:
    """Strip ``self`` / ``**kwargs`` from *exec_fn*, falling back to its docstring."""
    try:
        exec_sig = inspect.signature(exec_fn, eval_str=True)
    except (ValueError, TypeError, NameError):
        exec_sig = inspect.signature(exec_fn)
    params = [
        p
        for p in exec_sig.parameters.values()
        if p.name != "self" and p.kind != inspect.Parameter.VAR_KEYWORD
    ]
    return params or extract_docstring_params(exec_fn.__doc__)


def apply_signature(
    wrapper: _SignatureTarget,
    exec_fn: IntrospectableFn,
    override_module: ModuleType | None,
) -> None:
    """Set the typed ``__signature__`` so FastMCP builds the right schema."""
    try:
        union_params = collect_dispatcher_params(
            exec_fn, override_module=override_module
        )
        params = union_params if union_params is not None else signature_params(exec_fn)
        wrapper.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            parameters=params,
            return_annotation=dict[str, object] | str,
        )
    except (ValueError, TypeError):
        pass  # Fall back to generic **kwargs if introspection fails
