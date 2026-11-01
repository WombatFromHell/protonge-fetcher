"""
Integration tests for ProtonFetcher.

Consolidated integration tests for:
- NetworkClient with mocked subprocess
- Spinner functionality in download/extraction workflows
"""

import email.message
import hashlib
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.exceptions import NetworkError
from protonfetcher.filesystem import FileSystemClient
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


class TestResumeDownload:
    """Test resuming an interrupted download with a byte Range."""

    URL = "https://example.com/owner/repo/releases/download/GE-Proton10-11/GE-Proton10-11.tar.gz"
    ASSET = "GE-Proton10-11.tar.gz"

    @staticmethod
    def _downloader(mock_network_client: Any, file_system: Any) -> AssetDownloader:
        return AssetDownloader(mock_network_client, file_system)

    def test_resume_sends_range_and_appends(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A 206 answer must append to the bytes already held on disk."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"a" * 400)

        mocks = mock_urllib_download(
            chunks=[b"b" * 400, b""], content_length=400, status=206
        )

        self._downloader(mock_network_client, FileSystemClient()).download_with_spinner(
            url=self.URL, output_path=out_path, resume_from=400
        )

        assert mocks["urlopen_mock"].call_args[0][0].headers["Range"] == "bytes=400-"
        assert out_path.read_bytes() == b"a" * 400 + b"b" * 400

    def test_server_ignoring_range_restarts_from_byte_zero(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A plain 200 to a Range request means the prefix is unusable — rewrite it."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"junk" * 100)

        mock_urllib_download(chunks=[b"b" * 800, b""], content_length=800, status=200)

        self._downloader(mock_network_client, FileSystemClient()).download_with_spinner(
            url=self.URL, output_path=out_path, resume_from=400
        )

        assert out_path.read_bytes() == b"b" * 800

    def test_download_asset_resumes_a_partial_local_file(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """download_asset resumes from the .partial target, not the final path."""
        out_path = tmp_path / self.ASSET
        partial = out_path.with_name(f"{self.ASSET}.partial")
        partial.write_bytes(b"a" * 400)

        mocks = mock_urllib_download(
            chunks=[b"b" * 400, b""], content_length=400, status=206
        )

        self._downloader(mock_network_client, FileSystemClient()).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
        )

        assert mocks["urlopen_mock"].call_args[0][0].headers["Range"] == "bytes=400-"
        assert out_path.read_bytes() == b"a" * 400 + b"b" * 400
        assert not partial.exists()

    def test_download_asset_overwrites_a_larger_local_file(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A local file bigger than the remote asset is not a prefix — no Range."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"old" * 300)

        mocks = mock_urllib_download(chunks=[b"n" * 800, b""], content_length=800)

        self._downloader(mock_network_client, FileSystemClient()).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
        )

        assert "Range" not in mocks["urlopen_mock"].call_args[0][0].headers
        assert out_path.read_bytes() == b"n" * 800

    def test_download_asset_skips_a_complete_local_file(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Matching size still skips the download entirely."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"x" * 800)

        mocks = mock_urllib_download(chunks=[b"b" * 800, b""], content_length=800)

        self._downloader(mock_network_client, FileSystemClient()).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
        )

        assert mocks["urlopen_mock"].call_count == 0
        assert out_path.read_bytes() == b"x" * 800

    def test_download_asset_rejects_a_truncated_result(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A short body must fail instead of handing a broken archive to tar."""
        out_path = tmp_path / self.ASSET

        mock_urllib_download(chunks=[b"b" * 200, b""], content_length=800)

        with pytest.raises(NetworkError, match="ended early"):
            self._downloader(mock_network_client, FileSystemClient()).download_asset(
                "owner/repo",
                "GE-Proton10-11",
                self.ASSET,
                out_path,
                download_url=self.URL,
                remote_size=800,
            )

        # The half-written archive stays in the .partial target, out_path untouched.
        assert out_path.exists() is False
        assert (tmp_path / f"{self.ASSET}.partial").stat().st_size == 200

    def test_http_error_is_a_download_failure(
        self,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A non-resume HTTP status is still reported as a failed download."""
        out_path = Path("/mock/output/GE-Proton10-11.tar.gz")
        mock_urllib_download(
            raise_on_open=urllib.error.HTTPError(
                self.URL, 500, "Server Error", email.message.Message(), None
            )
        )

        with pytest.raises(NetworkError, match="Failed to download"):
            AssetDownloader(
                mock_network_client, FileSystemClient()
            ).download_with_spinner(url=self.URL, output_path=out_path)

    def test_url_error_stays_a_network_error(
        self,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A connection-level failure is reported as a download failure."""
        out_path = Path("/mock/output/GE-Proton10-11.tar.gz")
        mock_urllib_download(raise_on_open=urllib.error.URLError("Connection refused"))

        with pytest.raises(NetworkError, match="Connection refused"):
            AssetDownloader(
                mock_network_client, FileSystemClient()
            ).download_with_spinner(url=self.URL, output_path=out_path)

    def test_rejected_range_restarts_from_byte_zero(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """HTTP 416 means our prefix is not a prefix of the asset — restart, don't hand the user a delete job."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"a" * 900)

        error = urllib.error.HTTPError(
            self.URL, 416, "Range Not Satisfiable", email.message.Message(), None
        )
        mocks = mock_urllib_download(
            raise_on_open=[error], chunks=[b"b" * 800, b""], content_length=800
        )

        self._downloader(mock_network_client, FileSystemClient()).download_with_spinner(
            url=self.URL, output_path=out_path, resume_from=900
        )

        assert mocks["urlopen_mock"].call_count == 2
        assert "Range" not in mocks["urlopen_mock"].call_args[0][0].headers
        assert out_path.read_bytes() == b"b" * 800

    def test_resume_without_content_length_shows_the_remote_size(
        self,
        mocker: Any,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A 206 with no Content-Length must size the bar from the listing, not from the offset."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"a" * 400)

        mock_urllib_download(chunks=[b"b" * 400, b""], status=206)

        captured: dict[str, Any] = {}
        original_init = Spinner.__init__

        def capturing_init(self: Spinner, *args: Any, **kwargs: Any) -> None:
            captured.update(kwargs)
            original_init(self, *args, **kwargs)

        mocker.patch.object(Spinner, "__init__", capturing_init)

        self._downloader(mock_network_client, FileSystemClient()).download_with_spinner(
            url=self.URL,
            output_path=out_path,
            resume_from=400,
            expected_size=800,
        )

        assert captured["total"] == 800


class TestPartialTargetAndChecksum:
    """The archive is staged as <name>.partial and only renamed once size+checksum match."""

    URL = "https://example.com/owner/repo/releases/download/GE-Proton10-11/GE-Proton10-11.tar.gz"
    ASSET = "GE-Proton10-11.tar.gz"
    UPSTREAM = b"a" * 400 + b"b" * 400
    DIGEST = f"sha256:{hashlib.sha256(UPSTREAM).hexdigest()}"

    @staticmethod
    def _downloader(mock_network_client: Any, file_system: Any) -> AssetDownloader:
        return AssetDownloader(mock_network_client, file_system)

    def _download(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
        chunks: list[bytes],
        digest: str | None,
        remote_size: int | None = 800,
    ) -> Path:
        mock_urllib_download(chunks=chunks, content_length=len(chunks[0]))
        return self._downloader(mock_network_client, FileSystemClient()).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            tmp_path / self.ASSET,
            download_url=self.URL,
            remote_size=remote_size,
            digest=digest,
        )

    def test_fresh_download_is_staged_then_renamed(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A verified download lands at out_path and leaves no .partial behind."""
        out_path = self._download(
            tmp_path,
            mock_network_client,
            mock_urllib_download,
            [self.UPSTREAM, b""],
            self.DIGEST,
        )

        assert out_path.read_bytes() == self.UPSTREAM
        assert not (tmp_path / f"{self.ASSET}.partial").exists()

    def test_verified_asset_discards_a_stale_partial(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """An already-complete verified archive means any .partial is junk."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(self.UPSTREAM)
        stale = tmp_path / f"{self.ASSET}.partial"
        stale.write_bytes(b"junk")

        mocks = mock_urllib_download(chunks=[self.UPSTREAM, b""], content_length=800)
        result = self._downloader(
            mock_network_client, FileSystemClient()
        ).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
            digest=self.DIGEST,
        )

        assert result == out_path
        assert mocks["urlopen_mock"].call_count == 0
        assert not stale.exists()

    def test_corrupt_prefix_is_discarded_and_redownloaded(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A resumed prefix that hashes wrong is thrown away, not renamed."""
        out_path = tmp_path / self.ASSET
        out_path.with_name(f"{self.ASSET}.partial").write_bytes(b"junk" * 100)

        mocks = mock_urllib_download(
            chunks=[b"b" * 400, b"", self.UPSTREAM, b""], content_length=400, status=206
        )

        result = self._downloader(
            mock_network_client, FileSystemClient()
        ).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
            digest=self.DIGEST,
        )

        # First call resumes the garbage prefix; the digest rejects it and the
        # second call starts from byte 0 with no Range header.
        assert mocks["urlopen_mock"].call_count == 2
        assert "Range" not in mocks["urlopen_mock"].call_args[0][0].headers
        assert result.read_bytes() == self.UPSTREAM

    def test_checksum_mismatch_never_reaches_the_final_path(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A body that cannot match the digest fails loudly and cleans up."""
        with pytest.raises(NetworkError, match="Checksum mismatch"):
            self._download(
                tmp_path,
                mock_network_client,
                mock_urllib_download,
                [self.UPSTREAM, b"", self.UPSTREAM, b""],
                "sha256:" + "0" * 64,
            )

        assert not (tmp_path / self.ASSET).exists()
        assert not (tmp_path / f"{self.ASSET}.partial").exists()

    def test_local_archive_matching_size_is_verified_before_skipping(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Same size but wrong content must not be handed to tar."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(b"x" * 800)

        mocks = mock_urllib_download(chunks=[self.UPSTREAM, b""], content_length=800)

        result = self._downloader(
            mock_network_client, FileSystemClient()
        ).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
            digest=self.DIGEST,
        )

        assert mocks["urlopen_mock"].call_count == 1
        assert result.read_bytes() == self.UPSTREAM

    def test_verified_local_archive_is_skipped(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """A verified archive of matching size costs no request."""
        out_path = tmp_path / self.ASSET
        out_path.write_bytes(self.UPSTREAM)

        mocks = mock_urllib_download(chunks=[self.UPSTREAM, b""], content_length=800)

        result = self._downloader(
            mock_network_client, FileSystemClient()
        ).download_asset(
            "owner/repo",
            "GE-Proton10-11",
            self.ASSET,
            out_path,
            download_url=self.URL,
            remote_size=800,
            digest=self.DIGEST,
        )

        assert mocks["urlopen_mock"].call_count == 0
        assert result.read_bytes() == self.UPSTREAM

    def test_missing_digest_skips_verification(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """No digest (HTML fallback, self-hosted) still downloads — no false failure."""
        out_path = self._download(
            tmp_path,
            mock_network_client,
            mock_urllib_download,
            [self.UPSTREAM, b""],
            None,
        )

        assert out_path.read_bytes() == self.UPSTREAM

    def test_uppercase_checksum_digest_still_verifies(
        self,
        tmp_path: Path,
        mock_network_client: Any,
        mock_urllib_download: Any,
    ) -> None:
        """Published hex can be uppercase; it must still match our lowercase hash."""
        upper = f"sha256:{hashlib.sha256(self.UPSTREAM).hexdigest().upper()}"

        out_path = self._download(
            tmp_path,
            mock_network_client,
            mock_urllib_download,
            [self.UPSTREAM, b""],
            upper,
        )

        assert out_path.read_bytes() == self.UPSTREAM


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
