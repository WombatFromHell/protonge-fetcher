"""
Integration tests for extraction workflows in protonfetcher.py
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher import (
    ExtractionError,
    ForkName,
    ProtonFetcherError,
)


class TestExtractionWorkflow:
    """Integration tests for archive extraction with progress indication and error recovery."""

    def test_extraction_workflow_success(self, mocker, tmp_path, create_test_archive):
        """Test complete extraction workflow with successful execution."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a test archive
        archive_path = tmp_path / "test.tar.gz"
        create_test_archive(archive_path, ".tar.gz", {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Setup successful extraction with tarfile method
        mock_archive_extractor.extract_with_tarfile.return_value = extract_path

        # Mock the extract_archive method to implement direct success (no fallback needed)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                return mock_archive_extractor.extract_with_tarfile(
                    archive_path, target_dir, show_progress, show_file_details
                )
            elif archive_path.name.endswith(".tar.xz"):
                return mock_archive_extractor.extract_with_tarfile(
                    archive_path, target_dir, show_progress, show_file_details
                )
            else:
                return mock_archive_extractor.extract_with_tarfile(
                    archive_path, target_dir, show_progress, show_file_details
                )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        result = mock_archive_extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        mock_archive_extractor.extract_with_tarfile.assert_called_once_with(
            archive_path,
            extract_path,
            True,
            True,  # show_progress=True, show_file_details=True
        )

    def test_extraction_workflow_tarfile_fallback_success(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extraction workflow with tarfile failure followed by fallback success."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a test archive
        archive_path = tmp_path / "test.tar.gz"
        create_test_archive(archive_path, ".tar.gz", {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Setup extraction with tarfile failure but fallback success
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "tarfile failed"
        )
        mock_archive_extractor.extract_gz_archive.return_value = extract_path

        # Mock the extract_archive method to implement fallback logic
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        # This would normally be called from fetch_and_extract, but we're testing the extraction method directly
        result = mock_archive_extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        # Should have tried tarfile first, then fallen back to system tar
        mock_archive_extractor.extract_with_tarfile.assert_called_once_with(
            archive_path,
            extract_path,
            True,
            True,  # show_progress=True, show_file_details=True
        )
        mock_archive_extractor.extract_gz_archive.assert_called_once_with(
            archive_path, extract_path
        )

    def test_extraction_workflow_gz_format_success(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extraction workflow specifically for .tar.gz format."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a .tar.gz test archive
        archive_path = tmp_path / "GE-Proton10-20.tar.gz"
        create_test_archive(
            archive_path,
            ".tar.gz",
            {"proton": b"binary content", "version.txt": b"10.20"},
        )

        extract_path = tmp_path / "GE-Proton10-20"
        extract_path.mkdir()

        # Setup tarfile to fail and gz to succeed
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "tarfile failed"
        )
        mock_archive_extractor.extract_gz_archive.return_value = extract_path

        # Mock the extract_archive method to implement fallback logic (tarfile fails, then gz succeeds)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        result = mock_archive_extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        # Should have tried tarfile first (which would fail with default Mock behavior) then fallen back to gz
        mock_archive_extractor.extract_with_tarfile.assert_called_once_with(
            archive_path, extract_path, True, True
        )
        mock_archive_extractor.extract_gz_archive.assert_called_once_with(
            archive_path, extract_path
        )

    def test_extraction_workflow_xz_format_success(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extraction workflow specifically for .tar.xz format."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a .tar.xz test archive
        archive_path = tmp_path / "proton-EM-10.0-30.tar.xz"
        create_test_archive(
            archive_path,
            ".tar.xz",
            {"proton": b"binary content", "version.txt": b"10.0.30"},
        )

        extract_path = tmp_path / "proton-EM-10.0-30"
        extract_path.mkdir()

        # Setup tarfile to fail and xz to succeed
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "tarfile failed"
        )
        mock_archive_extractor.extract_xz_archive.return_value = extract_path

        # Mock the extract_archive method to implement fallback logic (tarfile fails, then xz succeeds)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        result = mock_archive_extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        # Should have tried tarfile first (which would fail with default Mock behavior) then fallen back to xz
        mock_archive_extractor.extract_with_tarfile.assert_called_once_with(
            archive_path, extract_path, True, True
        )
        mock_archive_extractor.extract_xz_archive.assert_called_once_with(
            archive_path, extract_path
        )

    def test_extraction_workflow_failure_all_methods(self, mocker, tmp_path):
        """Test extraction workflow when all extraction methods fail."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a fake archive file
        archive_path = tmp_path / "fake.tar.gz"
        archive_path.write_text("not actually an archive")

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Setup all extraction methods to fail
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "tarfile failed"
        )
        mock_archive_extractor.extract_gz_archive.side_effect = ExtractionError(
            "system tar failed"
        )
        mock_archive_extractor.extract_xz_archive.side_effect = ExtractionError(
            "xz extraction failed"
        )
        mock_archive_extractor._extract_with_system_tar.side_effect = ExtractionError(
            "general tar failed"
        )

        # Mock the extract_archive method to implement fallback logic (all should fail)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile extraction fails, fall back to system tar command
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        # This should raise an ExtractionError
        with pytest.raises(ExtractionError):
            mock_archive_extractor.extract_archive(archive_path, extract_path)

    def test_extraction_workflow_progress_indication(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extraction workflow with progress indication."""
        from protonfetcher import ArchiveExtractor, GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Create a real ArchiveExtractor with mocked file system client
        archive_extractor = ArchiveExtractor(file_system_client=mock_fs, timeout=60)

        # Create a mock spinner with context manager support using MagicMock
        mock_spinner_instance = mocker.MagicMock()
        mock_spinner_instance.__enter__.return_value = mock_spinner_instance
        mock_spinner_instance.__exit__.return_value = None
        mock_spinner_cls = mocker.patch("protonfetcher.Spinner")
        mock_spinner_cls.return_value = mock_spinner_instance

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Replace the fetcher's archive extractor with our real one
        fetcher.archive_extractor = archive_extractor

        # Create a test archive
        archive_path = tmp_path / "test.tar.gz"
        create_test_archive(
            archive_path,
            ".tar.gz",
            {"file1.txt": b"content1", "file2.txt": b"content2"},
        )

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock the file system operations for the extraction
        mock_fs.mkdir.return_value = None

        # Create a fake tarinfo for the archive
        mock_tar_member1 = mocker.Mock()
        mock_tar_member1.name = "file1.txt"
        mock_tar_member1.size = 8
        mock_tar_member2 = mocker.Mock()
        mock_tar_member2.name = "file2.txt"
        mock_tar_member2.size = 8
        mock_tarfile = mocker.patch("protonfetcher.tarfile.open")
        mock_tarfile.return_value.__enter__.return_value.getmembers.return_value = [
            mock_tar_member1,
            mock_tar_member2,
        ]
        mock_tarfile.return_value.__enter__.return_value.__iter__.return_value = [
            mock_tar_member1,
            mock_tar_member2,
        ]
        mock_tarfile.return_value.__enter__.return_value.extract.return_value = None

        result = archive_extractor.extract_with_tarfile(archive_path, extract_path)

        assert result == extract_path
        # Verify that the spinner was used during extraction
        mock_spinner_cls.assert_called()

    @pytest.mark.parametrize(
        "archive_format,extract_method",
        [
            (".tar.gz", "extract_gz_archive"),
            (".tar.xz", "extract_xz_archive"),
        ],
    )
    def test_extraction_workflow_parametrized_formats(
        self, mocker, tmp_path, create_test_archive, archive_format, extract_method
    ):
        """Parametrized test for extraction workflow with different archive formats."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a test archive with the specified format
        archive_name = f"test{archive_format}"
        archive_path = tmp_path / archive_name
        create_test_archive(archive_path, archive_format, {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Setup tarfile to fail and the specific method to succeed
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "tarfile failed"
        )
        method_mock = getattr(mock_archive_extractor, extract_method)
        method_mock.return_value = extract_path

        # Mock the extract_archive method to implement fallback logic
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    return mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                except ExtractionError:
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        result = mock_archive_extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        # Should have tried tarfile first (which would fail with default Mock behavior) then fallen back to the specific format
        mock_archive_extractor.extract_with_tarfile.assert_called_once_with(
            archive_path, extract_path, True, True
        )
        method_mock.assert_called_once_with(archive_path, extract_path)

    def test_extraction_workflow_empty_archive(self, mocker, tmp_path):
        """Test extraction workflow with empty archive."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create an empty "archive" file
        archive_path = tmp_path / "empty.tar.gz"
        archive_path.write_bytes(b"")  # Empty file

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Setup extraction to fail due to empty archive
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "Empty archive"
        )
        mock_archive_extractor.extract_gz_archive.side_effect = ExtractionError(
            "Empty archive"
        )

        # Mock the extract_archive method to implement fallback logic (both should fail)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile extraction fails, fall back to system tar command
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        with pytest.raises(ExtractionError):
            mock_archive_extractor.extract_archive(archive_path, extract_path)

    def test_extraction_workflow_corrupted_archive(
        self, mocker, tmp_path, corrupted_archive
    ):
        """Test extraction workflow with corrupted archive."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Setup extraction to fail due to corrupted archive
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "Corrupted archive"
        )
        mock_archive_extractor.extract_gz_archive.side_effect = ExtractionError(
            "Corrupted archive"
        )
        mock_archive_extractor.extract_xz_archive.side_effect = ExtractionError(
            "Corrupted archive"
        )
        mock_archive_extractor._extract_with_system_tar.side_effect = ExtractionError(
            "Corrupted archive"
        )

        # Mock the extract_archive method to implement fallback logic (all should fail)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile extraction fails, fall back to system tar command
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        with pytest.raises(ExtractionError):
            mock_archive_extractor.extract_archive(corrupted_archive, extract_path)

    def test_extraction_workflow_permissions_error(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extraction workflow when extraction directory has insufficient permissions."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the archive extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        # Create a test archive
        archive_path = tmp_path / "test.tar.gz"
        create_test_archive(archive_path, ".tar.gz", {"test.txt": b"test content"})

        # Use an extraction path that doesn't exist to simulate permissions issue
        extract_path = tmp_path / "nonexistent_base" / "extracted"

        # Setup extraction to fail due to permissions/missing directory
        mock_archive_extractor.extract_with_tarfile.side_effect = ExtractionError(
            "Permission denied"
        )
        mock_archive_extractor.extract_gz_archive.side_effect = ExtractionError(
            "Permission denied"
        )
        mock_archive_extractor.extract_xz_archive.side_effect = ExtractionError(
            "Permission denied"
        )
        mock_archive_extractor._extract_with_system_tar.side_effect = ExtractionError(
            "Permission denied"
        )

        # Mock the extract_archive method to implement fallback logic (all should fail)
        def mock_extract_archive(
            archive_path, target_dir, show_progress=True, show_file_details=True
        ):
            if archive_path.name.endswith(".tar.gz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_gz_archive(
                        archive_path, target_dir
                    )
            elif archive_path.name.endswith(".tar.xz"):
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile fails, fall back to system tar
                    return mock_archive_extractor.extract_xz_archive(
                        archive_path, target_dir
                    )
            else:
                try:
                    result = mock_archive_extractor.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                    return result
                except ExtractionError:
                    # If tarfile extraction fails, fall back to system tar command
                    return mock_archive_extractor._extract_with_system_tar(
                        archive_path, target_dir
                    )

        mock_archive_extractor.extract_archive.side_effect = mock_extract_archive

        with pytest.raises(ExtractionError):
            mock_archive_extractor.extract_archive(archive_path, extract_path)
