import io
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest
import requests

from fetcher import (
    GitHubReleaseFetcher,
    FetchError,
    PROTONGE_ASSET_PATTERN,
)

# Use a constant for the hardcoded repo to avoid magic strings
PROTON_GE_REPO = "GloriousEggroll/proton-ge-custom"


@pytest.fixture
def fetcher(mocker):
    """Create a fetcher with a mocked session."""
    mock_session = mocker.Mock(spec=requests.Session)
    return GitHubReleaseFetcher(session=mock_session)


@pytest.fixture
def tar_gz_archive(tmp_path):
    """Create a test tar.gz archive on disk."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
        info = tarfile.TarInfo(name="test.txt")
        info.size = 11
        tar.addfile(info, io.BytesIO(b"hello world"))

    path = tmp_path / "test.tar.gz"
    path.write_bytes(buffer.getvalue())
    return path


class TestFetchLatestTag:
    """Tests for fetch_latest_tag method."""

    def test_success(self, fetcher, mocker):
        """Successfully fetch the latest tag."""
        mocker.patch.object(
            fetcher.session,
            "head",
            return_value=mocker.Mock(
                url=f"https://github.com/{PROTON_GE_REPO}/releases/tag/v1.2.3"
            ),
        )
        assert fetcher.fetch_latest_tag(PROTON_GE_REPO) == "v1.2.3"

    @pytest.mark.parametrize(
        "error_type, expected_match",
        [
            ("invalid_url", "Could not determine latest tag"),
            ("connection_error", "Failed to fetch latest tag"),
            ("http_error", "Failed to fetch latest tag"),
        ],
    )
    def test_failures(self, fetcher, mocker, error_type, expected_match):
        """Raise error on various failure conditions."""
        mock_head = mocker.patch.object(fetcher.session, "head")

        if error_type == "invalid_url":
            mock_head.return_value = mocker.Mock(
                url=f"https://github.com/{PROTON_GE_REPO}/releases"
            )
        elif error_type == "connection_error":
            mock_head.side_effect = requests.ConnectionError("Network error")
        elif error_type == "http_error":
            error = requests.HTTPError("404 Client Error")
            mock_head.side_effect = error
            # Ensure raise_for_status is called for HTTPError
            mock_head.return_value.raise_for_status.side_effect = error

        with pytest.raises(FetchError, match=expected_match):
            fetcher.fetch_latest_tag(PROTON_GE_REPO)


class TestFindAssetByPattern:
    """Tests for find_asset_by_pattern method."""

    def test_success(self, fetcher, mocker):
        """Successfully find ProtonGE asset by pattern."""
        mocker.patch.object(
            fetcher.session,
            "get",
            return_value=mocker.Mock(
                text=f'<a href="/{PROTON_GE_REPO}/releases/download/v1.0/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>'
            ),
        )
        asset = fetcher.find_asset_by_pattern(
            PROTON_GE_REPO, "v1.0", PROTONGE_ASSET_PATTERN
        )
        assert asset == "GE-Proton8-25.tar.gz"

    @pytest.mark.parametrize(
        "error_type, expected_match",
        [
            ("no_assets", "No asset matching pattern"),
            ("connection_error", "Failed to fetch release page"),
        ],
    )
    def test_failures(self, fetcher, mocker, error_type, expected_match):
        """Raise error when no asset matches or on network failure."""
        mock_get = mocker.patch.object(fetcher.session, "get")

        if error_type == "no_assets":
            mock_get.return_value = mocker.Mock(text="<div>No assets here</div>")
        elif error_type == "connection_error":
            mock_get.side_effect = requests.ConnectionError("Network error")

        with pytest.raises(FetchError, match=expected_match):
            fetcher.find_asset_by_pattern(
                PROTON_GE_REPO, "v1.0", PROTONGE_ASSET_PATTERN
            )


class TestDownloadAsset:
    """Tests for download_asset method."""

    def test_success(self, fetcher, mocker, tmp_path):
        """Successfully download an asset."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"test content"]
        # Add context manager methods
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=None)
        mocker.patch.object(fetcher.session, "get", return_value=mock_response)

        out_path = tmp_path / "test.txt"
        result = fetcher.download_asset(PROTON_GE_REPO, "v1.0", "test.txt", out_path)

        assert result == out_path
        assert out_path.read_bytes() == b"test content"

    @pytest.mark.parametrize(
        "error_type, expected_match",
        [
            ("not_found", "Asset not found"),
            ("connection_error", "Failed to download"),
        ],
    )
    def test_failures(self, fetcher, mocker, error_type, expected_match):
        """Raise error on 404 or network failure."""
        mock_response = mocker.Mock()
        # Add context manager methods
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=None)
        mock_get = mocker.patch.object(
            fetcher.session, "get", return_value=mock_response
        )

        if error_type == "not_found":
            mock_response.status_code = 404
        elif error_type == "connection_error":
            mock_get.side_effect = requests.ConnectionError("Network error")

        with pytest.raises(FetchError, match=expected_match):
            fetcher.download_asset(
                PROTON_GE_REPO, "v1.0", "missing.txt", Path("/tmp/missing.txt")
            )

    def test_creates_parent_directories(self, fetcher, mocker, tmp_path):
        """Create parent directories if they don't exist."""
        mock_response = mocker.Mock(
            status_code=200, iter_content=lambda chunk_size=1024 * 1024: [b"content"]
        )
        # Add context manager methods
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=None)
        mocker.patch.object(fetcher.session, "get", return_value=mock_response)

        nested_path = tmp_path / "a" / "b" / "c" / "file.txt"
        fetcher.download_asset(PROTON_GE_REPO, "v1.0", "file.txt", nested_path)
        assert nested_path.exists()


class TestExtractArchive:
    """Tests for extract_archive method."""

    def test_success(self, fetcher, tar_gz_archive, tmp_path):
        """Extract tar.gz archive successfully."""
        extract_dir = tmp_path / "extract"
        fetcher.extract_archive(tar_gz_archive, extract_dir)
        assert (extract_dir / "test.txt").read_text() == "hello world"

    @pytest.mark.parametrize(
        "archive_content, expected_match",
        [
            (b"not a tar archive", "Failed to extract archive"),
            (b"\x1f\x8b\x08\x00invalid_tar_data", "Failed to extract archive"),
        ],
    )
    def test_failures(self, fetcher, tmp_path, archive_content, expected_match):
        """Raise error on invalid or corrupted archive."""
        invalid_archive = tmp_path / "invalid.tar.gz"
        invalid_archive.write_bytes(archive_content)
        with pytest.raises(FetchError, match=expected_match):
            fetcher.extract_archive(invalid_archive, tmp_path / "extract")

    def test_creates_target_directory(self, fetcher, tar_gz_archive, tmp_path):
        """Create target directory if it doesn't exist."""
        extract_dir = tmp_path / "nonexistent" / "nested" / "path"
        fetcher.extract_archive(tar_gz_archive, extract_dir)
        assert extract_dir.exists()
        assert (extract_dir / "test.txt").read_text() == "hello world"


class TestFetchAndExtract:
    """Tests for fetch_and_extract method."""

    def test_workflow_with_direct_asset(
        self, fetcher, mocker, tar_gz_archive, tmp_path, monkeypatch
    ):
        """Complete workflow when asset name is known."""
        # Mock network calls
        mocker.patch.object(
            fetcher.session,
            "head",
            return_value=mocker.Mock(url=".../releases/tag/v1.0"),
        )
        mock_response = mocker.Mock(
            status_code=200,
            iter_content=lambda chunk_size=1024 * 1024: [tar_gz_archive.read_bytes()],
        )
        # Add context manager methods
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=None)
        mocker.patch.object(fetcher.session, "get", return_value=mock_response)

        # Mock temporary directory to avoid disk I/O
        fake_temp_dir = tmp_path / "temp"
        fake_temp_dir.mkdir()
        mock_temp_dir = mocker.Mock()
        mock_temp_dir.__enter__ = mocker.Mock(return_value=str(fake_temp_dir))
        mock_temp_dir.__exit__ = mocker.Mock(return_value=None)
        monkeypatch.setattr(
            tempfile, "TemporaryDirectory", lambda prefix: mock_temp_dir
        )

        target_dir = tmp_path / "target"
        result = fetcher.fetch_and_extract(PROTON_GE_REPO, "asset.tar.gz", target_dir)

        assert result == target_dir
        assert (target_dir / "test.txt").read_text() == "hello world"

    def test_workflow_with_pattern(
        self, fetcher, mocker, tar_gz_archive, tmp_path, monkeypatch
    ):
        """Complete workflow using asset pattern matching."""
        # Mock network calls
        mocker.patch.object(
            fetcher.session,
            "head",
            return_value=mocker.Mock(url=".../releases/tag/9.14"),
        )
        release_page_response = mocker.Mock(
            text='<a href=".../GE-Proton9-14.tar.gz">GE-Proton9-14.tar.gz</a>'
        )
        download_response = mocker.Mock(
            status_code=200,
            iter_content=lambda chunk_size=1024 * 1024: [tar_gz_archive.read_bytes()],
        )
        # Add context manager methods
        download_response.__enter__ = mocker.Mock(return_value=download_response)
        download_response.__exit__ = mocker.Mock(return_value=None)
        fetcher.session.get.side_effect = [release_page_response, download_response]

        # Mock temporary directory
        fake_temp_dir = tmp_path / "temp"
        fake_temp_dir.mkdir()
        mock_temp_dir = mocker.Mock()
        mock_temp_dir.__enter__ = mocker.Mock(return_value=str(fake_temp_dir))
        mock_temp_dir.__exit__ = mocker.Mock(return_value=None)
        monkeypatch.setattr(
            tempfile, "TemporaryDirectory", lambda prefix: mock_temp_dir
        )

        target_dir = tmp_path / "target"
        result = fetcher.fetch_and_extract(
            PROTON_GE_REPO, PROTONGE_ASSET_PATTERN, target_dir
        )

        assert result == target_dir
        assert (target_dir / "test.txt").read_text() == "hello world"

    def test_calls_methods_in_sequence(self, fetcher, mocker, tmp_path):
        """Verify methods are called in correct order."""
        mocker.patch.object(
            fetcher.session,
            "head",
            return_value=mocker.Mock(url=".../releases/tag/v1.0"),
        )
        mock_response = mocker.Mock(
            status_code=200, iter_content=lambda chunk_size=1024 * 1024: []
        )
        # Add context manager methods
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=None)
        mocker.patch.object(fetcher.session, "get", return_value=mock_response)
        mock_extract = mocker.patch.object(fetcher, "extract_archive")

        fetcher.fetch_and_extract(PROTON_GE_REPO, "asset.tar.gz", tmp_path / "target")

        fetcher.session.head.assert_called_once()
        fetcher.session.get.assert_called_once()
        mock_extract.assert_called_once()


class TestMain:
    """Tests for the main function."""

    @pytest.mark.parametrize(
        "cli_args, expected_asset, expected_target",
        [
            ([], PROTONGE_ASSET_PATTERN, Path(".")),
            (["--asset-name", "custom.tar.gz"], "custom.tar.gz", Path(".")),
            (["--target-dir", "/foo/bar"], PROTONGE_ASSET_PATTERN, Path("/foo/bar")),
            (
                ["--asset-name", "custom.tar.gz", "--target-dir", "/foo/bar"],
                "custom.tar.gz",
                Path("/foo/bar"),
            ),
        ],
    )
    def test_argument_parsing(
        self, mocker, monkeypatch, cli_args, expected_asset, expected_target
    ):
        """Test that main correctly parses arguments and calls fetcher."""
        mock_fetcher_class = mocker.patch("fetcher.GitHubReleaseFetcher")
        mock_fetcher = mock_fetcher_class.return_value

        # Use monkeypatch to set sys.argv for the test
        monkeypatch.setattr(sys, "argv", ["fetcher.py"] + cli_args)

        from fetcher import main

        main()

        mock_fetcher.fetch_and_extract.assert_called_once_with(
            PROTON_GE_REPO, expected_asset, expected_target
        )

    def test_fetch_error_handling(self, mocker, monkeypatch):
        """Test main function handles FetchError correctly."""
        mock_fetcher_class = mocker.patch("fetcher.GitHubReleaseFetcher")
        mock_fetcher_class.return_value.fetch_and_extract.side_effect = FetchError(
            "Test error"
        )
        monkeypatch.setattr(sys, "argv", ["fetcher.py"])

        from fetcher import main

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
