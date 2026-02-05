"""
Tests for the graph module.

Tests CodeGraph operations and graph construction.
"""

import pytest
from engine.graph import CodeGraph, build_graph_from_source
from engine.models import CodeNode, CallEdge, DriftStatus


class TestCodeGraph:
    """Tests for the CodeGraph class."""

    def test_add_and_retrieve_node(self):
        """Test adding and retrieving a node."""
        graph = CodeGraph()

        node = CodeNode(
            id="module:func",
            name="func",
            file_path="module.py",
            start_line=1,
            end_line=3,
            semantic_hash="abc123",
            drift_status=DriftStatus.FRESH,
        )

        graph.add_node(node)

        retrieved = graph.get_node("module:func")
        assert retrieved is not None
        assert retrieved.name == "func"
        assert retrieved.semantic_hash == "abc123"

    def test_node_count(self):
        """Test node counting."""
        graph = CodeGraph()

        for i in range(5):
            node = CodeNode(
                id=f"module:func{i}",
                name=f"func{i}",
                file_path="module.py",
                start_line=i * 10,
                end_line=i * 10 + 5,
                semantic_hash=f"hash{i}",
            )
            graph.add_node(node)

        assert graph.node_count == 5

    def test_add_edge(self):
        """Test adding edges between nodes."""
        graph = CodeGraph()

        # Add nodes
        caller = CodeNode(
            id="mod:caller",
            name="caller",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="hash1",
        )
        callee = CodeNode(
            id="mod:callee",
            name="callee",
            file_path="mod.py",
            start_line=6,
            end_line=10,
            semantic_hash="hash2",
        )
        graph.add_node(caller)
        graph.add_node(callee)

        # Add edge
        edge = CallEdge(caller_id="mod:caller", callee_id="mod:callee", call_line=3)
        graph.add_edge(edge)

        assert graph.edge_count == 1

        # Check relationships
        callees = list(graph.get_callees("mod:caller"))
        assert "mod:callee" in callees

        callers = list(graph.get_callers("mod:callee"))
        assert "mod:caller" in callers

    def test_get_nodes_by_status(self):
        """Test filtering nodes by drift status."""
        graph = CodeGraph()

        statuses = [DriftStatus.FRESH, DriftStatus.STALE, DriftStatus.UNDOCUMENTED]
        for i, status in enumerate(statuses):
            node = CodeNode(
                id=f"mod:func{i}",
                name=f"func{i}",
                file_path="mod.py",
                start_line=i * 10,
                end_line=i * 10 + 5,
                semantic_hash=f"hash{i}",
                drift_status=status,
            )
            graph.add_node(node)

        fresh = list(graph.get_nodes_by_status(DriftStatus.FRESH))
        stale = list(graph.get_nodes_by_status(DriftStatus.STALE))
        undoc = list(graph.get_nodes_by_status(DriftStatus.UNDOCUMENTED))

        assert len(fresh) == 1
        assert len(stale) == 1
        assert len(undoc) == 1

    def test_get_nodes_by_file(self):
        """Test getting nodes from a specific file."""
        graph = CodeGraph()

        # Add nodes from different files
        for i in range(3):
            node = CodeNode(
                id=f"file{i // 2}:func{i}",
                name=f"func{i}",
                file_path=f"file{i // 2}.py",
                start_line=i * 10,
                end_line=i * 10 + 5,
                semantic_hash=f"hash{i}",
            )
            graph.add_node(node)

        file0_nodes = list(graph.get_nodes_by_file("file0.py"))
        file1_nodes = list(graph.get_nodes_by_file("file1.py"))

        assert len(file0_nodes) == 2
        assert len(file1_nodes) == 1

    def test_update_node_status(self):
        """Test updating a node's drift status."""
        graph = CodeGraph()

        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="hash",
            drift_status=DriftStatus.FRESH,
        )
        graph.add_node(node)

        # Update status
        graph.update_node_status("mod:func", DriftStatus.STALE)

        updated = graph.get_node("mod:func")
        assert updated.drift_status == DriftStatus.STALE

    def test_clear(self):
        """Test clearing the graph."""
        graph = CodeGraph()

        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="hash",
        )
        graph.add_node(node)
        assert graph.node_count == 1

        graph.clear()
        assert graph.node_count == 0


class TestGraphBuilding:
    """Tests for graph construction from source."""

    def test_build_from_simple_source(self):
        """Test building a graph from simple source code."""
        source = '''
def main():
    """Main entry point."""
    helper()

def helper():
    """A helper function."""
    pass
'''
        graph = build_graph_from_source(source)

        assert graph.node_count == 2

    def test_build_captures_edges(self):
        """Test that call edges are captured."""
        source = '''
def caller():
    callee()

def callee():
    pass
'''
        graph = build_graph_from_source(source)

        assert graph.edge_count >= 1

    def test_build_computes_hashes(self):
        """Test that semantic hashes are computed."""
        source = '''
def func():
    """Docstring."""
    return 42
'''
        graph = build_graph_from_source(source)

        nodes = list(graph.get_all_nodes())
        assert len(nodes) == 1
        assert nodes[0].semantic_hash is not None
        assert len(nodes[0].semantic_hash) == 64

    def test_build_extracts_docstrings(self):
        """Test that docstrings are captured."""
        source = '''
def documented():
    """This is the docstring."""
    pass

def undocumented():
    pass
'''
        graph = build_graph_from_source(source)

        nodes = {n.name: n for n in graph.get_all_nodes()}

        assert nodes["documented"].docstring == "This is the docstring."
        assert nodes["undocumented"].docstring is None
