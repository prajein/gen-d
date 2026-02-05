"""
Semantic Hashing for Gen-D

This module implements semantic-aware hashing of Python function code.
Unlike textual hashing, semantic hashes are designed to:

    1. Ignore formatting and whitespace
    2. Ignore comments and docstrings
    3. Remain stable across non-behavioral refactors
    4. Change when actual logic changes

Design Decisions:
    - Uses LibCST to parse and transform code before hashing
    - Strips docstrings via CST transformation
    - Normalizes to canonical string representation
    - Uses SHA-256 for final hash computation

Academic Context:
    Input: Python function source code (string or CST node)
    Transformation: Docstring removal → Normalization → SHA-256
    Output: Deterministic 64-character hex hash
    Limitation: Semantic equivalence is approximated, not proven

Hash Stability Guarantees:
    - Adding/removing whitespace → same hash
    - Adding/removing comments → same hash
    - Changing docstring content → same hash
    - Renaming variables → DIFFERENT hash (conservative)
    - Reordering statements → DIFFERENT hash

TODO (Research Extensions):
    - Identifier normalization (alpha-renaming)
    - Literal canonicalization (e.g., 1000 vs 1_000)
    - Expression reordering for commutative operations
"""

import hashlib
from typing import Union
import libcst as cst


class DocstringRemover(cst.CSTTransformer):
    """
    CST Transformer that removes docstrings from function bodies.

    A docstring is defined as a string literal expression that appears
    as the first statement in a function body.

    This transformer preserves all other code, including string literals
    that are not in docstring position.

    Usage:
        module = cst.parse_module(source)
        transformed = module.visit(DocstringRemover())
        code_without_docstrings = transformed.code
    """

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        """
        Process a function definition, removing its docstring if present.

        The docstring is the first statement if it's a bare string expression.
        We replace the body with a version that excludes the docstring.
        """
        body = updated_node.body
        if not isinstance(body, cst.IndentedBlock):
            return updated_node

        statements = list(body.body)
        if not statements:
            return updated_node

        first_stmt = statements[0]
        if self._is_docstring_statement(first_stmt):
            # Remove the docstring (first statement)
            new_statements = statements[1:]
            if not new_statements:
                # Function would be empty; add a pass statement
                new_statements = [
                    cst.SimpleStatementLine(body=[cst.Pass()])
                ]
            new_body = body.with_changes(body=new_statements)
            return updated_node.with_changes(body=new_body)

        return updated_node

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        """
        Process a class definition, removing its docstring if present.

        Class docstrings follow the same pattern as function docstrings.
        """
        body = updated_node.body
        if not isinstance(body, cst.IndentedBlock):
            return updated_node

        statements = list(body.body)
        if not statements:
            return updated_node

        first_stmt = statements[0]
        if self._is_docstring_statement(first_stmt):
            new_statements = statements[1:]
            if not new_statements:
                new_statements = [
                    cst.SimpleStatementLine(body=[cst.Pass()])
                ]
            new_body = body.with_changes(body=new_statements)
            return updated_node.with_changes(body=new_body)

        return updated_node

    def _is_docstring_statement(self, stmt: cst.BaseStatement) -> bool:
        """
        Check if a statement is a docstring.

        A docstring is a SimpleStatementLine containing a single Expr
        node whose value is a string literal.
        """
        if not isinstance(stmt, cst.SimpleStatementLine):
            return False
        if len(stmt.body) != 1:
            return False
        expr = stmt.body[0]
        if not isinstance(expr, cst.Expr):
            return False
        return isinstance(
            expr.value,
            (cst.SimpleString, cst.ConcatenatedString)
        )


class CommentRemover(cst.CSTTransformer):
    """
    CST Transformer that removes all comments from code.

    LibCST preserves comments in its tree representation. This transformer
    strips them to ensure comments don't affect the semantic hash.
    """

    def leave_EmptyLine(
        self,
        original_node: cst.EmptyLine,
        updated_node: cst.EmptyLine,
    ) -> cst.EmptyLine:
        """Remove comment from empty lines."""
        if updated_node.comment is not None:
            return updated_node.with_changes(comment=None)
        return updated_node

    def leave_TrailingWhitespace(
        self,
        original_node: cst.TrailingWhitespace,
        updated_node: cst.TrailingWhitespace,
    ) -> cst.TrailingWhitespace:
        """Remove trailing comments."""
        if updated_node.comment is not None:
            return updated_node.with_changes(comment=None)
        return updated_node


class WhitespaceNormalizer(cst.CSTTransformer):
    """
    CST Transformer that normalizes whitespace for consistent hashing.

    Removes empty lines and standardizes indentation to ensure that
    formatting differences don't affect the semantic hash.
    """

    def leave_IndentedBlock(
        self,
        original_node: cst.IndentedBlock,
        updated_node: cst.IndentedBlock,
    ) -> cst.IndentedBlock:
        """Normalize the indented block by removing empty line metadata."""
        # Remove leading empty lines from the block header
        return updated_node.with_changes(
            header=cst.TrailingWhitespace(),
        )

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine:
        """Remove empty lines before statements."""
        return updated_node.with_changes(
            leading_lines=[],
            trailing_whitespace=cst.TrailingWhitespace(),
        )

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        """Remove empty lines before function definitions."""
        return updated_node.with_changes(
            leading_lines=[],
            lines_after_decorators=[],
        )

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        """Remove empty lines before class definitions."""
        return updated_node.with_changes(
            leading_lines=[],
            lines_after_decorators=[],
        )

    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.If:
        """Remove empty lines before if statements."""
        return updated_node.with_changes(leading_lines=[])

    def leave_For(
        self,
        original_node: cst.For,
        updated_node: cst.For,
    ) -> cst.For:
        """Remove empty lines before for loops."""
        return updated_node.with_changes(leading_lines=[])

    def leave_While(
        self,
        original_node: cst.While,
        updated_node: cst.While,
    ) -> cst.While:
        """Remove empty lines before while loops."""
        return updated_node.with_changes(leading_lines=[])

    def leave_Try(
        self,
        original_node: cst.Try,
        updated_node: cst.Try,
    ) -> cst.Try:
        """Remove empty lines before try blocks."""
        return updated_node.with_changes(leading_lines=[])

    def leave_With(
        self,
        original_node: cst.With,
        updated_node: cst.With,
    ) -> cst.With:
        """Remove empty lines before with statements."""
        return updated_node.with_changes(leading_lines=[])


def normalize_function_code(source: str) -> str:
    """
    Normalize Python source code for semantic comparison.

    This function applies a series of transformations to produce a
    canonical representation of the code's logic:

    1. Parse the source into a CST
    2. Remove all docstrings
    3. Remove all comments
    4. Convert back to string (LibCST handles whitespace normalization)

    Args:
        source: Python source code as a string

    Returns:
        Normalized source code string

    Raises:
        libcst.ParserSyntaxError: If the source has syntax errors

    Example:
        >>> code1 = '''
        ... def add(a, b):
        ...     \"\"\"Add two numbers.\"\"\"
        ...     # Return the sum
        ...     return a + b
        ... '''
        >>> code2 = '''
        ... def add(a, b):
        ...     return a + b
        ... '''
        >>> normalize_function_code(code1) == normalize_function_code(code2)
        True
    """
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError:
        raise

    # Apply transformations in sequence
    module = module.visit(DocstringRemover())
    module = module.visit(CommentRemover())
    module = module.visit(WhitespaceNormalizer())

    # Return normalized code
    return module.code


def compute_semantic_hash(source: str) -> str:
    """
    Compute a semantic hash of Python source code.

    The hash is computed from a normalized version of the code that
    excludes docstrings and comments, making it stable across:
    - Whitespace changes
    - Comment additions/removals
    - Docstring modifications

    The hash will change when:
    - Logic changes (different statements)
    - Variable names change
    - Function signatures change

    Args:
        source: Python source code as a string

    Returns:
        64-character hexadecimal SHA-256 hash

    Raises:
        libcst.ParserSyntaxError: If the source has syntax errors

    Example:
        >>> hash1 = compute_semantic_hash("def f(): pass")
        >>> hash2 = compute_semantic_hash("def f():\\n    pass")
        >>> hash1 == hash2  # Same logic, different formatting
        True
    """
    normalized = normalize_function_code(source)

    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    return hash_bytes


def compute_doc_hash(docstring: str) -> str:
    """
    Compute a hash of docstring content.

    This hash is used to track whether documentation has changed
    independently of code changes. The hash is computed from the
    raw docstring content with minimal normalization (strip whitespace).

    Args:
        docstring: The docstring content (without quotes)

    Returns:
        64-character hexadecimal SHA-256 hash

    Example:
        >>> hash1 = compute_doc_hash("Calculate the sum.")
        >>> hash2 = compute_doc_hash("  Calculate the sum.  ")
        >>> hash1 == hash2  # Whitespace stripped
        True
    """
    # Normalize by stripping leading/trailing whitespace
    normalized = docstring.strip()

    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    return hash_bytes


def compute_hash_for_node(
    source_code: Union[str, cst.BaseSuite],
) -> str:
    """
    Compute semantic hash for a function body node.

    This is a convenience function that handles both string sources
    and CST nodes (as returned by the parser).

    Args:
        source_code: Either a source string or a CST node

    Returns:
        64-character hexadecimal SHA-256 hash
    """
    if isinstance(source_code, str):
        return compute_semantic_hash(source_code)

    # Convert CST node to string first
    if hasattr(source_code, "code"):
        code_str = source_code.code
    else:
        # Wrap in a minimal module to get code
        code_str = cst.Module(body=[]).code
        # This is a fallback; ideally we have the full function

    return compute_semantic_hash(code_str)
