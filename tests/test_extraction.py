"""
Extraction tests for ProtonFetcher.

Consolidated tests for archive extraction and asset download workflows:
- Archive extraction (.tar.gz and .tar.xz)
- System tar fallback
- Archive info retrieval
- Asset downloading with progress
"""

import errno
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.exceptions import ExtractionError, NetworkError
from protonfetcher.filesystem import FileSystemClient

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
        )

        assert result_path == target_dir

    @pytest.mark.parametrize(
        "archive_path,exists_return",
        [
            ("/mock/nonexistent.tar.gz", False),
        ],
    )
    def test_extract_nonexistent_archive(
        self,
        archive_path: str,
        exists_return: bool,
        mock_filesystem_client: Any,
    ) -> None:
        """Test extracting non-existent archive raises error."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")

        mock_filesystem_client.exists.return_value = exists_return

        with pytest.raises(ExtractionError):
            extractor.extract_archive(
                archive_path=Path(archive_path),
                target_dir=target_dir,
                show_progress=False,
            )


# =============================================================================
# System Tar Fallback Tests
# =============================================================================


class TestSystemTarFallback:
    """Test system tar fallback when tarfile fails."""

    @pytest.mark.parametrize(
        "archive_format,subprocess_returncode,expect_success",
        [
            ("gz", 0, True),
            ("xz", 0, True),
            ("gz", 2, False),
        ],
    )
    def test_system_tar_fallback(
        self,
        archive_format: str,
        subprocess_returncode: int,
        expect_success: bool,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test system tar fallback for both archive formats, success and failure."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path(f"/mock/test.tar.{archive_format}")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir
        mock_tarfile_operations(raise_on_open=Exception("tarfile failed"))
        mock_run = mock_subprocess_tar(
            returncode=subprocess_returncode, stdout="", stderr="tar failed"
        )

        if expect_success:
            extractor.extract_archive(
                archive_path=archive_path,
                target_dir=target_dir,
                show_progress=False,
            )
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert "tar" in call_args
        else:
            with pytest.raises(ExtractionError, match="tar failed"):
                extractor.extract_archive(
                    archive_path=archive_path,
                    target_dir=target_dir,
                    show_progress=False,
                )


# =============================================================================
# Real-filesystem extraction (no mocks: mock mkdir hid the fallback arg bug)
# =============================================================================


class TestRealFilesystemExtraction:
    """Extraction against real archives on disk."""

    def test_extract_archive_with_absolute_symlink(self, tmp_path: Path) -> None:
        """Proton forks ship symlinks to absolute paths; extraction must not fail."""
        archive = tmp_path / "proton-wineland-11.0.tar.xz"
        src = tmp_path / "files"
        (src / "share/mesa/drirc.d").mkdir(parents=True)
        (src / "version").write_text("11.0")
        (src / "share/mesa/drirc.d/99-system.conf").symlink_to("/etc/drirc")
        (src / "share/rel.conf").symlink_to("../version")
        with tarfile.open(archive, "w:xz") as tar:
            tar.add(src, arcname="files")

        target = tmp_path / "extracted"
        ArchiveExtractor(FileSystemClient()).extract_archive(
            archive, target, show_progress=False
        )

        assert (target / "files/version").read_text() == "11.0"
        absolute = target / "files/share/mesa/drirc.d/99-system.conf"
        assert absolute.is_symlink()
        assert str(absolute.readlink()) == "/etc/drirc"
        assert str((target / "files/share/rel.conf").readlink()) == "../version"

    def test_download_write_failure_is_not_a_network_error(
        self, tmp_path: Path, mocker: Any
    ) -> None:
        """A denied or impossible write must not be reported as a network failure."""
        response = mocker.MagicMock()
        response.__enter__.return_value = response
        response.headers.get.return_value = "4"
        response.read.side_effect = [b"data", b""]
        mocker.patch("urllib.request.urlopen", return_value=response)

        out_path = tmp_path / "proton.tar.xz"
        out_path.mkdir()
        downloader = AssetDownloader(mocker.MagicMock(), FileSystemClient())

        with pytest.raises(IsADirectoryError) as exc:
            downloader.download_with_spinner("https://example.com/x", out_path)

        assert exc.value.errno == errno.EISDIR
        assert f"Failed to download to {out_path}: is a directory" in str(exc.value)
        assert not isinstance(exc.value, NetworkError)

    def test_extract_symlink_escape_is_skipped(self, tmp_path: Path) -> None:
        """A symlink whose name escapes the target dir must not be created."""
        archive = tmp_path / "evil.tar.xz"
        with tarfile.open(archive, "w:xz") as tar:
            entry = tarfile.TarInfo("files/version")
            entry.size = 4
            tar.addfile(entry, BytesIO(b"11.0"))
            link = tarfile.TarInfo("../escape.conf")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/drirc"
            tar.addfile(link)

        target = tmp_path / "extracted"
        ArchiveExtractor(FileSystemClient()).extract_archive(
            archive, target, show_progress=False
        )

        assert (target / "files/version").read_text() == "11.0"
        assert not (tmp_path / "escape.conf").exists()

    @pytest.mark.parametrize(
        "archive_name,tar_args",
        [("proton.tar.zst", ["--zstd", "-xf"]), ("proton.tar.xz", ["-xJf"])],
    )
    def test_system_tar_fallback_builds_correct_command(
        self, archive_name: str, tar_args: list[str], tmp_path: Path, mocker: Any
    ) -> None:
        """tarfile cannot read .tar.zst; the tar fallback must get real args."""
        archive = tmp_path / archive_name
        archive.write_bytes(b"not readable by tarfile")
        target = tmp_path / "extracted"
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        ArchiveExtractor(FileSystemClient()).extract_archive(
            archive, target, show_progress=False
        )

        assert mock_run.call_args[0][0] == [
            "tar",
            "--checkpoint=1",
            "--checkpoint-action=dot",
            *tar_args,
            "-f",
            str(archive),
            "-C",
            str(target),
        ]
        assert target.is_dir()


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
        )

        assert result_path == target_dir

    @pytest.mark.parametrize(
        "show_progress,members",
        [
            (False, [{"name": "test_dir", "is_dir": True, "size": 0}]),
            (
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
        )

        assert result_path == target_dir

    def test_extract_corrupted_archive(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test extracting corrupted archive raises error."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        corrupted = Path("/mock/corrupted.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: p == corrupted
        mock_tarfile_operations(raise_on_open=tarfile.TarError("corrupted"))
        # Mock subprocess to prevent tar fallback from masking the error
        mock_subprocess_tar(returncode=2, stdout="", stderr="tar failed")

        with pytest.raises(ExtractionError, match="tar failed"):
            extractor.extract_archive(
                archive_path=corrupted,
                target_dir=target_dir,
                show_progress=False,
            )

    def test_extract_unknown_format(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_subprocess_tar: Any,
    ) -> None:
        """Test extracting unknown archive format raises error."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        unknown = Path("/mock/archive.zip")

        mock_filesystem_client.exists.side_effect = lambda p: p == unknown
        mock_subprocess_tar(returncode=2, stdout="", stderr="Unknown format")

        with pytest.raises(ExtractionError, match="Unknown format"):
            extractor.extract_archive(
                archive_path=unknown,
                target_dir=target_dir,
                show_progress=False,
            )
