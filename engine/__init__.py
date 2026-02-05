"""
Gen-D Engine

Core engine for parsing Python code, building dependency graphs,
computing semantic hashes, and detecting documentation drift.
"""

from engine.models import CodeNode, CallEdge, DriftStatus

__all__ = ["CodeNode", "CallEdge", "DriftStatus"]
__version__ = "0.1.0"
