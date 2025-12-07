"""
Tests for Spinner iteration with total in protonfetcher.py
"""

import sys
from pathlib import Path

# Add the project directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from protonfetcher.spinner import Spinner  # noqa: E402


class TestSpinnerIteration:
    """Tests for Spinner iteration with total parameter."""

    def test_spinner_with_total(self):
        """Test spinner iteration when total is specified."""
        spinner = Spinner(desc="Test", total=5)

        # Test iteration with total specified
        result = []
        for i in spinner:
            result.append(i)
            if len(result) >= 5:  # Stop when we reach total
                break

        # The spinner will yield 0, 1, 2, 3, 4 (up to total-1)
        assert len(result) == 5
        assert result == [0, 1, 2, 3, 4]

    def test_spinner_with_iterable_and_total(self):
        """Test spinner with both iterable and total."""
        data = ["a", "b", "c"]
        spinner = Spinner(iterable=iter(data), total=3)

        result = list(spinner)
        assert result == ["a", "b", "c"]

    def test_spinner_iteration_edge_cases(self):
        """Test spinner iteration edge cases."""
        # Test with total=0
        spinner = Spinner(total=0)
        result = list(spinner)
        assert result == []

        # Test with total=1
        spinner = Spinner(total=1)
        result = []
        for i in spinner:
            result.append(i)
            break  # Only take one item
        assert result == [0]
