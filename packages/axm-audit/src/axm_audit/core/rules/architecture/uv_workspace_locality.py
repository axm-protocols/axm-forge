"""Anti-regression rule: ``[tool.uv.workspace]`` parsing must live in axm_ingot.

The ``[tool.uv.workspace]`` TOML key is the single source of truth for the
workspace member layout. Resolving it ad-hoc in many packages is what the
uv-workspace factorisation (AXM-2147..2150) collapsed into the canonical
``axm_ingot.uv.resolve_workspace``. This rule is the *forcing function* that
keeps the gain: any module outside ``axm_ingot`` that reaches for that key
again is flagged so the regression never re-creeps in.

Detection is deliberately tuned for **low false-negatives** (prefer flagging
over missing): a string literal mentioning ``tool.uv.workspace`` /
``[tool.uv.workspace]``, or a ``dict``-access chain reaching the ``workspace``
sub-key under ``uv``, anywhere in a source file. ``axm_ingot`` itself and test
files (whose string literals are fixtures) are exempt.
"""

from __future__ import annotations

import ast
import importlib.util
import tomllib
from pathlib import Path

from axm_audit.core.rules._helpers import (
    get_ast_cache,
    get_python_files,
    parse_file_safe,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "UvWorkspaceLocalityRule",
    "is_exempt_path",
    "is_ingot_importable",
    "scan_source",
]

# The canonical seat callers must route through instead of re-parsing the key.
_CANONICAL = "axm_ingot.uv.resolve_workspace"

# Distribution / import names of the canonical workspace resolver package.
_INGOT_DIST = "axm-ingot"
_INGOT_IMPORT = "axm_ingot"

# Warn-only note appended when the offending site cannot yet route to ingot.
_WARN_NOTE = (
    f"{_INGOT_DIST} not importable here — publish + add it as a dependency "
    f"to make this blocking (then route through {_CANONICAL})"
)

# Textual markers of the forbidden key, matched inside string literals.
_TEXT_MARKERS = ("tool.uv.workspace", "[tool.uv.workspace]")

# Path segment that owns the key canonically (exempt) + test markers.
_INGOT_SEGMENT = "axm_ingot"

# This rule's own module defines the marker constants — it would self-flag.
_SELF_MODULE = "uv_workspace_locality.py"


def _ingot_in_pyproject(project_path: Path) -> bool:
    """True if *project_path*'s pyproject declares ``axm-ingot`` as a dep/source.

    Scans ``[project.dependencies]``, ``[project.optional-dependencies]`` and
    ``[tool.uv.sources]`` for the ``axm-ingot`` / ``axm_ingot`` name. A declared
    dependency means ingot resolves in this workspace even if it is not yet
    installed in the current interpreter.
    """
    pyproject = project_path / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False
    project = data.get("project", {})
    deps: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        deps.extend(group)
    if any(_names_ingot(dep) for dep in deps):
        return True
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    return any(_names_ingot(key) for key in sources)


def _names_ingot(spec: str) -> bool:
    """True if dependency *spec* names ``axm-ingot`` (any version marker)."""
    head = spec.strip().split(";", 1)[0]
    for sep in ("[", "=", ">", "<", "~", "!", "@", " "):
        head = head.split(sep, 1)[0]
    name = head.strip().lower().replace("_", "-")
    return name == _INGOT_DIST


def is_ingot_importable(project_path: Path) -> bool:
    """True if ``axm-ingot`` is reachable from the audited *project_path*.

    The decision is *calculated each run* (no frozen waiver list) from, in
    order of confidence:

    1. ``importlib.util.find_spec('axm_ingot')`` — ingot is installed in the
       interpreter auditing the project (same workspace / installed dep).
    2. ``axm-ingot`` declared in the project's ``pyproject.toml``
       (``dependencies``, ``optional-dependencies`` or ``[tool.uv.sources]``).

    Conservative by design: only a positive signal returns ``True``; when
    neither holds the rule treats ingot as not-yet-importable (warn-only) so
    a foreign workspace's CI is never broken by mistake.
    """
    try:
        if importlib.util.find_spec(_INGOT_IMPORT) is not None:
            return True
    except (ImportError, ValueError):
        pass
    return _ingot_in_pyproject(project_path)


def is_exempt_path(rel_path: str) -> bool:
    """True if *rel_path* is exempt from the locality rule.

    Exemptions (AC3):

    * Anything under ``axm_ingot/`` — the canonical seat of the key.
    * This rule's own module — it holds the marker constants by definition.
    * Test files and fixtures — a ``conftest.py``, a ``test_*.py`` module, or
      any path with a ``tests`` directory segment (their string literals are
      fixtures, not real parsing sites).

    Args:
        rel_path: A path relative to ``src/`` (POSIX-style or OS-native).

    Returns:
        ``True`` when the path must not be scanned, ``False`` otherwise.
    """
    parts = Path(rel_path).parts
    if _INGOT_SEGMENT in parts:
        return True
    if "tests" in parts:
        return True
    name = Path(rel_path).name
    return name in {_SELF_MODULE, "conftest.py"} or name.startswith("test_")


def _chain_keys(node: ast.AST) -> set[str]:
    """Collect every string key reached by a ``.get(...)`` / subscript chain.

    Walks the whole subtree of *node* and gathers the literal string
    arguments of ``.get("x")`` calls and ``["x"]`` subscripts. Used to decide
    whether a chain touches both ``uv`` and ``workspace``.
    """
    keys: set[str] = set()
    for sub in ast.walk(node):
        key = _string_key(sub)
        if key is not None:
            keys.add(key)
    return keys


def _get_call_key(node: ast.AST) -> str | None:
    """Return the literal string key of a ``x.get("key")`` call, else ``None``."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return None
    if node.func.attr != "get" or not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _subscript_key(node: ast.AST) -> str | None:
    """Return the literal string key of a ``x["key"]`` subscript, else ``None``."""
    if not isinstance(node, ast.Subscript):
        return None
    sl = node.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    return None


def _string_key(node: ast.AST) -> str | None:
    """Return the literal string key *node* accesses, via ``.get`` or subscript."""
    return _get_call_key(node) or _subscript_key(node)


def _literal_site(node: ast.Constant) -> tuple[int, str] | None:
    """Return ``(lineno, symbol)`` if *node* is a string literal naming the key."""
    value = node.value
    if isinstance(value, str) and any(m in value for m in _TEXT_MARKERS):
        return node.lineno, "<literal>"
    return None


def _access_site(node: ast.AST) -> tuple[int, str] | None:
    """Return ``(lineno, symbol)`` if *node* reaches ``workspace`` under ``uv``.

    A ``.get("workspace")`` call or ``["workspace"]`` subscript whose enclosing
    chain also touches the ``uv`` key is a parsing site.
    """
    if _string_key(node) != "workspace":
        return None
    if "uv" not in _chain_keys(node):
        return None
    lineno = getattr(node, "lineno", 0)
    return lineno, "workspace"


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Return ``id()`` of every string constant that is a docstring.

    A docstring mentioning the key is documentation, not a parsing site, so
    it must never be flagged. Covers module / class / function docstrings
    (the first statement of a body when it is a bare string ``Expr``).
    """
    ids: set[int] = set()
    scopes: list[ast.AST] = [tree]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            scopes.append(node)
    for scope in scopes:
        body = getattr(scope, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def scan_source(source: str) -> list[tuple[int, str]]:
    """Scan Python *source* for forbidden ``tool.uv.workspace`` accesses.

    Two heuristics (low false-negative by design):

    1. A string literal containing ``tool.uv.workspace`` /
       ``[tool.uv.workspace]`` (covers the TOML-section text pattern).
    2. A ``dict``-access chain (``.get`` / subscript) reaching the
       ``workspace`` sub-key while also touching ``uv`` in the same chain.

    Docstrings are never flagged — a docstring mentioning the key documents
    the migration, it does not parse it.

    Args:
        source: Python source text.

    Returns:
        Sorted, de-duplicated list of ``(lineno, symbol)`` offending sites.
        Empty when the source is clean (or fails to parse).
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []

    docstrings = _docstring_nodes(tree)
    sites: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            hit = None if id(node) in docstrings else _literal_site(node)
        else:
            hit = _access_site(node)
        if hit is not None:
            sites.add(hit)
    return sorted(sites)


@register_rule("architecture")
class UvWorkspaceLocalityRule(ProjectRule):
    """Ban ``[tool.uv.workspace]`` parsing outside ``axm_ingot``.

    Every site that re-parses the key outside the canonical seat is reported
    in ``details['sites']`` as ``{file, line, symbol}`` with a fix hint that
    points at :data:`axm_ingot.uv.resolve_workspace`.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "ARCH_UV_WORKSPACE_LOCALITY"

    def check(self, project_path: Path) -> CheckResult:
        """Flag every module outside ``axm_ingot`` that parses the key.

        Whether an offending site is *blocking* is decided per run from the
        real importability of ``axm-ingot`` in the audited project (AC1-AC3):
        importable -> blocking (``passed=False``, score penalised); not
        importable -> warn-only (``passed=True``, score kept, site still
        surfaced with an actionable note). No frozen waiver list.
        """
        early = self.check_src(project_path)
        if early is not None:
            return early

        sites = self._scan_tree(project_path / "src")
        if not sites:
            return self._clean_result()

        blocking = is_ingot_importable(project_path)
        return self._sites_result(sites, blocking=blocking)

    def _clean_result(self) -> CheckResult:
        """Return the passing result for a project with no offending site."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="0 tool.uv.workspace parsing site(s) outside axm_ingot",
            severity=Severity.INFO,
            score=100,
            details={"sites": []},
            text=None,
            fix_hint=None,
        )

    def _sites_result(
        self, sites: list[dict[str, object]], *, blocking: bool
    ) -> CheckResult:
        """Build the result for offending *sites*, gated on *blocking*."""
        text_lines = [f"• {s['file']}:{s['line']} ({s['symbol']})" for s in sites]
        if not blocking:
            text_lines.append(_WARN_NOTE)
        score = max(0, 100 - len(sites) * 10) if blocking else 100
        message = f"{len(sites)} tool.uv.workspace parsing site(s) outside axm_ingot"
        if not blocking:
            message = f"{message} (warn-only: {_INGOT_DIST} not importable here)"
        fix_hint = (
            f"Route workspace resolution through {_CANONICAL}"
            if blocking
            else _WARN_NOTE
        )
        return CheckResult(
            rule_id=self.rule_id,
            passed=not blocking,
            message=message,
            severity=Severity.ERROR if blocking else Severity.INFO,
            score=int(score),
            details={"sites": sites, "blocking": blocking},
            text="\n".join(text_lines),
            fix_hint=fix_hint,
        )

    def _scan_tree(self, src_path: Path) -> list[dict[str, object]]:
        """Walk ``src/`` and collect offending sites from non-exempt modules."""
        sites: list[dict[str, object]] = []
        for path in get_python_files(src_path):
            rel = path.relative_to(src_path)
            if is_exempt_path(str(rel)):
                continue
            cache = get_ast_cache()
            source = self._read_source(path, cache)
            if source is None:
                continue
            for lineno, symbol in scan_source(source):
                sites.append({"file": str(rel), "line": lineno, "symbol": symbol})
        return sites

    @staticmethod
    def _read_source(path: Path, cache: object) -> str | None:
        """Read *path* as text, guarding against unreadable files.

        The shared AST cache is checked first only to confirm the file parses;
        the scanner re-parses from text because it also matches raw string
        literals (cheaper and simpler than re-walking a cached tree twice).
        """
        if cache is not None and parse_file_safe(path) is None:
            return None
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
