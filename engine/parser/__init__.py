"""
Parser module for Gen-D.

This module provides LibCST-based extraction of functions, methods,
and their call relationships from Python source files.
"""

from engine.parser.extractor import (
    extract_functions_from_file,
    extract_functions_from_source,
    extract_calls_from_source,
    FunctionCollector,
    CallCollector,
)

__all__ = [
    "extract_functions_from_file",
    "extract_functions_from_source",
    "extract_calls_from_source",
    "FunctionCollector",
    "CallCollector",
]
