"""Unit tests for axm_audit.core.fix.pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.fix import pipeline
from axm_audit.core.fix.models import FileOp, PipelineReport

_ROOT = Path("/nonexistent-axm-audit-pipeline-root")

# name -> list of (args, kwargs) recorded each time the patched collaborator ran.
type CallLog = dict[str, list[tuple[tuple[Any, ...], dict[str, Any]]]]


def _op(kind: str, rationale: str = "r") -> FileOp:
    return FileOp(
        kind=kind,
        source=_ROOT / "tests/integration/test_x.py",
        target=_ROOT / "tests/unit/test_x.py",
        rationale=rationale,
        source_rule="X",
    )


@pytest.fixture
def neutralized(monkeypatch: pytest.MonkeyPatch) -> CallLog:
    """Replace every pipeline collaborator with an inert no-op recorder."""
    calls: CallLog = {}

    def _rec(name: str, ret: Any) -> Callable[..., Any]:
        calls.setdefault(name, [])

        def _fn(*args: Any, **kwargs: Any) -> Any:
            calls[name].append((args, kwargs))
            return ret

        return _fn

    monkeypatch.setattr(pipeline, "plan_relocate", _rec("plan_relocate", []))
    monkeypatch.setattr(pipeline, "plan_flatten", _rec("plan_flatten", []))
    monkeypatch.setattr(pipeline, "plan_naming", _rec("plan_naming", ([], [], [])))
    monkeypatch.setattr(
        pipeline, "relocate_non_canonical_tiers", _rec("relocate_nc", [])
    )
    monkeypatch.setattr(pipeline, "flatten_tier_layout", _rec("flatten_layout", []))
    monkeypatch.setattr(pipeline, "execute", _rec("execute", []))
    monkeypatch.setattr(pipeline, "invalidate_import_index", _rec("invalidate", None))
    monkeypatch.setattr(pipeline, "_extract_shared_helpers", _rec("extract", []))
    monkeypatch.setattr(pipeline, "_ruff_format_tests", _rec("ruff_format", []))
    monkeypatch.setattr(pipeline, "collect_unfixable", _rec("unfixable", []))
    return calls


def test_run_default_dryrun_report_is_empty_and_unapplied(
    neutralized: CallLog,
) -> None:
    """run() with no args yields an empty, unapplied dry-run report."""
    report = pipeline.run(_ROOT)
    assert isinstance(report, PipelineReport)
    assert report.applied is False
    assert report.ops == []
    assert report.iterations == 1


def test_run_default_rules_drives_relocate_planner(
    neutralized: CallLog,
) -> None:
    """rules=None falls back to DEFAULT_RULES, exercising the pyramid planner."""
    pipeline.run(_ROOT, apply=True, rules=None)
    assert neutralized["plan_relocate"], "PYRAMID rule should invoke plan_relocate"


def test_run_dryrun_sets_applied_false(neutralized: CallLog) -> None:
    """apply=False marks the report as not applied."""
    report = pipeline.run(_ROOT, apply=False)
    assert report.applied is False


def test_run_apply_sets_applied_true(neutralized: CallLog) -> None:
    """apply=True marks the report as applied."""
    report = pipeline.run(_ROOT, apply=True)
    assert report.applied is True


def test_run_dryrun_runs_single_iteration(neutralized: CallLog) -> None:
    """Dry-run performs exactly one pass (no mutation to converge on)."""
    report = pipeline.run(_ROOT, apply=False)
    assert report.iterations == 1


def test_run_dryrun_skips_apply_only_collaborators(
    neutralized: CallLog,
) -> None:
    """Dry-run never invokes execute() nor the post-polish extractor."""
    pipeline.run(_ROOT, apply=False)
    assert neutralized["execute"] == []
    assert neutralized["extract"] == []


def test_run_apply_invokes_post_polish(neutralized: CallLog) -> None:
    """apply=True runs the helper-extraction + ruff-format polish stage."""
    pipeline.run(_ROOT, apply=True)
    assert neutralized["extract"]
    assert neutralized["ruff_format"]


def test_run_converges_when_no_ops_planned(
    neutralized: CallLog,
) -> None:
    """With every planner empty, the apply loop converges after one iteration."""
    report = pipeline.run(_ROOT, apply=True)
    assert report.iterations == 1


def test_run_apply_loop_caps_at_max_iterations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A planner that never empties forces the loop to the MAX_ITERATIONS cap."""
    monkeypatch.setattr(pipeline, "plan_relocate", lambda _p: [_op("relocate")])
    monkeypatch.setattr(pipeline, "plan_flatten", lambda _p: [])
    monkeypatch.setattr(pipeline, "plan_naming", lambda _p: ([], [], []))
    monkeypatch.setattr(pipeline, "relocate_non_canonical_tiers", lambda _p: [])
    monkeypatch.setattr(pipeline, "flatten_tier_layout", lambda _p: [])
    monkeypatch.setattr(pipeline, "execute", lambda _o, _p: [])
    monkeypatch.setattr(pipeline, "invalidate_import_index", lambda _p: None)
    monkeypatch.setattr(pipeline, "_extract_shared_helpers", lambda _p: [])
    monkeypatch.setattr(pipeline, "_ruff_format_tests", lambda _p: [])
    monkeypatch.setattr(pipeline, "collect_unfixable", lambda _p: [])
    report = pipeline.run(_ROOT, apply=True)
    assert report.iterations == pipeline.MAX_ITERATIONS


def test_run_records_relocate_ops_in_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planned relocate ops accumulate into report.ops in dry-run mode."""
    monkeypatch.setattr(
        pipeline, "plan_relocate", lambda _p: [_op("relocate"), _op("relocate")]
    )
    monkeypatch.setattr(pipeline, "plan_flatten", lambda _p: [])
    monkeypatch.setattr(pipeline, "plan_naming", lambda _p: ([], [], []))
    monkeypatch.setattr(pipeline, "collect_unfixable", lambda _p: [])
    report = pipeline.run(_ROOT, apply=False)
    assert report.by_kind() == {"relocate": 2}


def test_run_propagates_unfixable_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collect_unfixable output lands verbatim on report.unfixable."""
    sentinel = [{"rule": "TEST_QUALITY_NO_PACKAGE_SYMBOL"}]
    monkeypatch.setattr(pipeline, "plan_relocate", lambda _p: [])
    monkeypatch.setattr(pipeline, "plan_flatten", lambda _p: [])
    monkeypatch.setattr(pipeline, "plan_naming", lambda _p: ([], [], []))
    monkeypatch.setattr(pipeline, "collect_unfixable", lambda _p: sentinel)
    report = pipeline.run(_ROOT, apply=False)
    assert report.unfixable == sentinel


def test_run_flatten_drops_pathological_ops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATHOLOGICAL flatten ops are filtered out and never reach the report."""
    good = _op("flatten", rationale="actionable")
    bad = _op("flatten", rationale="PATHOLOGICAL: cannot split")
    monkeypatch.setattr(pipeline, "plan_relocate", lambda _p: [])
    monkeypatch.setattr(pipeline, "plan_flatten", lambda _p: [good, bad])
    monkeypatch.setattr(pipeline, "plan_naming", lambda _p: ([], [], []))
    monkeypatch.setattr(pipeline, "collect_unfixable", lambda _p: [])
    report = pipeline.run(_ROOT, apply=False)
    assert report.by_kind() == {"flatten": 1}


def test_default_rules_membership() -> None:
    """DEFAULT_RULES holds the two deterministic tier/naming rule ids."""
    assert pipeline.DEFAULT_RULES == frozenset(
        {"TEST_QUALITY_PYRAMID_LEVEL", "TEST_QUALITY_FILE_NAMING"}
    )


def test_max_iterations_constant() -> None:
    """MAX_ITERATIONS is the documented fixed-point cap of 6."""
    assert pipeline.MAX_ITERATIONS == 6
