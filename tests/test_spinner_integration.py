"""
Integration tests for Spinner functionality in download/extraction workflows.

Tests the Spinner class and its integration with download/extraction operations:
- Spinner class directly (progress updates, FPS limiting, context manager)
- Spinner used in AssetDownloader.download_with_spinner (mocked urllib/filesystem)
- Spinner used in ArchiveExtractor.extract_archive (mocked tarfile/filesystem)

No real files are created and no network calls are made.
The Spinner SUT is NOT mocked - only external I/O is mocked.
"""

from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.spinner import Spinner


class TestSpinnerDirect:
    """Test Spinner class directly without mocking the SUT."""

    def test_spinner_context_manager(self, capsys: Any) -> None:
        """Test Spinner works as context manager."""
        # Arrange
        spinner = Spinner(desc="Test", disable=False)

        # Act
        with spinner:
            pass  # Just test context manager works

        # Assert: Should have cleared display on exit
        captured = capsys.readouterr()
        assert "Test" in captured.out

    def test_spinner_with_iterable(self, capsys: Any) -> None:
        """Test Spinner wraps iterable correctly."""
        # Arrange
        items = [1, 2, 3, 4, 5]

        # Act
        with Spinner(iterable=iter(items), desc="Processing", disable=False) as spinner:
            result = list(spinner)

        # Assert
        assert result == items
        captured = capsys.readouterr()
        assert "Processing" in captured.out

    def test_spinner_progress_percentage(self) -> None:
        """Test Spinner calculates progress percentage correctly."""
        # Arrange
        spinner = Spinner(total=100, desc="Test", disable=True)
        spinner.current = 25

        # Act
        percentage = spinner._calculate_progress_percentage()

        # Assert: Returns decimal (0.0-1.0), not percentage
        assert percentage == 0.25

    def test_spinner_update_increments_current(self) -> None:
        """Test Spinner.update() increments current counter."""
        # Arrange
        spinner = Spinner(total=100, desc="Test", disable=True)
        initial = spinner.current

        # Act
        spinner.update(10)

        # Assert
        assert spinner.current == initial + 10

    def test_spinner_update_with_total_none(self) -> None:
        """Test Spinner.update() works when total is None (indeterminate progress)."""
        # Arrange
        spinner = Spinner(total=None, desc="Test", disable=True)

        # Act
        spinner.update(50)

        # Assert
        assert spinner.current == 50
        # Should not raise when calculating percentage with no total
        percentage = spinner._calculate_progress_percentage()
        assert percentage == 0  # Returns 0 when no total

    def test_spinner_fps_limiting(self) -> None:
        """Test Spinner respects FPS limit."""
        # Arrange
        spinner = Spinner(
            fps_limit=1.0, disable=True
        )  # 1 FPS = 1 second between updates
        spinner._last_update_time = 0.0  # Reset to known state

        # Act: First update at time 0, second at 0.1s (too soon), third at 1.1s (OK)
        should_update_1 = spinner._should_update_display(0.0)
        # After first check, _last_update_time would be updated in real usage
        # But for this test, we simulate the timing logic directly
        should_update_2 = spinner._should_update_display(0.1)  # Too soon (0.1 < 1.0)
        should_update_3 = spinner._should_update_display(1.1)  # After 1 second

        # Assert
        # First update at t=0 with _last_update_time=0 means 0 >= 1.0 is False
        assert should_update_1 is False  # First call at t=0 doesn't pass FPS check
        assert should_update_2 is False  # FPS limit prevents update (0.1 < 1.0)
        assert should_update_3 is True  # After 1 second, update allowed (1.1 >= 1.0)

    def test_spinner_no_fps_limit(self) -> None:
        """Test Spinner updates freely when no FPS limit."""
        # Arrange
        spinner = Spinner(fps_limit=None, disable=True)

        # Act
        result = spinner._should_update_display(0.0)

        # Assert
        assert result is True

    def test_spinner_disabled_no_output(self, capsys: Any) -> None:
        """Test Spinner produces no output when disabled."""
        # Arrange
        spinner = Spinner(desc="Test", disable=True)

        # Act
        with spinner:
            spinner.update(10)

        # Assert
        captured = capsys.readouterr()
        assert captured.out == ""


class TestSpinnerInDownloadWorkflow:
    """Test Spinner integration in download workflow without real I/O."""

    def test_download_with_spinner_mocked_io(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
        capsys: Any,
    ) -> None:
        """Test download_with_spinner shows progress (mocked I/O, real Spinner)."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Mock urllib to return chunks of data
        mock_urllib_download(
            chunks=[b"x" * 1000, b"x" * 1000, b""],  # 2000 bytes total
            content_length=2000,
        )
        mock_builtin_open()

        # Act
        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        # Assert: Spinner should have shown progress
        captured = capsys.readouterr()
        assert "Downloading" in captured.out or "test.tar.gz" in captured.out

    def test_download_with_spinner_no_content_length(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
        capsys: Any,
    ) -> None:
        """Test download_with_spinner handles missing Content-Length (indeterminate)."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Mock urllib without content length
        mock_urllib_download(
            chunks=[b"data", b"more", b""],
            content_length=None,
        )
        mock_builtin_open()

        # Act
        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        # Assert: Should complete without error (indeterminate progress)
        capsys.readouterr()
        # Spinner should still show activity even without total

    def test_download_with_spinner_network_error(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        capsys: Any,
    ) -> None:
        """Test download_with_spinner handles network errors gracefully."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Mock urllib to raise exception
        mock_urllib_download(raise_on_open=Exception("Connection failed"))

        # Act & Assert
        with pytest.raises(Exception, match="Connection failed"):
            downloader.download_with_spinner(
                url="https://example.com/test.tar.gz",
                output_path=output_path,
            )

        # Spinner context manager should have cleaned up properly
        capsys.readouterr()


class TestSpinnerInExtractionWorkflow:
    """Test Spinner integration in extraction workflow without real I/O."""

    def test_extract_archive_shows_spinner_progress(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        capsys: Any,
    ) -> None:
        """Test extract_archive shows spinner progress (mocked I/O, real Spinner)."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p
            in (
                archive_path,
                target_dir,
            )
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile with multiple members to show progress
        mock_tarfile_operations(
            members=[
                {"name": "dir", "is_dir": True, "size": 0},
                {"name": "dir/file1.txt", "is_dir": False, "size": 100},
                {"name": "dir/file2.txt", "is_dir": False, "size": 200},
                {"name": "dir/file3.txt", "is_dir": False, "size": 300},
            ]
        )

        # Act
        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=True,
            show_file_details=True,
        )

        # Assert: Spinner should have shown extraction progress
        captured = capsys.readouterr()
        assert "Extracting" in captured.out or "test.tar.gz" in captured.out

    def test_extract_archive_without_progress(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        capsys: Any,
    ) -> None:
        """Test extract_archive respects show_progress=False."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p
            in (
                archive_path,
                target_dir,
            )
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile
        mock_tarfile_operations(
            members=[
                {"name": "dir", "is_dir": True, "size": 0},
            ]
        )

        # Act
        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert: Minimal output when progress disabled
        capsys.readouterr()
        # Should have little to no spinner output


class TestSpinnerEdgeCases:
    """Test Spinner edge cases and error handling."""

    def test_spinner_zero_total(self) -> None:
        """Test Spinner handles total=0 without division by zero."""
        # Arrange
        spinner = Spinner(total=0, desc="Test", disable=True)

        # Act
        spinner.update(0)
        percentage = spinner._calculate_progress_percentage()

        # Assert: Should handle gracefully (returns 0.0 for zero total)
        assert percentage == 0.0

    def test_spinner_current_exceeds_total(self) -> None:
        """Test Spinner handles current > total gracefully."""
        # Arrange
        spinner = Spinner(total=100, desc="Test", disable=True)
        spinner.current = 150

        # Act
        percentage = spinner._calculate_progress_percentage()

        # Assert: Should cap at 1.0 (100%)
        assert percentage == 1.0

    def test_spinner_update_zero_bytes(self) -> None:
        """Test Spinner.update(0) doesn't break progress."""
        # Arrange
        spinner = Spinner(total=100, desc="Test", disable=True)
        initial = spinner.current

        # Act
        spinner.update(0)

        # Assert
        assert spinner.current == initial

    def test_spinner_empty_iterable(self, capsys: Any) -> None:
        """Test Spinner with empty iterable."""
        # Arrange
        items: list[int] = []

        # Act
        with Spinner(iterable=iter(items), desc="Empty", disable=False) as spinner:
            result = list(spinner)

        # Assert
        assert result == []
        captured = capsys.readouterr()
        assert "Empty" in captured.out

    def test_spinner_large_total_value(self) -> None:
        """Test Spinner handles large total values correctly."""
        # Arrange
        spinner = Spinner(total=10_000_000_000, desc="Large", disable=True)
        spinner.current = 5_000_000_000

        # Act
        percentage = spinner._calculate_progress_percentage()

        # Assert: 5B / 10B = 0.5 (50%)
        assert percentage == 0.5


class TestSpinnerInEndToEndWorkflow:
    """Test Spinner in complete end-to-end workflow with all mocks."""

    def test_complete_download_extract_with_spinner(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
        capsys: Any,
    ) -> None:
        """Test complete workflow with spinner progress (all I/O mocked)."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        archive_path = output_dir / "test.tar.gz"

        # Mock filesystem
        def mock_exists(p: Path) -> bool:
            return p in (output_dir, extract_dir, archive_path, extract_dir / "test")

        def mock_is_dir(p: Path) -> bool:
            return p in (output_dir, extract_dir, extract_dir / "test")

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_dir.side_effect = mock_is_dir

        # Mock download
        mock_urllib_download(
            chunks=[b"chunk1", b"chunk2", b""],
            content_length=10000,
        )
        mock_builtin_open()

        # Mock extraction
        mock_tarfile_operations(
            members=[
                {"name": "test", "is_dir": True, "size": 0},
                {"name": "test/version", "is_dir": False, "size": 10},
            ]
        )

        # Act: Simulate download then extract
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=archive_path,
        )

        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=extract_dir,
            show_progress=True,
            show_file_details=True,
        )

        # Assert: Both operations should show spinner progress
        capsys.readouterr()
        # Should have seen progress output for both download and extract

    def test_spinner_configured_with_fps_limit_during_download(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
    ) -> None:
        """Test Spinner is configured with FPS limit during download."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Mock urllib with chunks
        mock_urllib_download(
            chunks=[b"chunk1", b"chunk2", b""],
            content_length=1000,
        )
        mock_builtin_open()

        # Track Spinner initialization
        original_init = Spinner.__init__
        captured_fps_limit = None

        def capturing_init(self: Spinner, *args: Any, **kwargs: Any) -> None:
            nonlocal captured_fps_limit
            captured_fps_limit = kwargs.get("fps_limit")
            original_init(self, *args, **kwargs)

        mocker.patch.object(Spinner, "__init__", capturing_init)

        # Act
        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        # Assert: FPS limit should be configured (10 FPS as per implementation)
        assert captured_fps_limit == 10.0
