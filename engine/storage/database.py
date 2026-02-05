"""
SQLite Database Layer for Gen-D

This module provides persistence for node snapshots and scan metadata,
enabling drift detection across multiple scans over time.

Design Decisions:
    - SQLite for zero-config, file-based storage
    - Snapshots are point-in-time copies (not live state)
    - Graph is authoritative in memory; database stores history
    - Simple schema optimized for read-heavy workloads

Schema:
    nodes: Stores snapshot of each function's hashes and location
    edges: Stores call relationships (for future graph persistence)
    scans: Metadata about each scan operation

Academic Context:
    Input: CodeNodes and scan metadata
    Transformation: SQL INSERT/UPDATE operations
    Output: Persisted snapshots for future comparison
    Limitation: No transactional guarantees for partial scans
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
import uuid

from engine.models import CodeNode, NodeSnapshot, CallEdge


# Default database location
DEFAULT_DB_PATH = ".gen-d/gen-d.db"


@dataclass
class ScanRecord:
    """
    Record of a scan operation.

    Attributes:
        scan_id: Unique identifier for this scan
        timestamp: When the scan was performed
        directory: Path that was scanned
        files_scanned: Number of files processed
        nodes_found: Number of functions discovered
        errors: Number of files that failed to parse
    """

    scan_id: str
    timestamp: datetime
    directory: str
    files_scanned: int
    nodes_found: int
    errors: int


class Database:
    """
    SQLite database manager for Gen-D.

    Handles all persistence operations including:
    - Storing and retrieving node snapshots
    - Recording scan metadata
    - Querying historical data

    Usage:
        db = Database("./my-project/.gdg/gen-d.db")
        db.save_nodes(nodes)
        snapshots = db.load_snapshots()
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        """
        Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file.
                     Parent directories will be created if needed.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize the database schema if not exists."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    semantic_hash TEXT NOT NULL,
                    doc_hash TEXT,
                    last_scanned TIMESTAMP NOT NULL,
                    scan_id TEXT
                );

                CREATE TABLE IF NOT EXISTS edges (
                    caller_id TEXT NOT NULL,
                    callee_id TEXT NOT NULL,
                    call_line INTEGER,
                    PRIMARY KEY (caller_id, callee_id)
                );

                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    directory TEXT NOT NULL,
                    files_scanned INTEGER NOT NULL,
                    nodes_found INTEGER NOT NULL,
                    errors INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_file
                    ON nodes(file_path);

                CREATE INDEX IF NOT EXISTS idx_nodes_scan
                    ON nodes(scan_id);

                CREATE INDEX IF NOT EXISTS idx_edges_caller
                    ON edges(caller_id);

                CREATE INDEX IF NOT EXISTS idx_edges_callee
                    ON edges(callee_id);
            """)

    def save_nodes(
        self,
        nodes: list[CodeNode],
        scan_id: Optional[str] = None,
    ) -> None:
        """
        Save node snapshots to the database.

        Existing nodes with the same ID will be updated.

        Args:
            nodes: List of CodeNodes to persist
            scan_id: Optional scan ID to associate with these snapshots
        """
        timestamp = datetime.utcnow().isoformat()

        with self._connection() as conn:
            for node in nodes:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO nodes
                    (node_id, file_path, start_line, end_line,
                     semantic_hash, doc_hash, last_scanned, scan_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.id,
                        node.file_path,
                        node.start_line,
                        node.end_line,
                        node.semantic_hash,
                        node.doc_hash,
                        timestamp,
                        scan_id,
                    ),
                )

    def save_edges(self, edges: list[CallEdge]) -> None:
        """
        Save call edges to the database.

        Existing edges will be replaced.

        Args:
            edges: List of CallEdges to persist
        """
        with self._connection() as conn:
            for edge in edges:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO edges
                    (caller_id, callee_id, call_line)
                    VALUES (?, ?, ?)
                    """,
                    (edge.caller_id, edge.callee_id, edge.call_line),
                )

    def load_snapshots(self) -> dict[str, NodeSnapshot]:
        """
        Load all node snapshots from the database.

        Returns:
            Dictionary mapping node IDs to their snapshots
        """
        snapshots = {}

        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT node_id, file_path, start_line, end_line,
                       semantic_hash, doc_hash, last_scanned
                FROM nodes
                """
            )

            for row in cursor:
                snapshot = NodeSnapshot(
                    node_id=row["node_id"],
                    file_path=row["file_path"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    semantic_hash=row["semantic_hash"],
                    doc_hash=row["doc_hash"],
                    timestamp=datetime.fromisoformat(row["last_scanned"]),
                )
                snapshots[snapshot.node_id] = snapshot

        return snapshots

    def load_snapshot(self, node_id: str) -> Optional[NodeSnapshot]:
        """
        Load a single node snapshot by ID.

        Args:
            node_id: The unique identifier of the node

        Returns:
            The NodeSnapshot if found, None otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT node_id, file_path, start_line, end_line,
                       semantic_hash, doc_hash, last_scanned
                FROM nodes
                WHERE node_id = ?
                """,
                (node_id,),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            return NodeSnapshot(
                node_id=row["node_id"],
                file_path=row["file_path"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                semantic_hash=row["semantic_hash"],
                doc_hash=row["doc_hash"],
                timestamp=datetime.fromisoformat(row["last_scanned"]),
            )

    def record_scan(
        self,
        directory: str,
        files_scanned: int,
        nodes_found: int,
        errors: int,
    ) -> str:
        """
        Record metadata about a scan operation.

        Args:
            directory: Path that was scanned
            files_scanned: Number of files processed
            nodes_found: Number of functions discovered
            errors: Number of files that failed to parse

        Returns:
            The generated scan_id
        """
        scan_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO scans
                (scan_id, timestamp, directory, files_scanned, nodes_found, errors)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (scan_id, timestamp, directory, files_scanned, nodes_found, errors),
            )

        return scan_id

    def get_scan_history(self, limit: int = 10) -> list[ScanRecord]:
        """
        Get recent scan records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of ScanRecords, most recent first
        """
        records = []

        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT scan_id, timestamp, directory,
                       files_scanned, nodes_found, errors
                FROM scans
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

            for row in cursor:
                record = ScanRecord(
                    scan_id=row["scan_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    directory=row["directory"],
                    files_scanned=row["files_scanned"],
                    nodes_found=row["nodes_found"],
                    errors=row["errors"],
                )
                records.append(record)

        return records

    def get_node_count(self) -> int:
        """Get the total number of stored node snapshots."""
        with self._connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM nodes")
            return cursor.fetchone()[0]

    def get_edge_count(self) -> int:
        """Get the total number of stored edges."""
        with self._connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM edges")
            return cursor.fetchone()[0]

    def clear(self) -> None:
        """Delete all data from the database."""
        with self._connection() as conn:
            conn.executescript("""
                DELETE FROM nodes;
                DELETE FROM edges;
                DELETE FROM scans;
            """)

    def delete_file_nodes(self, file_path: str) -> int:
        """
        Delete all nodes from a specific file.

        Useful for incremental updates when a file is re-scanned.

        Args:
            file_path: Path to the file

        Returns:
            Number of nodes deleted
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM nodes WHERE file_path = ?",
                (file_path,),
            )
            return cursor.rowcount


# Module-level convenience functions

def init_database(db_path: str | Path = DEFAULT_DB_PATH) -> Database:
    """
    Initialize and return a database instance.

    Args:
        db_path: Path to the database file

    Returns:
        Configured Database instance
    """
    return Database(db_path)


def save_snapshot(
    db: Database,
    node: CodeNode,
) -> None:
    """
    Save a single node snapshot.

    Args:
        db: Database instance
        node: CodeNode to save
    """
    db.save_nodes([node])


def load_snapshots(db: Database) -> dict[str, NodeSnapshot]:
    """
    Load all snapshots from the database.

    Args:
        db: Database instance

    Returns:
        Dictionary mapping node IDs to snapshots
    """
    return db.load_snapshots()


def get_scan_history(db: Database, limit: int = 10) -> list[ScanRecord]:
    """
    Get recent scan history.

    Args:
        db: Database instance
        limit: Maximum number of records

    Returns:
        List of scan records
    """
    return db.get_scan_history(limit)
