import io
import tarfile
from pathlib import Path

import pytest
import requests

from fetcher import GitHubReleaseFetcher, FetchError


@pytest.fixture
def fetcher(mocker):
    """Create a fetcher with mocked session."""
    return GitHubReleaseFetcher(session=mocker.MagicMock(spec=requests.Session))


@pytest.fixture
def tar_gz_archive(tmp_path):
    """Create a test tar.gz archive."""
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
        response = mocker.MagicMock()
        response.url = "https://github.com/owner/repo/releases/tag/v1.2.3"
        fetcher.session.head.return_value = response

        tag = fetcher.fetch_latest_tag("owner/repo")

        assert tag == "v1.2.3"

    def test_invalid_redirect_url(self, fetcher, mocker):
        """Raise error on invalid redirect URL."""
        response = mocker.MagicMock()
        response.url = "https://github.com/owner/repo/releases"
        fetcher.session.head.return_value = response

        with pytest.raises(FetchError, match="Could not determine latest tag"):
            fetcher.fetch_latest_tag("owner/repo")

    def test_request_exception(self, fetcher, mocker):
        """Raise error on network failure."""
        fetcher.session.head.side_effect = requests.ConnectionError("Network error")

        with pytest.raises(FetchError, match="Failed to fetch latest tag"):
            fetcher.fetch_latest_tag("owner/repo")

    def test_http_error(self, fetcher, mocker):
        """Raise error on HTTP error."""
        response = mocker.MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("404")
        fetcher.session.head.return_value = response

        with pytest.raises(FetchError, match="Failed to fetch latest tag"):
            fetcher.fetch_latest_tag("owner/repo")


class TestDownloadAsset:
    """Tests for download_asset method."""

    def test_success(self, fetcher, mocker, tmp_path):
        """Successfully download an asset."""
        response = mocker.MagicMock()
        response.status_code = 200
        response.iter_content.return_value = [b"test content"]
        response.__enter__.return_value = response
        response.__exit__.return_value = None
        fetcher.session.get.return_value = response

        out_path = tmp_path / "test.txt"
        result = fetcher.download_asset("owner/repo", "v1.0", "test.txt", out_path)

        assert result == out_path
        assert out_path.read_bytes() == b"test content"

    def test_asset_not_found(self, fetcher, mocker):
        """Raise error when asset returns 404."""
        response = mocker.MagicMock()
        response.status_code = 404
        response.__enter__.return_value = response
        response.__exit__.return_value = None
        fetcher.session.get.return_value = response

        with pytest.raises(FetchError, match="Asset not found"):
            fetcher.download_asset(
                "owner/repo", "v1.0", "missing.txt", Path("/tmp/missing.txt")
            )

    def test_request_exception(self, fetcher):
        """Raise error on network failure."""
        fetcher.session.get.side_effect = requests.ConnectionError("Network error")

        with pytest.raises(FetchError, match="Failed to download"):
            fetcher.download_asset(
                "owner/repo", "v1.0", "test.txt", Path("/tmp/test.txt")
            )

    def test_creates_parent_directories(self, fetcher, mocker, tmp_path):
        """Create parent directories if they don't exist."""
        response = mocker.MagicMock()
        response.status_code = 200
        response.iter_content.return_value = [b"content"]
        response.__enter__.return_value = response
        response.__exit__.return_value = None
        fetcher.session.get.return_value = response

        nested_path = tmp_path / "a" / "b" / "c" / "file.txt"
        fetcher.download_asset("owner/repo", "v1.0", "file.txt", nested_path)

        assert nested_path.exists()


class TestExtractArchive:
    """Tests for extract_archive method."""

    def test_extract_tar_gz(self, fetcher, tar_gz_archive, tmp_path):
        """Extract tar.gz archive."""
        extract_dir = tmp_path / "extract"
        fetcher.extract_archive(tar_gz_archive, extract_dir)

        assert (extract_dir / "test.txt").read_text() == "hello world"

    def test_unsupported_format(self, fetcher, tmp_path):
        """Raise error on invalid archive."""
        invalid = tmp_path / "test.tar.gz"
        invalid.write_bytes(b"not a tar archive")

        with pytest.raises(FetchError, match="Failed to extract archive"):
            fetcher.extract_archive(invalid, tmp_path / "extract")

    def test_creates_target_directory(self, fetcher, tar_gz_archive, tmp_path):
        """Create target directory if it doesn't exist."""
        extract_dir = tmp_path / "nonexistent" / "nested" / "path"
        fetcher.extract_archive(tar_gz_archive, extract_dir)

        assert extract_dir.exists()
        assert (extract_dir / "test.txt").read_text() == "hello world"

    def test_corrupted_archive(self, fetcher, tmp_path):
        """Raise error on corrupted archive."""
        corrupted = tmp_path / "corrupted.tar.gz"
        corrupted.write_bytes(b"\x1f\x8b\x08\x00invalid_tar_data")

        with pytest.raises(FetchError, match="Failed to extract archive"):
            fetcher.extract_archive(corrupted, tmp_path / "extract")


class TestFetchAndExtract:
    """Tests for fetch_and_extract method."""

    def test_complete_workflow(self, fetcher, mocker, tar_gz_archive, tmp_path):
        """Complete fetch and extract workflow."""
        head_response = mocker.MagicMock()
        head_response.url = "https://github.com/owner/repo/releases/tag/v1.0"
        fetcher.session.head.return_value = head_response

        get_response = mocker.MagicMock()
        get_response.status_code = 200
        get_response.iter_content.return_value = [tar_gz_archive.read_bytes()]
        get_response.__enter__.return_value = get_response
        get_response.__exit__.return_value = None
        fetcher.session.get.return_value = get_response

        target_dir = tmp_path / "target"
        result = fetcher.fetch_and_extract("owner/repo", "asset.tar.gz", target_dir)

        assert result == target_dir
        assert (target_dir / "test.txt").read_text() == "hello world"

    def test_calls_methods_in_sequence(self, fetcher, mocker, tmp_path):
        """Verify methods are called in correct order."""
        head_response = mocker.MagicMock()
        head_response.url = "https://github.com/owner/repo/releases/tag/v1.0"
        fetcher.session.head.return_value = head_response

        get_response = mocker.MagicMock()
        get_response.status_code = 200
        get_response.iter_content.return_value = []
        get_response.__enter__.return_value = get_response
        get_response.__exit__.return_value = None
        fetcher.session.get.return_value = get_response

        mocker.patch.object(fetcher, "extract_archive")

        fetcher.fetch_and_extract("owner/repo", "asset.tar.gz", tmp_path / "target")

        assert fetcher.session.head.call_count == 1
        assert fetcher.session.get.call_count == 1
