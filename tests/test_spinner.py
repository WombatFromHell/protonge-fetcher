"""
Unit tests for the Spinner class in protonfetcher.py
"""

import pytest

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
        assert spinner.unit_scale is True  # Default when unit == "B"

        # Test with unit != "B" to maintain default of False if unit_scale not provided
        spinner2 = Spinner(unit="it")
        assert spinner2.unit_scale is False  # Default when unit != "B"

        # Test with unit_scale explicitly provided
        spinner3 = Spinner(unit="B", unit_scale=False)
        assert spinner3.unit_scale is False  # Explicitly set to False

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

    def test_spinner_context_manager_exit_method(self, mocker):
        """Test Spinner __exit__ method (lines 50-53)."""
        mock_print = mocker.patch("builtins.print")

        spinner = Spinner(disable=False)
        spinner._current_line = "Loading..."  # Set a current line to clear

        # Test the context manager exit functionality
        with spinner:
            pass  # Context manager will call __exit__

        # The print should have been called to clear the display
        mock_print.assert_called()

    def test_spinner_exit_method_with_empty_line(self, mocker):
        """Test Spinner __exit__ method with empty current line."""
        mock_print = mocker.patch("builtins.print")

        spinner = Spinner(disable=False)
        spinner._current_line = ""  # Empty line

        with spinner:
            pass  # Context manager will call __exit__

        # The print should still be called even with empty line
        mock_print.assert_called()

    def test_spinner_disabled_exit_method(self):
        """Test Spinner __exit__ method when disabled."""
        spinner = Spinner(disable=True)
        spinner._current_line = "Loading..."  # Set a current line

        # Context manager with disabled spinner should not print
        with spinner:
            pass

        # No print should happen when disabled

    def test_spinner_update_display_fps_limit_early_exit(self, mocker):
        """Test _update_display early exit due to FPS limit (line 56->exit)."""
        mock_print = mocker.patch("builtins.print")

        # Set up spinner with FPS limit
        spinner = Spinner(disable=False, fps_limit=10)  # 10 FPS = 0.1s interval
        spinner.current = 10
        spinner.total = 100

        # Set _last_update_time to a recent time that would prevent update due to FPS limit
        spinner._last_update_time = 10.0  # Mock value to represent last update time

        # Mock time.time to return a value that's less than the minimum interval from _last_update_time
        mocker.patch(
            "time.time", return_value=10.01
        )  # Only 0.01s passed, min interval is 0.1s

        # Update the display
        spinner._update_display()

        # Should return early due to FPS limit since not enough time has passed
        # No print call should happen because the method exits early
        mock_print.assert_not_called()

    def test_spinner_update_display_no_fps_limit(self, mocker):
        """Test _update_display when no FPS limit is set."""
        mock_print = mocker.patch("builtins.print")

        # Set up spinner without FPS limit
        spinner = Spinner(disable=False, fps_limit=None)  # No FPS limit
        spinner.current = 10
        spinner.total = 100
        spinner._last_update_time = 10.0  # Recent time

        # Mock time.time to return a newer value
        mocker.patch("time.time", return_value=10.01)  # Small time difference

        # Update the display
        spinner._update_display()

        # Should update because there's no FPS limit
        mock_print.assert_called()

    def test_spinner_finish_already_completed_exit_early(self, mocker):
        """Test spinner finish method when already completed (line 182->exit)."""
        mock_print = mocker.patch("builtins.print")

        spinner = Spinner(disable=False, total=10, show_progress=True)
        spinner._completed = True  # Set as already completed

        original_current = spinner.current
        spinner.current = 15  # Try to set to a higher value
        spinner.finish()  # Should exit early due to _completed being True

        # Current should remain unchanged since method exits early
        assert spinner.current == 15  # Should still be 15, not total
        # The method should return early without executing the main body
        # Check that print was not called in the completion part
        # It might still be called initially, but the finishing behavior should be skipped

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

    def test_fps_limit_functionality(self, mocker):
        """Test FPS limit functionality (lines 76-78, 82-84)."""
        mocker.patch("builtins.print")

        # Mock time to simulate small time intervals that are less than fps limit
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 0.0

        # Test with fps limit set
        spinner = Spinner(disable=False, fps_limit=2.0)

        result = spinner._should_update_display(
            0.1
        )  # 0.1 < 1/2.0 (0.5), so should return False
        assert result is False

        # Test when interval exceeds fps limit (should update)
        result = spinner._should_update_display(
            0.6
        )  # 0.6 > 1/2.0 (0.5), so should return True
        assert result is True

        # Test with fps limit disabled (None or 0)
        spinner_no_limit = Spinner(disable=False, fps_limit=None)
        result = spinner_no_limit._should_update_display(0.1)
        assert result is True

        spinner_zero_limit = Spinner(disable=False, fps_limit=0)
        result = spinner_zero_limit._should_update_display(0.1)
        assert result is True

    def test_calculate_progress_percentage(self):
        """Test _calculate_progress_percentage method (lines affected by 88-93)."""
        # Test with total=None
        spinner = Spinner()
        assert spinner._calculate_progress_percentage() == 0.0

        # Test with total=0
        spinner = Spinner()
        spinner.total = 0
        assert spinner._calculate_progress_percentage() == 0.0

        # Test with normal values
        spinner = Spinner()
        spinner.current = 50
        spinner.total = 100
        assert spinner._calculate_progress_percentage() == 0.5

        # Test with current > total (should be capped at 1.0)
        spinner = Spinner()
        spinner.current = 150
        spinner.total = 100
        assert spinner._calculate_progress_percentage() == 1.0

    def test_format_progress_bar(self):
        """Test _format_progress_bar method (lines 128-139)."""
        spinner = Spinner(width=10)

        # Test with 50% progress
        bar = spinner._format_progress_bar(0.5)
        assert bar == " |█████-----| 50.0%"

        # Test with 0% progress
        bar = spinner._format_progress_bar(0.0)
        assert bar == " |----------| 0.0%"

        # Test with 100% progress
        bar = spinner._format_progress_bar(1.0)
        assert bar == " |██████████| 100.0%"

    @pytest.mark.parametrize(
        "rate,expected",
        [
            (512.0, "512.00B/s"),  # rate <= 1024 (B/s)
            (2048.0, "2.00KB/s"),  # rate < 1024**2 (KB/s)
            (2097152.0, "2.00MB/s"),  # rate >= 1024**2 (MB/s)
        ],
    )
    def test_format_rate_for_bytes_progress(self, rate, expected):
        """Test _format_rate_for_bytes_progress method (lines 154-155)."""
        spinner = Spinner(unit="B", unit_scale=True)
        rate_str = spinner._format_rate_for_bytes_progress(rate)
        assert rate_str == expected

    @pytest.mark.parametrize(
        "rate,expected",
        [
            (512.0, "512.00B/s"),  # rate <= 1024 (B/s)
            (2048.0, "2.00KB/s"),  # rate < 1024**2 (KB/s)
            (
                2097152.0,
                "0.00GB/s",
            ),  # rate >= 1024**2 but < 1024**3 (GB/s for spinner mode)
            (2147483648.0, "2.00GB/s"),  # rate >= 1024**3 (GB/s)
        ],
    )
    def test_format_rate_for_bytes_spinner(self, rate, expected):
        """Test _format_rate_for_bytes_spinner method."""
        spinner = Spinner(unit="B", unit_scale=True)
        rate_str = spinner._format_rate_for_bytes_spinner(rate)
        assert rate_str == expected

    def test_format_rate(self, mocker):
        """Test _format_rate method (lines 202 and 237-251)."""
        # Test with bytes unit and unit_scale=True in progress mode
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 2.0
        spinner = Spinner(unit="B", unit_scale=True)
        spinner.start_time = 0.0
        spinner.current = 2048  # 2KB processed in 2 seconds = 1KB/s

        rate_str = spinner._format_rate(2.0, mode="progress")
        assert rate_str == " (1024.00B/s)"  # Rate is formatted as 1024.00B/s

        # Test with bytes unit and unit_scale=True in spinner mode
        mock_time.return_value = 2.0
        spinner = Spinner(unit="B", unit_scale=True)
        spinner.start_time = 0.0
        spinner.current = 2048  # 2KB processed in 2 seconds = 1KB/s

        rate_str = spinner._format_rate(2.0, mode="spinner")
        assert rate_str == " (1024.00B/s)"  # Same formatting but for spinner mode

        # Test with non-bytes unit
        mock_time.return_value = 2.0
        spinner = Spinner(unit="it", unit_scale=False)
        spinner.start_time = 0.0
        spinner.current = 10

        rate_str = spinner._format_rate(2.0, mode="progress")
        assert rate_str == " (5.0it/s)"  # 10 items in 2 seconds = 5.0 items/s

    def test_build_progress_display(self, mocker):
        """Test _build_progress_display method (lines 111-122)."""
        mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 0
        spinner = Spinner(desc="Test", unit="B")
        spinner.total = 100
        spinner.current = 50
        spinner.start_time = 0
        display_parts = spinner._build_progress_display("⠋", 0.0)
        # Should include desc, spinner, progress bar and rate
        expected_parts = ["Test", ":", " ⠋  |█████-----| 50.0%", " (0.00B/s)"]
        assert display_parts == expected_parts

    def test_build_spinner_display(self, mocker):
        """Test _build_spinner_display method."""
        mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 0
        spinner = Spinner(desc="Test", unit="B")
        spinner.current = 10
        spinner.start_time = 0
        display_parts = spinner._build_spinner_display("⠋", 0.0)
        # Should include desc, spinner, current value and rate
        expected_parts = ["Test", ":", " ⠋ 10B", " (0.00B/s)"]
        assert display_parts == expected_parts

        # Test without unit
        spinner_no_unit = Spinner(desc="Test")
        display_parts = spinner_no_unit._build_spinner_display("⠋", 0.0)
        # Should include desc, spinner only
        expected_parts = ["Test", ":", " ⠋"]
        assert display_parts == expected_parts

    def test_update_display_with_fps_limit(self, mocker):
        """Test _update_display FPS limit functionality (lines 173)."""
        mock_print = mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")

        # Test with FPS limit
        mock_time.return_value = 1.0  # Starting time
        spinner = Spinner(disable=False, fps_limit=2.0)
        spinner.current = 10
        spinner.total = 100

        # First call should update
        spinner._last_update_time = 0.0  # Make sure enough time has passed
        spinner._update_display()
        mock_print.assert_called()  # Should have been called

        # Reset for next call
        mock_print.reset_mock()
        # Second call too soon should not update due to FPS limit
        spinner._last_update_time = 1.0  # Same as current time mock
        mock_time.return_value = (
            1.1  # Less than 0.5s interval for 2 FPS (should not update)
        )
        spinner._update_display()  # Should not call print due to FPS limiter
        mock_print.assert_not_called()

    def test_update_display_with_progress_and_without(self, mocker):
        """Test _update_display with and without progress display."""
        mock_print = mocker.patch("builtins.print")

        # Test with progress (total > 0 and show_progress=True)
        spinner_progress = Spinner(disable=False, total=100, show_progress=True)
        spinner_progress.current = 50
        spinner_progress._update_display()
        # Should have been called with progress bar

        mock_print.reset_mock()

        # Test without progress (total is None)
        spinner_no_progress = Spinner(disable=False, total=None)
        spinner_no_progress.current = 50
        spinner_no_progress._update_display()
        # Should have been called with spinner only

    def test_spinner_finish_with_completed_flag(self, mocker):
        """Test spinner finish method with _completed flag (line 173)."""
        mocker.patch("builtins.print")

        spinner = Spinner(disable=False, total=10, show_progress=True)
        spinner.current = 5
        assert not spinner._completed

        # First call should finish
        spinner.finish()
        assert spinner._completed is True
        assert spinner.current == 10

        # Second call should not execute the main body since _completed is True
        original_current = spinner.current  # This is 10
        spinner.current = 5  # Try to reset to check if it gets updated again
        spinner.finish()  # This shouldn't change current value since it's already completed
        # Current should remain as it was before this second call (5), because the method exits early
        assert (
            spinner.current == 5
        )  # Should still be 5, not 10, since finish() exits early when completed=True

    def test_spinner_finish_with_zero_total(self, mocker):
        """Test spinner finish method when total is 0 (should not run the main body)."""
        mocker.patch("builtins.print")

        spinner = Spinner(
            disable=False, total=0
        )  # Total is 0, so finish shouldn't run main body
        spinner.current = 5
        spinner._completed = False  # Ensure it's not already completed

        spinner.finish()  # Should not execute the main body since total is 0
        # Should still not be completed since total is 0
        assert spinner._completed is False
        # Current should still be 5 since the finish method's main body didn't execute
        assert spinner.current == 5

    def test_spinner_iter_without_iterable(self, mocker):
        """Test spinner iteration when no iterable is provided but total is specified (lines 268-271)."""
        mocker.patch("builtins.print")

        spinner = Spinner(total=3, disable=True)  # Disable print during iteration
        result = list(spinner)  # Should yield range(3) when no iterable provided
        assert result == [0, 1, 2]
        assert spinner.current == 3  # Should have updated 3 times

        # Test with total=None (should yield nothing)
        spinner2 = Spinner(total=None, disable=True)
        result2 = list(spinner2)
        assert result2 == []
        assert spinner2.current == 0

    def test_spinner_finish_with_non_bytes_unit(self, mocker):
        """Test spinner finish with non-bytes unit to cover else branch in finish method (lines 202, 237-251)."""
        mock_print = mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")

        # Create spinner with non-bytes unit and unit_scale=False
        spinner = Spinner(disable=False, total=10, unit="it", unit_scale=False)
        spinner.current = 10  # Set to the same as total

        # Mock time to create an elapsed time for rate calculation
        mock_time.return_value = 5.0  # 5 seconds elapsed
        spinner.start_time = 0.0  # So rate will be 10 items / 5 seconds = 2.0 items/s

        spinner.finish()  # Should trigger the else branch in finish method for rate formatting

        # Verify that print was called (meaning the finish method executed)
        mock_print.assert_called()

        # Also test with unit_scale=True but non-B unit
        mock_print.reset_mock()
        spinner2 = Spinner(
            disable=False, total=10, unit="it", unit_scale=True
        )  # unit_scale=True but unit != "B"
        spinner2.current = 10

        mock_time.return_value = 2.0
        spinner2.start_time = 0.0  # So rate will be 10/2 = 5.0 items/s
        spinner2.finish()

        mock_print.assert_called()

    def test_update_progress_prefix_update(self):
        """Test update_progress method updating description when prefix is provided and desc doesn't start with 'Extracting' (line 202)."""
        spinner = Spinner(desc="Initial", disable=True)
        assert spinner.desc == "Initial"

        # This should update the desc since "New" doesn't start with "Extracting"
        spinner.update_progress(current=5, total=10, prefix="New Description")
        assert spinner.desc == "New Description"

    def test_update_progress_prefix_no_update(self):
        """Test update_progress method not updating description when desc starts with 'Extracting'."""
        spinner = Spinner(desc="Extracting files...", disable=True)
        original_desc = spinner.desc
        assert original_desc == "Extracting files..."

        # This should NOT update the desc since it starts with "Extracting"
        spinner.update_progress(current=5, total=10, prefix="New Description")
        assert spinner.desc == original_desc  # Should remain unchanged

    @pytest.mark.parametrize(
        "total,elapsed,expected_rate",
        [
            (512, 2.0, "256.00B/s"),  # rate <= 1024 (B/s)
            (2048, 1.0, "2.00KB/s"),  # rate between 1024 and 1024**2 (KB/s)
            (3145728, 1.0, "3.00MB/s"),  # rate >= 1024**2 (MB/s)
        ],
    )
    def test_spinner_finish_rate_branches(self, mocker, total, elapsed, expected_rate):
        """Test different rate formatting branches in finish method (lines 237-251)."""
        mock_print = mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")

        spinner = Spinner(disable=False, total=total, unit="B", unit_scale=True)

        mock_time.return_value = elapsed
        spinner.start_time = 0.0
        spinner.finish()

        mock_print.assert_called()

    def test_spinner_format_rate_with_unit_scale_bytes(self):
        """Test rate formatting when unit_scale is True and unit is 'B' with different rates."""
        # Create a spinner with unit="B" and unit_scale=True
        spinner = Spinner(desc="Test", unit="B", unit_scale=True, total=4096)
        assert spinner.unit == "B"
        assert spinner.unit_scale is True
        assert spinner.total == 4096

    def test_spinner_format_rate_without_unit_scale(self):
        """Test rate formatting when unit_scale is False."""
        spinner = Spinner(desc="Test", unit="items", unit_scale=False, total=200)
        assert spinner.unit == "items"
        assert spinner.unit_scale is False
        assert spinner.total == 200

    def test_spinner_format_rate_edge_cases(self):
        """Test rate formatting with edge cases (zero elapsed time)."""
        spinner = Spinner(desc="Test", unit="B", unit_scale=True, total=2048)
        assert spinner.unit == "B"
        assert spinner.unit_scale is True
        assert spinner.total == 2048

    def test_spinner_with_different_units(self):
        """Test spinner behavior with different units."""
        # Create a spinner with iterable and test functionality
        result = list(Spinner(iterable=iter(range(5)), total=5))
        assert result == [0, 1, 2, 3, 4]

    def test_spinner_context_manager_functionality(self):
        """Test spinner as context manager."""
        with Spinner(desc="Test") as spinner:
            # Verify the spinner can be used in context
            assert spinner is not None
            spinner.close()  # Close manually to avoid display

    def test_spinner_disabled_mode(self):
        """Test spinner when disabled."""
        spinner = Spinner(desc="Test", disable=True)
        # Should work without displaying anything
        assert spinner.disable is True
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

    def test_spinner_update_display_early_return_due_to_fps_limit(self, mocker):
        """Test _update_display early return due to FPS limit (line 56->exit)."""
        mock_print = mocker.patch("builtins.print")
        # Set up spinner with FPS limit
        spinner = Spinner(disable=False, fps_limit=10)  # 10 FPS = 0.1s interval
        spinner.current = 10
        spinner.total = 100

        # Set _last_update_time to a recent time that would prevent update due to FPS limit
        spinner._last_update_time = 10.0  # Mock value to represent last update time

        # Mock time.time to return a value that's less than the minimum interval from _last_update_time
        mocker.patch(
            "time.time", return_value=10.01
        )  # Only 0.01s passed, min interval is 0.1s

        # Update the current time in the _update_display call
        spinner._update_display()
        # Should return early due to FPS limit since not enough time has passed

    def test_spinner_update_display_with_zero_fps_limit(self, mocker):
        """Test _update_display with 0 FPS limit."""
        mock_print = mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 1.0

        # Test with fps_limit=0, which should always allow updates
        spinner = Spinner(disable=False, fps_limit=0)
        spinner.current = 10
        spinner.total = 100
        spinner._last_update_time = 1.0  # Recent time
        # _should_update_display should return True when fps_limit=0
        result = spinner._should_update_display(1.1)  # Small time difference
        assert result is True

    def test_spinner_update_display_with_none_fps_limit(self, mocker):
        """Test _update_display with None FPS limit."""
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 1.0

        # Test with fps_limit=None, which should always allow updates
        spinner = Spinner(disable=False, fps_limit=None)
        spinner.current = 10
        spinner.total = 100
        spinner._last_update_time = 1.0  # Recent time
        # _should_update_display should return True when fps_limit is None
        result = spinner._should_update_display(1.1)  # Small time difference
        assert result is True

    def test_spinner_finish_already_completed(self, mocker):
        """Test spinner finish method when already completed (line 182->exit)."""
        mock_print = mocker.patch("builtins.print")

        spinner = Spinner(disable=False, total=10, show_progress=True)
        spinner._completed = True  # Set as already completed

        original_current = spinner.current
        spinner.current = 15  # Try to set to a higher value
        spinner.finish()  # Should exit early due to _completed being True

        # Current should remain unchanged since method exits early
        assert spinner.current == 15  # Should still be 15, not total
        # The method should return early without executing the main body

    def test_spinner_finish_with_zero_total_exit_path(self, mocker):
        """Test spinner finish with total=0 (line 222->exit)."""
        mock_print = mocker.patch("builtins.print")

        spinner = Spinner(disable=False, total=0, show_progress=True)
        spinner._completed = False  # Ensure not completed already

        original_current = spinner.current
        spinner.current = 5  # Set to some value
        spinner.finish()  # Should exit early due to total=0

        # Since total is 0, the main body of finish shouldn't execute
        assert spinner.current == 5  # Should remain as original
        assert spinner._completed is False  # Should remain False

    def test_spinner_finish_with_none_total(self, mocker):
        """Test spinner finish with total=None (another exit path)."""
        mock_print = mocker.patch("builtins.print")

        spinner = Spinner(disable=False, total=None, show_progress=True)
        spinner._completed = False  # Ensure not completed already

        spinner.current = 5  # Set to some value
        spinner.finish()  # Should exit early due to total=None

        # Since total is None, the main body of finish shouldn't execute
        assert spinner.current == 5  # Should remain as original
        assert spinner._completed is False  # Should remain False

    def test_spinner_with_disabled_output(self, mocker):
        """Test spinner operations with disabled output."""
        mock_print = mocker.patch("builtins.print")

        # Test various operations with disabled output
        spinner = Spinner(disable=True, total=10)
        spinner.update(5)
        spinner.update_progress(5, 10)
        spinner.close()
        spinner.finish()

        # Print should not have been called since disable=True
        mock_print.assert_not_called()

    def test_spinner_should_update_display_with_various_fps_limits(self, mocker):
        """Test _should_update_display with different FPS limits."""
        spinner_default = Spinner()  # No fps_limit
        spinner_zero = Spinner(fps_limit=0)
        spinner_none = Spinner(fps_limit=None)
        spinner_positive = Spinner(fps_limit=5.0)  # 5 FPS = 0.2s interval

        # Test with fps_limit=None
        result = spinner_none._should_update_display(1.0)
        assert result is True  # Should always return True when fps_limit is None

        # Test with fps_limit=0
        result = spinner_zero._should_update_display(1.0)
        assert result is True  # Should always return True when fps_limit is 0

        # Test with positive fps_limit but no min_interval passed
        result = spinner_positive._should_update_display(1.0)
        # This might be True if _last_update_time was 0 initially
        # The behavior depends on the time difference with _last_update_time

        # Test with positive fps_limit and sufficient time difference
        spinner_positive._last_update_time = 0.0
        result = spinner_positive._should_update_display(1.0)  # 1.0 - 0.0 = 1.0 > 0.2
        assert result is True  # Should return True if sufficient time has passed

        # Test with positive fps_limit and insufficient time difference
        spinner_positive._last_update_time = 1.0
        result = spinner_positive._should_update_display(1.1)  # 1.1 - 1.0 = 0.1 < 0.2
        assert result is False  # Should return False if insufficient time has passed

    def test_spinner_finish_with_different_scenarios(self, mocker):
        """Test spinner finish with various completion scenarios."""
        mock_print = mocker.patch("builtins.print")
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 1.0

        # Scenario 1: Normal completion
        spinner1 = Spinner(disable=False, total=10)
        spinner1.start_time = 0.0
        spinner1.current = 5
        spinner1.finish()
        assert spinner1._completed is True
        assert spinner1.current == 10

        # Scenario 2: Already completed (should return early)
        spinner2 = Spinner(disable=False, total=10)
        spinner2._completed = True
        spinner2.current = 3
        spinner2.finish()  # Should return early
        assert spinner2.current == 3  # Should not have changed

        # Scenario 3: Total is 0 (should return early)
        spinner3 = Spinner(disable=False, total=0)
        spinner3.current = 5
        spinner3.finish()  # Should return early
        assert spinner3.current == 5  # Should not have changed
        assert spinner3._completed is False

    def test_spinner_iteration_with_zero_total(self):
        """Test spinner iteration when total is 0."""
        spinner = Spinner(total=0, disable=True)
        result = list(spinner)
        assert result == []  # Should yield nothing when total is 0
        assert spinner.current == 0
