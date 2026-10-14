"""Symbol-aware test discovery for impact analysis, direct and transitive.

``ast_impact`` reports two families of test files for an edited symbol:

* **direct**: test files that *reference* the symbol. A function matches on
  its name as a whole identifier. A method also needs evidence that the test
  can reach the owning class: the class name (or one of its subclasses)
  appears in the file, or the file imports the defining module. Dunder
  methods (``__init__``, ``__call__``...) are invoked implicitly, so the
  class reference alone is enough for them.
* **transitive** (opt-in): the direct tests of the symbol *and* of every
  in-package caller reached by walking the call graph upward, level by level,
  up to a bounded depth. The walk is cycle-safe (each symbol is visited once)
  and capped at :data:`MAX_TRANSITIVE_SYMBOLS` visited symbols. Hitting the
  cap is reported, never silent.

The test suite is read and tokenised once per analysis
(:class:`TestCorpus`), so every lookup during the walk is a set
intersection, not a rescan of the suite.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from axm_ingot.suite import resolve_suite_dirs

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.callers import find_callers
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ClassInfo, ModuleInfo, PackageInfo

__all__ = [
    "MAX_TRANSITIVE_DEPTH",
    "MAX_TRANSITIVE_SYMBOLS",
    "ClassHierarchy",
    "DiscoveryContext",
    "SymbolTarget",
    "TestCorpus",
    "TransitiveTests",
    "find_transitive_tests",
    "validate_transitive_depth",
]

#: Upper bound accepted for the opt-in transitive walk depth.
MAX_TRANSITIVE_DEPTH = 10
#: Visited-symbol budget of one transitive walk (target included).
MAX_TRANSITIVE_SYMBOLS = 500

_IDENTIFIER = re.compile(r"\w+")
_SELF_RECEIVERS = frozenset({"self", "cls"})


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")  # noqa: PLR2004


@dataclass(frozen=True)
class SymbolTarget:
    """A resolved symbol: package-relative module plus qualified name.

    ``qualname`` is ``"func"`` for a top-level function or class and
    ``"Class.method"`` for a method.
    """

    module: str
    qualname: str

    @property
    def name(self) -> str:
        """Bare name as it appears at call sites."""
        return self.qualname.rsplit(".", 1)[-1]

    @property
    def owner(self) -> str | None:
        """Owning class name for a method, ``None`` otherwise."""
        head, sep, _ = self.qualname.rpartition(".")
        return head.rsplit(".", 1)[-1] if sep else None

    @property
    def key(self) -> str:
        """Fully qualified identity, ``module.qualname``."""
        return f"{self.module}.{self.qualname}" if self.module else self.qualname


def _bare_base(base: str) -> str:
    return base.split("[", 1)[0].rsplit(".", 1)[-1].strip()


class ClassHierarchy:
    """Name-based class hierarchy of one package.

    Bases are matched by bare name, so two homonymous classes in distinct
    modules share a node. That is a deliberate over-approximation: it can
    only widen the owner family, never drop a real subclass.
    """

    def __init__(self, pkg: PackageInfo) -> None:
        """Index every class of *pkg* by name and by base name."""
        self._bases: dict[str, set[str]] = {}
        self._children: dict[str, set[str]] = {}
        for mod in pkg.modules:
            for cls in mod.classes:
                bases = {_bare_base(base) for base in cls.bases}
                self._bases.setdefault(cls.name, set()).update(bases)
                for base in bases:
                    self._children.setdefault(base, set()).add(cls.name)

    @staticmethod
    def _closure(start: str, edges: dict[str, set[str]]) -> frozenset[str]:
        seen = {start}
        stack = [start]
        while stack:
            for nxt in edges.get(stack.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return frozenset(seen)

    def descendants(self, name: str) -> frozenset[str]:
        """Return *name* and every class inheriting from it."""
        return self._closure(name, self._children)

    def family(self, name: str) -> frozenset[str]:
        """Return *name*, its ancestors and its descendants.

        A ``self.m()`` call in a base class may dispatch to an override, and
        one in a subclass may reach the inherited definition.
        """
        return self._closure(name, self._bases) | self.descendants(name)


class TestCorpus:
    """The test files of a project, read and tokenised once.

    Matching is by whole identifier: ``greet`` matches ``greet(`` or
    ``mod.greet`` but not ``greeting``.
    """

    __test__ = False  # not a pytest test class despite the name

    def __init__(self, project_root: Path) -> None:
        """Read every ``test_*.py`` of the configured suites under *project_root*."""
        self.root = project_root
        self.files: list[Path] = sorted(
            test_file
            for tests_dir in resolve_suite_dirs(project_root)
            for test_file in tests_dir.rglob("test_*.py")
        )
        self._index: dict[str, set[int]] = {}
        for position, test_file in enumerate(self.files):
            try:
                content = test_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for token in set(_IDENTIFIER.findall(content)):
                self._index.setdefault(token, set()).add(position)

    def _referencing(self, names: Iterable[str]) -> set[int]:
        found: set[int] = set()
        for name in names:
            found |= self._index.get(name, set())
        return found

    def referencing(self, name: str) -> list[Path]:
        """Return the test files mentioning *name* as an identifier."""
        return [self.files[i] for i in sorted(self._referencing([name]))]

    def matching(
        self,
        target: SymbolTarget,
        hierarchy: ClassHierarchy,
        reaches_module: Callable[[Path, str], bool],
    ) -> list[Path]:
        """Return the test files directly referencing *target*.

        Args:
            target: Resolved symbol.
            hierarchy: Class hierarchy used to accept subclass references.
            reaches_module: ``(test_file, module) -> bool`` predicate telling
                whether a test imports the defining module (fail-open).
        """
        owner = target.owner
        if owner is None:
            return self.referencing(target.name)
        owner_refs = self._referencing(hierarchy.descendants(owner))
        if _is_dunder(target.name):
            return [self.files[i] for i in sorted(owner_refs)]
        name_refs = self._referencing([target.name])
        accepted = name_refs & owner_refs
        for position in sorted(name_refs - owner_refs):
            if reaches_module(self.files[position], target.module):
                accepted.add(position)
        return [self.files[i] for i in sorted(accepted)]


@dataclass
class DiscoveryContext:
    """Everything a transitive walk needs, computed once per analysis.

    Attributes:
        pkg: Package whose call graph is walked.
        corpus: Test corpus the direct matches are taken from.
        reaches_module: ``(test_file, module) -> bool`` import predicate.
        keep_function_callers: Provenance filter applied to the call sites
            of a plain function (drops callers proven to import a homonym).
    """

    pkg: PackageInfo
    corpus: TestCorpus
    reaches_module: Callable[[Path, str], bool]
    keep_function_callers: Callable[[SymbolTarget, list[CallSite]], list[CallSite]]
    hierarchy: ClassHierarchy = field(init=False)
    _modules: dict[str, ModuleInfo] = field(init=False)
    _sources: dict[str, frozenset[str]] = field(init=False, default_factory=dict)
    _direct: dict[SymbolTarget, list[Path]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        """Index the package once."""
        self.hierarchy = ClassHierarchy(self.pkg)
        self._modules = {
            module_dotted_name(mod.path, self.pkg.root): mod for mod in self.pkg.modules
        }

    def direct_tests(self, target: SymbolTarget) -> list[Path]:
        """Direct test files of *target* (memoised)."""
        if target not in self._direct:
            self._direct[target] = self.corpus.matching(
                target, self.hierarchy, self.reaches_module
            )
        return self._direct[target]

    def module_tokens(self, module: str) -> frozenset[str]:
        """Identifiers of a package module's source (memoised, empty on error)."""
        if module not in self._sources:
            mod = self._modules.get(module)
            try:
                text = mod.path.read_text(encoding="utf-8") if mod else ""
            except OSError:
                text = ""
            self._sources[module] = frozenset(_IDENTIFIER.findall(text))
        return self._sources[module]

    def enclosing(self, site: CallSite) -> SymbolTarget | None:
        """Top-level function or method whose body holds *site*."""
        mod = self._modules.get(site.module)
        if mod is None:
            return None
        for fn in mod.functions:
            if fn.line_start <= site.line <= fn.line_end:
                return SymbolTarget(site.module, fn.name)
        for cls in mod.classes:
            for method in cls.methods:
                if method.line_start <= site.line <= method.line_end:
                    return SymbolTarget(site.module, f"{cls.name}.{method.name}")
        return None

    def enclosing_class(self, site: CallSite) -> ClassInfo | None:
        """Top-level class whose body holds *site*."""
        mod = self._modules.get(site.module)
        if mod is None:
            return None
        return next(
            (c for c in mod.classes if c.line_start <= site.line <= c.line_end),
            None,
        )


def _receiver(site: CallSite) -> str:
    callee = site.call_expression.split("(", 1)[0]
    receiver, sep, _ = callee.rpartition(".")
    return receiver.strip() if sep else ""


def _method_call_sites(ctx: DiscoveryContext, target: SymbolTarget) -> list[CallSite]:
    """Call sites that can reach the method *target*.

    ``self``/``cls``/``super()`` calls are kept only inside the owner's class
    family. Any other receiver is kept when the calling module is the
    defining module or names the owner (or a subclass): without type
    inference, that reference is the evidence the receiver may be one.
    Constructor calls ``Owner(...)`` stand for ``Owner.__init__``.
    """
    owner = target.owner or ""
    family = ctx.hierarchy.family(owner)
    owners = ctx.hierarchy.descendants(owner)
    kept = [
        site
        for site in find_callers(ctx.pkg, target.name)
        if _reaches_method(ctx, site, target, family=family, owners=owners)
    ]
    if target.name == "__init__":
        for cls_name in sorted(owners):
            kept.extend(find_callers(ctx.pkg, cls_name))
    return kept


def _reaches_method(
    ctx: DiscoveryContext,
    site: CallSite,
    target: SymbolTarget,
    *,
    family: frozenset[str],
    owners: frozenset[str],
) -> bool:
    """Whether a by-name call site can dispatch to the method *target*."""
    receiver = _receiver(site)
    if receiver in _SELF_RECEIVERS or receiver.startswith("super("):
        cls = ctx.enclosing_class(site)
        return cls is not None and cls.name in family
    return site.module == target.module or bool(owners & ctx.module_tokens(site.module))


def _caller_targets(ctx: DiscoveryContext, target: SymbolTarget) -> set[SymbolTarget]:
    """Enclosing symbols of every call site that can reach *target*."""
    if target.owner is None:
        sites = ctx.keep_function_callers(target, find_callers(ctx.pkg, target.name))
    else:
        sites = _method_call_sites(ctx, target)
    callers = {ctx.enclosing(site) for site in sites}
    return {c for c in callers if c is not None and c != target}


def validate_transitive_depth(depth: int) -> None:
    """Reject a transitive depth outside ``[0, MAX_TRANSITIVE_DEPTH]``.

    Raises:
        ValueError: If *depth* is out of range (or not an ``int``).
    """
    if isinstance(depth, bool) or not isinstance(depth, int):
        msg = f"transitive_depth must be an integer, got {depth!r}"
        raise ValueError(msg)
    if not 0 <= depth <= MAX_TRANSITIVE_DEPTH:
        msg = (
            f"transitive_depth must be within [0, {MAX_TRANSITIVE_DEPTH}], got {depth}"
        )
        raise ValueError(msg)


@dataclass(frozen=True)
class TransitiveTests:
    """Outcome of a transitive walk.

    Attributes:
        test_files: Direct tests of the target and of every walked caller.
        callers: Walked caller symbols (``module.qualname``), target excluded.
        truncated: ``True`` when :data:`MAX_TRANSITIVE_SYMBOLS` stopped the
            walk before *depth* was exhausted.
    """

    test_files: list[Path]
    callers: list[str]
    truncated: bool


def find_transitive_tests(
    ctx: DiscoveryContext,
    target: SymbolTarget,
    depth: int,
    *,
    max_symbols: int = MAX_TRANSITIVE_SYMBOLS,
) -> TransitiveTests:
    """Walk the callers of *target* upward and collect their direct tests.

    Breadth-first, one level per depth unit, each symbol visited once
    (cycle-safe). ``depth=0`` returns the direct tests only.

    Args:
        ctx: Shared discovery context.
        target: Symbol whose change is analysed.
        depth: Number of caller levels to climb (``0`` to
            :data:`MAX_TRANSITIVE_DEPTH`).
        max_symbols: Visited-symbol budget, target included.

    Raises:
        ValueError: If *depth* is outside ``[0, MAX_TRANSITIVE_DEPTH]``.
    """
    validate_transitive_depth(depth)
    walk = _Walk(seen={target}, tests=set(ctx.direct_tests(target)))
    frontier = [target]
    for _ in range(depth):
        frontier = _climb(ctx, walk, frontier, max_symbols)
        if walk.truncated or not frontier:
            break
    return TransitiveTests(
        test_files=sorted(walk.tests),
        callers=sorted(t.key for t in walk.seen if t != target),
        truncated=walk.truncated,
    )


@dataclass
class _Walk:
    seen: set[SymbolTarget]
    tests: set[Path]
    truncated: bool = False


def _climb(
    ctx: DiscoveryContext,
    walk: _Walk,
    frontier: list[SymbolTarget],
    max_symbols: int,
) -> list[SymbolTarget]:
    """Visit the unseen callers of *frontier*; return the next frontier."""
    next_frontier: list[SymbolTarget] = []
    for current in frontier:
        for caller in sorted(_caller_targets(ctx, current), key=lambda t: t.key):
            if caller in walk.seen:
                continue
            if len(walk.seen) >= max_symbols:
                walk.truncated = True
                return next_frontier
            walk.seen.add(caller)
            next_frontier.append(caller)
            walk.tests.update(ctx.direct_tests(caller))
    return next_frontier
