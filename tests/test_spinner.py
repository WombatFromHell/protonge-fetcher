"""
Unit tests for the Spinner class in protonfetcher.py
"""

from protonfetcher.spinner import Spinner


class TestSpinner:
    """Tests for the Spinner class."""

    def test_spinner_initialization(self):
        """Test spinner initialization."""
        spinner = Spinner(desc="Test", unit="B", disable=True)
        assert spinner.desc == "Test"
        assert spinner.unit == "B"
        assert spinner.disable is True
        assert spinner.current == 0

    def test_spinner_update(self, mocker):
        """Test spinner update method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(
            desc="Test", disable=False, fps_limit=10
        )  # High FPS limit to allow updates
        spinner.update(5)
        assert spinner.current == 5
        # Verify it tried to print
        mock_print.assert_called()

    def test_spinner_update_progress(self, mocker):
        """Test spinner update_progress method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(desc="Test", disable=False, fps_limit=10)
        spinner.update_progress(50, 100)
        assert spinner.current == 50
        assert spinner.total == 100
        # Verify it tried to print
        mock_print.assert_called()

    def test_spinner_context_manager(self, mocker):
        """Test spinner as context manager."""
        mock_print = mocker.patch("builtins.print")
        with Spinner(disable=False, fps_limit=10) as spinner:
            spinner.update(1)
        # Verify print was called
        mock_print.assert_called()

    def test_spinner_iterable(self, mocker):
        """Test spinner with iterable."""
        mocker.patch("builtins.print")
        test_iterable = iter([1, 2, 3])
        spinner = Spinner(iterable=test_iterable, disable=True)
        result = list(spinner)
        assert result == [1, 2, 3]
        assert spinner.current == 3

    def test_spinner_close(self, mocker):
        """Test spinner close method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(disable=False)
        spinner.close()
        # Verify print was called to clear the line
        mock_print.assert_called()

    def test_spinner_finish(self, mocker):
        """Test spinner finish method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(disable=False, total=10)
        spinner.current = 5
        spinner.finish()
        # Verify current is set to total and print was called
        assert spinner.current == 10
        mock_print.assert_called()
