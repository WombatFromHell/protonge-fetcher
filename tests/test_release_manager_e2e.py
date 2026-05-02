"""
End-to-end tests for ReleaseManager release discovery and asset resolution.

Tests the complete release discovery workflow:
- Fetching latest release tags via redirect
- Finding assets via GitHub API
- HTML parsing fallback
- Listing recent releases
- Asset size caching
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import NetworkError
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.release_manager import ReleaseManager


class TestFetchLatestTag:
    """Test fetching latest release tag via GitHub redirect."""

    def test_fetch_latest_tag_ge_proton(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test fetching latest GE-Proton tag via redirect."""
        # Arrange
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/GE-Proton10-20",
            stderr="",
        )
        mock_network_client.head.return_value = mock_head_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        latest_tag = release_manager.fetch_latest_tag(
            repo="GloriousEggroll/proton-ge-custom"
        )

        # Assert
        assert latest_tag == "GE-Proton10-20"
        mock_network_client.head.assert_called_once_with(
            "https://github.com/GloriousEggroll/proton-ge-custom/releases/latest"
        )

    def test_fetch_latest_tag_proton_em(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test fetching latest Proton-EM tag via redirect."""
        # Arrange
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: https://github.com/Etaash-mathamsetty/Proton/releases/tag/EM-10.0-30",
            stderr="",
        )
        mock_network_client.head.return_value = mock_head_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        latest_tag = release_manager.fetch_latest_tag(repo="Etaash-mathamsetty/Proton")

        # Assert
        assert latest_tag == "EM-10.0-30"

    def test_fetch_latest_tag_network_error(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling network error when fetching latest tag."""
        # Arrange
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,
            stdout="",
            stderr="404 Not Found",
        )
        mock_network_client.head.return_value = mock_head_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act & Assert
        with pytest.raises(NetworkError, match="Failed to fetch latest tag"):
            release_manager.fetch_latest_tag(repo="invalid/repo")

    def test_fetch_latest_tag_no_redirect(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling when no redirect is found."""
        # Arrange
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",  # No Location header
            stderr="",
        )
        mock_network_client.head.return_value = mock_head_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act & Assert
        with pytest.raises(NetworkError, match="Could not determine latest tag"):
            release_manager.fetch_latest_tag(repo="GloriousEggroll/proton-ge-custom")


class TestFindAssetByName:
    """Test finding assets in GitHub releases."""

    def test_find_asset_via_api_ge_proton(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding GE-Proton asset via GitHub API."""
        # Arrange
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "assets": [
                        {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
                        {"name": "source.tar.gz", "size": 1024},
                    ]
                }
            ),
            stderr="",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        asset_name = release_manager.find_asset_by_name(
            repo="GloriousEggroll/proton-ge-custom",
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
        )

        # Assert
        assert asset_name == "GE-Proton10-20.tar.gz"

    def test_find_asset_via_api_proton_em(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding Proton-EM asset via GitHub API."""
        # Arrange
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "assets": [
                        {"name": "proton-EM-10.0-30.tar.xz", "size": 2097152},
                        {"name": "source.tar.gz", "size": 1024},
                    ]
                }
            ),
            stderr="",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        asset_name = release_manager.find_asset_by_name(
            repo="Etaash-mathamsetty/Proton",
            tag="EM-10.0-30",
            fork=ForkName.PROTON_EM,
        )

        # Assert
        assert asset_name == "proton-EM-10.0-30.tar.xz"

    def test_find_asset_via_api_cachyos_selects_x86_64(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding CachyOS x86_64 asset via GitHub API when multiple architectures exist.

        CachyOS releases have multiple architecture variants (arm64, x86_64, x86_64_v2, etc.).
        This test ensures the x86_64 variant is specifically selected.
        """
        # Arrange - Simulate CachyOS release with multiple architecture variants
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "assets": [
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-arm64.tar.xz",
                            "size": 1048576,
                        },
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-arm64.sha512sum",
                            "size": 128,
                        },
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-x86_64.tar.xz",
                            "size": 2097152,
                        },
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-x86_64.sha512sum",
                            "size": 128,
                        },
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-x86_64_v2.tar.xz",
                            "size": 2097152,
                        },
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-x86_64_v3.tar.xz",
                            "size": 2097152,
                        },
                        {
                            "name": "proton-cachyos-10.0-20260207-slr-x86_64_v4.tar.xz",
                            "size": 2097152,
                        },
                    ]
                }
            ),
            stderr="",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        asset_name = release_manager.find_asset_by_name(
            repo="CachyOS/proton-cachyos",
            tag="cachyos-10.0-20260207-slr",
            fork=ForkName.CACHYOS,
        )

        # Assert - Should specifically select x86_64, not arm64 or other variants
        assert asset_name == "proton-cachyos-10.0-20260207-slr-x86_64.tar.xz"

    def test_find_asset_html_fallback(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding asset via HTML parsing when API fails."""
        # Arrange: API fails
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,
            stdout="",
            stderr="403 Forbidden",
        )
        mock_network_client.get.return_value = api_response

        # HTML response contains asset name
        html_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="<html><body>GE-Proton10-20.tar.gz</body></html>",
            stderr="",
        )
        # Second call (HTML fallback) returns HTML
        mock_network_client.get.side_effect = [api_response, html_response]

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        asset_name = release_manager.find_asset_by_name(
            repo="GloriousEggroll/proton-ge-custom",
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
        )

        # Assert
        assert asset_name == "GE-Proton10-20.tar.gz"

    def test_find_asset_not_found(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling when asset is not found."""
        # Arrange: Both API and HTML fail
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,
            stdout="",
            stderr="403 Forbidden",
        )
        html_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="<html><body>No assets</body></html>",
            stderr="",
        )
        mock_network_client.get.side_effect = [api_response, html_response]

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        asset_name = release_manager.find_asset_by_name(
            repo="GloriousEggroll/proton-ge-custom",
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
        )

        # Assert
        assert asset_name is None

    def test_find_asset_empty_assets_list(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling when API returns empty assets list."""
        # Arrange: API returns empty, HTML fallback also fails
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"assets": []}),
            stderr="",
        )
        html_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="<html><body>No assets found</body></html>",
            stderr="",
        )
        # First call is API, second is HTML fallback
        mock_network_client.get.side_effect = [api_response, html_response]

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act: Should return None when asset not found
        result = release_manager.find_asset_by_name(
            repo="GloriousEggroll/proton-ge-custom",
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
        )

        # Assert: Returns None when asset not found
        assert result is None


class TestListRecentReleases:
    """Test listing recent releases from GitHub API."""

    def test_list_recent_releases_ge_proton(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test listing recent GE-Proton releases."""
        # Arrange
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {"tag_name": "GE-Proton10-20"},
                    {"tag_name": "GE-Proton10-19"},
                    {"tag_name": "GE-Proton10-18"},
                    {"tag_name": "GE-Proton10-17"},
                    {"tag_name": "GE-Proton10-16"},
                ]
            ),
            stderr="",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        releases = release_manager.list_recent_releases(
            repo="GloriousEggroll/proton-ge-custom"
        )

        # Assert
        assert len(releases) == 5
        assert releases[0] == "GE-Proton10-20"
        assert releases[4] == "GE-Proton10-16"

    def test_list_recent_releases_proton_em(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test listing recent Proton-EM releases."""
        # Arrange
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {"tag_name": "EM-10.0-30"},
                    {"tag_name": "EM-10.0-29"},
                    {"tag_name": "EM-10.0-28"},
                ]
            ),
            stderr="",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        releases = release_manager.list_recent_releases(
            repo="Etaash-mathamsetty/Proton"
        )

        # Assert
        assert len(releases) == 3
        assert releases[0] == "EM-10.0-30"

    def test_list_recent_releases_limits_to_20(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test that recent releases are limited to 20."""
        # Arrange: Return 25 releases
        releases_data = [{"tag_name": f"GE-Proton10-{i}"} for i in range(25)]
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(releases_data),
            stderr="",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        releases = release_manager.list_recent_releases(
            repo="GloriousEggroll/proton-ge-custom"
        )

        # Assert
        assert len(releases) == 20

    def test_list_recent_releases_rate_limit_error(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling GitHub API rate limit error."""
        # Arrange
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"message": "API rate limit exceeded"}',
            stderr="403 Forbidden",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act & Assert
        with pytest.raises(NetworkError, match="rate limit"):
            release_manager.list_recent_releases(
                repo="GloriousEggroll/proton-ge-custom"
            )

    def test_list_recent_releases_network_error(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling network error when listing releases."""
        # Arrange
        api_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,
            stdout="",
            stderr="Connection failed",
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act & Assert
        with pytest.raises(NetworkError, match="Failed to fetch releases"):
            release_manager.list_recent_releases(
                repo="GloriousEggroll/proton-ge-custom"
            )


class TestAssetSizeCaching:
    """Test asset size caching behavior."""

    def test_get_remote_asset_size_caching_behavior(
        self,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test that asset size caching is disabled during tests."""
        # Arrange
        fs = FileSystemClient()

        import os

        old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(tmp_path)

        try:
            mock_head_response = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Content-Length: 1048576",
                stderr="",
            )
            mock_network_client.head.return_value = mock_head_response

            release_manager = ReleaseManager(mock_network_client, fs)

            # Act: First call
            size1 = release_manager.get_remote_asset_size(
                repo="GloriousEggroll/proton-ge-custom",
                tag="GE-Proton10-20",
                asset_name="GE-Proton10-20.tar.gz",
            )

            # Act: Second call (would use cache if not in test mode)
            size2 = release_manager.get_remote_asset_size(
                repo="GloriousEggroll/proton-ge-custom",
                tag="GE-Proton10-20",
                asset_name="GE-Proton10-20.tar.gz",
            )

            # Assert: Both calls return the same size
            assert size1 == 1048576
            assert size2 == 1048576
            # Note: Cache files are not created during tests to preserve test isolation

        finally:
            # Restore environment
            if old_cache:
                os.environ["XDG_CACHE_HOME"] = old_cache
            else:
                del os.environ["XDG_CACHE_HOME"]

    def test_get_cached_asset_size_expired(
        self,
        mock_network_client: Any,
        tmp_path: Path,
        mocker: pytest.FixtureRequest,
    ) -> None:
        """Test that expired cache is not used."""
        # Arrange
        fs = FileSystemClient()

        import os

        old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(tmp_path)

        try:
            # Create expired cache
            release_manager = ReleaseManager(mock_network_client, fs)
            cache_path = release_manager._get_cache_path(
                "GloriousEggroll/proton-ge-custom",
                "GE-Proton10-20",
                "GE-Proton10-20.tar.gz",
            )

            import json
            import time

            expired_data = {
                "size": 1048576,
                "timestamp": time.time() - 7200,  # 2 hours ago (expired)
            }
            cache_path.write_text(json.dumps(expired_data))

            # Set file mtime to 2 hours ago to trigger cache expiration
            old_time = time.time() - 7200
            os.utime(cache_path, (old_time, old_time))

            # Mock fresh network response
            mock_head_response = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Content-Length: 2097152",  # Different size
                stderr="",
            )
            mock_network_client.head.return_value = mock_head_response

            # Act
            size = release_manager.get_remote_asset_size(
                repo="GloriousEggroll/proton-ge-custom",
                tag="GE-Proton10-20",
                asset_name="GE-Proton10-20.tar.gz",
            )

            # Assert: Should fetch fresh size, not use expired cache
            assert size == 2097152

        finally:
            if old_cache:
                os.environ["XDG_CACHE_HOME"] = old_cache
            else:
                del os.environ["XDG_CACHE_HOME"]

    def test_get_remote_asset_size_follows_redirect(
        self,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test that asset size fetch follows redirects."""
        # Use real FileSystemClient to avoid mtime() mock issues
        fs = FileSystemClient()

        # Arrange: curl -L follows redirects internally, so head() is called once
        # with the final response
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Content-Length: 1048576",
            stderr="",
        )

        mock_network_client.head.return_value = mock_head_response

        # Disable caching to ensure network call is made
        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        # Act
        size = release_manager.get_remote_asset_size(
            repo="GloriousEggroll/proton-ge-custom",
            tag="GE-Proton10-20",
            asset_name="GE-Proton10-20.tar.gz",
        )

        # Assert
        assert size == 1048576
        assert mock_network_client.head.call_count == 1

    def test_get_remote_asset_size_404_error(
        self,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test handling 404 error when getting asset size."""
        # Use real FileSystemClient to avoid mtime() mock issues
        fs = FileSystemClient()

        # Arrange
        mock_head_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,
            stdout="",
            stderr="404 Not Found",
        )
        mock_network_client.head.return_value = mock_head_response

        # Disable caching to ensure network call is made
        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        # Act & Assert
        with pytest.raises(NetworkError, match="Remote asset not found"):
            release_manager.get_remote_asset_size(
                repo="GloriousEggroll/proton-ge-custom",
                tag="GE-Proton10-20",
                asset_name="NonExistent.tar.gz",
            )


class TestAssetNameExtension:
    """Test asset extension handling based on fork."""

    def test_get_expected_extension_ge_proton(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test getting expected extension for GE-Proton."""
        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        extension = release_manager._get_expected_extension(ForkName.GE_PROTON)

        # Assert
        assert extension == ".tar.gz"

    def test_get_expected_extension_proton_em(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test getting expected extension for Proton-EM."""
        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        extension = release_manager._get_expected_extension(ForkName.PROTON_EM)

        # Assert
        assert extension == ".tar.xz"

    def test_find_matching_assets(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding assets matching expected extension."""
        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Arrange
        assets = [
            {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
            {"name": "source.tar.gz", "size": 1024},
            {"name": "README.md", "size": 512},
        ]

        # Act
        matching = release_manager._find_matching_assets(assets, ".tar.gz")

        # Assert
        assert len(matching) == 2
        assert matching[0]["name"] == "GE-Proton10-20.tar.gz"


# =============================================================================
# ReleaseManager with forgejo_adapter (Phase 3.2)
# =============================================================================


class TestReleaseManagerForgejoAdapter:
    """Tests verifying ReleaseManager works correctly with forgejo_adapter."""

    def test_release_manager_uses_forgejo_adapter(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test ReleaseManager accepts and uses forgejo_adapter."""
        from protonfetcher.platform_adapters import forgejo_adapter

        release_manager = ReleaseManager(
            mock_network_client,
            mock_filesystem_client,
            platform_adapter=forgejo_adapter,
        )

        assert release_manager.platform_adapter is forgejo_adapter

    def test_release_manager_uses_github_adapter(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test ReleaseManager accepts and uses github_adapter."""
        from protonfetcher.platform_adapters import github_adapter

        release_manager = ReleaseManager(
            mock_network_client,
            mock_filesystem_client,
            platform_adapter=github_adapter,
        )

        assert release_manager.platform_adapter is github_adapter

    def test_forgejo_adapter_builds_correct_api_url(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test forgejo_adapter builds correct API URLs for ReleaseManager."""
        from protonfetcher.platform_adapters import forgejo_adapter

        release_manager = ReleaseManager(
            mock_network_client,
            mock_filesystem_client,
            platform_adapter=forgejo_adapter,
        )

        # list_recent_releases uses build_api_url internally
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps([{"tag_name": "dwproton-10.0-26"}]),
            stderr="",
        )

        releases = release_manager.list_recent_releases("dawn-winery/dwproton")

        assert releases == ["dwproton-10.0-26"]
        # Verify the correct API URL was called
        call_args = mock_network_client.get.call_args
        assert "dawn.wine/api/v1/repos/dawn-winery/dwproton/releases" in str(call_args)

    def test_github_adapter_builds_correct_api_url(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test github_adapter builds correct API URLs for ReleaseManager."""
        from protonfetcher.platform_adapters import github_adapter

        release_manager = ReleaseManager(
            mock_network_client,
            mock_filesystem_client,
            platform_adapter=github_adapter,
        )

        # list_recent_releases uses build_api_url internally
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps([{"tag_name": "GE-Proton10-20"}]),
            stderr="",
        )

        releases = release_manager.list_recent_releases(
            "GloriousEggroll/proton-ge-custom"
        )

        assert releases == ["GE-Proton10-20"]
        call_args = mock_network_client.get.call_args
        assert "api.github.com/repos/GloriousEggroll/proton-ge-custom/releases" in str(
            call_args
        )

    def test_forgejo_adapter_download_url_differs_from_github(
        self,
    ) -> None:
        """Test that forgejo_adapter and github_adapter produce different download URLs."""
        from protonfetcher.platform_adapters import forgejo_adapter, github_adapter

        forgejo_url = forgejo_adapter.build_download_url(
            "dawn-winery/dwproton",
            "dwproton-10.0-26",
            "dwproton-10.0-26-x86_64.tar.xz",
        )
        github_url = github_adapter.build_download_url(
            "GloriousEggroll/proton-ge-custom",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
        )

        assert forgejo_url.startswith("https://dawn.wine/")
        assert github_url.startswith("https://github.com/")
        assert forgejo_url != github_url


# =============================================================================
# check_for_newer_release Tests (moved from test_cli.py)
# =============================================================================


class TestCheckForNewerRelease:
    """Tests for ReleaseManager.check_for_newer_release() method."""

    @pytest.mark.parametrize(
        "fork,repo,current_versions,latest_tag,expected",
        [
            # GE-Proton tests
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                ["GE-Proton10-20"],
                "GE-Proton10-21",
                "GE-Proton10-21",
            ),
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                ["GE-Proton10-20"],
                "GE-Proton10-20",
                None,
            ),
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                [],
                "GE-Proton10-21",
                "GE-Proton10-21",
            ),
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                ["GE-Proton10-18", "GE-Proton10-19", "GE-Proton10-20"],
                "GE-Proton10-22",
                "GE-Proton10-22",
            ),
            # Proton-EM tests (with directory naming convention)
            (
                ForkName.PROTON_EM,
                "Etaash-mathamsetty/Proton",
                ["proton-EM-10.0-30"],
                "EM-10.0-31",
                "EM-10.0-31",
            ),
            (
                ForkName.PROTON_EM,
                "Etaash-mathamsetty/Proton",
                ["proton-EM-10.0-30"],
                "EM-10.0-30",
                None,
            ),
            # CachyOS tests (with directory naming convention)
            (
                ForkName.CACHYOS,
                "CachyOS/proton-cachyos",
                ["proton-cachyos-10.0-20260207-slr-x86_64"],
                "cachyos-10.0-20260227-slr",
                "cachyos-10.0-20260227-slr",
            ),
            (
                ForkName.CACHYOS,
                "CachyOS/proton-cachyos",
                ["proton-cachyos-10.0-20260207-slr-x86_64"],
                "cachyos-10.0-20260207-slr",
                None,
            ),
        ],
    )
    def test_check_for_newer_release(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        fork: ForkName,
        repo: str,
        current_versions: list[str],
        latest_tag: str,
        expected: str | None,
    ) -> None:
        """Test detection of newer releases for all forks."""
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f'{{"tag_name": "{latest_tag}"}}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=f"Location: /releases/tag/{latest_tag}",
            stderr="",
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        result = release_manager.check_for_newer_release(
            repo,
            current_versions,
            fork,
        )

        assert result == expected
