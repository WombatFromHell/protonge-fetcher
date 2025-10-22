# ProtonFetcher Design Specification

## Overview

ProtonFetcher is a Python module designed to fetch and extract the latest ProtonGE GitHub release assets. It supports multiple Proton forks (primarily GE-Proton and Proton-EM) and provides functionality to download, verify, and extract these releases with progress indication.

## Architecture

The module follows a modular design with clear separation of concerns:

```text
protonfetcher.py
├── NetworkClient     - Handles all network operations
├── FileSystemClient  - Manages file system operations
├── Spinner           - Provides progress indication
├── GitHubReleaseFetcher - Main orchestrator class
└── Utility Functions - Helper functions for version parsing, etc.
```

## Components

### NetworkClient

Provides a concrete implementation of network operations using subprocess and urllib. It handles all HTTP requests through curl with proper timeout handling, header support, and error checking. The client supports GET requests, HEAD requests, and file downloads with appropriate error handling and response processing.

### FileSystemClient

Provides a concrete implementation of file system operations using standard pathlib operations. It wraps common file system operations like checking existence, creating directories, reading/writing files, creating symbolic links, and removing files or directories. This abstraction allows for easier testing and potential future extensions.

### Spinner

Provides a simple native spinner progress indicator without external dependencies. It displays a customizable spinning character with optional progress bars, file details, and transfer rates. The spinner includes FPS limiting to prevent excessive terminal updates and clean terminal handling to avoid leftover characters. It supports both simple spinning indicators and detailed progress bars with percentage completion.

### GitHubReleaseFetcher

The main orchestrator class that handles fetching and extracting GitHub release assets. It coordinates the network and file system operations to discover releases, identify appropriate assets, download them with progress indication, and extract them to target directories. The fetcher supports multiple Proton forks with different naming conventions and implements intelligent caching to avoid re-downloading files that already exist locally with matching sizes.

### Utility Functions

Helper functions for version parsing, asset naming, and formatting. These include parsing version tags for comparison, comparing version tags across different fork formats, generating expected asset names based on fork conventions, and formatting byte values into human-readable strings.

## Data Flow

1. **Initialization**: Create a GitHubReleaseFetcher with optional custom clients
2. **Tag Discovery**: Fetch the latest release tag for a repository
3. **Asset Identification**: Find the appropriate asset for the tag and fork
4. **Size Verification**: Get the remote asset size for comparison
5. **Download**: Download the asset with progress indication (skipping if local file matches)
6. **Extraction**: Extract the archive with progress indication
7. **Cleanup**: Handle any necessary post-processing

## Link Management System

ProtonFetcher implements a symbolic link management system to provide a consistent and predictable way to access Proton installations, regardless of the specific version directory name. This system creates a set of standardized symbolic links that point to the actual extracted Proton directory.

### Purpose

The link management system serves several key purposes:

- Provides stable, predictable paths for tools and scripts that need to reference the Proton installation
- Abstracts away version-specific directory names (e.g., `GE-Proton9-15`)
- Enables easy switching between Proton versions by updating links
- Supports fallback configurations for compatibility

### Link Structure

For each Proton fork, the system creates a standardized set of symbolic links in the extraction directory:

**For GE-Proton:**

- `GE-Proton` - Primary link to the latest installed version
- `GE-Proton-Fallback` - Secondary link for fallback configurations
- `GE-Proton-Fallback2` - Tertiary link for additional fallback options

**For Proton-EM:**

- `Proton-EM` - Primary link to the latest installed version
- `Proton-EM-Fallback` - Secondary link for fallback configurations
- `Proton-EM-Fallback2` - Tertiary link for additional fallback options

### Link Creation Process

1. **Directory Discovery**: After extracting an archive, the system identifies the actual Proton directory created during extraction. This directory typically has a version-specific name (e.g., `GE-Proton9-15` or `proton-EM-10.0-30`).

2. **Link Target Resolution**: The system resolves the absolute path to the discovered Proton directory to ensure links are absolute and not relative.

3. **Link Management**: The system removes any existing links with the same names to ensure clean updates, then creates new symbolic links pointing to the newly extracted directory.

4. **Validation**: The system validates that the links were created successfully and point to valid directories.

### Link Naming Convention

The link names are determined by the fork type and follow a consistent pattern:

- The primary link uses the fork name (e.g., `GE-Proton`)
- Fallback links append `-Fallback` and `-Fallback2` to the base name
- This convention ensures compatibility across different tools and scripts that expect these specific link names

### Integration with Extraction Process

The link management system is integrated into the extraction workflow:

- Links are created after successful archive extraction
- The system handles both manual and automatic release types
- For manual releases, the system searches for the correct directory within the extracted content
- The system uses the FileSystemClient for all link operations to maintain consistency

### Error Handling

The link management system includes robust error handling:

- Validates that the target directory exists before creating links
- Handles cases where links already exist by removing them first
- Provides clear error messages if link creation fails
- Ensures that the target directory is actually a directory, not a file

### Benefits

This link management system provides several benefits:

- **Consistency**: Tools can always reference `GE-Proton` regardless of the installed version
- **Flexibility**: Easy to update to new versions by simply updating the links
- **Compatibility**: Maintains compatibility with existing tools and scripts
- **Fallback Support**: Multiple links allow for fallback configurations
- **Clean Management**: Old versions can be removed without breaking the links

## Error Handling

The module implements a comprehensive error handling strategy with a custom FetchError exception for all failure cases. It provides detailed error messages with context, implements graceful fallbacks (e.g., from urllib to curl, from tarfile to system tar), includes proper logging at appropriate levels, and validates inputs and preconditions.

For the new `--ls` and `--rm` functionality:
- The `--ls` flag will list all known link names and their targets, showing "(not found)" for links that don't exist
- The `--rm` flag will raise a FetchError if the specified release directory does not exist
- Both flags follow the same error handling patterns as the rest of the module
- The link management system is automatically updated after removal to maintain consistency

## Dependencies

The module has minimal external dependencies, relying primarily on standard library modules including argparse, json, logging, re, shutil, subprocess, tarfile, time, urllib.parse, urllib.request, pathlib, and typing. It requires system dependencies of curl and tar for network operations and extraction. No third-party Python packages are required.

## Configuration

The module supports configuration through constants for default values (timeout, forks, etc.), command-line arguments (via argparse), fork-specific configurations in the FORKS dictionary, and optional client injection for testing and customization.

## Usage Examples

### Basic Usage

Create a fetcher instance, get the latest release tag, find the appropriate asset, download it with progress indication, and extract it to a target directory.

### Using with Custom Clients

Create custom network and file system clients with specific configurations, then use them to initialize a fetcher with those custom clients.

### Using with Proton-EM Fork

Follow the same process as basic usage but specify "Proton-EM" as the fork type to handle the different naming conventions and archive formats used by that fork.

### Using --ls Flag (List Links)

Use the `--ls` flag to list recognized symbolic links and their associated Proton fork folders:

```bash
# List links for ALL managed forks (default behavior)
./protonfetcher --ls

# List links for specific fork only
./protonfetcher --ls -f Proton-EM

# List links with custom extract directory  
./protonfetcher --ls --extract-dir ~/.steam/steam/compatibilitytools.d/
```

This will output the current state of symbolic links in the format:
```
Links for GE-Proton:
  GE-Proton -> /path/to/GE-Proton10-15
  GE-Proton-Fallback -> /path/to/GE-Proton10-12
  GE-Proton-Fallback2 -> (not found)
Success
```

### Using --rm Flag (Remove Release)

Use the `--rm` flag to remove a given Proton fork release folder and its associated links:

```bash
# Remove a specific GE-Proton release
./protonfetcher --rm GE-Proton10-15

# Remove a specific Proton-EM release
./protonfetcher --rm EM-10.0-30 -f Proton-EM

# Remove with custom extract directory
./protonfetcher --rm GE-Proton10-15 --extract-dir ~/.steam/steam/compatibilitytools.d/
```

This will:
1. Remove the specified release folder (e.g., `GE-Proton10-15`)
2. Remove any symbolic links that pointed to this release
3. Regenerate the link management system to maintain consistency
4. Output a success message or error if the directory doesn't exist

### Command-Line Interface Options

Full list of command-line options:

- `--extract-dir`, `-x`: Directory to extract the asset to (default: `~/.steam/steam/compatibilitytools.d/`)
- `--output`, `-o`: Directory to download the asset to (default: `~/Downloads/`)
- `--release`, `-r`: Manually specify a release tag to download instead of the latest
- `--fork`, `-f`: ProtonGE fork to download (default: `GE-Proton`, available: `GE-Proton`, `Proton-EM`)
- `--list`, `-l`: List the 20 most recent release tags for the selected fork
- `--ls`: List recognized symbolic links and their associated Proton fork folders
- `--rm`: Remove a given Proton fork release folder and its associated link
- `--debug`: Enable debug logging

## Future Considerations

Potential enhancements include implementing a more sophisticated caching mechanism for downloaded releases, adding support for parallel downloads of multiple assets, implementing checksum verification for downloaded files, extending support for additional Proton forks, adding support for configuration files to store preferences, providing hooks for GUI integration, implementing support for delta updates to reduce download sizes, and adding functionality to fetch and display release notes.

## Testing Considerations

The design facilitates testing through dependency injection for network and file system clients, modular components that can be tested in isolation, clear interfaces between components, mockable external dependencies (curl, tar), and comprehensive error handling that can be verified. Our design also utilizes the 'pytest' and 'pytest-mock' modules to reduce boilerplate through the user of test parametrization, 'mocker' and 'monkeypatch' utility functions, and a deliberate decision to avoid the use of the 'unittest' module when designing and building out tests. Tests should be categorized and split into separate files based on their position on the testing pyramid: 'test_e2e.py' for end-to-end tests, 'test_integration.py' for integration tests, 'test_unit.py' for unit tests, and 'conftest.py' for fixtures and utility functions used throughout the test suite.

## Security Considerations

Security measures include input validation for all inputs, protection against path traversal attacks in extraction, use of HTTPS for all network requests, size verification of downloaded content, and safe handling of symbolic links during extraction.

## Performance Considerations

Performance optimizations include streaming downloads of large files in chunks with progress indication, use of appropriate extraction methods for different archive formats, intelligent caching to skip re-downloading files that match remote size, FPS limiting for progress indication to prevent excessive terminal updates, and memory management through processing files in chunks to minimize memory usage.
