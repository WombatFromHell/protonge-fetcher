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
    """Protocol for network operations with timeout support.
    
    Implementations must provide HTTP GET, HEAD, and download capabilities
    with configurable timeout behavior. This protocol enables dependency
    injection and easy mocking for testing network operations.
    
    Attributes:
        timeout: Maximum timeout in seconds for network operations
        PROTOCOL_VERSION: Version identifier for protocol compatibility
    """
    timeout: int
    PROTOCOL_VERSION: str = "1.0"

    def get(
        self, url: str, headers: Optional[Headers] = None, stream: bool = False
    ) -> ProcessResult:
        """Perform HTTP GET request.
        
        Args:
            url: URL to request
            headers: Optional request headers as key-value pairs
            stream: Whether to stream the response (default: False)
            
        Returns:
            ProcessResult containing stdout, stderr, and returncode
            
        Raises:
            NetworkError: On network failures, timeouts, or invalid URLs
            
        Example:
            >>> result = network_client.get("https://api.github.com/releases")
            >>> print(result.stdout)
        """
        ...
    
    def head(
        self,
        url: str,
        headers: Optional[Headers] = None,
        follow_redirects: bool = False,
    ) -> ProcessResult:
        """Perform HTTP HEAD request to retrieve headers only.
        
        Args:
            url: URL to request
            headers: Optional request headers as key-value pairs
            follow_redirects: Whether to follow HTTP redirects (default: False)
            
        Returns:
            ProcessResult containing response headers and status
            
        Raises:
            NetworkError: On network failures, timeouts, or invalid URLs
            
        Example:
            >>> result = network_client.head("https://github.com/repo/releases/latest")
            >>> print(result.stdout)  # Contains redirect headers
        """
        ...
    
    def download(
        self, url: str, output_path: Path, headers: Optional[Headers] = None
    ) -> ProcessResult:
        """Download file from URL to specified path.
        
        Args:
            url: URL to download from
            output_path: Destination path for downloaded file
            headers: Optional request headers as key-value pairs
            
        Returns:
            ProcessResult containing download status and any error output
            
        Raises:
            NetworkError: On download failures, network issues, or disk errors
            
        Example:
            >>> result = network_client.download(
                "https://github.com/repo/releases/download/v1.0/app.tar.gz",
                Path("/tmp/app.tar.gz")
            )
        """
        ...


class FileSystemClientProtocol(Protocol):
    """Protocol for filesystem operations.
    
    Provides an abstract interface for filesystem operations to enable
    dependency injection and easy mocking for testing. Implementations
    should handle path operations, file I/O, and directory management.
    
    Note:
        All path operations should use Path objects for cross-platform compatibility.
    
    Attributes:
        PROTOCOL_VERSION: Version identifier for protocol compatibility
    """
    PROTOCOL_VERSION: str = "1.0"
    
    def exists(self, path: Path) -> bool:
        """Check if a file or directory exists at the given path.
        
        Args:
            path: Path to check for existence
            
        Returns:
            True if path exists, False otherwise
            
        Example:
            >>> if file_system.exists(Path("/tmp/file.txt")):
            ...     print("File exists")
        """
        ...
    
    def is_dir(self, path: Path) -> bool:
        """Check if the given path is a directory.
        
        Args:
            path: Path to check
            
        Returns:
            True if path exists and is a directory, False otherwise
            
        Raises:
            LinkManagementError: If path exists but cannot be accessed
            
        Example:
            >>> if file_system.is_dir(Path("/tmp")):
            ...     print("Is a directory")
        """
        ...
    
    def is_symlink(self, path: Path) -> bool:
        """Check if the given path is a symbolic link.
        
        Args:
            path: Path to check
            
        Returns:
            True if path exists and is a symbolic link, False otherwise
            
        Example:
            >>> if file_system.is_symlink(Path("/usr/bin/python")):
            ...     print("Is a symlink")
        """
        ...
    
    def mkdir(
        self, path: Path, parents: bool = False, exist_ok: bool = False
    ) -> None:
        """Create a directory at the specified path.
        
        Args:
            path: Directory path to create
            parents: If True, create parent directories as needed (default: False)
            exist_ok: If True, don't raise error if directory already exists (default: False)
            
        Raises:
            LinkManagementError: If directory cannot be created due to permissions or other issues
            
        Example:
            >>> file_system.mkdir(Path("/tmp/new_dir"), parents=True, exist_ok=True)
        """
        ...
    
    def write(self, path: Path, data: bytes) -> None:
        """Write binary data to a file.
        
        Args:
            path: Destination file path
            data: Binary data to write
            
        Raises:
            LinkManagementError: If file cannot be written due to permissions or disk issues
            
        Example:
            >>> file_system.write(Path("/tmp/test.txt"), b"Hello World")
        """
        ...
    
    def read(self, path: Path) -> bytes:
        """Read binary data from a file.
        
        Args:
            path: File path to read from
            
        Returns:
            Binary content of the file
            
        Raises:
            LinkManagementError: If file cannot be read or doesn't exist
            
        Example:
            >>> content = file_system.read(Path("/tmp/test.txt"))
        """
        ...
    
    def size(self, path: Path) -> int:
        """Get the size of a file in bytes.
        
        Args:
            path: File path to get size for
            
        Returns:
            Size of file in bytes
            
        Raises:
            LinkManagementError: If file doesn't exist or cannot be accessed
            
        Example:
            >>> file_size = file_system.size(Path("/tmp/large_file.tar.gz"))
        """
        ...
    
    def mtime(self, path: Path) -> float:
        """Get the modification time of a file as Unix timestamp.
        
        Args:
            path: File path to get modification time for
            
        Returns:
            Modification time as Unix timestamp (seconds since epoch)
            
        Raises:
            LinkManagementError: If file doesn't exist or cannot be accessed
            
        Example:
            >>> mod_time = file_system.mtime(Path("/tmp/cache_file"))
        """
        ...
    
    def symlink_to(
        self, link_path: Path, target_path: Path, target_is_directory: bool = True
    ) -> None:
        """Create a symbolic link.
        
        Args:
            link_path: Path where the symbolic link will be created
            target_path: Path that the symbolic link will point to
            target_is_directory: Whether the target is a directory (default: True)
            
        Raises:
            LinkManagementError: If symlink cannot be created due to permissions or other issues
            
        Example:
            >>> file_system.symlink_to(
                Path("/usr/local/bin/proton"),
                Path("/home/user/.steam/steam/compatibilitytools.d/GE-Proton")
            )
        """
        ...
    
    def resolve(self, path: Path) -> Path:
        """Resolve symbolic links and return the absolute path.
        
        Args:
            path: Path to resolve (can be relative or contain symlinks)
            
        Returns:
            Absolute path with all symbolic links resolved
            
        Raises:
            LinkManagementError: If path doesn't exist or contains broken symlinks
            
        Example:
            >>> resolved = file_system.resolve(Path("../some/symlink"))
        """
        ...
    
    def unlink(self, path: Path) -> None:
        """Remove a file or symbolic link.
        
        Args:
            path: Path to the file or symlink to remove
            
        Raises:
            LinkManagementError: If path doesn't exist or cannot be removed
            
        Example:
            >>> file_system.unlink(Path("/tmp/old_file.txt"))
        """
        ...
    
    def rmtree(self, path: Path) -> None:
        """Recursively remove a directory and all its contents.
        
        Args:
            path: Directory path to remove
            
        Raises:
            LinkManagementError: If directory doesn't exist or cannot be removed
            
        Example:
            >>> file_system.rmtree(Path("/tmp/old_directory"))
        """
        ...
    
    def iterdir(self, path: Path) -> Iterator[Path]:
        """Iterate over the contents of a directory.
        
        Args:
            path: Directory path to iterate over
            
        Returns:
            Iterator yielding Path objects for directory contents
            
        Raises:
            LinkManagementError: If directory doesn't exist or cannot be accessed
            
        Example:
            >>> for item in file_system.iterdir(Path("/tmp")):
            ...     print(item.name)
        """
        ...


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
