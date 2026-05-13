"""Evaluate a duplicate-detection rule against the labelled corpus.

Loads ``tests/fixtures/duplicate_corpus/cases.json``, recomputes the AST
features for every test (via ``git show``, no checkout), then for each
case asks: "does the candidate rule cluster this test with at least one
other test in the same file?"

- For ``real_dup`` cases, we want the rule to say YES (true positive).
- For ``false_positive`` cases, we want the rule to say NO.

Reports false-negative rate, noise-filter rate, and per-source breakdown.

Tweak ``candidate_rule`` at the bottom of the file and re-run.
"""

from __future__ import annotations

import ast
import json
import subprocess
from collections import defaultdict
from functools import lru_cache
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(__file__).resolve().parents[1]
CORPUS_PATH = PACKAGE_DIR / "tests" / "fixtures" / "duplicate_corpus" / "cases.json"


# ---------------------------------------------------------------------------
# AST feature extraction (mirrors what the detector uses)
# ---------------------------------------------------------------------------
def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def calls_of(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Call):
            f = c.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def literals_of(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Constant) and isinstance(c.value, (str, bytes)):
            out.add(repr(c.value))
    return out


def assert_attrs_of(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Assert):
            for sub in ast.walk(c):
                if isinstance(sub, ast.Attribute):
                    out.add(sub.attr)
    return out


def name_ids_of(node: ast.AST) -> set[str]:
    return {c.id for c in ast.walk(node) if isinstance(c, ast.Name)}


def attr_chain_of(node: ast.AST) -> set[str]:
    return {c.attr for c in ast.walk(node) if isinstance(c, ast.Attribute)}


def raises_of(node: ast.AST) -> set[str]:
    """Exception classes appearing in pytest.raises(...) or with-raises blocks."""
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Call):
            f = c.func
            is_raises = (isinstance(f, ast.Attribute) and f.attr == "raises") or (
                isinstance(f, ast.Name) and f.id == "raises"
            )
            if is_raises and c.args:
                arg = c.args[0]
                if isinstance(arg, ast.Name):
                    out.add(arg.id)
                elif isinstance(arg, ast.Attribute):
                    out.add(arg.attr)
                elif isinstance(arg, ast.Tuple):
                    for el in arg.elts:
                        if isinstance(el, ast.Name):
                            out.add(el.id)
                        elif isinstance(el, ast.Attribute):
                            out.add(el.attr)
    return out


def fixtures_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Function arguments = pytest fixtures (excluding self/cls)."""
    out: set[str] = set()
    for a in node.args.args:
        if a.arg not in ("self", "cls"):
            out.add(a.arg)
    return out


def marks_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """pytest.mark.X decorators (returns the X part)."""
    out: set[str] = set()
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        # pytest.mark.skip, pytest.mark.parametrize, ...
        if isinstance(target, ast.Attribute) and isinstance(
            target.value, ast.Attribute
        ):
            if target.value.attr == "mark":
                out.add(target.attr)
    return out


def decorators_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Non-pytest.mark decorators (e.g. @patch, @freeze_time)."""
    out: set[str] = set()
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Attribute):
            # skip pytest.mark.*
            if isinstance(target.value, ast.Attribute) and target.value.attr == "mark":
                continue
            out.add(target.attr)
        elif isinstance(target, ast.Name):
            out.add(target.id)
    return out


def with_ctx_of(node: ast.AST) -> set[str]:
    """Names of context manager callables in `with ...:` blocks."""
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, (ast.With, ast.AsyncWith)):
            for item in c.items:
                ce = item.context_expr
                if isinstance(ce, ast.Call):
                    f = ce.func
                    if isinstance(f, ast.Name):
                        out.add(f.id)
                    elif isinstance(f, ast.Attribute):
                        out.add(f.attr)
                elif isinstance(ce, ast.Name):
                    out.add(ce.id)
                elif isinstance(ce, ast.Attribute):
                    out.add(ce.attr)
    return out


def kwargs_of(node: ast.AST) -> set[str]:
    """Keyword argument names used at any Call site inside the test."""
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Call):
            for kw in c.keywords:
                if kw.arg is not None:
                    out.add(kw.arg)
    return out


def stmt_sequence_of(node: ast.AST) -> tuple[str, ...]:
    """Sequence of top-level statement types in the function body.

    Captures structure independently of identifiers. Two tests with the
    same sequence (Assign, Assign, Expr, Assert, Assert) are structurally
    identical even with different names.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return tuple(type(s).__name__ for s in node.body)
    return ()


def source_text_of(node: ast.AST) -> str:
    """Unparsed source text of the function (used for raw similarity)."""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def shape_of(node: ast.AST) -> dict[str, int]:
    """Structural metrics: stmt count, assert count, AST depth."""
    stmt_count = 0
    assert_count = 0
    for c in ast.walk(node):
        if isinstance(c, ast.stmt):
            stmt_count += 1
        if isinstance(c, ast.Assert):
            assert_count += 1

    def depth(n: ast.AST) -> int:
        children = list(ast.iter_child_nodes(n))
        if not children:
            return 1
        return 1 + max(depth(c) for c in children)

    return {
        "stmt_count": stmt_count,
        "assert_count": assert_count,
        "depth": depth(node),
    }


def class_ctx_of(node: ast.AST, tree: ast.AST) -> str | None:
    """Name of the enclosing ClassDef, if any."""
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            for child in ast.walk(cls):
                if child is node:
                    return cls.name
    return None


def features(node: ast.AST, tree: ast.AST | None = None) -> dict:
    out: dict = {
        "calls": calls_of(node),
        "lits": literals_of(node),
        "aattrs": assert_attrs_of(node),
        "names": name_ids_of(node),
        "attrs": attr_chain_of(node),
        "raises": raises_of(node),
        "with_ctx": with_ctx_of(node),
        "kwargs": kwargs_of(node),
    }
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        out["fixtures"] = fixtures_of(node)
        out["marks"] = marks_of(node)
        out["decorators"] = decorators_of(node)
    else:
        out["fixtures"] = set()
        out["marks"] = set()
        out["decorators"] = set()
    out["shape"] = shape_of(node)
    out["stmt_seq"] = stmt_sequence_of(node)
    out["src"] = source_text_of(node)
    out["test_name"] = (
        node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
    )
    out["lineno"] = getattr(node, "lineno", 0)
    if tree is not None:
        cls = class_ctx_of(node, tree)
        out["class_ctx"] = cls or ""
    else:
        out["class_ctx"] = ""
    return out


def _name_lcp(a: str, b: str) -> int:
    """Length of longest common prefix between two names."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def _src_ratio(a: str, b: str) -> float:
    """difflib SequenceMatcher ratio on full source text (cheap quick_ratio)."""
    if not a or not b:
        return 0.0
    import difflib

    return difflib.SequenceMatcher(None, a, b, autojunk=False).quick_ratio()


def pair_features(fa: dict, fb: dict) -> dict:
    sa, sb = fa["shape"], fb["shape"]
    # ORTHOGONAL signals: shape sequence, name proximity, source-line locality
    seq_a, seq_b = fa.get("stmt_seq", ()), fb.get("stmt_seq", ())
    same_stmt_seq = int(bool(seq_a) and seq_a == seq_b)
    # Stmt sequence Jaccard (multiset → set)
    stmt_seq_jaccard = jaccard(set(seq_a), set(seq_b)) if (seq_a or seq_b) else 0.0
    # Name LCP normalized by longer name length
    name_a, name_b = fa.get("test_name", ""), fb.get("test_name", "")
    longer = max(len(name_a), len(name_b)) or 1
    name_lcp_ratio = _name_lcp(name_a, name_b) / longer
    # Locality: distance between definitions in source (in lines)
    line_dist = abs(fa.get("lineno", 0) - fb.get("lineno", 0))
    # Raw source similarity (difflib)
    src_ratio = _src_ratio(fa.get("src", ""), fb.get("src", ""))
    return {
        # original Jaccards
        "call": jaccard(fa["calls"], fb["calls"]),
        "lit": jaccard(fa["lits"], fb["lits"]),
        "aattr": jaccard(fa["aattrs"], fb["aattrs"]),
        "name": jaccard(fa["names"], fb["names"]),
        "attr": jaccard(fa["attrs"], fb["attrs"]),
        # original size diagnostics
        "aattr_common": len(fa["aattrs"] & fb["aattrs"]),
        "call_common": len(fa["calls"] & fb["calls"]),
        "lit_common": len(fa["lits"] & fb["lits"]),
        # NEW features (Jaccards)
        "raises": jaccard(fa["raises"], fb["raises"]),
        "fixtures": jaccard(fa["fixtures"], fb["fixtures"]),
        "marks": jaccard(fa["marks"], fb["marks"]),
        "decorators": jaccard(fa["decorators"], fb["decorators"]),
        "with_ctx": jaccard(fa["with_ctx"], fb["with_ctx"]),
        "kwargs": jaccard(fa["kwargs"], fb["kwargs"]),
        # NEW size diagnostics
        "raises_common": len(fa["raises"] & fb["raises"]),
        "fixtures_common": len(fa["fixtures"] & fb["fixtures"]),
        "raises_either_nonempty": int(bool(fa["raises"]) or bool(fb["raises"])),
        # NEW shape deltas
        "stmt_delta": abs(sa["stmt_count"] - sb["stmt_count"]),
        "stmt_max": max(sa["stmt_count"], sb["stmt_count"]),
        "stmt_ratio": min(sa["stmt_count"], sb["stmt_count"])
        / max(sa["stmt_count"], sb["stmt_count"])
        if max(sa["stmt_count"], sb["stmt_count"])
        else 1.0,
        "assert_delta": abs(sa["assert_count"] - sb["assert_count"]),
        # NEW class context
        "same_class": int(fa["class_ctx"] == fb["class_ctx"] and fa["class_ctx"] != ""),
        "diff_class": int(
            fa["class_ctx"] != fb["class_ctx"]
            and fa["class_ctx"] != ""
            and fb["class_ctx"] != ""
        ),
        # ORTHOGONAL signals
        "same_stmt_seq": same_stmt_seq,
        "stmt_seq_jaccard": stmt_seq_jaccard,
        "name_lcp_ratio": name_lcp_ratio,
        "line_dist": line_dist,
        "src_ratio": src_ratio,
    }


# ---------------------------------------------------------------------------
# Source loading via git show (no checkout)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=4096)
def load_file_at(commit: str, file: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{commit}:{file}"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


@lru_cache(maxsize=4096)
def load_features_for_file(commit: str, file: str) -> tuple[tuple[str, dict], ...]:
    """Return ((test_name, features_dict), ...) for all tests in the file."""
    src = load_file_at(commit, file)
    if src is None:
        return ()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ()
    out: list[tuple[str, dict]] = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test_"):
            out.append((node.name, features(node, tree)))
    return tuple(out)


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------
def evaluate(rule, cases: list[dict]) -> dict:
    """Pair-level evaluation.

    For every pair of labelled cases sharing the same (commit, file):
    - both real_dup → MUST_CLUSTER pair (rule should return True)
    - both false_positive → MUST_SEPARATE pair (rule should return False)
    - mixed verdicts → MUST_SEPARATE pair (rule should return False)
    """
    # Group cases by (commit, file)
    by_loc: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        by_loc[(c["commit"], c["file"])].append(c)

    must_cluster_total = must_cluster_correct = 0  # both real_dup → rule says True
    must_separate_total = must_separate_correct = 0  # other → rule says False

    unloadable_pairs = 0

    for (commit, file), local_cases in by_loc.items():
        if len(local_cases) < 2:
            continue
        tests = load_features_for_file(commit, file)
        if not tests:
            unloadable_pairs += len(local_cases) * (len(local_cases) - 1) // 2
            continue
        feats_by_name = dict(tests)
        for ca, cb in combinations(local_cases, 2):
            fa = feats_by_name.get(ca["test"])
            fb = feats_by_name.get(cb["test"])
            if fa is None or fb is None:
                unloadable_pairs += 1
                continue
            predicted_cluster = rule(pair_features(fa, fb))
            both_real = ca["verdict"] == "real_dup" and cb["verdict"] == "real_dup"
            # Two real_dup tests are MUST_CLUSTER only if they share a fold
            # cluster_id (same actual fold within the commit). Different folds
            # in the same file/commit → MUST_SEPARATE.
            same_cluster = ca.get("cluster_id") is not None and ca.get(
                "cluster_id"
            ) == cb.get("cluster_id")
            both_real = both_real and same_cluster
            if both_real:
                must_cluster_total += 1
                if predicted_cluster:
                    must_cluster_correct += 1
            else:
                must_separate_total += 1
                if not predicted_cluster:
                    must_separate_correct += 1

    return {
        "must_cluster_total": must_cluster_total,
        "must_cluster_correct": must_cluster_correct,
        "must_separate_total": must_separate_total,
        "must_separate_correct": must_separate_correct,
        "unloadable_pairs": unloadable_pairs,
    }


def evaluate_debug(rule, cases: list[dict]) -> dict:
    """Same as evaluate() but also returns per-pair details for inspection."""
    by_loc: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        by_loc[(c["commit"], c["file"])].append(c)

    fn_pairs: list[dict] = []  # MUST_CLUSTER but rule says False
    fp_pairs: list[dict] = []  # MUST_SEPARATE but rule says True
    tn_pairs: list[dict] = []  # MUST_SEPARATE rule says False (correct)

    for (commit, file), local_cases in by_loc.items():
        if len(local_cases) < 2:
            continue
        tests = load_features_for_file(commit, file)
        if not tests:
            continue
        feats_by_name = dict(tests)
        for ca, cb in combinations(local_cases, 2):
            fa = feats_by_name.get(ca["test"])
            fb = feats_by_name.get(cb["test"])
            if fa is None or fb is None:
                continue
            pf = pair_features(fa, fb)
            predicted = rule(pf)
            both_real = ca["verdict"] == "real_dup" and cb["verdict"] == "real_dup"
            same_cluster = ca.get("cluster_id") is not None and ca.get(
                "cluster_id"
            ) == cb.get("cluster_id")
            both_real = both_real and same_cluster
            entry = {
                "commit": commit[:8],
                "file": file,
                "test_a": ca["test"],
                "test_b": cb["test"],
                "verdict_a": ca["verdict"],
                "verdict_b": cb["verdict"],
                "features": pf,
                "fa": fa,
                "fb": fb,
            }
            if both_real and not predicted:
                fn_pairs.append(entry)
            elif not both_real and predicted:
                fp_pairs.append(entry)
            elif not both_real and not predicted:
                tn_pairs.append(entry)
    return {"fn": fn_pairs, "fp": fp_pairs, "tn": tn_pairs}


def report(metrics: dict, rule_name: str) -> None:
    mct = metrics["must_cluster_total"]
    mcc = metrics["must_cluster_correct"]
    mst = metrics["must_separate_total"]
    msc = metrics["must_separate_correct"]
    recall = mcc / mct if mct else 0.0
    specificity = msc / mst if mst else 0.0
    print(f"=== Rule: {rule_name} ===")
    print(
        f"  RECALL (real-dup pairs clustered):  {mcc}/{mct} = {recall * 100:.1f}%   "
        f"(missed {mct - mcc} → FN)"
    )
    print(
        f"  SPECIFICITY (FP pairs separated):   {msc}/{mst} = {specificity * 100:.1f}%   "
        f"(falsely clustered: {mst - msc})"
    )
    if metrics["unloadable_pairs"]:
        print(f"  Unloadable pairs: {metrics['unloadable_pairs']}")


# ---------------------------------------------------------------------------
# Candidate rules — tweak here and re-run.
#
# A rule takes a feature dict {call, lit, aattr, name, attr} (all in [0,1])
# and returns True if the pair should be considered a duplicate (clustered).
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Production detector wrapper — uses the actual S1/S2/S3 + P1-P9 logic.
#
# We import the production module and call _cluster() per (commit, file).
# A pair is considered "clustered by production" iff both tests appear in
# the same merged cluster AND the cluster's signal is NOT one of the
# `ambiguous_*` labels (which means a P-rescue demoted the cluster).
# ---------------------------------------------------------------------------
from axm_audit.core.rules.test_quality import duplicate_tests as _prod  # noqa: E402


@lru_cache(maxsize=4096)
def _prod_clusters_for_file_full(
    commit: str, file: str
) -> tuple[tuple[str, frozenset[tuple[str, str]]], ...]:
    """Return ((signal, members), ...) for ALL clusters incl. ambiguous_*."""
    src = load_file_at(commit, file)
    if src is None:
        return ()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ()
    tests: list = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    tests.append(_prod.make_test_func(file, child, node.name))
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            tests.append(_prod.make_test_func(file, node, None))
    if not tests:
        return ()
    clusters = _prod._cluster(tests, threshold=0.8)
    out: list[tuple[str, frozenset[tuple[str, str]]]] = []
    for c in clusters:
        sig = c.get("signal", "")
        members = frozenset(
            (t.get("file", ""), t.get("name", "")) for t in c.get("tests", [])
        )
        if len(members) >= 2:
            out.append((sig, members))
    return tuple(out)


@lru_cache(maxsize=4096)
def _prod_clusters_for_file(
    commit: str, file: str
) -> tuple[frozenset[tuple[str, str]], ...]:
    """Run production detector on (commit, file). Return tuple of frozensets,
    each frozenset = the (file, test_name) members of one CONFIDENT cluster
    (ambiguous_* clusters are excluded — they're production's "uncertain"
    bucket, equivalent to "do not cluster firmly")."""
    src = load_file_at(commit, file)
    if src is None:
        return ()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ()
    tests: list = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    tests.append(_prod.make_test_func(file, child, node.name))
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            tests.append(_prod.make_test_func(file, node, None))
    if not tests:
        return ()
    clusters = _prod._cluster(tests, threshold=0.8)
    out: list[frozenset[tuple[str, str]]] = []
    for c in clusters:
        sig = c.get("signal", "")
        if sig.startswith("ambiguous_"):
            continue
        members = frozenset(
            (t.get("file", ""), t.get("name", "")) for t in c.get("tests", [])
        )
        if len(members) >= 2:
            out.append(members)
    return tuple(out)


def _v41_extra_separators(pf: dict) -> bool:
    """Return True iff our defensive stacked separators say 'separate'.

    Mirrors rule_v41 — the very_strong bypass is checked by caller.
    """
    if pf["line_dist"] > 300:
        return True
    if pf["stmt_ratio"] < 0.3:
        return True
    if (
        pf["diff_class"]
        and pf["aattr_common"] == 0
        and pf["lit_common"] == 0
        and pf["call_common"] <= 1
        and pf["call"] < 0.99
        and pf["name"] < 0.99
        and pf["attr"] < 0.99
    ):
        return True
    if (
        not pf["same_stmt_seq"]
        and pf["assert_delta"] >= 3
        and pf["aattr_common"] == 0
        and pf["lit_common"] == 0
        and pf["call"] < 0.99
    ):
        return True
    return False


def evaluate_prod(
    cases: list[dict],
    add_locality_filter: bool = False,
    add_full_stack: bool = False,
    include_ambiguous: bool = True,
) -> dict:
    """Pair-level eval using the actual production detector.

    If add_locality_filter is True, override prod's verdict to SEPARATE
    when line_dist > 300 (and pair has no extreme overlap).
    """
    by_loc: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        by_loc[(c["commit"], c["file"])].append(c)

    must_cluster_total = must_cluster_correct = 0
    must_separate_total = must_separate_correct = 0

    for (commit, file), local_cases in by_loc.items():
        if len(local_cases) < 2:
            continue
        tests = load_features_for_file(commit, file)
        if not tests:
            continue
        feats_by_name = dict(tests)
        if include_ambiguous:
            full_clusters = _prod_clusters_for_file_full(commit, file)
            clusters = tuple(members for _, members in full_clusters)
        else:
            clusters = _prod_clusters_for_file(commit, file)

        for ca, cb in combinations(local_cases, 2):
            fa = feats_by_name.get(ca["test"])
            fb = feats_by_name.get(cb["test"])
            if fa is None or fb is None:
                continue
            # Production verdict
            in_same_cluster = False
            for c in clusters:
                if (file, ca["test"]) in c and (file, cb["test"]) in c:
                    in_same_cluster = True
                    break
            verdict = in_same_cluster

            # Optional defensive filters (only override if no very strong direct signal)
            if (add_locality_filter or add_full_stack) and verdict:
                pf = pair_features(fa, fb)
                very_strong = (
                    (pf["call"] >= 0.99 and pf["attr"] >= 0.99)
                    or (pf["aattr_common"] >= 3)
                    or (pf["lit_common"] >= 3 and pf["call"] >= 0.7)
                    or (pf["src_ratio"] >= 0.85 and pf["call"] >= 0.5)
                )
                if not very_strong:
                    if add_full_stack and _v41_extra_separators(pf):
                        verdict = False
                    elif add_locality_filter and pf["line_dist"] > 300:
                        verdict = False

            both_real = ca["verdict"] == "real_dup" and cb["verdict"] == "real_dup"
            same_cluster_id = ca.get("cluster_id") is not None and ca.get(
                "cluster_id"
            ) == cb.get("cluster_id")
            both_real = both_real and same_cluster_id

            if both_real:
                must_cluster_total += 1
                if verdict:
                    must_cluster_correct += 1
            else:
                must_separate_total += 1
                if not verdict:
                    must_separate_correct += 1

    return {
        "must_cluster_total": must_cluster_total,
        "must_cluster_correct": must_cluster_correct,
        "must_separate_total": must_separate_total,
        "must_separate_correct": must_separate_correct,
        "unloadable_pairs": 0,
    }


def rule_prod_factory():
    """Return a closure that decides cluster/separate by inspecting prod clusters.

    Because the production detector is per-file (not per-pair), we attach
    file/commit context as a closure rather than passing it through `pair_features`.
    """
    state: dict = {"commit": None, "file": None}

    def set_context(commit: str, file: str) -> None:
        state["commit"] = commit
        state["file"] = file

    def rule(p: dict) -> bool:
        commit = state["commit"]
        file = state["file"]
        if commit is None or file is None:
            return False
        ta, tb = p.get("test_a"), p.get("test_b")
        if ta is None or tb is None:
            return False
        clusters = _prod_clusters_for_file(commit, file)
        for c in clusters:
            if (file, ta) in c and (file, tb) in c:
                return True
        return False

    rule.set_context = set_context  # type: ignore[attr-defined]
    return rule


def rule_always_cluster(p: dict[str, float]) -> bool:
    """Sanity check: cluster everything. Recall=100%, specificity=0%."""
    return True


def rule_never_cluster(p: dict[str, float]) -> bool:
    """Sanity check: cluster nothing. Recall=0%, specificity=100%."""
    return False


def rule_call_or_lit(p: dict[str, float]) -> bool:
    """Permissive: cluster if calls OR literals share something."""
    return p["call"] >= 0.5 or p["lit"] >= 0.3


def rule_old_filter(p: dict[str, float]) -> bool:
    """Cluster unless (call<0.5 AND lit<0.1) — the OLD filter we tested."""
    return not (p["call"] < 0.5 and p["lit"] < 0.1)


def rule_new_filter(p: dict[str, float]) -> bool:
    """Cluster unless (call<0.5 AND lit<0.1 AND name<0.5 AND attr<0.7).

    Baseline: recall 99.2% (4 FN), specificity 37.8% (2469 FP).
    All 4 FN share signature: call=0.125, lit=0, aattr=1.0 (size=2),
    name=0.273, attr=0.6 — both tests assert on {details, passed}.
    """
    return not (
        p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    )


def rule_v2(p: dict[str, float]) -> bool:
    """v2: rescue FN where aattr=1.0 AND common assert-attrs >= 2.

    Adds rescue clause: if both tests assert on the same set of >=2 attrs,
    cluster regardless of other features. Targets the 4 FN of rule_new_filter.
    """
    base = not (
        p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    )
    rescue = p["aattr"] >= 0.99 and p["aattr_common"] >= 2
    return base or rescue


def rule_v3(p: dict[str, float]) -> bool:
    """v3: v2 + tighten separate condition with aattr_common requirement.

    v2 brings FN to 0 but adds FP. To compensate, tighten the base "cluster"
    decision: also require some aattr signal (common >=1) OR another feature.
    """
    rescue = p["aattr"] >= 0.99 and p["aattr_common"] >= 2
    if rescue:
        return True
    # Base separate condition: weak across the board
    weak = p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    return not weak


def rule_v4(p: dict[str, float]) -> bool:
    """v4: tighten separate to require non-trivial sharing somewhere.

    Idea: separate (return False) when no feature is strong AND no real
    overlap exists. Adds: pairs with NO common asserts AND no shared
    literals AND name<0.7 AND attr<0.9 → separate.
    """
    rescue = p["aattr"] >= 0.99 and p["aattr_common"] >= 2
    if rescue:
        return True
    weak_baseline = (
        p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    )
    if weak_baseline:
        return False
    # Additional separate: empty asserts + low literal sharing + moderate name/attr
    no_signal = (
        p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["name"] < 0.7
        and p["attr"] < 0.9
        and p["call"] < 0.7
    )
    if no_signal:
        return False
    return True


def rule_v6(p: dict[str, float]) -> bool:
    """v6: positive-signal rule. Cluster only when at least one of:
    - call=1.0
    - name>=0.9
    - attr=1.0
    - lit>=0.5
    - aattr=1.0 with common>=2 (rescue)
    - moderate combo: name>=0.7 AND attr>=0.5 AND aattr_common>=1
    - moderate combo: call>=0.5 AND name>=0.7 AND lit_common>=1
    - moderate combo: call>=0.5 AND aattr_common>=2
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    if f["call"] >= 0.99:
        return True
    if f["name"] >= 0.9:
        return True
    if f["attr"] >= 0.99:
        return True
    if f["lit"] >= 0.5:
        return True
    if f["name"] >= 0.7 and f["attr"] >= 0.5 and f["aattr_common"] >= 1:
        return True
    if f["call"] >= 0.5 and f["name"] >= 0.7 and f["lit_common"] >= 1:
        return True
    if f["call"] >= 0.5 and f["aattr_common"] >= 2:
        return True
    return False


def rule_v7(p: dict[str, float]) -> bool:
    """v7: more permissive than v6 — keep base "weak everywhere → separate"
    but cluster more eagerly when 2+ moderate signals coexist.
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    # Original "weak everywhere" → separate
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    # If we get here: at least one feature is non-weak. Now further filter:
    # require at least one of these "real signal" indicators.
    has_signal = (
        f["call"] >= 0.99
        or f["name"] >= 0.9
        or f["attr"] >= 0.99
        or f["lit"] >= 0.3
        or f["aattr_common"] >= 1
    )
    return has_signal


def rule_v40(p: dict) -> bool:
    """v40: SAFE locality — line_dist>300 only if NO strong duplicate signal.

    Defensive ordering: a pair with strong evidence of duplication (perfect
    call match, identical asserts, high src similarity) overrides locality.
    Only when the pair would cluster on weak/moderate evidence AND is far
    apart in the source do we override and separate.
    """
    # Step 1: baseline weakness check (unchanged)
    weak = p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    if weak:
        return False

    # Step 2: strong-signal lanes — these BYPASS the locality filter
    very_strong = (
        (p["call"] >= 0.99 and p["attr"] >= 0.99)
        or (p["aattr_common"] >= 3)
        or (p["lit_common"] >= 3 and p["call"] >= 0.7)
        or (p["src_ratio"] >= 0.85 and p["call"] >= 0.5)
    )
    if very_strong:
        return True

    # Step 3: locality separator (only fires if not very_strong)
    if p["line_dist"] > 300:
        return False

    return True


def rule_v41(p: dict) -> bool:
    """v41: v40 + structural & class-context separators (also conditional)."""
    weak = p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    if weak:
        return False

    very_strong = (
        (p["call"] >= 0.99 and p["attr"] >= 0.99)
        or (p["aattr_common"] >= 3)
        or (p["lit_common"] >= 3 and p["call"] >= 0.7)
        or (p["src_ratio"] >= 0.85 and p["call"] >= 0.5)
    )
    if very_strong:
        return True

    if p["line_dist"] > 300:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call_common"] <= 1
        and p["call"] < 0.99
        and p["name"] < 0.99
        and p["attr"] < 0.99
    ):
        return False
    if (
        not p["same_stmt_seq"]
        and p["assert_delta"] >= 3
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call"] < 0.99
    ):
        return False
    return True


def rule_v30(p: dict) -> bool:
    """v30: baseline + locality (line_dist>300 → separate).

    Orthogonal signal: if two tests are >300 lines apart in the source file,
    they're effectively never folded by any agent. 0 RD-kill, ~558 FP-kill.
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["line_dist"] > 300:
        return False
    return True


def rule_v31(p: dict) -> bool:
    """v31: v30 + line_dist>200 with no aattr/lit overlap.

    Tighten: pairs >200 lines apart with zero shared asserts/literals are
    almost certainly not duplicates. Expected RD-kill: ~3, FP-kill: ~big.
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["line_dist"] > 300:
        return False
    if p["line_dist"] > 200 and p["aattr_common"] == 0 and p["lit_common"] == 0:
        return False
    return True


def rule_v32(p: dict) -> bool:
    """v32: v30 + stmt_ratio<0.3 + diff_class no-overlap separators (stack)."""
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["line_dist"] > 300:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call_common"] <= 1
        and p["call"] < 0.99
        and p["name"] < 0.99
        and p["attr"] < 0.99
    ):
        return False
    return True


def rule_v33(p: dict) -> bool:
    """v33: v32 + name_lcp + structural-divergence stack.

    Add: when no overlap AND stmt_seq differs AND assert_delta>=2 → separate.
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["line_dist"] > 300:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call_common"] <= 1
        and p["call"] < 0.99
        and p["name"] < 0.99
        and p["attr"] < 0.99
    ):
        return False
    # Structural divergence with no overlap: different stmt sequences AND
    # asserts diverge AND no shared lits/asserts → almost surely not dup
    if (
        not p["same_stmt_seq"]
        and p["assert_delta"] >= 3
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call"] < 0.99
    ):
        return False
    return True


def rule_v34(p: dict) -> bool:
    """v34: v33 + push line_dist threshold to 250 (slightly less safe).

    line_dist>250 with no overlap → separate. Expected: ~2 RD-kill, much
    larger FP-kill.
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["line_dist"] > 300:
        return False
    if p["line_dist"] > 250 and p["aattr_common"] == 0 and p["lit_common"] == 0:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call_common"] <= 1
        and p["call"] < 0.99
        and p["name"] < 0.99
        and p["attr"] < 0.99
    ):
        return False
    if (
        not p["same_stmt_seq"]
        and p["assert_delta"] >= 3
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call"] < 0.99
    ):
        return False
    return True


def rule_v20(p: dict) -> bool:
    """v20: baseline + separate when stmt_ratio < 0.3 (very different sizes).

    Real_dup pairs: 0% have stmt_ratio<0.3. Separate pairs: 0.2%. Free win.
    """
    if not (p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7):
        if p["stmt_ratio"] < 0.3:
            return False
        return True
    return False


def rule_v21(p: dict) -> bool:
    """v21: v20 + separate diff_class when zero overlap.

    diff_class=1 is 9.3% of real_dup but 62.1% of separate. To preserve
    recall, only separate diff_class pairs that have NO meaningful overlap.
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call_common"] <= 1
        and p["call"] < 0.99
        and p["name"] < 0.99
        and p["attr"] < 0.99
    ):
        return False
    return True


def rule_v22(p: dict) -> bool:
    """v22: v21 + tighten diff_class with assert_delta.

    Among diff_class pairs with no aattr/lit overlap, also separate when
    assert counts differ a lot (different test contracts).
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call_common"] <= 1
        and p["call"] < 0.99
        and p["name"] < 0.99
        and p["attr"] < 0.99
    ):
        return False
    # Big assert_delta + zero shared asserts/lits is suspicious regardless
    if (
        p["assert_delta"] >= 4
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call"] < 0.99
        and p["name"] < 0.99
    ):
        return False
    return True


def rule_v23(p: dict) -> bool:
    """v23: v22 + separate diff_class also when overlap is weak (loosen condition).

    Try more aggressive diff_class separation: drop the call_common<=1 cap.
    Risk: could lose recall on cross-class folds.
    """
    if p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7:
        return False
    if p["stmt_ratio"] < 0.3:
        return False
    if (
        p["diff_class"]
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call"] < 0.99
        and p["name"] < 0.9
        and p["attr"] < 0.99
    ):
        return False
    if (
        p["assert_delta"] >= 4
        and p["aattr_common"] == 0
        and p["lit_common"] == 0
        and p["call"] < 0.99
        and p["name"] < 0.99
    ):
        return False
    return True


def rule_v10(p: dict) -> bool:
    """v10: v2 + use diff_class as a separator.

    Pairs in DIFFERENT test classes are 11.7% of real_dup but 61.5% of separate.
    Strong negative signal — separate them unless very strong other signal.
    """
    f = p
    # Rescue lane (preserve recall on the original 4 FN)
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    # Original baseline: weak everywhere → separate
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    # NEW: different test classes → separate unless very strong signal
    if f["diff_class"]:
        very_strong = (
            f["call"] >= 0.99
            or (f["lit"] >= 0.5 and f["lit_common"] >= 2)
            or (f["aattr"] >= 0.99 and f["aattr_common"] >= 2)
        )
        if not very_strong:
            return False
    return True


def rule_v11(p: dict) -> bool:
    """v11: v10 + use assert_delta as filter.

    real_dup pairs have assert_delta==0 in 90% of cases. Pairs with very
    different #asserts AND no aattr_common are likely separate.
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    if f["diff_class"]:
        very_strong = (
            f["call"] >= 0.99
            or (f["lit"] >= 0.5 and f["lit_common"] >= 2)
            or (f["aattr"] >= 0.99 and f["aattr_common"] >= 2)
        )
        if not very_strong:
            return False
    # NEW: large assert_delta + no aattr overlap → separate
    if f["assert_delta"] >= 3 and f["aattr_common"] == 0:
        return False
    return True


def rule_v12(p: dict) -> bool:
    """v12: v11 + stmt_ratio filter.

    Pairs with very different statement counts (stmt_ratio < 0.5) and no
    aattr/lit overlap are unlikely duplicates.
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    if f["diff_class"]:
        very_strong = (
            f["call"] >= 0.99
            or (f["lit"] >= 0.5 and f["lit_common"] >= 2)
            or (f["aattr"] >= 0.99 and f["aattr_common"] >= 2)
        )
        if not very_strong:
            return False
    if f["assert_delta"] >= 3 and f["aattr_common"] == 0:
        return False
    if f["stmt_ratio"] < 0.5 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    return True


def rule_v13(p: dict) -> bool:
    """v13: v2 + only assert_delta + stmt_ratio filters (no diff_class).

    Use the strongest discriminators that don't kill recall: assert_delta
    and stmt_ratio. These are structural, not contextual.
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    # Large assert_delta + no aattr/lit overlap → separate
    if f["assert_delta"] >= 3 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    # Very different sizes + no overlap → separate
    if f["stmt_ratio"] < 0.4 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    return True


def rule_v14(p: dict) -> bool:
    """v14: v13 + softer diff_class.

    diff_class=1 alone kills recall. But diff_class=1 AND no shared
    asserts/literals AND no shared fixtures might be safe to separate.
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    if f["assert_delta"] >= 3 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    if f["stmt_ratio"] < 0.4 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    if (
        f["diff_class"]
        and f["aattr_common"] == 0
        and f["lit_common"] == 0
        and f["fixtures_common"] < 2
        and f["call"] < 0.99
    ):
        return False
    return True


def rule_v15(p: dict) -> bool:
    """v15: v14 + stmt_delta + assert_delta combined.

    Even with same #stmts, big assert_delta is suspicious. And one of the
    real_dup gold standard signals is "structurally identical" — we can
    require stmt_delta<=N when other signals are mid-range.
    """
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    # structural divergence
    if f["assert_delta"] >= 3 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    if f["stmt_ratio"] < 0.4 and f["aattr_common"] == 0 and f["lit_common"] == 0:
        return False
    # different classes + no semantic overlap
    if (
        f["diff_class"]
        and f["aattr_common"] == 0
        and f["lit_common"] == 0
        and f["fixtures_common"] < 2
        and f["call"] < 0.99
    ):
        return False
    # mid-range everywhere + structural mismatch
    no_strong = not (
        f["call"] >= 0.99 or f["name"] >= 0.9 or f["attr"] >= 0.99 or f["lit"] >= 0.5
    )
    if no_strong and f["assert_delta"] >= 2 and f["aattr_common"] == 0:
        return False
    return True


def rule_v8(p: dict[str, float]) -> bool:
    """v8: rescue + tighten with 'has any signal' BUT keep aattr_common>=1
    rescue lane for moderate cases. Aim: 100% recall, specificity > 38%.
    """
    f = p
    # Rescue lane: strong shared assert pattern
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    # Original separate baseline
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    # Beyond-baseline: require at least one signal indicator
    has_signal = (
        f["call"] >= 0.99
        or f["name"] >= 0.9
        or f["attr"] >= 0.99
        or f["lit"] >= 0.3
        or f["aattr_common"] >= 1
        or f["lit_common"] >= 2
    )
    return has_signal


def rule_v9(p: dict[str, float]) -> bool:
    """v9: v8 with stricter signal — no aattr_common=1 alone."""
    f = p
    if f["aattr"] >= 0.99 and f["aattr_common"] >= 2:
        return True
    weak = f["call"] < 0.5 and f["lit"] < 0.1 and f["name"] < 0.5 and f["attr"] < 0.7
    if weak:
        return False
    has_signal = (
        f["call"] >= 0.99
        or f["name"] >= 0.9
        or f["attr"] >= 0.99
        or f["lit"] >= 0.3
        or f["aattr_common"] >= 2
        or (f["aattr_common"] >= 1 and (f["call"] >= 0.7 or f["name"] >= 0.7))
        or f["lit_common"] >= 2
    )
    return has_signal


def rule_v5(p: dict[str, float]) -> bool:
    """v5: more aggressive — separate when *any two* features are very weak.

    Hypothesis: real_dup pairs have at least one strong signal (call=1, name=1,
    or attr=1, or aattr=1 with common>=2). Separate pairs often have
    every feature in the mid-range without any peak.
    """
    rescue = p["aattr"] >= 0.99 and p["aattr_common"] >= 2
    if rescue:
        return True
    has_strong = (
        p["call"] >= 0.99 or p["name"] >= 0.9 or p["attr"] >= 0.99 or (p["lit"] >= 0.5)
    )
    weak_baseline = (
        p["call"] < 0.5 and p["lit"] < 0.1 and p["name"] < 0.5 and p["attr"] < 0.7
    )
    if weak_baseline:
        return False
    if not has_strong:
        return False
    return True


def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(
            f"Corpus not found at {CORPUS_PATH} — run build_corpus.py first"
        )
    cases = json.loads(CORPUS_PATH.read_text())
    print(f"Loaded {len(cases)} cases\n")

    for name, rule in [
        ("ALWAYS cluster (sanity ceiling on recall)", rule_always_cluster),
        ("NEVER cluster (sanity ceiling on specificity)", rule_never_cluster),
        ("call≥0.5 OR lit≥0.3 → cluster", rule_call_or_lit),
        ("OLD filter (cluster unless call<0.5 AND lit<0.1)", rule_old_filter),
        ("NEW filter (OLD + name<0.5 AND attr<0.7)", rule_new_filter),
        ("v2: NEW + rescue (aattr=1.0 AND common>=2)", rule_v2),
        ("v3: same as v2 (no extra tightening yet)", rule_v3),
        ("v4: v2 + separate when no aattr/lit signal AND mid-range", rule_v4),
        ("v5: v2 + require at least one strong feature peak", rule_v5),
        ("v6: positive-signal rule (cluster only if explicit signal)", rule_v6),
        ("v7: weak baseline + 'has any signal' filter", rule_v7),
        ("v8: rescue + has-signal (aattr_common>=1 OR strong)", rule_v8),
        ("v9: v8 stricter (aattr_common>=2 alone, =1 needs companion)", rule_v9),
        ("v10: v2 + diff_class separator", rule_v10),
        ("v11: v10 + large assert_delta separator", rule_v11),
        ("v12: v11 + stmt_ratio<0.5 separator", rule_v12),
        ("v13: v2 + assert_delta + stmt_ratio (struct only)", rule_v13),
        ("v14: v13 + soft diff_class (no overlap at all)", rule_v14),
        ("v15: v14 + assert_delta>=2 when no strong signal", rule_v15),
        ("v20: baseline + stmt_ratio<0.3 separator", rule_v20),
        ("v21: v20 + diff_class with no overlap", rule_v21),
        ("v22: v21 + assert_delta>=4 with no overlap", rule_v22),
        ("v23: v22 + looser diff_class condition", rule_v23),
        ("v30: baseline + line_dist>300 separator (orthogonal)", rule_v30),
        ("v31: v30 + line_dist>200 with no overlap", rule_v31),
        ("v32: v30 + stmt_ratio + diff_class stack", rule_v32),
        ("v33: v32 + structural divergence (stmt_seq + assert_delta)", rule_v33),
        ("v34: v33 + line_dist>250 with no overlap (aggressive)", rule_v34),
        ("v40: SAFE — locality only if no strong-signal bypass", rule_v40),
        ("v41: v40 + structural/class-context separators (all conditional)", rule_v41),
    ]:
        m = evaluate(rule, cases)
        report(m, name)
        print()

    # Production detector — actual S1/S2/S3 + P1-P9 logic
    print("=" * 60)
    print("Production detector evaluation (actual duplicate_tests.py)")
    print("=" * 60)
    m = evaluate_prod(cases, add_locality_filter=False, include_ambiguous=False)
    report(m, "PROD CONFIDENT only (signal1/2/3, multi_signal)")
    print()
    m = evaluate_prod(cases, add_locality_filter=False, include_ambiguous=True)
    report(m, "PROD ALL (incl. ambiguous_* — what user actually sees)")
    print()
    m = evaluate_prod(cases, add_locality_filter=True, include_ambiguous=True)
    report(m, "PROD ALL + line_dist>300 (defensive locality filter)")
    print()
    m = evaluate_prod(cases, add_full_stack=True, include_ambiguous=True)
    report(
        m, "PROD ALL + full v41 stack (locality + stmt_ratio + diff_class + structural)"
    )
    print()

    # Diagnostic: how often are real_dup pairs in an *ambiguous* cluster?
    print("Diagnostic: production cluster signal distribution for real_dup pairs")
    by_loc: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        by_loc[(c["commit"], c["file"])].append(c)
    sig_counts: dict[str, int] = defaultdict(int)
    for (commit, file), local in by_loc.items():
        if len(local) < 2:
            continue
        full = _prod_clusters_for_file_full(commit, file)
        for ca, cb in combinations(local, 2):
            if not (ca["verdict"] == "real_dup" and cb["verdict"] == "real_dup"):
                continue
            if ca.get("cluster_id") != cb.get("cluster_id"):
                continue
            found_sig = "NOT_CLUSTERED"
            for sig, members in full:
                if (file, ca["test"]) in members and (file, cb["test"]) in members:
                    found_sig = sig
                    break
            sig_counts[found_sig] += 1
    total = sum(sig_counts.values())
    for sig, n in sorted(sig_counts.items(), key=lambda x: -x[1]):
        print(f"  {sig:40s} {n:4d}  ({100 * n / total:.1f}%)")


if __name__ == "__main__":
    main()
