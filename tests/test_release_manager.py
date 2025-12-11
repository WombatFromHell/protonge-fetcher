"""
Unit tests for ReleaseManager in protonfetcher.py
"""

import json
import os
import time

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import NetworkError
from protonfetcher.release_manager import ReleaseManager


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

    def test_get_expected_extension_with_invalid_fork_string(self, mocker):
        """Test _get_expected_extension with invalid fork string (lines 168-174)."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test with invalid fork string - should return default extension
        result = manager._get_expected_extension("invalid-fork")
        assert result == ".tar.gz"  # Default extension for invalid fork string

        # Test with ForkName enum - should return appropriate extension
        result_ge = manager._get_expected_extension(ForkName.GE_PROTON)
        assert result_ge == ".tar.gz"

        result_em = manager._get_expected_extension(ForkName.PROTON_EM)
        assert result_em == ".tar.xz"

        # Test with string that's not valid ForkName - should return default
        result = manager._get_expected_extension("some-random-string")
        assert result == ".tar.gz"

    def test_follow_redirect_and_get_size_functionality(self, mocker):
        """Test _follow_redirect_and_get_size method with various scenarios (lines 387-393)."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test successful redirect with content-length
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://redirected.example.com/file.tar.gz\n"

        redirected_result = mocker.Mock()
        redirected_result.returncode = 0
        redirected_result.stdout = "Content-Length: 123456789\nOther-Header: value\n"

        mock_network.head.return_value = redirected_result

        size = manager._follow_redirect_and_get_size(
            initial_result,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            in_test=True,  # Skip caching during test
        )

        assert size == 123456789
        mock_network.head.assert_called_once_with(
            "https://redirected.example.com/file.tar.gz", follow_redirects=False
        )

        # Test when redirect URL is same as original
        initial_result_same_url = mocker.Mock()
        initial_result_same_url.stdout = (
            "Location: https://original.example.com/file.tar.gz\n"
        )

        size = manager._follow_redirect_and_get_size(
            initial_result_same_url,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            in_test=True,
        )

        assert size is None  # Should return None when URLs are the same

    def test_follow_redirect_and_get_size_with_error_response(self, mocker):
        """Test _follow_redirect_and_get_size method when redirect response contains error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test redirect with error in response - this should raise NetworkError
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://redirected.example.com/file.tar.gz\n"

        redirected_result_with_error = mocker.Mock()
        redirected_result_with_error.returncode = 0
        redirected_result_with_error.stdout = "404 Not Found"

        mock_network.head.return_value = redirected_result_with_error

        with pytest.raises(NetworkError):
            manager._follow_redirect_and_get_size(
                initial_result,
                "https://original.example.com/file.tar.gz",
                "test/repo",
                "GE-Proton10-20",
                "GE-Proton10-20.tar.gz",
                in_test=True,
            )

    def test_init_with_xdg_cache_home(self, mocker):
        """Test ReleaseManager initialization with XDG_CACHE_HOME environment variable."""
        # Mock the environment to include XDG_CACHE_HOME
        mocker.patch.dict(os.environ, {"XDG_CACHE_HOME": "/tmp/custom_cache"})
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(mock_network, mock_fs)

        # Verify that the cache directory was set correctly
        assert "/tmp/custom_cache/protonfetcher" in str(manager._cache_dir)

    def test_init_with_default_cache_dir(self, mocker):
        """Test ReleaseManager initialization with default cache directory."""
        # Mock environment to not have XDG_CACHE_HOME
        mocker.patch.dict(os.environ, {}, clear=True)
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(mock_network, mock_fs)

        # Verify that the cache directory was set to the default
        expected_path = manager._cache_dir
        assert str(expected_path).endswith(".cache/protonfetcher")

    # Cache-related tests
    def test_get_cache_key(self, mocker):
        """Test _get_cache_key method generates consistent keys."""
        # Create a release manager with mocked clients
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(mock_network, mock_fs)

        # Test that the same inputs always generate the same key
        key1 = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        key2 = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        assert key1 == key2

        # Test that different inputs generate different keys
        key3 = manager._get_cache_key("other/repo", "test-tag", "test-asset.tar.gz")
        assert key1 != key3

    def test_get_cache_path(self, mocker, tmp_path):
        """Test _get_cache_path returns correct path."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        manager = ReleaseManager(mock_network, mock_fs)
        # Override cache dir for testing
        manager._cache_dir = tmp_path / "cache"

        cache_key = "abc123"
        expected_path = tmp_path / "cache" / "abc123"
        actual_path = manager._get_cache_path(cache_key)

        assert actual_path == expected_path

    def test_is_cache_valid_file_not_exists(self, mocker, tmp_path):
        """Test _is_cache_valid returns False when cache file doesn't exist."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Mock the filesystem client to return False for exists and appropriate values for other methods
        mock_fs.exists.return_value = False

        manager = ReleaseManager(mock_network, mock_fs)
        # Override cache dir for testing
        manager._cache_dir = tmp_path / "cache"

        cache_path = tmp_path / "cache" / "nonexistent"
        assert not manager._is_cache_valid(cache_path)

    def test_is_cache_valid_file_exists_not_expired(self, mocker, tmp_path):
        """Test _is_cache_valid returns True for non-expired cache file."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Mock the filesystem client to return appropriate values
        mock_fs.exists.return_value = True
        # Mock mtime to return a recent time (not expired)
        current_time = time.time()
        mock_fs.mtime.return_value = (
            current_time - 100
        )  # 100 seconds ago, well within 3600s default

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        # Create a cache file path
        cache_file = tmp_path / "cache" / "test_cache"
        assert manager._is_cache_valid(cache_file)

    def test_is_cache_valid_file_exists_expired(self, mocker, tmp_path):
        """Test _is_cache_valid returns False for expired cache file."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Mock the filesystem client to return appropriate values
        mock_fs.exists.return_value = True
        # Mock mtime to return an old time (expired)
        current_time = time.time()
        mock_fs.mtime.return_value = (
            current_time - 4000
        )  # 4000 seconds ago, more than default 3600 and custom 1000

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        # Create a cache file path
        cache_file = tmp_path / "cache" / "test_cache"
        # File should be invalid with default max_age (3600 seconds) and short custom max_age
        assert not manager._is_cache_valid(cache_file, max_age=1000)

    @pytest.mark.parametrize(
        "mock_read_data,expected_result",
        [
            (
                json.dumps(
                    {
                        "size": 12345,
                        "timestamp": time.time(),
                        "repo": "test/repo",
                        "tag": "test-tag",
                        "asset_name": "test-asset.tar.gz",
                    }
                ).encode(),
                12345,
            ),  # Valid cache
            (b"invalid json", None),  # Invalid JSON
            (
                json.dumps(
                    {
                        "timestamp": time.time(),
                        "repo": "test/repo",
                        "tag": "test-tag",
                        "asset_name": "test-asset.tar.gz",
                    }
                ).encode(),
                None,
            ),  # Missing size field
            (
                json.dumps(
                    {
                        "size": "not_a_number",
                        "timestamp": time.time(),
                        "repo": "test/repo",
                        "tag": "test-tag",
                        "asset_name": "test-asset.tar.gz",
                    }
                ).encode(),
                None,
            ),  # Invalid size type
        ],
    )
    def test_get_cached_asset_size_various_scenarios(
        self, mocker, tmp_path, mock_read_data, expected_result
    ):
        """Test _get_cached_asset_size with various cache scenarios."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Calculate the actual cache key that will be generated
        import hashlib

        expected_cache_key = hashlib.md5(
            b"test/repo_test-tag_test-asset.tar.gz_size"
        ).hexdigest()
        cache_file_path = tmp_path / "cache" / expected_cache_key

        def exists_side_effect(path):
            return path == cache_file_path

        def mtime_side_effect(path):
            return time.time() - 100  # Not expired

        def read_side_effect(path):
            return mock_read_data

        mock_fs.exists.side_effect = exists_side_effect
        mock_fs.mtime.side_effect = mtime_side_effect
        mock_fs.read.side_effect = read_side_effect

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size == expected_result

    def test_get_cached_asset_size_expired_cache(self, mocker, tmp_path):
        """Test _get_cached_asset_size returns None for expired cache."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Calculate the actual cache key that will be generated
        import hashlib

        expected_cache_key = hashlib.md5(
            b"test/repo_test-tag_test-asset.tar.gz_size"
        ).hexdigest()
        cache_file_path = tmp_path / "cache" / expected_cache_key

        def exists_side_effect(path):
            return path == cache_file_path

        def mtime_side_effect(path):
            return time.time() - 4000  # Expired (older than default 3600 seconds)

        def read_side_effect(path):
            cache_data = {
                "size": 12345,
                "timestamp": time.time(),
                "repo": "test/repo",
                "tag": "test-tag",
                "asset_name": "test-asset.tar.gz",
            }
            return json.dumps(cache_data).encode()

        mock_fs.exists.side_effect = exists_side_effect
        mock_fs.mtime.side_effect = mtime_side_effect
        mock_fs.read.side_effect = read_side_effect

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        # Should return None because cache is expired
        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size is None

    def test_get_cached_asset_size_missing_file(self, mocker):
        """Test getting cached asset size when cache file doesn't exist."""
        # Mock file system operations
        mock_fs = mocker.Mock()
        mock_fs.exists.return_value = False

        manager = ReleaseManager(mocker.Mock(), mock_fs)

        size = manager._get_cached_asset_size(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )
        assert size is None

    def test_get_cached_asset_size_valid_cache(self, mocker, tmp_path):
        """Test _get_cached_asset_size returns size from valid cache."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Calculate the actual cache key that will be generated
        import hashlib

        expected_cache_key = hashlib.md5(
            b"test/repo_test-tag_test-asset.tar.gz_size"
        ).hexdigest()
        cache_file_path = tmp_path / "cache" / expected_cache_key

        def exists_side_effect(path):
            return path == cache_file_path

        def mtime_side_effect(path):
            return time.time() - 100  # Not expired

        def read_side_effect(path):
            cache_data = {
                "size": 12345,
                "timestamp": time.time(),
                "repo": "test/repo",
                "tag": "test-tag",
                "asset_name": "test-asset.tar.gz",
            }
            return json.dumps(cache_data).encode()

        mock_fs.exists.side_effect = exists_side_effect
        mock_fs.mtime.side_effect = mtime_side_effect
        mock_fs.read.side_effect = read_side_effect

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size == 12345

    def test_get_cached_asset_size_invalid_cache(self, mocker, tmp_path):
        """Test _get_cached_asset_size returns None for invalid cache."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Calculate the actual cache key that will be generated
        import hashlib

        expected_cache_key = hashlib.md5(
            b"test/repo_test-tag_test-asset.tar.gz_size"
        ).hexdigest()
        cache_file_path = tmp_path / "cache" / expected_cache_key

        def exists_side_effect(path):
            return path == cache_file_path

        def mtime_side_effect(path):
            return time.time() - 100  # Not expired

        def read_side_effect(path):
            return b"invalid json"

        mock_fs.exists.side_effect = exists_side_effect
        mock_fs.mtime.side_effect = mtime_side_effect
        mock_fs.read.side_effect = read_side_effect

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size is None

    def test_get_cached_asset_size_missing_size(self, mocker, tmp_path):
        """Test _get_cached_asset_size returns None when size is missing from cache."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Calculate the actual cache key that will be generated
        import hashlib

        expected_cache_key = hashlib.md5(
            b"test/repo_test-tag_test-asset.tar.gz_size"
        ).hexdigest()
        cache_file_path = tmp_path / "cache" / expected_cache_key

        def exists_side_effect(path):
            return path == cache_file_path

        def mtime_side_effect(path):
            return time.time() - 100  # Not expired

        def read_side_effect(path):
            cache_data = {
                "timestamp": time.time(),
                "repo": "test/repo",
                "tag": "test-tag",
                "asset_name": "test-asset.tar.gz",
            }
            return json.dumps(cache_data).encode()

        mock_fs.exists.side_effect = exists_side_effect
        mock_fs.mtime.side_effect = mtime_side_effect
        mock_fs.read.side_effect = read_side_effect

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size is None

    def test_get_cached_asset_size_io_error(self, mocker):
        """Test getting cached asset size when there's an IO error reading the cache."""
        # Mock file system operations
        mock_fs = mocker.Mock()
        mock_fs.exists.return_value = True
        mock_fs.mtime.return_value = 1000000  # Some timestamp

        # Raise IOError when reading
        mock_fs.read.side_effect = IOError("File read error")

        manager = ReleaseManager(mocker.Mock(), mock_fs)

        size = manager._get_cached_asset_size(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )
        assert size is None

    def test_cache_asset_size_success(self, mocker, tmp_path):
        """Test _cache_asset_size successfully stores asset size."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Mock filesystem client to track write calls
        written_files = {}

        def write_side_effect(path, data):
            written_files[path] = data
            return None  # write method returns None

        mock_fs.write.side_effect = write_side_effect

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"

        # Cache an asset size
        repo, tag, asset_name, size = (
            "test/repo",
            "test-tag",
            "test-asset.tar.gz",
            12345,
        )
        manager._cache_asset_size(repo, tag, asset_name, size)

        # Verify the cache file was created with correct data
        cache_key = manager._get_cache_key(repo, tag, asset_name)
        expected_path = manager._get_cache_path(cache_key)

        # Check that write was called exactly once
        assert mock_fs.write.call_count == 1

        # Check that it was called with the correct path
        call_args = mock_fs.write.call_args
        written_path, written_data = call_args[0]  # Extract path and data from the call

        assert written_path == expected_path
        written_data_dict = json.loads(written_data.decode())

        assert written_data_dict["size"] == size
        assert written_data_dict["repo"] == repo
        assert written_data_dict["tag"] == tag
        assert written_data_dict["asset_name"] == asset_name
        assert "timestamp" in written_data_dict

    def test_cache_asset_size_io_error(self, tmp_path, mocker):
        """Test _cache_asset_size handles IO errors gracefully."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        # Mock the write method to raise an exception
        mock_fs.write.side_effect = OSError("Permission denied")

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        # Don't create the cache dir to force an IO error

        # Mock logger.debug to verify it gets called
        mock_logger = mocker.patch("protonfetcher.release_manager.logger")

        # This should not raise an exception even if cache write fails
        manager._cache_asset_size("test/repo", "test-tag", "test-asset.tar.gz", 12345)

        # Verify that logger.debug was called (indicating the error was caught)
        mock_logger.debug.assert_called_once()
        # The method should not raise an exception on IO failure

    # Tag fetching tests
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

    def test_fetch_latest_tag_with_original_url_fallback(self, mocker):
        """Test fetching latest tag falling back to original URL when no location or URL found."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response without Location or URL header - use original URL
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "HTTP/1.1 200 OK\nSome other headers\n"
        mock_network.head.return_value = mock_response

        # This should raise NetworkError since no tag can be extracted from the original URL
        with pytest.raises(NetworkError):
            manager.fetch_latest_tag("test/repo")

    def test_fetch_latest_tag_network_error(self, mocker):
        """Test fetching latest tag with network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock a failed response
        mock_response = mocker.Mock()
        mock_response.returncode = 1
        mock_response.stderr = "Connection error"
        mock_network.head.return_value = mock_response

        with pytest.raises(NetworkError):
            manager.fetch_latest_tag("test/repo")

    def test_fetch_latest_tag_exception(self, mocker):
        """Test fetching latest tag with exception."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock a failed response
        mock_network.head.side_effect = Exception("Network error")

        with pytest.raises(NetworkError):
            manager.fetch_latest_tag("test/repo")

    # Asset finding tests
    @pytest.mark.parametrize(
        "fork,tag,expected_asset,expected_extension",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20", "GE-Proton10-20.tar.gz", ".tar.gz"),
            (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30.tar.xz", ".tar.xz"),
        ],
    )
    def test_find_asset_by_name_api_success_parametrized(
        self, mocker, fork, tag, expected_asset, expected_extension
    ):
        """Test finding asset using API successfully with both GE-Proton and Proton-EM."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock successful API response
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = json.dumps(
            {"assets": [{"name": expected_asset}, {"name": "other-file.txt"}]}
        )
        mock_network.get.return_value = mock_response

        result = manager.find_asset_by_name("test/repo", tag, fork)

        assert result == expected_asset
        mock_network.get.assert_called_once()

    def test_find_asset_by_name_api_no_matching_extension(self, mocker):
        """Test finding asset when no matching extension found, falling back to first asset."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock API response with no matching extension assets
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = json.dumps(
            {"assets": [{"name": "different.txt"}, {"name": "another-file.zip"}]}
        )
        mock_network.get.return_value = mock_response

        result = manager.find_asset_by_name(
            "test/repo", "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result == "different.txt"  # First available asset
        mock_network.get.assert_called_once()

    def test_find_asset_by_name_api_empty_assets(self, mocker):
        """Test finding asset when no assets are available via API."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock API response with no assets
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = json.dumps({"assets": []})
        mock_network.get.return_value = mock_response

        result = manager.find_asset_by_name(
            "test/repo", "GE-Proton10-20", ForkName.GE_PROTON
        )
        # With empty assets, it should return None since no matching asset is found
        assert result is None

    def test_find_asset_by_name_api_no_assets_field(self, mocker):
        """Test finding asset when 'assets' field is missing in API response."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock API response without 'assets' field
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = json.dumps({"tag_name": "GE-Proton10-20"})
        mock_network.get.return_value = mock_response

        with pytest.raises(Exception, match="No assets found in release API response"):
            manager._try_api_approach("test/repo", "GE-Proton10-20", ForkName.GE_PROTON)

    def test_find_asset_by_name_api_json_decode_error(self, mocker):
        """Test finding asset when API response is not valid JSON."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock malformed JSON response
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "{invalid json"
        mock_network.get.return_value = mock_response

        with pytest.raises(Exception, match="Failed to parse JSON"):
            manager._try_api_approach("test/repo", "GE-Proton10-20", ForkName.GE_PROTON)

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

        result = manager.find_asset_by_name(
            "test/repo", "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result == "GE-Proton10-20.tar.gz"
        assert mock_network.get.call_count == 2

    def test_find_asset_by_name_not_found_in_html(self, mocker):
        """Test finding asset when not found in HTML and returns None."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # API fails and HTML parsing also fails to find the asset
        mock_api_response = mocker.Mock()
        mock_api_response.returncode = 1
        mock_api_response.stderr = "API error"

        mock_html_response = mocker.Mock()
        mock_html_response.returncode = 0
        mock_html_response.stdout = "Some content without the asset name"

        mock_network.get.side_effect = [mock_api_response, mock_html_response]

        result = manager.find_asset_by_name(
            "test/repo", "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result is None
        assert mock_network.get.call_count == 2

    def test_find_asset_by_name_html_network_error(self, mocker):
        """Test finding asset when HTML fallback also has network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # API fails and HTML parsing also fails
        mock_api_response = mocker.Mock()
        mock_api_response.returncode = 1
        mock_api_response.stderr = "API error"

        mock_html_response = mocker.Mock()
        mock_html_response.returncode = 1
        mock_html_response.stderr = "HTML fetch error"

        mock_network.get.side_effect = [mock_api_response, mock_html_response]

        with pytest.raises(NetworkError):
            manager.find_asset_by_name(
                "test/repo", "GE-Proton10-20", ForkName.GE_PROTON
            )

        assert mock_network.get.call_count == 2

    # Asset size tests
    @pytest.mark.parametrize(
        "fork,tag,expected_asset",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20", "GE-Proton10-20.tar.gz"),
            (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30.tar.xz"),
        ],
    )
    def test_get_remote_asset_size_parametrized(
        self, mocker, fork, tag, expected_asset
    ):
        """Parametrized test for getting remote asset size."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with Content-Length header
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "Content-Length: 123456789\nOther-Header: value\n"
        mock_network.head.return_value = mock_response

        result = manager.get_remote_asset_size("test/repo", tag, expected_asset)

        assert result == 123456789
        mock_network.head.assert_called_once()

    @pytest.mark.parametrize(
        "fork,tag,asset_name,error_type,error_content",
        [
            (
                ForkName.GE_PROTON,
                "GE-Proton10-20",
                "GE-Proton10-20.tar.gz",
                "stderr",
                "404 Not Found",
            ),
            (
                ForkName.PROTON_EM,
                "EM-10.0-30",
                "proton-EM-10.0-30.tar.xz",
                "stderr",
                "404 Not Found",
            ),
            (
                ForkName.GE_PROTON,
                "GE-Proton9-15",
                "GE-Proton9-15.tar.gz",
                "stdout",
                "404 Not Found",
            ),
            (
                ForkName.PROTON_EM,
                "EM-9.5-25",
                "proton-EM-9.5-25.tar.xz",
                "stdout",
                "404 Not Found",
            ),
            (
                ForkName.GE_PROTON,
                "GE-Proton8-10",
                "GE-Proton8-10.tar.gz",
                "returncode",
                "nonzero",
            ),
            (
                ForkName.PROTON_EM,
                "EM-8.0-20",
                "proton-EM-8.0-20.tar.xz",
                "returncode",
                "nonzero",
            ),
        ],
    )
    def test_get_remote_asset_size_error_scenarios(
        self, mocker, fork, tag, asset_name, error_type, error_content
    ):
        """Parametrized test for getting remote asset size with various error scenarios."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response based on error type
        mock_response = mocker.Mock()
        if error_type == "returncode":
            mock_response.returncode = 1
            mock_response.stderr = "Some error"
        else:
            mock_response.returncode = 0
            if error_type == "stderr":
                mock_response.stderr = error_content
                mock_response.stdout = ""
            elif error_type == "stdout":
                mock_response.stdout = error_content
                mock_response.stderr = ""

        mock_network.head.return_value = mock_response

        with pytest.raises(NetworkError):
            manager.get_remote_asset_size("test/repo", tag, asset_name)

    def test_get_remote_asset_size_no_content_length(self, mocker):
        """Test getting remote asset size when no content length is present."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response without content length header
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "Some other headers\n"
        mock_network.head.return_value = mock_response

        # Mock the follow redirect method to return a size
        mocker.patch.object(
            manager, "_follow_redirect_and_get_size", return_value=123456
        )

        result = manager.get_remote_asset_size(
            "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
        )

        assert result == 123456

    def test_get_remote_asset_size_no_content_length_and_no_redirect_size(self, mocker):
        """Test getting remote asset size when no content length and redirect also fails."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response without content length header
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "Some other headers\n"
        mock_network.head.return_value = mock_response

        # Mock the follow redirect method to return None
        mocker.patch.object(manager, "_follow_redirect_and_get_size", return_value=None)

        with pytest.raises(NetworkError):
            manager.get_remote_asset_size(
                "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
            )

    def test_get_remote_asset_size_exception(self, mocker):
        """Test getting remote asset size with exception."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock network client to raise an exception
        mock_network.head.side_effect = Exception("Network error")

        with pytest.raises(NetworkError):
            manager.get_remote_asset_size(
                "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
            )

    def test_get_expected_extension(self, mocker):
        """Test getting expected extension for different forks."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Test GE Proton
        assert manager._get_expected_extension(ForkName.GE_PROTON) == ".tar.gz"

        # Test Proton EM
        assert manager._get_expected_extension(ForkName.PROTON_EM) == ".tar.xz"

        # Test invalid fork - should default to .tar.gz
        assert manager._get_expected_extension("invalid") == ".tar.gz"

    def test_find_matching_assets(self, mocker):
        """Test finding matching assets by extension."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        assets = [
            {"name": "file1.tar.gz"},
            {"name": "file2.tar.xz"},
            {"name": "file3.txt"},
            {"name": "file4.TAR.GZ"},  # Test case insensitivity
        ]

        # Find .tar.gz files
        matching = manager._find_matching_assets(assets, ".tar.gz")
        assert len(matching) == 2
        assert matching[0]["name"] == "file1.tar.gz"
        assert matching[1]["name"] == "file4.TAR.GZ"

    def test_handle_api_response_matching_assets(self, mocker):
        """Test handling API response with matching assets."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        assets = [
            {"name": "file1.tar.gz"},
            {"name": "file2.tar.xz"},
        ]

        result = manager._handle_api_response(assets, ".tar.gz")
        assert result == "file1.tar.gz"

    def test_handle_api_response_no_matching_assets(self, mocker):
        """Test handling API response with no matching assets."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        assets = [
            {"name": "file1.zip"},
            {"name": "file2.txt"},
        ]

        result = manager._handle_api_response(assets, ".tar.gz")
        assert result == "file1.zip"  # First available asset

    def test_handle_api_response_empty_assets(self, mocker):
        """Test handling API response with empty assets."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        assets = []

        with pytest.raises(Exception, match="No assets found in release"):
            manager._handle_api_response(assets, ".tar.gz")

    def test_check_for_error_in_response_404_stdout(self, mocker):
        """Test checking for error in response with 404 in stdout."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        result = mocker.Mock()
        result.stdout = "404 Not Found"
        result.stderr = ""

        with pytest.raises(NetworkError, match="Remote asset not found"):
            manager._check_for_error_in_response(result, "test.tar.gz")

    def test_check_for_error_in_response_not_found_stdout(self, mocker):
        """Test checking for error in response with 'not found' in stdout."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        result = mocker.Mock()
        result.stdout = "file not found"
        result.stderr = ""

        with pytest.raises(NetworkError, match="Remote asset not found"):
            manager._check_for_error_in_response(result, "test.tar.gz")

    def test_check_for_error_in_response_404_stderr(self, mocker):
        """Test checking for error in response with 404 in stderr."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        result = mocker.Mock()
        result.stdout = ""
        result.stderr = "404 Not Found"

        with pytest.raises(NetworkError, match="Remote asset not found"):
            manager._check_for_error_in_response(result, "test.tar.gz")

    def test_check_for_error_in_response_not_found_stderr(self, mocker):
        """Test checking for error in response with 'not found' in stderr."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        result = mocker.Mock()
        result.stdout = ""
        result.stderr = "file not found"

        with pytest.raises(NetworkError, match="Remote asset not found"):
            manager._check_for_error_in_response(result, "test.tar.gz")

    def test_extract_size_from_response_single_line(self, mocker):
        """Test extracting size from response with content-length in a single line."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "Content-Length: 123456789\nOther-Header: value\n"
        size = manager._extract_size_from_response(response_text)
        assert size == 123456789

    def test_extract_size_from_response_case_insensitive(self, mocker):
        """Test extracting size from response with case-insensitive header."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "content-length: 987654321\nOther-Header: value\n"
        size = manager._extract_size_from_response(response_text)
        assert size == 987654321

    def test_extract_size_from_response_with_colon_space(self, mocker):
        """Test extracting size from response with various spacing after colon."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "Content-Length:    111222333\nOther-Header: value\n"
        size = manager._extract_size_from_response(response_text)
        assert size == 111222333

    def test_extract_size_from_response_regex_fallback(self, mocker):
        """Test extracting size using regex fallback when not found in individual lines."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "Some headers\n  Content-Length: 555666777  \nMore headers"
        size = manager._extract_size_from_response(response_text)
        assert size == 555666777

    def test_extract_size_from_response_zero_size(self, mocker):
        """Test extracting size when it's 0 (should return None)."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "Content-Length: 0\nOther-Header: value\n"
        size = manager._extract_size_from_response(response_text)
        assert size is None

    def test_extract_size_from_response_negative_size(self, mocker):
        """Test extracting size when it's negative."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "Content-Length: -1\nOther-Header: value\n"
        size = manager._extract_size_from_response(response_text)
        assert size is None

    def test_extract_size_from_response_no_size(self, mocker):
        """Test extracting size when no content-length is found."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        response_text = "Some other headers\nNo content-length here\n"
        size = manager._extract_size_from_response(response_text)
        assert size is None

    def test_follow_redirect_and_get_size_success(self, mocker):
        """Test following redirect and getting size successfully."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Initial response with redirect
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://redirected.example.com/file.tar.gz\n"

        # Redirect response with content length
        redirected_result = mocker.Mock()
        redirected_result.returncode = 0
        redirected_result.stdout = "Content-Length: 123456789\n"

        mock_network.head.return_value = redirected_result

        size = manager._follow_redirect_and_get_size(
            initial_result,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            True,  # in_test=True to skip caching
        )

        assert size == 123456789
        mock_network.head.assert_called_once_with(
            "https://redirected.example.com/file.tar.gz", follow_redirects=False
        )

    def test_follow_redirect_and_get_size_no_redirect(self, mocker):
        """Test following redirect when no redirect is present."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Initial response without redirect
        initial_result = mocker.Mock()
        initial_result.stdout = "Some other headers\n"

        size = manager._follow_redirect_and_get_size(
            initial_result,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            True,
        )

        assert size is None
        # head should not have been called since there's no redirect
        mock_network.head.assert_not_called()

    def test_follow_redirect_and_get_size_same_url(self, mocker):
        """Test following redirect when redirect URL is the same as original."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Initial response with redirect to same URL (no real redirect)
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://original.example.com/file.tar.gz\n"

        size = manager._follow_redirect_and_get_size(
            initial_result,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            True,
        )

        assert size is None
        # head should not have been called since it's the same URL
        mock_network.head.assert_not_called()

    def test_follow_redirect_and_get_size_head_error(self, mocker):
        """Test following redirect when head request fails."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Initial response with redirect
        initial_result = mocker.Mock()
        initial_result.stdout = "Location: https://redirected.example.com/file.tar.gz\n"

        # Head request returns error
        redirected_result = mocker.Mock()
        redirected_result.returncode = 1
        redirected_result.stderr = "Connection error"

        mock_network.head.return_value = redirected_result

        size = manager._follow_redirect_and_get_size(
            initial_result,
            "https://original.example.com/file.tar.gz",
            "test/repo",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
            True,  # in_test=True to skip caching
        )

        assert size is None

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

    # Recent releases tests
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

    def test_list_recent_releases_rate_limit_error_stderr(self, mocker):
        """Test listing recent releases with rate limit error in stderr."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with rate limit error in stderr (return code 1 for errors)
        mock_response = mocker.Mock()
        mock_response.returncode = 1  # Non-zero return code triggers the error
        mock_response.stderr = "rate limit exceeded"
        mock_response.stdout = ""
        mock_network.get.return_value = mock_response

        with pytest.raises(NetworkError):
            manager.list_recent_releases("test/repo")

    def test_list_recent_releases_rate_limit_error_stdout(self, mocker):
        """Test listing recent releases with rate limit error in stdout after JSON parsing."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with content that will trigger rate limit error check after JSON parsing
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stderr = ""
        mock_response.stdout = (
            '{"some_data": "value"}\nrate limit exceeded somewhere in the response'
        )
        mock_network.get.return_value = mock_response

        # Mock json.loads to return normal data - the actual rate limit check happens after JSON parsing
        mocker.patch("json.loads", return_value=[{"tag_name": "test_release"}])

        with pytest.raises(NetworkError, match="rate limit exceeded"):
            manager.list_recent_releases("test/repo")

    def test_list_recent_releases_json_decode_error(self, mocker):
        """Test listing recent releases with JSON decode error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with invalid JSON
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        mock_response.stdout = "{invalid json"
        mock_network.get.return_value = mock_response

        with pytest.raises(NetworkError, match="Failed to parse JSON response"):
            manager.list_recent_releases("test/repo")

    def test_list_recent_releases_network_error(self, mocker):
        """Test listing recent releases with network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with non-zero return code
        mock_response = mocker.Mock()
        mock_response.returncode = 1
        mock_response.stderr = "Connection error"
        mock_network.get.return_value = mock_response

        with pytest.raises(NetworkError):
            manager.list_recent_releases("test/repo")

    def test_list_recent_releases_network_exception(self, mocker):
        """Test listing recent releases with network exception."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock network client to raise an exception
        mock_network.get.side_effect = Exception("Network error")

        with pytest.raises(NetworkError):
            manager.list_recent_releases("test/repo")

    def test_list_recent_releases_limit_to_20(self, mocker):
        """Test listing recent releases limits to 20 items."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with more than 20 releases
        mock_response = mocker.Mock()
        mock_response.returncode = 0
        releases_data = [{"tag_name": f"GE-Proton10-{i}"} for i in range(25)]
        mock_response.stdout = json.dumps(releases_data)
        mock_network.get.return_value = mock_response

        result = manager.list_recent_releases("test/repo")

        assert len(result) == 20  # Should be limited to 20
        assert result[0] == "GE-Proton10-0"
        assert result[-1] == "GE-Proton10-19"


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

    @pytest.mark.parametrize(
        "fork_name,expected_ext",
        [
            (ForkName.GE_PROTON, ".tar.gz"),
            (ForkName.PROTON_EM, ".tar.xz"),
        ],
    )
    def test_get_expected_extension_parametrized(self, mocker, fork_name, expected_ext):
        """Parametrized test for _get_expected_extension."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        assert manager._get_expected_extension(fork_name) == expected_ext

    @pytest.mark.parametrize(
        "fork,expected_ext",
        [
            (ForkName.GE_PROTON, ".tar.gz"),
            (ForkName.PROTON_EM, ".tar.xz"),
        ],
    )
    def test_find_matching_assets_parametrized(self, mocker, fork, expected_ext):
        """Parametrized test for _find_matching_assets."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Create assets with different extensions
        all_assets = [
            {"name": "GE-Proton10-20.tar.gz"},
            {"name": "proton-EM-10.0-30.tar.xz"},
            {"name": "other-file.zip"},
        ]

        matching_assets = manager._find_matching_assets(all_assets, expected_ext)

        # Verify that the matching assets have the expected extension
        for asset in matching_assets:
            assert asset["name"].endswith(expected_ext)
