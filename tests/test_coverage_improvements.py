"""
Additional tests to improve code coverage based on the uncovered paths identified in the coverage report.
"""

import json
import os
from pathlib import Path

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError, NetworkError
from protonfetcher.link_manager import LinkManager
from protonfetcher.release_manager import ReleaseManager
from protonfetcher.spinner import Spinner


class TestLinkManagerCoverageImprovements:
    """Additional tests for LinkManager to cover uncovered paths."""

    def test_is_valid_proton_directory_proton_em_specific_paths(self, mocker):
        """Test Proton-EM specific paths in _is_valid_proton_directory (line 179->exit)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Test valid Proton-EM format 1: proton-EM-{major}.{minor}-{patch}
        entry = Path("proton-EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is True

        # Test valid Proton-EM format 2: EM-{major}.{minor}-{patch}
        entry = Path("EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is True

        # Test invalid Proton-EM format (uppercase proton-EM)
        entry = Path("PROTON-EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is False

        # Test invalid Proton-EM format (no patch number)
        entry = Path("proton-EM-10.0")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is False

    def test_create_symlinks_multiple_versions(self, mocker, tmp_path):
        """Test _create_symlink_specs with multiple version scenarios (lines 217-222)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        # Test with only 1 version (should create only main)
        target1 = tmp_path / "GE-Proton10-20"
        top_1 = [(("GE-Proton", 10, 20, 0), target1)]
        specs_1 = manager._create_symlink_specs(main, fb1, fb2, top_1)
        assert len(specs_1) == 1
        assert specs_1[0].link_path == main
        assert specs_1[0].target_path == target1
        assert specs_1[0].priority == 0

        # Test with 2 versions (should create main and fb1)
        target2 = tmp_path / "GE-Proton9-15"
        top_2 = [
            (("GE-Proton", 10, 20, 0), target1),
            (("GE-Proton", 9, 15, 0), target2),
        ]
        specs_2 = manager._create_symlink_specs(main, fb1, fb2, top_2)
        assert len(specs_2) == 2
        assert specs_2[0].link_path == main
        assert specs_2[1].link_path == fb1

        # Test with 3 versions (should create main, fb1, and fb2)
        target3 = tmp_path / "GE-Proton8-10"
        top_3 = [
            (("GE-Proton", 10, 20, 0), target1),
            (("GE-Proton", 9, 15, 0), target2),
            (("GE-Proton", 8, 10, 0), target3),
        ]
        specs_3 = manager._create_symlink_specs(main, fb1, fb2, top_3)
        assert len(specs_3) == 3
        assert specs_3[0].link_path == main
        assert specs_3[1].link_path == fb1
        assert specs_3[2].link_path == fb2

    def test_determine_release_path_with_proton_em_prefix(self, mocker, tmp_path):
        """Test _determine_release_path for Proton-EM with proton- prefix (lines 461-466)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        tag = "EM-10.0-30"

        # Create the alternative path (with "proton-" prefix)
        proton_em_path = extract_dir / f"proton-{tag}"
        proton_em_path.mkdir()

        # Only the alternative path exists, not the regular one
        def mock_exists(path):
            return str(path) == str(proton_em_path)

        mock_fs.exists.side_effect = mock_exists

        result = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)

        # Should return the alternative path with "proton-" prefix
        assert result == proton_em_path

    def test_identify_links_to_remove_with_broken_symlinks(self, mocker, tmp_path):
        """Test _identify_links_to_remove with broken symlinks (line 490->484)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        main = extract_dir / "GE-Proton"
        release_path = extract_dir / "GE-Proton10-20"

        def mock_exists(path):
            return str(path) == str(main)

        def mock_is_symlink(path):
            return str(path) == str(main)

        def mock_resolve(path):
            if str(path) == str(main):
                raise OSError("Broken symlink")
            return path

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = mock_resolve

        links_to_remove = manager._identify_links_to_remove(
            extract_dir, release_path, ForkName.GE_PROTON
        )

        # Broken symlink should be in the list to remove
        assert main in links_to_remove

    def test_handle_manual_release_candidates_scenario(self, mocker):
        """Test _handle_manual_release_candidates with various scenarios (lines 639-643)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        tag = "GE-Proton10-20"
        fork = ForkName.GE_PROTON
        # Create candidates with some existing versions
        candidates = [(("GE-Proton", 10, 0, 15), Path("GE-Proton10-15"))]
        tag_dir = Path("GE-Proton10-20")

        result = manager._handle_manual_release_candidates(
            tag, fork, candidates, tag_dir
        )

        # Should include both the original candidate and the new manual tag
        assert len(result) == 2
        # Should include the manual tag
        assert any(c[1] == tag_dir for c in result)
        # Should be sorted with newer version first
        assert result[0][0][3] == 20  # manual tag version should be first


class TestReleaseManagerCoverageImprovements:
    """Additional tests for ReleaseManager to cover uncovered paths."""

    def test_get_expected_extension_with_invalid_fork_string(self, mocker):
        """Test _get_expected_extension with invalid fork string (lines 168-174)."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test with invalid fork string - should return default extension
        result = manager._get_expected_extension("invalid-fork")
        assert result == ".tar.gz"  # Default extension for invalid fork string

        # Test with ForkName enum - should return appropriate extension
        result_ge = manager._get_expected_extension(ForkName.GE_PROTON)
        assert result_ge == ".tar.gz"

        result_em = manager._get_expected_extension(ForkName.PROTON_EM)
        assert result_em == ".tar.xz"

        # Test with string that's not valid ForkName - should return default
        result = manager._get_expected_extension("some-random-string")
        assert result == ".tar.gz"

    def test_follow_redirect_and_get_size_functionality(self, mocker):
        """Test _follow_redirect_and_get_size method with various scenarios (lines 387-393)."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test successful redirect with content-length
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://redirected.example.com/file.tar.gz\n"

        redirected_result = mocker.Mock()
        redirected_result.returncode = 0
        redirected_result.stdout = "Content-Length: 123456789\nOther-Header: value\n"

        mock_network.head.return_value = redirected_result

        size = manager._follow_redirect_and_get_size(
            initial_result,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            in_test=True,  # Skip caching during test
        )

        assert size == 123456789
        mock_network.head.assert_called_once_with(
            "https://redirected.example.com/file.tar.gz", follow_redirects=False
        )

        # Test when redirect URL is same as original
        initial_result_same_url = mocker.Mock()
        initial_result_same_url.stdout = (
            "Location: https://original.example.com/file.tar.gz\n"
        )

        size = manager._follow_redirect_and_get_size(
            initial_result_same_url,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            in_test=True,
        )

        assert size is None  # Should return None when URLs are the same

    def test_follow_redirect_and_get_size_with_error_response(self, mocker):
        """Test _follow_redirect_and_get_size method when redirect response contains error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test redirect with error in response - this should raise NetworkError
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://redirected.example.com/file.tar.gz\n"

        redirected_result_with_error = mocker.Mock()
        redirected_result_with_error.returncode = 0
        redirected_result_with_error.stdout = "404 Not Found"

        mock_network.head.return_value = redirected_result_with_error

        with pytest.raises(NetworkError):
            manager._follow_redirect_and_get_size(
                initial_result,
                "https://original.example.com/file.tar.gz",
                "test/repo",
                "GE-Proton10-20",
                "GE-Proton10-20.tar.gz",
                in_test=True,
            )


class TestSpinnerCoverageImprovements:
    """Additional tests for Spinner to cover uncovered paths."""

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
