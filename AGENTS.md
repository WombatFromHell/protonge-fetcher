# AGENTS.md

## Overview

Actionable guidelines for agentic tools when working with the ProtonFetcher codebase.

## Architecture

- **Main orchestrator**: `GitHubReleaseFetcher` coordinates operations via dependency injection
- **Specialized managers**: `ReleaseManager`, `AssetDownloader`, `ArchiveExtractor`, `LinkManager`
- **Infrastructure**: Protocol-based design with `NetworkClientProtocol`, `FileSystemClientProtocol`
- **Progress indication**: `Spinner` with FPS limiting and file details

## Workflow Guidelines

### Module Placement
- Common types/protocols: `src/protonfetcher/common.py`
- Exceptions: `src/protonfetcher/exceptions.py`
- Utilities: `src/protonfetcher/utils.py`
- Infrastructure: `src/protonfetcher/network.py`, `filesystem.py`, `spinner.py`
- Core logic: Corresponding specialized modules

### Refactoring Safeguards
- Maintain existing method signatures; extend with optional parameters if needed
- Preserve protocol contracts and dependency injection patterns
- Keep single-responsibility principle intact
- Use established error hierarchy: `ProtonFetcherError` → specific types

### Testing Approach
- Mock protocols for isolated testing
- Parametrize fork tests: `@pytest.mark.parametrize` for GE-Proton/Proton-EM
- Test error scenarios and caching behavior
- Validate link management functionality

## Critical Constraints

- No new dependencies: Use only standard library and system tools (curl, tar)
- Preserve three-tier symlink system (main, fallback, fallback2)
- Maintain backward compatibility
- Support both GE-Proton (.tar.gz) and Proton-EM (.tar.xz) formats

## Development Commands

- `make test` - Run test suite
- `make lint` - Lint and format code
- `make radon` - Check code complexity
- `make quality` - Run quality checks

## Error Handling

Use established hierarchy:
```python
from protonfetcher.exceptions import ProtonFetcherError, NetworkError, ExtractionError, LinkManagementError
```