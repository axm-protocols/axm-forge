"""Single source of truth for serializing an audit's ``score`` and ``grade``.

The machine-facing ``audit --json`` surface carries a numeric ``score`` (and the
matching ``grade``) whenever a score can be *derived* from at least one measured
scored-category check. When ``AuditResult.quality_score`` is ``None`` the score
is genuinely **not-applicable** — either no scored-category check ran at all, or
every scored-category check came back not-applicable (``score=None``, dropped by
:func:`~axm_audit.models.results.collect_category_scores`). Rather than assume a
misleading 0/F for that case, serialization signals N/A: the strict surface
fails loud via :class:`ScoreIncalculableError` (CLI ``--json`` exits non-zero)
and the tolerant surface returns ``(None, None)``.

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
    "ScoreIncalculableError",
    "resolve_score_grade",
    "score_grade_or_none",
]


class ScoreIncalculableError(RuntimeError):
    """Raised when an audit yields no measurable scored signal (N/A).

    Covers both an audit with no scored-category check at all and one whose
    scored-category checks are every one not-applicable (``score=None``).
    Signals that a success payload without a ``score`` must NOT be emitted; the
    strict callers (``audit --json``) fail loud instead of dropping the key
    silently or reporting a misleading 0/F.
    """


def _has_scored_signal(result: AuditResult) -> bool:
    """True if any check belongs to a scored category (measured or not)."""
    return any(check.category in SCORED_CATEGORIES for check in result.checks)


def resolve_score_grade(result: AuditResult) -> tuple[float, str]:
    """Return ``(score, grade)`` as numbers, or raise if genuinely N/A.

    Single source of truth for score/grade serialization:

    - a computed :attr:`AuditResult.quality_score` is returned verbatim with
      its matching grade;
    - when :attr:`AuditResult.quality_score` is ``None`` the score is
      not-applicable — either no scored-category check ran, or every one came
      back not-applicable (``score=None``, dropped by
      :func:`~axm_audit.models.results.collect_category_scores`). Both resolve
      to N/A (never an assumed 0/F): :class:`ScoreIncalculableError` is raised,
      so the tolerant surface can surface N/A and the strict surface fails loud.

    N/A is driven entirely off :attr:`AuditResult.quality_score` being ``None``
    (which already normalises over the *present* scored categories), so the
    project level and the category level cannot drift apart.
    """
    score = result.quality_score
    if score is not None:
        return score, grade_for_score(score)
    if _has_scored_signal(result):
        raise ScoreIncalculableError(
            "quality score is not-applicable: every scored-category check was "
            "not-applicable (score=None); nothing to average"
        )
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
