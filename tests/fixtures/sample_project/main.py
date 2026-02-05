"""
Sample Project for Testing Gen-D

This is a realistic sample Python project used for integration testing.
It contains various function types, documentation patterns, and call relationships.
"""


def main():
    """
    Main entry point for the sample application.

    This function orchestrates the data processing pipeline:
    1. Loads data from source
    2. Processes the data
    3. Generates a report
    """
    data = load_data("sample.csv")
    processed = process_data(data)
    report = generate_report(processed)
    return report


def load_data(filename: str) -> list:
    """
    Load data from a file.

    Args:
        filename: Path to the data file

    Returns:
        List of data records
    """
    # Simulated data loading
    return [
        {"id": 1, "value": 100},
        {"id": 2, "value": 200},
        {"id": 3, "value": 300},
    ]


def process_data(data: list) -> list:
    """
    Process raw data records.

    Applies transformations including:
    - Validation
    - Normalization
    - Enrichment

    Args:
        data: List of raw data records

    Returns:
        List of processed records
    """
    validated = validate_data(data)
    normalized = normalize_values(validated)
    return normalized


def validate_data(data: list) -> list:
    """Validate data records, removing invalid entries."""
    return [record for record in data if record.get("value", 0) > 0]


def normalize_values(data: list) -> list:
    """Normalize values to a 0-1 range."""
    if not data:
        return data
    max_value = max(record["value"] for record in data)
    return [
        {**record, "value": record["value"] / max_value}
        for record in data
    ]


def generate_report(data: list) -> str:
    """
    Generate a summary report from processed data.

    Args:
        data: List of processed records

    Returns:
        Formatted report string
    """
    total = sum(record["value"] for record in data)
    count = len(data)
    return f"Report: {count} records, total value: {total:.2f}"


# Function without documentation (for testing UNDOCUMENTED detection)
def helper_function():
    return "I have no docstring"


class DataProcessor:
    """
    A class for processing data with various strategies.

    This demonstrates class-based organization with documented
    and undocumented methods.
    """

    def __init__(self, strategy: str = "default"):
        """
        Initialize the processor with a strategy.

        Args:
            strategy: Processing strategy name
        """
        self.strategy = strategy
        self.processed_count = 0

    def process(self, data: list) -> list:
        """
        Process data using the configured strategy.

        Args:
            data: Input data to process

        Returns:
            Processed data
        """
        self.processed_count += len(data)
        if self.strategy == "double":
            return self._double_values(data)
        return data

    def _double_values(self, data: list) -> list:
        # Private method without docstring
        return [x * 2 for x in data]

    def get_stats(self):
        """Get processing statistics."""
        return {"processed": self.processed_count}
