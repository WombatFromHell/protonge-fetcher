# ProtonFetcher Design Specification

## Overview

ProtonFetcher is a Python module designed to fetch and extract ProtonGE GitHub release assets. It supports multiple Proton forks (GE-Proton and Proton-EM) with functionality for downloading, verifying, extracting, and managing symbolic links with progress indication.

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
- `entry.py` - Entry point for distribution

### GitHubReleaseFetcher

Main orchestrator with methods for:

- Complete workflow coordination (`fetch_and_extract`)
- Link management (`list_links`, `remove_release`)
- Release discovery (`list_recent_releases`)
- Environment validation and process flow management

### ReleaseManager

Handles release discovery and asset management:

- Tag fetching with GitHub API redirects
- Asset finding with API and HTML fallbacks
- Asset size caching with XDG-compliant storage
- Recent releases listing

### AssetDownloader

Manages downloads with:

- File size comparison caching
- Progress indication
- Curl-based operations with fallbacks
- Spinner-based progress display

### ArchiveExtractor

Handles archive extraction:

- Format detection and fallback mechanisms
- Tarfile library and system tar support
- Progress indication for both formats
- Archive validation and information retrieval

### LinkManager

Manages symbolic links with intelligent version sorting and optimized link management:

- **Creation with priority ordering**: Creates main, fallback1, and fallback2 symlinks
- **Listing and removal operations**: Comprehensive symlink management
- **Intelligent version sorting**: Proper version parsing for correct symlink targeting
- **Fork-specific link naming**: Handles both GE-Proton and Proton-EM conventions
- **Manual release handling**: Special logic for manually specified releases
- **Intelligent link status checking**: New `are_links_up_to_date()` method prevents unnecessary symlink recreation
- **Performance optimization**: Only updates symlinks when targets change or links are broken
- **Error handling**: Comprehensive error handling for filesystem operations

#### Link Optimization

The LinkManager now includes intelligent link status checking to improve performance:

- **`are_links_up_to_date()` method**: Checks if existing symlinks are already correct
- **Conditional link management**: Only calls `manage_proton_links()` when links need updating
- **Reduced I/O operations**: Avoids unnecessary filesystem operations when links are already correct
- **Better user experience**: Less "noise" in logs when no changes are needed
- **Backward compatibility**: Existing behavior is preserved, only optimized

### CLI Interface

Provides command-line functionality:

- Argument parsing with validation
- Logging configuration
- Operation flow handling (fetch, list, remove, links)
- Fork name conversion and validation

## CLI Interface

### Features and Options

- `--extract-dir`, `-x`: Extract directory (default: `~/.steam/steam/compatibilitytools.d/`)
- `--output`, `-o`: Download directory (default: `~/Downloads/`)
- `--release`, `-r`: Specify release tag instead of latest
- `--fork`, `-f`: Fork to download (GE-Proton, Proton-EM)
- `--list`, `-l`: List recent releases
- `--ls`: List managed symbolic links (default behavior)
- `--rm`: Remove specific release and update links
- `--relink`: Force recreation of symbolic links without downloading or extracting (requires `--fork`)
- `--debug`: Enable debug logging

### Validation and Constraints

- Mutually exclusive flags: `--list`/`--release`, `--ls`/`--rm`
- Path validation and directory permission checks
- Fork name validation using ForkName enum
- Environment validation for required tools (curl)
- Directory writability validation

### Operation Flows

- **Default (`--ls`)**: Lists managed symbolic links and targets
- **List releases (`--list`)**: Fetches and displays recent releases from GitHub API
- **List links (`--ls`)**: Displays managed symbolic links and targets
- **Remove release (`--rm`)**: Removes specified release directory and updates symlinks
- **Relink (`--relink`)**: Forces recreation of symbolic links without downloading or extracting

Default behavior shows current installed versions when no operation flags are provided.

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
```

This provides users with fine-grained control over symlink management while preserving the automatic optimization for normal operations.

## Fork Configuration System

Supports multiple Proton forks with structured configuration:

- `ForkName`: StrEnum with `GE_PROTON` and `PROTON_EM`
- `ForkConfig`: Dataclass with repository and archive format per fork
- `FORKS`: Dictionary mapping ForkName enums to ForkConfig objects
- Archive formats: GE-Proton (`.tar.gz`), Proton-EM (`.tar.xz`)
- Fork-specific symlink naming and version parsing
- Repository-specific asset naming and detection
- Extraction path handling with `proton-` prefix support

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
- **Parametrized Tests**: Fork-specific testing for GE-Proton and Proton-EM scenarios
- **Mock-based Testing**: Protocol-based dependency injection for isolated testing
- **Error Handling Tests**: Exception type testing and error recovery scenarios
- **Coverage Tests**: Integrated into respective module test files

### Test Organization

- **Module-Based Structure**: Tests organized by component being tested
- **Separation of Concerns**: Clear separation between unit, integration, and workflow tests
- **Consistent Naming**: `test_<module_name>.py` pattern
- **Coverage Integration**: Coverage tests integrated into respective module files
- **Fork Parametrization**: Systematic parametrization across both Proton forks

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

- **Standard library**: argparse, dataclasses, hashlib, json, logging, os, re, shutil, subprocess, sys, tarfile, time, urllib, pathlib, enum, typing
- **System dependencies**: curl (network operations), tar (archive extraction)
- **Modern Python 3.11+**: StrEnum, protocols, ExceptionGroup, type hints, match/case
- **XDG caching**: File-based caching with configurable expiration
- **Configurable progress**: FPS-limited progress indication
- **Environment validation**: Tool availability and directory permission checks
- **Protocol-based architecture**: Abstract protocols with documentation and versioning
- **Dual extraction methods**: tarfile library + system tar fallback
- **Intelligent version parsing**: Sophisticated version comparison
- **Symlink management**: Automated creation with fallback chains
- **Network resilience**: GitHub API fallbacks including HTML parsing
- **Asset verification**: Size-based caching to avoid redundant downloads
- **Comprehensive error handling**: Specific exceptions with detailed context
