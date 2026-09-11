# ProtonFetcher Test Fixtures Reference

## Overview

This document provides comprehensive documentation for all test fixtures available in the ProtonFetcher test suite. Fixtures are organized by category and include usage examples.

**Location:** `tests/conftest.py` is a thin re-export layer (it also sets up `sys.path`). The fixtures themselves live in three modular files:

| Module | Contents |
|--------|----------|
| `tests/data.py` | Centralized test data (`test_data`) |
| `tests/factories.py` | Factory fixtures (network, filesystem, archive) |
| `tests/fixtures.py` | Clients, environment, fork parametrization, component (SUT), and mock-helper fixtures |

## Fixture Categories

| Category | Purpose | Key Fixtures |
|----------|---------|--------------|
| **Factories** | Configurable mock/object creation | `mock_network_factory`, `mock_filesystem_factory`, `sample_archive_factory` |
| **Data** | Centralized test data | `test_data` |
| **Clients** | Pre-configured protocol mocks | `mock_network_client`, `mock_filesystem_client` |
| **Archives** | Real archive files | `sample_tar_gz_archive`, `sample_tar_xz_archive` |
| **Environment** | Directory structures & symlink envs | `temp_environment`, `extract_dir`, `installed_proton_versions`, `symlink_environment` |
| **Fork Parametrization** | Multi-fork test coverage | `fork` |
| **Component (SUT)** | System-under-test instances | `link_manager` |
| **Mock Helpers** | Low-level patch factories | `mock_tarfile_operations`, `mock_urllib_download`, `mock_subprocess_tar`, `mock_builtin_open` |

## Factory Fixtures

### `mock_network_factory`

**Purpose:** Create a configured `NetworkClientProtocol` mock.

**Returns:** `MagicMock(spec=NetworkClientProtocol)` — `get()` and `head()` return `HttpResponse` objects.

**Parameters:**
- `get_response` (dict | str | None): JSON body for GET (dicts are auto-serialized); default is a sample assets payload
- `head_response` (dict | str | None): header dump for HEAD (dicts are converted to `key: value` lines); a `Location` header sets `final_url`
- `rate_limit` (bool): GET returns a 403 rate-limit response
- `not_found` (bool): GET and HEAD both return 404
- `custom_returncode` (int | None): overrides the status code (22 maps to 404)

**Usage:**
```python
def test_default(mock_network_factory):
    mock_network = mock_network_factory()

def test_custom_response(mock_network_factory):
    mock_network = mock_network_factory(
        get_response={"assets": [{"name": "test.tar.gz", "size": 1024}]},
    )

def test_rate_limit(mock_network_factory):
    mock_network = mock_network_factory(rate_limit=True)

def test_not_found(mock_network_factory):
    mock_network = mock_network_factory(not_found=True)
```

---

### `mock_filesystem_factory`

**Purpose:** Create a configured `FileSystemClientProtocol` mock.

**Returns:** `MagicMock(spec=FileSystemClientProtocol)`

**Parameters:**
- `exists_map` (dict[str, bool] | None): path → exists; default `True`
- `is_dir_map` (dict[str, bool] | None): path → is_dir; default `True`
- `is_symlink_map` (dict[str, bool] | None): path → is_symlink; default `False`
- `read_map` (dict[str, bytes] | None): path → bytes; default `b"test content"`
- `size_map` (dict[str, int] | None): path → size; default `1048576`
- `use_tmp_path` (bool): bind every method to real `Path` operations (exists, is_dir, is_symlink, read/write bytes, stat, mkdir, iterdir, symlink_to, resolve, unlink, rmtree)

**Usage:**
```python
def test_with_custom_structure(mock_filesystem_factory):
    mock_fs = mock_filesystem_factory(
        exists_map={"/dir": True, "/file": True},
        is_dir_map={"/dir": True, "/file": False},
        read_map={"/file": b"content"},
    )

def test_with_real_tmp(mock_filesystem_factory):
    mock_fs = mock_filesystem_factory(use_tmp_path=True)
```

---

### `sample_archive_factory`

**Purpose:** Create real archive files for extraction tests.

**Returns:** `Path` to a real archive under `tmp_path`.

**Parameters:**
- `format` (str): `"gz"` → `{tag}.tar.gz`; anything else → `proton-{tag}.tar.xz`
- `tag` (str): archive tag / top-level directory name; default `"GE-Proton10-20"`
- `files` (list[tuple[str, str]] | None): `(relative_path, content)` entries; default `[("version", tag), ("file.txt", "test content")]`

**Usage:**
```python
def test_default_archive(sample_archive_factory):
    archive = sample_archive_factory()

def test_custom_structure(sample_archive_factory):
    archive = sample_archive_factory(
        format="xz",
        tag="EM-10.0-30",
        files=[
            ("version", "EM-10.0-30"),
            ("lib/libwine.so", "fake libwine"),
        ],
    )
```

## Test Data Fixtures

### `test_data`

**Purpose:** Centralized test data for all test scenarios (fork repos, example tags/assets, archive formats, CLI output markers).

**Returns:** `dict[str, Any]` with:
- `FORKS`: `dict[ForkName, dict]` — per-fork `repo`, `example_tag`, `example_asset`, `archive_format`
- `CLI_OUTPUTS`: `success` / `error_prefix` strings
- `GITHUB_API`: `rate_limit_message` / `not_found` markers

**Usage:**
```python
def test_fork_configuration(test_data: dict[str, Any], fork: ForkName):
    repo = test_data["FORKS"][fork]["repo"]
    example_tag = test_data["FORKS"][fork]["example_tag"]
    example_asset = test_data["FORKS"][fork]["example_asset"]

def test_cli_output(capsys):
    ...
    assert test_data["CLI_OUTPUTS"]["success"] in output
```

## Parametrized Fork Fixtures

### `fork`

**Purpose:** Parametrized fixture for testing all forks.

**Returns:** `ForkName` — parametrized over `GE_PROTON`, `PROTON_EM`, `CACHYOS`, `DW_PROTON`.

**Usage:**
```python
def test_fork_behavior(fork: ForkName, test_data: dict[str, Any]):
    repo = test_data["FORKS"][fork]["repo"]
```

Per-fork values (repo, example tag, example asset, archive format, link names) come from the `test_data` fixture. Fork-aware environment fixtures (`installed_proton_versions`, `symlink_environment`) read `fork` automatically, so they are parametrized too when used.

## Sample Archive Fixtures

### `sample_tar_gz_archive` / `sample_tar_xz_archive`

**Purpose:** Pre-built sample archives (backward-compat sugar over `sample_archive_factory`).

**Returns:** `Path` to a real archive under `tmp_path`.

| Fixture | Equivalent call |
|---------|-----------------|
| `sample_tar_gz_archive` | `sample_archive_factory(format="gz", tag="GE-Proton10-20")` |
| `sample_tar_xz_archive` | `sample_archive_factory(format="xz", tag="EM-10.0-30")` |

**Usage:**
```python
def test_extraction(sample_tar_gz_archive: Path):
    # sample_tar_gz_archive is a real .tar.gz ready to extract
```

## Environment Fixtures

### `temp_environment`

**Purpose:** Create temporary directories for testing workflows.

**Returns:** `dict[str, Path]` — `{"tmp": tmp_path, "output_dir": tmp_path/"Downloads", "extract_dir": tmp_path/"compatibilitytools.d"}`

**Usage:**
```python
def test_download_workflow(temp_environment: dict[str, Path]):
    output_dir = temp_environment["output_dir"]
    extract_dir = temp_environment["extract_dir"]

    archive_path = output_dir / "test.tar.gz"
    # ...
```

---

### `extract_dir`

**Purpose:** Create a temporary extract directory.

**Returns:** `Path` (`tmp_path/"compatibilitytools.d"`)

**Usage:**
```python
def test_extraction(extract_dir: Path):
    # extract_dir is a temporary directory ready for use
    target = extract_dir / "GE-Proton10-20"
    # ...
```

---

### `installed_proton_versions`

**Purpose:** Fork-aware fake installed Proton version directories.

**Parameters:** uses the `fork` fixture (auto-parametrized over all 4 forks).

**Returns:** `list[Path]` — 3 version directories (newest first) under a temp `compatibilitytools.d`, each containing a `version` file.

| Fork | Directory naming |
|------|------------------|
| GE-Proton | `GE-Proton10-20`, `GE-Proton10-19`, `GE-Proton10-18` |
| Proton-EM | `proton-EM-10.0-30`, `proton-EM-10.0-29`, `proton-EM-10.0-28` |
| CachyOS | `proton-cachyos-10.0-20260207-slr-x86_64`, `...-20260206-...`, `...-20260205-...` |
| DW-Proton | `dwproton-10.0-26-x86_64`, `dwproton-10.0-25-x86_64`, `dwproton-10.0-24-x86_64` |

**Usage:**
```python
def test_prune_candidates(installed_proton_versions: list[Path]):
    assert len(installed_proton_versions) == 3
    assert installed_proton_versions[0].name.endswith(("10-20", "10.0-30", "slr-x86_64", "x86_64"))
```

---

### `symlink_environment`

**Purpose:** Complete symlink testing environment (version dirs + live symlinks), fork-aware.

**Returns:** `SymlinkEnvironment` TypedDict:
- `extract_dir` (Path)
- `version_dirs` (list[Path]) — 3 newest-first version directories
- `symlinks` (dict[str, Path]) — link name → link path
- `link_names` (list[str]) — `[main, -Fallback, -Fallback2]`
- `fork` (ForkName)

**Usage:**
```python
def test_symlink_workflow(symlink_environment: SymlinkEnvironment):
    extract_dir = symlink_environment["extract_dir"]
    fork = symlink_environment["fork"]

    # symlinks are live, pointing at the newest version dirs
    main_link = symlink_environment["symlinks"][symlink_environment["link_names"][0]]
    assert main_link.is_symlink()
```

## Component Fixtures (SUT Factories)

Component fixtures create instances of the System Under Test (SUT) with mocked dependencies. Only `LinkManager` keeps a dedicated fixture; the other SUTs (`ReleaseManager`, `AssetDownloader`, `ArchiveExtractor`, fetchers) are constructed inline in tests using the factory fixtures.

### `link_manager`

**Purpose:** Create `LinkManager` with mocked dependencies.

**Returns:** `LinkManager` instance (`LinkManager(mock_filesystem_client, DEFAULT_TIMEOUT)`)

**Dependencies:** `mock_filesystem_client`

**Usage:**
```python
def test_symlink_creation(link_manager: LinkManager, mock_filesystem_factory, tmp_path):
    mock_fs = mock_filesystem_factory(use_tmp_path=True)
    link_manager.file_system_client = mock_fs

    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()

    version_dir = extract_dir / "GE-Proton10-20"
    version_dir.mkdir()

    link_manager.create_symlinks(
        main=extract_dir / "GE-Proton",
        fb1=extract_dir / "GE-Proton-Fallback",
        fb2=extract_dir / "GE-Proton-Fallback2",
        top_3=[(("GE-Proton", 10, 20, 0), version_dir)],
    )

    assert (extract_dir / "GE-Proton").is_symlink()
```

## Helper Fixtures

### `mock_network_client` / `mock_filesystem_client`

**Purpose:** Default pre-configured protocol mocks (backward-compat sugar over the factories).

**Returns:**
- `mock_network_client` → `mock_network_factory(get_response={"tag_name": "GE-Proton10-20"})`
- `mock_filesystem_client` → `mock_filesystem_factory()`

**Usage:**
```python
def test_with_default_network(mock_network_client):
    response = mock_network_client.get("https://api.github.com/repos/...")
    assert response.status == 200
```

---

### `mock_tarfile_operations`

**Purpose:** Mock tarfile operations for extraction testing (covers the native Python 3.14 streaming path).

**Patches:** `tarfile.open`, `protonfetcher.archive_extractor.os.path.getsize` (returns 1024), `builtins.open`, and `ArchiveExtractor._open_decompressor`.

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

**Purpose:** Mock the system `tar` subprocess command for fallback testing.

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

**Purpose:** Mock built-in `open()` to capture writes without creating real files.

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

### DO: Use `test_data` for Fork-Specific Values

```python
# ✅ CORRECT: Centralized data
def test_fork_repo(test_data: dict[str, Any], fork: ForkName):
    repo = test_data["FORKS"][fork]["repo"]
```

### DON'T: Hardcode Fork Values

```python
# ❌ WRONG: Duplicated fork knowledge
def test_fork_repo():
    assert repo == "GloriousEggroll/proton-ge-custom"
```

### DO: Use Environment Fixtures for Directory Trees

```python
# ✅ CORRECT: Environment fixture
def test_prune(installed_proton_versions: list[Path]):
    ...
```

### DON'T: Build Directory Trees Manually

```python
# ❌ WRONG: Rebuilding what a fixture already provides
def test_prune(tmp_path):
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir()
    for version in ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]:
        ...
```

## Migration Guide (Removed Fixtures → Current)

| Removed Fixture | Current Replacement |
|-----------------|---------------------|
| `fork_repo` | `test_data["FORKS"][fork]["repo"]` |
| `fork_archive_format` | `test_data["FORKS"][fork]["archive_format"]` |
| `fork_link_names` | `symlink_environment["link_names"]` |
| `test_environment_builder` | Environment fixtures directly (`temp_environment`, `extract_dir`, `installed_proton_versions`, `symlink_environment`) |
| `output_dir` | `temp_environment["output_dir"]` |
| `release_manager` | Construct `ReleaseManager` inline with factory mocks |
| `asset_downloader` | Construct `AssetDownloader` inline with factory mocks |
| `archive_extractor` | Construct `ArchiveExtractor` inline with factory mocks |
| `github_fetcher` | Construct `GitHubReleaseFetcher` inline with factory mocks |
| `release_assets` / `github_release_response` / `recent_releases` | `test_data` + inline data |
| `mock_network_with_rate_limit` | `mock_network_factory(rate_limit=True)` |
| `mock_filesystem_with_directory_structure` | `mock_filesystem_factory(exists_map=..., is_dir_map=...)` |

---

*Last updated: 2026-07-16*
