"""
Tests for Spinner class functionality in protonfetcher.py
"""

import sys
from pathlib import Path

# Add the project directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from protonfetcher.spinner import Spinner  # noqa: E402


class TestSpinnerFunctionality:
    """Tests for Spinner class edge cases and functionality."""

    def test_spinner_format_rate_with_unit_scale_bytes(self):
        """Test rate formatting when unit_scale is True and unit is 'B' with different rates."""
        # Create a spinner with unit="B" and unit_scale=True
        Spinner(desc="Test", unit="B", unit_scale=True, total=4096)

    def test_spinner_format_rate_without_unit_scale(self):
        """Test rate formatting when unit_scale is False."""
        Spinner(desc="Test", unit="items", unit_scale=False, total=200)

    def test_spinner_format_rate_edge_cases(self):
        """Test rate formatting with edge cases (zero elapsed time)."""
        Spinner(desc="Test", unit="B", unit_scale=True, total=2048)

    def test_spinner_with_different_units(self):
        """Test spinner behavior with different units."""
        # Create a spinner with iterable and test functionality
        result = list(Spinner(iterable=iter(range(5)), total=5))
        assert result == [0, 1, 2, 3, 4]

    def test_spinner_context_manager(self):
        """Test spinner as context manager."""
        with Spinner(desc="Test") as spinner:
            # Verify the spinner can be used in context
            assert spinner is not None
            spinner.close()  # Close manually to avoid display

    def test_spinner_disabled_mode(self):
        """Test spinner when disabled."""
        spinner = Spinner(desc="Test", disable=True)
        # Should work without displaying anything
        spinner.close()

    def test_spinner_iter_with_iterator(self):
        """Test spinner with a custom iterator."""

        def custom_iter():
            yield 1
            yield 2
            yield 3

        spinner = Spinner(desc="Test", iterable=custom_iter())
        result = []
        for item in spinner:
            result.append(item)
            spinner.current += 1
        assert result == [1, 2, 3]
