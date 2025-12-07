"""
Workflow tests for protonfetcher module.
Testing complete end-to-end workflows that involve multiple components.
This consolidates the workflow tests from the previous test_integrations.py file.
"""

import json
import subprocess

import pytest

from protonfetcher.common import DEFAULT_FORK, FORKS, ForkName
from protonfetcher.exceptions import ProtonFetcherError
from protonfetcher.github_fetcher import GitHubReleaseFetcher


class TestCompleteWorkflowIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.parametrize(
        "fork,expected_tag,expected_asset",
        [
            (ForkName.GE_PROTON, "GE-Proton8-25", "GE-Proton8-25.tar.gz"),
            (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30.tar.xz"),
        ],
    )
    def test_fetch_and_extract_with_different_forks(
        self,
        mocker,
        mock_network_client,
        mock_filesystem_client,
        tmp_path,
        fork,
        expected_tag,
        expected_asset,
    ):
        """Test fetch_and_extract with different ProtonGE forks using parametrization."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        output_dir = tmp_path / f"output_{fork}"
        extract_dir = tmp_path / f"extract_{fork}"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[fork]["repo"]

        # Mock all the external dependencies
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        # Mock file system operations
        mock_filesystem_client.exists.return_value = False
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.mkdir.return_value = None
        mock_filesystem_client.write.return_value = None
        mock_filesystem_client.read.return_value = b"mock archive"

        # Mock the fetching methods
        mocker.patch.object(
            fetcher.release_manager,
            "find_asset_by_name",
            return_value=expected_asset,
        )
        mocker.patch.object(
            fetcher.release_manager, "get_remote_asset_size", return_value=1024
        )

        # Mock download and extraction
        archive_path = output_dir / expected_asset
        archive_path.write_bytes(b"mock archive")

        mock_download = mocker.patch.object(
            fetcher.asset_downloader, "download_asset", return_value=archive_path
        )
        mock_extract = mocker.patch.object(fetcher.archive_extractor, "extract_archive")
        mock_manage_links = mocker.patch.object(
            fetcher.link_manager, "manage_proton_links"
        )

        result = fetcher.fetch_and_extract(
            repo, output_dir, extract_dir, release_tag=expected_tag, fork=fork
        )

        expected_extracted_dir = extract_dir / expected_tag
        assert result == expected_extracted_dir
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        mock_manage_links.assert_called_once()

        # Verify the call used the correct fork
        call_args = mock_manage_links.call_args
        assert call_args[0][2] == fork  # fork parameter

    def test_fetch_and_extract_complete_workflow(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test complete fetch_and_extract workflow."""
        # Create fetcher with mocked clients
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]
        expected_tag = "GE-Proton8-25"
        expected_asset = "GE-Proton8-25.tar.gz"

        # Mock all the external dependencies
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        # Mock the fetching methods
        mocker.patch.object(
            fetcher.release_manager, "fetch_latest_tag", return_value=expected_tag
        )
        mocker.patch.object(
            fetcher.release_manager, "find_asset_by_name", return_value=expected_asset
        )
        mocker.patch.object(
            fetcher.release_manager, "get_remote_asset_size", return_value=1024
        )

        # Mock file system operations
        mock_filesystem_client.exists.return_value = False
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.mkdir.return_value = None
        mock_filesystem_client.write.return_value = None
        mock_filesystem_client.read.return_value = b"mock archive"

        # Mock download and extraction
        archive_path = output_dir / expected_asset
        archive_path.write_bytes(b"mock archive")

        mock_download = mocker.patch.object(
            fetcher.asset_downloader, "download_asset", return_value=archive_path
        )
        mock_extract = mocker.patch.object(fetcher.archive_extractor, "extract_archive")
        mock_manage_links = mocker.patch.object(
            fetcher.link_manager, "manage_proton_links"
        )

        result = fetcher.fetch_and_extract(repo, output_dir, extract_dir)

        expected_extracted_dir = extract_dir / expected_tag
        assert result == expected_extracted_dir
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        mock_manage_links.assert_called_once()

        # Verify the call args
        call_args = mock_manage_links.call_args
        assert (
            call_args[1]["is_manual_release"] is False
        )  # Since no specific tag was provided

    def test_fetch_and_extract_with_manual_tag(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test fetch_and_extract workflow with manual tag."""
        # Create fetcher with mocked clients
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]
        manual_tag = "GE-Proton9-10"
        expected_asset = f"{manual_tag}.tar.gz"

        # Mock all the external dependencies
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        # Mock the fetching methods
        mocker.patch.object(
            fetcher.release_manager, "find_asset_by_name", return_value=expected_asset
        )
        mocker.patch.object(
            fetcher.release_manager, "get_remote_asset_size", return_value=1024
        )

        # Mock file system operations
        mock_filesystem_client.exists.return_value = False
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.mkdir.return_value = None
        mock_filesystem_client.write.return_value = None
        mock_filesystem_client.read.return_value = b"mock archive"

        # Mock download and extraction
        archive_path = output_dir / expected_asset
        archive_path.write_bytes(b"mock archive")

        mock_download = mocker.patch.object(
            fetcher.asset_downloader, "download_asset", return_value=archive_path
        )
        mock_extract = mocker.patch.object(fetcher.archive_extractor, "extract_archive")
        mock_manage_links = mocker.patch.object(
            fetcher.link_manager, "manage_proton_links"
        )

        result = fetcher.fetch_and_extract(
            repo, output_dir, extract_dir, release_tag=manual_tag
        )

        expected_extracted_dir = extract_dir / manual_tag
        assert result == expected_extracted_dir
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        mock_manage_links.assert_called_once()

        # Verify the call args
        call_args = mock_manage_links.call_args
        assert (
            call_args[1]["is_manual_release"] is True
        )  # Because manual tag was provided
        assert call_args[0][1] == manual_tag  # The tag passed should be the manual one

    def test_fetch_and_extract_curl_not_available(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test fetch_and_extract when curl is not available."""
        # Create fetcher with mocked clients
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]

        mocker.patch("shutil.which", return_value=None)

        with pytest.raises(ProtonFetcherError, match="curl is not available"):
            fetcher.fetch_and_extract(repo, output_dir, extract_dir)


class TestFindAssetByName:
    """Integration tests for find_asset_by_name API fallback functionality."""

    def test_find_asset_by_name_api_success_with_matching_assets(
        self, mocker, mock_network_client
    ):
        """Test find_asset_by_name when API succeeds and finds matching assets."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock API response with matching assets
        api_response = {
            "assets": [
                {"name": "other_file.zip"},
                {"name": "GE-Proton8-25.tar.gz"},  # This matches expected extension
                {"name": "another_file.txt"},
            ]
        }

        # Mock network client to return the API response
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
        )
        mock_network_client.get.return_value = mock_result
        fetcher.release_manager.network_client = mock_network_client

        asset_name = fetcher.release_manager.find_asset_by_name(
            repo, tag, ForkName.GE_PROTON
        )

        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_success_no_matching_assets_use_fallback(
        self, mocker, mock_network_client
    ):
        """Test find_asset_by_name when API succeeds but no matching assets, uses first available."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock API response with no matching assets, but has other assets
        api_response = {
            "assets": [
                {"name": "info.txt"},
                {"name": "readme.md"},
                {"name": "GE-Proton8-25.exe"},
            ]
        }

        # Mock network client to return the API response
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
        )
        mock_network_client.get.return_value = mock_result
        fetcher.release_manager.network_client = mock_network_client

        asset_name = fetcher.release_manager.find_asset_by_name(
            repo, tag, ForkName.GE_PROTON
        )

        # Should return first available asset since no matching extensions found
        assert asset_name == "info.txt"

    def test_find_asset_by_name_api_failure_fallback_success(
        self, mocker, mock_network_client
    ):
        """Test find_asset_by_name when API completely fails and falls back to HTML."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock network client to simulate API failure and then success for HTML
        api_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="API error"
        )
        html_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='<a href="/releases/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
            stderr="",
        )

        mock_network_client.get.side_effect = [api_result, html_result]
        fetcher.release_manager.network_client = mock_network_client

        asset_name = fetcher.release_manager.find_asset_by_name(
            repo, tag, ForkName.GE_PROTON
        )

        # Should fall back to HTML parsing and find the asset
        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_failure_html_fallback_fails(
        self, mocker, mock_network_client
    ):
        """Test find_asset_by_name when both API and HTML fallback fail."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock network client to simulate failures for both API and HTML
        api_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="API error"
        )
        html_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="HTML error"
        )

        mock_network_client.get.side_effect = [api_result, html_result]
        fetcher.release_manager.network_client = mock_network_client

        with pytest.raises(ProtonFetcherError):
            fetcher.release_manager.find_asset_by_name(repo, tag, ForkName.GE_PROTON)


class TestGetRemoteAssetSize:
    """Integration tests for get_remote_asset_size functionality."""

    def test_get_remote_asset_size_success_from_first_response(
        self, mocker, mock_network_client
    ):
        """Test get_remote_asset_size success when content-length is found in initial response."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n",
            stderr="",
        )
        mock_network_client.head.return_value = mock_result
        fetcher.release_manager.network_client = mock_network_client

        size = fetcher.release_manager.get_remote_asset_size(repo, tag, asset_name)
        assert size == 1024

    def test_get_remote_asset_size_follows_redirects_to_get_size(
        self, mocker, mock_network_client
    ):
        """Test get_remote_asset_size follows redirects to get final size."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock network client to return redirect first and then content-length
        redirect_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 302 Found\r\nLocation: https://redirect.example.com/file\r\n",
            stderr="",
        )
        content_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 2048\r\n",
            stderr="",
        )

        mock_network_client.head.side_effect = [redirect_result, content_result]
        fetcher.release_manager.network_client = mock_network_client

        size = fetcher.release_manager.get_remote_asset_size(repo, tag, asset_name)
        assert size == 2048

    def test_get_remote_asset_size_404_error_raises_fetch_error(
        self, mocker, mock_network_client
    ):
        """Test get_remote_asset_size raises ProtonFetcherError when server returns 404."""
        fetcher = GitHubReleaseFetcher(mock_network_client, mocker.Mock())
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="404 Not Found"
        )
        mock_network_client.head.return_value = mock_result
        fetcher.release_manager.network_client = mock_network_client

        with pytest.raises(ProtonFetcherError, match="Remote asset not found"):
            fetcher.release_manager.get_remote_asset_size(repo, tag, asset_name)


class TestListLinksAndRemoveRelease:
    """Integration tests for the new --ls and --rm functionality."""

    def test_list_links_ge_proton_integration(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test list_links method integration for GE-Proton."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create a target directory and make symlinks
        target_dir = tmp_path / "GE-Proton10-15"
        target_dir.mkdir()

        # Mock file system operations
        mock_fs = mock_filesystem_client
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        mock_fs.is_symlink = mocker.MagicMock(return_value=True)
        mock_fs.resolve.return_value = target_dir

        # Call the method
        result = fetcher.link_manager.list_links(extract_dir, ForkName.GE_PROTON)

        # Verify the structure and values of the result
        assert "GE-Proton" in result
        assert "GE-Proton-Fallback" in result
        assert "GE-Proton-Fallback2" in result

    def test_list_links_proton_em_integration(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test list_links method integration for Proton-EM."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create a Proton-EM target directory
        target_dir = tmp_path / "proton-EM-10.0-30"
        target_dir.mkdir()

        # Mock file system operations
        mock_fs = mock_filesystem_client
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        mock_fs.is_symlink = mocker.MagicMock(return_value=True)
        mock_fs.resolve.return_value = target_dir

        # Call the method
        result = fetcher.link_manager.list_links(extract_dir, ForkName.PROTON_EM)

        # Verify the structure and values of the result
        assert "Proton-EM" in result
        assert "Proton-EM-Fallback" in result
        assert "Proton-EM-Fallback2" in result

    @pytest.mark.parametrize(
        "fork,tag_name",
        [
            (ForkName.GE_PROTON, "GE-Proton10-15"),
            (ForkName.PROTON_EM, "EM-10.0-30"),
        ],
    )
    def test_remove_release_success_integration(
        self,
        mocker,
        mock_network_client,
        mock_filesystem_client,
        tmp_path,
        fork: ForkName,
        tag_name: str,
    ):
        """Test remove_release method integration with real filesystem for both Proton forks."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create a release directory to remove
        # For GE-Proton: create directory as tag_name (e.g. GE-Proton10-15)
        # For Proton-EM: create directory as proton-{tag_name} (e.g. proton-EM-10.0-30)
        if fork == ForkName.PROTON_EM:
            release_dir = extract_dir / f"proton-{tag_name}"  # proton-EM-10.0-30
        else:  # GE-Proton
            release_dir = extract_dir / tag_name  # GE-Proton10-15
        release_dir.mkdir()

        # Mock file system operations
        mock_fs = mock_filesystem_client

        # Mock exists method to properly handle all possible path checks
        def mock_exists(path):
            path_str = str(path)
            # Define the main path we created for the test
            if fork == ForkName.PROTON_EM:
                expected_main_path = str(extract_dir / f"proton-{tag_name}")
                initial_path = str(extract_dir / tag_name)

                # Special case paths for the main release directory logic
                if path_str == initial_path:
                    return False  # First check: regular tag path doesn't exist for Proton-EM
                elif path_str == expected_main_path:
                    return True  # Second check: proton-prefixed path exists (this is what we created)

            else:  # GE-Proton
                expected_main_path = str(extract_dir / tag_name)

                # For GE-Proton, the main path exists
                if path_str == expected_main_path:
                    return True  # The tag path exists for GE-Proton

            # Handle symlink paths that are checked in the link removal loop
            expected_symlinks = {
                str(extract_dir / "GE-Proton"),
                str(extract_dir / "GE-Proton-Fallback"),
                str(extract_dir / "GE-Proton-Fallback2"),
                str(extract_dir / "Proton-EM"),
                str(extract_dir / "Proton-EM-Fallback"),
                str(extract_dir / "Proton-EM-Fallback2"),
            }

            # Return False for symlink paths (they may or may not exist, return False for test simplicity)
            if path_str in expected_symlinks:
                return False

            # For any other path not explicitly handled, return False
            return False

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.return_value = True
        mock_fs.rmtree.return_value = None
        mock_fs.unlink.return_value = None
        mock_fs.resolve.return_value = release_dir

        # Mock the link-related path operations to return real Path objects
        # Since the implementation calls path.is_symlink() and path.resolve() directly on Path objects,
        main_link_name = "GE-Proton" if fork == ForkName.GE_PROTON else "Proton-EM"
        fallback_link_name = f"{ForkName.GE_PROTON if fork == ForkName.GE_PROTON else ForkName.PROTON_EM}-Fallback"
        fallback2_link_name = f"{ForkName.GE_PROTON if fork == ForkName.GE_PROTON else ForkName.PROTON_EM}-Fallback2"

        main_link = extract_dir / main_link_name
        fallback_link = extract_dir / fallback_link_name
        fallback2_link = extract_dir / fallback2_link_name

        # Mock the get_link_names_for_fork method to return real Path objects
        _mock_get_link_names = mocker.patch.object(
            fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(main_link, fallback_link, fallback2_link),
        )

        # Mock the manage_proton_links method to verify it's called
        mock_manage_links = mocker.patch.object(
            fetcher.link_manager, "manage_proton_links"
        )

        # Call the remove method
        result = fetcher.link_manager.remove_release(extract_dir, tag_name, fork)

        # Verify the return value
        assert result is True

        # First check that rmtree was called at all
        assert mock_fs.rmtree.call_count > 0, (
            f"rmtree was never called. All calls: {mock_fs.rmtree.call_args_list}"
        )

        # Now verify it was called with the correct path
        if fork == ForkName.PROTON_EM:
            expected_path = extract_dir / f"proton-{tag_name}"
        else:  # GE-Proton
            expected_path = extract_dir / tag_name

        mock_fs.rmtree.assert_called_once_with(expected_path)

        # Verify that manage_proton_links was called to maintain consistency
        mock_manage_links.assert_called_once()

    def test_remove_release_directory_not_found(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test remove_release method when the specified directory doesn't exist."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Try to remove a directory that doesn't exist
        non_existent_tag = "GE-Proton99-99"
        _non_existent_dir = extract_dir / non_existent_tag

        # Mock file system operations
        mock_fs = mock_filesystem_client
        # Mock exists to return False for all checked paths
        mock_fs.exists = mocker.Mock(return_value=False)

        # Call the remove method, which should raise ProtonFetcherError
        with pytest.raises(
            ProtonFetcherError, match="Release directory does not exist"
        ):
            fetcher.link_manager.remove_release(
                extract_dir, non_existent_tag, ForkName.GE_PROTON
            )
