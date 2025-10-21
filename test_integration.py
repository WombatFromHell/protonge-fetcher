"""
Integration tests for protonfetcher module.
Testing workflows that involve multiple components working together.
"""

import json
import re
import subprocess

import pytest

from protonfetcher import DEFAULT_FORK, FORKS, FetchError, GitHubReleaseFetcher


class TestLinkManagementIntegration:
    """Integration tests for link management workflows."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_manage_links_ge_proton_newest(self, fetcher, tmp_path):
        """Test link management when new version is the newest for GE-Proton."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create version directories
        old_main = "GE-Proton8-20"
        new_version = "GE-Proton10-1"

        (extract_dir / old_main).mkdir()
        (extract_dir / new_version).mkdir()

        main_link = extract_dir / "GE-Proton"
        fallback_link = extract_dir / "GE-Proton-Fallback"

        # Initially, main points to old version
        main_link.symlink_to(extract_dir / old_main)

        # Add new version that should become main
        fetcher._manage_proton_links(
            extract_dir, new_version, "GE-Proton", is_manual_release=True
        )

        # Verify that new version is main and old becomes fallback
        assert main_link.exists()
        assert fallback_link.exists()

        main_target = main_link.resolve()
        fallback_target = fallback_link.resolve()

        assert new_version in str(main_target)
        assert old_main in str(fallback_target)

    def test_manage_links_ge_proton_between_versions(self, fetcher, tmp_path):
        """Test link management when new version is between existing versions."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        main_tag = "GE-Proton10-10"
        fallback_tag = "GE-Proton9-10"
        new_tag = "GE-Proton9-15"  # Between main and fallback

        # Create all directories
        for tag in [main_tag, fallback_tag, new_tag]:
            (extract_dir / tag).mkdir()

        main_link = extract_dir / "GE-Proton"
        fallback_link = extract_dir / "GE-Proton-Fallback"
        fallback2_link = extract_dir / "GE-Proton-Fallback2"

        main_link.symlink_to(extract_dir / main_tag)
        fallback_link.symlink_to(extract_dir / fallback_tag)

        # Initially no fallback2
        assert not fallback2_link.exists()

        fetcher._manage_proton_links(
            extract_dir, new_tag, "GE-Proton", is_manual_release=True
        )

        # Should shift current fallback to fallback2 and put new as fallback
        assert fallback2_link.exists()
        assert fallback_link.exists()
        assert main_link.exists()

        main_target = main_link.resolve()
        fallback_target = fallback_link.resolve()
        fallback2_target = fallback2_link.resolve()

        assert main_tag in str(main_target)  # Main unchanged
        assert new_tag in str(fallback_target)  # New becomes fallback
        assert fallback_tag in str(fallback2_target)  # Old fallback becomes fallback2

    def test_manage_links_proton_em_newest(self, fetcher, tmp_path):
        """Test link management for Proton-EM fork with newest version."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # For Proton-EM, directories are named with proton- prefix
        old_main = "proton-EM-9.5-20"
        new_version = "proton-EM-10.0-30"

        (extract_dir / old_main).mkdir()
        (extract_dir / new_version).mkdir()

        main_link = extract_dir / "Proton-EM"

        main_link.symlink_to(extract_dir / old_main)

        # Add new version (tag without prefix)
        fetcher._manage_proton_links(
            extract_dir, "EM-10.0-30", "Proton-EM", is_manual_release=True
        )

        # Verify that new version is main
        assert main_link.exists()
        main_target = main_link.resolve()
        assert new_version in str(main_target)

    def test_manage_links_multiple_versions_rotation(self, fetcher, tmp_path):
        """Test rotation of multiple versions."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create multiple version directories
        versions = ["GE-Proton8-20", "GE-Proton9-15", "GE-Proton10-1", "GE-Proton10-2"]
        for ver in versions:
            (extract_dir / ver).mkdir()

        main_link = extract_dir / "GE-Proton"
        fallback_link = extract_dir / "GE-Proton-Fallback"
        fallback2_link = extract_dir / "GE-Proton-Fallback2"

        # Set up initial links
        main_link.symlink_to(extract_dir / "GE-Proton10-1")
        fallback_link.symlink_to(extract_dir / "GE-Proton9-15")
        fallback2_link.symlink_to(extract_dir / "GE-Proton8-20")

        # Add new newest version
        fetcher._manage_proton_links(
            extract_dir, "GE-Proton10-2", "GE-Proton", is_manual_release=True
        )

        # Should rotate: newest becomes main, others shift down
        main_target = main_link.resolve()
        fallback_target = fallback_link.resolve()
        fallback2_target = fallback2_link.resolve()

        assert "GE-Proton10-2" in str(main_target)
        assert "GE-Proton10-1" in str(fallback_target)
        assert "GE-Proton9-15" in str(
            fallback2_target
        )  # Old fallback becomes fallback2

    def test_manage_links_handles_extracted_dir_not_found(
        self, fetcher, mocker, tmp_path
    ):
        """Test link management when expected extracted directory doesn't exist."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Don't create the expected directory
        manual_tag = "GE-Proton9-5"

        # Mock logger to verify warning
        mock_logger = mocker.patch("protonfetcher.logger")

        # Should log warning and return early
        fetcher._manage_proton_links(
            extract_dir, manual_tag, "GE-Proton", is_manual_release=True
        )

        # Verify warning was logged
        assert any(
            "Expected extracted directory does not exist" in str(call)
            for call in mock_logger.warning.call_args_list
        )


class TestDownloadWorkflowIntegration:
    """Integration tests for download workflow."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_download_workflow_with_existing_file_same_size(
        self, fetcher, mocker, tmp_path
    ):
        """Test download workflow when local file exists with same size."""
        output_path = tmp_path / "existing.tar.gz"
        output_path.write_bytes(b"same content")

        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock get_remote_asset_size to return same size as local file
        mocker.patch.object(
            fetcher, "get_remote_asset_size", return_value=len(b"same content")
        )

        # Mock download methods to verify they're not called
        mock_spinner_download = mocker.patch.object(fetcher, "_download_with_spinner")
        mock_curl_download = mocker.patch.object(fetcher, "_curl_download")

        result = fetcher.download_asset(repo, tag, asset_name, output_path)

        # Should return early without downloading
        assert result == output_path
        mock_spinner_download.assert_not_called()
        mock_curl_download.assert_not_called()

    def test_download_workflow_with_existing_file_different_size(
        self, fetcher, mocker, tmp_path
    ):
        """Test download workflow when local file exists with different size."""
        output_path = tmp_path / "existing.tar.gz"
        output_path.write_bytes(b"old content")

        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock get_remote_asset_size to return different size
        mocker.patch.object(
            fetcher,
            "get_remote_asset_size",
            return_value=len(b"definitely different content"),
        )

        # Mock download methods
        mock_spinner_download = mocker.patch.object(fetcher, "_download_with_spinner")
        mocker.patch("builtins.open", mocker.mock_open())

        fetcher.download_asset(repo, tag, asset_name, output_path)

        # Should proceed with download because sizes are different
        assert mock_spinner_download.called

    def test_download_workflow_spinner_fallback(self, fetcher, mocker, tmp_path):
        """Test download workflow when spinner fails and falls back to curl."""
        output_path = tmp_path / "test.tar.gz"

        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock spinner download to fail
        mocker.patch.object(
            fetcher, "_download_with_spinner", side_effect=Exception("Network error")
        )

        # Mock curl download to succeed
        mock_curl_download = mocker.patch.object(
            fetcher,
            "_curl_download",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        )

        # Mock size check
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        fetcher.download_asset(repo, tag, asset_name, output_path)

        # Should have called curl download as fallback
        mock_curl_download.assert_called_once()

    def test_download_workflow_curl_404_error(self, fetcher, mocker, tmp_path):
        """Test download workflow when curl fallback results in 404 error."""
        output_path = tmp_path / "test.tar.gz"

        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock spinner to fail
        mocker.patch.object(
            fetcher, "_download_with_spinner", side_effect=Exception("Network error")
        )

        # Mock curl download to return 404 error
        mock_curl_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="404 Not Found"
        )
        mocker.patch.object(fetcher, "_curl_download", return_value=mock_curl_result)

        # Also mock size check to complete the call chain
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        with pytest.raises(FetchError, match="Asset not found"):
            fetcher.download_asset(repo, tag, asset_name, output_path)

    def test_download_workflow_creates_parent_directories(
        self, fetcher, mocker, tmp_path
    ):
        """Test that download workflow creates parent directories."""
        nested_path = tmp_path / "nested" / "dirs" / "file.tar.gz"

        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock the size check
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock urllib for download
        mock_response = mocker.MagicMock()
        mock_response.headers.get.return_value = "1024"
        mock_response.read.side_effect = [b"data", b""]
        mock_response.__enter__ = mocker.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mocker.MagicMock(return_value=None)
        mocker.patch("urllib.request.urlopen", return_value=mock_response)
        mocker.patch("builtins.open", mocker.mock_open())

        fetcher.download_asset(repo, tag, asset_name, nested_path)

        assert nested_path.parent.exists()


class TestExtractionWorkflowIntegration:
    """Integration tests for extraction workflow."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_extraction_workflow_gz_format(self, fetcher, mocker, tmp_path):
        """Test extraction workflow for .tar.gz format."""
        archive = tmp_path / "test.tar.gz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        # Should dispatch to extract_gz_archive
        fetcher.extract_archive(archive, extract_dir)

        # Verify that extract_gz_archive was called with correct parameters
        assert (
            extract_dir / "extracted_file"
        ).exists() is False  # Check that it didn't create unexpected files

    def test_extraction_workflow_xz_format(self, fetcher, mocker, tmp_path):
        """Test extraction workflow for .tar.xz format."""
        archive = tmp_path / "test.tar.xz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        # Should dispatch to extract_xz_archive
        fetcher.extract_archive(archive, extract_dir)

        # Verify that extract_xz_archive was called with correct parameters
        assert (
            extract_dir / "extracted_file"
        ).exists() is False  # Check that it didn't create unexpected files

    def test_extraction_workflow_with_progress(self, fetcher, mocker, tmp_path):
        """Test extraction workflow with progress indication."""
        archive = tmp_path / "test.tar.gz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        # Call with progress enabled
        fetcher.extract_archive(archive, extract_dir, show_progress=True)

        # Verify the extraction completed successfully
        assert extract_dir.exists()

    def test_extraction_workflow_error_handling(self, fetcher, mocker, tmp_path):
        """Test extraction workflow handles errors properly."""
        archive = tmp_path / "test.tar.gz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        error_msg = "tar: Unexpected EOF in archive"
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=error_msg
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match=error_msg):
            fetcher.extract_gz_archive(archive, extract_dir)


class TestCompleteWorkflowIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_fetch_and_extract_complete_workflow(self, fetcher, mocker, tmp_path):
        """Test complete fetch_and_extract workflow."""
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
        mocker.patch.object(fetcher, "fetch_latest_tag", return_value=expected_tag)
        mocker.patch.object(fetcher, "find_asset_by_name", return_value=expected_asset)
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock download and extraction
        archive_path = output_dir / expected_asset
        archive_path.write_bytes(b"mock archive")

        mock_download = mocker.patch.object(
            fetcher, "download_asset", return_value=archive_path
        )
        mock_extract = mocker.patch.object(fetcher, "extract_archive")
        mock_manage_links = mocker.patch.object(fetcher, "_manage_proton_links")

        result = fetcher.fetch_and_extract(repo, output_dir, extract_dir)

        assert result == extract_dir
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        mock_manage_links.assert_called_once()

        # Verify the call args
        call_args = mock_manage_links.call_args
        assert (
            call_args[1]["is_manual_release"] is False
        )  # Since no specific tag was provided

    def test_fetch_and_extract_with_manual_tag(self, fetcher, mocker, tmp_path):
        """Test fetch_and_extract workflow with manual tag."""
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
        mocker.patch.object(fetcher, "find_asset_by_name", return_value=expected_asset)
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock download and extraction
        archive_path = output_dir / expected_asset
        archive_path.write_bytes(b"mock archive")

        mock_download = mocker.patch.object(
            fetcher, "download_asset", return_value=archive_path
        )
        mock_extract = mocker.patch.object(fetcher, "extract_archive")
        mock_manage_links = mocker.patch.object(fetcher, "_manage_proton_links")

        result = fetcher.fetch_and_extract(
            repo, output_dir, extract_dir, release_tag=manual_tag
        )

        assert result == extract_dir
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        mock_manage_links.assert_called_once()

        # Verify the call args
        call_args = mock_manage_links.call_args
        assert (
            call_args[1]["is_manual_release"] is True
        )  # Because manual tag was provided
        assert call_args[0][1] == manual_tag  # The tag passed should be the manual one

    def test_fetch_and_extract_curl_not_available(self, fetcher, mocker, tmp_path):
        """Test fetch_and_extract when curl is not available."""
        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]

        mocker.patch("shutil.which", return_value=None)

        with pytest.raises(FetchError, match="curl is not available"):
            fetcher.fetch_and_extract(repo, output_dir, extract_dir)

    def test_fetch_and_extract_directories_not_writable(
        self, fetcher, mocker, tmp_path
    ):
        """Test fetch_and_extract when directories are not writable."""
        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]

        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        # Make output_dir not writable
        output_dir.chmod(0o444)

        with pytest.raises(FetchError, match="not writable"):
            fetcher.fetch_and_extract(repo, output_dir, extract_dir)

        # Restore permissions for other tests
        output_dir.chmod(0o755)

    def test_fetch_and_extract_unpacked_exists_early_return(
        self, fetcher, mocker, tmp_path
    ):
        """Test fetch_and_extract returns early when unpacked directory already exists."""
        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]
        existing_tag = "GE-Proton8-25"

        # Create the unpacked directory to trigger early return
        unpacked = extract_dir / existing_tag
        unpacked.mkdir()

        mocker.patch("shutil.which", return_value="/usr/bin/curl")
        mocker.patch.object(fetcher, "fetch_latest_tag", return_value=existing_tag)
        mocker.patch.object(
            fetcher, "find_asset_by_name", return_value=f"{existing_tag}.tar.gz"
        )

        # Mock download and extract to ensure they're not called
        mock_download = mocker.patch.object(fetcher, "download_asset")
        mock_extract = mocker.patch.object(fetcher, "extract_archive")

        result = fetcher.fetch_and_extract(repo, output_dir, extract_dir)

        assert result == extract_dir
        mock_download.assert_not_called()
        mock_extract.assert_not_called()

    def test_fetch_and_extract_checks_after_download(self, fetcher, mocker, tmp_path):
        """Test that fetch_and_extract checks for unpacked dir after download."""
        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        repo = FORKS[DEFAULT_FORK]["repo"]
        expected_tag = "GE-Proton8-25"
        expected_asset = f"{expected_tag}.tar.gz"

        # Mock all the external dependencies
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        # Mock the fetching methods
        mocker.patch.object(fetcher, "fetch_latest_tag", return_value=expected_tag)
        mocker.patch.object(fetcher, "find_asset_by_name", return_value=expected_asset)
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Create unpacked dir after download is called
        def create_after_download(*args, **kwargs):
            unpacked = extract_dir / expected_tag
            unpacked.mkdir()
            return args[3]  # Return output_path

        mocker.patch.object(
            fetcher, "download_asset", side_effect=create_after_download
        )
        mock_extract = mocker.patch.object(fetcher, "extract_archive")

        result = fetcher.fetch_and_extract(repo, output_dir, extract_dir)

        assert result == extract_dir
        mock_extract.assert_not_called()

    def test_fetch_and_extract_with_different_forks(self, fetcher, mocker, tmp_path):
        """Test fetch_and_extract with different ProtonGE forks."""
        output_dir = tmp_path / "output"
        extract_dir = tmp_path / "extract"
        output_dir.mkdir()
        extract_dir.mkdir()

        for fork_name in FORKS.keys():
            repo = FORKS[fork_name]["repo"]
            expected_tag = "EM-10.0-30" if fork_name == "Proton-EM" else "GE-Proton8-25"
            expected_asset = (
                f"proton-{expected_tag}.tar.xz"
                if fork_name == "Proton-EM"
                else f"{expected_tag}.tar.gz"
            )

            # Mock all the external dependencies
            mocker.patch("shutil.which", return_value="/usr/bin/curl")

            # Mock the fetching methods
            mocker.patch.object(
                fetcher, "find_asset_by_name", return_value=expected_asset
            )
            mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

            # Mock download and extraction
            archive_path = output_dir / expected_asset
            archive_path.write_bytes(b"mock archive")

            mock_download = mocker.patch.object(
                fetcher, "download_asset", return_value=archive_path
            )
            mock_extract = mocker.patch.object(fetcher, "extract_archive")
            mock_manage_links = mocker.patch.object(fetcher, "_manage_proton_links")

            result = fetcher.fetch_and_extract(
                repo, output_dir, extract_dir, release_tag=expected_tag, fork=fork_name
            )

            assert result == extract_dir
            mock_download.assert_called_once()
            mock_extract.assert_called_once()
            mock_manage_links.assert_called_once()

            # Verify the call used the correct fork
            call_args = mock_manage_links.call_args
            assert call_args[0][2] == fork_name  # fork parameter

    def test_list_recent_releases_workflow(self, fetcher, mocker):
        """Test the complete list_recent_releases workflow."""
        repo = "GloriousEggroll/proton-ge-custom"

        # Mock API response with multiple releases
        api_response = [
            {"tag_name": f"GE-Proton9-{i:02d}", "name": f"Release 9-{i:02d}"}
            for i in range(25, 0, -1)  # 25 releases from 9-25 to 9-01
        ]

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        tags = fetcher.list_recent_releases(repo)

        # Should return only the first 20 tags (most recent ones from the API)
        expected_tags = [
            f"GE-Proton9-{i:02d}" for i in range(25, 5, -1)
        ]  # 9-25 down to 9-06
        assert tags == expected_tags
        assert len(tags) == 20  # Should be limited to 20

    def test_list_recent_releases_with_different_forks(self, fetcher, mocker):
        """Test list_recent_releases with different fork repositories."""
        for fork_name in FORKS.keys():
            repo = FORKS[fork_name]["repo"]

            # Mock different response format based on fork
            if fork_name == "Proton-EM":
                api_response = [
                    {"tag_name": f"EM-10.0-{i}", "name": f"EM Release {i}"}
                    for i in range(30, 10, -1)
                ]
            else:  # GE-Proton
                api_response = [
                    {"tag_name": f"GE-Proton10-{i:02d}", "name": f"GE Release {i:02d}"}
                    for i in range(20, 0, -1)
                ]

            mock_result = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
            )
            mocker.patch("subprocess.run", return_value=mock_result)

            tags = fetcher.list_recent_releases(repo)

            assert len(tags) <= 20  # Should be limited to 20 tags
            assert all(isinstance(tag, str) for tag in tags)  # All should be strings


class TestFindAssetByName:
    """Integration tests for find_asset_by_name API fallback functionality."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_find_asset_by_name_api_success_with_matching_assets(self, fetcher, mocker):
        """Test find_asset_by_name when API succeeds and finds matching assets."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock successful API response with matching assets
        api_response = {
            "assets": [
                {"name": "other_file.zip"},
                {"name": "GE-Proton8-25.tar.gz"},  # This matches expected extension
                {"name": "another_file.txt"},
            ]
        }

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        asset_name = fetcher.find_asset_by_name(repo, tag, "GE-Proton")

        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_success_no_matching_assets_use_fallback(
        self, fetcher, mocker
    ):
        """Test find_asset_by_name when API succeeds but no matching assets, uses first available."""
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

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        asset_name = fetcher.find_asset_by_name(repo, tag, "GE-Proton")

        # Should return first available asset since no matching extensions found
        assert asset_name == "info.txt"

    def test_find_asset_by_name_api_success_no_assets(self, fetcher, mocker):
        """Test find_asset_by_name when API succeeds but no assets in response."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock API response with no assets
        api_response = {
            "assets": []  # Empty assets list
        }

        responses = [
            # First call (API) - returns empty assets
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
            ),
            # Second call (HTML fallback) - successful response
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/releases/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset_name = fetcher.find_asset_by_name(repo, tag, "GE-Proton")

        # Should fall back to HTML parsing and find the asset
        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_missing_assets_field_fallback(
        self, fetcher, mocker
    ):
        """Test find_asset_by_name when API response lacks assets field and falls back to HTML."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # Mock API response without assets field
        api_response = {
            "tag_name": tag,
            "name": "Release name",
            "body": "Release notes",
        }

        responses = [
            # API call - no assets field, raises exception
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
            ),
            # HTML fallback call - successful
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/releases/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset_name = fetcher.find_asset_by_name(repo, tag, "GE-Proton")

        # Should fall back to HTML parsing and find the asset
        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_json_decode_error_fallback(self, fetcher, mocker):
        """Test find_asset_by_name when API returns invalid JSON and falls back to HTML."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        responses = [
            # API call - returns invalid JSON
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="invalid json {", stderr=""
            ),
            # HTML fallback call - successful
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/releases/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset_name = fetcher.find_asset_by_name(repo, tag, "GE-Proton")

        # Should fall back to HTML parsing and find the asset
        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_failure_fallback_success(self, fetcher, mocker):
        """Test find_asset_by_name when API completely fails and falls back to HTML."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        responses = [
            # API call - fails completely
            subprocess.CompletedProcess(
                args=[], returncode=22, stdout="", stderr="API error"
            ),
            # HTML fallback call - successful with expected asset
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/releases/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset_name = fetcher.find_asset_by_name(repo, tag, "GE-Proton")

        # Should fall back to HTML parsing and find the asset
        assert asset_name == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_failure_html_fallback_fails(self, fetcher, mocker):
        """Test find_asset_by_name when both API and HTML fallback fail."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        responses = [
            # API call - fails
            subprocess.CompletedProcess(
                args=[], returncode=22, stdout="", stderr="API error"
            ),
            # HTML fallback call - also fails
            subprocess.CompletedProcess(
                args=[], returncode=22, stdout="", stderr="HTML error"
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        with pytest.raises(FetchError):
            fetcher.find_asset_by_name(repo, tag, "GE-Proton")

    def test_find_asset_by_name_api_failure_html_fallback_asset_not_found(
        self, fetcher, mocker
    ):
        """Test find_asset_by_name when API fails and HTML fallback doesn't find expected asset."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        responses = [
            # API call - fails
            subprocess.CompletedProcess(
                args=[], returncode=22, stdout="", stderr="API error"
            ),
            # HTML fallback call - returns page without expected asset
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="<html>no asset here</html>", stderr=""
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        with pytest.raises(FetchError):
            fetcher.find_asset_by_name(repo, tag, "GE-Proton")


class TestGetRemoteAssetSize:
    """Integration tests for get_remote_asset_size functionality."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_get_remote_asset_size_success_from_first_response(self, fetcher, mocker):
        """Test get_remote_asset_size success when content-length is found in initial response."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 1024

    def test_get_remote_asset_size_case_insensitive_headers(self, fetcher, mocker):
        """Test get_remote_asset_size handles case-insensitive Content-Length headers."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        test_cases = [
            "content-length: 2048\r\n",
            "Content-Length: 4096\r\n",
            "CONTENT-LENGTH: 8192\r\n",
        ]

        for header_line in test_cases:
            mock_result = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"HTTP/1.1 200 OK\r\n{header_line}",
                stderr="",
            )
            mocker.patch("subprocess.run", return_value=mock_result)

            match = re.search(r":\s*(\d+)", header_line)
            assert match is not None
            expected_size = int(match.group(1))
            size = fetcher.get_remote_asset_size(repo, tag, asset_name)
            assert size == expected_size

    def test_get_remote_asset_size_from_full_response_regex(self, fetcher, mocker):
        """Test get_remote_asset_size when content-length is found using regex on full response."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nServer: nginx\r\nContent-Length: 512\r\nConnection: close\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 512

    def test_get_remote_asset_size_zero_content_length_raises_error(
        self, fetcher, mocker
    ):
        """Test get_remote_asset_size raises error when Content-Length is 0."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 0\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Could not determine size"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)

    def test_get_remote_asset_size_follows_redirects_to_get_size(self, fetcher, mocker):
        """Test get_remote_asset_size follows redirects to get final size."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        responses = [
            # First call (initial URL) - returns redirect
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 302 Found\r\nLocation: https://redirect.example.com/file\r\n",
                stderr="",
            ),
            # Second call (redirect URL) - returns content-length
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 200 OK\r\nContent-Length: 2048\r\n",
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 2048

    def test_get_remote_asset_size_redirect_with_content_length_in_lines(
        self, fetcher, mocker
    ):
        """Test get_remote_asset_size after redirect when content-length is found in response lines."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        responses = [
            # First call (initial URL) - returns redirect
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 302 Found\r\nLocation: https://redirect.example.com/file\r\n",
                stderr="",
            ),
            # Second call (redirect URL) - returns content-length in lines
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 200 OK\r\nServer: nginx\r\nContent-Length: 3072\r\nConnection: close\r\n",
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 3072

    def test_get_remote_asset_size_redirect_with_zero_size_raises_error(
        self, fetcher, mocker
    ):
        """Test get_remote_asset_size raises error after redirect when content-length is 0."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        responses = [
            # First call (initial URL) - returns redirect
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 302 Found\r\nLocation: https://redirect.example.com/file\r\n",
                stderr="",
            ),
            # Second call (redirect URL) - returns content-length: 0
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 200 OK\r\nContent-Length: 0\r\n",
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        with pytest.raises(FetchError, match="Could not determine size"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)

    def test_get_remote_asset_size_no_content_length_raises_error(
        self, fetcher, mocker
    ):
        """Test get_remote_asset_size raises error when no content-length is found."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nServer: nginx\r\nConnection: close\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Could not determine size"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)

    def test_get_remote_asset_size_404_error_raises_fetch_error(self, fetcher, mocker):
        """Test get_remote_asset_size raises FetchError when server returns 404."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="404 Not Found"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Remote asset not found"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)

    def test_get_remote_asset_size_other_error_raises_fetch_error(
        self, fetcher, mocker
    ):
        """Test get_remote_asset_size raises FetchError when other errors occur."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="Connection timeout"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Failed to get remote asset size"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)


class TestDownloadAssetWorkflow:
    """Integration tests for download_asset workflow."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_download_asset_local_matches_remote_skip_download(
        self, fetcher, mocker, tmp_path
    ):
        """Test download_asset when local file exists with same size as remote, skips download."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "test.tar.gz"

        # Create local file with content
        local_content = b"test content"
        out_path.write_bytes(local_content)

        # Mock file system client to return that file exists
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = True

        # Mock the Path.stat method at the class level to return the file size
        mock_stat_result = mocker.MagicMock()
        mock_stat_result.st_size = len(local_content)
        mocker.patch.object(type(out_path), "stat", return_value=mock_stat_result)

        # Mock get_remote_asset_size to return same size as local
        mocker.patch.object(
            fetcher, "get_remote_asset_size", return_value=len(local_content)
        )

        # Mock download methods to verify they are not called
        mock_spinner_download = mocker.patch.object(fetcher, "_download_with_spinner")
        mock_curl_download = mocker.patch.object(fetcher, "_curl_download")

        result = fetcher.download_asset(repo, tag, asset_name, out_path)

        # Should return early without downloading
        assert result == out_path
        mock_spinner_download.assert_not_called()
        mock_curl_download.assert_not_called()

    def test_download_asset_local_different_size_download_occurs(
        self, fetcher, mocker, tmp_path
    ):
        """Test download_asset when local file exists with different size, downloads new version."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "test.tar.gz"

        # Create local file with content
        local_content = b"old content"
        out_path.write_bytes(local_content)

        # Mock file system client to return that file exists
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = True
        # Mock the Path.stat method at the class level to return the file size
        mock_stat_result = mocker.MagicMock()
        mock_stat_result.st_size = len(local_content)
        mocker.patch.object(type(out_path), "stat", return_value=mock_stat_result)

        # Mock get_remote_asset_size to return different size
        mocker.patch.object(
            fetcher,
            "get_remote_asset_size",
            return_value=len(b"new content that is different"),
        )

        # Mock the download methods
        mock_spinner_download = mocker.patch.object(fetcher, "_download_with_spinner")
        mock_spinner_download.return_value = (
            None  # Spinner download doesn't return anything
        )

        result = fetcher.download_asset(repo, tag, asset_name, out_path)

        assert result == out_path
        mock_spinner_download.assert_called_once()

    def test_download_asset_local_file_does_not_exist_proceeds(
        self, fetcher, mocker, tmp_path
    ):
        """Test download_asset when local file doesn't exist, proceeds with download."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "test.tar.gz"

        # Mock file system client to return that file does not exist
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = False

        # Mock get_remote_asset_size
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock the download methods
        mock_spinner_download = mocker.patch.object(fetcher, "_download_with_spinner")
        mock_spinner_download.return_value = None

        result = fetcher.download_asset(repo, tag, asset_name, out_path)

        assert result == out_path
        mock_spinner_download.assert_called_once()

    def test_download_asset_spinner_fallback_to_curl(self, fetcher, mocker, tmp_path):
        """Test download_asset when spinner download fails, falls back to curl."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "test.tar.gz"

        # Mock file system client
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = False
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock spinner download to fail
        mocker.patch.object(
            fetcher, "_download_with_spinner", side_effect=Exception("Network error")
        )

        # Mock curl download to succeed
        mock_curl_result = mocker.MagicMock()
        mock_curl_result.returncode = 0
        mock_curl_download = mocker.patch.object(
            fetcher, "_curl_download", return_value=mock_curl_result
        )

        result = fetcher.download_asset(repo, tag, asset_name, out_path)

        assert result == out_path
        mock_curl_download.assert_called_once()

    def test_download_asset_spinner_and_curl_both_fail(self, fetcher, mocker, tmp_path):
        """Test download_asset raises error when both spinner and curl downloads fail."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "test.tar.gz"

        # Mock file system client
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = False
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock spinner download to fail
        mocker.patch.object(
            fetcher, "_download_with_spinner", side_effect=Exception("Network error")
        )

        # Mock curl download to also fail
        mock_curl_result = mocker.MagicMock()
        mock_curl_result.returncode = 22  # curl error
        _ = mocker.patch.object(
            fetcher, "_curl_download", return_value=mock_curl_result
        )

        with pytest.raises(FetchError, match="Failed to download"):
            fetcher.download_asset(repo, tag, asset_name, out_path)

    def test_download_asset_curl_404_error(self, fetcher, mocker, tmp_path):
        """Test download_asset raises specific error when curl returns 404."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "test.tar.gz"

        # Mock file system client
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = False
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock spinner download to fail
        mocker.patch.object(
            fetcher, "_download_with_spinner", side_effect=Exception("Network error")
        )

        # Mock curl download to return 404 error
        mock_curl_result = mocker.MagicMock()
        mock_curl_result.returncode = 22
        mock_curl_result.stderr = "404 Not Found"
        mocker.patch.object(fetcher, "_curl_download", return_value=mock_curl_result)

        with pytest.raises(FetchError, match="Asset not found"):
            fetcher.download_asset(repo, tag, asset_name, out_path)

    def test_download_asset_creates_parent_directories(self, fetcher, mocker, tmp_path):
        """Test download_asset creates parent directories if they don't exist."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"
        out_path = tmp_path / "nested" / "dirs" / "test.tar.gz"

        # Mock file system client
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = False
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=1024)

        # Mock the download methods
        mock_spinner_download = mocker.patch.object(fetcher, "_download_with_spinner")
        mock_spinner_download.return_value = None

        result = fetcher.download_asset(repo, tag, asset_name, out_path)

        assert result == out_path
        # Verify that mkdir was called with correct parameters to create parent directories
        # The function should create out_path.parent which is tmp_path / "nested" / "dirs"
        expected_parent = out_path.parent
        mock_fs.mkdir.assert_called_with(expected_parent, parents=True, exist_ok=True)


class TestExtractionWorkflow:
    """Integration tests for extraction functionality."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_get_archive_info_success(self, fetcher, mocker, tmp_path):
        """Test _get_archive_info method returns correct file count and size."""
        # Create a fake archive file
        archive_path = tmp_path / "test.tar.gz"
        archive_path.write_text("fake archive content")

        # Mock tarfile operations
        mock_tar = mocker.MagicMock()
        mock_member1 = mocker.MagicMock()
        mock_member1.name = "file1.txt"
        mock_member1.size = 100
        mock_member2 = mocker.MagicMock()
        mock_member2.name = "file2.txt"
        mock_member2.size = 200
        mock_members = [mock_member1, mock_member2]

        mock_tar.__enter__.return_value = mock_tar
        mock_tar.__exit__.return_value = None
        mock_tar.getmembers.return_value = mock_members

        mocker.patch("tarfile.open", return_value=mock_tar)

        total_files, total_size = fetcher._get_archive_info(archive_path)

        assert total_files == 2
        assert total_size == 300

    def test_get_archive_info_exception_raises_error(self, fetcher, mocker, tmp_path):
        """Test _get_archive_info method raises error when tarfile operations fail."""
        # Create a fake archive file
        archive_path = tmp_path / "test.tar.gz"
        archive_path.write_text("fake archive content")

        # Mock tarfile to raise an exception
        mocker.patch("tarfile.open", side_effect=Exception("Invalid archive"))

        with pytest.raises(FetchError, match="Error reading archive"):
            fetcher._get_archive_info(archive_path)

    def test_extract_archive_gz_dispatch_to_tarfile_success(
        self, fetcher, mocker, tmp_path
    ):
        """Test extract_archive with .tar.gz calls _extract_with_tarfile."""
        archive_path = tmp_path / "test.tar.gz"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Mock _extract_with_tarfile method to succeed
        mock_extract_method = mocker.patch.object(fetcher, "_extract_with_tarfile")

        fetcher.extract_archive(archive_path, target_dir)

        # Verify _extract_with_tarfile was called
        mock_extract_method.assert_called_once_with(
            archive_path, target_dir, True, True
        )

    def test_extract_archive_xz_dispatch_to_tarfile_success(
        self, fetcher, mocker, tmp_path
    ):
        """Test extract_archive with .tar.xz calls _extract_with_tarfile."""
        archive_path = tmp_path / "test.tar.xz"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Mock _extract_with_tarfile method to succeed
        mock_extract_method = mocker.patch.object(fetcher, "_extract_with_tarfile")

        fetcher.extract_archive(archive_path, target_dir)

        # Verify _extract_with_tarfile was called
        mock_extract_method.assert_called_once_with(
            archive_path, target_dir, True, True
        )

    def test_extract_archive_tarfile_fallback_to_system_tar(
        self, fetcher, mocker, tmp_path
    ):
        """Test extract_archive when _extract_with_tarfile fails, falls back to system tar."""
        archive_path = tmp_path / "test.tar.gz"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Mock _extract_with_tarfile to raise FetchError (triggering fallback)
        mocker.patch.object(
            fetcher, "_extract_with_tarfile", side_effect=FetchError("Tarfile error")
        )

        # Mock extract_gz_archive for .tar.gz fallback
        mock_gz_method = mocker.patch.object(fetcher, "extract_gz_archive")

        fetcher.extract_archive(archive_path, target_dir)

        # Verify extract_gz_archive was called as fallback
        mock_gz_method.assert_called_once_with(archive_path, target_dir)

    def test_extract_archive_tarfile_fallback_xz_to_system_tar(
        self, fetcher, mocker, tmp_path
    ):
        """Test extract_archive with .tar.xz when _extract_with_tarfile fails, falls back to system tar."""
        archive_path = tmp_path / "test.tar.xz"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Mock _extract_with_tarfile to raise FetchError (triggering fallback)
        mocker.patch.object(
            fetcher, "_extract_with_tarfile", side_effect=FetchError("Tarfile error")
        )

        # Mock extract_xz_archive for .tar.xz fallback
        mock_xz_method = mocker.patch.object(fetcher, "extract_xz_archive")

        fetcher.extract_archive(archive_path, target_dir)

        # Verify extract_xz_archive was called as fallback
        mock_xz_method.assert_called_once_with(archive_path, target_dir)

    def test_extract_archive_progress_and_details_flags(
        self, fetcher, mocker, tmp_path
    ):
        """Test extract_archive with different progress and details flags."""
        archive_path = tmp_path / "test.tar.gz"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Test with progress disabled and details disabled
        mock_extract_method = mocker.patch.object(fetcher, "_extract_with_tarfile")

        fetcher.extract_archive(
            archive_path, target_dir, show_progress=False, show_file_details=False
        )

        # Verify _extract_with_tarfile was called with the correct flags
        mock_extract_method.assert_called_once_with(
            archive_path, target_dir, False, False
        )

    def test_extract_with_tarfile_success(self, fetcher, mocker, tmp_path):
        """Test _extract_with_tarfile method successful extraction."""
        archive_path = tmp_path / "test.tar"
        archive_path.touch()
        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock _get_archive_info to return test values
        mocker.patch.object(fetcher, "_get_archive_info", return_value=(2, 1024))

        # Mock tarfile operations
        mock_tar = mocker.MagicMock()
        mock_member1 = mocker.MagicMock()
        mock_member1.name = "file1.txt"
        mock_member1.size = 512
        mock_member2 = mocker.MagicMock()
        mock_member2.name = "file2.txt"
        mock_member2.size = 512
        mock_members = [mock_member1, mock_member2]

        mock_tar.__enter__.return_value = mock_tar
        mock_tar.__exit__.return_value = None
        mock_tar.__iter__.return_value = mock_members
        mock_tar.getmembers.return_value = mock_members

        # Mock tarfile.open context manager
        mocker.patch("tarfile.open", return_value=mock_tar)

        # Mock Spinner
        mock_spinner = mocker.MagicMock()
        mocker.patch.object(fetcher, "file_system_client")
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)

        # Mock the extract method to avoid actual file operations
        mocker.patch.object(mock_tar, "extract")

        # Call the method - should complete without errors
        fetcher._extract_with_tarfile(archive_path, target_dir)

        # Verify that tarfile operations were called
        assert mock_tar.__enter__.called
        assert mock_tar.extract.called
        assert mock_spinner.finish.called

    def test_extract_with_tarfile_file_details_progress(
        self, fetcher, mocker, tmp_path
    ):
        """Test _extract_with_tarfile with file details shown in progress."""
        archive_path = tmp_path / "test.tar"
        archive_path.touch()
        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock _get_archive_info to return test values
        mocker.patch.object(fetcher, "_get_archive_info", return_value=(1, 1024))

        # Mock tarfile operations
        mock_tar = mocker.MagicMock()
        mock_member = mocker.MagicMock()
        mock_member.name = "a_very_long_filename_that_will_be_truncated.txt"
        mock_member.size = 1024
        mock_members = [mock_member]

        mock_tar.__enter__.return_value = mock_tar
        mock_tar.__exit__.return_value = None
        mock_tar.__iter__.return_value = mock_members
        mock_tar.getmembers.return_value = mock_members

        # Mock tarfile.open context manager
        mocker.patch("tarfile.open", return_value=mock_tar)

        # Mock Spinner with file details functionality
        mock_spinner = mocker.MagicMock()
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)
        mocker.patch.object(fetcher, "file_system_client")

        # Mock the extract method to avoid actual file operations
        mocker.patch.object(mock_tar, "extract")

        # Call the method with show_file_details=True
        fetcher._extract_with_tarfile(archive_path, target_dir, show_file_details=True)

        # Spinner should have been called with file details
        mock_spinner.update_progress.assert_called()

    def test_extract_with_tarfile_spinner_progress_update(
        self, fetcher, mocker, tmp_path
    ):
        """Test _extract_with_tarfile calls spinner with progress updates."""
        archive_path = tmp_path / "test.tar"
        archive_path.touch()
        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock _get_archive_info to return test values
        mocker.patch.object(fetcher, "_get_archive_info", return_value=(2, 1024))

        # Mock tarfile operations
        mock_tar = mocker.MagicMock()
        mock_member1 = mocker.MagicMock()
        mock_member1.name = "file1.txt"
        mock_member1.size = 500
        mock_member2 = mocker.MagicMock()
        mock_member2.name = "file2.txt"
        mock_member2.size = 524
        mock_members = [mock_member1, mock_member2]  # Total: 1024 bytes

        mock_tar.__enter__.return_value = mock_tar
        mock_tar.__exit__.return_value = None
        mock_tar.__iter__.return_value = mock_members
        mock_tar.getmembers.return_value = mock_members

        # Mock tarfile.open context manager
        mocker.patch("tarfile.open", return_value=mock_tar)

        # Mock Spinner and mock update_progress method to track calls
        mock_spinner = mocker.MagicMock()
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)
        mocker.patch.object(fetcher, "file_system_client")

        # Mock the extract method to avoid actual file operations
        mocker.patch.object(mock_tar, "extract")

        # Call the method
        fetcher._extract_with_tarfile(archive_path, target_dir)

        # Spinner update_progress should be called for each file extracted
        assert mock_spinner.update_progress.called

    def test_extract_with_tarfile_exception_handling(self, fetcher, mocker, tmp_path):
        """Test _extract_with_tarfile exception handling path."""
        archive_path = tmp_path / "test.tar"
        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock _get_archive_info to return normal values
        mocker.patch.object(fetcher, "_get_archive_info", return_value=(2, 1024))

        # Mock tarfile operations to simulate an exception during extraction
        import tarfile

        _ = tarfile.open
        mock_tar = mocker.MagicMock()
        mock_member = mocker.MagicMock()
        mock_member.name = "file1.txt"
        mock_member.size = 512
        mock_members = [mock_member]

        mock_tar.__enter__.return_value = mock_tar
        mock_tar.__exit__.return_value = None
        mock_tar.__iter__.return_value = mock_members
        mock_tar.getmembers.return_value = mock_members

        # Extract should raise an exception
        def extract_side_effect(*args, **kwargs):
            raise Exception("Extraction failed")

        mock_tar.extract.side_effect = extract_side_effect

        # Mock tarfile.open to return our mock
        mocker.patch("tarfile.open", return_value=mock_tar)

        # Mock Spinner
        mock_spinner = mocker.MagicMock()
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)
        mocker.patch.object(fetcher, "file_system_client")

        # Mock logger to verify error logging
        mock_logger = mocker.patch("protonfetcher.logger")

        with pytest.raises(FetchError, match="Failed to extract archive"):
            fetcher._extract_with_tarfile(archive_path, target_dir)

        # Verify error was logged
        assert mock_logger.error.called

    def test_ensure_directory_is_writable_success_when_exists(
        self, fetcher, mocker, tmp_path
    ):
        """Test _ensure_directory_is_writable when directory exists and is writable."""
        directory = tmp_path / "existing_dir"
        directory.mkdir()

        # Mock the file system client methods
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True

        # Mock the write/unlink operations to succeed
        mock_fs.write.return_value = None
        mock_fs.unlink.return_value = None

        # Should not raise any exception
        fetcher._ensure_directory_is_writable(directory)

    def test_ensure_directory_is_writable_creates_new_dir(
        self, fetcher, mocker, tmp_path
    ):
        """Test _ensure_directory_is_writable creates directory if it doesn't exist."""
        directory = tmp_path / "new_dir"

        # Mock the file system client methods
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = False  # Directory doesn't exist initially
        mock_fs.is_dir.return_value = True  # But after creation, it's a directory
        mock_fs.write.return_value = None
        mock_fs.unlink.return_value = None

        # Should create the directory and not raise any exception
        fetcher._ensure_directory_is_writable(directory)

        # Verify that mkdir was called to create the directory
        mock_fs.mkdir.assert_called_with(directory, parents=True, exist_ok=True)

    def test_ensure_directory_is_writable_fails_when_not_a_dir(
        self, fetcher, mocker, tmp_path
    ):
        """Test _ensure_directory_is_writable raises error when path exists but is not a directory."""
        not_a_dir = tmp_path / "not_a_dir"
        not_a_dir.write_text("This is a file, not a directory")

        # Mock the file system client methods
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = False  # Path exists but is not a directory

        with pytest.raises(FetchError, match="not a directory"):
            fetcher._ensure_directory_is_writable(not_a_dir)

    def test_ensure_directory_is_writable_fails_when_not_writable(
        self, fetcher, mocker, tmp_path
    ):
        """Test _ensure_directory_is_writable raises error when directory is not writable."""
        directory = tmp_path / "dir"
        directory.mkdir()

        # Mock the file system client methods
        mock_fs = mocker.patch.object(fetcher, "file_system_client")
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        # Make the write operation fail to simulate non-writable directory
        mock_fs.write.side_effect = OSError("Permission denied")

        with pytest.raises(FetchError, match="not writable"):
            fetcher._ensure_directory_is_writable(directory)


class TestLinkManagementSystem:
    """Integration tests for the link management system."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_get_link_names_for_fork_ge_proton(self, fetcher, tmp_path):
        """Test _get_link_names_for_fork with GE-Proton fork."""
        extract_dir = tmp_path / "extract"

        main, fb1, fb2 = fetcher._get_link_names_for_fork(extract_dir, "GE-Proton")

        assert main == extract_dir / "GE-Proton"
        assert fb1 == extract_dir / "GE-Proton-Fallback"
        assert fb2 == extract_dir / "GE-Proton-Fallback2"

    def test_get_link_names_for_fork_proton_em(self, fetcher, tmp_path):
        """Test _get_link_names_for_fork with Proton-EM fork."""
        extract_dir = tmp_path / "extract"

        main, fb1, fb2 = fetcher._get_link_names_for_fork(extract_dir, "Proton-EM")

        assert main == extract_dir / "Proton-EM"
        assert fb1 == extract_dir / "Proton-EM-Fallback"
        assert fb2 == extract_dir / "Proton-EM-Fallback2"

    def test_find_tag_directory_manual_release_ge_proton(self, fetcher, tmp_path):
        """Test _find_tag_directory for GE-Proton manual release."""
        # Create the expected directory
        expected_dir = tmp_path / "GE-Proton10-11"
        expected_dir.mkdir()

        result = fetcher._find_tag_directory(
            tmp_path, "GE-Proton10-11", "GE-Proton", is_manual_release=True
        )

        assert result == expected_dir

    def test_find_tag_directory_manual_release_proton_em_with_prefix(
        self, fetcher, tmp_path
    ):
        """Test _find_tag_directory for Proton-EM manual release with proton- prefix."""
        # Create the expected directory with proton- prefix
        expected_dir = tmp_path / "proton-EM-10.0-30"
        expected_dir.mkdir()

        result = fetcher._find_tag_directory(
            tmp_path, "EM-10.0-30", "Proton-EM", is_manual_release=True
        )

        assert result == expected_dir

    def test_find_tag_directory_manual_release_proton_em_without_prefix(
        self, fetcher, tmp_path
    ):
        """Test _find_tag_directory for Proton-EM manual release without proton- prefix."""
        # Create the expected directory without proton- prefix (fallback)
        expected_dir = tmp_path / "EM-10.0-30"
        expected_dir.mkdir()

        result = fetcher._find_tag_directory(
            tmp_path, "EM-10.0-30", "Proton-EM", is_manual_release=True
        )

        assert result == expected_dir

    def test_find_tag_directory_not_found(self, fetcher, tmp_path):
        """Test _find_tag_directory when directory doesn't exist."""
        result = fetcher._find_tag_directory(
            tmp_path, "nonexistent", "GE-Proton", is_manual_release=True
        )

        assert result is None

    def test_find_version_candidates_empty_dir(self, fetcher, tmp_path):
        """Test _find_version_candidates with empty directory."""
        candidates = fetcher._find_version_candidates(tmp_path, "GE-Proton")

        assert candidates == []

    def test_find_version_candidates_ge_proton(self, fetcher, tmp_path):
        """Test _find_version_candidates with GE-Proton versions."""
        # Create some version directories
        v1_dir = tmp_path / "GE-Proton10-10"
        v2_dir = tmp_path / "GE-Proton10-11"
        v1_dir.mkdir()
        v2_dir.mkdir()

        # Also create a non-version directory (this will still be included but with fallback parsing)
        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        candidates = fetcher._find_version_candidates(tmp_path, "GE-Proton")

        # Should have 3 candidates (all directories are included but parsed differently)
        assert len(candidates) == 3
        versions = [candidate[0] for candidate in candidates]
        # Parse expected versions
        from protonfetcher import parse_version

        expected_v1 = parse_version("GE-Proton10-10", "GE-Proton")
        expected_v2 = parse_version("GE-Proton10-11", "GE-Proton")
        expected_other = parse_version("other_dir", "GE-Proton")  # fallback parsing
        assert expected_v1 in versions
        assert expected_v2 in versions
        assert expected_other in versions

    def test_find_version_candidates_proton_em(self, fetcher, tmp_path):
        """Test _find_version_candidates with Proton-EM versions (with proton- prefix)."""
        # Create some Proton-EM version directories with proton- prefix
        v1_dir = tmp_path / "proton-EM-10.0-30"
        v2_dir = tmp_path / "proton-EM-10.0-31"
        v1_dir.mkdir()
        v2_dir.mkdir()

        # Also create a non-version directory (this will still be included but with fallback parsing)
        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        candidates = fetcher._find_version_candidates(tmp_path, "Proton-EM")

        # Should have 3 candidates (all directories are included but parsed differently)
        assert len(candidates) == 3
        versions = [candidate[0] for candidate in candidates]
        # Parse expected versions (the method strips the proton- prefix for parsing)
        from protonfetcher import parse_version

        expected_v1 = parse_version("EM-10.0-30", "Proton-EM")  # Strips "proton-"
        expected_v2 = parse_version("EM-10.0-31", "Proton-EM")
        expected_other = parse_version("other_dir", "Proton-EM")  # fallback parsing
        assert expected_v1 in versions
        assert expected_v2 in versions
        assert expected_other in versions

    def test_create_symlinks_success(self, fetcher, mocker, tmp_path):
        """Test _create_symlinks method success case."""
        # Create some version candidates
        dir1 = tmp_path / "GE-Proton10-1"
        dir1.mkdir()
        dir2 = tmp_path / "GE-Proton9-15"
        dir2.mkdir()
        dir3 = tmp_path / "GE-Proton8-20"
        dir3.mkdir()

        # Create symlinks
        main = tmp_path / "GE-Proton"
        fallback = tmp_path / "GE-Proton-Fallback"
        fallback2 = tmp_path / "GE-Proton-Fallback2"

        # Set up candidates (version, path) tuples
        top_3 = [
            ((10, 1, 0, 0), dir1),  # Newest
            ((9, 15, 0, 0), dir2),  # Second newest
            ((8, 20, 0, 0), dir3),  # Third newest
        ]

        # Mock file system client methods
        mock_fs = mocker.MagicMock()
        fetcher.file_system_client = mock_fs

        # Configure mocks
        mock_fs.exists.return_value = False  # symlinks don't exist yet
        mock_fs.is_symlink.return_value = False
        mock_fs.resolve.return_value = dir1  # For comparison
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        # Test the _create_symlinks method
        fetcher._create_symlinks(main, fallback, fallback2, top_3)

        # Verify the symlink creation calls
        assert mock_fs.symlink_to.call_count == 3  # Main, fallback, fallback2

    def test_create_symlinks_with_existing_symlinks(self, fetcher, tmp_path):
        """Test _create_symlinks when symlinks already exist and need to be updated."""
        # Create some version candidates
        dir1 = tmp_path / "GE-Proton10-1"
        dir1.mkdir()
        dir2 = tmp_path / "GE-Proton9-15"
        dir2.mkdir()
        dir3 = tmp_path / "GE-Proton8-5"
        dir3.mkdir()

        # Create old symlinks pointing to different (non-existent) targets
        main = tmp_path / "GE-Proton"
        fallback = tmp_path / "GE-Proton-Fallback"
        fallback2 = tmp_path / "GE-Proton-Fallback2"

        # Create old symlinks pointing to non-existent old targets
        old_target = tmp_path / "old_target"
        main.symlink_to(old_target, target_is_directory=True)
        fallback.symlink_to(old_target, target_is_directory=True)
        fallback2.symlink_to(old_target, target_is_directory=True)

        # Verify they are symlinks pointing to the old target
        assert main.is_symlink()
        assert fallback.is_symlink()
        assert fallback2.is_symlink()

        # Set up candidates (version, path) tuples with proper format
        top_3 = [
            (("GE-Proton", 10, 0, 1), dir1),  # Newest
            (("GE-Proton", 9, 0, 15), dir2),  # Second newest
            (("GE-Proton", 8, 0, 5), dir3),  # Third newest
        ]

        # Test the _create_symlinks method
        fetcher._create_symlinks(main, fallback, fallback2, top_3)

        # Verify all symlinks exist and point to correct targets
        assert main.is_symlink()
        assert fallback.is_symlink()
        assert fallback2.is_symlink()

        # Verify they point to the correct new targets (using relative paths)
        assert main.resolve() == dir1.resolve()
        assert fallback.resolve() == dir2.resolve()
        assert fallback2.resolve() == dir3.resolve()

    def test_create_symlinks_with_resolve_oserror(self, fetcher, mocker, tmp_path):
        """Test _create_symlinks when resolve raises OSError (broken symlink)."""
        # Create some version candidates
        dir1 = tmp_path / "GE-Proton10-1"
        dir1.mkdir()
        dir2 = tmp_path / "GE-Proton9-15"
        dir2.mkdir()
        dir3 = tmp_path / "GE-Proton8-20"
        dir3.mkdir()

        # Create symlinks
        main = tmp_path / "GE-Proton"
        fallback = tmp_path / "GE-Proton-Fallback"
        fallback2 = tmp_path / "GE-Proton-Fallback2"

        # Create a broken symlink
        main.symlink_to(tmp_path / "nonexistent")

        # Set up candidates (version, path) tuples
        top_3 = [
            ((10, 1, 0, 0), dir1),  # Newest
            ((9, 15, 0, 0), dir2),  # Second newest
            ((8, 20, 0, 0), dir3),  # Third newest
        ]

        # Mock file system client methods
        mock_fs = mocker.MagicMock()
        fetcher.file_system_client = mock_fs

        # Configure mocks for the different scenarios
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        mock_fs.resolve.side_effect = OSError("Broken symlink")
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        # Test the _create_symlinks method
        fetcher._create_symlinks(main, fallback, fallback2, top_3)

        # Verify the unlink was called (to remove broken symlink)
        mock_fs.unlink.assert_called()

    def test_manage_proton_links_success_case(self, fetcher, mocker, tmp_path):
        """Test _manage_proton_links success case."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create a version directory that should be found
        tag_dir = extract_dir / "GE-Proton10-11"
        tag_dir.mkdir()

        # Create some other version directories for comparison
        old_version = extract_dir / "GE-Proton9-15"
        old_version.mkdir()

        # Mock the helper methods
        mocker.patch.object(
            fetcher,
            "_get_link_names_for_fork",
            return_value=(
                extract_dir / "GE-Proton",
                extract_dir / "GE-Proton-Fallback",
                extract_dir / "GE-Proton-Fallback2",
            ),
        )
        mocker.patch.object(fetcher, "_find_tag_directory", return_value=tag_dir)
        mocker.patch.object(
            fetcher,
            "_find_version_candidates",
            return_value=[
                (("GE-Proton", 10, 0, 11), tag_dir),
                (("GE-Proton", 9, 0, 15), old_version),
            ],
        )
        mock_create_symlinks = mocker.patch.object(fetcher, "_create_symlinks")

        # Call the method
        fetcher._manage_proton_links(
            extract_dir, "GE-Proton10-11", "GE-Proton", is_manual_release=True
        )

        # Verify the create_symlinks method was called
        mock_create_symlinks.assert_called()

    def test_manage_proton_links_missing_expected_directory(
        self, fetcher, mocker, tmp_path
    ):
        """Test _manage_proton_links when expected extracted directory doesn't exist."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Don't create the expected directory
        manual_tag = "GE-Proton9-5"

        # Mock the helper methods
        mocker.patch.object(
            fetcher,
            "_get_link_names_for_fork",
            return_value=(
                extract_dir / "GE-Proton",
                extract_dir / "GE-Proton-Fallback",
                extract_dir / "GE-Proton-Fallback2",
            ),
        )
        mocker.patch.object(
            fetcher, "_find_tag_directory", return_value=None
        )  # Directory not found
        mock_find_candidates = mocker.patch.object(fetcher, "_find_version_candidates")
        mock_create_symlinks = mocker.patch.object(fetcher, "_create_symlinks")

        # Mock logger to verify warning
        mock_logger = mocker.patch("protonfetcher.logger")

        # Call the method
        fetcher._manage_proton_links(
            extract_dir, manual_tag, "GE-Proton", is_manual_release=True
        )

        # Verify that find_version_candidates was NOT called since the function returns early
        mock_find_candidates.assert_not_called()
        # create_symlinks should also NOT be called since the function returns early
        mock_create_symlinks.assert_not_called()

        # Verify warning was logged about missing directory
        assert any(
            "Expected extracted directory does not exist" in str(call)
            for call in mock_logger.warning.call_args_list
        )

    def test_manage_proton_links_no_candidates_found(self, fetcher, mocker, tmp_path):
        """Test _manage_proton_links when no version candidates are found."""
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create the expected directory
        tag_dir = extract_dir / "GE-Proton10-11"
        tag_dir.mkdir()

        # Mock the helper methods
        mocker.patch.object(
            fetcher,
            "_get_link_names_for_fork",
            return_value=(
                extract_dir / "GE-Proton",
                extract_dir / "GE-Proton-Fallback",
                extract_dir / "GE-Proton-Fallback2",
            ),
        )
        mocker.patch.object(fetcher, "_find_tag_directory", return_value=tag_dir)
        mocker.patch.object(
            fetcher, "_find_version_candidates", return_value=[]
        )  # No candidates
        mock_create_symlinks = mocker.patch.object(fetcher, "_create_symlinks")

        # Mock logger to verify warning
        mock_logger = mocker.patch("protonfetcher.logger")

        # Call the method
        fetcher._manage_proton_links(
            extract_dir, "GE-Proton10-11", "GE-Proton", is_manual_release=True
        )

        # create_symlinks should not be called since there are no candidates
        mock_create_symlinks.assert_not_called()

        # Verify warning was logged about no candidates
        assert any(
            "No extracted Proton directories found" in str(call)
            for call in mock_logger.warning.call_args_list
        )
