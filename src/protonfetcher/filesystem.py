"""File system client implementation for ProtonFetcher."""

import shutil
from pathlib import Path
from typing import Iterator


class FileSystemClient:
    """Concrete implementation of FileSystemClientProtocol.
    
    Provides filesystem operations using standard pathlib operations.
    Implements all methods defined in FileSystemClientProtocol v1.0.
    """
    
    PROTOCOL_VERSION: str = "1.0"

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def is_symlink(self, path: Path) -> bool:
        return path.is_symlink()

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def write(self, path: Path, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    def read(self, path: Path) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def size(self, path: Path) -> int:
        return path.stat().st_size

    def mtime(self, path: Path) -> float:
        return path.stat().st_mtime

    def symlink_to(
        self, link_path: Path, target_path: Path, target_is_directory: bool = True
    ) -> None:
        link_path.symlink_to(target_path, target_is_directory=target_is_directory)

    def resolve(self, path: Path) -> Path:
        return path.resolve()

    def unlink(self, path: Path) -> None:
        path.unlink()

    def rmtree(self, path: Path) -> None:
        shutil.rmtree(path)

    def iterdir(self, path: Path) -> Iterator[Path]:
        return path.iterdir()
