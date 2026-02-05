"""Utilities module for the sample project."""


def format_currency(amount: float) -> str:
    """
    Format a number as currency.

    Args:
        amount: The numeric amount

    Returns:
        Formatted string with currency symbol
    """
    return f"${amount:,.2f}"


def parse_date(date_string):
    # No docstring - should be detected as UNDOCUMENTED
    return date_string.split("-")


def calculate_percentage(part: float, whole: float) -> float:
    """
    Calculate percentage.

    Args:
        part: The partial value
        whole: The total value

    Returns:
        Percentage as a float (0-100)
    """
    if whole == 0:
        return 0.0
    return (part / whole) * 100
