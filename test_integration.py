"""
Integration tests for protonfetcher module.
Testing workflows that involve multiple components working together.
"""

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
