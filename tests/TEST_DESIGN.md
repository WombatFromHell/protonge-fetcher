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

### Directory Structure (Current)

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_cli.py              # CLI interface tests (all operations)
├── test_github_fetcher.py   # Main orchestrator tests
├── test_link_manager_e2e.py # Symlink management E2E tests
├── test_release_manager_e2e.py # Release discovery E2E tests
├── test_extraction.py       # Archive extraction tests
├── test_integration.py      # Integration tests
├── test_utils.py            # Utility function tests (version parsing)
├── test_prune.py            # Prune operation tests (NEW)
└── TEST_DESIGN.md           # This document
```

**Note:** The test suite continues to evolve. In 2026-03, `test_prune.py` was added to test the new `--prune` feature with 27 comprehensive tests covering argument parsing, operation flow, LinkManager integration, and end-to-end scenarios.

### Original Structure (Pre-Streamlining)

```
tests/
├── conftest.py                    # 1,155 lines
├── test_cli_e2e.py                # 824 lines
├── test_check_mode.py             # 594 lines
├── test_dry_run.py                # 493 lines
├── test_extraction_workflow_e2e.py # 747 lines
├── test_github_fetcher_e2e.py     # 917 lines
├── test_link_manager_e2e.py       # 852 lines
├── test_network_integration.py    # 336 lines
├── test_release_manager_e2e.py    # 734 lines
├── test_spinner_integration.py    # 487 lines
└── TEST_DESIGN.md
```

### Test Categories

| Category | Purpose | Files |
|----------|---------|-------|
| **Unit Tests** | Component-specific method testing | `test_utils.py`, embedded in E2E files |
| **Integration Tests** | Component interaction testing | `test_integration.py` |
| **End-to-End Tests** | Complete workflow testing | `test_cli.py`, `test_github_fetcher.py`, `test_prune.py` |
| **CLI Tests** | Command-line interface testing | `test_cli.py` |
| **Feature Tests** | New feature testing (comprehensive) | `test_prune.py` |

### Test Suite Statistics (2026-03)

| Metric | Count |
|--------|-------|
| Test files | 9 |
| Total tests | 260+ |
| Test coverage | ~85% |
| Newest feature tests | `test_prune.py` (27 tests) |

**Key improvements since streamlining:**
- ✅ Added comprehensive prune feature tests (27 tests)
- ✅ Real filesystem testing for symlink operations (where mocks fail)
- ✅ Enhanced CLI operation flow testing
- ✅ Better integration between LinkManager and filesystem
- ✅ Maintained fast test execution (<1 second for full suite)

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

### 3. Real Filesystem for Symlink Operations

Tests use the real filesystem for symlink operations where mocks don't properly handle `resolve()`:

```python
# ✅ Prefer: Real filesystem for symlink testing (in tmp_path)
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.link_manager import LinkManager

def test_prune_releases_protects_linked_versions(tmp_path: Path):
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    
    # Create real directories and symlinks
    fs = FileSystemClient()
    link_manager = LinkManager(fs)
    
    # Test with real symlink operations
    result = link_manager.prune_releases(...)
```

**When to use real vs. mocked filesystem:**

| Scenario | Approach | Reason |
|----------|----------|--------|
| Symlink creation/resolution | Real filesystem | Mocks don't handle `resolve()` properly |
| Directory iteration | Real filesystem | Mocks require complex side_effect setup |
| File write/read | Mocked | Faster, no I/O |
| Network calls | Always mocked | External dependency |
| tarfile operations | Mocked | Complex archive handling |

## Golden Rules

The ProtonFetcher test suite follows four fundamental rules. All contributors must adhere to these principles.

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

### Rule 2: Use Real Filesystem for Symlink Operations

**Never mock symlink creation or resolution.** The mock `FileSystemClientProtocol` doesn't properly implement `resolve()`, which breaks symlink testing.

```python
# ❌ WRONG: Using mocked filesystem for symlinks
def test_symlink_with_mock(mock_filesystem_client: Any):
    link_manager = LinkManager(mock_filesystem_client)
    # resolve() returns MagicMock, not actual path - assertions fail!

# ✅ CORRECT: Use real filesystem in tmp_path
def test_symlink_with_real_fs(tmp_path: Path):
    from protonfetcher.filesystem import FileSystemClient
    from protonfetcher.link_manager import LinkManager
    
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    
    fs = FileSystemClient()  # Real filesystem
    link_manager = LinkManager(fs)
    
    # Create real symlink
    main_link.symlink_to(version_dir)
    
    # resolve() works correctly
    assert main_link.resolve() == version_dir
```

**Rationale:** Mocking `resolve()` requires complex `side_effect` chains that are brittle and error-prone. Real filesystem operations in `tmp_path` are fast, reliable, and test actual behavior.

**Scope:** This rule applies specifically to symlink operations. Continue mocking:
- Network calls (external dependency)
- File read/write (faster with mocks)
- tarfile operations (complex archive handling)
- subprocess calls (external tools)

### Rule 3: Leverage pytest/pytest-mock Features Fully

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

## Fixtures

**See [`FIXTURES.md`](FIXTURES.md) for comprehensive fixture documentation.**

The test suite uses **factory-based fixtures** to reduce duplication and improve flexibility. Key fixtures include:

| Category | Key Fixtures | Purpose |
|----------|--------------|---------|
| **Factories** | `mock_network_factory`, `mock_filesystem_factory`, `sample_archive_factory` | Configurable mock creation |
| **Test Data** | `test_data` | Centralized fork configurations |
| **Fork Fixtures** | `fork`, `fork_repo`, `fork_archive_format` | Parametrized fork testing |
| **Environment** | `test_environment_builder` | Fluent test environment setup |
| **Components** | `release_manager`, `link_manager`, `github_fetcher` | SUT creation with mocked deps |

### Quick Example

```python
# Factory-based mocking
def test_custom_scenario(mock_network_factory, test_environment_builder):
    mock_network = mock_network_factory(rate_limit=True)
    env = test_environment_builder.with_extract_dir().build()
    
    # Test code using configured mocks and environment
```

For complete fixture documentation including all parameters and usage examples, see [`FIXTURES.md`](FIXTURES.md).

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

### Pattern 7: Feature Test with Multiple Test Types

New features should include comprehensive test coverage across multiple test types:

```python
# test_prune.py - Example feature test structure

class TestPruneArgumentParsing:
    """Test CLI argument parsing for --prune flag."""
    
    def test_parse_prune_flag(self) -> None: ...
    def test_parse_prune_with_keep(self) -> None: ...
    def test_parse_prune_mutually_exclusive_with_release(self) -> None: ...

class TestPruneOperationFlow:
    """Test the --prune operation flow."""
    
    def test_prune_no_unmanaged_releases(self) -> None: ...
    def test_prune_with_dry_run(self) -> None: ...
    def test_prune_with_confirmation_yes(self) -> None: ...

class TestLinkManagerPruneIntegration:
    """Integration tests for LinkManager.prune_releases()."""
    
    def test_prune_releases_protects_linked_versions(self) -> None: ...
    def test_prune_releases_dry_run_no_deletion(self) -> None: ...

class TestPruneE2E:
    """End-to-end tests for prune functionality."""
    
    def test_prune_e2e_all_forks_no_prunable(self) -> None: ...
    def test_prune_e2e_with_prunable_versions(self) -> None: ...
```

**Feature test checklist:**
- ✅ Argument parsing tests (all flags, mutual exclusivity)
- ✅ Operation flow tests (all scenarios, confirmation, dry-run)
- ✅ Integration tests (real filesystem where needed)
- ✅ E2E tests (complete workflow verification)
- ✅ Error handling tests (edge cases, invalid inputs)

## Running Tests

### Basic Commands

```bash
# Run all tests
uv run pytest -xvs

# Run specific test file
uv run pytest tests/test_prune.py -xvs

# Run specific test class
uv run pytest tests/test_prune.py::TestPruneOperationFlow -xvs

# Run specific test
uv run pytest tests/test_prune.py::TestPruneOperationFlow::test_prune_with_dry_run -xvs

# Run tests for specific fork
uv run pytest tests/test_link_manager_e2e.py -k "ge_proton" -xvs

# Run with coverage
uv run pytest --cov=protonfetcher --cov-report=term-missing

# Run prune tests only
uv run pytest tests/test_prune.py -v
```

## Testing New Features

### Feature Test Template

When adding a new feature, follow the `test_prune.py` template:

1. **Argument Parsing Tests** - Verify CLI flags parse correctly
2. **Operation Flow Tests** - Test the feature's main workflow
3. **Integration Tests** - Test with real components where mocks fail
4. **E2E Tests** - Test complete user scenarios

### Example: Prune Feature Tests

The `test_prune.py` file (27 tests) demonstrates comprehensive feature testing:

| Test Category | Count | Purpose |
|---------------|-------|---------|
| Argument Parsing | 10 | CLI flag validation, mutual exclusivity |
| Operation Flow | 8 | Dry-run, confirmation, single/all forks |
| LinkManager Integration | 7 | Real filesystem, version protection |
| E2E Tests | 2 | Complete workflow verification |

**Key design decisions:**
- Uses real `FileSystemClient` for symlink operations (mocks don't handle `resolve()`)
- Tests all three forks (GE-Proton, Proton-EM, CachyOS)
- Verifies linked version protection
- Tests confirmation workflow (yes/no/abort)

## Test Markers

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

### DO: Use Real Filesystem for Symlinks

```python
# ✅ Correct: Real filesystem for symlink testing
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.link_manager import LinkManager

def test_symlink(tmp_path: Path):
    fs = FileSystemClient()
    lm = LinkManager(fs)
    # Test with real symlinks
```

### DON'T: Mock Symlink Operations

```python
# ❌ Wrong: Mocked filesystem for symlinks
def test_symlink(mock_filesystem_client: Any):
    lm = LinkManager(mock_filesystem_client)
    # resolve() returns MagicMock - assertions will fail!
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

**For prune-specific testing, see `test_prune.py`:**
- `TestLinkManagerPruneIntegration` - Real filesystem for symlink protection tests
- `TestPruneE2E` - End-to-end workflow with real directories
- All tests use `tmp_path` for isolation

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
