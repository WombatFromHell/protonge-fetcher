"""
Integration tests for ProtonFetcher.

Consolidated integration tests for:
- NetworkClient with mocked subprocess
- Spinner functionality in download/extraction workflows
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.network import NetworkClient
from protonfetcher.spinner import Spinner

# =============================================================================
# NetworkClient Integration Tests
# =============================================================================


class TestNetworkClientIntegration:
    """Test NetworkClient with mocked subprocess."""

    def test_get_follows_redirects_mocked(self, mocker: Any) -> None:
        """Test GET request follows redirects (mocked subprocess)."""
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
        result = client.get(
            "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
        )

        assert result.returncode == 0
        assert "GE-Proton10-20" in result.stdout

        call_args = mock_run.call_args[0][0]
        assert "curl" in call_args
        assert "-L" in call_args  # Follow redirects

    @pytest.mark.parametrize(
        "headers,expected_header",
        [
            (
                {"Accept": "application/vnd.github.v3+json"},
                "Accept: application/vnd.github.v3+json",
            ),
            ({"User-Agent": "ProtonFetcher/1.0"}, "User-Agent: ProtonFetcher/1.0"),
        ],
    )
    def test_get_with_headers_mocked(
        self,
        headers: dict,
        expected_header: str,
        mocker: Any,
    ) -> None:
        """Test GET request includes custom headers."""
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"data": "test"}', stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        result = client.get(
            "https://api.github.com/repos/test/repo/releases",
            headers=headers,
        )

        assert result.returncode == 0

        call_args = mock_run.call_args[0][0]
        assert "-H" in call_args
        assert expected_header in call_args

    @pytest.mark.parametrize(
        "follow_redirects,should_have_L_flag",
        [(True, True), (False, False)],
    )
    def test_head_redirect_handling_mocked(
        self,
        follow_redirects: bool,
        should_have_L_flag: bool,
        mocker: Any,
    ) -> None:
        """Test HEAD request redirect handling."""
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: https://github.com/owner/repo/releases/download/v1.0/test.tar.gz",
            stderr="",
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        result = client.head(
            "https://github.com/owner/repo/releases/latest",
            follow_redirects=follow_redirects,
        )

        assert result.returncode == 0

        call_args = mock_run.call_args[0][0]
        assert "-I" in call_args  # HEAD request
        if should_have_L_flag:
            assert "-L" in call_args
        else:
            assert "-L" not in call_args

    @pytest.mark.parametrize(
        "headers,should_have_H_flag",
        [({"Accept": "application/octet-stream"}, True), (None, False)],
    )
    def test_download_command_mocked(
        self,
        headers: dict | None,
        should_have_H_flag: bool,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """Test download constructs correct curl command."""
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        output_path = tmp_path / "test.tar.gz"

        result = client.download(
            url="https://github.com/owner/repo/releases/download/v1.0/test.tar.gz",
            output_path=output_path,
            headers=headers,
        )

        assert result.returncode == 0

        call_args = mock_run.call_args[0][0]
        assert "curl" in call_args
        assert "-L" in call_args  # Follow redirects
        assert "-s" in call_args  # Silent
        assert "-f" in call_args  # Fail on error

        if should_have_H_flag:
            assert "-H" in call_args
        else:
            assert "-H" not in call_args

    def test_get_handles_error_response_mocked(self, mocker: Any) -> None:
        """Test GET handles HTTP error responses."""
        mock_response = subprocess.CompletedProcess(
            args=[],
            returncode=22,
            stdout="",
            stderr="404 Not Found",
        )
        mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=30)
        result = client.get("https://api.github.com/repos/invalid/repo/releases")

        assert result.returncode != 0
        assert "404" in result.stderr

    @pytest.mark.parametrize("timeout", [30, 60])
    def test_timeout_applied_mocked(self, timeout: int, mocker: Any) -> None:
        """Test timeout is applied to all request types."""
        mock_response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="{}", stderr=""
        )
        mock_run = mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_response,
        )

        client = NetworkClient(timeout=timeout)
        client.get("https://example.com/api")
        client.head("https://example.com/api")

        for call in mock_run.call_args_list:
            call_args = call[0][0]
            assert "--max-time" in call_args
            assert str(timeout) in call_args

    def test_network_client_in_github_fetcher_workflow_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test NetworkClient used in GitHubReleaseFetcher workflow."""
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
        mocker.patch(
            "protonfetcher.network.subprocess.run",
            return_value=mock_api_response,
        )

        from protonfetcher.release_manager import ReleaseManager

        network_client = NetworkClient(timeout=30)
        ReleaseManager(network_client, mock_filesystem_client, 30)

        result = network_client.get(
            "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tag_name"] == "GE-Proton10-20"


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

    def test_spinner_with_iterable(self, capsys: Any) -> None:
        """Test Spinner wraps iterable correctly."""
        items = [1, 2, 3, 4, 5]

        with Spinner(iterable=iter(items), desc="Processing", disable=False) as spinner:
            result = list(spinner)

        assert result == items
        captured = capsys.readouterr()
        assert "Processing" in captured.out

    @pytest.mark.parametrize(
        "current,total,expected",
        [(25, 100, 0.25), (0, 100, 0.0), (100, 100, 1.0), (150, 100, 1.0)],
    )
    def test_spinner_progress_percentage(
        self, current: int, total: int, expected: float
    ) -> None:
        """Test Spinner calculates progress percentage correctly."""
        spinner = Spinner(total=total, desc="Test", disable=True)
        spinner.current = current

        percentage = spinner._calculate_progress_percentage()

        assert percentage == expected

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

        result = spinner._should_update_display(test_time)

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
            show_file_details=True,
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
            show_file_details=False,
        )


class TestSpinnerEdgeCases:
    """Test Spinner edge cases."""

    def test_spinner_zero_total(self) -> None:
        """Test Spinner handles total=0 without division by zero."""
        spinner = Spinner(total=0, desc="Test", disable=True)

        spinner.update(0)
        percentage = spinner._calculate_progress_percentage()

        assert percentage == 0.0

    def test_spinner_empty_iterable(self, capsys: Any) -> None:
        """Test Spinner with empty iterable."""
        items: list[int] = []

        with Spinner(iterable=iter(items), desc="Empty", disable=False) as spinner:
            result = list(spinner)

        assert result == []
        captured = capsys.readouterr()
        assert "Empty" in captured.out

    def test_spinner_large_total_value(self) -> None:
        """Test Spinner handles large total values correctly."""
        spinner = Spinner(total=10_000_000_000, desc="Large", disable=True)
        spinner.current = 5_000_000_000

        percentage = spinner._calculate_progress_percentage()

        assert percentage == 0.5

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
