"""
Tests for the storage module.

Tests SQLite persistence operations.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from engine.storage import Database, init_database
from engine.models import CodeNode, CallEdge, NodeSnapshot, DriftStatus


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        yield db


class TestDatabaseBasics:
    """Tests for basic database operations."""

    def test_init_creates_schema(self, temp_db):
        """Test that initialization creates the required tables."""
        # If we can get counts, the tables exist
        assert temp_db.get_node_count() == 0
        assert temp_db.get_edge_count() == 0

    def test_save_and_load_node(self, temp_db):
        """Test saving and loading a single node."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="abc123",
            doc_hash="doc456",
        )

        temp_db.save_nodes([node])

        snapshots = temp_db.load_snapshots()
        assert "mod:func" in snapshots

        snapshot = snapshots["mod:func"]
        assert snapshot.semantic_hash == "abc123"
        assert snapshot.doc_hash == "doc456"

    def test_save_multiple_nodes(self, temp_db):
        """Test saving multiple nodes."""
        nodes = [
            CodeNode(
                id=f"mod:func{i}",
                name=f"func{i}",
                file_path="mod.py",
                start_line=i * 10,
                end_line=i * 10 + 5,
                semantic_hash=f"hash{i}",
            )
            for i in range(5)
        ]

        temp_db.save_nodes(nodes)

        assert temp_db.get_node_count() == 5

    def test_update_existing_node(self, temp_db):
        """Test that saving updates existing nodes."""
        node_v1 = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="old_hash",
        )
        temp_db.save_nodes([node_v1])

        node_v2 = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="new_hash",
        )
        temp_db.save_nodes([node_v2])

        # Should still be 1 node
        assert temp_db.get_node_count() == 1

        snapshot = temp_db.load_snapshot("mod:func")
        assert snapshot.semantic_hash == "new_hash"

    def test_load_single_snapshot(self, temp_db):
        """Test loading a specific snapshot by ID."""
        node = CodeNode(
            id="mod:target",
            name="target",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="hash",
        )
        temp_db.save_nodes([node])

        snapshot = temp_db.load_snapshot("mod:target")
        assert snapshot is not None
        assert snapshot.node_id == "mod:target"

        missing = temp_db.load_snapshot("nonexistent")
        assert missing is None


class TestEdgePersistence:
    """Tests for edge storage."""

    def test_save_and_count_edges(self, temp_db):
        """Test saving call edges."""
        edges = [
            CallEdge("mod:a", "mod:b", call_line=5),
            CallEdge("mod:a", "mod:c", call_line=6),
            CallEdge("mod:b", "mod:c", call_line=10),
        ]

        temp_db.save_edges(edges)

        assert temp_db.get_edge_count() == 3


class TestScanHistory:
    """Tests for scan history tracking."""

    def test_record_scan(self, temp_db):
        """Test recording a scan."""
        scan_id = temp_db.record_scan(
            directory="/path/to/project",
            files_scanned=10,
            nodes_found=50,
            errors=2,
        )

        assert scan_id is not None
        assert len(scan_id) > 0

    def test_get_scan_history(self, temp_db):
        """Test retrieving scan history."""
        # Record multiple scans
        for i in range(3):
            temp_db.record_scan(
                directory=f"/project{i}",
                files_scanned=i * 5,
                nodes_found=i * 10,
                errors=i,
            )

        history = temp_db.get_scan_history(limit=10)

        assert len(history) == 3
        # Most recent first
        assert history[0].directory == "/project2"

    def test_scan_history_limit(self, temp_db):
        """Test that history limit works."""
        for i in range(10):
            temp_db.record_scan(
                directory=f"/project{i}",
                files_scanned=i,
                nodes_found=i * 2,
                errors=0,
            )

        history = temp_db.get_scan_history(limit=3)
        assert len(history) == 3


class TestDatabaseCleanup:
    """Tests for cleanup operations."""

    def test_clear_database(self, temp_db):
        """Test clearing all data."""
        node = CodeNode(
            id="mod:func",
            name="func",
            file_path="mod.py",
            start_line=1,
            end_line=5,
            semantic_hash="hash",
        )
        temp_db.save_nodes([node])
        temp_db.record_scan("/project", 1, 1, 0)

        assert temp_db.get_node_count() == 1

        temp_db.clear()

        assert temp_db.get_node_count() == 0
        assert temp_db.get_edge_count() == 0
        assert len(temp_db.get_scan_history()) == 0

    def test_delete_file_nodes(self, temp_db):
        """Test deleting nodes from a specific file."""
        nodes = [
            CodeNode(
                id="file1:func1",
                name="func1",
                file_path="file1.py",
                start_line=1,
                end_line=5,
                semantic_hash="hash1",
            ),
            CodeNode(
                id="file1:func2",
                name="func2",
                file_path="file1.py",
                start_line=6,
                end_line=10,
                semantic_hash="hash2",
            ),
            CodeNode(
                id="file2:func1",
                name="func1",
                file_path="file2.py",
                start_line=1,
                end_line=5,
                semantic_hash="hash3",
            ),
        ]
        temp_db.save_nodes(nodes)

        assert temp_db.get_node_count() == 3

        deleted = temp_db.delete_file_nodes("file1.py")

        assert deleted == 2
        assert temp_db.get_node_count() == 1


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_init_database(self):
        """Test the init_database convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_database(db_path)

            assert isinstance(db, Database)
            assert db.get_node_count() == 0
