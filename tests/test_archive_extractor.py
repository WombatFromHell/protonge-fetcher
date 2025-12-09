"""
Unit tests for ArchiveExtractor in protonfetcher.py
"""

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.exceptions import ExtractionError


class TestArchiveExtractor:
    """Tests for ArchiveExtractor class."""

    def test_init(self, mocker):
        """Test ArchiveExtractor initialization."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)
        assert extractor.file_system_client == mock_fs

    @pytest.mark.parametrize(
        "extension,files",
        [
            (".tar.gz", {"test.txt": b"test content"}),
            (".tar.xz", {"test.txt": b"test content"}),
            (".tar.gz", {"file1.txt": b"content1", "file2.txt": b"content2"}),
            (
                ".tar.xz",
                {
                    "file1.txt": b"content1",
                    "file2.txt": b"content2",
                    "subdir/file3.txt": b"content3",
                },
            ),
        ],
    )
    def test_extract_with_tarfile_success(
        self, mocker, tmp_path, create_test_archive, extension, files
    ):
        """Test extract_with_tarfile method with successful extraction for both formats and various file contents."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with appropriate extension and files
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, files)

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock the spinner behavior
        mock_spinner = mocker.patch("protonfetcher.archive_extractor.Spinner")
        mock_spinner_instance = mocker.Mock()
        mock_spinner.return_value.__enter__.return_value = mock_spinner_instance

        result = extractor.extract_with_tarfile(archive_path, extract_path)

        assert result == extract_path
        # Verify that Spinner was created
        mock_spinner.assert_called()

    def test_extract_with_tarfile_invalid_archive(self, mocker, tmp_path):
        """Test extract_with_tarfile with invalid archive."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create an invalid archive
        invalid_archive = tmp_path / "invalid.tar.gz"
        invalid_archive.write_bytes(b"not a valid archive")

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        with pytest.raises(ExtractionError):
            extractor.extract_with_tarfile(invalid_archive, extract_path)

    def test_extract_with_tarfile_missing_file(self, mocker, tmp_path):
        """Test extract_with_tarfile with missing archive file."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        missing_archive = tmp_path / "missing.tar.gz"
        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        with pytest.raises(ExtractionError):
            extractor.extract_with_tarfile(missing_archive, extract_path)

    @pytest.mark.parametrize("extension", [".tar.gz", ".tar.xz"])
    def test_extract_archive_success(
        self, mocker, tmp_path, create_test_archive, extension
    ):
        """Test extract_gz_archive and extract_xz_archive methods with successful extraction."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with the appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock subprocess.run to simulate tar command
        mock_subprocess = mocker.patch("subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Call the appropriate method based on the extension
        if extension == ".tar.gz":
            result = extractor.extract_gz_archive(archive_path, extract_path)
        else:  # .tar.xz
            result = extractor.extract_xz_archive(archive_path, extract_path)

        assert result == extract_path
        mock_subprocess.assert_called()

    @pytest.mark.parametrize(
        "extension,error_message",
        [
            (".tar.gz", "tar: Error extracting archive"),
            (".tar.xz", "tar: Error extracting archive"),
            (".tar.gz", "gzip: parse error"),
            (".tar.xz", "xz: Compressed data is corrupt"),
        ],
    )
    def test_extract_archive_failure(
        self, mocker, tmp_path, create_test_archive, extension, error_message
    ):
        """Test extract_gz_archive and extract_xz_archive with extraction failure for various error messages."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with the appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock subprocess.run to simulate tar command failure
        mock_subprocess = mocker.patch("subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = 1
        mock_result.stderr = error_message
        mock_subprocess.return_value = mock_result

        # Call the appropriate method based on the extension
        if extension == ".tar.gz":
            with pytest.raises(ExtractionError):
                extractor.extract_gz_archive(archive_path, extract_path)
        else:  # .tar.xz
            with pytest.raises(ExtractionError):
                extractor.extract_xz_archive(archive_path, extract_path)

    def test_extract_archive_with_tarfile_success(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extract_archive method with tarfile extraction (success)."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive
        archive_path = tmp_path / "test.tar.gz"
        create_test_archive(archive_path, ".tar.gz", {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock the extract_with_tarfile method to succeed
        mock_extract_with_tarfile = mocker.patch.object(
            extractor, "extract_with_tarfile", return_value=extract_path
        )

        result = extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        mock_extract_with_tarfile.assert_called_once_with(archive_path, extract_path)

    def test_extract_archive_with_tarfile_fallback_success(
        self, mocker, tmp_path, create_test_archive
    ):
        """Test extract_archive method with tarfile failure followed by fallback success."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive
        archive_path = tmp_path / "test.tar.gz"
        create_test_archive(archive_path, ".tar.gz", {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock the extract_with_tarfile method to fail, then extract_gz_archive to succeed
        mock_extract_with_tarfile = mocker.patch.object(
            extractor,
            "extract_with_tarfile",
            side_effect=ExtractionError("tarfile failed"),
        )
        mock_extract_gz = mocker.patch.object(
            extractor, "extract_gz_archive", return_value=extract_path
        )

        result = extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        mock_extract_with_tarfile.assert_called_once_with(archive_path, extract_path)
        mock_extract_gz.assert_called_once_with(archive_path, extract_path)

    @pytest.mark.parametrize(
        "extension,extract_method",
        [(".tar.gz", "extract_gz_archive"), (".tar.xz", "extract_xz_archive")],
    )
    def test_extract_archive_format_specific_success(
        self, mocker, tmp_path, create_test_archive, extension, extract_method
    ):
        """Test extract_archive fallback to format-specific method when tarfile extraction fails."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock extract_with_tarfile to fail, then format-specific method to succeed
        mock_extract_with_tarfile = mocker.patch.object(
            extractor,
            "extract_with_tarfile",
            side_effect=ExtractionError("tarfile extraction failed"),
        )
        mock_extract_format = mocker.patch.object(
            extractor, extract_method, return_value=extract_path
        )

        result = extractor.extract_archive(archive_path, extract_path)

        assert result == extract_path
        mock_extract_with_tarfile.assert_called_once_with(archive_path, extract_path)
        mock_extract_format.assert_called_once_with(archive_path, extract_path)

    def test_extract_archive_unsupported_format(self, mocker, tmp_path):
        """Test extract_archive with unsupported archive format."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a file with unsupported extension
        archive_path = tmp_path / "test.zip"
        archive_path.write_text("dummy content")

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock all extraction methods to fail
        mocker.patch.object(
            extractor,
            "extract_with_tarfile",
            side_effect=ExtractionError("Not supported"),
        )
        mocker.patch.object(
            extractor,
            "_extract_with_system_tar",
            side_effect=ExtractionError("Not supported"),
        )

        with pytest.raises(ExtractionError):
            extractor.extract_archive(archive_path, extract_path)

    @pytest.mark.parametrize("extension", [".tar.gz", ".tar.xz"])
    def test_get_archive_info_success(
        self, mocker, tmp_path, create_test_archive, extension
    ):
        """Test get_archive_info method with successful extraction of metadata for both formats."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(
            archive_path,
            extension,
            {
                "file1.txt": b"content1",
                "file2.txt": b"content2",
                "subdir/file3.txt": b"content3",
            },
        )

        info = extractor.get_archive_info(archive_path)

        assert info is not None
        assert info["file_count"] > 0
        assert info["total_size"] > 0

    def test_get_archive_info_invalid_archive(self, mocker, tmp_path):
        """Test get_archive_info with invalid archive."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create an invalid archive
        invalid_archive = tmp_path / "invalid.tar.gz"
        invalid_archive.write_bytes(b"not a valid archive")

        with pytest.raises(ExtractionError):
            extractor.get_archive_info(invalid_archive)

    @pytest.mark.parametrize("extension", [".tar.gz", ".tar.xz"])
    def test_is_tar_file_true(self, mocker, tmp_path, create_test_archive, extension):
        """Test is_tar_file method with valid tar file for both formats."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, {"test.txt": b"test content"})

        result = extractor.is_tar_file(archive_path)
        assert result is True

    def test_is_tar_file_false(self, mocker, tmp_path):
        """Test is_tar_file method with non-tar file."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a non-tar file
        non_tar_file = tmp_path / "not_tar.txt"
        non_tar_file.write_bytes(b"not a tar file")

        result = extractor.is_tar_file(non_tar_file)
        assert result is False

    def test_is_tar_file_missing_file(self, mocker, tmp_path):
        """Test is_tar_file method with missing file."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        missing_file = tmp_path / "missing_file.tar.gz"

        result = extractor.is_tar_file(missing_file)
        assert result is False

    @pytest.mark.parametrize("extension", [".tar.gz", ".tar.xz"])
    def test_extract_with_system_tar_success(
        self, mocker, tmp_path, create_test_archive, extension
    ):
        """Test _extract_with_system_tar method with successful extraction for both formats."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock subprocess.run to simulate tar command
        mock_subprocess = mocker.patch("subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = extractor._extract_with_system_tar(archive_path, extract_path)

        assert result == extract_path
        mock_subprocess.assert_called()

    @pytest.mark.parametrize("extension", [".tar.gz", ".tar.xz"])
    def test_extract_with_system_tar_failure(
        self, mocker, tmp_path, create_test_archive, extension
    ):
        """Test _extract_with_system_tar with extraction failure for both formats."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a test archive with appropriate extension
        archive_path = tmp_path / f"test{extension}"
        create_test_archive(archive_path, extension, {"test.txt": b"test content"})

        extract_path = tmp_path / "extracted"
        extract_path.mkdir()

        # Mock subprocess.run to simulate tar command failure
        mock_subprocess = mocker.patch("subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = 1
        mock_result.stderr = "tar: Error extracting archive"
        mock_subprocess.return_value = mock_result

        with pytest.raises(ExtractionError):
            extractor._extract_with_system_tar(archive_path, extract_path)
