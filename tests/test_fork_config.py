"""
Unit tests for ForkConfig and related functionality in protonfetcher.py
"""

import pytest

from protonfetcher.common import ForkConfig


class TestForkConfig:
    """Tests for ForkConfig dataclass functionality."""

    def test_fork_config_getitem_repo(self):
        """Test ForkConfig.__getitem__ with 'repo' key."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")
        assert config["repo"] == "test/repo"

    def test_fork_config_getitem_archive_format(self):
        """Test ForkConfig.__getitem__ with 'archive_format' key."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")
        assert config["archive_format"] == ".tar.gz"

    def test_fork_config_getitem_invalid_key_raises_keyerror(self):
        """Test ForkConfig.__getitem__ with invalid key raises KeyError."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")

        with pytest.raises(KeyError):
            _ = config["invalid_key"]
