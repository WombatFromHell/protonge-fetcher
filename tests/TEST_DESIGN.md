# ProtonFetcher Test Suite Design

## Overview

The ProtonFetcher test suite employs a comprehensive, multi-layered testing strategy designed around the protocol-based architecture. Tests are organized by component and testing level, with heavy use of mocking to ensure fast, reliable, and isolated test execution.

## Test Suite Philosophy

### User-Facing Tests Over Coverage Metrics

**The ProtonFetcher test suite prioritizes meaningful end-to-end and integration tests that verify user-facing functionality over maximizing code coverage percentages.**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Test Priority Pyramid                        │
│                                                                 │
│                         /‾‾‾\                                   │
│                        / E2E \                                  │
│                       / Tests  \     ← Highest priority         │
│                      /──────────\                               │
│                     / Integration \                             │
│                    /    Tests      \    ← High priority         │
│                   /──────────────────\                          │
│                  /    Unit Tests      \   ← As needed           │
│                 /______________________\                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Approach?

| Metric-Focused Testing | User-Focused Testing |
|------------------------|----------------------|
| Tests every getter/setter | Tests complete workflows |
| 100% coverage, 0 confidence | High confidence in critical paths |
| Brittle tests tied to implementation | Resilient tests tied to behavior |
| "Did we test every line?" | "Did we test what users experience?" |
| Mocks everything | Mocks boundaries, tests integration |

### Our Testing Priorities

1. **E2E Workflows** - Test complete user journeys (fetch, extract, link)
2. **Integration Points** - Test component interactions (network + filesystem + extraction)
3. **Error Handling** - Test failure modes users might encounter
4. **Edge Cases** - Test boundary conditions that affect real usage
5. **Unit Logic** - Test complex algorithms (version parsing, deduplication)

### What We Don't Test

```python
# ❌ Don't test trivial getters/setters
def test_fork_name_enum():
    assert ForkName.GE_PROTON.value == "GE-Proton"  # Waste of time

# ❌ Don't test Python builtins
def test_path_concatenation():
    assert Path("/a") / "b" == Path("/a/b")  # Python's job to test

# ❌ Don't test protocol definitions
def test_protocol_has_method():
    assert hasattr(NetworkClientProtocol, "get")  # Already enforced by type checker
```

### Coverage as a Side Effect

Good E2E and integration tests naturally achieve high coverage:

```
User clicks "fetch latest GE-Proton"
    ↓
CLI parses arguments              ← cli.py covered
    ↓
GitHubReleaseFetcher.orchestrate() ← github_fetcher.py covered
    ↓
ReleaseManager.find_asset()       ← release_manager.py covered
    ↓
AssetDownloader.download()        ← asset_downloader.py covered
    ↓
ArchiveExtractor.extract()        ← archive_extractor.py covered
    ↓
LinkManager.manage_proton_links() ← link_manager.py covered
    ↓
Symlinks created                  ← User's goal achieved ✓
```

**One E2E test = Coverage of 6+ modules + verification they work together**

### Coverage Guidelines

| Coverage Range | Action |
|----------------|--------|
| 80-100% | Excellent - focus on test quality, not increasing number |
| 60-80% | Good - review missing critical paths |
| Below 60% | Add E2E tests for missing workflows |

**Never add tests solely to increase coverage percentage.** Add tests to:
- Verify user-facing behavior
- Prevent regression of bugs
- Document expected behavior
- Test error conditions users might hit

### Test Quality Indicators

**High Quality Tests:**
- ✅ Test would pass even if internal implementation changed
- ✅ Test fails when user-facing behavior breaks
- ✅ Test documents expected behavior clearly
- ✅ Test covers realistic scenarios

**Low Quality Tests:**
- ❌ Test verifies internal method call counts
- ❌ Test breaks when refactoring (same behavior, different code)
- ❌ Test only exists to cover an `if` branch
- ❌ Test mocks the class it's testing

### The Coverage Tool is a Lie Detector

Use coverage reports to find **untested user paths**, not to chase percentages:

```bash
# Run tests with coverage
uv run pytest --cov=protonfetcher --cov-report=term-missing

# Look at uncovered lines and ask:
# "Is this a user-facing path that needs testing?"
# NOT "How do I get this line covered?"
```

**Example:** If `except IOError` branch shows uncovered:
- **Wrong response:** Add test that forces IOError just to cover line
- **Right response:** Ask "Can users hit this error?" → If yes, add realistic test

## Test Organization

### Directory Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_cli_e2e.py          # CLI interface tests
├── test_extraction_workflow_e2e.py  # Archive extraction tests
├── test_github_fetcher_e2e.py       # Main orchestrator tests
├── test_link_manager_e2e.py         # Symlink management tests
├── test_network_integration.py      # Network client integration tests
├── test_release_manager_e2e.py      # Release discovery tests
├── test_spinner_integration.py      # Progress indication tests
└── TEST_DESIGN.md           # This document
```

### Test Categories

| Category | Purpose | Files |
|----------|---------|-------|
| **Unit Tests** | Component-specific method testing | Embedded in e2e files |
| **Integration Tests** | Component interaction testing | `test_network_integration.py` |
| **End-to-End Tests** | Complete workflow testing | `test_*_e2e.py` files |
| **CLI Tests** | Command-line interface testing | `test_cli_e2e.py` |

## Core Testing Principles

### 1. Protocol-Based Mocking

The test suite leverages the protocol-based architecture for dependency injection:

```python
from protonfetcher.common import NetworkClientProtocol, FileSystemClientProtocol

# Mock the protocol, not the implementation
mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
```

**Benefits:**
- Tests are decoupled from implementation details
- Easy to swap real/fake implementations
- Clear interface contracts

### 2. Comprehensive Mocking Strategy

Tests mock external dependencies to ensure reliability:

| Dependency | Mock Approach | Fixture |
|------------|---------------|---------|
| Filesystem | `FileSystemClientProtocol` mock | `mock_filesystem_client` |
| Network | `NetworkClientProtocol` mock | `mock_network_client` |
| tarfile | `tarfile.open` patch | `mock_tarfile_operations` |
| urllib | `urllib.request.urlopen` patch | `mock_urllib_download` |
| subprocess | `subprocess.run` patch | `mock_subprocess_tar` |
| builtins.open | `builtins.open` patch | `mock_builtin_open` |

### 3. No Real I/O in Tests

All tests avoid real file I/O, network calls, and system operations:

```python
# ❌ Avoid: Real file creation
Path("/tmp/test.txt").write_text("data")

# ✅ Prefer: Mocked filesystem
mock_filesystem_client.write.assert_called_with(expected_path, expected_data)
```

## Golden Rules

The ProtonFetcher test suite follows three fundamental rules. All contributors must adhere to these principles.

### Rule 1: Do Not Mock the SUT (System Under Test)

**Never mock the class or function you are testing.** Only mock its dependencies.

```python
# ❌ WRONG: Mocking the SUT
def test_fetcher(mock_github_fetcher: Any):  # Don't do this
    mock_github_fetcher.fetch_and_extract.return_value = Path("/mock/result")
    # This tests nothing - you're testing your mock, not the code

# ✅ CORRECT: Mock dependencies, instantiate real SUT
def test_fetcher(mock_network_client: Any, mock_filesystem_client: Any):
    fetcher = GitHubReleaseFetcher(  # Real SUT
        network_client=mock_network_client,
        file_system_client=mock_filesystem_client,
    )
    result = fetcher.fetch_and_extract(...)  # Real method call
    assert result == expected_path  # Verify real behavior
```

**Rationale:** Mocking the SUT means you're not testing actual code - you're testing your mock configuration. The SUT should be real; its dependencies should be mocked.

**When to break this rule:** Only when testing at a higher integration level where the "SUT" is a complete workflow and you're verifying component interaction.

### Rule 2: Leverage pytest/pytest-mock Features Fully

**Use pytest's built-in features before writing custom test logic.** This includes parametrization, fixtures, markers, and built-in assertions.

```python
# ❌ WRONG: Manual test repetition
def test_ge_proton():
    test_fork(ForkName.GE_PROTON)

def test_proton_em():
    test_fork(ForkName.PROTON_EM)

def test_cachyos():
    test_fork(ForkName.CACHYOS)

# ✅ CORRECT: Use pytest.mark.parametrize
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_all_forks(fork: ForkName, ...):
    test_fork(fork)
```

```python
# ❌ WRONG: Custom fixture when pytest-mock provides it
@pytest.fixture
def mocker():
    from unittest.mock import MagicMock
    return MagicMock()

# ✅ CORRECT: Use pytest-mock's mocker fixture
def test_with_mock(mocker: Any):
    mock = mocker.MagicMock()  # Rich mocker API available
```

**Key pytest/pytest-mock features to use:**

| Feature | Use Case | Example |
|---------|----------|---------|
| `@pytest.mark.parametrize` | Run same test with different inputs | Testing all forks |
| `@pytest.fixture` | Shared setup/teardown | `mock_network_client` |
| `tmp_path` | Temporary file paths | `tmp_path / "test.txt"` |
| `capsys` | Capture stdout/stderr | CLI output testing |
| `caplog` | Capture log messages | Logging verification |
| `mocker.patch` | Patch objects | `mocker.patch("tarfile.open")` |
| `mocker.spy` | Spy on real methods | Verify method calls without mocking |
| `pytest.raises` | Exception testing | `with pytest.raises(NetworkError)` |

**Centralize fixtures in `conftest.py`:**

```python
# ❌ WRONG: Duplicate fixtures in test files
# tests/test_a.py
@pytest.fixture
def mock_network_client(mocker): ...

# tests/test_b.py
@pytest.fixture
def mock_network_client(mocker): ...  # Duplicate!

# ✅ CORRECT: Single source of truth
# conftest.py
@pytest.fixture
def mock_network_client(mocker): ...  # Available to all tests
```

### Rule 3: Don't Repeat Yourself (DRY)

**Never write overlapping or redundant tests.** Each test should verify exactly one behavior or scenario.

```python
# ❌ WRONG: Overlapping tests
def test_symlink_created():
    # Creates symlink, verifies it exists
    ...

def test_symlink_points_to_correct_target():
    # Creates same symlink, verifies target
    ...

def test_symlink_workflow():
    # Creates same symlink, verifies everything
    ...

# ✅ CORRECT: Single responsibility per test
def test_symlink_creation_creates_link():
    # Only verify symlink is created
    ...

def test_symlink_creation_correct_target():
    # Only verify target is correct
    ...

def test_symlink_creation_priority_order():
    # Only verify priority ordering with multiple versions
    ...
```

**Test organization by scenario, not by method:**

```python
# ❌ WRONG: One test per method
def test_manage_proton_links():
    # Tests everything: creation, ordering, updates, edge cases
    ...

# ✅ CORRECT: One test per scenario
class TestManageProtonLinks:
    def test_creates_all_three_symlinks(self): ...
    def test_orders_by_version_newest_first(self): ...
    def test_skips_existing_correct_symlinks(self): ...
    def test_handles_missing_target_directory(self): ...
```

**Use helper functions for shared setup, not for shared assertions:**

```python
# ❌ WRONG: Shared assertion logic
def assert_symlinks_correct(result, expected):
    assert result.symlink_count == expected.count
    assert result.targets == expected.targets

def test_case_1():
    assert_symlinks_correct(result1, expected1)

def test_case_2():
    assert_symlinks_correct(result2, expected2)

# ✅ CORRECT: Shared setup, explicit assertions
@pytest.fixture
def symlink_environment(tmp_path):
    # Shared setup
    ...

def test_case_1(symlink_environment):
    # Explicit, readable assertions
    assert symlink_environment["symlinks"]["main"].exists()
    assert symlink_environment["symlinks"]["main"].resolve() == expected_target
```

**Signs of DRY violations:**

1. **Copy-paste tests** - Same test with different data → Use `@pytest.mark.parametrize`
2. **Multiple assertions on same object** - Test verifies too much → Split into separate tests
3. **Helper assertion functions** - Hides test intent → Make assertions explicit
4. **Duplicate fixtures** - Same fixture in multiple files → Move to `conftest.py`
5. **Overlapping test coverage** - Multiple tests verify same behavior → Consolidate or clarify scope

## Fixture Guide

### Centralized Test Data

The `test_data` fixture provides fork-specific configurations and patterns:

```python
@pytest.fixture
def test_data() -> dict[str, Any]:
    """
    Centralized test data for all test scenarios.
    
    Usage:
        def test_fork_config(test_data: dict[str, Any], fork: ForkName):
            repo = test_data["FORKS"][fork]["repo"]
            assert repo == "GloriousEggroll/proton-ge-custom"
    """
    return {
        "FORKS": {
            ForkName.GE_PROTON: {
                "repo": "GloriousEggroll/proton-ge-custom",
                "example_tag": "GE-Proton10-20",
                "example_asset": "GE-Proton10-20.tar.gz",
                "link_names": ("GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"),
            },
            ForkName.PROTON_EM: {
                "repo": "Etaash-mathamsetty/Proton",
                "example_tag": "EM-10.0-30",
                "example_asset": "proton-EM-10.0-30.tar.xz",
                "link_names": ("Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"),
            },
            ForkName.CACHYOS: {
                "repo": "CachyOS/proton-cachyos",
                "example_tag": "cachyos-10.0-20260207-slr",
                "example_asset": "proton-cachyos-10.0-20260207-slr-x86_64.tar.xz",
                "link_names": ("CachyOS", "CachyOS-Fallback", "CachyOS-Fallback2"),
            },
        },
        "CLI_OUTPUTS": {
            "success": "Success",
            "error_prefix": "Error:",
        },
        "GITHUB_API": {
            "rate_limit_message": "API rate limit exceeded",
            "not_found": "404",
        },
    }
```

**Usage Examples:**

```python
# Use test_data to avoid hardcoding strings
def test_fork_configuration(test_data: dict[str, Any], fork: ForkName):
    repo = test_data["FORKS"][fork]["repo"]
    expected_tag = test_data["FORKS"][fork]["example_tag"]
    assert repo in expected_tag.lower() or expected_tag in repo

# Combine with parametrized fork fixture for comprehensive testing
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_all_forks_config(test_data, fork):
    fork_config = test_data["FORKS"][fork]
    assert "repo" in fork_config
    assert "example_tag" in fork_config
```

### Network Mocks

#### Basic Network Mock

```python
@pytest.fixture
def mock_network_client(mocker: Any) -> Any:
    """Create a realistic mock of NetworkClientProtocol."""
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.timeout = DEFAULT_TIMEOUT
    
    # Configure default responses
    mock_network.get.return_value = subprocess.CompletedProcess(...)
    return mock_network
```

**Usage:**
```python
def test_api_call(mock_network_client: Any, mock_filesystem_client: Any):
    fetcher = GitHubReleaseFetcher(
        network_client=mock_network_client,
        file_system_client=mock_filesystem_client,
    )
    # Test uses mocked network
```

#### Specialized Network Mocks

```python
# GitHub redirect simulation
mock_network_with_github_redirect

# Rate limit simulation
mock_network_with_rate_limit

# 404 error simulation
mock_network_with_404

# Custom API response
mock_network_with_api_response
```

### Filesystem Mocks

#### Basic Filesystem Mock

```python
@pytest.fixture
def mock_filesystem_client(mocker: Any) -> Any:
    """Create a realistic mock of FileSystemClientProtocol."""
    mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
    mock_fs.PROTOCOL_VERSION = "1.0"
    
    # Configure default behavior
    mock_fs.exists.return_value = True
    mock_fs.read.return_value = b"test content"
    return mock_fs
```

**Usage:**
```python
def test_file_read(mock_filesystem_client: Any):
    mock_filesystem_client.exists.return_value = True
    mock_filesystem_client.read.return_value = b"version data"
    
    # Test code
    content = mock_filesystem_client.read(Path("/mock/path"))
    assert content == b"version data"
```

#### Temporary Directory Filesystem

```python
@pytest.fixture
def mock_filesystem_with_directory_structure(mocker: Any, tmp_path: Path) -> Any:
    """Mock filesystem that delegates to real tmp_path operations."""
    mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
    
    # Delegate to real tmp_path
    mock_fs.exists.side_effect = lambda p: p.exists()
    mock_fs.write.side_effect = lambda p, d: p.write_bytes(d)
    
    return mock_fs
```

### Archive Mocks

#### Tarfile Operations Mock

```python
@pytest.fixture
def mock_tarfile_operations(mocker: Any) -> Any:
    """Factory for mocking tarfile operations."""
    
    def _setup_tarfile_mock(
        members: list[dict[str, Any]] | None = None,
        raise_on_open: Exception | None = None,
    ) -> dict[str, Any]:
        mock_tarfile = mocker.patch("tarfile.open")
        # ... setup logic
        return {"tarfile_mock": mock_tarfile, "tar_mock": mock_tar}
    
    return _setup_tarfile_mock
```

**Usage:**
```python
def test_extraction(mock_tarfile_operations: Any):
    # Configure tarfile mock with members
    mocks = mock_tarfile_operations(
        members=[
            {"name": "GE-Proton10-20", "is_dir": True, "size": 0},
            {"name": "GE-Proton10-20/version", "is_dir": False, "size": 14},
        ]
    )
    
    # Test extraction
    extractor.extract_archive(archive_path, target_dir)
    
    # Verify tarfile was used
    assert mocks["tarfile_mock"].called
```

#### Sample Archive Fixtures

```python
@pytest.fixture
def sample_tar_gz_archive(tmp_path: Path) -> Path:
    """Create a real .tar.gz archive for integration tests."""
    # Creates actual archive file in tmp_path
    ...
    return archive_path
```

### Download Mocks

#### Urllib Download Mock

```python
@pytest.fixture
def mock_urllib_download(mocker: Any) -> Any:
    """Factory for mocking urllib download operations."""
    
    def _setup_urllib_mock(
        chunks: list[bytes] | None = None,
        content_length: int | None = None,
        raise_on_open: Exception | None = None,
    ) -> Any:
        mock_urllib = mocker.patch("urllib.request.urlopen")
        # ... setup logic
        return mock_resp_obj
    
    return _setup_urllib_mock
```

**Usage:**
```python
def test_download(mock_urllib_download: Any, mock_builtin_open: Any):
    # Configure download mock
    mock_urllib_download(
        chunks=[b"chunk1", b"chunk2", b""],
        content_length=1048576,
    )
    
    # Capture writes
    _, written_data = mock_builtin_open()
    
    # Test download
    downloader.download_with_spinner(url, output_path)
    
    # Verify data was written
    assert b"".join(written_data) == b"chunk1chunk2"
```

#### Built-in Open Mock

```python
@pytest.fixture
def mock_builtin_open(mocker: Any) -> Any:
    """Mock built-in open() to capture writes without real files."""
    
    def _setup_builtin_open() -> tuple[Any, list[bytes]]:
        written_data: list[bytes] = []
        mock_file = mocker.MagicMock()
        
        def capture_write(data: bytes) -> None:
            written_data.append(data)
        
        mock_file.write.side_effect = capture_write
        # ... setup
        return mock_file, written_data
    
    return _setup_builtin_open
```

### Directory Structure Fixtures

#### Temporary Environment

```python
@pytest.fixture
def temp_environment(tmp_path: Path) -> dict[str, Path]:
    """Create temporary directories for testing workflows."""
    output_dir = tmp_path / "Downloads"
    extract_dir = tmp_path / "compatibilitytools.d"
    output_dir.mkdir(parents=True)
    extract_dir.mkdir(parents=True)
    
    return {
        "tmp": tmp_path,
        "output_dir": output_dir,
        "extract_dir": extract_dir,
    }
```

#### Installed Proton Versions

```python
@pytest.fixture
def installed_proton_versions(tmp_path: Path, fork: ForkName) -> list[Path]:
    """Create fake installed Proton directories."""
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    versions = []
    for version_name in ["GE-Proton10-20", "GE-Proton10-19", ...]:
        version_dir = extract_dir / version_name
        version_dir.mkdir()
        (version_dir / "version").write_text(version_name)
        versions.append(version_dir)
    
    return versions
```

#### Symlink Environment

```python
@pytest.fixture
def symlink_environment(tmp_path: Path, fork: ForkName) -> dict[str, Any]:
    """Create complete symlink testing environment."""
    # Creates version directories and symlinks
    return {
        "extract_dir": extract_dir,
        "version_dirs": version_dirs,
        "symlinks": symlinks,
        "link_names": link_names,
        "fork": fork,
    }
```

### Parametrized Fork Fixtures

The test suite uses parametrized fixtures to ensure comprehensive fork coverage:

```python
# Base parametrized fixture - runs test for each fork
@pytest.fixture(params=[ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def fork(request: pytest.FixtureRequest) -> ForkName:
    """Parametrized fixture for testing all forks."""
    return request.param

# Derived fixtures that depend on `fork`
@pytest.fixture
def fork_repo(fork: ForkName) -> str:
    """
    Get repository name for a given fork.
    
    Usage:
        @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
        def test_repo_config(fork, fork_repo):
            # fork_repo automatically matches the fork parameter
            assert "proton" in fork_repo.lower()
    """
    from protonfetcher.common import FORKS
    return FORKS[fork].repo

@pytest.fixture
def fork_archive_format(fork: ForkName) -> str:
    """Get archive format for a given fork (.tar.gz or .tar.xz)."""
    from protonfetcher.common import FORKS
    return FORKS[fork].archive_format

@pytest.fixture
def fork_link_names(fork: ForkName, extract_dir: Path) -> tuple[Path, Path, Path]:
    """
    Get symlink paths for a given fork.
    
    Returns: (main_link, fallback1, fallback2)
    """
    from protonfetcher.filesystem import FileSystemClient
    from protonfetcher.link_manager import LinkManager
    
    fs = FileSystemClient()
    lm = LinkManager(fs)
    return lm.get_link_names_for_fork(extract_dir, fork)
```

**Best Practices:**

```python
# ✅ CORRECT: Use parametrized fixture for comprehensive testing
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_all_forks(fork: ForkName, fork_repo: str, test_data: dict):
    # Test runs 3 times, once per fork
    expected_repo = test_data["FORKS"][fork]["repo"]
    assert fork_repo == expected_repo

# ✅ CORRECT: Combine with other fixtures
def test_fork_specific_behavior(fork: ForkName, symlink_environment: dict):
    # symlink_environment automatically configured for the fork
    extract_dir = symlink_environment["extract_dir"]
    tag = symlink_environment["version_dirs"][0].name
    
    # Test uses fork-specific setup
    link_manager.manage_proton_links(extract_dir, tag, fork)

# ❌ WRONG: Hardcoding fork values when parametrization available
def test_ge_proton_only():
    fork = ForkName.GE_PROTON  # Misses Proton-EM and CachyOS
    test_fork(fork)
```

**Important:** Fixtures like `symlink_environment` and `installed_proton_versions` require the `fork` parameter and should be used with the parametrized `fork` fixture:

```python
# ✅ CORRECT: fork parameter comes from parametrized fixture
def test_with_symlinks(symlink_environment: dict):
    fork = symlink_environment["fork"]  # GE-Proton, Proton-EM, or CachyOS
    tag = symlink_environment["version_dirs"][0].name

# ❌ WRONG: Don't hardcode fork when using these fixtures
def test_with_symlinks():
    # This will fail - symlink_environment needs fork parameter
    pass
```

### Mock Data Factories

Factory fixtures provide reusable test data with optional parametrization:

```python
# release_assets - Factory for GitHub release assets
@pytest.fixture
def release_assets(request: pytest.FixtureRequest) -> list[dict[str, Any]]:
    """
    Factory for creating GitHub release assets.
    
    Usage:
        # Default assets
        def test_with_defaults(release_assets):
            assert len(release_assets) > 0
        
        # Custom assets with indirect parametrization
        @pytest.mark.parametrize(
            "release_assets",
            [[{"name": "custom.tar.gz", "size": 1024}]],
            indirect=True,
        )
        def test_with_custom_assets(release_assets):
            assert release_assets[0]["name"] == "custom.tar.gz"
    """

# github_release_response - Factory for API responses
@pytest.fixture
def github_release_response(request: pytest.FixtureRequest) -> dict[str, Any]:
    """
    Factory for GitHub API release responses.
    
    Usage:
        @pytest.mark.parametrize(
            "github_release_response",
            [{"tag_name": "custom-tag"}],
            indirect=True,
        )
        def test_custom_response(github_release_response):
            assert github_release_response["tag_name"] == "custom-tag"
    """

# recent_releases - Factory for release tag lists
@pytest.fixture
def recent_releases(request: pytest.FixtureRequest) -> list[str]:
    """
    Factory for recent release tags.
    
    Usage:
        @pytest.mark.parametrize(
            "recent_releases",
            [["release-1", "release-2"]],
            indirect=True,
        )
        def test_custom_releases(recent_releases):
            assert recent_releases[0] == "release-1"
    """
```

**Specialized Network Mocks:**

```python
# Pre-configured network mocks for common scenarios
mock_network_with_github_redirect  # Simulates /releases/latest redirect
mock_network_with_rate_limit       # Simulates API rate limit error
mock_network_with_404              # Simulates 404 Not Found
mock_network_with_api_response     # Custom API response (uses release_assets)
```

**Usage Examples:**

```python
# Use factory fixture with indirect parametrization
@pytest.mark.parametrize(
    "release_assets",
    [
        [{"name": "GE-Proton10-20.tar.gz", "size": 1048576}],
        [{"name": "proton-EM-10.0-30.tar.xz", "size": 2097152}],
    ],
    indirect=True,
)
def test_asset_processing(release_assets, mock_network_with_api_response):
    # mock_network_with_api_response configured with release_assets
    release_manager = ReleaseManager(mock_network_with_api_response, mock_fs)
    # Test uses the parametrized assets

# Use specialized network mock for error scenarios
def test_rate_limit_handling(mock_network_with_rate_limit, mock_filesystem_client):
    release_manager = ReleaseManager(mock_network_with_rate_limit, mock_filesystem_client)
    
    with pytest.raises(NetworkError, match="rate limit"):
        release_manager.list_recent_releases(repo="...")
```

### Component Fixtures (SUT Factories)

```python
@pytest.fixture
def release_manager(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """Create ReleaseManager with mocked dependencies."""
    from protonfetcher.release_manager import ReleaseManager
    return ReleaseManager(mock_network_client, mock_filesystem_client, DEFAULT_TIMEOUT)

@pytest.fixture
def github_fetcher(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """Create GitHubReleaseFetcher with mocked dependencies."""
    from protonfetcher.github_fetcher import GitHubReleaseFetcher
    return GitHubReleaseFetcher(
        network_client=mock_network_client,
        file_system_client=mock_filesystem_client,
    )
```

## Test Patterns

### Pattern 1: Complete Workflow Test

```python
def test_fetch_and_extract_complete_workflow(
    self,
    mocker: Any,
    mock_network_client: Any,
    mock_filesystem_client: Any,
    mock_tarfile_operations: Any,
    mock_urllib_download: Any,
    mock_builtin_open: Any,
) -> None:
    """Test complete download and extraction workflow."""
    # 1. Arrange: Configure all mocks
    mock_filesystem_client.exists.side_effect = lambda p: p in expected_paths
    mock_network_client.get.return_value = subprocess.CompletedProcess(...)
    mock_tarfile_operations(members=[...])
    mock_urllib_download(chunks=[b"data", b""])
    
    # 2. Act: Execute workflow
    result = fetcher.fetch_and_extract(...)
    
    # 3. Assert: Verify results and mock interactions
    assert result == expected_path
    mock_filesystem_client.symlink_to.assert_called()
```

### Pattern 2: Error Handling Test

```python
def test_network_error_handling(
    self,
    mock_network_client: Any,
    mock_filesystem_client: Any,
) -> None:
    """Test handling of network errors."""
    # Arrange: Configure error response
    mock_network_client.get.return_value = subprocess.CompletedProcess(
        returncode=22, stderr="404 Not Found"
    )
    
    # Act & Assert: Verify exception raised
    with pytest.raises(NetworkError, match="404"):
        fetcher.fetch_and_extract(...)
```

### Pattern 3: Parametrized Fork Test

```python
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_fork_specific_behavior(
    self,
    fork: ForkName,
    mock_filesystem_client: Any,
    fork_repo: str,
) -> None:
    """Test behavior across all forks."""
    # Arrange
    mock_filesystem_client.exists.return_value = True
    
    # Act
    result = link_manager.find_tag_directory(extract_dir, tag, fork)
    
    # Assert
    assert result is not None
```

### Pattern 4: Integration Test with Real Components

```python
def test_link_manager_with_real_filesystem(
    self,
    tmp_path: Path,
) -> None:
    """Test LinkManager with real filesystem."""
    # Arrange: Use real filesystem in tmp_path
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    
    # Create real directories
    (extract_dir / "GE-Proton10-20").mkdir()
    
    # Use real FileSystemClient
    fs = FileSystemClient()
    link_manager = LinkManager(fs)
    
    # Act
    link_manager.manage_proton_links(extract_dir, "GE-Proton10-20", ForkName.GE_PROTON)
    
    # Assert: Verify real symlinks created
    assert (extract_dir / "GE-Proton").is_symlink()
```

### Pattern 5: CLI Test with Argument Parsing

```python
def test_cli_argument_parsing(self) -> None:
    """Test CLI argument parsing."""
    with patch.object(sys, "argv", ["protonfetcher", "--list"]):
        args = parse_arguments()
        assert args.list is True
```

### Pattern 6: CLI Test with Mocked Fetcher

```python
def test_list_releases_operation(
    self,
    mocker: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test CLI --list operation."""
    # Arrange: Mock fetcher
    mock_fetcher = mocker.MagicMock()
    mock_fetcher.release_manager.list_recent_releases.return_value = [...]
    
    mocker.patch("protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher)
    mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher", "--list"])
    
    # Act
    main()
    
    # Assert
    captured = capsys.readouterr()
    assert "GE-Proton10-20" in captured.out
    assert "Success" in captured.out
```

## Running Tests

### Basic Commands

```bash
# Run all tests
uv run pytest -xvs

# Run specific test file
uv run pytest tests/test_github_fetcher_e2e.py -xvs

# Run specific test class
uv run pytest tests/test_link_manager_e2e.py::TestSymlinkCreation -xvs

# Run specific test
uv run pytest tests/test_link_manager_e2e.py::TestSymlinkCreation::test_create_symlinks_main_only -xvs

# Run tests for specific fork
uv run pytest tests/test_link_manager_e2e.py -k "ge_proton" -xvs

# Run with coverage
uv run pytest --cov=protonfetcher --cov-report=term-missing
```

### Test Markers

```bash
# Run only integration tests
uv run pytest -m integration

# Run only unit tests
uv run pytest -m unit

# Skip slow tests
uv run pytest -m "not slow"
```

## Mocking Best Practices

### DO: Mock Protocols

```python
# ✅ Correct: Mock the protocol
mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
mock_fs.exists.return_value = True
```

### DON'T: Mock the SUT

```python
# ❌ Wrong: Mocking the class under test
mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
```

### DO: Use Fixtures for Common Setups

```python
# ✅ Correct: Use fixture
def test_extraction(mock_tarfile_operations: Any):
    mocks = mock_tarfile_operations(members=[...])
```

### DON'T: Repeat Mock Setup

```python
# ❌ Wrong: Repeated setup in every test
mock_tarfile = mocker.patch("tarfile.open")
mock_tar = mocker.MagicMock()
mock_tar.getmembers.return_value = [...]
```

### DO: Verify Mock Interactions

```python
# ✅ Correct: Verify mock was used correctly
mock_filesystem_client.symlink_to.assert_called_with(
    link_path, target_path, target_is_directory=True
)
```

### DON'T: Only Check Return Values

```python
# ❌ Incomplete: Only checking result
assert result == expected

# ✅ Better: Also verify interactions
assert result == expected
mock_network_client.get.assert_called_once()
```

## Test Data Guidelines

### Test Data Fixture

Use the centralized `test_data` fixture for consistent test data:

```python
def test_fork_config(test_data: dict[str, Any]):
    ge_data = test_data["FORKS"][ForkName.GE_PROTON]
    assert ge_data["repo"] == "GloriousEggroll/proton-ge-custom"
```

### Temporary Paths

Always use `tmp_path` for temporary files:

```python
def test_with_temp_files(tmp_path: Path):
    temp_file = tmp_path / "test.txt"
    temp_file.write_text("data")
    # Automatically cleaned up after test
```

### Parametrized Data

Use parametrized fixtures for fork-specific data:

```python
@pytest.fixture(params=[ForkName.GE_PROTON, ForkName.PROTON_EM])
def fork_data(request: pytest.FixtureRequest, test_data: dict) -> dict:
    return test_data["FORKS"][request.param]
```

## Error Testing

### Exception Type Testing

```python
def test_invalid_input_raises_error():
    with pytest.raises(LinkManagementError, match="does not exist"):
        link_manager.remove_release(extract_dir, "NonExistent", ForkName.GE_PROTON)
```

### Error Message Testing

```python
def test_network_error_message(mock_network_client: Any):
    mock_network_client.get.return_value = subprocess.CompletedProcess(
        returncode=22, stderr="404 Not Found"
    )
    
    with pytest.raises(NetworkError, match="404"):
        fetcher.fetch_and_extract(...)
```

### Exception Chaining Testing

```python
def test_exception_chaining():
    try:
        # Code that raises chained exception
        pass
    except ProtonFetcherError as e:
        assert e.__cause__ is not None
```

## Integration Testing

### Network Integration

The `test_network_integration.py` file tests NetworkClient with mocked subprocess:

```python
def test_get_follows_redirects_mocked(mocker: Any):
    mock_response = subprocess.CompletedProcess(...)
    mock_run = mocker.patch("protonfetcher.network.subprocess.run", return_value=mock_response)
    
    client = NetworkClient(timeout=30)
    result = client.get("https://example.com/api")
    
    # Verify curl command structure
    call_args = mock_run.call_args[0][0]
    assert "-L" in call_args  # Follow redirects
```

### Filesystem Integration

Use real filesystem in `tmp_path` for integration tests:

```python
def test_symlink_creation(tmp_path: Path):
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    
    # Use real FileSystemClient
    fs = FileSystemClient()
    link_manager = LinkManager(fs)
    
    # Create real symlink
    link_manager.create_symlinks(...)
    
    # Verify real symlink
    assert (extract_dir / "GE-Proton").is_symlink()
```

## CI/CD Integration

### Quality Checks

```bash
# Run quality checks
make quality

# Run complexity checks
make radon

# Run all tests
make test
```

### Coverage Requirements

Tests should maintain:
- High branch coverage for error handling paths
- Full coverage of protocol implementations
- Comprehensive fork-specific testing

## Troubleshooting

### Common Issues

#### Mock Not Called

```python
# Issue: Mock configured but not used
# Solution: Verify SUT receives mocked dependencies

fetcher = GitHubReleaseFetcher(
    network_client=mock_network_client,  # ✅ Pass mock
    file_system_client=mock_filesystem_client,
)
```

#### Side Effect Not Triggered

```python
# Issue: side_effect not matching call signature
# Solution: Check argument types and order

mock_fs.exists.side_effect = lambda p: p in expected_paths
# Ensure p is Path object, not string
```

#### Fixture Not Found

```python
# Issue: Fixture not in scope
# Solution: Ensure fixture is in conftest.py or test file

# In conftest.py (available to all tests)
@pytest.fixture
def my_fixture(): ...

# Or in test file (available only to that file)
@pytest.fixture
def local_fixture(): ...
```

### Debugging Tips

1. **Print Mock Calls**: `print(mock_object.call_args_list)`
2. **Check Fixture Values**: Add `print()` in fixture to verify setup
3. **Use pytest -s**: Show print output during tests
4. **Use pytest --tb=long**: Full traceback on failures
5. **Use caplog**: Capture and assert log messages

```python
def test_with_logging(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("DEBUG"):
        # Code that logs
        pass
    
    assert "Expected log message" in caplog.text
```

## Extending the Test Suite

### Adding New Component Tests

1. Create test file: `tests/test_new_component_e2e.py`
2. Import fixtures from `conftest.py`
3. Follow existing test patterns
4. Add parametrized tests for all forks

### Adding New Fixtures

1. Add to `conftest.py` for global availability
2. Follow naming convention: `mock_*` for mocks, `*_environment` for setups
3. Document with docstrings and usage examples
4. Type hint return values
5. **Avoid default parameters** for fixtures that depend on parametrized fixtures

**Fixture Documentation Template:**

```python
@pytest.fixture
def my_new_fixture(...) -> ReturnType:
    """
    Brief description of fixture purpose.
    
    Detailed explanation if needed.
    
    Args:
        param1: Description of parameters
    
    Returns:
        Description of return value
    
    Usage:
        def test_example(my_new_fixture):
            # Example usage code
            pass
    """
```

### Adding Fork Support

1. Add fork to parametrized `fork` fixture in `conftest.py`
2. Update `test_data` fixture with fork config
3. Add fork-specific test cases where behavior differs
4. Ensure all parametrized tests include the new fork

## Fixture Best Practices Summary

### DO: Use Parametrized Fixtures

```python
# ✅ CORRECT: One test runs for all forks
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_all_forks(fork: ForkName, test_data: dict):
    config = test_data["FORKS"][fork]
    # Test fork-specific behavior
```

### DO: Use Centralized Test Data

```python
# ✅ CORRECT: Use test_data fixture
def test_config(test_data: dict, fork: ForkName):
    repo = test_data["FORKS"][fork]["repo"]
    # Avoids hardcoding strings
```

### DO: Use Factory Fixtures with Indirect Parametrization

```python
# ✅ CORRECT: Use factory fixture
@pytest.mark.parametrize("release_assets", [[{"name": "test.tar.gz"}]], indirect=True)
def test_assets(release_assets):
    # Uses parametrized factory data
```

### DO: Use Specialized Mocks for Error Scenarios

```python
# ✅ CORRECT: Use purpose-built mock
def test_rate_limit(mock_network_with_rate_limit, mock_filesystem_client):
    # Pre-configured for rate limit error
```

### DON'T: Hardcode Fork Values

```python
# ❌ WRONG: Misses other forks
def test_ge_proton():
    fork = ForkName.GE_PROTON
    test_fork(fork)
```

### DON'T: Duplicate Fixture Setup

```python
# ❌ WRONG: Duplicate mock setup
def test_one():
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.get.return_value = ...

def test_two():
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.get.return_value = ...  # Duplicate!

# ✅ CORRECT: Use fixture
def test_one(mock_network_client):
    # Fixture provides consistent setup
```

### DON'T: Use Default Parameters for Parametrized Dependencies

```python
# ❌ WRONG: Default parameter conflicts with parametrization
@pytest.fixture
def my_fixture(tmp_path, fork: ForkName = ForkName.GE_PROTON):
    # Will always use GE-Proton even when parametrized

# ✅ CORRECT: Require explicit parameter
@pytest.fixture
def my_fixture(tmp_path, fork: ForkName):
    # Properly uses the parametrized fork value
```
