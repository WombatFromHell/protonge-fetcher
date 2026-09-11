"""
Integration tests for ProtonFetcher.

Consolidated integration tests for:
- NetworkClient with mocked subprocess
- Spinner functionality in download/extraction workflows
"""

import email.message
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.exceptions import NetworkError
from protonfetcher.network import NetworkClient
from protonfetcher.spinner import Spinner

# =============================================================================
# NetworkClient Integration Tests
# =============================================================================


class TestNetworkClientIntegration:
    """Test NetworkClient (urllib-based) with mocked urlopen."""

    def _fake_response(
        self,
        mocker: Any,
        status: int = 200,
        body: bytes = b"",
        url: str = "https://example.com/",
        headers: dict[str, str] | None = None,
    ) -> Any:
        resp = mocker.MagicMock()
        resp.status = status
        resp.url = url
        resp.read.return_value = body
        msg = email.message.EmailMessage()
        for key, value in (headers or {}).items():
            msg[key] = value
        resp.headers = msg
        resp.__enter__ = mocker.MagicMock(return_value=resp)
        resp.__exit__ = mocker.MagicMock(return_value=False)
        return resp

    def test_get_returns_body(self, mocker: Any) -> None:
        """Test GET returns decoded body and final URL."""
        url = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
        mock_response = self._fake_response(
            mocker,
            status=200,
            body=json.dumps({"tag_name": "GE-Proton10-20"}).encode(),
            url=url,
        )
        mocker.patch(
            "protonfetcher.network.urllib.request.urlopen",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        result = client.get(url)

        assert result.status == 200
        assert "GE-Proton10-20" in result.body
        assert result.final_url == url

    def test_get_with_headers(self, mocker: Any) -> None:
        """Test GET request passes custom headers to urlopen."""
        mock_response = self._fake_response(
            mocker, status=200, body=b'{"data": "test"}'
        )
        mock_urlopen = mocker.patch(
            "protonfetcher.network.urllib.request.urlopen",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        result = client.get(
            "https://api.github.com/repos/test/repo/releases",
            headers={"Accept": "application/vnd.github.v3+json"},
        )

        assert result.status == 200
        request = mock_urlopen.call_args[0][0]
        assert request.get_header("Accept") == "application/vnd.github.v3+json"

    def test_head_returns_final_url(self, mocker: Any) -> None:
        """Test HEAD returns the final URL after redirects."""
        mock_response = self._fake_response(
            mocker,
            status=200,
            url="https://github.com/owner/repo/releases/download/v1.0/test.tar.gz",
            headers={"Content-Length": "1048576"},
        )
        mocker.patch(
            "protonfetcher.network.urllib.request.urlopen",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        result = client.head("https://github.com/owner/repo/releases/latest")

        assert result.status == 200
        assert result.body == ""
        assert result.final_url == (
            "https://github.com/owner/repo/releases/download/v1.0/test.tar.gz"
        )
        assert result.headers["content-length"] == "1048576"

    def test_get_http_error_returns_response(self, mocker: Any) -> None:
        """Test GET returns 404 as HttpResponse, not an exception."""
        url = "https://api.github.com/repos/invalid/repo/releases"
        http_error = urllib.error.HTTPError(
            url,
            404,
            "Not Found",
            email.message.EmailMessage(),
            io.BytesIO(b'{"message": "not found"}'),
        )
        mocker.patch(
            "protonfetcher.network.urllib.request.urlopen",
            side_effect=http_error,
        )

        client = NetworkClient(timeout=30)
        result = client.get(url)

        assert result.status == 404
        assert "not found" in result.body

    def test_connection_error_raises_network_error(self, mocker: Any) -> None:
        """Test connection failures raise NetworkError."""
        mocker.patch(
            "protonfetcher.network.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        )

        client = NetworkClient(timeout=30)
        with pytest.raises(NetworkError):
            client.get("https://invalid.example.com/api")

    @pytest.mark.parametrize("timeout", [30, 60])
    def test_timeout_stored(self, timeout: int) -> None:
        """Test timeout is stored for use in requests."""
        client = NetworkClient(timeout=timeout)
        assert client.timeout == timeout


# =============================================================================
# Spinner Integration Tests
# =============================================================================


class TestSpinnerDirect:
    """Test Spinner class directly."""

    def test_spinner_context_manager(self, capsys: Any) -> None:
        """Test Spinner works as context manager."""
        spinner = Spinner(desc="Test", disable=False)

        with spinner:
            pass

        captured = capsys.readouterr()
        assert "Test" in captured.out

    def test_spinner_update_increments_current(self) -> None:
        """Test Spinner.update() increments current counter."""
        spinner = Spinner(total=100, desc="Test", disable=True)
        initial = spinner.current

        spinner.update(10)

        assert spinner.current == initial + 10

    @pytest.mark.parametrize(
        "fps_limit,test_time,expected_updates",
        [
            (1.0, 0.0, False),  # First call at t=0
            (1.0, 0.1, False),  # Too soon (0.1 < 1.0)
            (1.0, 1.1, True),  # After 1 second
            (None, 0.0, True),  # No FPS limit
        ],
    )
    def test_spinner_fps_limiting(
        self,
        fps_limit: float | None,
        test_time: float,
        expected_updates: bool,
    ) -> None:
        """Test Spinner respects FPS limit."""
        spinner = Spinner(fps_limit=fps_limit, disable=True)
        spinner._last_update_time = 0.0

        result = spinner._should_update(test_time)

        if fps_limit is None:
            assert result is True
        else:
            # First call at t=0 with _last_update_time=0 means 0 >= 1.0 is False
            if test_time == 0.0:
                assert result is False
            else:
                assert result == expected_updates

    def test_spinner_disabled_no_output(self, capsys: Any) -> None:
        """Test Spinner produces no output when disabled."""
        spinner = Spinner(desc="Test", disable=True)

        with spinner:
            spinner.update(10)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestSpinnerInDownloadWorkflow:
    """Test Spinner integration in download workflow."""

    def test_download_with_spinner_mocked_io(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
        capsys: Any,
    ) -> None:
        """Test download_with_spinner shows progress (mocked I/O)."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        mock_urllib_download(
            chunks=[b"x" * 1000, b"x" * 1000, b""],
            content_length=2000,
        )
        mock_builtin_open()

        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        captured = capsys.readouterr()
        assert "Downloading" in captured.out or "test.tar.gz" in captured.out

    def test_download_with_spinner_no_content_length(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
    ) -> None:
        """Test download_with_spinner handles missing Content-Length."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        mock_urllib_download(
            chunks=[b"data", b"more", b""],
            content_length=None,
        )
        mock_builtin_open()

        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

    def test_download_with_spinner_network_error(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Test download_with_spinner handles network errors gracefully."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        mock_urllib_download(raise_on_open=Exception("Connection failed"))

        with pytest.raises(Exception, match="Connection failed"):
            downloader.download_with_spinner(
                url="https://example.com/test.tar.gz",
                output_path=output_path,
            )


class TestSpinnerInExtractionWorkflow:
    """Test Spinner integration in extraction workflow."""

    def test_extract_archive_shows_spinner_progress(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        capsys: Any,
    ) -> None:
        """Test extract_archive shows spinner progress."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        mock_tarfile_operations(
            members=[
                {"name": "dir", "is_dir": True, "size": 0},
                {"name": "dir/file1.txt", "is_dir": False, "size": 100},
                {"name": "dir/file2.txt", "is_dir": False, "size": 200},
            ]
        )

        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=True,
        )

        captured = capsys.readouterr()
        assert "Extracting" in captured.out or "test.tar.gz" in captured.out

    def test_extract_archive_without_progress(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        capsys: Any,
    ) -> None:
        """Test extract_archive respects show_progress=False."""
        extractor = ArchiveExtractor(mock_filesystem_client)
        target_dir = Path("/mock/extracted")
        archive_path = Path("/mock/test.tar.gz")

        mock_filesystem_client.exists.side_effect = lambda p: (
            p in (archive_path, target_dir)
        )
        mock_filesystem_client.is_dir.side_effect = lambda p: p == target_dir

        mock_tarfile_operations(members=[{"name": "dir", "is_dir": True, "size": 0}])

        extractor.extract_archive(
            archive_path=archive_path,
            target_dir=target_dir,
            show_progress=False,
        )


class TestSpinnerEdgeCases:
    """Test Spinner edge cases."""

    def test_spinner_configured_with_fps_limit_during_download(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_urllib_download: Any,
        mock_builtin_open: Any,
    ) -> None:
        """Test Spinner is configured with FPS limit during download."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)
        output_path = Path("/mock/output/test.tar.gz")

        mock_urllib_download(
            chunks=[b"chunk1", b"chunk2", b""],
            content_length=1000,
        )
        mock_builtin_open()

        original_init = Spinner.__init__
        captured_fps_limit = None

        def capturing_init(self: Spinner, *args: Any, **kwargs: Any) -> None:
            nonlocal captured_fps_limit
            captured_fps_limit = kwargs.get("fps_limit")
            original_init(self, *args, **kwargs)

        mocker.patch.object(Spinner, "__init__", capturing_init)

        downloader.download_with_spinner(
            url="https://example.com/test.tar.gz",
            output_path=output_path,
        )

        assert captured_fps_limit == 10.0
