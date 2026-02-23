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
- Dry-run preview (`fetch_and_extract` with `dry_run=True`)
- Multi-fork updates (`update_all_managed_forks`)
- Update checking (`check_for_updates`)

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
- **Managed link detection**: `has_managed_links()` method checks if fork has active symlinks
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
- Operation flow handling (fetch, list, remove, links, relink, dry-run)
- Fork name conversion and validation

## CLI Interface

### Features and Options

- `--extract-dir`, `-x`: Extract directory (default: `~/.steam/steam/compatibilitytools.d/`)
- `--output`, `-o`: Download directory (default: `~/Downloads/`)
- `--release`, `-r`: Specify release tag instead of latest
- `--fork`, `-f`: Fork to download (GE-Proton, Proton-EM, CachyOS). Use `-f` without a value to update all forks with managed links
- `--list`, `-l`: List recent releases
- `--ls`: List managed symbolic links (default behavior)
- `--rm`: Remove specific release and update links
- `--relink`: Force recreation of symbolic links without downloading or extracting (requires `--fork`)
- `--check`, `-c`: Check if newer releases are available for managed forks (script-friendly output, requires `--fork`)
- `--dry-run`, `-n`: Show what would be downloaded/extracted/linked without making any changes
- `--debug`: Enable debug logging

### Validation and Constraints

- Mutually exclusive flags: `--list`/`--release`, `--ls`/`--release`, `--rm`/`--release`, `--relink`/`--release`, `--check`/(`--list`, `--ls`, `--rm`, `--relink`, `--dry-run`), `--dry-run`/(`--list`, `--ls`, `--rm`, `--relink`)
- `--relink` requires explicit `--fork` flag
- Path validation and directory permission checks
- Fork name validation using ForkName enum
- Environment validation for required tools (curl)
- Directory writability validation (skipped in dry-run mode)

### Operation Flows

- **Default (no flags)**: Lists managed symbolic links for all forks
- **List releases (`--list`)**: Fetches and displays recent releases from GitHub API
- **List links (`--ls`)**: Displays managed symbolic links and targets (all forks or specific fork with `--fork`)
- **Remove release (`--rm`)**: Removes specified release directory and updates symlinks
- **Relink (`--relink`)**: Forces recreation of symbolic links without downloading or extracting
- **Fetch and extract (with `--fork` or `--release`)**: Downloads and extracts the specified release
- **Update all managed forks (`-f` without value)**: Updates all forks that have managed symbolic links

#### Multi-Fork Update Mode

The `-f` flag can be used without a value to update all forks that have managed symbolic links:

- **Purpose**: Automatically update all Proton forks that are already in use (have managed symlinks)
- **Use Case**: Keep all installed Proton forks up-to-date with a single command
- **Behavior**:
  - Scans all supported forks (GE-Proton, Proton-EM, CachyOS)
  - For each fork, checks if any managed symlinks exist
  - For forks with managed symlinks, fetches and installs the latest release
  - Skips forks without managed symlinks
- **Output**: Shows which forks were updated and which were skipped

**Example Usage:**

```bash
# Update all forks with managed links
protonfetcher -f

# Update all forks with managed links (long form)
protonfetcher --fork

# Preview which forks would be updated
protonfetcher -f -n
```

**Example Output:**

```
Updating all forks with managed links...
Skipping GE-Proton: no managed links found
Updating Proton-EM: fetching latest release...
Successfully updated Proton-EM
Skipping CachyOS: no managed links found
Successfully updated 1 fork(s)
```

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

#### Dry-Run Operation

The `--dry-run`/`-n` flag provides a way to preview what would be done without making any changes:

- **Purpose**: Show what would be downloaded, extracted, and linked without performing any filesystem modifications
- **Use Case**: Verify which release would be fetched and what symlinks would be created before committing to the operation
- **Behavior**:
  - Resolves the release tag (or uses the specified one)
  - Finds the appropriate asset for the fork
  - Gets the remote asset size for display
  - Logs what would be downloaded, extracted, and linked
  - Makes no filesystem changes (no download, no extraction, no symlink creation)
- **Mutual Exclusivity**: Cannot be used with `--list`, `--ls`, `--rm`, or `--relink` (these are already informational or non-destructive)
- **Output**: Prints "Dry run complete" instead of "Success"

**Example Usage:**

```bash
# Preview what would be downloaded for latest GE-Proton
protonfetcher --fork GE-Proton --dry-run

# Short form
protonfetcher -f GE-Proton -n

# Preview specific release
protonfetcher --fork Proton-EM --release EM-10.0-30 --dry-run
```

**Example Output:**

```
Would download: GE-Proton10-20.tar.gz (123456789 bytes)
  URL: https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton10-20/GE-Proton10-20.tar.gz
  Destination: ~/Downloads/GE-Proton10-20.tar.gz
Would extract to: ~/.steam/steam/compatibilitytools.d/GE-Proton10-20
Would create/update symlinks:
  GE-Proton -> GE-Proton10-20
  GE-Proton-Fallback -> GE-Proton10-19
  GE-Proton-Fallback2 -> GE-Proton10-18
Dry run complete - no changes made
```

This allows users to verify the tool's behavior before making changes to their system.

#### Check Mode Operation

The `--check`/`-c` flag provides a script-friendly way to check for updates:

- **Purpose**: Check if newer ProtonGE releases are available without downloading
- **Use Case**: Timer scripts, automation, update notifications
- **Behavior**:
  - Used alone (`-c`): Check all forks with managed links
  - With `--fork <name>` (`-c -f <name>`): Check specific fork
  - With `-f` without value (`-c -f`): Check all forks with managed links
  - Prints `"New release available for {fork}: {latest_tag}!"` for each available update
  - Prints `"{fork}: up-to-date"` when no updates available
  - Exit code 0 if updates available, 1 if none available
- **Mutual Exclusivity**: Cannot be used with `--list`, `--ls`, `--rm`, `--relink`, or `--dry-run`

**Example Usage:**

```bash
# Check all managed forks (standalone)
protonfetcher --check

# Check all managed forks (short form)
protonfetcher -c

# Check single fork
protonfetcher --fork GE-Proton --check

# Check all managed forks (explicit -f)
protonfetcher -f -c

# In a script
if protonfetcher -c; then
    protonfetcher -f  # Update all managed forks
fi
```

**Example Output:**

```bash
# When updates available:
$ protonfetcher -c
New release available for GE-Proton: GE-Proton10-21!
New release available for Proton-EM: EM-10.0-31!

# When up-to-date (exit code 1):
$ protonfetcher -c
GE-Proton: up-to-date
Proton-EM: up-to-date
CachyOS: up-to-date
$ echo $?
1

# Check specific fork:
$ protonfetcher -f GE-Proton -c
New release available for GE-Proton: GE-Proton10-21!

# Check specific fork (up-to-date):
$ protonfetcher -f GE-Proton -c
GE-Proton: up-to-date
$ echo $?
1
```

This allows automation scripts to efficiently check for updates and trigger downloads only when needed.

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
