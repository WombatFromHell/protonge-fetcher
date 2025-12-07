"""
Tests for ReleaseManager cache functionality in protonfetcher.py
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add the project directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from protonfetcher.release_manager import ReleaseManager  # noqa: E402


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

        manager = ReleaseManager(mock_network, mock_fs)
        # Override cache dir for testing
        manager._cache_dir = tmp_path / "cache"

        cache_path = tmp_path / "cache" / "nonexistent"
        assert not manager._is_cache_valid(cache_path)

    def test_is_cache_valid_file_exists_not_expired(self, tmp_path):
        """Test _is_cache_valid returns True for non-expired cache file."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a cache file
        cache_file = manager._cache_dir / "test_cache"
        cache_file.write_text("test content")

        # File should be valid with default max_age (3600 seconds)
        assert manager._is_cache_valid(cache_file)

    def test_is_cache_valid_file_exists_expired(self, tmp_path):
        """Test _is_cache_valid returns False for expired cache file."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a cache file
        cache_file = manager._cache_dir / "test_cache"
        cache_file.write_text("test content")

        # Modify the file's modification time to be in the past
        import os

        old_time = time.time() - 4000  # 4000 seconds ago (more than default 3600)
        os.utime(cache_file, (old_time, old_time))

        # File should be invalid with default max_age (3600 seconds) and short custom max_age
        assert not manager._is_cache_valid(cache_file, max_age=1000)

    def test_get_cached_asset_size_valid_cache(self, tmp_path):
        """Test _get_cached_asset_size returns size from valid cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a cache file with valid data
        cache_key = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        cache_path = manager._get_cache_path(cache_key)

        cache_data = {
            "size": 12345,
            "timestamp": time.time(),
            "repo": "test/repo",
            "tag": "test-tag",
            "asset_name": "test-asset.tar.gz",
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size == 12345

    def test_get_cached_asset_size_invalid_cache(self, tmp_path):
        """Test _get_cached_asset_size returns None for invalid cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a cache file with invalid JSON
        cache_key = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        cache_path = manager._get_cache_path(cache_key)

        with open(cache_path, "w") as f:
            f.write("invalid json")

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size is None

    def test_get_cached_asset_size_expired_cache(self, tmp_path):
        """Test _get_cached_asset_size returns None for expired cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a cache file with valid data but set mtime to be expired
        cache_key = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        cache_path = manager._get_cache_path(cache_key)

        cache_data = {
            "size": 12345,
            "timestamp": time.time(),
            "repo": "test/repo",
            "tag": "test-tag",
            "asset_name": "test-asset.tar.gz",
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Modify the file's modification time to be expired
        import os

        old_time = time.time() - 4000  # 4000 seconds ago
        os.utime(cache_path, (old_time, old_time))

        # Should return None because cache is expired
        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size is None

    def test_get_cached_asset_size_missing_size(self, tmp_path):
        """Test _get_cached_asset_size returns None when size is missing from cache."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a cache file without size field
        cache_key = manager._get_cache_key("test/repo", "test-tag", "test-asset.tar.gz")
        cache_path = manager._get_cache_path(cache_key)

        cache_data = {
            "timestamp": time.time(),
            "repo": "test/repo",
            "tag": "test-tag",
            "asset_name": "test-asset.tar.gz",
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        size = manager._get_cached_asset_size(
            "test/repo", "test-tag", "test-asset.tar.gz"
        )
        assert size is None

    def test_cache_asset_size_success(self, tmp_path):
        """Test _cache_asset_size successfully stores asset size."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        manager = ReleaseManager(mock_network, mock_fs)
        manager._cache_dir = tmp_path / "cache"
        manager._cache_dir.mkdir(parents=True, exist_ok=True)

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
        cache_path = manager._get_cache_path(cache_key)

        assert cache_path.exists()

        with open(cache_path) as f:
            cached_data = json.load(f)

        assert cached_data["size"] == size
        assert cached_data["repo"] == repo
        assert cached_data["tag"] == tag
        assert cached_data["asset_name"] == asset_name
        assert "timestamp" in cached_data

    def test_cache_asset_size_io_error(self, tmp_path, mocker):
        """Test _cache_asset_size handles IO errors gracefully."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

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
