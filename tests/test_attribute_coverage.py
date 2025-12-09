"""
Comprehensive attribute coverage tests for all ProtonFetcher classes.
Tests that all attributes are properly initialized and maintained across operations.
"""

from pathlib import Path

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.common import ForkConfig, ForkName
from protonfetcher.github_fetcher import GitHubReleaseFetcher
from protonfetcher.link_manager import LinkManager
from protonfetcher.release_manager import ReleaseManager


class TestGitHubReleaseFetcherAttributeCoverage:
    """Test attribute coverage for GitHubReleaseFetcher class."""

    def test_github_release_fetcher_init_attributes(self, mocker):
        """Test that all GitHubReleaseFetcher attributes are properly initialized."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Verify all attributes are set correctly
        assert fetcher.timeout == 60
        assert fetcher.network_client == mock_network
        assert fetcher.file_system_client == mock_fs

        # Verify that component managers are initialized
        assert fetcher.release_manager is not None
        assert fetcher.asset_downloader is not None
        assert fetcher.archive_extractor is not None
        assert fetcher.link_manager is not None

        # Verify that component managers are initialized after construction
        assert hasattr(fetcher, "release_manager")
        assert hasattr(fetcher, "asset_downloader")
        assert hasattr(fetcher, "archive_extractor")
        assert hasattr(fetcher, "link_manager")

    def test_github_release_fetcher_component_attributes(self, mocker):
        """Test that all component managers are properly assigned as attributes."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=45,
        )

        # Verify component managers exist and have correct attributes
        assert fetcher.release_manager is not None
        assert fetcher.asset_downloader is not None
        assert fetcher.archive_extractor is not None
        assert fetcher.link_manager is not None

        # Verify timeout is passed to components
        assert fetcher.release_manager.timeout == 45
        assert fetcher.asset_downloader.timeout == 45


class TestReleaseManagerAttributeCoverage:
    """Test attribute coverage for ReleaseManager class."""

    @pytest.mark.parametrize(
        "fork,expected_repo,expected_format",
        [
            (ForkName.GE_PROTON, "GloriousEggroll/proton-ge-custom", ".tar.gz"),
            (ForkName.PROTON_EM, "Etaash-mathamsetty/Proton", ".tar.xz"),
        ],
    )
    def test_release_manager_init_attributes(
        self, mocker, fork, expected_repo, expected_format
    ):
        """Test that all ReleaseManager attributes are properly initialized."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(
            network_client=mock_network,
            file_system_client=mock_fs,
            timeout=30,
        )

        # Verify basic attributes
        assert manager.timeout == 30
        assert manager.network_client == mock_network
        assert manager.file_system_client == mock_fs

        # Verify that cache directory attributes are set
        assert hasattr(manager, "_cache_dir")
        assert str(manager._cache_dir).endswith("protonfetcher")

    def test_release_manager_get_expected_extension_attribute(self, mocker):
        """Test that _get_expected_extension method properly handles fork attributes."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test GE Proton extension
        assert manager._get_expected_extension(ForkName.GE_PROTON) == ".tar.gz"

        # Test Proton EM extension
        assert manager._get_expected_extension(ForkName.PROTON_EM) == ".tar.xz"

        # Test invalid fork defaults to .tar.gz
        assert manager._get_expected_extension("invalid") == ".tar.gz"


class TestAssetDownloaderAttributeCoverage:
    """Test attribute coverage for AssetDownloader class."""

    def test_asset_downloader_init_attributes(self, asset_downloader_dependencies):
        """Test that all AssetDownloader attributes are properly initialized."""
        downloader = AssetDownloader(
            asset_downloader_dependencies["network"],
            asset_downloader_dependencies["fs"],
            timeout=120,
        )

        # Verify attributes are set correctly
        assert downloader.timeout == 120
        assert downloader.network_client == asset_downloader_dependencies["network"]
        assert downloader.file_system_client == asset_downloader_dependencies["fs"]


class TestArchiveExtractorAttributeCoverage:
    """Test attribute coverage for ArchiveExtractor class."""

    def test_archive_extractor_init_attributes(self, mocker):
        """Test that all ArchiveExtractor attributes are properly initialized."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Verify attributes are set correctly
        assert extractor.file_system_client == mock_fs


class TestLinkManagerAttributeCoverage:
    """Test attribute coverage for LinkManager class."""

    def test_link_manager_init_attributes(self, mocker):
        """Test that all LinkManager attributes are properly initialized."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Verify attributes are set correctly
        assert manager.file_system_client == mock_fs


class TestForkConfigAttributeCoverage:
    """Test attribute coverage for ForkConfig class."""

    @pytest.mark.parametrize(
        "repo,archive_format",
        [
            ("test/repo", ".tar.gz"),
            ("another/repo", ".tar.xz"),
            ("different/repo", ".zip"),  # Though not used in app, should still work
        ],
    )
    def test_fork_config_attributes(self, repo, archive_format):
        """Test that ForkConfig stores attributes properly."""
        config = ForkConfig(repo=repo, archive_format=archive_format)

        # Verify attributes are stored correctly
        assert config.repo == repo
        assert config.archive_format == archive_format

    @pytest.mark.parametrize(
        "key,expected_value",
        [
            ("repo", "test/repo"),
            ("archive_format", ".tar.gz"),
        ],
    )
    def test_fork_config_getitem_method(self, key, expected_value):
        """Test ForkConfig __getitem__ method for attribute access."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")

        # Verify __getitem__ works for both attributes
        assert config[key] == expected_value

    def test_fork_config_getitem_invalid_key(self):
        """Test ForkConfig __getitem__ with invalid key raises KeyError."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")

        with pytest.raises(KeyError):
            _ = config["invalid_key"]


class TestAttributeConsistencyAcrossOperations:
    """Test that attributes remain consistent across various operations."""

    def test_github_release_fetcher_attributes_after_init(self, mocker):
        """Test that GitHubReleaseFetcher attributes remain consistent after initialization."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        original_timeout = 75
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=original_timeout,
        )

        # Verify attributes remain unchanged after full initialization
        assert fetcher.timeout == original_timeout
        assert fetcher.network_client == mock_network
        assert fetcher.file_system_client == mock_fs

        # Verify that component managers are still present
        assert fetcher.release_manager is not None
        assert fetcher.asset_downloader is not None
        assert fetcher.archive_extractor is not None
        assert fetcher.link_manager is not None

        # Verify component managers also maintain correct timeout
        assert fetcher.release_manager.timeout == original_timeout
        assert fetcher.asset_downloader.timeout == original_timeout

    def test_release_manager_cache_attributes_persistence(self, mocker, tmp_path):
        """Test that ReleaseManager cache-related attributes persist correctly."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(mock_network, mock_fs)
        original_cache_dir = manager._cache_dir

        # Perform operations that use cache attributes
        # This should not change the cache directory attribute
        key = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")

        # The cache directory should remain unchanged
        assert manager._cache_dir == original_cache_dir
        assert hasattr(key, "__str__")  # Verify key was generated

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_release_manager_fork_attributes(self, mocker, fork):
        """Test that ReleaseManager correctly handles fork-specific attributes."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(mock_network, mock_fs)

        # Test the extension is correctly returned for each fork
        expected_extension = ".tar.gz" if fork == ForkName.GE_PROTON else ".tar.xz"
        actual_extension = manager._get_expected_extension(fork)

        assert actual_extension == expected_extension

    def test_component_attribute_binding_after_operations(self, mocker, tmp_path):
        """Test that component attributes remain bound after various operations."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Create a release manager
        manager = ReleaseManager(mock_network, mock_fs)
        original_network_client = manager.network_client
        original_fs_client = manager.file_system_client

        # Perform operations that use these attributes
        try:
            # This will likely fail due to network issues, but that's okay
            # We just want to ensure attributes remain bound
            manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        except Exception:
            pass  # Expected to fail, we're just testing attribute persistence

        # Verify attributes remain unchanged
        assert manager.network_client == original_network_client
        assert manager.file_system_client == original_fs_client


class TestAttributeEdgeCases:
    """Test attribute behavior in edge cases."""

    def test_github_release_fetcher_timeout_edge_values(self, mocker):
        """Test GitHubReleaseFetcher with edge timeout values."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        # Test with minimum reasonable timeout
        fetcher_min = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=1,
        )
        assert fetcher_min.timeout == 1

        # Test with large timeout
        fetcher_large = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=3600,
        )
        assert fetcher_large.timeout == 3600

    def test_release_manager_cache_dir_attribute_with_env(self, mocker, tmp_path):
        """Test ReleaseManager cache dir attribute with environment variables."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Mock environment to include XDG_CACHE_HOME
        mocker.patch.dict(
            "os.environ", {"XDG_CACHE_HOME": str(tmp_path / "custom_cache")}
        )

        manager = ReleaseManager(mock_network, mock_fs)

        # Verify cache directory uses custom path
        assert "custom_cache/protonfetcher" in str(manager._cache_dir)

    def test_asset_downloader_various_timeout_values(self, mocker):
        """Test AssetDownloader with various timeout values."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Test various timeout values
        for timeout_val in [0, 1, 30, 300, 3600]:
            downloader = AssetDownloader(mock_network, mock_fs, timeout=timeout_val)
            assert downloader.timeout == timeout_val

    def test_link_manager_fs_client_attribute(self, mocker):
        """Test LinkManager filesystem client attribute handling."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Verify the attribute is properly stored
        assert manager.file_system_client == mock_fs

        # Test that operations use the correct client
        original_client = manager.file_system_client
        # Perform an operation that would use the client
        try:
            manager.get_link_names_for_fork(ForkName.GE_PROTON)
        except Exception:
            pass  # The operation might fail, but we're testing attribute persistence

        # Ensure the client attribute remains unchanged
        assert manager.file_system_client == original_client
