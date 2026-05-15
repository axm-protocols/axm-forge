"""Prototype e2e: derive canonical tuple-based filenames for e2e tests.

Companion to `tuple_naming_proto.py` (v5, integration tier). Same conceptual
pipeline — extract a per-test tuple, rank by usage, take top-K=2, sort
alphabetically, emit `test_<a>-<b>.py` — but the unit counted is no longer
a Python symbol: it is a CLI invocation key `(bin, sub)` where:

  - `bin`   = argv[0] of a subprocess call OR the script-name of a CliRunner's
              `app` object, filtered to names declared in `[project.scripts]`
              of the package under test.
  - `sub`   = argv[1] if argv[1] is a non-flag positional (does not start
              with '-' and is not a path-like / tmp_path expression), else
              the empty string (singleton invocation).

Out-of-package binaries (`git`, `uv`, `pytest`, `pip`, …) are setup
plumbing and are filtered out, exactly as stdlib imports are filtered
when collecting integration symbols.

See README_E2E.md for the full design.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(
    "/Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages"
)
DEFAULT_PACKAGES = ["axm-audit", "axm-init", "axm-ast", "axm-smelt"]
TOP_K = 2
TOP_DRILLDOWN = 5

# Module-level PACKAGE rebound per analyzed package by main()
PACKAGE = ""


# ---------------------------------------------------------------------------
# pyproject.toml — collect [project.scripts] and entry-points app objects
# ---------------------------------------------------------------------------


def _load_project_scripts(pyproject: Path) -> set[str]:
    """Return the set of script names declared under [project.scripts]."""
    data = tomllib.loads(pyproject.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    return set(scripts.keys())


def _load_app_targets(pyproject: Path) -> dict[str, str]:
    """Return {module_path: script_name} for each [project.scripts] entry.

    `axm-audit = "axm_audit.cli:main"` → {"axm_audit.cli": "axm-audit"}

    Used to recognize CliRunner().invoke(app, ...) calls where `app` is
    imported from a known script entry point module.
    """
    data = tomllib.loads(pyproject.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    out: dict[str, str] = {}
    for name, target in scripts.items():
        if ":" in target:
            mod, _ = target.split(":", 1)
            out[mod] = name
    return out


# ---------------------------------------------------------------------------
# Integration-style fallback (from v5, condensed)
# ---------------------------------------------------------------------------


def _collect_package_imports(tree: ast.AST) -> dict[str, str]:
    """{local_name: dotted_origin} for every import from PACKAGE."""
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


def _used_first_party_names(node: ast.AST, known: set[str]) -> Counter[str]:
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


def to_snake(name: str) -> str:
    """PascalCase or kebab-case → snake_case (for filename emission)."""
    if not name:
        return name
    # kebab → snake
    name = name.replace("-", "_")
    out: list[str] = []
    for i, ch in enumerate(name):
        if (
            ch.isupper()
            and i > 0
            and (name[i - 1].islower() or (i + 1 < len(name) and name[i + 1].islower()))
        ):
            out.append("_")
        out.append(ch.lower())
    return "".join(out).lstrip("_")


# ---------------------------------------------------------------------------
# AST extraction: subprocess / CliRunner invocations
# ---------------------------------------------------------------------------


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "string"` bindings — for resolving argv elements
    when the test does `subprocess.run([BIN, "audit"])` with `BIN = "axm-audit"`.
    """
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if (
                isinstance(t, ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                out[t.id] = node.value.value
    return out


def _local_string_constants(func: ast.AST) -> dict[str, str]:
    """One-level intra-function `NAME = "string"` bindings."""
    out: dict[str, str] = {}
    for sub in ast.walk(func):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
            t = sub.targets[0]
            if (
                isinstance(t, ast.Name)
                and isinstance(sub.value, ast.Constant)
                and isinstance(sub.value.value, str)
            ):
                out[t.id] = sub.value.value
    return out


def _local_list_bindings(func: ast.AST) -> dict[str, list[ast.expr]]:
    """One-level intra-function `NAME = [...]` bindings.

    Used to trace `cmd = ["axm-audit", "audit"]; subprocess.run(cmd)`.
    """
    out: dict[str, list[ast.expr]] = {}
    for sub in ast.walk(func):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
            t = sub.targets[0]
            if isinstance(t, ast.Name) and isinstance(sub.value, ast.List):
                out[t.id] = list(sub.value.elts)
    return out


def _imports_of_module(tree: ast.Module, target_module: str) -> set[str]:
    """Local names bound to `from {target_module} import X` (any X).

    Used to detect `from axm_audit.cli import app` and recognise that
    `app` (or `app as foo`) refers to the script entry point.
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "") == target_module:
                for alias in node.names:
                    out.add(alias.asname or alias.name)
    return out


def _resolve_str_expr(
    expr: ast.expr,
    mod_strs: dict[str, str],
    local_strs: dict[str, str],
) -> str | None:
    """Resolve an AST expression to a string literal if statically possible."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        if expr.id in local_strs:
            return local_strs[expr.id]
        if expr.id in mod_strs:
            return mod_strs[expr.id]
    # str(BIN), str(tmp_path / "x") etc. — skip
    return None


def _argv_from_list(
    list_node: ast.List,
    mod_strs: dict[str, str],
    local_strs: dict[str, str],
) -> list[str | None]:
    """Resolve every element of a list literal to a string or None."""
    return [_resolve_str_expr(e, mod_strs, local_strs) for e in list_node.elts]


def _extract_invocation_from_call(
    call: ast.Call,
    scripts: set[str],
    script_app_locals: set[str],
    app_to_script: dict[str, str],
    mod_strs: dict[str, str],
    local_strs: dict[str, str],
    local_lists: dict[str, list[ast.expr]],
) -> tuple[str, str] | None:
    """If `call` is a subprocess/CliRunner invocation of an in-package script,
    return its (bin, sub) tuple; else None.

    `sub` is "" for singleton invocations (only argv[0], or argv[1] is a flag).
    """
    func = call.func

    # --- subprocess.run([...]) / subprocess.check_call([...]) / Popen([...]) ---
    subprocess_call = (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
        and func.attr in {"run", "call", "check_call", "check_output", "Popen"}
    )
    if subprocess_call and call.args:
        # shell=True → skip
        for kw in call.keywords:
            if (
                kw.arg == "shell"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return None
        first = call.args[0]
        argv: list[str | None]
        if isinstance(first, ast.List):
            argv = _argv_from_list(first, mod_strs, local_strs)
        elif isinstance(first, ast.Name) and first.id in local_lists:
            argv = [
                _resolve_str_expr(e, mod_strs, local_strs)
                for e in local_lists[first.id]
            ]
        else:
            return None
        if not argv:
            return None
        # Strategy: scan argv for the first element that matches a known
        # in-package script (or its module-path form, e.g. "axm_audit" for
        # the "axm-audit" script). Non-resolvable elements are skipped
        # (handles `shutil.which("uv")` / fixture-injected runner paths).
        # The next non-flag element after the match is the sub-command.
        script_modules = {s.replace("-", "_"): s for s in scripts}
        match_idx: int | None = None
        match_script: str | None = None
        for i, tok in enumerate(argv):
            if tok is None:
                continue
            if tok in scripts:
                match_idx, match_script = i, tok
                break
            if tok in script_modules:
                match_idx, match_script = i, script_modules[tok]
                break
        if match_idx is None or match_script is None:
            return None
        sub = ""
        sub_idx = match_idx + 1
        if (
            len(argv) > sub_idx
            and argv[sub_idx] is not None
            and not argv[sub_idx].startswith("-")
        ):
            sub = argv[sub_idx]
        return (match_script, sub)

    # --- CliRunner().invoke(app, [...]) / runner.invoke(app, [...]) ---
    invoke_call = isinstance(func, ast.Attribute) and func.attr == "invoke"
    if invoke_call and len(call.args) >= 1:
        app_arg = call.args[0]
        # Resolve app object to script name
        bin_name: str | None = None
        if isinstance(app_arg, ast.Name) and app_arg.id in script_app_locals:
            # `app` was imported from a known script-entry module
            # Find which script it maps to via app_to_script (module-level)
            # script_app_locals tells us this name resolves to a script, but
            # we need to know WHICH script. For prototype simplicity, if
            # there's exactly one script, attribute it; else skip.
            if len(app_to_script) == 1:
                bin_name = next(iter(app_to_script.values()))
            else:
                # ambiguous — could refine via per-import tracking
                return None
        if bin_name is None:
            return None
        sub = ""
        if len(call.args) >= 2:
            second = call.args[1]
            if isinstance(second, ast.List) and second.elts:
                first_argv = _resolve_str_expr(second.elts[0], mod_strs, local_strs)
                if first_argv is not None and not first_argv.startswith("-"):
                    sub = first_argv
        if bin_name not in scripts:
            return None
        return (bin_name, sub)

    return None


# ---------------------------------------------------------------------------
# Test walker (mirrors v5 integration proto)
# ---------------------------------------------------------------------------


def _walk_test_funcs(tree: ast.Module) -> list[ast.FunctionDef]:
    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            funcs.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    funcs.append(child)
    return funcs


def _module_level_funcs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _direct_calls(node: ast.AST) -> set[str]:
    callees: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name):
                callees.add(f.id)
            elif isinstance(f, ast.Attribute):
                callees.add(f.attr)
    return callees


def _closure_nodes_for_test(
    test_func: ast.FunctionDef,
    mod_funcs: dict[str, ast.FunctionDef],
) -> list[ast.AST]:
    seen: set[str] = set()
    stack: list[str] = []
    if test_func.name in mod_funcs:
        stack.append(test_func.name)
    else:
        for callee in _direct_calls(test_func):
            if callee in mod_funcs:
                stack.append(callee)
    while stack:
        name = stack.pop()
        if name in seen or name not in mod_funcs:
            continue
        seen.add(name)
        for callee in _direct_calls(mod_funcs[name]):
            if callee in mod_funcs and callee not in seen:
                stack.append(callee)
    nodes: list[ast.AST] = [mod_funcs[n] for n in seen]
    if test_func.name not in seen:
        nodes.append(test_func)
    return nodes


# ---------------------------------------------------------------------------
# Per-test extraction
# ---------------------------------------------------------------------------


@dataclass
class TestInvocations:
    test_name: str
    invocations: Counter[tuple[str, str]] = field(default_factory=Counter)
    dynamic_skipped: int = 0  # invocations where argv was non-resolvable
    symbols: Counter[str] = field(default_factory=Counter)  # integration-style fallback

    def tuple_topk(self, k: int = TOP_K) -> tuple[str, ...]:
        """Return top-K invocation labels, sorted alphabetically.

        Label = "bin" if sub == "" else "bin-sub".
        """
        ranked = [self._label(inv) for inv, _ in self.invocations.most_common()]
        return tuple(sorted(ranked[:k]))

    @staticmethod
    def _label(inv: tuple[str, str]) -> str:
        bin_, sub = inv
        return bin_ if not sub else f"{bin_}-{sub}"


def _extract_test_invocations(
    test_func: ast.FunctionDef,
    mod_funcs: dict[str, ast.FunctionDef],
    scripts: set[str],
    script_app_locals: set[str],
    app_to_script: dict[str, str],
    mod_strs: dict[str, str],
    first_party_known: set[str],
) -> TestInvocations:
    out = TestInvocations(test_name=test_func.name)
    for node in _closure_nodes_for_test(test_func, mod_funcs):
        local_strs = _local_string_constants(node)
        local_lists = _local_list_bindings(node)
        out.symbols.update(_used_first_party_names(node, first_party_known))
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                inv = _extract_invocation_from_call(
                    sub,
                    scripts,
                    script_app_locals,
                    app_to_script,
                    mod_strs,
                    local_strs,
                    local_lists,
                )
                if inv is not None:
                    out.invocations[inv] += 1
                else:
                    # Detect a "looks like subprocess/invoke call we skipped"
                    # to track our dynamic-argv blind spot
                    f = sub.func
                    if (
                        isinstance(f, ast.Attribute)
                        and isinstance(f.value, ast.Name)
                        and f.value.id == "subprocess"
                        and f.attr
                        in {"run", "call", "check_call", "check_output", "Popen"}
                    ):
                        out.dynamic_skipped += 1
    return out


# ---------------------------------------------------------------------------
# Per-file analysis (mirrors v5)
# ---------------------------------------------------------------------------


@dataclass
class FileReport:
    path: Path
    tests: list[TestInvocations]
    tuples_k2: list[tuple[str, ...]] = field(default_factory=list)
    tuples_k3: list[tuple[str, ...]] = field(default_factory=list)
    union_k2: tuple[str, ...] = ()
    union_k3: tuple[str, ...] = ()
    cohesion_k2: float = 0.0
    cohesion_k3: float = 0.0
    fallback_k2: tuple[str, ...] = ()  # integration-style tuple when union_k2 empty
    has_first_party_imports: bool = False
    single_binary: str | None = None  # script name if package has exactly one

    @staticmethod
    def name_from(t: tuple[str, ...], single_binary: str | None = None) -> str:
        """Emit canonical filename. With single_binary set, strip the redundant
        binary prefix from each tuple element ('axm-audit-audit' -> 'audit')."""
        if not t:
            return "test_UNKNOWN.py"
        parts = list(t)
        if single_binary is not None:
            prefix = single_binary + "-"
            parts = [
                p[len(prefix) :]
                if p.startswith(prefix)
                else ("" if p == single_binary else p)
                for p in parts
            ]
            parts = [p for p in parts if p]
            if not parts:
                # all parts were the bare binary — keep one occurrence
                parts = [to_snake(single_binary)]
        return "test_" + "-".join(to_snake(s) for s in parts) + ".py"

    @property
    def name_k2(self) -> str:
        return self.name_from(self.union_k2, self.single_binary)

    @property
    def name_k3(self) -> str:
        return self.name_from(self.union_k3, self.single_binary)

    @property
    def n_tests(self) -> int:
        return len(self.tests)

    @property
    def split_k2(self) -> bool:
        return len({t for t in self.tuples_k2 if t}) > 1


def analyze_file(
    path: Path,
    scripts: set[str],
    app_to_script: dict[str, str],
) -> FileReport:
    tree = ast.parse(path.read_text())
    assert isinstance(tree, ast.Module)
    mod_funcs = _module_level_funcs(tree)
    mod_strs = _module_string_constants(tree)
    first_party_imports = _collect_package_imports(tree)
    first_party_known = set(first_party_imports.keys())
    # Names locally bound to an `app` symbol imported from a script entry module
    script_app_locals: set[str] = set()
    for module_path in app_to_script:
        script_app_locals.update(_imports_of_module(tree, module_path))

    tests: list[TestInvocations] = []
    for f in _walk_test_funcs(tree):
        tests.append(
            _extract_test_invocations(
                f,
                mod_funcs,
                scripts,
                script_app_locals,
                app_to_script,
                mod_strs,
                first_party_known,
            )
        )

    rep = FileReport(path=path, tests=tests)
    rep.has_first_party_imports = bool(first_party_imports)
    rep.single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    rep.tuples_k2 = [t.tuple_topk(2) for t in tests]
    rep.tuples_k3 = [t.tuple_topk(3) for t in tests]

    agg: Counter[str] = Counter()
    for t in tests:
        for inv, n in t.invocations.items():
            agg[TestInvocations._label(inv)] += n
    ranked = [s for s, _ in agg.most_common()]
    rep.union_k2 = tuple(sorted(ranked[:2]))
    rep.union_k3 = tuple(sorted(ranked[:3]))
    if rep.tuples_k2:
        rep.cohesion_k2 = sum(1 for t in rep.tuples_k2 if t == rep.union_k2) / len(
            rep.tuples_k2
        )
        rep.cohesion_k3 = sum(1 for t in rep.tuples_k3 if t == rep.union_k3) / len(
            rep.tuples_k3
        )

    # Integration-style fallback for files with no e2e-style tuple
    if not rep.union_k2:
        sym_agg: Counter[str] = Counter()
        for t in tests:
            sym_agg.update(t.symbols)
        sym_ranked = [s for s, _ in sym_agg.most_common()]
        rep.fallback_k2 = tuple(sorted(sym_ranked[:2]))

    return rep


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _analyze_package(pkg_dir: Path) -> list[FileReport]:
    """Analyze one package's tests/e2e/ directory. Sets module-level PACKAGE."""
    global PACKAGE
    pyproject = pkg_dir / "pyproject.toml"
    if not pyproject.exists():
        return []
    PACKAGE = pkg_dir.name.replace("-", "_")
    scripts = _load_project_scripts(pyproject)
    app_to_script = _load_app_targets(pyproject)
    tests_dir = pkg_dir / "tests" / "e2e"
    if not tests_dir.exists():
        return []
    files = sorted(
        p for p in tests_dir.rglob("test_*.py") if "__pycache__" not in p.parts
    )
    return [analyze_file(p, scripts, app_to_script) for p in files]


def _report_package(pkg_dir: Path, reports: list[FileReport]) -> None:
    pyproject = pkg_dir / "pyproject.toml"
    scripts = _load_project_scripts(pyproject) if pyproject.exists() else set()
    single = next(iter(scripts)) if len(scripts) == 1 else None

    print("\n" + "#" * 120)
    print(
        f"# PACKAGE: {pkg_dir.name}   scripts={sorted(scripts)}   "
        f"single_binary_collapse={'YES (' + single + ')' if single else 'NO'}"
    )
    print("#" * 120)

    if not reports:
        print("  (no tests/e2e/ directory or empty)")
        return

    print(f"\nAnalyzed {len(reports)} e2e test files")
    print("=" * 120)
    print(f"{'CURRENT':<60} {'#T':>3} {'COH':>5}  PROPOSED")
    print("=" * 120)
    for r in reports:
        flag = " *S*" if r.split_k2 else ""
        dyn = sum(t.dynamic_skipped for t in r.tests)
        dyn_tag = f"  [{dyn} dyn-skip]" if dyn else ""
        if r.union_k2:
            status = "E2E"
            name = r.name_k2
        elif r.fallback_k2:
            status = "INT"
            name = FileReport.name_from(r.fallback_k2, r.single_binary)
        else:
            status = "UNK"
            name = "test_UNKNOWN.py"
        print(
            f"{r.path.name:<60} {r.n_tests:>3} {r.cohesion_k2:>5.0%}  "
            f"[{status}] {name}{flag}{dyn_tag}"
        )

    # ---- COLLIDE: inter-file name collisions on E2E-named files only ----
    by_name: dict[str, list[FileReport]] = defaultdict(list)
    for r in reports:
        if r.union_k2:
            by_name[r.name_k2].append(r)
    collisions = {n: rs for n, rs in by_name.items() if len(rs) > 1}
    n_in_collision = sum(len(rs) for rs in collisions.values())
    n_e2e = sum(1 for r in reports if r.union_k2)
    print("\n" + "-" * 80)
    print(
        f"E2E status:  {n_e2e} files E2E-named, {n_in_collision} in collision groups "
        f"({len(collisions)} groups), {sum(1 for r in reports if r.split_k2)} SPLIT"
    )
    print(
        f"INT status:  {sum(1 for r in reports if not r.union_k2 and r.fallback_k2)} "
        f"integration-style fallback (mis-tiered candidates)"
    )
    print(
        f"UNK status:  {sum(1 for r in reports if not r.union_k2 and not r.fallback_k2)} "
        f"true UNKNOWN (rule violations)"
    )
    if reports:
        avg_coh = sum(r.cohesion_k2 for r in reports) / len(reports)
        print(f"Avg cohesion (intra-file, K=2):  {avg_coh:.0%}")
        if n_e2e:
            frag = n_in_collision / n_e2e
            print(
                f"Inter-file fragmentation:        {frag:.0%} "
                f"({n_in_collision}/{n_e2e} E2E files in collision)"
            )

    if collisions:
        print("\nCOLLIDE — files that would share the same canonical name:")
        for name, group in sorted(collisions.items(), key=lambda x: -len(x[1])):
            print(f"  {name}  ({len(group)} files)")
            for r in group:
                print(f"     - {r.path.name}")

    int_fallback = [r for r in reports if not r.union_k2 and r.fallback_k2]
    if int_fallback:
        print(
            f"\nMIS-TIERED ({len(int_fallback)}) — passes via integration-criterion; "
            f"recommend move to tests/integration/:"
        )
        for r in int_fallback:
            print(
                f"  {r.path.name:<54} → {FileReport.name_from(r.fallback_k2, r.single_binary)}"
            )

    true_unknown = [r for r in reports if not r.union_k2 and not r.fallback_k2]
    if true_unknown:
        print(
            f"\nTRUE UNKNOWN ({len(true_unknown)}) — rule violations (no first-party + no in-package CLI):"
        )
        for r in true_unknown:
            dyn = sum(t.dynamic_skipped for t in r.tests)
            print(f"  {r.path.name:<54} ({r.n_tests} tests, {dyn} dyn-skip)")


def main() -> int:
    pkg_args = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_PACKAGES
    per_pkg: list[tuple[Path, list[FileReport]]] = []
    for name in pkg_args:
        pkg_dir = WORKSPACE / name
        reports = _analyze_package(pkg_dir)
        per_pkg.append((pkg_dir, reports))
        _report_package(pkg_dir, reports)

    # ---- summary table across packages ----
    print("\n" + "=" * 100)
    print("CROSS-PACKAGE SUMMARY")
    print("=" * 100)
    print(
        f"{'Package':<14} {'#Files':>7} {'E2E':>5} {'INT':>5} {'UNK':>5} "
        f"{'COLLIDE%':>9} {'COH%':>6} {'SPLIT':>6}"
    )
    print("-" * 100)
    for pkg_dir, reports in per_pkg:
        if not reports:
            print(f"{pkg_dir.name:<14}    (no e2e directory)")
            continue
        n = len(reports)
        n_e2e = sum(1 for r in reports if r.union_k2)
        n_int = sum(1 for r in reports if not r.union_k2 and r.fallback_k2)
        n_unk = sum(1 for r in reports if not r.union_k2 and not r.fallback_k2)
        n_split = sum(1 for r in reports if r.split_k2)
        by_name: dict[str, int] = defaultdict(int)
        for r in reports:
            if r.union_k2:
                by_name[r.name_k2] += 1
        n_collide = sum(v for v in by_name.values() if v > 1)
        collide_pct = (n_collide / n_e2e * 100) if n_e2e else 0
        avg_coh = sum(r.cohesion_k2 for r in reports) / n
        print(
            f"{pkg_dir.name:<14} {n:>7} {n_e2e:>5} {n_int:>5} {n_unk:>5} "
            f"{collide_pct:>8.0f}% {avg_coh * 100:>5.0f}% {n_split:>6}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
