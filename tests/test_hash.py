"""
Tests for the semantic hashing module.

Tests hash stability, normalization, and semantic equivalence.
"""

import pytest
from engine.hash import (
    compute_semantic_hash,
    compute_doc_hash,
    normalize_function_code,
    DocstringRemover,
)
from tests.fixtures import (
    SEMANTICALLY_EQUIVALENT_1,
    SEMANTICALLY_EQUIVALENT_2,
    SEMANTICALLY_DIFFERENT,
)


class TestSemanticHashStability:
    """Tests for hash stability across non-behavioral changes."""

    def test_hash_ignores_whitespace(self):
        """Test that whitespace changes don't affect the hash."""
        code1 = "def f():\n    return 1"
        code2 = "def f():\n\n    return 1"  # extra blank line

        hash1 = compute_semantic_hash(code1)
        hash2 = compute_semantic_hash(code2)

        assert hash1 == hash2

    def test_hash_ignores_comments(self):
        """Test that comments don't affect the hash."""
        code1 = """
def add(a, b):
    return a + b
"""
        code2 = """
def add(a, b):
    # Add the numbers together
    return a + b  # return the sum
"""
        hash1 = compute_semantic_hash(code1)
        hash2 = compute_semantic_hash(code2)

        assert hash1 == hash2

    def test_hash_ignores_docstrings(self):
        """Test that docstring changes don't affect the hash."""
        hash1 = compute_semantic_hash(SEMANTICALLY_EQUIVALENT_1)
        hash2 = compute_semantic_hash(SEMANTICALLY_EQUIVALENT_2)

        assert hash1 == hash2

    def test_hash_changes_with_logic(self):
        """Test that logic changes do affect the hash."""
        hash1 = compute_semantic_hash(SEMANTICALLY_EQUIVALENT_1)
        hash2 = compute_semantic_hash(SEMANTICALLY_DIFFERENT)

        assert hash1 != hash2

    def test_hash_deterministic(self):
        """Test that the same code always produces the same hash."""
        code = "def f(x):\n    return x * 2"

        hashes = [compute_semantic_hash(code) for _ in range(10)]

        assert len(set(hashes)) == 1

    def test_hash_format(self):
        """Test that the hash is a valid SHA-256 hex string."""
        code = "def f(): pass"
        hash_value = compute_semantic_hash(code)

        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestDocstringRemoval:
    """Tests for the DocstringRemover transformer."""

    def test_removes_function_docstring(self):
        """Test that function docstrings are removed."""
        code = '''
def greet(name):
    """Say hello."""
    return f"Hello, {name}"
'''
        normalized = normalize_function_code(code)

        assert '"""Say hello."""' not in normalized
        assert "Hello" in normalized  # f-string is preserved

    def test_removes_class_docstring(self):
        """Test that class docstrings are removed."""
        code = '''
class MyClass:
    """A class docstring."""

    def method(self):
        """Method docstring."""
        pass
'''
        normalized = normalize_function_code(code)

        assert "A class docstring" not in normalized
        assert "Method docstring" not in normalized

    def test_preserves_non_docstring_strings(self):
        """Test that regular strings are preserved."""
        code = '''
def func():
    message = "Hello, World!"
    return message
'''
        normalized = normalize_function_code(code)

        assert "Hello, World!" in normalized

    def test_handles_empty_function_after_docstring_removal(self):
        """Test that functions with only docstrings become pass statements."""
        code = '''
def documented_only():
    """This function only has a docstring."""
'''
        normalized = normalize_function_code(code)

        assert "pass" in normalized


class TestDocHash:
    """Tests for docstring hashing."""

    def test_doc_hash_strips_whitespace(self):
        """Test that leading/trailing whitespace is ignored."""
        hash1 = compute_doc_hash("Hello, World!")
        hash2 = compute_doc_hash("  Hello, World!  ")

        assert hash1 == hash2

    def test_doc_hash_deterministic(self):
        """Test that docstring hashing is deterministic."""
        docstring = "This is a docstring."
        hashes = [compute_doc_hash(docstring) for _ in range(10)]

        assert len(set(hashes)) == 1

    def test_doc_hash_differs_for_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = compute_doc_hash("First docstring")
        hash2 = compute_doc_hash("Second docstring")

        assert hash1 != hash2

    def test_doc_hash_format(self):
        """Test that the doc hash is a valid SHA-256 hex string."""
        hash_value = compute_doc_hash("Test")

        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_function(self):
        """Test hashing an empty function."""
        code = "def f(): pass"
        hash_value = compute_semantic_hash(code)

        assert len(hash_value) == 64

    def test_complex_expressions(self):
        """Test hashing complex expressions."""
        code = '''
def complex():
    result = [x**2 for x in range(10) if x % 2 == 0]
    mapping = {k: v for k, v in zip("abc", [1, 2, 3])}
    return result, mapping
'''
        hash_value = compute_semantic_hash(code)
        assert len(hash_value) == 64

    def test_nested_functions_all_hashed(self):
        """Test that nested function content is included in hash."""
        code1 = '''
def outer():
    def inner():
        return 1
    return inner()
'''
        code2 = '''
def outer():
    def inner():
        return 2
    return inner()
'''
        hash1 = compute_semantic_hash(code1)
        hash2 = compute_semantic_hash(code2)

        assert hash1 != hash2
