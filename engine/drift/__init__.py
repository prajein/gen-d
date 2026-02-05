"""
Drift detection module for Gen-D.

This module provides logic to detect documentation drift by comparing
current code semantics against stored snapshots.
"""

from engine.drift.detector import (
    DriftDetector,
    detect_node_drift,
    analyze_codebase_drift,
)

__all__ = [
    "DriftDetector",
    "detect_node_drift",
    "analyze_codebase_drift",
]
