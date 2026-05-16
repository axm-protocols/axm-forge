"""Build the duplicate-test detection ground-truth corpus.

Two label sources, both extracted from git history:

1. ``real_dup``  — tests deleted in commits that add a parametrize/merge.
   The agent (or human) judged these tests as duplicates and folded them.
2. ``false_positive`` — tests that were in a duplicate cluster BEFORE a
   dedup commit, are still in a cluster AFTER, and live in a file modified
   by that commit. The agent examined them and decided NOT to fold.

Output: ``tests/fixtures/duplicate_corpus/cases.json`` (a flat list of
labelled (commit, file, test) triplets).
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # axm-forge/
PACKAGE_DIR = Path(__file__).resolve().parents[1]  # axm-audit/
CORPUS_PATH = PACKAGE_DIR / "tests" / "fixtures" / "duplicate_corpus" / "cases.json"

DEDUP_MSG_RE = re.compile(r"(parametriz|merge.*test|dedup)", re.IGNORECASE)
DEF_RE = re.compile(r"^[+-]\s*(?:async\s+)?def\s+(test_\w+)\s*\(")
FILE_RE = re.compile(r"^diff --git a/.+ b/(.+\.py)$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Two deleted tests separated by more than this many lines in the original
# file are considered different clusters within the same fold commit.
CLUSTER_GAP_LINES = 80


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
    )


def list_dedup_commits() -> list[tuple[str, str]]:
    """Return [(sha, msg)] for commits whose subject mentions a fold/dedup."""
    log = git("log", "--all", "--pretty=%H %s")
    out: list[tuple[str, str]] = []
    for line in log.strip().splitlines():
        sha, _, msg = line.partition(" ")
        if DEDUP_MSG_RE.search(msg):
            out.append((sha, msg))
    return out


def parse_diff_deletions(
    sha: str,
) -> tuple[dict[str, list[tuple[str, int]]], dict[str, list[int]]]:
    """Return per-file structures for cluster-aware extraction.

    - per_file_deleted: file -> [(test_name, original_line), ...]
    - per_file_param_lines: file -> [original_line, ...] for each parametrize
      block added in the diff (line in the original file = hunk's `-` start)
    """
    diff = git("show", sha)
    per_file_deleted: dict[str, list[tuple[str, int]]] = {}
    per_file_param_lines: dict[str, list[int]] = {}
    cur: str | None = None
    orig_line: int | None = None  # current line counter in the original file
    new_line: int | None = None
    for ln in diff.splitlines():
        m = FILE_RE.match(ln)
        if m:
            cur = m.group(1)
            orig_line = None
            new_line = None
            continue
        if cur is None:
            continue
        h = HUNK_RE.match(ln)
        if h:
            orig_line = int(h.group(1))
            new_line = int(h.group(3))
            continue
        if orig_line is None or new_line is None:
            continue
        if ln.startswith("-") and not ln.startswith("---"):
            mm = DEF_RE.match(ln)
            if mm:
                per_file_deleted.setdefault(cur, []).append((mm.group(1), orig_line))
            orig_line += 1
        elif ln.startswith("+") and not ln.startswith("+++"):
            if "parametrize" in ln or "pytest.param" in ln:
                # Anchor the parametrize block to the original-file line where
                # the hunk started (i.e. where the deletions happen). This lets
                # us associate it with nearby deleted tests.
                per_file_param_lines.setdefault(cur, []).append(orig_line)
            new_line += 1
        else:
            # context line
            orig_line += 1
            new_line += 1
    return per_file_deleted, per_file_param_lines


def cluster_deletions(
    deletions: list[tuple[str, int]],
    param_lines: list[int],
    gap: int = CLUSTER_GAP_LINES,
) -> list[list[str]]:
    """Group deleted tests into clusters by line proximity in the original file.

    Two deletions are in the same cluster iff their original-file lines are
    within `gap` of each other (transitively). A cluster is kept only if at
    least one parametrize block added in the diff is within `gap` lines of
    a deletion in the cluster — otherwise the deletions might not be a fold
    (could be a rename / pure removal).
    """
    if not deletions:
        return []
    sorted_dels = sorted(deletions, key=lambda x: x[1])
    clusters: list[list[tuple[str, int]]] = [[sorted_dels[0]]]
    for name, line in sorted_dels[1:]:
        if line - clusters[-1][-1][1] <= gap:
            clusters[-1].append((name, line))
        else:
            clusters.append([(name, line)])

    # Filter: cluster must have a parametrize anchor nearby AND >=2 deletions
    out: list[list[str]] = []
    for cl in clusters:
        if len(cl) < 2:
            continue
        cl_lines = [ln for _, ln in cl]
        cl_min, cl_max = min(cl_lines), max(cl_lines)
        has_anchor = any(cl_min - gap <= pl <= cl_max + gap for pl in param_lines)
        if has_anchor:
            out.append([name for name, _ in cl])
    return out


def get_test_node(content: str, name: str) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node  # type: ignore[return-value]
    return None


def extract_real_dups() -> list[dict[str, str]]:
    """Tests deleted in fold commits = real duplicates (per the human judge).

    Each deleted test gets a `cluster_id` of the form `<sha7>:<idx>` so the
    pair-level evaluator can distinguish multiple folds within a single
    file/commit (e.g. one commit folding both a BlockingIO cluster and an
    AntiMirror cluster in the same file).
    """
    cases: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for sha, msg in list_dedup_commits():
        try:
            per_file_del, per_file_param_lines = parse_diff_deletions(sha)
        except subprocess.CalledProcessError:
            continue
        if not per_file_del:
            continue
        try:
            parent = git("rev-parse", f"{sha}^").strip()
        except subprocess.CalledProcessError:
            continue
        for fpath, deletions in per_file_del.items():
            param_lines = per_file_param_lines.get(fpath, [])
            # File-removed fallback: whole-file deletion → single cluster
            try:
                git("show", f"{sha}:{fpath}")
                file_still_exists = True
            except subprocess.CalledProcessError:
                file_still_exists = False

            if not file_still_exists and len(deletions) <= 3:
                clusters = [[name for name, _ in deletions]]
            elif param_lines:
                clusters = cluster_deletions(deletions, param_lines)
            else:
                clusters = []
            if not clusters:
                continue

            try:
                content = git("show", f"{parent}:{fpath}")
            except subprocess.CalledProcessError:
                continue

            for cluster_idx, cluster_tests in enumerate(clusters):
                cluster_id = f"{sha[:7]}:{cluster_idx}"
                for test_name in cluster_tests:
                    if get_test_node(content, test_name) is None:
                        continue
                    key = (parent, fpath, test_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    cases.append(
                        {
                            "verdict": "real_dup",
                            "source": f"git_commit:{sha[:7]}",
                            "rationale": msg[:80],
                            "repo": REPO_ROOT.name,
                            "commit": parent,
                            "file": fpath,
                            "test": test_name,
                            "cluster_id": cluster_id,
                        }
                    )
    return cases


def get_clusters_at(sha: str) -> set[tuple[str, str]]:
    """Run audit at a given commit, return {(file, test)} in any cluster."""
    res = subprocess.run(
        ["git", "archive", sha, "packages/axm-audit"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if res.returncode != 0:
        return set()
    tmp = tempfile.mkdtemp(prefix="axm_corpus_")
    try:
        with tarfile.open(fileobj=io.BytesIO(res.stdout)) as tar:
            tar.extractall(tmp)
        # Lazy import to avoid loading until needed
        from axm_audit.core.auditor import audit_project

        result = audit_project(
            Path(tmp) / "packages" / "axm-audit", category="test_quality"
        )
        for check in result.checks:
            if "Duplicate" in check.__class__.__name__:
                clusters = check.model_dump()["metadata"]["clusters"]
                return {(t["file"], t["name"]) for c in clusters for t in c["members"]}
    except Exception:
        return set()
    return set()


def extract_false_positives() -> list[dict[str, str]]:
    """Tests in clusters before AND after a dedup commit that touched their file
    = examined-and-not-folded by the human judge.
    """
    cases: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for sha, msg in list_dedup_commits():
        try:
            files_changed = (
                git("show", "--name-only", "--pretty=", sha).strip().splitlines()
            )
        except subprocess.CalledProcessError:
            continue
        files_changed = {
            f.replace("packages/axm-audit/", "")
            for f in files_changed
            if f.endswith(".py") and "test" in f
        }
        if not files_changed:
            continue
        try:
            parent = git("rev-parse", f"{sha}^").strip()
        except subprocess.CalledProcessError:
            continue

        before = get_clusters_at(parent)
        after = get_clusters_at(sha)
        if not before or not after:
            continue
        survivors = before & after
        for fpath, test in survivors:
            # Match against files actually touched by this commit (path may have prefix differences)
            if not any(
                touched.endswith(fpath) or fpath.endswith(touched)
                for touched in files_changed
            ):
                continue
            # Normalize file path to be repo-relative (workspace-relative) like real_dup entries
            full_fpath = f"packages/axm-audit/{fpath}"
            key = (parent, full_fpath, test)
            if key in seen:
                continue
            seen.add(key)
            cases.append(
                {
                    "verdict": "false_positive",
                    "source": f"git_commit_survivor:{sha[:7]}",
                    "rationale": f"Survived dedup pass: {msg[:80]}",
                    "repo": REPO_ROOT.name,
                    "commit": parent,
                    "file": full_fpath,
                    "test": test,
                }
            )
    return cases


def main() -> None:
    print("Extracting real_dup cases (deleted in fold commits)…")
    real_cases = extract_real_dups()
    print(f"  → {len(real_cases)} real_dup cases")

    print("Extracting false_positive cases (survivors of dedup commits)…")
    fp_cases = extract_false_positives()
    print(f"  → {len(fp_cases)} false_positive cases")

    all_cases = real_cases + fp_cases
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(json.dumps(all_cases, indent=2))
    print(f"\nWrote {len(all_cases)} cases to {CORPUS_PATH}")


if __name__ == "__main__":
    main()
