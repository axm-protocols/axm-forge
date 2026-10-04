"""Read authority derived from the target test interpreter's declared dependencies."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

__all__ = [
    "ACCESS_FAILURE_KEY",
    "DependencyEnvironment",
    "DependencySources",
    "current_read_contract",
    "dependency_read_context",
    "dependency_sources",
    "resolve_read_path",
    "session_dependencies",
    "session_dependency_environment",
    "session_readable",
    "unresolved_dependency_refusals",
]


@dataclass(frozen=True)
class DependencyEnvironment:
    """Trusted runner inputs, transported with the phase contract."""

    interpreter: str
    package_root: str
    pythonpath: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> DependencyEnvironment:
        """Validate absolute runner locations; never infer a service interpreter."""
        interpreter, root = raw.get("interpreter"), raw.get("package_root")
        paths = raw.get("pythonpath", ())
        if not isinstance(interpreter, str) or not Path(interpreter).is_absolute():
            raise ValueError("dependency interpreter must be absolute")
        if not isinstance(root, str) or not Path(root).is_absolute():
            raise ValueError("dependency package_root must be absolute")
        if not isinstance(paths, (list, tuple)) or any(
            not isinstance(p, str) or not Path(p).is_absolute() for p in paths
        ):
            raise ValueError("dependency pythonpath entries must be absolute")
        return cls(interpreter, os.path.realpath(root), tuple(str(p) for p in paths))

    def to_mapping(self) -> dict[str, object]:
        """Serialize the runner inputs without granting any write prefix."""
        return {
            "interpreter": self.interpreter,
            "package_root": self.package_root,
            "pythonpath": list(self.pythonpath),
        }


@dataclass(frozen=True)
class DependencySources:
    """Import prefixes and their resolved package/file roots, never site-packages."""

    roots: tuple[tuple[str, str], ...] = ()

    def permits(self, path: str | Path) -> bool:
        """Authorize canonical dependency descendants, refusing escaping symlinks."""
        candidate = Path(path).resolve()
        return any(
            candidate == Path(root)
            or (Path(root).is_dir() and candidate.is_relative_to(Path(root)))
            for _, root in self.roots
        )

    def resolve_symbol(
        self,
        symbol: str,
        _seen: frozenset[str] = frozenset(),
    ) -> tuple[Path, str, str] | None:
        """Resolve modules and static re-exports without importing dependency code."""
        if symbol in _seen:
            return None
        resolved = self._locate_symbol(symbol)
        if resolved is None or not resolved[2]:
            return resolved
        imported = _reexport_reference(resolved)
        if imported is not None:
            return self.resolve_symbol(imported, _seen | {symbol})
        return resolved

    def _locate_symbol(self, symbol: str) -> tuple[Path, str, str] | None:
        """Resolve the longest module prefix without importing dependency code."""
        parts = symbol.split(".")
        for length in range(len(parts), 0, -1):
            module = ".".join(parts[:length])
            for prefix, raw in self.roots:
                if module != prefix and not module.startswith(prefix + "."):
                    continue
                root = Path(raw)
                if root.is_file() and module != prefix:
                    continue
                suffix = module[len(prefix) :].lstrip(".").split(".")
                base = root.joinpath(*suffix) if suffix != [""] else root
                candidates = (
                    (base / "__init__.py", base.with_suffix(".py"))
                    if root.is_dir()
                    else (root,)
                )
                for candidate in candidates:
                    if candidate.is_file() and self.permits(candidate):
                        return candidate.resolve(), module, ".".join(parts[length:])
        return None


def _reexport_reference(resolved: tuple[Path, str, str]) -> str | None:
    """Follow an explicit import binding, keeping resolution inside the closure."""
    import ast

    path, module, member = resolved
    head, *tail = member.split(".")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if (alias.asname or alias.name) != head:
                continue
            if node.level:
                parent = package.split(".")[: len(package.split(".")) - node.level + 1]
                imported_module = ".".join(
                    [*parent, *([node.module] if node.module else [])]
                )
            else:
                imported_module = node.module or ""
            return ".".join([imported_module, alias.name, *tail]).strip(".")
    return None


def dependency_sources(environment: DependencyEnvironment) -> DependencySources:
    """Probe distribution metadata in the test environment; errors fail closed."""
    probe = Path(__file__).with_name("_dependency_probe.py")
    result = subprocess.run(  # noqa: S603 - trusted runner, no shell
        [environment.interpreter, "-I", "-B", str(probe)],
        input=json.dumps(environment.to_mapping()),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"dependency resolution failed: {result.stderr.strip()}")
    roots = json.loads(result.stdout)
    if not isinstance(roots, list):
        raise ValueError("invalid dependency resolution response")
    return DependencySources(
        tuple((str(item[0]), os.path.realpath(item[1])) for item in roots)
    )


def session_dependencies() -> DependencySources:
    """Get read authority from the current session, never from ambient sys.path."""
    # The transport context wins over process environment.

    contract = current_read_contract()
    if contract is None or contract.dependency_environment is None:
        return DependencySources()
    return dependency_sources(contract.dependency_environment)


# Context variables keep concurrent MCP sessions independent. None explicitly
# suppresses any ambient contract when the transport has no bound session.


if TYPE_CHECKING:
    from axm.tools.write_scope import WriteContract

_UNBOUND = object()
_READ_CONTRACT: ContextVar[object] = ContextVar(
    "dependency_read_contract", default=_UNBOUND
)


def current_read_contract() -> WriteContract | None:
    """Return the transport-bound contract, falling back only for local CLI calls."""
    from axm.tools.write_scope import WriteContract, write_contract_from_env

    value = _READ_CONTRACT.get()
    if value is _UNBOUND:
        return write_contract_from_env()
    return value if isinstance(value, WriteContract) else None


@contextmanager
def dependency_read_context(contract: WriteContract | None) -> Iterator[None]:
    """Bind trusted transport authority for one tool invocation."""
    token = _READ_CONTRACT.set(contract)
    try:
        yield
    finally:
        _READ_CONTRACT.reset(token)


def session_readable(path: Path) -> bool:
    """Use precisely the same canonical read decision as the transport."""
    contract = current_read_contract()
    return contract is not None and contract.readable(str(path.resolve()))


def resolve_read_path(base: Path, candidate: str) -> Path | None:
    """Resolve a local read or an authorized external dependency source."""
    path = (base / candidate).resolve()
    contract = current_read_contract()
    if contract is not None:
        return path if contract.readable(str(path)) else None
    return path if path.is_relative_to(base.resolve()) else None


ACCESS_FAILURE_KEY = "axm_dependency_access_failure"


def _symbol_is_defined(resolved: tuple[Path, str, str]) -> bool:
    path, _, member = resolved
    if not member:
        return True
    import ast

    nodes = ast.parse(path.read_text(encoding="utf-8")).body
    for part in member.split("."):
        node = next((n for n in nodes if getattr(n, "name", None) == part), None)
        if node is None:
            return False
        nodes = node.body if isinstance(node, ast.ClassDef) else []
    return True


def _call_sources(
    name: str,
    arguments: Mapping[str, object],
    environment: DependencyEnvironment,
    sources: DependencySources,
) -> list[str]:
    if name == "read_file":
        file = arguments.get("file")
        base = arguments.get("path", environment.package_root)
        if isinstance(file, str) and isinstance(base, str):
            path = (Path(base) / file).resolve()
            return [str(path)] if sources.permits(path) else []
        return []
    queries = arguments.get("symbols", ())
    if not isinstance(queries, (list, tuple)):
        queries = ()
    paths = []
    for query in (*queries, arguments.get("symbol"), arguments.get("name")):
        if isinstance(query, str) and (resolved := sources.resolve_symbol(query)):
            if _symbol_is_defined(resolved):
                paths.append(str(resolved[0]))
    return paths


def _read_failed(call: Mapping[str, object]) -> bool:
    result = call.get("result")
    if isinstance(result, Mapping):
        return result.get("success") is False
    text = str(result)
    return call.get("ok") is False or text.startswith(
        ("✗", "success: False", "read_file | ESCAPE", "error:")
    )


def unresolved_dependency_refusals(
    calls: tuple[dict[str, object], ...],
    environment: DependencyEnvironment,
) -> tuple[str, ...]:
    """Attribute unresolved dependency access failures using backend evidence."""
    sources = dependency_sources(environment)
    failed: dict[str, str] = {}
    for call in calls:
        name = str(call.get("name", "")).rsplit("__", 1)[-1]
        arguments = call.get("arguments")
        if name not in {"read_file", "ast_inspect", "ast_search"} or not isinstance(
            arguments, Mapping
        ):
            continue
        paths = _call_sources(name, arguments, environment, sources)
        text = str(call.get("result"))
        if not _read_failed(call):
            for location in paths:
                failed.pop(location, None)
        elif any(
            marker in text
            for marker in (
                "ESCAPE",
                "not found",
                "Permission denied",
                "path escapes",
                "dependency resolution failed",
            )
        ):
            for location in paths:
                failed[location] = (
                    f"{name} {location} arguments={dict(arguments)!r}: {text}"
                )
    return tuple(failed.values())


def session_dependency_environment(
    project_path: str | Path,
) -> DependencyEnvironment | None:
    """Resolve a declared runtime, refusing implicit execution via read authority.

    Return None only without a transport/local contract. Under a contract a
    matching declared environment is mandatory, including for readable roots.
    Keep the interpreter's lexical venv path; resolving its symlink loses venv
    activation semantics.
    """
    contract = current_read_contract()
    if contract is None:
        return None
    environments = contract.dependency_environments
    if contract.dependency_environment is not None:
        environments = (contract.dependency_environment, *environments)
    root = Path(project_path).resolve()
    matches = [
        env
        for env in environments
        if root.is_relative_to(Path(env.package_root).resolve())
    ]
    if not matches:
        raise ValueError(f"no declared runtime for: {root}")
    selected = _unambiguous_runtime(matches, root)
    if not Path(selected.interpreter).is_file():
        raise ValueError(
            f"declared runtime interpreter missing: {selected.interpreter}"
        )
    return selected


def _unambiguous_runtime(
    matches: list[DependencyEnvironment],
    root: Path,
) -> DependencyEnvironment:
    """Select the most specific root, refusing equally specific conflicts."""
    depth = max(len(Path(env.package_root).parts) for env in matches)
    deepest = {env for env in matches if len(Path(env.package_root).parts) == depth}
    if len(deepest) != 1:
        raise ValueError(f"ambiguous declared runtime for: {root}")
    return deepest.pop()
