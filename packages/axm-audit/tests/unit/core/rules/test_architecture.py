"""Tests for Architecture Rules — RED phase."""

import pytest


class TestCircularImportRuleUnit:
    """Pure tests for CircularImportRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_CIRCULAR."""
        from axm_audit.core.rules.architecture import CircularImportRule

        rule = CircularImportRule()
        assert rule.rule_id == "ARCH_CIRCULAR"


class TestGodClassRuleUnit:
    """Pure tests for GodClassRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_GOD_CLASS."""
        from axm_audit.core.rules.architecture import GodClassRule

        rule = GodClassRule()
        assert rule.rule_id == "ARCH_GOD_CLASS"


class TestCouplingMetricRuleUnit:
    """Pure tests for CouplingMetricRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_COUPLING."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        assert rule.rule_id == "ARCH_COUPLING"


class TestStripPrefix:
    """Tests for _strip_prefix helper."""

    @pytest.mark.parametrize(
        ("modules", "expected"),
        [
            pytest.param(
                ["pkg.core.a", "pkg.core.b", "pkg.models.c"],
                ["core.a", "core.b", "models.c"],
                id="strips_shared_prefix",
            ),
            pytest.param(["a", "b"], ["a", "b"], id="no_dot_returns_unchanged"),
            pytest.param(
                ["pkg_a.mod", "pkg_b.mod"],
                ["pkg_a.mod", "pkg_b.mod"],
                id="mixed_prefix_returns_unchanged",
            ),
        ],
    )
    def test_strip_prefix(self, modules: list[str], expected: list[str]) -> None:
        """strip_prefix removes a shared top-level package only when present."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        assert strip_prefix(modules) == expected

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        assert strip_prefix([]) == []


class TestTarjanSCC:
    """Direct tests for the iterative _tarjan_scc algorithm."""

    def test_tarjan_iterative_simple_cycle(self) -> None:
        """A→B→A graph detects SCC [A, B]."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {"A": {"B"}, "B": {"A"}}
        sccs = tarjan_scc(graph)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A", "B"}

    @pytest.mark.parametrize(
        ("graph", "expected"),
        [
            pytest.param(
                {"A": {"B"}, "B": {"C"}, "C": set()},
                [],
                id="linear_chain_no_cycle",
            ),
            pytest.param(
                {f"n{i}": {f"n{i + 1}"} if i < 1999 else set() for i in range(2000)},
                [],
                id="deep_chain_no_recursion_error",
            ),
            pytest.param({"A": {"A"}}, [], id="self_loop_filtered"),
            pytest.param(
                {"A": set(), "B": set(), "C": set()}, [], id="disconnected_nodes"
            ),
        ],
    )
    def test_tarjan_returns_no_sccs(
        self, graph: dict[str, set[str]], expected: list[list[str]]
    ) -> None:
        """tarjan_scc returns no SCCs for acyclic / self-loop / disconnected graphs."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        assert tarjan_scc(graph) == expected

    def test_tarjan_iterative_multiple_sccs(self) -> None:
        """Two independent cycles both detected."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {
            "A": {"B"},
            "B": {"A"},
            "C": {"D"},
            "D": {"C"},
        }
        sccs = tarjan_scc(graph)
        assert len(sccs) == 2
        scc_sets = [set(scc) for scc in sccs]
        assert {"A", "B"} in scc_sets
        assert {"C", "D"} in scc_sets
