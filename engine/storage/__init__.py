"""
Storage module for Gen-D.

This module provides SQLite-based persistence for storing and retrieving
node snapshots, enabling drift detection across scans.
"""

from engine.storage.database import (
    Database,
    init_database,
    save_snapshot,
    load_snapshots,
    get_scan_history,
)

__all__ = [
    "Database",
    "init_database",
    "save_snapshot",
    "load_snapshots",
    "get_scan_history",
]
