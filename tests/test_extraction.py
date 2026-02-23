"""
Extraction tests for ProtonFetcher.

Consolidated tests for archive extraction and asset download workflows:
- Archive extraction (.tar.gz and .tar.xz)
- System tar fallback
- Archive info retrieval
- Asset downloading with progress
"""

import tarfile
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.exceptions import ExtractionError, NetworkError

# =============================================================================
# Archive Extraction Tests
# =============================================================================


class TestArchiveExtraction:
    """Test archive extraction for both formats."""

    @pytest.mark.parametrize(
        "archive_format,archive_name,members",
        [
            (
                "gz",
                "GE-Proton10-20.tar.gz",
                [
                    {"name": "GE-Proton10-20", "is_dir": True, "size": 0},
                    {"name": "GE-Proton10-20/version", "is_dir": False, "size": 14},
                ],
            ),
            (
                "xz",
                "proton-EM-10.0-30.tar.xz",
                [
                    {"name": "proton-EM-10.0-30", "is_dir": True, "size": 0},
                    {"name": "proton-EM-10.0-30/version", "is_dir": False, "size": 11},
                ],
            ),
        ],
    )
    def test_extract_archive_with_mock(
        self,
        archive_format: str,
        archive_name: str,
        members: list[dict],
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting archives using filesystem mocks."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path(f"/mock/{archive_name}")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir
        mock_tarfile_operations(members=members)

        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        assert result_path == target_dir

    def test_extract_nonexistent_archive(
        self,
        mock_filesystem_client: Any,
    ) -> None:
        """Test extracting non-existent archive raises error."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        nonexistent_archive = Path("/mock/nonexistent.tar.gz")

        mock_filesystem_client.exists.return_value = False

        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=nonexistent_archive,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )


# =============================================================================
# System Tar Fallback Tests
# =============================================================================


class TestSystemTarFallback:
    """Test system tar fallback when tarfile fails."""

    @pytest.mark.parametrize("archive_format", ["gz", "xz"])
    def test_system_tar_fallback(
        self,
        archive_format: str,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test system tar fallback for both archive formats."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_name = f"test.tar.{archive_format}"
        archive_path = Path(f"/mock/{archive_name}")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir
        mock_tarfile_operations(raise_on_open=Exception("tarfile failed"))
        mock_run = mock_subprocess_tar(returncode=0, stdout="", stderr="")

        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert "tar" in call_args

    def test_system_tar_fallback_failure(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test system tar fallback failure raises ExtractionError."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: p == archive_path
        mock_tarfile_operations(raise_on_open=Exception("tarfile failed"))
        mock_subprocess_tar(returncode=2, stdout="", stderr="tar failed")

        with pytest.raises(ExtractionError, match="tar failed"):
            extractor.extract_archive(
                archive_path=archive_path,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )


# =============================================================================
# Archive Info Tests
# =============================================================================


class TestArchiveInfo:
    """Test archive information retrieval."""

    @pytest.mark.parametrize(
        "archive_name,members,expected_count,expected_size",
        [
            (
                "test.tar.gz",
                [{"name": "file.txt", "is_dir": False, "size": 1024}],
                1,
                1024,
            ),
            ("test.tar.xz", [{"name": "dir", "is_dir": True, "size": 0}], 1, 0),
            ("empty.tar.gz", [], 0, 0),
        ],
    )
    def test_get_archive_info(
        self,
        archive_name: str,
        members: list[dict],
        expected_count: int,
        expected_size: int,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test getting info from archives."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        archive_path = Path(f"/mock/{archive_name}")

        mock_filesystem_client.exists.return_value = True
        mock_tarfile_operations(members=members)

        info = extractor.get_archive_info(archive_path)

        assert info["file_count"] == expected_count
        assert info["total_size"] == expected_size

    def test_get_archive_info_read_error(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test getting info from corrupted archive raises error."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        archive_path = Path("/mock/corrupted.tar.gz")

        mock_filesystem_client.exists.return_value = True
        mock_tarfile_operations(raise_on_open=tarfile.TarError("corrupted"))

        with pytest.raises(ExtractionError, match="Error reading archive"):
            extractor.get_archive_info(archive_path)


# =============================================================================
# Asset Download Tests
# =============================================================================


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
        """Test downloading asset with progress spinner."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        mock_urllib_download(
            chunks=[b"chunk1", b"chunk2", b""],
            content_length=1048576,
        )
        _, written_data = mock_builtin_open()

        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        assert b"".join(written_data) == b"chunk1chunk2"

    @pytest.mark.parametrize(
        "error_scenario,expected_message",
        [
            ({"raise_on_open": Exception("Network failed")}, "Network failed"),
            (
                {"content_length": None, "chunks": [b"data", b""]},
                None,
            ),  # No content-length should succeed
        ],
    )
    def test_download_asset_scenarios(
        self,
        error_scenario: dict,
        expected_message: str | None,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
    ) -> None:
        """Test download with various scenarios (error and edge cases)."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        if expected_message:
            mock_urllib_download(**error_scenario)

            with pytest.raises(NetworkError, match="Failed to download"):
                downloader.download_with_spinner(
                    url="https://example.com/test.tar.gz",
                    output_path=output_path,
                )
        else:
            # No content-length should succeed
            mock_urllib_download(**error_scenario)
            _, written_data = mock_builtin_open()

            downloader.download_with_spinner(
                url="https://example.com/test.tar.gz",
                output_path=output_path,
            )

            assert b"".join(written_data) == b"data"


# =============================================================================
# Extraction Edge Cases Tests
# =============================================================================


class TestExtractionEdgeCases:
    """Test edge cases in extraction."""

    @pytest.mark.parametrize(
        "scenario,members,description",
        [
            (
                "existing_dir",
                [{"name": "test_dir", "is_dir": True, "size": 0}],
                "Extract to existing directory",
            ),
            (
                "dirs_only",
                [
                    {"name": "empty_dir", "is_dir": True, "size": 0},
                    {"name": "another_dir", "is_dir": True, "size": 0},
                ],
                "Directories only",
            ),
            (
                "large_file",
                [{"name": "data.bin", "is_dir": False, "size": 104857600}],
                "Large file entry",
            ),
        ],
    )
    def test_extraction_scenarios(
        self,
        scenario: str,
        members: list[dict],
        description: str,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test various extraction scenarios."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path(f"/mock/{scenario}.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir
        mock_tarfile_operations(members=members)

        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
            show_file_details=False,
        )

        assert result_path == target_dir

    @pytest.mark.parametrize(
        "show_progress,show_file_details,members",
        [
            (False, False, [{"name": "test_dir", "is_dir": True, "size": 0}]),
            (
                True,
                True,
                [
                    {"name": "test_dir", "is_dir": True, "size": 0},
                    {"name": "file.txt", "is_dir": False, "size": 1024},
                ],
            ),
        ],
    )
    def test_extraction_progress_options(
        self,
        show_progress: bool,
        show_file_details: bool,
        members: list[dict],
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extraction with different progress options."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir
        mock_tarfile_operations(members=members)

        result_path = extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=show_progress,
            show_file_details=show_file_details,
        )

        assert result_path == target_dir

    def test_extract_corrupted_archive(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
    ) -> None:
        """Test extracting corrupted archive raises error."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        corrupted = Path("/mock/corrupted.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: p == corrupted
        mock_tarfile_operations(raise_on_open=tarfile.TarError("corrupted"))

        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=corrupted,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )

    def test_extract_unknown_format(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test extracting unknown archive format."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        unknown = Path("/mock/archive.zip")

        mock_filesystem_client.exists.side_effect = lambda p: p == unknown
        mock_subprocess_tar(returncode=2, stdout="", stderr="Unknown format")

        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=unknown,
                target_dir=target_dir,
                show_progress=False,
                show_file_details=False,
            )
