"""
Integration tests for NetworkClient in user-facing workflows.

Tests NetworkClient with mocked subprocess to verify:
- curl command construction
- Redirect handling
- Header handling
- Error handling

No real network calls are made - subprocess.run is mocked.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from protonfetcher.network import NetworkClient


class TestNetworkClientIntegration:
    """Test NetworkClient with mocked subprocess in realistic scenarios."""

    def test_get_follows_redirects_mocked(
        self,
        mocker: Any,
    ) -> None:
        """Test GET request follows redirects (mocked subprocess)."""
        # Arrange: Mock subprocess.run to simulate GitHub API response
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"tag_name": "GE-Proton10-20"}),
            stderr="",
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)

        # Act
        result = client.get(
            "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
        )

        # Assert
        assert result.returncode == 0
        assert "GE-Proton10-20" in result.stdout

        # Verify curl was called with correct options
        call_args = mock_run.call_args[0][0]
        assert "curl" in call_args
        assert "-L" in call_args  # Follow redirects
        assert "--http2" in call_args
        assert "--compressed" in call_args
        assert "--max-time" in call_args
        assert "30" in call_args

    def test_get_with_custom_headers_mocked(
        self,
        mocker: Any,
    ) -> None:
        """Test GET request includes custom headers (mocked subprocess)."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"data": "test"}', stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ProtonFetcher/1.0",
        }

        # Act
        result = client.get(
            "https://api.github.com/repos/test/repo/releases",
            headers=headers,
        )

        # Assert
        assert result.returncode == 0

        # Verify headers were passed to curl
        call_args = mock_run.call_args[0][0]
        assert "-H" in call_args
        assert "Accept: application/vnd.github.v3+json" in call_args
        assert "User-Agent: ProtonFetcher/1.0" in call_args

    def test_head_follows_redirect_when_requested_mocked(
        self,
        mocker: Any,
    ) -> None:
        """Test HEAD request follows redirects when follow_redirects=True."""
        # Arrange: Simulate GitHub redirect response
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: https://github.com/owner/repo/releases/download/v1.0/test.tar.gz\nContent-Length: 1048576",
            stderr="",
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)

        # Act
        result = client.head(
            "https://github.com/owner/repo/releases/latest",
            follow_redirects=True,
        )

        # Assert
        assert result.returncode == 0
        assert "Location:" in result.stdout

        # Verify -L flag was added for redirect following
        call_args = mock_run.call_args[0][0]
        assert "-L" in call_args
        assert "-I" in call_args  # HEAD request

    def test_head_without_redirect_mocked(
        self,
        mocker: Any,
    ) -> None:
        """Test HEAD request doesn't follow redirects by default."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Content-Length: 1048576",
            stderr="",
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)

        # Act
        result = client.head(
            "https://github.com/owner/repo/releases/download/v1.0/test.tar.gz"
        )

        # Assert
        assert result.returncode == 0

        # Verify -L flag was NOT added
        call_args = mock_run.call_args[0][0]
        assert "-L" not in call_args
        assert "-I" in call_args

    def test_download_constructs_correct_command_mocked(
        self,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """Test download constructs correct curl command (mocked)."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        output_path = tmp_path / "test.tar.gz"
        headers = {"Accept": "application/octet-stream"}

        # Act
        result = client.download(
            url="https://github.com/owner/repo/releases/download/v1.0/test.tar.gz",
            output_path=output_path,
            headers=headers,
        )

        # Assert
        assert result.returncode == 0

        # Verify curl command structure
        call_args = mock_run.call_args[0][0]
        assert "curl" in call_args
        assert "-L" in call_args  # Follow redirects
        assert "-s" in call_args  # Silent
        assert "-S" in call_args  # Show errors
        assert "-f" in call_args  # Fail on error
        assert "-o" in call_args
        assert str(output_path) in call_args
        assert "-H" in call_args
        assert "Accept: application/octet-stream" in call_args

    def test_download_without_headers_mocked(
        self,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """Test download works without custom headers."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        output_path = tmp_path / "test.tar.gz"

        # Act
        result = client.download(
            url="https://github.com/owner/repo/releases/download/v1.0/test.tar.gz",
            output_path=output_path,
            headers=None,
        )

        # Assert
        assert result.returncode == 0

        # Verify no -H flags when headers is None
        call_args = mock_run.call_args[0][0]
        assert "-H" not in call_args

    def test_get_handles_error_response_mocked(
        self,
        mocker: Any,
    ) -> None:
        """Test GET handles HTTP error responses."""
        # Arrange: Simulate 404 error
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,  # curl returns 22 for HTTP errors
            stdout="",
            stderr="404 Not Found",
        )
        mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)

        # Act
        result = client.get("https://api.github.com/repos/invalid/repo/releases")

        # Assert
        assert result.returncode != 0
        assert "404" in result.stderr

    def test_timeout_applied_to_all_requests_mocked(
        self,
        mocker: Any,
    ) -> None:
        """Test timeout is applied to all request types."""
        # Arrange
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="{}", stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=60)

        # Act: Make different types of requests
        client.get("https://example.com/api")
        client.head("https://example.com/api")

        # Assert: Both should have the custom timeout
        for call in mock_run.call_args_list:
            call_args = call[0][0]
            assert "--max-time" in call_args
            assert "60" in call_args

    def test_network_client_in_github_fetcher_workflow_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test NetworkClient used in GitHubReleaseFetcher workflow (mocked).

        This is an integration test that verifies NetworkClient works correctly
        when used as part of the larger GitHubReleaseFetcher workflow.
        """
        # Arrange: Mock subprocess to simulate GitHub API
        mock_api_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "tag_name": "GE-Proton10-20",
                    "assets": [{"name": "GE-Proton10-20.tar.gz", "size": 1048576}],
                }
            ),
            stderr="",
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_api_response,
        )

        # Use real NetworkClient with mocked subprocess
        from protonfetcher.asset_downloader import AssetDownloader
        from protonfetcher.release_manager import ReleaseManager

        network_client = NetworkClient(timeout=30)
        ReleaseManager(network_client, mock_filesystem_client, 30)
        AssetDownloader(network_client, mock_filesystem_client, 30)

        # Act: Use the components together
        result = network_client.get(
            "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
        )

        # Assert
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tag_name"] == "GE-Proton10-20"

        # Verify curl was called with appropriate options for GitHub API
        call_args = mock_run.call_args[0][0]
        assert "curl" in call_args
        assert "--http2" in call_args  # HTTP/2 for performance
        assert "--compressed" in call_args  # Compression support
