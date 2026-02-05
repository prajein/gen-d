"""
Tests for the drift detection module.

Tests drift classification rules and report generation.
"""

import pytest
from engine.drift import DriftDetector, detect_node_drift, analyze_codebase_drift
from engine.models import CodeNode, DriftStatus, NodeSnapshot, DriftReport


class TestDriftClassification:
    """Tests for the drift classification rules."""

    def test_undocumented_when_no_docstring(self):
        """Test that nodes without docstrings are UNDOCUMENTED."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="abc123",
            doc_hash=None,
            docstring=None,
        )

        status = detect_node_drift(node, stored=None)
        assert status == DriftStatus.UNDOCUMENTED

    def test_fresh_when_new_node(self):
        """Test that new nodes with docstrings are FRESH."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="abc123",
            doc_hash="doc456",
            docstring="A docstring.",
        )

        # No stored snapshot = new node
        status = detect_node_drift(node, stored=None)
        assert status == DriftStatus.FRESH

    def test_fresh_when_hash_unchanged(self):
        """Test that nodes with unchanged semantic hash are FRESH."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="abc123",
            doc_hash="doc456",
            docstring="A docstring.",
        )

        snapshot = NodeSnapshot(
            node_id="mod:func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="abc123",  # Same hash
            doc_hash="doc456",
        )

        status = detect_node_drift(node, snapshot)
        assert status == DriftStatus.FRESH

    def test_fresh_when_docs_updated(self):
        """Test that FRESH when docs were updated after code change."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="new_hash",  # Code changed
            doc_hash="new_doc",  # Docs also changed
            docstring="Updated docstring.",
        )

        snapshot = NodeSnapshot(
            node_id="mod:func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="old_hash",
            doc_hash="old_doc",
        )

        status = detect_node_drift(node, snapshot)
        assert status == DriftStatus.FRESH

    def test_stale_when_code_changed_docs_same(self):
        """Test that STALE when code changed but docs didn't."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="new_hash",  # Code changed
            doc_hash="same_doc",  # Same doc hash
            docstring="Original docstring.",
        )

        snapshot = NodeSnapshot(
            node_id="mod:func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="old_hash",  # Different from current
            doc_hash="same_doc",  # Same as current
        )

        status = detect_node_drift(node, snapshot)
        assert status == DriftStatus.STALE


class TestDriftDetector:
    """Tests for the DriftDetector class."""

    def test_detect_all_updates_status(self):
        """Test that detect_all returns nodes with updated status."""
        nodes = [
            CodeNode(
                id=f"mod:func{i}",
                name=f"func{i}",
                file_path="mod.py",
                start_line=i * 10,
                end_line=i * 10 + 5,
                semantic_hash=f"hash{i}",
                docstring=f"Doc {i}" if i % 2 == 0 else None,
                doc_hash=f"dochash{i}" if i % 2 == 0 else None,
            )
            for i in range(4)
        ]

        detector = DriftDetector()
        updated = detector.detect_all(nodes)

        assert len(updated) == 4

        # Check statuses
        documented = [n for n in updated if n.docstring is not None]
        undocumented = [n for n in updated if n.docstring is None]

        for node in documented:
            assert node.drift_status == DriftStatus.FRESH
        for node in undocumented:
            assert node.drift_status == DriftStatus.UNDOCUMENTED

    def test_explain_provides_details(self):
        """Test that explain provides useful information."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="new_hash",
            doc_hash="same_doc",
            docstring="The docstring.",
        )

        snapshot = NodeSnapshot(
            node_id="mod:func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="old_hash",
            doc_hash="same_doc",
        )

        detector = DriftDetector({node.id: snapshot})
        explanation = detector.explain(node)

        assert explanation.current_status == DriftStatus.STALE
        assert "changed" in explanation.reason.lower()
        assert len(explanation.suggestions) > 0


class TestDriftReport:
    """Tests for drift report generation."""

    def test_analyze_codebase_drift(self):
        """Test report generation for a codebase."""
        nodes = [
            # Fresh node
            CodeNode(
                id="mod:fresh",
                name="fresh",
                file_path="mod.py",
                start_line=1,
                end_line=5,
                semantic_hash="same",
                doc_hash="doc1",
                docstring="Doc.",
            ),
            # Stale node
            CodeNode(
                id="mod:stale",
                name="stale",
                file_path="mod.py",
                start_line=6,
                end_line=10,
                semantic_hash="new",
                doc_hash="doc2",
                docstring="Doc.",
            ),
            # Undocumented node
            CodeNode(
                id="mod:undoc",
                name="undoc",
                file_path="mod.py",
                start_line=11,
                end_line=15,
                semantic_hash="hash3",
                doc_hash=None,
                docstring=None,
            ),
        ]

        snapshots = {
            "mod:fresh": NodeSnapshot(
                node_id="mod:fresh",
                file_path="mod.py",
                start_line=1,
                end_line=5,
                semantic_hash="same",  # Unchanged
                doc_hash="doc1",
            ),
            "mod:stale": NodeSnapshot(
                node_id="mod:stale",
                file_path="mod.py",
                start_line=6,
                end_line=10,
                semantic_hash="old",  # Changed
                doc_hash="doc2",  # Same doc
            ),
        }

        report = analyze_codebase_drift(nodes, snapshots)

        assert report.fresh_count == 1
        assert report.stale_count == 1
        assert report.undocumented_count == 1
        assert report.total_nodes == 3
        assert "mod:stale" in report.stale_nodes
        assert "mod:undoc" in report.undocumented_nodes

    def test_report_percentages(self):
        """Test report percentage calculations."""
        report = DriftReport(
            fresh_count=7,
            stale_count=2,
            undocumented_count=1,
        )

        assert report.total_nodes == 10
        assert report.documented_percentage == 90.0  # 9/10
        assert report.fresh_percentage == pytest.approx(77.78, rel=0.01)  # 7/9

    def test_empty_report(self):
        """Test report with no nodes."""
        report = DriftReport()

        assert report.total_nodes == 0
        assert report.documented_percentage == 0.0
        assert report.fresh_percentage == 0.0
