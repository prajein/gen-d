"""
Graph module for Gen-D.

This module provides NetworkX-based graph construction and management
for representing function-level dependencies in Python codebases.
"""

from engine.graph.builder import (
    CodeGraph,
    build_graph_from_source,
    build_graph_from_directory,
)

__all__ = [
    "CodeGraph",
    "build_graph_from_source",
    "build_graph_from_directory",
]
