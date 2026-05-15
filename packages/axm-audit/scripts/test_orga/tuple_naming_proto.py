"""Prototype v5: derive canonical tuple-based filenames for integration tests.

Fixes vs v4:
  (4) resolve @pytest.fixture return type and propagate to test parameters.
      A test that takes `rule` as a parameter where `rule` is a top-level
      fixture annotated `-> DependencyHygieneRule` (or returning a known
      symbol) now counts `DependencyHygieneRule` for each reference to
      `rule` in the test body.

Earlier fixes retained:
  (1) imports walked recursively (catches `from axm_audit... import X` inside
      a helper function).
  (2) test functions inside `Test*` classes are walked.
  (3) per-test symbol usage transitively includes usage inside helper
      functions of the same module that the test (directly or indirectly)
      calls. Intra-module call closure only — no cross-file resolution.

For each test file in tests/integration/:
  - extract per-test the set of symbols from PACKAGE (imports + transitive uses)
  - propose canonical filename test__<s1>__<s2>.py (snake_case, K=2)
  - flag UNKNOWN files (no package symbol) and classify their nature
  - flag SPLIT files and propose decomposition into per-tuple sub-files
  - drill-down on the top-N largest files
"""
from __future__ import annotations

import ast
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE = "axm_smelt"
TESTS_DIR = Path(
    "/Users/gabriel/Documents/Code/python/axm-workspaces/"
    "axm-forge/packages/axm-smelt/tests/integration"
)
TOP_K = 2
TOP_DRILLDOWN = 5

EXEC_HINT_MODULES = {"subprocess", "tomllib", "tomli", "shutil", "socket"}


def to_snake(name: str) -> str:
    if not name:
        return name
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and (
            name[i - 1].islower()
            or (i + 1 < len(name) and name[i + 1].islower())
        ):
            out.append("_")
        out.append(ch.lower())
    return "".join(out).lstrip("_")


@dataclass
class TestSymbols:
    test_name: str
    imported: set[str] = field(default_factory=set)
    used: Counter[str] = field(default_factory=Counter)

    def tuple_topk(self, k: int = TOP_K) -> tuple[str, ...]:
        ranked = [s for s, _ in self.used.most_common() if s in self.imported]
        if not ranked:
            ranked = sorted(self.imported)
        return tuple(sorted(ranked[:k]))


# ---------------------------------------------------------------------------
# Fix (1): walk imports recursively (any depth, any scope)
# ---------------------------------------------------------------------------


def _collect_package_imports(tree: ast.AST) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == PACKAGE or mod.startswith(PACKAGE + "."):
                for alias in node.names:
                    local = alias.asname or alias.name
                    imports[local] = f"{mod}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE or alias.name.startswith(PACKAGE + "."):
                    local = alias.asname or alias.name.split(".")[0]
                    imports[local] = alias.name
    return imports


def _stdlib_hint_imports(tree: ast.AST) -> set[str]:
    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in EXEC_HINT_MODULES:
                    hits.add(root)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in EXEC_HINT_MODULES:
                hits.add(root)
    return hits


def _used_names_in_node(node: ast.AST, known: set[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in known:
            counter[sub.id] += 1
        elif isinstance(sub, ast.Attribute):
            root = sub
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in known:
                counter[root.id] += 1
    return counter


# ---------------------------------------------------------------------------
# Fix (2): walk test funcs at module level + inside Test* classes
# ---------------------------------------------------------------------------


def _walk_test_funcs(tree: ast.Module) -> list[ast.FunctionDef]:
    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            funcs.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                    funcs.append(child)
    return funcs


# ---------------------------------------------------------------------------
# Fix (3): module-level helper functions + intra-module call closure
# ---------------------------------------------------------------------------


def _module_level_funcs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """All top-level function defs (helpers and tests alike) by name."""
    funcs: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs[node.name] = node
    return funcs


def _module_level_classes(tree: ast.Module) -> dict[str, ast.ClassDef]:
    """All top-level class defs (e.g. synthetic subclasses) by name."""
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def _direct_calls(node: ast.AST) -> set[str]:
    """Names directly called inside `node` (only ast.Name callees, not attrs)."""
    callees: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name):
                callees.add(func.id)
            elif isinstance(func, ast.Attribute):
                # e.g. self._helper(...) — pick the rightmost attr name as
                # candidate (only resolved if it matches a module-level def)
                callees.add(func.attr)
    return callees


def _closure_nodes_for_test(
    test_func: ast.FunctionDef,
    mod_funcs: dict[str, ast.FunctionDef],
    mod_classes: dict[str, ast.ClassDef],
) -> list[ast.AST]:
    """Return the test body + bodies of transitively-called module helpers.

    Works for top-level test functions AND methods inside Test* classes:
      - If the test is top-level (in `mod_funcs`), seed the closure with it.
      - If the test is a class method (NOT in `mod_funcs`), seed the closure
        with helpers it directly calls (e.g. `self._run(...)`, `_make_result()`)
        and walk from there.

    Also include any top-level class whose name is referenced (by Name) inside
    the closure — covers patterns like `class _Synthetic(ProjectRule): ...`
    instantiated in the test.
    """
    seen_funcs: set[str] = set()
    to_visit: list[str] = []

    if test_func.name in mod_funcs:
        # top-level test function
        to_visit.append(test_func.name)
    else:
        # method inside a Test* class: seed closure with helpers it calls
        for callee in _direct_calls(test_func):
            if callee in mod_funcs:
                to_visit.append(callee)

    while to_visit:
        name = to_visit.pop()
        if name in seen_funcs or name not in mod_funcs:
            continue
        seen_funcs.add(name)
        for callee in _direct_calls(mod_funcs[name]):
            if callee in mod_funcs and callee not in seen_funcs:
                to_visit.append(callee)

    nodes: list[ast.AST] = [mod_funcs[n] for n in seen_funcs if n in mod_funcs]
    # always include the test function/method itself (its own body counts)
    if test_func.name not in seen_funcs:
        nodes.append(test_func)

    # pull in module-level classes referenced anywhere in the closure
    referenced_class_names: set[str] = set()
    for n in nodes:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name) and sub.id in mod_classes:
                referenced_class_names.add(sub.id)
    for cname in referenced_class_names:
        nodes.append(mod_classes[cname])

    return nodes


# ---------------------------------------------------------------------------
# Fix (4): pytest fixture resolution — map fixture name -> package symbol
# ---------------------------------------------------------------------------


def _is_pytest_fixture(func: ast.FunctionDef) -> bool:
    """Decorated by @pytest.fixture, @fixture, @pytest.fixture(...) etc."""
    for dec in func.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _resolve_fixture_symbol(
    func: ast.FunctionDef, known: set[str]
) -> str | None:
    """Return the package symbol the fixture yields/returns, if any.

    Tries (in order):
      - return-type annotation (`-> DependencyHygieneRule`)
      - last `return X(...)` or `return X` in the body
      - last `yield X(...)` or `yield X` in the body
    Only resolves to names present in `known` (i.e. imported from PACKAGE).
    """
    # 1. annotation
    if isinstance(func.returns, ast.Name) and func.returns.id in known:
        return func.returns.id
    if isinstance(func.returns, ast.Attribute):
        root = func.returns
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in known:
            return root.id

    # 2. return / yield in body — pick the last one walked
    candidate: str | None = None
    for sub in ast.walk(func):
        value: ast.AST | None = None
        if isinstance(sub, ast.Return):
            value = sub.value
        elif isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Yield):
            value = sub.value.value
        if value is None:
            continue
        if isinstance(value, ast.Call):
            value = value.func
        if isinstance(value, ast.Name) and value.id in known:
            candidate = value.id
        elif isinstance(value, ast.Attribute):
            root = value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in known:
                candidate = root.id
    return candidate


def _collect_fixtures(
    tree: ast.Module, known: set[str]
) -> dict[str, str]:
    """Return {fixture_name: package_symbol} for resolvable top-level fixtures."""
    mapping: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture(node):
            sym = _resolve_fixture_symbol(node, known)
            if sym is not None:
                mapping[node.name] = sym
    return mapping


def _param_names(func: ast.FunctionDef) -> set[str]:
    """All parameter names of a function/method (positional + kw-only)."""
    args = func.args
    names: set[str] = set()
    for a in args.args + args.kwonlyargs:
        names.add(a.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _count_fixture_uses_in(
    node: ast.AST, fixture_map: dict[str, str], param_names: set[str]
) -> Counter[str]:
    """Count references to fixture-mapped params inside `node`'s body.

    Only counts a name reference if (a) the name is a parameter of the test,
    and (b) the parameter name appears in `fixture_map`. Each reference adds
    one to the package symbol the fixture resolves to.
    """
    out: Counter[str] = Counter()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in param_names and sub.id in fixture_map:
            out[fixture_map[sub.id]] += 1
        elif isinstance(sub, ast.Attribute):
            root = sub
            while isinstance(root, ast.Attribute):
                root = root.value
            if (
                isinstance(root, ast.Name)
                and root.id in param_names
                and root.id in fixture_map
            ):
                out[fixture_map[root.id]] += 1
    return out


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------


@dataclass
class FileReport:
    path: Path
    tests: list[TestSymbols]
    tuples_k2: list[tuple[str, ...]] = field(default_factory=list)
    tuples_k3: list[tuple[str, ...]] = field(default_factory=list)
    union_k2: tuple[str, ...] = ()
    union_k3: tuple[str, ...] = ()
    cohesion_k2: float = 0.0
    cohesion_k3: float = 0.0
    stdlib_hints: set[str] = field(default_factory=set)

    @staticmethod
    def name_from(t: tuple[str, ...]) -> str:
        if not t:
            return "test_UNKNOWN.py"
        return "test_" + "-".join(to_snake(s) for s in t) + ".py"

    @property
    def name_k2(self) -> str:
        return self.name_from(self.union_k2)

    @property
    def name_k3(self) -> str:
        return self.name_from(self.union_k3)

    @property
    def n_tests(self) -> int:
        return len(self.tests)

    @property
    def split_k2(self) -> bool:
        return len({t for t in self.tuples_k2 if t}) > 1

    @property
    def split_k3(self) -> bool:
        return len({t for t in self.tuples_k3 if t}) > 1


def analyze_file(path: Path) -> FileReport:
    tree = ast.parse(path.read_text())
    assert isinstance(tree, ast.Module)
    imports = _collect_package_imports(tree)
    known = set(imports.keys())
    mod_funcs = _module_level_funcs(tree)
    mod_classes = _module_level_classes(tree)
    fixture_map = _collect_fixtures(tree, known)

    # the symbol pool now includes fixture-resolved symbols (they may not be
    # imported in this file at all if e.g. a fixture re-exports, but here we
    # only resolve fixtures whose returns are in `known`, so this is safe).
    pool = known | set(fixture_map.values())

    tests: list[TestSymbols] = []
    for f in _walk_test_funcs(tree):
        closure_nodes = _closure_nodes_for_test(f, mod_funcs, mod_classes)
        used: Counter[str] = Counter()
        for n in closure_nodes:
            used.update(_used_names_in_node(n, known))
        # fixture contribution: for each ref to a param that maps to a
        # package symbol, add that symbol to the count.
        params = _param_names(f)
        used.update(_count_fixture_uses_in(f, fixture_map, params))
        tests.append(TestSymbols(test_name=f.name, imported=pool.copy(), used=used))

    rep = FileReport(path=path, tests=tests)
    rep.stdlib_hints = _stdlib_hint_imports(tree)
    rep.tuples_k2 = [t.tuple_topk(2) for t in tests]
    rep.tuples_k3 = [t.tuple_topk(3) for t in tests]

    agg: Counter[str] = Counter()
    for t in tests:
        agg.update(t.used)
    ranked = [s for s, _ in agg.most_common()]
    rep.union_k2 = tuple(sorted(ranked[:2]))
    rep.union_k3 = tuple(sorted(ranked[:3]))

    if rep.tuples_k2:
        rep.cohesion_k2 = sum(1 for t in rep.tuples_k2 if t == rep.union_k2) / len(rep.tuples_k2)
        rep.cohesion_k3 = sum(1 for t in rep.tuples_k3 if t == rep.union_k3) / len(rep.tuples_k3)
    return rep


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def main() -> int:
    files = sorted(
        p for p in TESTS_DIR.rglob("test_*.py")
        if "__pycache__" not in p.parts
    )
    reports = [analyze_file(p) for p in files]

    print(f"Analyzed {len(reports)} integration test files\n")
    print("=" * 110)
    print(f"{'CURRENT':<55} {'#T':>3} {'COH':>5}  PROPOSED")
    print("=" * 110)
    for r in reports:
        flag = " *S*" if r.split_k2 else ""
        print(
            f"{r.path.name:<55} {r.n_tests:>3} {r.cohesion_k2:>5.0%}  "
            f"{r.name_k2}{flag}"
        )

    # ---- K=2 vs K=3 metrics ----
    def _metrics(reports: list[FileReport], k: int) -> dict[str, object]:
        by_name: dict[str, list[FileReport]] = defaultdict(list)
        for r in reports:
            name = r.name_k2 if k == 2 else r.name_k3
            by_name[name].append(r)
        coll = {k: v for k, v in by_name.items() if len(v) > 1}
        return {
            "unique": len(by_name),
            "n_split": sum(1 for r in reports if (r.split_k2 if k == 2 else r.split_k3)),
            "n_collide": sum(len(v) for v in coll.values()),
            "n_empty": sum(1 for r in reports if not (r.union_k2 if k == 2 else r.union_k3)),
            "avg_coh": sum(r.cohesion_k2 if k == 2 else r.cohesion_k3 for r in reports) / max(len(reports), 1),
            "collisions": coll,
        }

    m2 = _metrics(reports, 2)
    m3 = _metrics(reports, 3)
    n = len(reports)
    print("\n" + "=" * 80)
    print("METRICS — K=2 vs K=3 (v4)")
    print("=" * 80)
    print(f"  total files:                   {n}")
    print(f"{'metric':<32} {'K=2':>10} {'K=3':>10}   {'Δ':>6}")
    print(f"{'unique proposed names':<32} {m2['unique']:>10} {m3['unique']:>10}   {m3['unique']-m2['unique']:>+6}")
    print(f"{'files UNKNOWN':<32} {m2['n_empty']:>10} {m3['n_empty']:>10}   {m3['n_empty']-m2['n_empty']:>+6}")
    print(f"{'files SPLIT':<32} {m2['n_split']:>10} {m3['n_split']:>10}   {m3['n_split']-m2['n_split']:>+6}")
    print(f"{'files in collision group':<32} {m2['n_collide']:>10} {m3['n_collide']:>10}   {m3['n_collide']-m2['n_collide']:>+6}")
    print(f"{'avg per-file cohesion':<32} {m2['avg_coh']:>9.0%}  {m3['avg_coh']:>9.0%}   {(m3['avg_coh']-m2['avg_coh'])*100:>+5.1f}pt")

    # files where K=3 changed something vs K=2 (different name or different cohesion)
    diffs: list[tuple[FileReport, str, str]] = []
    for r in reports:
        if r.name_k2 != r.name_k3 or abs(r.cohesion_k2 - r.cohesion_k3) > 0.01:
            diffs.append((r, r.name_k2, r.name_k3))
    print(f"\n  files where K=3 differs from K=2: {len(diffs)}")
    for r, n2, n3 in diffs[:20]:
        print(f"     {r.path.name:<48} K2={n2:<35} K3={n3}  (coh {r.cohesion_k2:.0%}→{r.cohesion_k3:.0%})")
    if len(diffs) > 20:
        print(f"     ... +{len(diffs) - 20} more")

    unknowns = [r for r in reports if not r.union_k2]
    print("\n" + "=" * 80)
    print(f"UNKNOWN FILES ({len(unknowns)})")
    print("=" * 80)
    for r in unknowns:
        hint = ", ".join(sorted(r.stdlib_hints)) or "<none>"
        print(f"  {r.path.name:<50}  hints: {hint}")

    # ---- drill-down on previously-misclassified files ----
    watched = {
        "test_check_src_score.py",
        "test_dependency_text_format.py",
        "test_pyramid_level_class_helpers.py",
        "test_security_text.py",
        "test_tautology_triage_strengthen_side.py",
    }
    print("\n" + "=" * 80)
    print("REGRESSION CHECK: previously-UNKNOWN files that should now resolve")
    print("=" * 80)
    for r in reports:
        if r.path.name in watched:
            print(f"  {r.path.name:<50}  → {r.name_k2}")

    # ---- top-N largest with K=2 tuple distribution ----
    by_size = sorted(reports, key=lambda r: -r.n_tests)[:TOP_DRILLDOWN]
    print("\n" + "=" * 80)
    print(f"DRILL-DOWN: TOP-{TOP_DRILLDOWN} LARGEST FILES")
    print("=" * 80)
    for r in by_size:
        dist: Counter[tuple[str, ...]] = Counter(r.tuples_k2)
        print(
            f"\n  {r.path.name}  ({r.n_tests} tests | cohesion {r.cohesion_k2:.0%}"
            f" | {len(dist)} distinct tuples)"
        )
        for tup, count in dist.most_common(6):
            label = FileReport.name_from(tup) if tup else "<empty>"
            print(f"     {count:>3}x  {label}")
        if len(dist) > 6:
            print(f"     ... +{len(dist) - 6} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
