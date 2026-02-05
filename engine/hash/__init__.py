"""
Hash module for Gen-D.

This module provides semantic hashing functionality that computes
stable hashes of function logic, ignoring formatting and documentation.
"""

from engine.hash.semantic_hash import (
    compute_semantic_hash,
    compute_doc_hash,
    normalize_function_code,
    DocstringRemover,
)

__all__ = [
    "compute_semantic_hash",
    "compute_doc_hash",
    "normalize_function_code",
    "DocstringRemover",
]
