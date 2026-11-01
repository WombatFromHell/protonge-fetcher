"""FileSystemClient error handling against a real filesystem."""

import errno
import os
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.filesystem import FileSystemClient


@pytest.fixture
def fs() -> FileSystemClient:
    return FileSystemClient()


def assert_failure(
    error: OSError, action: str, path: Path, hint: str, expected_errno: int
) -> None:
    """Plain English message, original type's errno, and the path named."""
    assert error.errno == expected_errno
    assert f"Failed to {action} {path}: {hint}" in str(error)


class TestFileSystemClientErrors:
    """Errors must say what failed, on which path, and why."""

    def test_read_missing_file(self, fs: FileSystemClient, tmp_path: Path) -> None:
        missing = tmp_path / "missing.bin"
        with pytest.raises(FileNotFoundError) as exc:
            fs.read(missing)
        assert_failure(exc.value, "read", missing, "does not exist", errno.ENOENT)

    def test_size_missing_file(self, fs: FileSystemClient, tmp_path: Path) -> None:
        missing = tmp_path / "missing.bin"
        with pytest.raises(FileNotFoundError) as exc:
            fs.size(missing)
        assert_failure(
            exc.value, "read size of", missing, "does not exist", errno.ENOENT
        )

    def test_mtime_missing_file(self, fs: FileSystemClient, tmp_path: Path) -> None:
        missing = tmp_path / "missing.bin"
        with pytest.raises(FileNotFoundError) as exc:
            fs.mtime(missing)
        assert_failure(
            exc.value,
            "read modification time of",
            missing,
            "does not exist",
            errno.ENOENT,
        )

    def test_mkdir_over_existing_file(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        path = tmp_path / "file.txt"
        path.write_text("x")
        with pytest.raises(FileExistsError) as exc:
            fs.mkdir(path, parents=True, exist_ok=True)
        assert_failure(
            exc.value, "create directory", path, "already exists", errno.EEXIST
        )

    def test_mkdir_in_unwritable_directory(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores directory permissions")
        ro = tmp_path / "ro"
        ro.mkdir(mode=0o500)
        sub = ro / "sub"
        with pytest.raises(PermissionError) as exc:
            fs.mkdir(sub)
        assert_failure(
            exc.value, "create directory", sub, "permission denied", errno.EACCES
        )

    def test_write_to_unwritable_directory(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores file permissions")
        ro = tmp_path / "ro"
        ro.mkdir(mode=0o500)
        target = ro / "f.bin"
        with pytest.raises(PermissionError) as exc:
            fs.write(target, b"x")
        assert_failure(exc.value, "write", target, "permission denied", errno.EACCES)

    def test_write_reports_disk_full(
        self, fs: FileSystemClient, tmp_path: Path, mocker: Any
    ) -> None:
        target = tmp_path / "f.bin"

        def boom(*args: Any, **kwargs: Any) -> None:
            raise OSError(errno.ENOSPC, "No space left on device", str(target))

        mocker.patch("builtins.open", boom)
        with pytest.raises(OSError) as exc:
            fs.write(target, b"x")
        assert_failure(
            exc.value, "write", target, "no space left on device", errno.ENOSPC
        )

    def test_unlink_missing(self, fs: FileSystemClient, tmp_path: Path) -> None:
        missing = tmp_path / "gone"
        with pytest.raises(FileNotFoundError) as exc:
            fs.unlink(missing)
        assert_failure(exc.value, "remove", missing, "does not exist", errno.ENOENT)

    def test_rmtree_missing(self, fs: FileSystemClient, tmp_path: Path) -> None:
        missing = tmp_path / "gone"
        with pytest.raises(OSError) as exc:
            fs.rmtree(missing)
        assert_failure(
            exc.value, "remove directory", missing, "does not exist", errno.ENOENT
        )

    def test_rmtree_on_file(self, fs: FileSystemClient, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("x")
        with pytest.raises(OSError) as exc:
            fs.rmtree(path)
        assert_failure(
            exc.value, "remove directory", path, "not a directory", errno.ENOTDIR
        )

    def test_symlink_to_existing_path(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        with pytest.raises(FileExistsError) as exc:
            fs.symlink_to(link, target)
        assert_failure(
            exc.value, "create symlink", link, "already exists", errno.EEXIST
        )

    def test_iterdir_missing_directory(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        missing = tmp_path / "gone"
        with pytest.raises(FileNotFoundError) as exc:
            list(fs.iterdir(missing))
        assert_failure(exc.value, "list", missing, "does not exist", errno.ENOENT)

    def test_iterdir_on_file(self, fs: FileSystemClient, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("x")
        with pytest.raises(OSError) as exc:
            list(fs.iterdir(path))
        assert_failure(exc.value, "list", path, "not a directory", errno.ENOTDIR)

    def test_iterdir_lists_directory(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        (tmp_path / "a").mkdir()
        assert list(fs.iterdir(tmp_path)) == [tmp_path / "a"]

    def test_errors_are_still_catchable_as_oserror(
        self, fs: FileSystemClient, tmp_path: Path
    ) -> None:
        """Symlink handling code guards on OSError, so the type must survive."""
        with pytest.raises(OSError):
            fs.unlink(tmp_path / "gone")
