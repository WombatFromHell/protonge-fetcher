"""
Unit tests for ReleaseManager in protonfetcher.py
"""

import json
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher import (
    FORKS,
    ExtractionError,
    ForkName,
    NetworkError,
    ReleaseManager,
)


class TestReleaseManager:
    """Tests for ReleaseManager class."""

    def test_init(self, mocker):
        """Test ReleaseManager initialization."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs, timeout=60)
        assert manager.timeout == 60
        assert manager.network_client == mock_network
        assert manager.file_system_client == mock_fs

    def test_fetch_latest_tag_success(self, mocker):
        """Test successful fetching of latest tag."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock a successful response
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = (
            "Location: https://github.com/test/repo/releases/tag/GE-Proton10-20\n"
        )
        mock_network.head.return_value = mock_response

        result = manager.fetch_latest_tag("test/repo")

        assert result == "GE-Proton10-20"
        mock_network.head.assert_called_once()

    def test_fetch_latest_tag_with_url_fallback(self, mocker):
        """Test fetching latest tag with URL fallback."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response without Location header but with URL
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = (
            "URL: https://github.com/test/repo/releases/tag/GE-Proton10-30\n"
        )
        mock_network.head.return_value = mock_response

        result = manager.fetch_latest_tag("test/repo")

        assert result == "GE-Proton10-30"
        mock_network.head.assert_called_once()

    def test_fetch_latest_tag_network_error(self, mocker):
        """Test fetching latest tag with network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock a failed response
        mock_network.head.side_effect = Exception("Network error")

        with pytest.raises(NetworkError):
            manager.fetch_latest_tag("test/repo")

    def test_find_asset_by_name_api_success(self, mocker):
        """Test finding asset using API successfully."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock successful API response
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = json.dumps(
            {"assets": [{"name": "GE-Proton10-20.tar.gz"}, {"name": "other-file.txt"}]}
        )
        mock_network.get.return_value = mock_response

        result = manager.find_asset_by_name("test/repo", "GE-Proton10-20")

        assert result == "GE-Proton10-20.tar.gz"
        mock_network.get.assert_called_once()

    def test_find_asset_by_name_api_fallback_to_html(self, mocker):
        """Test finding asset with API failure falling back to HTML parsing."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # First call (API) fails, second call (HTML) succeeds
        mock_api_response = mocker.Mock()
        mock_api_response.returncode = 1
        mock_api_response.stderr = "API error"

        mock_html_response = mocker.Mock()
        mock_html_response.returncode = 0
        mock_html_response.stdout = "GE-Proton10-20.tar.gz content here"

        mock_network.get.side_effect = [mock_api_response, mock_html_response]

        result = manager.find_asset_by_name("test/repo", "GE-Proton10-20")

        assert result == "GE-Proton10-20.tar.gz"
        assert mock_network.get.call_count == 2

    def test_get_remote_asset_size_success(self, mocker):
        """Test getting remote asset size successfully."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with Content-Length header
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "Content-Length: 123456789\nOther-Header: value\n"
        mock_network.head.return_value = mock_response

        result = manager.get_remote_asset_size(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )

        assert result == 123456789
        mock_network.head.assert_called_once()

    def test_get_remote_asset_size_not_found(self, mocker):
        """Test getting remote asset size with 404 error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with 404 error
        mock_response = mocker.Mock()
        mock_response.returncode = 0  # return code 0 but contains 404 in stderr
        mock_response.stderr = "404 Not Found"
        mock_network.head.return_value = mock_response

        with pytest.raises(NetworkError):
            manager.get_remote_asset_size(
                "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
            )

    def test_multi_level_redirects(self, mocker, mock_redirect_chain):
        """Test handling of multiple sequential redirects."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock the initial call to get_remote_asset_size - first returns a redirect, then follow_redirect_and_get_size is called
        initial_response = mocker.Mock()
        initial_response.returncode = 0
        initial_response.stdout = (
            "Location: https://redirect1.example.com/file.tar.gz\n"
        )
        mock_network.head.return_value = initial_response

        # Mock the _follow_redirect_and_get_size method separately
        mock_follow_redirect = mocker.patch.object(
            manager, "_follow_redirect_and_get_size", return_value=104857600
        )

        result = manager.get_remote_asset_size(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )

        assert result == 104857600
        mock_follow_redirect.assert_called_once()

    def test_redirect_loop_detection(self, mocker):
        """Test detection and handling of redirect loops."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Create a redirect loop
        def mock_head(url, **kwargs):
            result = mocker.Mock()
            result.returncode = 0
            # Always redirect back to the same URL to create a loop
            result.stdout = f"Location: {url}\n"
            return result

        mock_network.head.side_effect = mock_head

        # This should complete without infinite loop
        # The actual behavior depends on the implementation in protonfetcher.py
        # If there are safeguards against loops, it should handle them gracefully
        result = manager._follow_redirect_and_get_size(
            mocker.Mock(stdout="Location: https://loop.example.com/file.tar.gz\n"),
            "https://loop.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            True,  # in_test = True to avoid caching
        )
        # The result should be None since it's a redirect loop
        assert result is None

    def test_cross_protocol_redirects(self, mocker):
        """Test redirects from HTTP to HTTPS and vice versa."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock the initial request to have a redirect
        initial_response = mocker.Mock()
        initial_response.returncode = 0
        initial_response.stdout = "Location: https://secure.example.com/file.tar.gz\n"
        mock_network.head.return_value = initial_response

        # Mock the HTTPS request to have content length
        def mock_head(url, **kwargs):
            if url.startswith("https://"):
                result = mocker.Mock()
                result.returncode = 0
                result.stdout = "Content-Length: 52428800\n"  # 50MB
                return result
            return initial_response

        mock_network.head.side_effect = mock_head

        result = manager._follow_redirect_and_get_size(
            initial_response,
            "http://example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            True,  # in_test = True to avoid caching
        )
        assert result == 52428800

    def test_list_recent_releases_success(self, mocker):
        """Test listing recent releases successfully."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock successful API response for releases
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        releases_data = [{"tag_name": f"GE-Proton10-{i}"} for i in range(20)]
        mock_response.stdout = json.dumps(releases_data)
        mock_network.get.return_value = mock_response

        result = manager.list_recent_releases("test/repo")

        assert len(result) == 20
        assert result[0] == "GE-Proton10-0"
        mock_network.get.assert_called_once()


class TestReleaseManagerWithFixtures:
    """Tests for ReleaseManager using shared fixtures."""

    def test_init_with_fixtures(self, mock_network_client, mock_filesystem_client):
        """Test ReleaseManager initialization with shared fixtures."""
        manager = ReleaseManager(
            mock_network_client, mock_filesystem_client, timeout=60
        )
        assert manager.timeout == 60
        assert manager.network_client == mock_network_client
        assert manager.file_system_client == mock_filesystem_client

    def test_fetch_latest_tag_with_fixtures(self, mocker, mock_network_client):
        """Test successful fetching of latest tag with shared fixtures."""
        manager = ReleaseManager(mock_network_client, mocker.Mock())

        # Mock a successful response
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = (
            "Location: https://github.com/test/repo/releases/tag/GE-Proton10-20\n"
        )
        mock_network_client.head.return_value = mock_response

        result = manager.fetch_latest_tag("test/repo")

        assert result == "GE-Proton10-20"
        mock_network_client.head.assert_called_once()

    @pytest.mark.parametrize(
        "fork,tag,expected",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20", "GE-Proton10-20.tar.gz"),
            (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30.tar.xz"),
        ],
    )
    def test_find_asset_by_name_parametrized(
        self, mocker, mock_network_client, mock_filesystem_client, fork, tag, expected
    ):
        """Parametrized test for finding asset by name."""
        import json

        manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Mock successful API response with expected asset
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = json.dumps(
            {"assets": [{"name": expected}, {"name": "other-file.txt"}]}
        )
        mock_network_client.get.return_value = mock_response

        result = manager.find_asset_by_name("test/repo", tag, fork)

        assert result == expected
        mock_network_client.get.assert_called_once()
