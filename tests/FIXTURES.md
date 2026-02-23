# ProtonFetcher Test Fixtures Reference

## Overview

This document provides comprehensive documentation for all test fixtures available in the ProtonFetcher test suite. Fixtures are organized by category and include usage examples.

**Location:** `tests/conftest.py`

## Fixture Categories

| Category | Purpose | Key Fixtures |
|----------|---------|--------------|
| **Factories** | Configurable mock/object creation | `mock_network_factory`, `mock_filesystem_factory`, `sample_archive_factory` |
| **Test Data** | Centralized test configurations | `test_data` |
| **Fork Fixtures** | Fork-specific parametrization | `fork`, `fork_repo`, `fork_archive_format` |
| **Environment** | Test environment setup | `test_environment_builder`, `temp_environment` |
| **Components** | SUT (System Under Test) creation | `release_manager`, `link_manager`, `github_fetcher` |
| **Helpers** | Mocking utilities | `mock_tarfile_operations`, `mock_urllib_download` |

---

## Factory Fixtures

Factory fixtures return callable functions that create configured objects. This approach reduces fixture duplication and provides flexibility.

### `mock_network_factory`

**Purpose:** Create configured `NetworkClientProtocol` mocks.

**Returns:** `Callable[..., MagicMock]`

**Parameters:**
- `get_response` (dict | str | None): Response body for GET requests
- `head_response` (dict | str | None): Response for HEAD requests
- `download_response` (dict | None): Response for download operations
- `rate_limit` (bool): Simulate API rate limit error
- `not_found` (bool): Simulate 404 Not Found error
- `custom_returncode` (int | None): Custom subprocess return code

**Usage Examples:**

```python
# Default mock (successful API response)
def test_default_behavior(mock_network_factory):
    mock_network = mock_network_factory()
    release_manager = ReleaseManager(mock_network, mock_filesystem_client)
    result = release_manager.fetch_latest_tag("owner/repo")

# Custom API response
def test_asset_processing(mock_network_factory):
    mock_network = mock_network_factory(
        get_response={
            "assets": [
                {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
                {"name": "GE-Proton10-19.tar.gz", "size": 1048575},
            ]
        }
    )

# Rate limit error scenario
def test_rate_limit_handling(mock_network_factory):
    mock_network = mock_network_factory(rate_limit=True)
    release_manager = ReleaseManager(mock_network, mock_filesystem_client)
    
    with pytest.raises(NetworkError, match="rate limit"):
        release_manager.list_recent_releases("owner/repo")

# 404 error scenario
def test_not_found_handling(mock_network_factory):
    mock_network = mock_network_factory(not_found=True)
    
    with pytest.raises(NetworkError, match="404"):
        # Test code that handles 404
```

**Implementation:**
```python
@pytest.fixture
def mock_network_factory(mocker: Any) -> Callable[..., Any]:
    def _create_mock(
        get_response: dict | str | None = None,
        head_response: dict | str | None = None,
        download_response: dict | None = None,
        rate_limit: bool = False,
        not_found: bool = False,
        custom_returncode: int | None = None,
    ) -> Any:
        mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
        mock_network.timeout = DEFAULT_TIMEOUT
        
        # Configure based on parameters...
        return mock_network
    
    return _create_mock
```

---

### `mock_filesystem_factory`

**Purpose:** Create configured `FileSystemClientProtocol` mocks.

**Returns:** `Callable[..., MagicMock]`

**Parameters:**
- `exists_map` (dict[str, bool]): Path → exists result
- `is_dir_map` (dict[str, bool]): Path → is_dir result
- `is_symlink_map` (dict[str, bool]): Path → is_symlink result
- `read_map` (dict[str, bytes]): Path → file content
- `size_map` (dict[str, int]): Path → file size
- `use_tmp_path` (bool): Delegate to real tmp_path operations

**Usage Examples:**

```python
# Mock with custom path mappings
def test_file_operations(mock_filesystem_factory):
    mock_fs = mock_filesystem_factory(
        exists_map={
            "/dir": True,
            "/file.txt": True,
            "/missing": False,
        },
        is_dir_map={
            "/dir": True,
            "/file.txt": False,
        },
        read_map={
            "/file.txt": b"file content",
        },
    )
    
    assert mock_fs.exists(Path("/dir")) is True
    assert mock_fs.exists(Path("/missing")) is False
    assert mock_fs.read(Path("/file.txt")) == b"file content"

# Mock that delegates to real tmp_path
def test_with_real_tmp(mock_filesystem_factory, tmp_path):
    mock_fs = mock_filesystem_factory(use_tmp_path=True)
    
    # Create real file in tmp_path
    test_file = tmp_path / "test.txt"
    test_file.write_text("data")
    
    # Mock delegates to real filesystem
    assert mock_fs.exists(test_file) is True
    assert mock_fs.read(test_file) == b"data"
```

---

### `sample_archive_factory`

**Purpose:** Create sample tar archives for extraction testing.

**Returns:** `Callable[..., Path]`

**Parameters:**
- `format` (str): Archive format ("gz" or "xz")
- `tag` (str): Release tag name (used for directory name)
- `files` (list[tuple[str, str]]): List of (filename, content) tuples

**Usage Examples:**

```python
# Default archive (GE-Proton10-20.tar.gz)
def test_extraction(sample_archive_factory, tmp_path):
    archive = sample_archive_factory()
    assert archive.name == "GE-Proton10-20.tar.gz"

# Custom archive format
@pytest.mark.parametrize("fmt", ["gz", "xz"])
def test_both_formats(fmt, sample_archive_factory):
    archive = sample_archive_factory(format=fmt, tag="EM-10.0-30")
    if fmt == "gz":
        assert archive.suffix == ".gz"
    else:
        assert archive.suffix == ".xz"

# Custom file structure
def test_complex_archive(sample_archive_factory):
    archive = sample_archive_factory(
        tag="GE-Proton10-20",
        files=[
            ("version", "GE-Proton10-20"),
            ("lib/libwine.so", "fake libwine"),
            ("lib64/wine/x86_64-windows/kernel32.dll", "fake dll"),
        ],
    )
    # Archive contains realistic Proton directory structure
```

---

### `test_environment_builder`

**Purpose:** Builder pattern for creating complete test environments.

**Returns:** `EnvironmentBuilder` instance with fluent interface

**Builder Methods:**
- `with_extract_dir(path: str | None)`: Create extract directory
- `with_output_dir(path: str | None)`: Create output/download directory
- `with_versions(versions: list[str])`: Create version directories
- `with_symlinks()`: Create symlinks for versions
- `with_fork(fork: ForkName)`: Set fork type
- `build()`: Build and return environment dict

**Usage Examples:**

```python
# Basic environment
def test_basic_setup(test_environment_builder):
    env = (test_environment_builder
        .with_extract_dir()
        .with_output_dir()
        .build())
    
    assert env["extract_dir"].exists()
    assert env["output_dir"].exists()

# Environment with version directories
def test_with_versions(test_environment_builder):
    env = (test_environment_builder
        .with_extract_dir()
        .with_versions(["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"])
        .build())
    
    assert len(env["version_dirs"]) == 3
    assert env["version_dirs"][0].name == "GE-Proton10-20"

# Complete symlink environment
def test_with_symlinks(test_environment_builder):
    env = (test_environment_builder
        .with_extract_dir()
        .with_fork(ForkName.GE_PROTON)
        .with_versions(["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"])
        .with_symlinks()
        .build())
    
    # Returns dict with symlinks created
    assert "GE-Proton" in env["symlinks"]
    assert env["symlinks"]["GE-Proton"].is_symlink()

# Fork-specific environment
def test_proton_em_environment(test_environment_builder):
    env = (test_environment_builder
        .with_fork(ForkName.PROTON_EM)
        .with_extract_dir()
        .with_versions(["EM-10.0-30", "EM-10.0-29"])
        .build())
    
    assert env["fork"] == ForkName.PROTON_EM
```

**Returned Environment Dict:**
```python
{
    "tmp": Path,              # Base tmp_path
    "extract_dir": Path,      # Extract directory
    "output_dir": Path,       # Output directory (if created)
    "version_dirs": list[Path],  # Version directory paths
    "symlinks": dict[str, Path],  # Symlink name → path
    "fork": ForkName,         # Fork type
}
```

---

## Test Data Fixtures

### `test_data`

**Purpose:** Centralized fork-specific test data to avoid hardcoding strings.

**Returns:** `dict[str, Any]`

**Structure:**
```python
{
    "FORKS": {
        ForkName.GE_PROTON: {
            "repo": "GloriousEggroll/proton-ge-custom",
            "example_tag": "GE-Proton10-20",
            "example_asset": "GE-Proton10-20.tar.gz",
            "archive_format": ".tar.gz",
        },
        # ... Proton-EM and CachyOS
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
# Access fork-specific data
def test_fork_configuration(test_data: dict[str, Any], fork: ForkName):
    repo = test_data["FORKS"][fork]["repo"]
    expected_tag = test_data["FORKS"][fork]["example_tag"]
    assert repo in expected_tag.lower() or expected_tag in repo

# Access CLI output strings
def test_success_message(test_data: dict[str, Any], capsys):
    # Run CLI operation
    main()
    captured = capsys.readouterr()
    assert test_data["CLI_OUTPUTS"]["success"] in captured.out

# Access GitHub API error patterns
def test_rate_limit_error(test_data: dict[str, Any], mock_network_factory):
    mock_network = mock_network_factory(rate_limit=True)
    
    with pytest.raises(NetworkError, match=test_data["GITHUB_API"]["rate_limit_message"]):
        # Test code
```

---

## Parametrized Fork Fixtures

These fixtures enable comprehensive testing across all supported Proton forks.

### `fork`

**Purpose:** Base parametrized fixture that runs tests for each fork.

**Returns:** `ForkName` enum value

**Usage:**
```python
# Automatically runs test 3 times (once per fork)
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_all_forks(fork: ForkName):
    # Test runs with GE-Proton, Proton-EM, and CachyOS
```

---

### `fork_repo`

**Purpose:** Get repository name for a given fork.

**Returns:** `str` in format `"owner/repo"`

**Usage:**
```python
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
def test_repo_configuration(fork: ForkName, fork_repo: str):
    # fork_repo automatically matches the fork parameter
    assert "proton" in fork_repo.lower()
    assert "/" in fork_repo
```

---

### `fork_archive_format`

**Purpose:** Get archive format extension for a given fork.

**Returns:** `str` (`.tar.gz` or `.tar.xz`)

**Usage:**
```python
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_archive_format(fork: ForkName, fork_archive_format: str):
    assert fork_archive_format.startswith(".tar")
    if fork == ForkName.GE_PROTON:
        assert fork_archive_format == ".tar.gz"
    else:
        assert fork_archive_format == ".tar.xz"
```

---

### `fork_link_names`

**Purpose:** Get symlink paths for a given fork.

**Returns:** `tuple[Path, Path, Path]` - (main, fallback1, fallback2)

**Usage:**
```python
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
def test_symlink_paths(fork: ForkName, fork_link_names: tuple[Path, Path, Path], extract_dir: Path):
    main_link, fb1, fb2 = fork_link_names
    
    # Verify fork-specific naming
    assert "Proton" in main_link.name
    assert "Fallback" in fb1.name
```

---

## Environment Fixtures

### `temp_environment`

**Purpose:** Create temporary directories for testing workflows.

**Returns:** `dict[str, Path]`

**Usage:**
```python
def test_download_workflow(temp_environment: dict[str, Path]):
    output_dir = temp_environment["output_dir"]
    extract_dir = temp_environment["extract_dir"]
    
    # Use directories for test
    archive_path = output_dir / "test.tar.gz"
    # ...
```

---

### `extract_dir`

**Purpose:** Create a temporary extract directory.

**Returns:** `Path`

**Usage:**
```python
def test_extraction(extract_dir: Path):
    # extract_dir is a temporary directory ready for use
    target = extract_dir / "GE-Proton10-20"
    # ...
```

---

### `output_dir`

**Purpose:** Create a temporary output/download directory.

**Returns:** `Path`

**Usage:**
```python
def test_download(output_dir: Path):
    # output_dir is a temporary directory ready for use
    archive = output_dir / "download.tar.gz"
    # ...
```

---

## Component Fixtures (SUT Factories)

Component fixtures create instances of the System Under Test (SUT) with mocked dependencies.

### `release_manager`

**Purpose:** Create `ReleaseManager` with mocked dependencies.

**Returns:** `ReleaseManager` instance

**Dependencies:** `mock_network_client`, `mock_filesystem_client`

**Usage:**
```python
def test_fetch_latest_tag(release_manager: ReleaseManager, mock_network_factory):
    mock_network = mock_network_factory(
        get_response={"tag_name": "GE-Proton10-20"}
    )
    release_manager.network_client = mock_network
    
    tag = release_manager.fetch_latest_tag("GloriousEggroll/proton-ge-custom")
    assert tag == "GE-Proton10-20"
```

---

### `asset_downloader`

**Purpose:** Create `AssetDownloader` with mocked dependencies.

**Returns:** `AssetDownloader` instance

**Dependencies:** `mock_network_client`, `mock_filesystem_client`

---

### `archive_extractor`

**Purpose:** Create `ArchiveExtractor` with mocked dependencies.

**Returns:** `ArchiveExtractor` instance

**Dependencies:** `mock_filesystem_client`

---

### `link_manager`

**Purpose:** Create `LinkManager` with mocked dependencies.

**Returns:** `LinkManager` instance

**Dependencies:** `mock_filesystem_client`

**Usage:**
```python
def test_symlink_creation(link_manager: LinkManager, mock_filesystem_factory, tmp_path):
    mock_fs = mock_filesystem_factory(use_tmp_path=True)
    link_manager.file_system_client = mock_fs
    
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    
    # Create version directory
    version_dir = extract_dir / "GE-Proton10-20"
    version_dir.mkdir()
    
    # Create symlinks
    link_manager.create_symlinks(
        main=extract_dir / "GE-Proton",
        fb1=extract_dir / "GE-Proton-Fallback",
        fb2=extract_dir / "GE-Proton-Fallback2",
        top_3=[(("GE-Proton", 10, 20, 0), version_dir)]
    )
    
    assert (extract_dir / "GE-Proton").is_symlink()
```

---

### `github_fetcher`

**Purpose:** Create `GitHubReleaseFetcher` (main orchestrator) with mocked dependencies.

**Returns:** `GitHubReleaseFetcher` instance

**Dependencies:** `mock_network_client`, `mock_filesystem_client`

**Usage:**
```python
def test_complete_workflow(github_fetcher: GitHubReleaseFetcher, mock_network_factory, mock_filesystem_factory):
    # Configure mocks
    mock_network = mock_network_factory(get_response={...})
    mock_fs = mock_filesystem_factory(use_tmp_path=True)
    
    github_fetcher.network_client = mock_network
    github_fetcher.file_system_client = mock_fs
    
    # Run workflow
    result = github_fetcher.fetch_and_extract(
        fork=ForkName.GE_PROTON,
        output_dir=Path("/tmp/output"),
        extract_dir=Path("/tmp/extract"),
    )
```

---

## Helper Fixtures

### `mock_tarfile_operations`

**Purpose:** Mock tarfile operations for extraction testing.

**Returns:** `Callable[..., dict[str, Any]]`

**Parameters:**
- `members` (list[dict] | None): Tar member definitions
- `raise_on_open` (Exception | None): Exception to raise on tarfile.open

**Returns Dict:**
- `tarfile_mock`: The patched `tarfile.open` mock
- `tar_mock`: The mock tar object from `__enter__`

**Usage:**
```python
def test_extraction(mock_tarfile_operations: Any):
    mocks = mock_tarfile_operations(
        members=[
            {"name": "GE-Proton10-20", "is_dir": True, "size": 0},
            {"name": "GE-Proton10-20/version", "is_dir": False, "size": 14},
            {"name": "GE-Proton10-20/lib/libwine.so", "is_dir": False, "size": 1024},
        ]
    )
    
    # Run extraction code
    extractor.extract_archive(archive_path, target_dir)
    
    # Verify tarfile was used
    assert mocks["tarfile_mock"].called
    assert mocks["tar_mock"].getmembers.called
```

---

### `mock_urllib_download`

**Purpose:** Mock urllib download operations.

**Returns:** `Callable[..., Any]`

**Parameters:**
- `chunks` (list[bytes] | None): Byte chunks to return from read()
- `content_length` (int | None): Content-Length header value
- `raise_on_open` (Exception | None): Exception to raise on urlopen

**Usage:**
```python
def test_download(mock_urllib_download: Any, mock_builtin_open: Any):
    # Configure mock to return chunks
    mock_urllib_download(
        chunks=[b"chunk1", b"chunk2", b""],
        content_length=1048576,
    )
    
    # Capture writes
    _, written_data = mock_builtin_open()
    
    # Run download
    downloader.download_with_spinner(url, output_path)
    
    # Verify data was written
    assert b"".join(written_data) == b"chunk1chunk2"
```

---

### `mock_subprocess_tar`

**Purpose:** Mock subprocess.tar command for system tar fallback testing.

**Returns:** `Callable[..., Any]`

**Parameters:**
- `returncode` (int): Return code for CompletedProcess
- `stdout` (str): Stdout for CompletedProcess
- `stderr` (str): Stderr for CompletedProcess
- `raise_on_call` (Exception | None): Exception to raise on subprocess.run

**Usage:**
```python
def test_system_tar_fallback(mock_subprocess_tar: Any):
    mock_run = mock_subprocess_tar(returncode=0, stdout="", stderr="")
    
    # Run extraction (will use system tar fallback)
    extractor.extract_archive(archive_path, target_dir)
    
    # Verify tar command was called
    assert mock_run.called
    call_args = mock_run.call_args[0][0]
    assert "tar" in call_args
```

---

### `mock_builtin_open`

**Purpose:** Mock built-in open() to capture writes without creating real files.

**Returns:** `Callable[..., tuple[Any, list[bytes]]]`

**Returns Tuple:**
- `mock_file`: The mock file object
- `written_data`: List of bytes chunks written

**Usage:**
```python
def test_file_writes(mock_builtin_open: Any):
    mock_file, written_data = mock_builtin_open()
    
    # Code that writes to file
    with open("/mock/path", "wb") as f:
        f.write(b"chunk1")
        f.write(b"chunk2")
    
    # Verify writes
    assert len(written_data) == 2
    assert written_data[0] == b"chunk1"
    assert written_data[1] == b"chunk2"
```

---

## Data Factory Fixtures

These fixtures provide parametrized test data.

### `release_assets`

**Purpose:** Factory for creating GitHub release assets.

**Returns:** `list[dict[str, Any]]` - List of `{"name": str, "size": int}`

**Usage:**
```python
# Default assets
def test_with_default_assets(release_assets: list[dict]):
    assert len(release_assets) > 0

# Custom assets with indirect parametrization
@pytest.mark.parametrize(
    "release_assets",
    [
        [{"name": "GE-Proton10-20.tar.gz", "size": 1048576}],
        [{"name": "proton-EM-10.0-30.tar.xz", "size": 2097152}],
    ],
    indirect=True,
)
def test_with_custom_assets(release_assets: list[dict]):
    assert release_assets[0]["name"].endswith(".tar.gz")
```

---

### `github_release_response`

**Purpose:** Factory for GitHub API release responses.

**Returns:** `dict[str, Any]` - `{"tag_name": str, "name": str, "assets": list}`

**Usage:**
```python
# Default response
def test_default_response(github_release_response: dict):
    assert github_release_response["tag_name"] == "GE-Proton10-20"

# Custom response with indirect parametrization
@pytest.mark.parametrize(
    "github_release_response",
    [{"tag_name": "custom-tag", "name": "Custom Release"}],
    indirect=True,
)
def test_custom_response(github_release_response: dict):
    assert github_release_response["tag_name"] == "custom-tag"
```

---

### `recent_releases`

**Purpose:** Factory for recent release tag lists.

**Returns:** `list[str]` - List of release tag strings

**Usage:**
```python
# Default releases
def test_default_releases(recent_releases: list[str]):
    assert len(recent_releases) == 5
    assert recent_releases[0] == "GE-Proton10-20"

# Custom releases
@pytest.mark.parametrize(
    "recent_releases",
    [["custom-1", "custom-2", "custom-3"]],
    indirect=True,
)
def test_custom_releases(recent_releases: list[str]):
    assert recent_releases[0] == "custom-1"
```

---

## Fixture Best Practices

### DO: Use Factory Fixtures

```python
# ✅ CORRECT: Flexible factory
def test_custom_scenario(mock_network_factory):
    mock_network = mock_network_factory(
        get_response={"custom": "response"},
        rate_limit=False,
    )
```

### DON'T: Create Redundant Specialized Fixtures

```python
# ❌ WRONG: Multiple similar fixtures
@pytest.fixture
def mock_network_with_custom_response(mocker): ...

@pytest.fixture
def mock_network_without_rate_limit(mocker): ...

# ✅ CORRECT: Single factory
@pytest.fixture
def mock_network_factory(mocker):
    def _create(...): ...
    return _create
```

---

### DO: Use Builder for Complex Environments

```python
# ✅ CORRECT: Fluent builder pattern
def test_complex_scenario(test_environment_builder):
    env = (test_environment_builder
        .with_extract_dir()
        .with_fork(ForkName.PROTON_EM)
        .with_versions(["EM-10.0-30", "EM-10.0-29"])
        .with_symlinks()
        .build())
```

### DON'T: Duplicate Setup Logic

```python
# ❌ WRONG: Repeated setup in every test
def test_one(tmp_path):
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    # ...

def test_two(tmp_path):
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    # ... duplicate code

# ✅ CORRECT: Use fixture
def test_one(test_environment_builder):
    env = test_environment_builder.with_extract_dir().build()
```

---

### DO: Use Parametrized Fork Fixtures

```python
# ✅ CORRECT: Comprehensive fork testing
@pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def test_all_forks(fork: ForkName, fork_repo: str):
    # Test runs for all forks
```

### DON'T: Hardcode Fork Values

```python
# ❌ WRONG: Misses other forks
def test_ge_proton():
    fork = ForkName.GE_PROTON
    test_fork(fork)

def test_proton_em():
    fork = ForkName.PROTON_EM
    test_fork(fork)
```

---

### DO: Use Centralized Test Data

```python
# ✅ CORRECT: Avoids hardcoding
def test_repo(test_data: dict, fork: ForkName):
    repo = test_data["FORKS"][fork]["repo"]
    assert "proton" in repo.lower()
```

### DON'T: Hardcode Strings

```python
# ❌ WRONG: Magic strings
def test_repo(fork: ForkName):
    if fork == ForkName.GE_PROTON:
        repo = "GloriousEggroll/proton-ge-custom"
    # ...
```

---

## Troubleshooting

### Fixture Not Found

**Problem:** `fixture 'xyz' not found`

**Solutions:**
1. Ensure fixture is in `conftest.py` (available to all tests)
2. Check fixture name spelling
3. Verify fixture is not conditionally defined

---

### Fixture Depends on Parametrized Fixture

**Problem:** Fixture doesn't respect parametrization

**Solution:** Don't use default parameters for fixtures that depend on parametrized fixtures:

```python
# ❌ WRONG: Default conflicts with parametrization
@pytest.fixture
def my_fixture(fork: ForkName = ForkName.GE_PROTON):
    # Always uses GE-Proton

# ✅ CORRECT: Require explicit parameter
@pytest.fixture
def my_fixture(fork: ForkName):
    # Properly uses parametrized fork value
```

---

### Factory Fixture Not Callable

**Problem:** `TypeError: 'MagicMock' object is not callable`

**Solution:** Ensure factory returns the inner function:

```python
# ❌ WRONG: Returns mock directly
@pytest.fixture
def my_factory(mocker):
    return mocker.MagicMock()

# ✅ CORRECT: Returns factory function
@pytest.fixture
def my_factory(mocker):
    def _create(...):
        return mocker.MagicMock()
    return _create
```

---

## Migration Guide (Pre-Streamlining)

If you're familiar with the pre-streamlining fixtures, here's the mapping:

| Old Fixture | New Fixture | Notes |
|-------------|-------------|-------|
| `mock_network_client` | `mock_network_factory()` | Call factory with no args |
| `mock_network_with_rate_limit` | `mock_network_factory(rate_limit=True)` | Use parameter |
| `mock_network_with_404` | `mock_network_factory(not_found=True)` | Use parameter |
| `mock_filesystem_client` | `mock_filesystem_factory()` | Call factory with no args |
| `mock_filesystem_with_directory_structure` | `mock_filesystem_factory(use_tmp_path=True)` | Use parameter |
| `sample_tar_gz_archive` | `sample_archive_factory(format="gz")` | Use factory |
| `sample_tar_xz_archive` | `sample_archive_factory(format="xz")` | Use factory |
| `temp_environment` | `test_environment_builder.with_extract_dir().with_output_dir().build()` | Use builder |
| `installed_proton_versions` | `test_environment_builder.with_versions([...]).build()["version_dirs"]` | Use builder |
| `symlink_environment` | `test_environment_builder.with_symlinks().build()` | Use builder |

---

*Last updated: 2026-02-23*
