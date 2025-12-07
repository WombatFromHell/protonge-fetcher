"""
Tests for ReleaseManager cache functionality in protonfetcher.py
"""

import json
import time
from unittest.mock import MagicMock

from protonfetcher.release_manager import ReleaseManager


class TestReleaseManagerCache:
    """Tests for ReleaseManager cache-related methods."""

    def test_get_cache_key(self):
        """Test _get_cache_key method generates consistent keys."""
        # Create a release manager with mocked clients
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)

        # Test that the same inputs always generate the same key
        key1 = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        key2 = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        assert key1 == key2

        # Test that different inputs generate different keys
        key3 = manager._get_cache_key("other/repo", "test-tag", "test-asset.tar.gz")
        assert key1 != key3

    def test_get_cache_path(self, tmp_path):
        """Test _get_cache_path returns correct path."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        # Override cache dir for testing
        manager._cache_dir = tmp_path / "cache"

        cache_key = "abc123"
        expected_path = tmp_path / "cache" / "abc123"
        actual_path = manager._get_cache_path(cache_key)

        assert actual_path == expected_path

    def test_is_cache_valid_file_not_exists(self, tmp_path):
        """Test _is_cache_valid returns False when cache file doesn't exist."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        # Mock the filesystem client to return False for exists and appropriate values for other methods
        mock_fs.exists.return_value = False

        manager = ReleaseManager(mock_network, mock_fs)
        # Override cache dir for testing
        manager._cache_dir = tmp_path / "cache"

        cache_path = tmp_path / "cache" / "nonexistent"
        assert not manager._is_cache_valid(cache_path)

    def test_is_cache_valid_file_exists_not_expired(self, tmp_path):
        """Test _is_cache_valid returns True for non-expired cache file."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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

    def test_is_cache_valid_file_exists_expired(self, tmp_path):
        """Test _is_cache_valid returns False for expired cache file."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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

    def test_get_cached_asset_size_valid_cache(self, tmp_path):
        """Test _get_cached_asset_size returns size from valid cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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

    def test_get_cached_asset_size_invalid_cache(self, tmp_path):
        """Test _get_cached_asset_size returns None for invalid cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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

    def test_get_cached_asset_size_expired_cache(self, tmp_path):
        """Test _get_cached_asset_size returns None for expired cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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

    def test_get_cached_asset_size_missing_size(self, tmp_path):
        """Test _get_cached_asset_size returns None when size is missing from cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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

    def test_cache_asset_size_success(self, tmp_path):
        """Test _cache_asset_size successfully stores asset size."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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
        mock_network = MagicMock()
        mock_fs = MagicMock()

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
