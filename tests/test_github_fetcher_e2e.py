"""
End-to-end tests for GitHubReleaseFetcher user-facing workflows.

Tests the main orchestrator class that coordinates all components:
- fetch_and_extract(): Complete download and extraction workflow
- list_recent_releases(): List available releases
- list_links(): List managed symlinks
- remove_release(): Remove release and update symlinks
- relink_fork(): Force recreation of symlinks

All tests use comprehensive mocking to avoid real file I/O:
- Mock filesystem protocol (not the SUT)
- Mock tarfile and subprocess (external dependencies)
- Mock urllib (network operations)
- No real file I/O - all paths are mock Path objects
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import (
    LinkManagementError,
    NetworkError,
    ProtonFetcherError,
)
from protonfetcher.github_fetcher import GitHubReleaseFetcher


class TestFetchAndExtract:
    """Test the main fetch_and_extract workflow."""

    def test_fetch_and_extract_ge_proton_complete_workflow_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_builtin_open: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Test complete GE-Proton download and extraction workflow using mocks."""
        # Arrange: All paths are mock Path objects
        latest_tag = "GE-Proton10-20"
        asset_name = "GE-Proton10-20.tar.gz"
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        archive_path = output_dir / asset_name
        result_dir = extract_dir / latest_tag

        # Mock filesystem existence checks
        # Note: result_dir exists after extraction, so we include it
        def mock_exists(p: Path) -> bool:
            return p in (output_dir, extract_dir, archive_path, result_dir)

        def mock_is_dir(p: Path) -> bool:
            return p in (output_dir, extract_dir, result_dir)

        def mock_is_symlink(p: Path) -> bool:
            return False  # No symlinks yet

        def mock_iterdir(p: Path):
            if p == extract_dir:
                return iter([result_dir])
            return iter([])

        def mock_read(p: Path) -> bytes:
            if "version" in str(p):
                return latest_tag.encode()
            return b""

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_dir.side_effect = mock_is_dir
        mock_filesystem_client.is_symlink.side_effect = mock_is_symlink
        mock_filesystem_client.iterdir.side_effect = mock_iterdir
        mock_filesystem_client.read.side_effect = mock_read

        # Mock network responses
        mock_get_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"assets": [{"name": asset_name, "size": 1048576}]}),
            stderr="",
        )
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Content-Length: 1048576",
            stderr="",
        )

        # Mock download to succeed (no real file written)
        mock_download_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_network_client.get.return_value = mock_get_response
        mock_network_client.head.return_value = mock_head_response
        mock_network_client.download.return_value = mock_download_response

        # Mock urllib to prevent actual download - return empty content
        mock_urllib_download(
            chunks=[b""],  # Empty content - no real download
            content_length=1048576,
        )

        # Mock builtins.open for any file operations
        mock_builtin_open()

        # Mock tarfile operations for extraction
        mock_tarfile_operations(
            members=[
                {"name": "GE-Proton10-20", "is_dir": True, "size": 0},
                {"name": "GE-Proton10-20/version", "is_dir": False, "size": 14},
            ]
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Act
        result_path = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=output_dir,
            extract_dir=extract_dir,
            release_tag=latest_tag,
            fork=ForkName.GE_PROTON,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == result_dir

        # Verify symlinks were created (mocked)
        mock_filesystem_client.symlink_to.assert_called()

    def test_fetch_and_extract_proton_em_complete_workflow_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        mock_builtin_open: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Test complete Proton-EM download and extraction workflow using mocks."""
        # Arrange
        latest_tag = "EM-10.0-30"
        asset_name = "proton-EM-10.0-30.tar.xz"
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        result_dir = extract_dir / latest_tag

        # Mock filesystem - result_dir exists after extraction
        def mock_exists(p: Path) -> bool:
            return p in (output_dir, extract_dir, output_dir / asset_name, result_dir)

        def mock_is_dir(p: Path) -> bool:
            return p in (output_dir, extract_dir, result_dir)

        def mock_is_symlink(p: Path) -> bool:
            return False

        def mock_iterdir(p: Path):
            if p == extract_dir:
                return iter([result_dir])
            return iter([])

        def mock_read(p: Path) -> bytes:
            if "version" in str(p):
                return latest_tag.encode()
            return b""

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_dir.side_effect = mock_is_dir
        mock_filesystem_client.is_symlink.side_effect = mock_is_symlink
        mock_filesystem_client.iterdir.side_effect = mock_iterdir
        mock_filesystem_client.read.side_effect = mock_read

        # Mock network responses
        mock_get_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"assets": [{"name": asset_name, "size": 2097152}]}),
            stderr="",
        )
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Content-Length: 2097152",
            stderr="",
        )
        mock_download_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        mock_network_client.get.return_value = mock_get_response
        mock_network_client.head.return_value = mock_head_response
        mock_network_client.download.return_value = mock_download_response

        # Mock urllib to prevent actual download
        mock_urllib_download(
            chunks=[b""],  # Empty content - no real download
            content_length=2097152,
        )

        # Mock builtins.open for any file operations
        mock_builtin_open()

        # Mock tarfile operations
        mock_tarfile_operations(
            members=[
                {"name": "proton-EM-10.0-30", "is_dir": True, "size": 0},
                {"name": "proton-EM-10.0-30/version", "is_dir": False, "size": 11},
            ]
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Act
        result_path = fetcher.fetch_and_extract(
            repo="Etaash-mathamsetty/Proton",
            output_dir=output_dir,
            extract_dir=extract_dir,
            release_tag=latest_tag,
            fork=ForkName.PROTON_EM,
            show_progress=False,
            show_file_details=False,
        )

        # Assert
        assert result_path == result_dir
        mock_filesystem_client.symlink_to.assert_called()

    def test_fetch_and_extract_skip_existing_directory_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test that existing directories are skipped (mocked)."""
        # Arrange
        tag = "GE-Proton10-20"
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        existing_dir = extract_dir / tag

        # Mock Path.exists and Path.is_dir for the skip check
        # (the code uses Path.exists() directly in _check_ge_proton_directory)
        mocker.patch(
            "protonfetcher.github_fetcher.Path.exists",
            return_value=True,
        )
        mocker.patch(
            "protonfetcher.github_fetcher.Path.is_dir",
            return_value=True,
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Act
        result_path = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=output_dir,
            extract_dir=extract_dir,
            release_tag=tag,
            fork=ForkName.GE_PROTON,
            show_progress=False,
            show_file_details=False,
        )

        # Assert: Returns existing directory, no network calls made
        assert result_path == existing_dir
        mock_network_client.get.assert_not_called()
        mock_network_client.download.assert_not_called()

    def test_fetch_and_extract_asset_not_found_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling when asset is not found (mocked)."""
        # Arrange
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        mock_get_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"assets": []}),
            stderr="",
        )
        mock_network_client.get.return_value = mock_get_response

        # Mock filesystem
        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Act & Assert
        with pytest.raises(ProtonFetcherError, match="Could not find asset"):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=output_dir,
                extract_dir=extract_dir,
                release_tag="GE-Proton10-20",
                fork=ForkName.GE_PROTON,
                show_progress=False,
                show_file_details=False,
            )


class TestListRecentReleases:
    """Test the list_recent_releases workflow."""

    def test_list_recent_releases_ge_proton_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test listing recent GE-Proton releases using mocks."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {"tag_name": "GE-Proton10-20"},
                    {"tag_name": "GE-Proton10-19"},
                    {"tag_name": "GE-Proton10-18"},
                ]
            ),
            stderr="",
        )
        mock_network_client.get.return_value = mock_response

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Act
        releases = fetcher.list_recent_releases(repo="GloriousEggroll/proton-ge-custom")

        # Assert
        assert len(releases) == 3
        assert releases[0] == "GE-Proton10-20"

    def test_list_recent_releases_proton_em_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test listing recent Proton-EM releases using mocks."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {"tag_name": "EM-10.0-30"},
                    {"tag_name": "EM-10.0-29"},
                ]
            ),
            stderr="",
        )
        mock_network_client.get.return_value = mock_response

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Act
        releases = fetcher.list_recent_releases(repo="Etaash-mathamsetty/Proton")

        # Assert
        assert len(releases) == 2
        assert releases[0] == "EM-10.0-30"


class TestListLinks:
    """Test the list_links workflow."""

    def test_list_links_ge_proton_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test listing GE-Proton symlinks using mocks."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")
        main_link = extract_dir / "GE-Proton"
        fb1_link = extract_dir / "GE-Proton-Fallback"
        fb2_link = extract_dir / "GE-Proton-Fallback2"
        target_dir = extract_dir / "GE-Proton10-20"

        # Mock filesystem to simulate existing symlinks
        def mock_exists(p: Path) -> bool:
            return p in (extract_dir, main_link, fb1_link, fb2_link, target_dir)

        def mock_is_symlink(p: Path) -> bool:
            return p in (main_link, fb1_link, fb2_link)

        def mock_resolve(p: Path) -> Path:
            if p == main_link:
                return target_dir
            elif p == fb1_link:
                return extract_dir / "GE-Proton10-19"
            elif p == fb2_link:
                return extract_dir / "GE-Proton10-18"
            return p

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_symlink.side_effect = mock_is_symlink
        mock_filesystem_client.resolve.side_effect = mock_resolve
        mock_filesystem_client.is_dir.return_value = True

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act
        links = fetcher.list_links(extract_dir, ForkName.GE_PROTON)

        # Assert
        assert "GE-Proton" in links
        assert "GE-Proton-Fallback" in links
        assert "GE-Proton-Fallback2" in links
        assert links["GE-Proton"] is not None

    def test_list_links_proton_em_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test listing Proton-EM symlinks using mocks."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")
        main_link = extract_dir / "Proton-EM"
        version_dir = extract_dir / "EM-10.0-30"

        # Mock filesystem
        def mock_exists(p: Path) -> bool:
            return p in (extract_dir, main_link, version_dir)

        def mock_is_symlink(p: Path) -> bool:
            return p == main_link

        def mock_resolve(p: Path) -> Path:
            return version_dir if p == main_link else p

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_symlink.side_effect = mock_is_symlink
        mock_filesystem_client.resolve.side_effect = mock_resolve
        mock_filesystem_client.is_dir.return_value = True

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act
        links = fetcher.list_links(extract_dir, ForkName.PROTON_EM)

        # Assert
        assert "Proton-EM" in links
        assert links["Proton-EM"] is not None


class TestRemoveRelease:
    """Test the remove_release workflow."""

    def test_remove_release_ge_proton_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test removing GE-Proton release using mocks."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")
        tag = "GE-Proton10-20"
        version_dir = extract_dir / tag
        main_link = extract_dir / "GE-Proton"

        # Mock filesystem
        def mock_exists(p: Path) -> bool:
            return p in (extract_dir, version_dir, main_link)

        def mock_is_symlink(p: Path) -> bool:
            return p == main_link

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_symlink.side_effect = mock_is_symlink
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.resolve.return_value = version_dir

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act
        result = fetcher.remove_release(extract_dir, tag, ForkName.GE_PROTON)

        # Assert
        assert result is True
        mock_filesystem_client.rmtree.assert_called_with(version_dir)

    def test_remove_release_proton_em_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test removing Proton-EM release using mocks."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")
        tag = "EM-10.0-30"
        version_dir = extract_dir / tag

        # Mock filesystem
        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (extract_dir, version_dir)
        )
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.is_symlink.return_value = False

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act
        result = fetcher.remove_release(extract_dir, tag, ForkName.PROTON_EM)

        # Assert
        assert result is True
        mock_filesystem_client.rmtree.assert_called_with(version_dir)

    def test_remove_nonexistent_release_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test removing non-existent release raises error (mocked)."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")
        mock_filesystem_client.exists.return_value = False

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act & Assert
        with pytest.raises(LinkManagementError, match="does not exist"):
            fetcher.remove_release(extract_dir, "NonExistent-10-20", ForkName.GE_PROTON)


class TestRelinkFork:
    """Test the relink_fork workflow."""

    def test_relink_fork_ge_proton_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test relinking GE-Proton symlinks using mocks."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")

        # Mock filesystem to find version directories
        version_dirs = [
            extract_dir / "GE-Proton10-20",
            extract_dir / "GE-Proton10-19",
            extract_dir / "GE-Proton10-18",
        ]

        def mock_exists(p: Path) -> bool:
            return p == extract_dir or p in version_dirs

        def mock_is_dir(p: Path) -> bool:
            return p == extract_dir or p in version_dirs

        def mock_iterdir(p: Path):
            if p == extract_dir:
                return iter(version_dirs)
            return iter([])

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_dir.side_effect = mock_is_dir
        mock_filesystem_client.iterdir.side_effect = mock_iterdir
        mock_filesystem_client.read.return_value = b"GE-Proton10-20"
        mock_filesystem_client.is_symlink.return_value = False

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act
        result = fetcher.relink_fork(extract_dir, ForkName.GE_PROTON)

        # Assert
        assert result is True

        # Verify symlinks were created (mocked)
        assert mock_filesystem_client.symlink_to.call_count >= 3

    def test_relink_fork_proton_em_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test relinking Proton-EM symlinks using mocks."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")
        version_dirs = [
            extract_dir / "EM-10.0-30",
            extract_dir / "EM-10.0-29",
        ]

        def mock_exists(p: Path) -> bool:
            return p == extract_dir or p in version_dirs

        def mock_is_dir(p: Path) -> bool:
            return p == extract_dir or p in version_dirs

        def mock_iterdir(p: Path):
            if p == extract_dir:
                return iter(version_dirs)
            return iter([])

        mock_filesystem_client.exists.side_effect = mock_exists
        mock_filesystem_client.is_dir.side_effect = mock_is_dir
        mock_filesystem_client.iterdir.side_effect = mock_iterdir
        mock_filesystem_client.read.return_value = b"EM-10.0-30"
        mock_filesystem_client.is_symlink.return_value = False

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act
        result = fetcher.relink_fork(extract_dir, ForkName.PROTON_EM)

        # Assert
        assert result is True
        assert mock_filesystem_client.symlink_to.call_count >= 2

    def test_relink_fork_no_versions_raises_error_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test relinking when no versions exist raises error (mocked)."""
        # Arrange
        extract_dir = Path("/mock/compatibilitytools.d")

        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.iterdir.return_value = iter([])

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act & Assert
        with pytest.raises(LinkManagementError, match="No valid.*versions found"):
            fetcher.relink_fork(extract_dir, ForkName.GE_PROTON)


class TestEnvironmentValidation:
    """Test environment validation in GitHubReleaseFetcher."""

    def test_fetch_and_extract_curl_not_available_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test that missing curl raises NetworkError (mocked)."""
        # Arrange: Mock shutil.which to return None (curl not found)
        mocker.patch("shutil.which", return_value=None)

        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")

        # Mock filesystem
        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        # Act & Assert
        with pytest.raises(NetworkError, match="curl is not available"):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=output_dir,
                extract_dir=extract_dir,
                release_tag="GE-Proton10-20",
                fork=ForkName.GE_PROTON,
                show_progress=False,
                show_file_details=False,
            )
