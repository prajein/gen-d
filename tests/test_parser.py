"""
Tests for the parser module.

Tests the LibCST-based function extraction and call detection.
"""

import pytest
from engine.parser import (
    extract_functions_from_source,
    extract_calls_from_source,
    FunctionCollector,
)
from tests.fixtures import (
    SIMPLE_FUNCTION,
    FUNCTION_NO_DOCSTRING,
    CLASS_WITH_METHODS,
    NESTED_FUNCTIONS,
    FUNCTION_WITH_CALLS,
)


class TestFunctionExtraction:
    """Tests for function extraction."""

    def test_simple_function_extraction(self):
        """Test extracting a simple function with docstring."""
        functions = extract_functions_from_source(SIMPLE_FUNCTION)

        assert len(functions) == 1
        func = functions[0]
        assert func.name == "greet"
        assert func.docstring == "Say hello to someone."
        assert func.is_method is False
        assert func.start_line > 0
        assert func.end_line >= func.start_line

    def test_function_without_docstring(self):
        """Test extracting a function without docstring."""
        functions = extract_functions_from_source(FUNCTION_NO_DOCSTRING)

        assert len(functions) == 1
        func = functions[0]
        assert func.name == "add"
        assert func.docstring is None

    def test_class_method_extraction(self):
        """Test extracting methods from a class."""
        functions = extract_functions_from_source(CLASS_WITH_METHODS)

        # Should find: __init__, add, subtract
        assert len(functions) == 3

        # Check that methods are properly identified
        method_names = {f.name for f in functions}
        assert method_names == {"__init__", "add", "subtract"}

        # Check is_method flag
        for func in functions:
            assert func.is_method is True
            assert func.class_name == "Calculator"

        # Check docstrings
        init_func = next(f for f in functions if f.name == "__init__")
        assert init_func.docstring == "Initialize with a starting value."

        subtract_func = next(f for f in functions if f.name == "subtract")
        assert subtract_func.docstring is None

    def test_nested_function_extraction(self):
        """Test extracting nested functions."""
        functions = extract_functions_from_source(NESTED_FUNCTIONS)

        # Should find both outer and inner
        assert len(functions) == 2

        names = {f.name for f in functions}
        assert names == {"outer", "inner"}

        # Check qualified names
        outer = next(f for f in functions if f.name == "outer")
        inner = next(f for f in functions if f.name == "inner")

        assert "outer" in outer.qualified_name
        assert "inner" in inner.qualified_name

    def test_module_name_qualification(self):
        """Test that module name is included in qualified names."""
        functions = extract_functions_from_source(
            SIMPLE_FUNCTION,
            module_name="mymodule",
        )

        assert len(functions) == 1
        assert functions[0].qualified_name == "mymodule.greet"


class TestCallExtraction:
    """Tests for function call extraction."""

    def test_simple_calls(self):
        """Test extracting function calls."""
        calls = extract_calls_from_source(FUNCTION_WITH_CALLS)

        # process_data calls: fetch_data, clean_data, transform
        process_calls = [c for c in calls if "process_data" in c.caller_qualified_name]
        callee_names = {c.callee_name for c in process_calls}

        assert "fetch_data" in callee_names
        assert "clean_data" in callee_names
        assert "transform" in callee_names

    def test_call_line_tracking(self):
        """Test that call line numbers are tracked."""
        calls = extract_calls_from_source(FUNCTION_WITH_CALLS)

        for call in calls:
            assert call.call_line > 0

    def test_no_calls_outside_functions(self):
        """Test that module-level calls are not captured."""
        source = """
x = print("hello")  # module level call

def func():
    print("in function")
"""
        calls = extract_calls_from_source(source)

        # Only the call inside func should be captured
        assert len(calls) == 1
        assert "func" in calls[0].caller_qualified_name


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_source(self):
        """Test handling of empty source."""
        functions = extract_functions_from_source("")
        assert functions == []

    def test_syntax_error(self):
        """Test that syntax errors raise exceptions."""
        with pytest.raises(Exception):  # libcst.ParserSyntaxError
            extract_functions_from_source("def broken(")

    def test_multiline_docstring(self):
        """Test extraction of multiline docstrings."""
        source = '''
def func():
    """
    This is a multiline
    docstring with multiple
    lines.
    """
    pass
'''
        functions = extract_functions_from_source(source)
        assert len(functions) == 1
        # Docstring should be extracted (content may vary)
        assert functions[0].docstring is not None
        assert "multiline" in functions[0].docstring

    def test_concatenated_string_docstring(self):
        """Test handling of concatenated string docstrings."""
        source = '''
def func():
    "Part 1" "Part 2"
    pass
'''
        functions = extract_functions_from_source(source)
        assert len(functions) == 1
        # Concatenated strings should be handled
        assert functions[0].docstring is not None
