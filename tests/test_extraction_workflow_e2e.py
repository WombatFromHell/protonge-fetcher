"""
End-to-end tests for archive extraction and asset download workflows.

Tests the complete extraction workflow using comprehensive mocking:
- Mock filesystem protocol (not the SUT)
- Mock tarfile and subprocess (external dependencies)
- Mock urllib (network operations)
- No real file I/O - all paths are mock Path objects
"""

import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.exceptions import ExtractionError, NetworkError


class TestTarGzExtraction:
    """Test .tar.gz archive extraction."""

    def test_extract_tar_gz_with_mock(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting a .tar.gz archive using filesystem mocks."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/GE-Proton10-20.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Use fixture to mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "GE-Proton10-20", "is_dir": True, "size": 0},
                {"name": "GE-Proton10-20/version", "is_dir": False, "size": 14},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == target_dir

    def test_extract_tar_gz_nonexistent_archive(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test extracting non-existent archive raises error."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        nonexistent_archive = Path("/mock/nonexistent.tar.gz")

        # Mock filesystem to say archive doesn't exist
        mock_filesystem_client.exists.return_value = False

        # Act & Assert
        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=nonexistent_archive,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )


class TestTarXzExtraction:
    """Test .tar.xz archive extraction."""

    def test_extract_tar_xz_with_mock(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting a .tar.xz archive using filesystem mocks."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/proton-EM-10.0-30.tar.xz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Use fixture to mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "proton-EM-10.0-30", "is_dir": True, "size": 0},
                {"name": "proton-EM-10.0-30/version", "is_dir": False, "size": 11},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == target_dir


class TestSystemTarFallback:
    """Test system tar fallback when tarfile fails."""

    def test_system_tar_fallback_gz(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test system tar fallback for .tar.gz extraction."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile.open to raise exception
        mock_tarfile_operations(raise_on_open=Exception("tarfile failed"))

        # Mock subprocess.run for system tar
        mock_run = mock_subprocess_tar(returncode=0, stdout="", stderr="")

        # Act
        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert: Should have tried system tar
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert "tar" in call_args

    def test_system_tar_fallback_xz(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test system tar fallback for .tar.xz extraction."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.xz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile.open to raise exception
        mock_tarfile_operations(raise_on_open=Exception("tarfile failed"))

        # Mock subprocess.run for system tar
        mock_run = mock_subprocess_tar(returncode=0, stdout="", stderr="")

        # Act
        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert mock_run.called

    def test_system_tar_fallback_failure(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test system tar fallback failure raises ExtractionError."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: p == archive_path

        # Mock tarfile.open to raise exception
        mock_tarfile_operations(raise_on_open=Exception("tarfile failed"))

        # Mock subprocess.run to fail
        mock_subprocess_tar(returncode=2, stdout="", stderr="tar failed")

        # Act & Assert
        with pytest.raises(ExtractionError, match="tar failed"):
            extractor.extract_archive(
                archive_path=archive_path,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )


class TestArchiveInfo:
    """Test archive information retrieval."""

    def test_get_archive_info_tar_gz_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test getting info from .tar.gz archive using mocks."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem to say archive exists
        mock_filesystem_client.exists.return_value = True

        # Use fixture to mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "test_dir", "is_dir": True, "size": 0},
                {"name": "test_dir/file.txt", "is_dir": False, "size": 1024},
            ]
        )

        # Act
        info = extractor.get_archive_info(archive_path)

        # Assert
        assert "file_count" in info
        assert "total_size" in info
        assert info["file_count"] == 2
        assert info["total_size"] == 1024

    def test_get_archive_info_tar_xz_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test getting info from .tar.xz archive using mocks."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        archive_path = Path("/mock/test.tar.xz")

        # Mock filesystem
        mock_filesystem_client.exists.return_value = True

        # Use fixture to mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "test_dir", "is_dir": True, "size": 0},
            ]
        )

        # Act
        info = extractor.get_archive_info(archive_path)

        # Assert
        assert "file_count" in info
        assert "total_size" in info
        assert info["file_count"] == 1
        assert info["total_size"] == 0

    def test_get_archive_info_empty_archive(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test getting info from empty archive."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        archive_path = Path("/mock/empty.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.return_value = True

        # Use fixture to mock tarfile operations with empty members
        mock_tarfile_operations(members=[])

        # Act
        info = extractor.get_archive_info(archive_path)

        # Assert
        assert info["file_count"] == 0
        assert info["total_size"] == 0

    def test_get_archive_info_read_error(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test getting info from corrupted archive raises error."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        archive_path = Path("/mock/corrupted.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.return_value = True

        # Mock tarfile to raise error
        mock_tarfile_operations(raise_on_open=tarfile.TarError("corrupted"))

        # Act & Assert
        with pytest.raises(ExtractionError, match="Error reading archive"):
            extractor.get_archive_info(archive_path)


class TestAssetDownload:
    """Test asset downloading with progress."""

    def test_download_asset_with_spinner(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
    ) -> None:
        """Test downloading asset with progress spinner - no real files."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Use fixtures to mock urllib and builtins.open
        mock_urllib_download(
            chunks=[b"chunk1", b"chunk2", b""],
            content_length=1048576,
        )
        _, written_data = mock_builtin_open()

        # Act
        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        # Assert - check what was written via mock
        assert b"".join(written_data) == b"chunk1chunk2"

    def test_download_asset_network_error(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Test handling network error during download."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Mock urllib to raise exception
        mock_urllib_download(raise_on_open=Exception("Network failed"))

        # Act & Assert
        with pytest.raises(NetworkError, match="Failed to download"):
            downloader.download_with_spinner(
                url="https://example.com/test.tar.gz",
                output_path=output_path,
            )

    def test_download_asset_with_spinner_no_content_length(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
    ) -> None:
        """Test downloading asset without Content-Length header."""
        # Arrange
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        # Mock urllib without content length
        mock_urllib_download(
            chunks=[b"data", b""],
            content_length=None,
        )
        _, written_data = mock_builtin_open()

        # Act
        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        # Assert
        assert b"".join(written_data) == b"data"


class TestDownloadIntegration:
    """Test download and extraction integration."""

    def test_download_and_extract_workflow_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test complete download and extraction workflow using mocks."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)

        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        archive_path = output_dir / "GE-Proton10-20.tar.gz"

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p
            in (
                archive_path,
                output_dir,
                extract_dir,
            )
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: (
            p in (output_dir, extract_dir)
        )

        # Mock download to succeed
        def mock_download(
            url: str, output_path: Path, headers: Any = None
        ) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_network_client.download.side_effect = mock_download

        # Mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "GE-Proton10-20", "is_dir": True, "size": 0},
            ]
        )

        # Act: Download
        download_result = mock_network_client.download(
            url="https://example.com/GE-Proton10-20.tar.gz",
            output_path=archive_path,
        )

        assert download_result.returncode == 0

        # Act: Extract
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=extract_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == extract_dir


class TestProgressIndication:
    """Test progress indication during extraction."""

    def test_extraction_without_progress_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extraction with progress disabled."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "test_dir", "is_dir": True, "size": 0},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == target_dir

    def test_extraction_with_file_details_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extraction with file details displayed."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "test_dir", "is_dir": True, "size": 0},
                {"name": "test_dir/file.txt", "is_dir": False, "size": 1024},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=True,
            show_file_details=True,
        )

        # Assert
        assert result_path == target_dir


class TestExtractionEdgeCases:
    """Test edge cases in extraction."""

    def test_extract_to_existing_directory_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting to directory that already has content."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        # Mock filesystem - directory exists
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "test_dir", "is_dir": True, "size": 0},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == target_dir

    def test_extract_corrupted_archive_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting corrupted archive raises error."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        corrupted = Path("/mock/corrupted.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: p == corrupted

        # Mock tarfile to fail
        mock_tarfile_operations(raise_on_open=tarfile.TarError("corrupted"))

        # Act & Assert
        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=corrupted,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )

    def test_extract_unknown_format_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test extracting unknown archive format."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        unknown = Path("/mock/archive.zip")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: p == unknown

        # Mock subprocess to fail for unknown format
        mock_subprocess_tar(returncode=2, stdout="", stderr="Unknown format")

        # Act & Assert
        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=unknown,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )

    def test_extract_directories_only_archive(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting archive with only directories (no files)."""
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/dirs_only.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile with directories only
        mocks = mock_tarfile_operations(
            members=[
                {"name": "empty_dir", "is_dir": True, "size": 0},
                {"name": "another_dir", "is_dir": True, "size": 0},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert - verify tarfile.open was called (mocked, no real extraction)
        assert result_path == target_dir
        assert mocks["tarfile_mock"].called

    def test_extract_archive_with_large_file_entry_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extraction handles archive entries with large size values (mocked).

        Verifies that the extraction workflow processes tar members with large
        size attributes without special handling - all I/O is mocked, no real
        files are created.
        """
        # Arrange
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/archive.tar.gz")

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        # Mock tarfile with a file entry reporting large size (100MB)
        mocks = mock_tarfile_operations(
            members=[
                {"name": "data.bin", "is_dir": False, "size": 104857600},
            ]
        )

        # Act
        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        # Assert - verify extraction completed using mocks (no real I/O)
        assert result_path == target_dir
        assert mocks["tarfile_mock"].called
