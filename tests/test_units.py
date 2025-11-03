"""
Unit tests for protonfetcher.py
"""

import json
import tarfile
import tempfile
from pathlib import Path

import pytest

from protonfetcher import (
    ArchiveExtractor,
    AssetDownloader,
    ExtractionError,
    FileSystemClient,
    # Types
    ForkName,
    GitHubReleaseFetcher,
    LinkManagementError,
    LinkManager,
    NetworkClient,
    # Exceptions
    NetworkError,
    ReleaseManager,
    # Classes
    Spinner,
    VersionTuple,
    compare_versions,
    format_bytes,
    get_proton_asset_name,
    # Utility functions
    parse_version,
)


class TestUtilityFunctions:
    """Tests for utility functions."""

    @pytest.mark.parametrize(
        "tag,fork,expected",
        [
            # GE-Proton tests
            ("GE-Proton10-20", "GE-Proton", ("GE-Proton", 10, 0, 20)),
            ("GE-Proton1-5", "GE-Proton", ("GE-Proton", 1, 0, 5)),
            # Proton-EM tests
            ("EM-10.0-30", "Proton-EM", ("EM", 10, 0, 30)),
            ("EM-1.5-10", "Proton-EM", ("EM", 1, 5, 10)),
            # Edge cases
            ("invalid-tag", "GE-Proton", ("invalid-tag", 0, 0, 0)),
            ("", "GE-Proton", ("", 0, 0, 0)),
        ],
    )
    def test_parse_version(self, tag: str, fork: ForkName, expected: VersionTuple):
        """Test parse_version function."""
        result = parse_version(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag1,tag2,fork,expected",
        [
            # GE-Proton comparisons
            ("GE-Proton10-20", "GE-Proton10-19", "GE-Proton", 1),  # newer
            ("GE-Proton10-19", "GE-Proton10-20", "GE-Proton", -1),  # older
            ("GE-Proton10-20", "GE-Proton10-20", "GE-Proton", 0),  # equal
            ("GE-Proton11-20", "GE-Proton10-20", "GE-Proton", 1),  # major version
            ("GE-Proton10-21", "GE-Proton10-20", "GE-Proton", 1),  # minor version
            # Proton-EM comparisons
            ("EM-10.0-30", "EM-10.0-29", "Proton-EM", 1),  # newer
            ("EM-10.0-29", "EM-10.0-30", "Proton-EM", -1),  # older
            ("EM-10.0-30", "EM-10.0-30", "Proton-EM", 0),  # equal
            ("EM-11.0-30", "EM-10.0-30", "Proton-EM", 1),  # major version
            ("EM-10.1-30", "EM-10.0-30", "Proton-EM", 1),  # minor version
        ],
    )
    def test_compare_versions(
        self, tag1: str, tag2: str, fork: ForkName, expected: int
    ):
        """Test compare_versions function."""
        result = compare_versions(tag1, tag2, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag,fork,expected",
        [
            ("GE-Proton10-20", "GE-Proton", "GE-Proton10-20.tar.gz"),
            ("EM-10.0-30", "Proton-EM", "proton-EM-10.0-30.tar.xz"),
            ("GE-Proton1-5", "GE-Proton", "GE-Proton1-5.tar.gz"),
            ("EM-1.5-10", "Proton-EM", "proton-EM-1.5-10.tar.xz"),
        ],
    )
    def test_get_proton_asset_name(self, tag: str, fork: ForkName, expected: str):
        """Test get_proton_asset_name function."""
        result = get_proton_asset_name(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (512, "512 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
            (2048, "2.00 KB"),
            (2 * 1024 * 1024, "2.00 MB"),
        ],
    )
    def test_format_bytes(self, bytes_value: int, expected: str):
        """Test format_bytes function."""
        result = format_bytes(bytes_value)
        assert result == expected


class TestSpinner:
    """Tests for the Spinner class."""

    def test_spinner_initialization(self):
        """Test spinner initialization."""
        spinner = Spinner(desc="Test", unit="B", disable=True)
        assert spinner.desc == "Test"
        assert spinner.unit == "B"
        assert spinner.disable is True
        assert spinner.current == 0

    def test_spinner_update(self, mocker):
        """Test spinner update method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(
            desc="Test", disable=False, fps_limit=10
        )  # High FPS limit to allow updates
        spinner.update(5)
        assert spinner.current == 5
        # Verify it tried to print
        mock_print.assert_called()

    def test_spinner_update_progress(self, mocker):
        """Test spinner update_progress method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(desc="Test", disable=False, fps_limit=10)
        spinner.update_progress(50, 100)
        assert spinner.current == 50
        assert spinner.total == 100
        # Verify it tried to print
        mock_print.assert_called()

    def test_spinner_context_manager(self, mocker):
        """Test spinner as context manager."""
        mock_print = mocker.patch("builtins.print")
        with Spinner(disable=False, fps_limit=10) as spinner:
            spinner.update(1)
        # Verify print was called
        mock_print.assert_called()

    def test_spinner_iterable(self, mocker):
        """Test spinner with iterable."""
        mocker.patch("builtins.print")
        test_iterable = iter([1, 2, 3])
        spinner = Spinner(iterable=test_iterable, disable=True)
        result = list(spinner)
        assert result == [1, 2, 3]
        assert spinner.current == 3

    def test_spinner_close(self, mocker):
        """Test spinner close method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(disable=False)
        spinner.close()
        # Verify print was called to clear the line
        mock_print.assert_called()

    def test_spinner_finish(self, mocker):
        """Test spinner finish method."""
        mock_print = mocker.patch("builtins.print")
        spinner = Spinner(disable=False, total=10)
        spinner.current = 5
        spinner.finish()
        # Verify current is set to total and print was called
        assert spinner.current == 10
        mock_print.assert_called()


class TestNetworkClient:
    """Tests for NetworkClient class."""

    def test_init(self):
        """Test NetworkClient initialization."""
        client = NetworkClient(timeout=60)
        assert client.timeout == 60

    def test_get_method(self, mock_subprocess_success):
        """Test GET method."""
        client = NetworkClient(timeout=30)
        _result = client.get("https://example.com")

        mock_subprocess_success.assert_called_once()
        # Verify the command includes the timeout
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert str(30) in cmd  # timeout value should be in the command

    def test_get_method_with_headers(self, mock_subprocess_success):
        """Test GET method with headers."""
        client = NetworkClient(timeout=30)
        headers = {"User-Agent": "Test-Agent"}
        _result = client.get("https://example.com", headers=headers)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "-H" in cmd
        assert "User-Agent: Test-Agent" in cmd

    def test_head_method(self, mock_subprocess_success):
        """Test HEAD method."""
        client = NetworkClient(timeout=30)
        _result = client.head("https://example.com")

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "-I" in cmd  # Verify it's a HEAD request

    def test_download_method(self, mock_subprocess_success):
        """Test download method."""
        client = NetworkClient(timeout=30)
        output_path = Path("/tmp/test.tar.gz")
        _result = client.download("https://example.com/file.tar.gz", output_path)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert str(output_path) in cmd  # Verify output path is in command
        assert "-o" in cmd  # Verify download flag is in command


class TestNetworkClientProtocol:
    """Tests for NetworkClientProtocol using shared fixtures."""

    def test_protocol_compliance(self, mock_network_client):
        """Test that mock network client complies with protocol."""
        # Test that all required methods exist
        assert hasattr(mock_network_client, "get")
        assert hasattr(mock_network_client, "head")
        assert hasattr(mock_network_client, "download")
        assert hasattr(mock_network_client, "timeout")


class TestFileSystemClient:
    """Tests for FileSystemClient class."""

    def test_exists(self):
        """Test exists method."""
        client = FileSystemClient()
        # Test with a path that exists (the root path should exist)
        assert client.exists(Path("/"))
        # Test with a path that doesn't exist
        assert not client.exists(Path("/nonexistent_path_12345"))

    def test_is_dir(self):
        """Test is_dir method."""
        client = FileSystemClient()
        # Test with a directory
        assert client.is_dir(Path("/"))
        # Test with a non-existent path
        assert not client.is_dir(Path("/nonexistent_path_12345"))

    def test_mkdir(self):
        """Test mkdir method."""
        client = FileSystemClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new_dir"
            client.mkdir(new_dir, parents=True, exist_ok=True)
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_write_and_read(self):
        """Test write and read methods."""
        client = FileSystemClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            test_data = b"Hello, world!"

            # Write data
            client.write(file_path, test_data)

            # Read data back
            read_data = client.read(file_path)
            assert read_data == test_data

    def test_symlink_to(self):
        """Test symlink_to method."""
        client = FileSystemClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "target"
            link = Path(temp_dir) / "link"

            # Create target directory
            target.mkdir()

            # Create symlink
            client.symlink_to(link, target, target_is_directory=True)

            # Verify symlink exists and points to target
            assert link.is_symlink()
            assert link.resolve() == target.resolve()

    def test_resolve(self):
        """Test resolve method."""
        client = FileSystemClient()
        path = Path(".")
        resolved = client.resolve(path)
        assert isinstance(resolved, Path)
        assert resolved.is_absolute()

    def test_unlink(self):
        """Test unlink method."""
        client = FileSystemClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "to_delete.txt"
            file_path.write_text("test content")

            assert file_path.exists()

            # Remove the file
            client.unlink(file_path)

            assert not file_path.exists()

    def test_rmtree(self):
        """Test rmtree method."""
        client = FileSystemClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_to_remove = Path(temp_dir) / "to_remove"
            dir_to_remove.mkdir()
            (dir_to_remove / "file.txt").write_text("content")

            assert dir_to_remove.exists()

            # Remove the directory
            client.rmtree(dir_to_remove)

            assert not dir_to_remove.exists()


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
            ("GE-Proton", "GE-Proton10-20", "GE-Proton10-20.tar.gz"),
            ("Proton-EM", "EM-10.0-30", "proton-EM-10.0-30.tar.xz"),
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


class TestAssetDownloader:
    """Tests for AssetDownloader class."""

    def test_init(self, mocker):
        """Test AssetDownloader initialization."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        downloader = AssetDownloader(mock_network, mock_fs, timeout=60)
        assert downloader.timeout == 60
        assert downloader.network_client == mock_network
        assert downloader.file_system_client == mock_fs

    def test_curl_get_method(self, mocker):
        """Test curl_get method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        downloader = AssetDownloader(mock_network, mock_fs)

        mock_response = mocker.Mock()
        mock_network.get.return_value = mock_response

        result = downloader.curl_get("https://example.com")

        mock_network.get.assert_called_once_with("https://example.com", None, False)
        assert result == mock_response

    def test_curl_head_method(self, mocker):
        """Test curl_head method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        downloader = AssetDownloader(mock_network, mock_fs)

        mock_response = mocker.Mock()
        mock_network.head.return_value = mock_response

        result = downloader.curl_head("https://example.com")

        mock_network.head.assert_called_once_with("https://example.com", None, False)
        assert result == mock_response

    def test_download_asset_skip_existing(self, tmp_path, mocker):
        """Test download_asset skips download when file exists with matching size."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        release_manager = mocker.Mock()
        downloader = AssetDownloader(mock_network, mock_fs)

        # Mock file system client to indicate file exists
        mock_fs.exists.return_value = True

        asset_path = tmp_path / "test_asset.tar.gz"
        # Create a file with exactly 100 bytes to match the expected size
        asset_path.write_bytes(b"x" * 100)  # 100 bytes of content

        release_manager.get_remote_asset_size.return_value = 100  # Same size

        # Mock the download methods to avoid network calls
        mock_download_spinner = mocker.patch.object(downloader, "download_with_spinner")

        # Mock network download response for fallback (won't be used in this case)
        mock_download_response = mocker.Mock()
        mock_download_response.return_value = mocker.Mock(returncode=0, stderr="")
        mock_network.download.return_value = mock_download_response

        result = downloader.download_asset(
            "test/repo",
            "GE-Proton10-20",
            "test_asset.tar.gz",
            asset_path,
            release_manager,
        )

        assert result == asset_path
        # Verify network download was NOT called since sizes match
        mock_network.download.assert_not_called()
        # The download should not have been attempted at all
        mock_download_spinner.assert_not_called()

    def test_download_asset_different_size(self, tmp_path, mocker):
        """Test download_asset downloads when file exists with different size."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        release_manager = mocker.Mock()
        downloader = AssetDownloader(mock_network, mock_fs)

        # Mock file system client to indicate file exists
        mock_fs.exists.return_value = True

        asset_path = tmp_path / "test_asset.tar.gz"
        # Create a file with 50 bytes to differ from the expected 100 bytes
        asset_path.write_bytes(b"x" * 50)  # 50 bytes of content

        release_manager.get_remote_asset_size.return_value = 100  # Different size

        # Mock the download_with_spinner method to avoid network calls
        # This way it won't try to actually download but will "succeed"
        mock_download_spinner = mocker.patch.object(downloader, "download_with_spinner")

        # Mock network download response for fallback (won't be used if spinner succeeds)
        mock_download_response = mocker.Mock()
        mock_download_response.return_value = mocker.Mock(returncode=0, stderr="")
        mock_network.download.return_value = mock_download_response

        result = downloader.download_asset(
            "test/repo",
            "GE-Proton10-20",
            "test_asset.tar.gz",
            asset_path,
            release_manager,
        )

        assert result == asset_path
        # download_with_spinner should have been called because sizes differ
        mock_download_spinner.assert_called_once()
        # network.download should NOT be called since spinner "succeeded"
        mock_network.download.assert_not_called()

    def test_download_asset_not_exists(self, tmp_path, mocker):
        """Test download_asset downloads when file doesn't exist."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        release_manager = mocker.Mock()
        downloader = AssetDownloader(mock_network, mock_fs)

        # Mock file system client to indicate file doesn't exist
        mock_fs.exists.return_value = False

        asset_path = tmp_path / "new_asset.tar.gz"
        release_manager.get_remote_asset_size.return_value = 100

        # Mock the download_with_spinner method to simulate success
        # This prevents the network call and the need to mock urllib
        mock_download_spinner = mocker.patch.object(downloader, "download_with_spinner")

        # Mock network download response for fallback (won't be used in this case)
        mock_download_response = mocker.Mock()
        mock_download_response.return_value = mocker.Mock(returncode=0, stderr="")
        mock_network.download.return_value = mock_download_response

        result = downloader.download_asset(
            "test/repo",
            "GE-Proton10-20",
            "new_asset.tar.gz",
            asset_path,
            release_manager,
        )

        assert result == asset_path
        # Since download_with_spinner should be called first and succeed,
        # the fallback to network.download should not happen
        mock_network.download.assert_not_called()
        mock_download_spinner.assert_called_once()
        # Verify mkdir was called with parents=True
        mock_fs.mkdir.assert_called_once()


class TestAssetDownloaderWithFixtures:
    """Tests for AssetDownloader using shared fixtures."""

    def test_init_with_fixtures(self, mock_network_client, mock_filesystem_client):
        """Test AssetDownloader initialization with shared fixtures."""
        downloader = AssetDownloader(
            mock_network_client, mock_filesystem_client, timeout=60
        )
        assert downloader.timeout == 60
        assert downloader.network_client == mock_network_client
        assert downloader.file_system_client == mock_filesystem_client

    @pytest.mark.parametrize(
        "fork,expected_asset",
        [
            ("GE-Proton", "GE-Proton10-20.tar.gz"),
            ("Proton-EM", "proton-EM-10.0-30.tar.xz"),
        ],
    )
    def test_curl_head_method_parametrized(
        self, mocker, mock_network_client, mock_filesystem_client, fork, expected_asset
    ):
        """Parametrized test for curl_head method."""
        downloader = AssetDownloader(mock_network_client, mock_filesystem_client)

        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_network_client.head.return_value = mock_response

        result = downloader.curl_head("https://example.com")

        assert result.returncode == 0
        mock_network_client.head.assert_called_once_with(
            "https://example.com", None, False
        )


class TestArchiveExtractor:
    """Tests for ArchiveExtractor class."""

    def test_init(self, mocker):
        """Test ArchiveExtractor initialization."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs, timeout=60)
        assert extractor.timeout == 60
        assert extractor.file_system_client == mock_fs

    def test_extract_gz_archive_success(
        self, tmp_path, mocker, mock_subprocess_success
    ):
        """Test extracting .tar.gz archive."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a mock archive file
        archive_path = tmp_path / "test.tar.gz"

        mock_subprocess_success.return_value.returncode = 0

        target_dir = tmp_path / "extracted"
        extractor.extract_gz_archive(archive_path, target_dir)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "tar" in cmd
        assert "-xzf" in cmd  # gz flag
        assert str(archive_path) in cmd
        assert str(target_dir) in cmd

        # Verify mkdir was called
        mock_fs.mkdir.assert_called_once_with(target_dir, parents=True, exist_ok=True)

    def test_extract_xz_archive_success(
        self, tmp_path, mocker, mock_subprocess_success
    ):
        """Test extracting .tar.xz archive."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a mock archive file
        archive_path = tmp_path / "test.tar.xz"

        mock_subprocess_success.return_value.returncode = 0

        target_dir = tmp_path / "extracted"
        extractor.extract_xz_archive(archive_path, target_dir)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "tar" in cmd
        assert "-xJf" in cmd  # xz flag
        assert str(archive_path) in cmd
        assert str(target_dir) in cmd

        # Verify mkdir was called
        mock_fs.mkdir.assert_called_once_with(target_dir, parents=True, exist_ok=True)

    def test_extract_gz_archive_failure(
        self, tmp_path, mocker, mock_subprocess_success
    ):
        """Test extracting .tar.gz archive with failure."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a mock archive file
        archive_path = tmp_path / "test.tar.gz"

        mock_subprocess_success.return_value.returncode = 1
        mock_subprocess_success.return_value.stderr = "Extraction failed"

        target_dir = tmp_path / "extracted"

        with pytest.raises(ExtractionError):
            extractor.extract_gz_archive(archive_path, target_dir)

    def test_extract_xz_archive_failure(
        self, tmp_path, mocker, mock_subprocess_success
    ):
        """Test extracting .tar.xz archive with failure."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a mock archive file
        archive_path = tmp_path / "test.tar.xz"

        mock_subprocess_success.return_value.returncode = 1
        mock_subprocess_success.return_value.stderr = "Extraction failed"

        target_dir = tmp_path / "extracted"

        with pytest.raises(ExtractionError):
            extractor.extract_xz_archive(archive_path, target_dir)

    def test_is_tar_file(self, tmp_path, mocker):
        """Test is_tar_file method."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a real small tar file for testing
        tar_file = tmp_path / "test.tar"
        with tarfile.open(tar_file, "w") as tar:
            # Add a small file
            import io

            tarinfo = tarfile.TarInfo(name="test.txt")
            tarinfo.size = 12  # Length of "Hello, world!"
            tar.addfile(tarinfo, io.BytesIO(b"Hello, world!"))

        # Test with valid tar file
        assert extractor.is_tar_file(tar_file)

        # Test with non-existent file - this is handled by tarfile's exception handling
        non_existent = tmp_path / "non_existent.tar"
        # This should return False due to the exception handling in is_tar_file
        assert not extractor.is_tar_file(non_existent)

        # Test with regular file
        regular_file = tmp_path / "regular.txt"
        regular_file.write_text("not a tar file")
        assert not extractor.is_tar_file(regular_file)

    def test_extract_archive_tar_gz(self, tmp_path, mocker, mock_subprocess_success):
        """Test extract_archive method for .tar.gz files."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        archive_path = tmp_path / "test.tar.gz"
        target_dir = tmp_path / "extracted"

        # Import the specific exception type
        from protonfetcher import ProtonFetcherError

        # Mock the extract_with_tarfile method to raise a ProtonFetcherError to trigger fallback
        mock_extract_with_tarfile = mocker.patch.object(
            extractor, "extract_with_tarfile"
        )
        mock_extract_with_tarfile.side_effect = ProtonFetcherError(
            "Tarfile extraction failed temporarily"
        )

        # Also mock extract_gz_archive as the fallback method
        mock_extract_gz = mocker.patch.object(extractor, "extract_gz_archive")

        extractor.extract_archive(archive_path, target_dir)

        # Should have tried extract_with_tarfile first
        mock_extract_with_tarfile.assert_called_once_with(
            archive_path, target_dir, True, True
        )
        # And then called the fallback method
        mock_extract_gz.assert_called_once_with(archive_path, target_dir)

    def test_extract_archive_tar_xz(self, tmp_path, mocker, mock_subprocess_success):
        """Test extract_archive method for .tar.xz files."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        archive_path = tmp_path / "test.tar.xz"
        target_dir = tmp_path / "extracted"

        # Import the specific exception type
        from protonfetcher import ProtonFetcherError

        # Mock the extract_with_tarfile method to raise a ProtonFetcherError to trigger fallback
        mock_extract_with_tarfile = mocker.patch.object(
            extractor, "extract_with_tarfile"
        )
        mock_extract_with_tarfile.side_effect = ProtonFetcherError(
            "Tarfile extraction failed temporarily"
        )

        # Also mock extract_xz_archive as the fallback method
        mock_extract_xz = mocker.patch.object(extractor, "extract_xz_archive")

        extractor.extract_archive(archive_path, target_dir)

        # Should have tried extract_with_tarfile first
        mock_extract_with_tarfile.assert_called_once_with(
            archive_path, target_dir, True, True
        )
        # And then called the fallback method
        mock_extract_xz.assert_called_once_with(archive_path, target_dir)

    def test_extract_with_tarfile_success(self, tmp_path, mocker):
        """Test extract_with_tarfile method success."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a real tar file for testing
        archive_path = tmp_path / "test.tar.gz"
        target_dir = tmp_path / "extracted"

        # Create a small tar.gz file
        with tarfile.open(archive_path, "w:gz") as tar:
            import io

            tarinfo = tarfile.TarInfo(name="test.txt")
            tarinfo.size = 12  # Length of "Hello, world!"
            tar.addfile(tarinfo, io.BytesIO(b"Hello, world!"))

        # Mock the get_archive_info method
        mock_get_archive_info = mocker.patch.object(
            extractor, "get_archive_info", return_value=(1, 12)
        )

        # Mock the spinner
        _mock_spinner = mocker.patch("protonfetcher.Spinner", autospec=True)

        extractor.extract_with_tarfile(
            archive_path, target_dir, show_progress=True, show_file_details=True
        )

        # Verify mkdir was called
        mock_fs.mkdir.assert_called_once_with(target_dir, parents=True, exist_ok=True)
        # Verify get_archive_info was called
        mock_get_archive_info.assert_called_once_with(archive_path)

    def test_get_archive_info(self, tmp_path, mocker):
        """Test get_archive_info method."""
        mock_fs = mocker.Mock()
        extractor = ArchiveExtractor(mock_fs)

        # Create a real tar file for testing
        archive_path = tmp_path / "test.tar.gz"

        # Create a small tar.gz file
        with tarfile.open(archive_path, "w:gz") as tar:
            import io

            tarinfo = tarfile.TarInfo(name="test.txt")
            tarinfo.size = 12  # Length of "Hello, world!"
            tar.addfile(tarinfo, io.BytesIO(b"Hello, world!"))

        total_files, total_size = extractor.get_archive_info(archive_path)

        assert total_files == 1
        assert total_size == 12


class TestArchiveExtractorWithFixtures:
    """Tests for ArchiveExtractor using shared fixtures."""

    def test_init_with_fixtures(self, mock_filesystem_client):
        """Test ArchiveExtractor initialization with shared fixtures."""
        extractor = ArchiveExtractor(mock_filesystem_client, timeout=60)
        assert extractor.timeout == 60
        assert extractor.file_system_client == mock_filesystem_client

    @pytest.mark.parametrize(
        "archive_format,flag",
        [
            (".tar.gz", "-xzf"),
            (".tar.xz", "-xJf"),
        ],
    )
    def test_extract_archive_parametrized(
        self,
        mocker,
        tmp_path,
        mock_filesystem_client,
        mock_subprocess_success,
        archive_format,
        flag,
    ):
        """Parametrized test for archive extraction methods."""
        extractor = ArchiveExtractor(mock_filesystem_client)

        # Create a mock archive file with appropriate extension
        archive_path = tmp_path / f"test{archive_format}"

        mock_subprocess_success.return_value.returncode = 0

        target_dir = tmp_path / "extracted"

        # Use the appropriate extraction method based on format
        if archive_format == ".tar.gz":
            extractor.extract_gz_archive(archive_path, target_dir)
        else:  # .tar.xz
            extractor.extract_xz_archive(archive_path, target_dir)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "tar" in cmd
        assert flag in cmd  # Correct flag for the format
        assert str(archive_path) in cmd
        assert str(target_dir) in cmd

        # Verify mkdir was called
        mock_filesystem_client.mkdir.assert_called_once_with(
            target_dir, parents=True, exist_ok=True
        )


class TestLinkManager:
    """Tests for LinkManager class."""

    def test_init(self, mocker):
        """Test LinkManager initialization."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs, timeout=60)
        assert manager.timeout == 60
        assert manager.file_system_client == mock_fs

    def test_get_link_names_for_fork(self, tmp_path, mocker):
        """Test getting link names for different forks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Test GE-Proton
        main, fb1, fb2 = manager.get_link_names_for_fork(tmp_path, "GE-Proton")
        assert main.name == "GE-Proton"
        assert fb1.name == "GE-Proton-Fallback"
        assert fb2.name == "GE-Proton-Fallback2"

        # Test Proton-EM
        main, fb1, fb2 = manager.get_link_names_for_fork(tmp_path, "Proton-EM")
        assert main.name == "Proton-EM"
        assert fb1.name == "Proton-EM-Fallback"
        assert fb2.name == "Proton-EM-Fallback2"

    def test_find_version_candidates_ge_proton(self, tmp_path, mocker):
        """Test finding version candidates for GE-Proton."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories
        dir1 = tmp_path / "GE-Proton10-20"
        dir2 = tmp_path / "GE-Proton9-15"
        dir3 = tmp_path / "LegacyRuntime"  # Should be filtered out
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        # Mock all the filesystem client methods that are called
        mock_fs.is_dir.return_value = True
        mock_fs.exists.return_value = True

        # Create mock path objects
        mock_ge_dir1 = mocker.Mock()
        mock_ge_dir1.name = "GE-Proton10-20"
        mock_ge_dir1.is_symlink.return_value = False

        mock_ge_dir2 = mocker.Mock()
        mock_ge_dir2.name = "GE-Proton9-15"
        mock_ge_dir2.is_symlink.return_value = False

        mock_legacy_dir = mocker.Mock()
        mock_legacy_dir.name = "LegacyRuntime"
        mock_legacy_dir.is_symlink.return_value = False

        mock_fs.iterdir.return_value = [mock_ge_dir1, mock_ge_dir2, mock_legacy_dir]

        candidates = manager.find_version_candidates(tmp_path, "GE-Proton")

        # Should have GE-Proton10-20 and GE-Proton9-15 (parsed versions)
        # LegacyRuntime should be filtered out based on naming pattern
        expected_versions = [
            parse_version("GE-Proton10-20"),
            parse_version("GE-Proton9-15"),
        ]
        found_versions = [c[0] for c in candidates]
        for expected in expected_versions:
            assert expected in found_versions

    def test_find_version_candidates_proton_em(self, tmp_path, mocker):
        """Test finding version candidates for Proton-EM."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories
        dir1 = tmp_path / "proton-EM-10.0-30"
        dir2 = tmp_path / "EM-10.0-25"
        dir3 = tmp_path / "GE-Proton10-20"  # Should be skipped for Proton-EM
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        # Create mock path entries for the directory
        mock_em_dir1 = mocker.Mock(spec=Path)
        mock_em_dir1.name = "proton-EM-10.0-30"
        mock_em_dir1.is_symlink.return_value = False

        mock_em_dir2 = mocker.Mock(spec=Path)
        mock_em_dir2.name = "EM-10.0-25"
        mock_em_dir2.is_symlink.return_value = False

        mock_ge_dir = mocker.Mock(spec=Path)
        mock_ge_dir.name = "GE-Proton10-20"
        mock_ge_dir.is_symlink.return_value = False

        mock_fs.is_dir.return_value = True
        mock_fs.exists.return_value = True
        mock_fs.iterdir.return_value = [mock_em_dir1, mock_em_dir2, mock_ge_dir]

        candidates = manager.find_version_candidates(tmp_path, "Proton-EM")

        # Should have Proton-EM directories but not GE-Proton
        # Proton-EM directories should be parsed with expected versions
        expected_versions = [
            parse_version("EM-10.0-30", "Proton-EM"),
            parse_version("EM-10.0-25", "Proton-EM"),
        ]
        found_versions = [c[0] for c in candidates]
        for expected in expected_versions:
            assert expected in found_versions
        # Check that GE-Proton is not in the results for Proton-EM
        ge_versions = [v for v, _ in candidates if v[0] == "GE-Proton"]
        assert len(ge_versions) == 0

    def test_create_symlinks(self, tmp_path, mocker):
        """Test creating symlinks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock the directory paths
        dir1 = tmp_path / "GE-Proton10-20"
        dir2 = tmp_path / "GE-Proton9-15"
        dir3 = tmp_path / "GE-Proton8-10"

        # Create test directories
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        # Define test candidates (version, path)
        candidates = [
            (parse_version("GE-Proton10-20"), dir1),
            (parse_version("GE-Proton9-15"), dir2),
            (parse_version("GE-Proton8-10"), dir3),
        ]

        # Mock file system methods with mocker Mock objects
        main_link = tmp_path / "GE-Proton"
        fb1_link = tmp_path / "GE-Proton-Fallback"
        fb2_link = tmp_path / "GE-Proton-Fallback2"

        mock_fs.exists.return_value = False  # Assume links don't exist initially
        mock_fs.unlink.return_value = None
        mock_fs.rmtree.return_value = None
        mock_fs.symlink_to.return_value = None
        mock_fs.resolve.return_value = main_link  # Mock resolve

        # Test creating symlinks
        manager.create_symlinks(main_link, fb1_link, fb2_link, candidates)

        # Verify that symlink_to was called appropriately
        assert mock_fs.symlink_to.called

    def test_list_links(self, tmp_path, mocker):
        """Test listing links."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create mock path objects for the links
        main = mocker.Mock()
        main.name = "GE-Proton"
        fb1 = mocker.Mock()
        fb1.name = "GE-Proton-Fallback"
        fb2 = mocker.Mock()
        fb2.name = "GE-Proton-Fallback2"

        # Mock the get_link_names_for_fork method to return our mock paths
        _mock_get_link_names = mocker.patch.object(
            manager, "get_link_names_for_fork", return_value=(main, fb1, fb2)
        )

        # Mock file system responses - main and fb1 exist, fb2 doesn't
        def mock_exists(path):
            return path.name in ["GE-Proton", "GE-Proton-Fallback"]

        mock_fs.exists = mock_exists

        # Mock the path objects themselves
        main.is_symlink.return_value = True
        main.resolve.return_value = tmp_path / "target_dir"
        fb1.is_symlink.return_value = True
        fb1.resolve.return_value = tmp_path / "target_dir"
        fb2.is_symlink.return_value = False  # fb2 doesn't exist, so it's not a symlink
        fb2.resolve.side_effect = OSError(
            "No such file or directory"
        )  # This would be the case for non-existent symlinks

        links = manager.list_links(tmp_path, "GE-Proton")

        # Should have 3 links
        assert len(links) == 3
        assert links["GE-Proton"] == str(tmp_path / "target_dir")
        assert links["GE-Proton-Fallback"] == str(tmp_path / "target_dir")
        # GE-Proton-Fallback2 should be None since it doesn't exist
        assert links["GE-Proton-Fallback2"] is None

    def test_remove_release_success(self, tmp_path, mocker):
        """Test successful removal of a release."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create a test release directory
        release_dir = tmp_path / "GE-Proton10-20"
        release_dir.mkdir()

        # Mock file system methods with mocker Mock objects
        def mock_exists(path):
            return path == release_dir

        mock_fs.exists = mock_exists
        mock_fs.rmtree.return_value = None
        mock_fs.unlink.return_value = None
        mock_fs.resolve.return_value = (
            release_dir  # Mock symlink resolution to point to release dir
        )

        # Mock manage_proton_links to avoid side effects
        mock_manage = mocker.patch.object(manager, "manage_proton_links")

        success = manager.remove_release(tmp_path, "GE-Proton10-20", "GE-Proton")

        assert success is True
        mock_fs.rmtree.assert_called_once_with(release_dir)
        mock_manage.assert_called_once_with(tmp_path, "GE-Proton10-20", "GE-Proton")

    def test_remove_release_not_found(self, tmp_path, mocker):
        """Test removal of a non-existent release."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock file system to indicate directory doesn't exist
        mock_fs.exists.return_value = False

        with pytest.raises(LinkManagementError):
            manager.remove_release(tmp_path, "NonExistent", "GE-Proton")


class TestLinkManagerWithFixtures:
    """Tests for LinkManager using shared fixtures."""

    def test_init_with_fixtures(self, mock_filesystem_client):
        """Test LinkManager initialization with shared fixtures."""
        manager = LinkManager(mock_filesystem_client, timeout=60)
        assert manager.timeout == 60
        assert manager.file_system_client == mock_filesystem_client

    @pytest.mark.parametrize(
        "fork,expected_links",
        [
            ("GE-Proton", ["GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"]),
            ("Proton-EM", ["Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"]),
        ],
    )
    def test_get_link_names_for_fork_parametrized(
        self, tmp_path, mock_filesystem_client, fork, expected_links
    ):
        """Parametrized test for getting link names for different forks."""
        manager = LinkManager(mock_filesystem_client)

        main, fb1, fb2 = manager.get_link_names_for_fork(tmp_path, fork)
        link_names = [main.name, fb1.name, fb2.name]

        assert link_names == expected_links


class TestGitHubReleaseFetcher:
    """Tests for GitHubReleaseFetcher class."""

    def test_init(self):
        """Test GitHubReleaseFetcher initialization."""
        fetcher = GitHubReleaseFetcher(timeout=60)
        assert fetcher.timeout == 60
        assert isinstance(fetcher.network_client, NetworkClient)
        assert isinstance(fetcher.file_system_client, FileSystemClient)
        assert isinstance(fetcher.release_manager, ReleaseManager)
        assert isinstance(fetcher.asset_downloader, AssetDownloader)
        assert isinstance(fetcher.archive_extractor, ArchiveExtractor)
        assert isinstance(fetcher.link_manager, LinkManager)

    def test_init_with_custom_clients(self, mocker):
        """Test GitHubReleaseFetcher initialization with custom clients."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            timeout=60, network_client=mock_network, file_system_client=mock_fs
        )
        assert fetcher.network_client == mock_network
        assert fetcher.file_system_client == mock_fs

    def test_list_recent_releases(self, mocker):
        """Test list_recent_releases method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager
        mock_release_manager.list_recent_releases.return_value = ["v1.0", "v1.1"]

        result = fetcher.list_recent_releases("test/repo")

        assert result == ["v1.0", "v1.1"]
        mock_release_manager.list_recent_releases.assert_called_once_with("test/repo")

    def test_list_links(self, tmp_path, mocker):
        """Test list_links method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to link_manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager
        mock_link_manager.list_links.return_value = {"GE-Proton": "/path/to/proton"}

        result = fetcher.list_links(tmp_path, "GE-Proton")

        assert result == {"GE-Proton": "/path/to/proton"}
        mock_link_manager.list_links.assert_called_once_with(tmp_path, "GE-Proton")

    def test_remove_release(self, tmp_path, mocker):
        """Test remove_release method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to link_manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager
        mock_link_manager.remove_release.return_value = True

        result = fetcher.remove_release(tmp_path, "GE-Proton10-20", "GE-Proton")

        assert result is True
        mock_link_manager.remove_release.assert_called_once_with(
            tmp_path, "GE-Proton10-20", "GE-Proton"
        )

    def test_fetch_latest_tag(self, mocker):
        """Test fetch_latest_tag method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"

        result = fetcher.fetch_latest_tag("test/repo")

        assert result == "GE-Proton10-20"
        mock_release_manager.fetch_latest_tag.assert_called_once_with("test/repo")

    def test_find_asset_by_name(self, mocker):
        """Test find_asset_by_name method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"

        result = fetcher.find_asset_by_name("test/repo", "GE-Proton10-20")

        assert result == "GE-Proton10-20.tar.gz"
        mock_release_manager.find_asset_by_name.assert_called_once_with(
            "test/repo", "GE-Proton10-20", "GE-Proton"
        )

    def test_get_remote_asset_size(self, mocker):
        """Test get_remote_asset_size method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager
        mock_release_manager.get_remote_asset_size.return_value = 123456789

        result = fetcher.get_remote_asset_size(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )

        assert result == 123456789
        mock_release_manager.get_remote_asset_size.assert_called_once_with(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )

    def test_download_asset(self, tmp_path, mocker):
        """Test download_asset method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to asset_downloader
        mock_asset_downloader = mocker.Mock()
        fetcher.asset_downloader = mock_asset_downloader
        asset_path = tmp_path / "test.tar.gz"
        mock_asset_downloader.download_asset.return_value = asset_path

        result = fetcher.download_asset(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz", asset_path
        )

        assert result == asset_path
        mock_asset_downloader.download_asset.assert_called_once()

    def test_extract_archive(self, tmp_path, mocker):
        """Test extract_archive method."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        # The method should delegate to archive_extractor
        mock_archive_extractor = mocker.Mock()
        fetcher.archive_extractor = mock_archive_extractor

        archive_path = tmp_path / "test.tar.gz"
        target_dir = tmp_path / "target"

        fetcher.extract_archive(archive_path, target_dir)

        mock_archive_extractor.extract_archive.assert_called_once_with(
            archive_path,
            target_dir,
            True,
            True,  # show_progress=True, show_file_details=True
        )


class TestGitHubReleaseFetcherWithFixtures:
    """Tests for GitHubReleaseFetcher using shared fixtures."""

    def test_init_with_fixtures(self, mock_network_client, mock_filesystem_client):
        """Test GitHubReleaseFetcher initialization with shared fixtures."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        assert fetcher.network_client == mock_network_client
        assert fetcher.file_system_client == mock_filesystem_client
        # The managers should be initialized with the fixed clients
        assert fetcher.release_manager.network_client == mock_network_client
        assert fetcher.asset_downloader.network_client == mock_network_client
        assert fetcher.link_manager.file_system_client == mock_filesystem_client

    @pytest.mark.parametrize(
        "fork,repo",
        [
            ("GE-Proton", "GloriousEggroll/proton-ge-custom"),
            ("Proton-EM", "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_list_recent_releases_parametrized(
        self, mocker, mock_network_client, mock_filesystem_client, fork, repo
    ):
        """Parametrized test for list_recent_releases method."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # The method should delegate to release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager
        mock_release_manager.list_recent_releases.return_value = ["v1.0", "v1.1"]

        result = fetcher.list_recent_releases(repo)

        assert result == ["v1.0", "v1.1"]
        mock_release_manager.list_recent_releases.assert_called_once_with(repo)
