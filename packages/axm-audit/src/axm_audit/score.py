"""Single source of truth for serializing an audit's ``score`` and ``grade``.

The machine-facing ``audit --json`` surface must ALWAYS carry a numeric
``score`` (and the matching ``grade``) whenever a score can be derived — even
when individual scored metrics come back unmeasured. When *no* scored signal
exists at all the score is genuinely incalculable: rather than silently emit a
payload without a ``score`` key, serialization fails loud via
:class:`ScoreIncalculableError` so the caller (CLI ``--json``) can exit
non-zero with an explicit error.

Every code path that serializes a score/grade pair routes through
:func:`resolve_score_grade` (strict) or :func:`score_grade_or_none` (tolerant),
so the value can never be computed two different ways or dropped silently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_audit.models.results import SCORED_CATEGORIES, grade_for_score

if TYPE_CHECKING:
    from axm_audit.models.results import AuditResult

__all__ = [
    "UNMEASURED_ASSUMED_SCORE",
    "ScoreIncalculableError",
    "resolve_score_grade",
    "score_grade_or_none",
]

# A scored category that ran but produced no measurable metric cannot be
# assumed to pass; it floors to 0 (fail-loud, no masking) — mirroring the
# crash convention in ``models.results.crash_check_result``.
UNMEASURED_ASSUMED_SCORE: float = 0.0


class ScoreIncalculableError(RuntimeError):
    """Raised when an audit carries no scored signal at all.

    Signals that a success payload without a ``score`` must NOT be emitted;
    the strict callers (``audit --json``) fail loud instead of dropping the
    key silently.
    """


def _has_scored_signal(result: AuditResult) -> bool:
    """True if any check belongs to a scored category (measured or not)."""
    return any(check.category in SCORED_CATEGORIES for check in result.checks)


def resolve_score_grade(result: AuditResult) -> tuple[float, str]:
    """Return ``(score, grade)`` as numbers, or raise if incalculable.

    Single source of truth for score/grade serialization:

    - a computed :attr:`AuditResult.quality_score` is returned verbatim with
      its matching grade;
    - when scored categories ran but every metric was unmeasured, the score is
      *assumed* (see :data:`UNMEASURED_ASSUMED_SCORE`) so the payload still
      carries a number instead of dropping ``score``;
    - when no scored signal exists at all the score is genuinely incalculable
      and :class:`ScoreIncalculableError` is raised.
    """
    score = result.quality_score
    if score is not None:
        return score, grade_for_score(score)
    if _has_scored_signal(result):
        return UNMEASURED_ASSUMED_SCORE, grade_for_score(UNMEASURED_ASSUMED_SCORE)
    raise ScoreIncalculableError(
        "quality score is incalculable: the audit produced no scored-category "
        "checks (nothing to score)"
    )


def score_grade_or_none(result: AuditResult) -> tuple[float | None, str | None]:
    """Tolerant variant of :func:`resolve_score_grade`.

    Returns ``(None, None)`` instead of raising for non-strict surfaces
    (agent / test-quality summaries) that may legitimately run over unscored
    categories and must not crash. Still derives from
    :func:`resolve_score_grade` so no surface computes score/grade differently.
    """
    try:
        return resolve_score_grade(result)
    except ScoreIncalculableError:
        return None, None
