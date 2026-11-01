"""File system client implementation for ProtonFetcher."""

import shutil
from functools import wraps
from pathlib import Path
from typing import Callable, Iterator

from .utils import friendly_os_error


def _friendly(action: str) -> Callable:
    """Re-raise an OSError from a filesystem op with a plain-English message.

    The exception type is deliberately preserved (FileNotFoundError, EEXIST...):
    symlink handling guards on OSError/FileExistsError, so a new class here
    would turn broken-symlink recovery into a crash.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapped(self, path: Path, *args: object, **kwargs: object) -> object:
            try:
                return fn(self, path, *args, **kwargs)
            except OSError as e:
                raise friendly_os_error(action, path, e) from e

        return wrapped

    return decorator


def _friendly_iter(action: str, path: Path) -> Iterator[Path]:
    """Same translation for iteration, which raises on the first next()."""
    try:
        yield from path.iterdir()
    except OSError as e:
        raise friendly_os_error(action, path, e) from e


class FileSystemClient:
    """Concrete implementation of FileSystemClientProtocol.

    Provides filesystem operations using standard pathlib operations.
    Implements all methods defined in FileSystemClientProtocol v1.0.
    """

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def is_symlink(self, path: Path) -> bool:
        return path.is_symlink()

    @_friendly("create directory")
    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    @_friendly("write")
    def write(self, path: Path, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    @_friendly("read")
    def read(self, path: Path) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    @_friendly("read size of")
    def size(self, path: Path) -> int:
        return path.stat().st_size

    @_friendly("read modification time of")
    def mtime(self, path: Path) -> float:
        return path.stat().st_mtime

    @_friendly("create symlink")
    def symlink_to(
        self, link_path: Path, target_path: Path, target_is_directory: bool = True
    ) -> None:
        link_path.symlink_to(target_path, target_is_directory=target_is_directory)

    @_friendly("resolve")
    def resolve(self, path: Path) -> Path:
        return path.resolve()

    @_friendly("remove")
    def unlink(self, path: Path) -> None:
        path.unlink()

    @_friendly("remove directory")
    def rmtree(self, path: Path) -> None:
        shutil.rmtree(path)

    def iterdir(self, path: Path) -> Iterator[Path]:
        return _friendly_iter("list", path)
