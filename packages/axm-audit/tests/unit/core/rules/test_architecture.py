"""Tests for Architecture Rules — RED phase."""


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

    def test_strips_shared_prefix(self) -> None:
        """Removes common top-level package from all modules."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        result = strip_prefix(["pkg.core.a", "pkg.core.b", "pkg.models.c"])
        assert result == ["core.a", "core.b", "models.c"]

    def test_no_dot_returns_unchanged(self) -> None:
        """Bare module names (no dot) are returned as-is."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        result = strip_prefix(["a", "b"])
        assert result == ["a", "b"]

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        assert strip_prefix([]) == []

    def test_mixed_prefix_returns_unchanged(self) -> None:
        """If modules don't share a prefix, return unchanged."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        result = strip_prefix(["pkg_a.mod", "pkg_b.mod"])
        assert result == ["pkg_a.mod", "pkg_b.mod"]


class TestTarjanSCC:
    """Direct tests for the iterative _tarjan_scc algorithm."""

    def test_tarjan_iterative_simple_cycle(self) -> None:
        """A→B→A graph detects SCC [A, B]."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {"A": {"B"}, "B": {"A"}}
        sccs = tarjan_scc(graph)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A", "B"}

    def test_tarjan_iterative_no_cycle(self) -> None:
        """A→B→C linear chain produces no SCCs."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {"A": {"B"}, "B": {"C"}, "C": set()}
        sccs = tarjan_scc(graph)
        assert sccs == []

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

    def test_tarjan_deep_chain_no_recursion_error(self) -> None:
        """2000-node linear chain completes without RecursionError."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        n = 2000
        graph: dict[str, set[str]] = {}
        for i in range(n):
            graph[f"n{i}"] = {f"n{i + 1}"} if i < n - 1 else set()
        # Should not raise RecursionError
        sccs = tarjan_scc(graph)
        assert sccs == []

    def test_tarjan_self_loop(self) -> None:
        """A→A self-loop is not reported (len=1 filtered)."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {"A": {"A"}}
        sccs = tarjan_scc(graph)
        assert sccs == []

    def test_tarjan_disconnected_nodes(self) -> None:
        """Nodes with no edges produce no SCCs."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph: dict[str, set[str]] = {"A": set(), "B": set(), "C": set()}
        sccs = tarjan_scc(graph)
        assert sccs == []
