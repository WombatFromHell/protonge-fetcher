"""
Unit tests for FileSystemClient and FileSystemClientProtocol in protonfetcher.py
"""

import tempfile
from pathlib import Path

from protonfetcher.filesystem import FileSystemClient


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


class TestFileSystemClientProtocol:
    """Tests for FileSystemClientProtocol compliance."""

    def test_protocol_compliance(self):
        """Test that FileSystemClient complies with FileSystemClientProtocol."""
        client = FileSystemClient()

        # Test that all required methods exist
        assert hasattr(client, "exists")
        assert hasattr(client, "is_dir")
        assert hasattr(client, "mkdir")
        assert hasattr(client, "write")
        assert hasattr(client, "read")
        assert hasattr(client, "symlink_to")
        assert hasattr(client, "resolve")
        assert hasattr(client, "unlink")
        assert hasattr(client, "rmtree")
