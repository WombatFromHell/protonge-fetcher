# ProtonFetcher Design Specification

## Overview

ProtonFetcher is a Python module designed to fetch and extract ProtonGE GitHub release assets. It supports multiple Proton forks (GE-Proton, Proton-EM, and CachyOS) with functionality for downloading, verifying, extracting, and managing symbolic links with progress indication.

## Architecture

The module follows a modular design with clear separation of concerns and dependency injection, organized under `src/protonfetcher/`.

### Core Components

- **GitHubReleaseFetcher**: Main orchestrator coordinating workflow, environment validation, and process flow
- **ReleaseManager**: Handles release discovery, GitHub API interactions, asset resolution, and XDG-compliant caching
- **AssetDownloader**: Manages downloads with progress indication and file size comparison caching
- **ArchiveExtractor**: Handles extraction for `.tar.gz` and `.tar.xz` formats with fallback mechanisms
- **LinkManager**: Manages symbolic links with intelligent version sorting and priority ordering

### Protocol-Based Design

The architecture uses Protocol-based dependency injection for easy testing and component substitution:

- **NetworkClientProtocol**: Abstract interface for network operations
- **FileSystemClientProtocol**: Abstract interface for filesystem operations
- **Runtime Validation**: `validate_protocol_instance()` utility for development-time validation
- **Versioning**: Protocol version constants for future compatibility

### Key Features

- **Protocol-based architecture** with comprehensive documentation and versioning
- **XDG-compliant caching** for asset size information
- **Dual extraction methods** (tarfile library + system tar fallback)
- **Intelligent version parsing** for proper Proton release sorting
- **Comprehensive error handling** with specific exception hierarchy
- **Modern Python 3.11+ features**: StrEnum, protocols, ExceptionGroup, type hints

## Core Components

### Module Structure

- `common.py` - Shared types, enums, protocols, and constants
- `exceptions.py` - Custom exception hierarchy
- `utils.py` - Utility functions and protocol validation
- `network.py` - Network client implementation
- `filesystem.py` - File system client implementation
- `spinner.py` - Progress indication with FPS limiting
- `release_manager.py` - Release discovery and asset management
- `asset_downloader.py` - Download operations with caching
- `archive_extractor.py` - Archive extraction with fallbacks
- `link_manager.py` - Symbolic link management with intelligent status checking
- `github_fetcher.py` - Main orchestrator with optimized link management
- `cli.py` - CLI interface and argument parsing
- `entry.py` - Entry point for distribution (located in `src/entry.py`)

### GitHubReleaseFetcher

Main orchestrator with methods for:

- Complete workflow coordination (`fetch_and_extract`)
- Link management (`list_links`, `remove_release`)
- Release discovery (`list_recent_releases`)
- Environment validation and process flow management
- Relink operations (`relink_fork`)

### ReleaseManager

Handles release discovery and asset management:

- Tag fetching with GitHub API redirects
- Asset finding with API and HTML fallbacks
- Asset size caching with XDG-compliant storage
- Recent releases listing
- Cache management with configurable expiration (default: 1 hour)

### AssetDownloader

Manages downloads with:

- File size comparison caching
- Progress indication with spinner
- Urllib-based primary download with curl fallback
- Spinner-based progress display with configurable FPS limiting

### ArchiveExtractor

Handles archive extraction:

- Format detection and fallback mechanisms
- Tarfile library and system tar support
- Progress indication for both formats
- Archive validation and information retrieval
- Support for `.tar.gz`, `.tar.xz`, and generic tar formats

### LinkManager

Manages symbolic links with intelligent version sorting and optimized link management:

- **Creation with priority ordering**: Creates main, fallback1, and fallback2 symlinks
- **Listing and removal operations**: Comprehensive symlink management
- **Intelligent version sorting**: Proper version parsing for correct symlink targeting
- **Fork-specific link naming**: Handles GE-Proton, Proton-EM, and CachyOS conventions
- **Manual release handling**: Special logic for manually specified releases
- **Intelligent link status checking**: `are_links_up_to_date()` method prevents unnecessary symlink recreation
- **Performance optimization**: Only updates symlinks when targets change or links are broken
- **Error handling**: Comprehensive error handling for filesystem operations
- **Directory validation**: Pattern-based validation to exclude non-Proton directories

#### Link Optimization

The LinkManager includes intelligent link status checking to improve performance:

- **`are_links_up_to_date()` method**: Checks if existing symlinks are already correct
- **Conditional link management**: Only calls `manage_proton_links()` when links need updating
- **Reduced I/O operations**: Avoids unnecessary filesystem operations when links are already correct
- **Better user experience**: Less "noise" in logs when no changes are needed
- **Backward compatibility**: Existing behavior is preserved, only optimized

#### Version Parsing

The LinkManager uses fork-specific version parsing:

- **GE-Proton**: `GE-Proton{major}-{minor}` format (e.g., `GE-Proton10-20`)
- **Proton-EM**: `EM-{major}.{minor}-{patch}` format (e.g., `EM-10.0-30`)
- **CachyOS**: `cachyos-{major}.{minor}-{date}-slr` format (e.g., `cachyos-10.0-20260207-slr`)

### CLI Interface

Provides command-line functionality:

- Argument parsing with validation
- Logging configuration
- Operation flow handling (fetch, list, remove, links, relink)
- Fork name conversion and validation

## CLI Interface

### Features and Options

- `--extract-dir`, `-x`: Extract directory (default: `~/.steam/steam/compatibilitytools.d/`)
- `--output`, `-o`: Download directory (default: `~/Downloads/`)
- `--release`, `-r`: Specify release tag instead of latest
- `--fork`, `-f`: Fork to download (GE-Proton, Proton-EM, CachyOS)
- `--list`, `-l`: List recent releases
- `--ls`: List managed symbolic links (default behavior)
- `--rm`: Remove specific release and update links
- `--relink`: Force recreation of symbolic links without downloading or extracting (requires `--fork`)
- `--debug`: Enable debug logging

### Validation and Constraints

- Mutually exclusive flags: `--list`/`--release`, `--ls`/`--release`, `--rm`/`--release`, `--relink`/`--release`
- `--relink` requires explicit `--fork` flag
- Path validation and directory permission checks
- Fork name validation using ForkName enum
- Environment validation for required tools (curl)
- Directory writability validation

### Operation Flows

- **Default (no flags)**: Lists managed symbolic links for all forks
- **List releases (`--list`)**: Fetches and displays recent releases from GitHub API
- **List links (`--ls`)**: Displays managed symbolic links and targets (all forks or specific fork with `--fork`)
- **Remove release (`--rm`)**: Removes specified release directory and updates symlinks
- **Relink (`--relink`)**: Forces recreation of symbolic links without downloading or extracting
- **Fetch and extract (with `--fork` or `--release`)**: Downloads and extracts the specified release

#### Relink Operation

The `--relink` flag provides a way to force recreation of symbolic links when needed:

- **Purpose**: Force recreation of symlinks without downloading or extracting releases
- **Use Case**: When symlinks become corrupted or need to be updated manually
- **Requirements**: Must be used with `--fork` to specify which fork's links to recreate
- **Behavior**: Finds all existing versions for the specified fork and recreates symlinks
- **Mutual Exclusivity**: Cannot be used with `--release`, `--list`, `--ls`, or `--rm`

**Example Usage:**

```bash
# Force relinking of GE-Proton symlinks
protonfetcher --relink --fork GE-Proton

# Force relinking of Proton-EM symlinks
protonfetcher --relink --fork Proton-EM

# Force relinking of CachyOS symlinks
protonfetcher --relink --fork CachyOS
```

This provides users with fine-grained control over symlink management while preserving the automatic optimization for normal operations.

## Fork Configuration System

Supports multiple Proton forks with structured configuration:

### ForkName Enum

- `GE_PROTON = "GE-Proton"`
- `PROTON_EM = "Proton-EM"`
- `CACHYOS = "CachyOS"`

### ForkConfig Dataclass

```python
@dataclasses.dataclass(frozen=True)
class ForkConfig:
    repo: str
    archive_format: str
```

### Forks Dictionary

```python
FORKS: dict[ForkName, ForkConfig] = {
    ForkName.GE_PROTON: ForkConfig(
        repo="GloriousEggroll/proton-ge-custom",
        archive_format=".tar.gz",
    ),
    ForkName.PROTON_EM: ForkConfig(
        repo="Etaash-mathamsetty/Proton",
        archive_format=".tar.xz",
    ),
    ForkName.CACHYOS: ForkConfig(
        repo="CachyOS/proton-cachyos",
        archive_format=".tar.xz",
    ),
}
```

### Archive Formats

- **GE-Proton**: `.tar.gz`
- **Proton-EM**: `.tar.xz`
- **CachyOS**: `.tar.xz`

### Asset Naming Conventions

- **GE-Proton**: `{tag}.tar.gz` (e.g., `GE-Proton10-20.tar.gz`)
- **Proton-EM**: `proton-{tag}.tar.xz` (e.g., `proton-EM-10.0-30.tar.xz`)
- **CachyOS**: `proton-{tag}-x86_64.tar.xz` (e.g., `proton-cachyos-10.0-20260207-slr-x86_64.tar.xz`)

### Extraction Directory Naming

- **GE-Proton**: `{tag}` (e.g., `GE-Proton10-20`)
- **Proton-EM**: `proton-{tag}` (e.g., `proton-EM-10.0-30`)
- **CachyOS**: `proton-{tag}-x86_64` (e.g., `proton-cachyos-10.0-20260207-slr-x86_64`)

### Symlink Naming

- **GE-Proton**: `GE-Proton`, `GE-Proton-Fallback`, `GE-Proton-Fallback2`
- **Proton-EM**: `Proton-EM`, `Proton-EM-Fallback`, `Proton-EM-Fallback2`
- **CachyOS**: `CachyOS`, `CachyOS-Fallback`, `CachyOS-Fallback2`

## Error Handling

Comprehensive error hierarchy with specific exception types:

- `ProtonFetcherError`: Base exception (backward compatible alias: `FetchError`)
- `NetworkError`: Network-related failures (HTTP errors, timeouts, rate limits)
- `ExtractionError`: Archive extraction failures (corrupted archives, disk space, format issues)
- `LinkManagementError`: Link management failures (permissions, broken symlinks, directory access)
- `MultiLinkManagementError`: Batch operation failures using ExceptionGroup

Exceptions include context-specific information, error causes, troubleshooting guidance, and proper exception chaining.

## Testing Approach

The test suite employs multiple testing strategies:

- **Unit Tests**: Component-specific tests for individual methods and classes
- **Integration Tests**: Workflow-oriented tests for component interactions
- **CLI Tests**: Command-line interface functionality and argument parsing validation
- **Quality Tests**: Complexity regression and maintainability checks
- **Parametrized Tests**: Fork-specific testing for GE-Proton, Proton-EM, and CachyOS scenarios
- **Mock-based Testing**: Protocol-based dependency injection for isolated testing
- **Error Handling Tests**: Exception type testing and error recovery scenarios
- **Coverage Tests**: Integrated into respective module test files

### Test Organization

- **Module-Based Structure**: Tests organized by component being tested
- **Separation of Concerns**: Clear separation between unit, integration, and workflow tests
- **Consistent Naming**: `test_<module_name>.py` pattern
- **Coverage Integration**: Coverage tests integrated into respective module files
- **Fork Parametrization**: Systematic parametrization across all three Proton forks

### Complexity Regression Test Thresholds

Code quality thresholds enforced by complexity regression tests:

- **Cyclomatic Complexity**: Max 10 per function, max 5.0 average
- **ABC Metrics**: Max 15 assignments, 10 branches, 10 conditions, 25.0 score
- **Cognitive Complexity**: Max 15 per function
- **Raw Metrics**: Max 3500 LOC, 2500 SLOC per project
- **Maintainability**: Minimum index 15.0
- **Code Duplication**: Max 5 blocks, 100 lines
- **File-Level Complexity**: Max 30 functions, 200 total, 10.0 average per file
- **Dependency Analysis**: Max 20 imports per file

## Dependencies and Features

### Standard Library

- argparse, dataclasses, hashlib, json, logging, os, re, shutil, subprocess, sys, tarfile, time, urllib, pathlib, enum, typing

### System Dependencies

- **curl**: Network operations (HTTP requests, downloads)
- **tar**: Archive extraction fallback mechanism

### Modern Python 3.11+ Features

- StrEnum for fork names
- Protocols for dependency injection
- ExceptionGroup for batch errors
- Type hints throughout codebase
- Match/case statements for fork-specific logic
- Self type for context managers

### Key Features

- **XDG caching**: File-based caching with configurable expiration (default: 1 hour)
- **Configurable progress**: FPS-limited progress indication (default: 10 FPS)
- **Environment validation**: Tool availability and directory permission checks
- **Protocol-based architecture**: Abstract protocols with documentation and versioning
- **Dual extraction methods**: tarfile library + system tar fallback
- **Intelligent version parsing**: Sophisticated version comparison for proper sorting
- **Symlink management**: Automated creation with fallback chains and optimization
- **Network resilience**: GitHub API fallbacks including HTML parsing
- **Asset verification**: Size-based caching to avoid redundant downloads
- **Comprehensive error handling**: Specific exceptions with detailed context
- **Multi-fork support**: GE-Proton, Proton-EM, and CachyOS with fork-specific handling

## Protocol Specifications

### NetworkClientProtocol

Version: 1.0

```python
class NetworkClientProtocol(Protocol):
    timeout: int
    PROTOCOL_VERSION: str = "1.0"

    def get(url: str, headers: Optional[Headers] = None, stream: bool = False) -> ProcessResult: ...
    def head(url: str, headers: Optional[Headers] = None, follow_redirects: bool = False) -> ProcessResult: ...
    def download(url: str, output_path: Path, headers: Optional[Headers] = None) -> ProcessResult: ...
```

### FileSystemClientProtocol

Version: 1.0

```python
class FileSystemClientProtocol(Protocol):
    PROTOCOL_VERSION: str = "1.0"

    def exists(path: Path) -> bool: ...
    def is_dir(path: Path) -> bool: ...
    def is_symlink(path: Path) -> bool: ...
    def mkdir(path: Path, parents: bool = False, exist_ok: bool = False) -> None: ...
    def write(path: Path, data: bytes) -> None: ...
    def read(path: Path) -> bytes: ...
    def size(path: Path) -> int: ...
    def mtime(path: Path) -> float: ...
    def symlink_to(link_path: Path, target_path: Path, target_is_directory: bool = True) -> None: ...
    def resolve(path: Path) -> Path: ...
    def unlink(path: Path) -> None: ...
    def rmtree(path: Path) -> None: ...
    def iterdir(path: Path) -> Iterator[Path]: ...
```

## Type Aliases

The module defines several type aliases for clarity and maintainability:

- `Headers = dict[str, str]`
- `ProcessResult = subprocess.CompletedProcess[str]`
- `AssetInfo = tuple[str, int]` # (name, size)
- `VersionTuple = tuple[str, int, int, int]` # (prefix, major, minor, patch)
- `LinkNamesTuple = tuple[Path, Path, Path]`
- `ReleaseTagsList = list[str]`
- `VersionCandidateList = list[tuple[VersionTuple, Path]]`
- `SymlinkMapping = dict[Path, Path]`
- `DirectoryTuple = tuple[Path, Path | None]`
- `ExistenceCheckResult = tuple[bool, Path | None]`
- `ProcessingResult = tuple[bool, Path | None]`
- `ForkList = list[ForkName]`
- `VersionGroups = dict[VersionTuple, list[Path]]`
- `LinkSpecList = list[SymlinkSpec]`

## Constants

- `DEFAULT_TIMEOUT = 30` (seconds for network operations)
- `GITHUB_URL_PATTERN = r"/releases/tag/([^/?#]+)"` (regex for extracting tags from URLs)
- `DEFAULT_FORK = ForkName.GE_PROTON`

## Cache Management

The ReleaseManager implements XDG-compliant caching:

- **Cache Location**: `$XDG_CACHE_HOME/protonfetcher` or `~/.cache/protonfetcher`
- **Cache Key**: MD5 hash of `{repo}_{tag}_{asset_name}_size`
- **Cache Format**: JSON with size, timestamp, repo, tag, and asset_name
- **Cache Expiration**: 1 hour (3600 seconds)
- **Cache Invalidation**: Automatic based on modification time

## Progress Indication

The Spinner class provides configurable progress indication:

- **Braille Spinner Characters**: Smooth animation with 6 characters
- **FPS Limiting**: Configurable (default: 10 FPS) to prevent excessive terminal updates
- **Progress Bar**: Optional bar display when total is known
- **Rate Calculation**: Shows transfer rate (B/s, KB/s, MB/s, GB/s)
- **Unit Scaling**: Automatic scaling for byte-based units
- **Context Manager Support**: Can be used with `with` statement
- **Iterable Wrapping**: Can wrap iterables for automatic progress tracking

## Directory Validation

The LinkManager implements pattern-based directory validation:

- **GE-Proton Pattern**: `^GE-Proton\d+-\d+$`
- **Proton-EM Patterns**: `^proton-EM-\d+\.\d+-\d+$` or `^EM-\d+\.\d+-\d+$`
- **CachyOS Patterns**: `^proton-cachyos-\d+\.\d+-\d+-slr(-x86_64)?$` or `^cachyos-\d+\.\d+-\d+-slr$`

This prevents non-Proton directories (e.g., "LegacyRuntime") from being included in version candidates.

## Duplicate Handling

The LinkManager handles duplicate versions with different naming conventions:

- Groups candidates by parsed version
- Prefers directories without `proton-` prefix
- Uses directory name length as secondary preference
- Ensures consistent ordering for reproducible results
