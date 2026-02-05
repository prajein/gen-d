"""
Test fixtures for Gen-D.

This module provides sample Python code and helper functions
for testing the documentation engine.
"""

# Sample code with various function types
SIMPLE_FUNCTION = '''
def greet(name):
    """Say hello to someone."""
    return f"Hello, {name}!"
'''

FUNCTION_NO_DOCSTRING = '''
def add(a, b):
    return a + b
'''

CLASS_WITH_METHODS = '''
class Calculator:
    """A simple calculator class."""

    def __init__(self, value=0):
        """Initialize with a starting value."""
        self.value = value

    def add(self, x):
        """Add a number to the current value."""
        self.value += x
        return self.value

    def subtract(self, x):
        self.value -= x
        return self.value
'''

NESTED_FUNCTIONS = '''
def outer():
    """The outer function."""
    def inner():
        """The inner function."""
        return 42
    return inner()
'''

FUNCTION_WITH_CALLS = '''
def process_data():
    """Process some data."""
    data = fetch_data()
    cleaned = clean_data(data)
    return transform(cleaned)

def fetch_data():
    """Fetch data from source."""
    return [1, 2, 3]

def clean_data(data):
    """Clean the data."""
    return [x for x in data if x > 0]

def transform(data):
    return [x * 2 for x in data]
'''

ASYNC_FUNCTION = '''
async def fetch_async(url):
    """Fetch a URL asynchronously."""
    response = await make_request(url)
    return response.json()
'''

DECORATED_FUNCTION = '''
@staticmethod
def static_method():
    """A static method."""
    return "static"

@classmethod
def class_method(cls):
    """A class method."""
    return cls.__name__
'''

# Code that should produce the same semantic hash
SEMANTICALLY_EQUIVALENT_1 = '''
def compute(x, y):
    """Compute something."""
    return x + y
'''

SEMANTICALLY_EQUIVALENT_2 = '''
def compute(x, y):
    """Different docstring."""
    return x + y
'''

# Code that should produce different semantic hashes
SEMANTICALLY_DIFFERENT = '''
def compute(x, y):
    """Compute something."""
    return x * y  # Different operation
'''
