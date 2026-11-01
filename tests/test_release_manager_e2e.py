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
import os
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.common import HttpResponse
from protonfetcher.exceptions import ChecksumError, NetworkError
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.github_fetcher import GitHubReleaseFetcher
from protonfetcher.release_manager import ReleaseManager


class TestFetchLatestTag:
    """Test fetching latest release tag via GitHub redirect."""

    def test_fetch_latest_tag_ge_proton(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test fetching latest Proton-GE tag via redirect."""
        # Arrange
        mock_head_response = HttpResponse(
            status=200,
            final_url="https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/GE-Proton10-20",
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
        mock_head_response = HttpResponse(
            status=200,
            final_url="https://github.com/Etaash-mathamsetty/Proton/releases/tag/EM-10.0-30",
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
        mock_head_response = HttpResponse(status=404)
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
        mock_head_response = HttpResponse(status=200)  # No redirect
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
        """Test finding Proton-GE asset via GitHub API."""
        # Arrange
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "assets": [
                        {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
                        {"name": "source.tar.gz", "size": 1024},
                    ]
                }
            ),
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
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "assets": [
                        {"name": "proton-EM-10.0-30.tar.xz", "size": 2097152},
                        {"name": "source.tar.gz", "size": 1024},
                    ]
                }
            ),
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
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
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

    def test_find_asset_via_api_wineland_selects_v3(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding Proton-Wineland _v3 asset via GitHub API.

        Wineland releases ship -x86_64, -x86_64_v3 and -x86_64_wow64 variants,
        all of which contain "x86_64" in the name. The fork's asset template
        (the _v3 variant) must take precedence over the arch heuristic.
        """
        # Arrange - Simulate Wineland release with multiple variants
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "assets": [
                        {
                            "name": ("proton-wineland-11.0-20261005-x86_64.sha512sum"),
                            "size": 128,
                        },
                        {
                            "name": "proton-wineland-11.0-20261005-x86_64.tar.xz",
                            "size": 2097152,
                        },
                        {
                            "name": (
                                "proton-wineland-11.0-20261005-x86_64_v3.sha512sum"
                            ),
                            "size": 128,
                        },
                        {
                            "name": "proton-wineland-11.0-20261005-x86_64_v3.tar.xz",
                            "size": 2097152,
                        },
                        {
                            "name": (
                                "proton-wineland-11.0-20261005-x86_64_wow64.sha512sum"
                            ),
                            "size": 128,
                        },
                        {
                            "name": "proton-wineland-11.0-20261005-x86_64_wow64.tar.xz",
                            "size": 2097152,
                        },
                    ]
                }
            ),
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act
        asset_name = release_manager.find_asset_by_name(
            repo="nanomatters/proton-cachyos",
            tag="wineland-11.0-20261005",
            fork=ForkName.WINELAND,
        )

        # Assert - Should select the _v3 asset from the fork's asset template
        assert asset_name == "proton-wineland-11.0-20261005-x86_64_v3.tar.xz"

    def test_find_asset_via_api_ge_proton_selects_x86_64(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test Proton-GE selects the x86_64 asset when an aarch64 variant also exists."""
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "assets": [
                        {
                            "name": "GE-Proton11-6-aarch64.tar.gz",
                            "size": 1048576,
                        },
                        {
                            "name": "GE-Proton11-6-x86_64.tar.gz",
                            "size": 2097152,
                        },
                    ]
                }
            ),
        )
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        asset_name = release_manager.find_asset_by_name(
            repo="GloriousEggroll/proton-ge-custom",
            tag="GE-Proton11-6",
            fork=ForkName.GE_PROTON,
        )

        assert asset_name == "GE-Proton11-6-x86_64.tar.gz"

    def test_find_asset_html_fallback(
        self,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test finding asset via HTML parsing when API fails."""
        # Arrange: API fails
        api_response = HttpResponse(status=404)
        mock_network_client.get.return_value = api_response

        # HTML response contains asset name
        html_response = HttpResponse(
            status=200, body="<html><body>GE-Proton10-20.tar.gz</body></html>"
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
        api_response = HttpResponse(status=404)
        html_response = HttpResponse(
            status=200, body="<html><body>No assets</body></html>"
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
        api_response = HttpResponse(status=200, body=json.dumps({"assets": []}))
        html_response = HttpResponse(
            status=200, body="<html><body>No assets found</body></html>"
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
        """Test listing recent Proton-GE releases."""
        # Arrange
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
                [
                    {"tag_name": "GE-Proton10-20"},
                    {"tag_name": "GE-Proton10-19"},
                    {"tag_name": "GE-Proton10-18"},
                    {"tag_name": "GE-Proton10-17"},
                    {"tag_name": "GE-Proton10-16"},
                ]
            ),
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
        api_response = HttpResponse(
            status=200,
            body=json.dumps(
                [
                    {"tag_name": "EM-10.0-30"},
                    {"tag_name": "EM-10.0-29"},
                    {"tag_name": "EM-10.0-28"},
                ]
            ),
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
        api_response = HttpResponse(status=200, body=json.dumps(releases_data))
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
        api_response = HttpResponse(
            status=403, body='{"message": "API rate limit exceeded"}'
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
        api_response = HttpResponse(status=404)
        mock_network_client.get.return_value = api_response

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Act & Assert
        with pytest.raises(NetworkError, match="Failed to fetch releases"):
            release_manager.list_recent_releases(
                repo="GloriousEggroll/proton-ge-custom"
            )


class TestAssetSizeCaching:
    """Asset size and checksum come from the release API listing, cached."""

    REPO = "GloriousEggroll/proton-ge-custom"
    TAG = "GE-Proton10-20"
    ASSET = "GE-Proton10-20.tar.gz"
    HEX512 = "a" * 128

    @staticmethod
    def _release_body(size: int, digest: str | None = None, name: str = ASSET) -> str:
        asset = {"name": name, "size": size}
        if digest is not None:
            asset["digest"] = digest
        return json.dumps({"assets": [asset]})

    def test_get_remote_asset_size_caching_behavior(
        self,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """The release listing is fetched once and reused from cache."""
        fs = FileSystemClient()

        old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(tmp_path)

        try:
            mock_network_client.get.return_value = HttpResponse(
                status=200, body=self._release_body(1048576, "sha256:" + "b" * 64)
            )

            release_manager = ReleaseManager(mock_network_client, fs)

            size1 = release_manager.get_remote_asset_size(
                self.REPO, self.TAG, self.ASSET
            )
            size2 = release_manager.get_remote_asset_size(
                self.REPO, self.TAG, self.ASSET
            )

            assert size1 == 1048576
            assert size2 == 1048576
            assert mock_network_client.get.call_count == 1
        finally:
            if old_cache:
                os.environ["XDG_CACHE_HOME"] = old_cache
            else:
                del os.environ["XDG_CACHE_HOME"]

    def test_get_cached_asset_info_expired(
        self,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Expired cache is not used."""
        fs = FileSystemClient()

        old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(tmp_path)

        try:
            release_manager = ReleaseManager(mock_network_client, fs)
            cache_path = release_manager._get_cache_path(
                self.REPO, self.TAG, self.ASSET
            )

            import time

            expired_data = {
                "size": 1048576,
                "digest": "sha256:" + "b" * 64,
                "timestamp": time.time() - 7200,  # 2 hours ago (expired)
            }
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(expired_data))

            old_time = time.time() - 7200
            os.utime(cache_path, (old_time, old_time))

            mock_network_client.get.return_value = HttpResponse(
                status=200, body=self._release_body(2097152)
            )

            size, digest = release_manager.get_asset_info(
                self.REPO, self.TAG, self.ASSET
            )

            assert size == 2097152
            assert digest is None
        finally:
            if old_cache:
                os.environ["XDG_CACHE_HOME"] = old_cache
            else:
                del os.environ["XDG_CACHE_HOME"]

    def test_asset_size_comes_from_api_listing(
        self,
        mock_network_client: Any,
    ) -> None:
        """Size comes from the release listing — no HEAD request, which dawn.wine rejects."""
        fs = FileSystemClient()

        mock_network_client.get.return_value = HttpResponse(
            status=200, body=self._release_body(1048576)
        )

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        size = release_manager.get_remote_asset_size(self.REPO, self.TAG, self.ASSET)

        assert size == 1048576
        assert mock_network_client.head.call_count == 0

    def test_asset_info_missing_asset_raises(
        self,
        mock_network_client: Any,
    ) -> None:
        """An asset the listing does not contain is reported as not found."""
        fs = FileSystemClient()

        mock_network_client.get.return_value = HttpResponse(
            status=200, body=self._release_body(1024, name="Other.tar.gz")
        )

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        with pytest.raises(NetworkError, match="Remote asset not found"):
            release_manager.get_asset_info(self.REPO, self.TAG, self.ASSET)

    def test_asset_info_api_failure_raises(
        self,
        mock_network_client: Any,
    ) -> None:
        """A failed API request must not look like an unknown size."""
        fs = FileSystemClient()

        mock_network_client.get.return_value = HttpResponse(status=500)

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        with pytest.raises(NetworkError, match="HTTP 500"):
            release_manager.get_asset_info(self.REPO, self.TAG, self.ASSET)

    def test_listing_without_size_cannot_be_verified(
        self,
        mock_network_client: Any,
    ) -> None:
        """A listing asset with no size cannot gate a download."""
        fs = FileSystemClient()

        mock_network_client.get.return_value = HttpResponse(
            status=200,
            body=json.dumps({"assets": [{"name": self.ASSET}]}),
        )

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        assert (
            release_manager.get_asset_info(self.REPO, self.TAG, self.ASSET).size is None
        )
        with pytest.raises(NetworkError, match="Could not determine size"):
            release_manager.get_remote_asset_size(self.REPO, self.TAG, self.ASSET)

    def test_digest_falls_back_to_the_checksum_asset(
        self,
        mock_network_client: Any,
    ) -> None:
        """Forgejo has no digest field, so the published .sha512sum asset is used."""
        fs = FileSystemClient()

        mock_network_client.get.side_effect = [
            HttpResponse(status=200, body=self._release_body(339558796)),
            HttpResponse(status=200, body=f"{self.HEX512}  {self.ASSET}\n"),
        ]

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        size, digest = release_manager.get_asset_info(self.REPO, self.TAG, self.ASSET)

        assert size == 339558796
        assert digest == f"sha512:{self.HEX512}"
        assert mock_network_client.get.call_count == 2
        # The stem drops the whole archive suffix, not just the last dot.
        assert mock_network_client.get.call_args_list[1][0][0].endswith(
            "/GE-Proton10-20.sha512sum"
        )

    def test_missing_checksum_asset_is_not_a_failure(
        self,
        mock_network_client: Any,
    ) -> None:
        """No published checksum means no digest — verification is skipped, not failed."""
        fs = FileSystemClient()

        mock_network_client.get.side_effect = [
            HttpResponse(status=200, body=self._release_body(1024)),
            HttpResponse(status=404),
            HttpResponse(status=404),
        ]

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        size, digest = release_manager.get_asset_info(self.REPO, self.TAG, self.ASSET)

        assert size == 1024
        assert digest is None

    def test_malformed_checksum_asset_is_ignored(
        self,
        mock_network_client: Any,
    ) -> None:
        """A body that is not a hex digest yields no digest."""
        fs = FileSystemClient()

        mock_network_client.get.side_effect = [
            HttpResponse(status=200, body=self._release_body(1024)),
            HttpResponse(status=200, body="not a checksum"),
            HttpResponse(status=200, body="zz" * 64),
        ]

        release_manager = ReleaseManager(mock_network_client, fs, cache_enabled=False)

        size, digest = release_manager.get_asset_info(self.REPO, self.TAG, self.ASSET)

        assert size == 1024
        assert digest is None

    def test_stale_cached_checksum_is_dropped_when_the_download_fails(
        self,
        mock_network_client: Any,
        mock_urllib_download: Any,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """A republished asset makes the cached digest wrong — stop serving it."""
        fs = FileSystemClient()
        manager = ReleaseManager(mock_network_client, fs)
        cache_path = manager._get_cache_path(self.REPO, self.TAG, self.ASSET)
        manager._cache_asset_info(
            self.REPO, self.TAG, self.ASSET, 800, "sha256:" + "0" * 64
        )
        assert cache_path.exists()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
            timeout=30,
        )
        mocker.patch.object(fetcher, "_resolve_asset", return_value=self.ASSET)
        mocker.patch.object(
            fetcher,
            "_build_download_url",
            return_value=f"https://example.com/repo/releases/download/{self.TAG}/{self.ASSET}",
        )
        # Two attempts: the cached digest rejects the first, so the fresh retry needs bytes too.
        mock_urllib_download(
            chunks=[b"z" * 800, b"", b"z" * 800, b""], content_length=800
        )

        output_dir = tmp_path / "Downloads"
        with pytest.raises(ChecksumError, match="run again"):
            fetcher._download_asset(self.REPO, self.TAG, ForkName.GE_PROTON, output_dir)

        assert not (output_dir / self.ASSET).exists()
        assert not cache_path.exists()


class TestAssetNameExtension:
    """Test asset extension handling based on fork."""

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
        mock_network_client.get.return_value = HttpResponse(
            status=200, body=json.dumps([{"tag_name": "dwproton-10.0-26"}])
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
        mock_network_client.get.return_value = HttpResponse(
            status=200, body=json.dumps([{"tag_name": "GE-Proton10-20"}])
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
            # Proton-GE tests
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
        mock_network_client.get.return_value = HttpResponse(
            status=200, body=f'{{"tag_name": "{latest_tag}"}}'
        )
        mock_network_client.head.return_value = HttpResponse(
            status=200, final_url=f"/releases/tag/{latest_tag}"
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        result = release_manager.check_for_newer_release(
            repo,
            current_versions,
            fork,
        )

        assert result == expected
