"""
LibCST-based Function and Call Extractor

This module provides the core parsing functionality for Gen-D,
extracting function definitions and call relationships from Python source code.

Key Components:
    - FunctionCollector: CST visitor that extracts function/method definitions
    - CallCollector: CST visitor that extracts function call sites
    - extract_functions_from_file: Main entry point for file-based extraction
    - extract_functions_from_source: Entry point for string-based extraction

Design Decisions:
    - Uses LibCST (not ast) to preserve position information and enable future rewrites
    - Extracts both standalone functions and class methods
    - Handles nested functions by creating hierarchical IDs
    - Does not resolve dynamic calls (limitation of static analysis)

Academic Context:
    Input: Python source file or string
    Transformation: CST traversal with visitor pattern
    Output: List of (function_info, docstring, source_code) tuples
    Limitation: Cannot resolve dynamic dispatch or metaprogramming
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


@dataclass
class FunctionInfo:
    """
    Raw extracted information about a function or method.

    This is an intermediate representation before creating a full CodeNode.
    It contains the structural information extracted from the CST.

    Attributes:
        name: Simple function name
        qualified_name: Full qualified name including class/module path
        start_line: 1-indexed starting line
        end_line: 1-indexed ending line
        is_method: True if this is a class method
        class_name: Name of containing class if is_method
        docstring: Extracted docstring content, if present
        source_code: Original source code of the function body
    """

    name: str
    qualified_name: str
    start_line: int
    end_line: int
    is_method: bool = False
    class_name: Optional[str] = None
    docstring: Optional[str] = None
    source_code: str = ""


@dataclass
class CallInfo:
    """
    Information about a function call site.

    Attributes:
        caller_qualified_name: Qualified name of the calling function
        callee_name: Name of the called function (may be unqualified)
        call_line: Line number where the call occurs
    """

    caller_qualified_name: str
    callee_name: str
    call_line: int


class FunctionCollector(cst.CSTVisitor):
    """
    CST Visitor that collects function and method definitions.

    Traverses a LibCST tree and extracts information about all function
    definitions, including their docstrings and source code.

    Handles:
        - Top-level functions
        - Class methods (instance, class, static)
        - Nested functions
        - Async functions

    Usage:
        wrapper = MetadataWrapper(module)
        collector = FunctionCollector()
        wrapper.visit(collector)
        functions = collector.functions
    """

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, module_name: str = "") -> None:
        """
        Initialize the collector.

        Args:
            module_name: Base module name for qualified names
        """
        self.module_name = module_name
        self.functions: list[FunctionInfo] = []
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Enter a class definition, tracking class context."""
        self._class_stack.append(node.name.value)
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        """Exit a class definition."""
        self._class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        """
        Visit a function definition and extract its information.

        Extracts:
            - Function name and qualified name
            - Line range from position metadata
            - Docstring if present
            - Source code for semantic hashing
        """
        func_name = node.name.value

        # Build qualified name
        parts = []
        if self.module_name:
            parts.append(self.module_name)
        parts.extend(self._class_stack)
        parts.extend(self._function_stack)
        parts.append(func_name)
        qualified_name = ".".join(parts)

        # Get position information
        try:
            pos = self.get_metadata(PositionProvider, node)
            start_line = pos.start.line
            end_line = pos.end.line
        except KeyError:
            # Fallback if metadata not available
            start_line = 0
            end_line = 0

        # Extract docstring
        docstring = self._extract_docstring(node)

        # Get source code - convert the function node to a string
        # This gives us the complete, parseable function definition
        try:
            source_code = cst.Module(body=[node]).code
        except Exception:
            source_code = ""

        # Determine if this is a method
        is_method = len(self._class_stack) > 0
        class_name = self._class_stack[-1] if is_method else None

        func_info = FunctionInfo(
            name=func_name,
            qualified_name=qualified_name,
            start_line=start_line,
            end_line=end_line,
            is_method=is_method,
            class_name=class_name,
            docstring=docstring,
            source_code=source_code,
        )
        self.functions.append(func_info)

        # Track nested functions
        self._function_stack.append(func_name)
        return True

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Exit a function definition."""
        self._function_stack.pop()

    def _extract_docstring(self, node: cst.FunctionDef) -> Optional[str]:
        """
        Extract the docstring from a function definition.

        A docstring is the first statement in a function body if it's
        a string literal expression.

        Args:
            node: The function definition node

        Returns:
            The docstring content without quotes, or None if no docstring
        """
        body = node.body
        if isinstance(body, cst.IndentedBlock):
            statements = body.body
            if statements:
                first_stmt = statements[0]
                if isinstance(first_stmt, cst.SimpleStatementLine):
                    if first_stmt.body:
                        first_expr = first_stmt.body[0]
                        if isinstance(first_expr, cst.Expr):
                            if isinstance(first_expr.value, (cst.SimpleString, cst.ConcatenatedString)):
                                return self._extract_string_value(first_expr.value)
                            elif isinstance(first_expr.value, cst.FormattedString):
                                # f-strings are not valid docstrings
                                return None
        return None

    def _extract_string_value(self, node: cst.BaseExpression) -> str:
        """
        Extract the actual string value from a string literal node.

        Handles both simple strings and concatenated strings.
        """
        if isinstance(node, cst.SimpleString):
            # Remove quotes (handles ', ", ''', \""")
            value = node.value
            if value.startswith(('"""', "'''")):
                return value[3:-3]
            elif value.startswith(('"', "'")):
                return value[1:-1]
            return value
        elif isinstance(node, cst.ConcatenatedString):
            parts = []
            for part in node.left, node.right:
                parts.append(self._extract_string_value(part))
            return "".join(parts)
        return ""


class CallCollector(cst.CSTVisitor):
    """
    CST Visitor that collects function call sites.

    Traverses a LibCST tree and extracts information about all function
    calls, recording which function contains each call.

    Handles:
        - Simple function calls: func()
        - Method calls: obj.method()
        - Chained calls: obj.method1().method2()

    Limitations:
        - Cannot resolve dynamic calls (getattr, *args unpacking)
        - Cannot trace calls through variables
        - Method calls are recorded with partial names

    Usage:
        wrapper = MetadataWrapper(module)
        collector = CallCollector()
        wrapper.visit(collector)
        calls = collector.calls
    """

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, module_name: str = "") -> None:
        """
        Initialize the collector.

        Args:
            module_name: Base module name for qualified names
        """
        self.module_name = module_name
        self.calls: list[CallInfo] = []
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []
        self._in_function: bool = False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Enter a class definition, tracking class context."""
        self._class_stack.append(node.name.value)
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        """Exit a class definition."""
        self._class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        """Enter a function definition, tracking context."""
        func_name = node.name.value
        self._function_stack.append(func_name)
        self._in_function = True
        return True

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Exit a function definition."""
        self._function_stack.pop()
        self._in_function = len(self._function_stack) > 0

    def visit_Call(self, node: cst.Call) -> bool:
        """
        Visit a function call and extract call information.

        Only records calls that occur within a function body.
        """
        if not self._in_function:
            return True

        # Build caller qualified name
        parts = []
        if self.module_name:
            parts.append(self.module_name)
        parts.extend(self._class_stack)
        parts.extend(self._function_stack)
        caller_name = ".".join(parts)

        # Extract callee name
        callee_name = self._extract_callee_name(node.func)
        if callee_name is None:
            return True

        # Get line number
        try:
            pos = self.get_metadata(PositionProvider, node)
            call_line = pos.start.line
        except KeyError:
            call_line = 0

        call_info = CallInfo(
            caller_qualified_name=caller_name,
            callee_name=callee_name,
            call_line=call_line,
        )
        self.calls.append(call_info)

        return True

    def _extract_callee_name(self, node: cst.BaseExpression) -> Optional[str]:
        """
        Extract the name of the called function.

        Args:
            node: The expression representing the function being called

        Returns:
            The callee name, or None if it cannot be statically determined
        """
        if isinstance(node, cst.Name):
            # Simple call: func()
            return node.value
        elif isinstance(node, cst.Attribute):
            # Method call: obj.method() or module.func()
            # We return the full dotted name if possible
            parts = []
            current = node
            while isinstance(current, cst.Attribute):
                parts.append(current.attr.value)
                current = current.value
            if isinstance(current, cst.Name):
                parts.append(current.value)
            parts.reverse()
            return ".".join(parts)
        # Cannot determine callee for complex expressions
        return None


def extract_functions_from_source(
    source: str,
    module_name: str = "",
) -> list[FunctionInfo]:
    """
    Extract all function definitions from Python source code.

    This is the main entry point for parsing source code strings.
    It handles CST parsing and metadata resolution internally.

    Args:
        source: Python source code as a string
        module_name: Optional module name for qualified names

    Returns:
        List of FunctionInfo objects for each function/method found

    Raises:
        libcst.ParserSyntaxError: If the source code has syntax errors

    Example:
        >>> source = '''
        ... def hello(name):
        ...     \"\"\"Greet someone.\"\"\"
        ...     print(f"Hello, {name}!")
        ... '''
        >>> functions = extract_functions_from_source(source)
        >>> functions[0].name
        'hello'
        >>> functions[0].docstring
        'Greet someone.'
    """
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError:
        raise

    wrapper = MetadataWrapper(module)
    collector = FunctionCollector(module_name=module_name)
    wrapper.visit(collector)

    return collector.functions


def extract_functions_from_file(
    file_path: Path | str,
) -> list[FunctionInfo]:
    """
    Extract all function definitions from a Python file.

    Reads the file, determines the module name from the path,
    and extracts all function definitions.

    Args:
        file_path: Path to the Python file

    Returns:
        List of FunctionInfo objects for each function/method found

    Raises:
        FileNotFoundError: If the file doesn't exist
        libcst.ParserSyntaxError: If the file has syntax errors
        UnicodeDecodeError: If the file has encoding issues

    Example:
        >>> functions = extract_functions_from_file("my_module.py")
        >>> for func in functions:
        ...     print(f"{func.qualified_name}: {func.start_line}-{func.end_line}")
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    source = file_path.read_text(encoding="utf-8")

    # Derive module name from file path
    module_name = file_path.stem

    return extract_functions_from_source(source, module_name=module_name)


def extract_calls_from_source(
    source: str,
    module_name: str = "",
) -> list[CallInfo]:
    """
    Extract all function calls from Python source code.

    Args:
        source: Python source code as a string
        module_name: Optional module name for qualified names

    Returns:
        List of CallInfo objects for each call found

    Raises:
        libcst.ParserSyntaxError: If the source code has syntax errors

    Example:
        >>> source = '''
        ... def process():
        ...     data = fetch_data()
        ...     return transform(data)
        ... '''
        >>> calls = extract_calls_from_source(source)
        >>> [c.callee_name for c in calls]
        ['fetch_data', 'transform']
    """
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError:
        raise

    wrapper = MetadataWrapper(module)
    collector = CallCollector(module_name=module_name)
    wrapper.visit(collector)

    return collector.calls
