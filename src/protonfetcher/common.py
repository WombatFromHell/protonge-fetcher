"""Common types, protocols, and constants for ProtonFetcher."""

from __future__ import annotations

import dataclasses
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterator, Optional, Protocol


class ForkName(StrEnum):
    GE_PROTON = "GE-Proton"
    PROTON_EM = "Proton-EM"


# Type aliases for better readability
Headers = dict[str, str]
ProcessResult = subprocess.CompletedProcess[str]
AssetInfo = tuple[str, int]  # (name, size)
VersionTuple = tuple[str, int, int, int]  # (prefix, major, minor, patch)
LinkNamesTuple = tuple[Path, Path, Path]
ReleaseTagsList = list[str]
VersionCandidateList = list[tuple[VersionTuple, Path]]
SymlinkMapping = dict[Path, Path]
DirectoryTuple = tuple[Path, Path | None]
ExistenceCheckResult = tuple[bool, Path | None]
ProcessingResult = tuple[bool, Path | None]
ForkList = list[ForkName]
VersionGroups = dict[VersionTuple, list[Path]]


@dataclasses.dataclass(frozen=True)
class ForkConfig:
    repo: str
    archive_format: str

    def __getitem__(self, key: str) -> str:
        """Allow dict-like access for backward compatibility."""
        if key == "repo":
            return self.repo
        elif key == "archive_format":
            return self.archive_format
        else:
            raise KeyError(key)


@dataclasses.dataclass
class SymlinkSpec:
    link_path: Path
    target_path: Path
    priority: int  # 0 = main, 1 = fallback, 2 = fallback2


# Now that SymlinkSpec is defined, we can define the list type alias
LinkSpecList = list[SymlinkSpec]


@dataclasses.dataclass
class SpinnerConfig:
    iterable: Optional[Iterator[Any]] = None
    total: Optional[int] = None
    desc: str = ""
    unit: Optional[str] = None
    unit_scale: Optional[bool] = None
    disable: bool = False
    fps_limit: Optional[float] = None
    width: int = 10
    show_progress: bool = False  # New parameter to control progress display
    show_file_details: bool = False  # New parameter to control file details display


class NetworkClientProtocol(Protocol):
    timeout: int

    def get(
        self, url: str, headers: Optional[Headers] = None, stream: bool = False
    ) -> ProcessResult: ...
    def head(
        self,
        url: str,
        headers: Optional[Headers] = None,
        follow_redirects: bool = False,
    ) -> ProcessResult: ...
    def download(
        self, url: str, output_path: Path, headers: Optional[Headers] = None
    ) -> ProcessResult: ...


class FileSystemClientProtocol(Protocol):
    def exists(self, path: Path) -> bool: ...
    def is_dir(self, path: Path) -> bool: ...
    def is_symlink(self, path: Path) -> bool: ...
    def mkdir(
        self, path: Path, parents: bool = False, exist_ok: bool = False
    ) -> None: ...
    def write(self, path: Path, data: bytes) -> None: ...
    def read(self, path: Path) -> bytes: ...
    def size(self, path: Path) -> int: ...
    def mtime(self, path: Path) -> float: ...
    def symlink_to(
        self, link_path: Path, target_path: Path, target_is_directory: bool = True
    ) -> None: ...
    def resolve(self, path: Path) -> Path: ...
    def unlink(self, path: Path) -> None: ...
    def rmtree(self, path: Path) -> None: ...
    def iterdir(self, path: Path) -> Iterator[Path]: ...


# Constants
DEFAULT_TIMEOUT = 30
GITHUB_URL_PATTERN = r"/releases/tag/([^/?#]+)"

# Constants for ProtonGE forks
FORKS: dict[ForkName, ForkConfig] = {
    ForkName.GE_PROTON: ForkConfig(
        repo="GloriousEggroll/proton-ge-custom",
        archive_format=".tar.gz",
    ),
    ForkName.PROTON_EM: ForkConfig(
        repo="Etaash-mathamsetty/Proton",
        archive_format=".tar.xz",
    ),
}
DEFAULT_FORK: ForkName = ForkName.GE_PROTON
