# ProtonFetcher Test Suite — Code Navigation Map

> Mermaid-first reference. For fixture docs, see [`FIXTURES.md`](FIXTURES.md).

---

## 1. Test Priority Pyramid

```mermaid
graph TD
    subgraph E2E["E2E — Complete User Journeys (Highest Priority)"]
        E2E_CLI["test_cli.py"]
        E2E_PRUNE["test_prune.py"]
        E2E_RELEASE["test_release_manager_e2e.py"]
    end

    subgraph INTEGRATION["Integration — Component Interaction (High Priority)"]
        INT_LINK["test_link_manager_e2e.py"]
        INT_RELEASE["test_release_manager_e2e.py"]
        INT_INTEGRATION["test_integration.py"]
    end

    subgraph UNIT["Unit — Logic & Edge Cases (As Needed)"]
        UT_UTILS["test_utils.py"]
        UT_BASE["test_base_release_fetcher.py"]
        UT_FORGEJO["test_forgejo_fetcher.py"]
    end

    E2E_CLI --> INTEGRATION
    E2E_PRUNE --> INTEGRATION
    E2E_RELEASE --> INTEGRATION
    INTEGRATION --> UNIT
```

---

## 2. Test File → Source Module Mapping

```mermaid
graph LR
    subgraph TESTS["tests/"]
        T_CLI["test_cli.py<br/>31 tests"]
        T_DISPATCH["test_cli_dispatch.py<br/>30 tests"]
        T_BASE["test_base_release_fetcher.py<br/>25 tests"]
        T_PRUNE["test_prune.py<br/>27 tests"]
        T_PRUNE_OPS["test_prune_operations.py<br/>20 tests"]
        T_VERSION["test_version_finder.py<br/>19 tests"]
        T_RELEASE_E2E["test_release_manager_e2e.py<br/>28 tests"]
        T_INTEGRATION["test_integration.py<br/>22 tests"]
        T_LINK_STATUS["test_link_status.py<br/>16 tests"]
        T_RELEASE_OPS["test_release_operations.py<br/>16 tests"]
        T_FORGEJO["test_forgejo_fetcher.py<br/>23 tests"]
        T_SYMLINK_OPS["test_symlink_operations.py<br/>14 tests"]
        T_CLI_HANDLERS["test_cli_handlers.py<br/>9 tests"]
        T_CLI_VALIDATORS["test_cli_validators.py<br/>7 tests"]
        T_GITHUB["test_github_fetcher.py<br/>12 tests"]
        T_EXTRACTION["test_extraction.py<br/>12 tests"]
        T_LINK_MGR["test_link_manager_e2e.py<br/>10 tests"]
        T_UTILS["test_utils.py<br/>10 tests"]
        C["conftest.py<br/>shared fixtures"]
    end

    subgraph SRC["src/protonfetcher/"]
        S_CLI["cli.py"]
        S_FETCHER["base_release_fetcher.py"]
        S_GITHUB["github_fetcher.py"]
        S_FORGEJO["forgejo_fetcher.py"]
        S_LINK["link_manager.py"]
        S_LINK_STATUS["link_status.py"]
        S_RELEASE["release_manager.py"]
        S_RELEASE_OPS["release_operations.py"]
        S_PRUNE_OPS["prune_operations.py"]
        S_EXTRACTION["archive_extractor.py"]
        S_DOWNLOAD["asset_downloader.py"]
        S_NETWORK["network.py"]
        S_FS["filesystem.py"]
        S_ADAPTER["platform_adapters.py"]
        S_COMMON["common.py"]
        S_UTILS["utils.py"]
        S_SPINNER["spinner.py"]
        S_VERSION["version_finder.py"]
        S_CANDIDATE["candidate_selection.py"]
        S_SYMLINK_OPS["symlink_operations.py"]
    end

    T_CLI --> S_CLI
    T_DISPATCH --> S_CLI
    T_DISPATCH --> S_GITHUB & S_FORGEJO
    T_CLI_HANDLERS --> S_CLI
    T_CLI_VALIDATORS --> S_CLI
    T_BASE --> S_FETCHER
    T_PRUNE --> S_LINK & S_CLI
    T_PRUNE_OPS --> S_PRUNE_OPS & S_VERSION
    T_LINK_STATUS --> S_LINK_STATUS & S_COMMON
    T_RELEASE_OPS --> S_RELEASE_OPS & S_FS
    T_RELEASE_E2E --> S_RELEASE & S_ADAPTER
    T_GITHUB --> S_GITHUB & S_FETCHER
    T_FORGEJO --> S_FORGEJO & S_ADAPTER
    T_EXTRACTION --> S_EXTRACTION & S_DOWNLOAD
    T_INTEGRATION --> S_NETWORK & S_SPINNER
    T_UTILS --> S_UTILS
    T_VERSION --> S_VERSION
    T_SYMLINK_OPS --> S_SYMLINK_OPS & S_COMMON
    T_LINK_MGR --> S_LINK & S_FS
    C --> TESTS
```

---

## 3. Adapter-Based Architecture & Test Implications

```mermaid
classDiagram
    class BaseReleaseFetcher {
        +platform: str
        +release_manager: ReleaseManager
        +fetch_and_extract()
        +check_for_newer()
        +remove_release()
        +relink_fork()
        +update_all_managed_forks()
    }

    class GitHubReleaseFetcher {
        <<marker>>
        platform = "github"
    }

    class ForgejoReleaseFetcher {
        <<marker>>
        platform = "forgejo"
    }

    class PlatformAdapter {
        <<protocol>>
        +api_base: str
        +host_base: str
        +default_headers: dict
        +build_api_url()
        +build_download_url()
        +build_host_url()
    }

    class GitHubPlatformAdapter {
        api_base = "https://api.github.com"
    }

    class ForgejoPlatformAdapter {
        api_base = "https://dawn.wine/api/v1"
    }

    class ReleaseManager {
        +platform_adapter: PlatformAdapter
        +find_asset()
        +list_recent_releases()
    }

    class ForkConfig {
        +platform: str
        +repo: str
        +archive_format: str
        +version_pattern: str
    }

    BaseReleaseFetcher <|-- GitHubReleaseFetcher
    BaseReleaseFetcher <|-- ForgejoReleaseFetcher
    BaseReleaseFetcher o-- ReleaseManager
    ReleaseManager o-- PlatformAdapter
    PlatformAdapter <|.. GitHubPlatformAdapter
    PlatformAdapter <|.. ForgejoPlatformAdapter
    ForkConfig --> BaseReleaseFetcher : "platform field selects adapter"

    note for GitHubReleaseFetcher["~28 lines, zero overrides<br/>Test: adapter selection + URL delegation"]
    note for ForgejoReleaseFetcher["~28 lines, zero overrides<br/>Test: adapter selection + URL delegation"]
    note for BaseReleaseFetcher["~400 lines, ALL logic<br/>Test: test_base_release_fetcher.py (20 tests)"]
    note for PlatformAdapter["URL/header construction<br/>Test: test_forgejo_fetcher.py + test_release_manager_e2e.py (Pattern 8)"]
```

---

## 4. Mocking Strategy & Dependency Injection

```mermaid
graph TB
    subgraph SUT["System Under Test (REAL)"]
        FETCHER["BaseReleaseFetcher<br/>GitHubReleaseFetcher<br/>ForgejoReleaseFetcher"]
        LINK_MGR["LinkManager"]
        RELEASE_MGR["ReleaseManager"]
        EXTRACTOR["ArchiveExtractor"]
    end

    subgraph MOCKS["Mocks (Protocol-Based)"]
        NET_MOCK["mock_network_client<br/>NetworkClientProtocol"]
        FS_MOCK["mock_filesystem_client<br/>FileSystemClientProtocol"]
        TAR_MOCK["mock_tarfile_operations<br/>tarfile.open patch"]
        URL_MOCK["mock_urllib_download<br/>urllib.request.urlopen"]
        SUB_MOCK["mock_subprocess_tar<br/>subprocess.run"]
        OPEN_MOCK["mock_builtin_open<br/>builtins.open"]
    end

    subgraph REAL_FS["Real Filesystem (tmp_path)"]
        SYMLINK["Symlink creation/resolution"]
        DIR_ITER["Directory iteration"]
    end

    FETCHER --> NET_MOCK
    FETCHER --> FS_MOCK
    EXTRACTOR --> TAR_MOCK
    EXTRACTOR --> URL_MOCK
    EXTRACTOR --> SUB_MOCK
    EXTRACTOR --> OPEN_MOCK
    LINK_MGR --> REAL_FS
    RELEASE_MGR --> NET_MOCK

    note for MOCKS["Always mock: network, tarfile,<br/>file read/write, subprocess"]
    note for REAL_FS["Never mock: symlinks<br/>(resolve() breaks with mocks)"]
```

---

## 5. Fixture Dependency Graph

```mermaid
graph TD
    subgraph FACTORIES["Factory Fixtures"]
        NET_FACTORY["mock_network_factory"]
        FS_FACTORY["mock_filesystem_factory"]
        ARCHIVE_FACTORY["sample_archive_factory"]
    end

    subgraph ENVIRONMENT["Environment Fixtures"]
        ENV_BUILDER["test_environment_builder<br/>fluent builder"]
    end

    subgraph DATA["Test Data Fixtures"]
        TEST_DATA["test_data<br/>centralized fork configs"]
        FORK_FIXTURE["fork (parametrized)"]
        FORK_REPO["fork_repo"]
        FORK_FORMAT["fork_archive_format"]
    end

    subgraph COMPONENTS["Component Fixtures"]
        RM_FIXTURE["release_manager"]
        LM_FIXTURE["link_manager"]
        GF_FIXTURE["github_fetcher"]
    end

    subgraph MOCKS["Mock Fixtures"]
        NET_CLIENT["mock_network_client"]
        FS_CLIENT["mock_filesystem_client"]
        TAR_OPS["mock_tarfile_operations"]
        URL_DL["mock_urllib_download"]
        SUB_TAR["mock_subprocess_tar"]
        BUILTIN_OPEN["mock_builtin_open"]
        RATE_LIMIT["mock_network_with_rate_limit"]
    end

    NET_FACTORY --> NET_CLIENT
    NET_FACTORY --> RATE_LIMIT
    FS_FACTORY --> FS_CLIENT
    FS_FACTORY --> LM_FIXTURE
    FS_FACTORY --> RM_FIXTURE
    FS_FACTORY --> GF_FIXTURE
    ARCHIVE_FACTORY --> TAR_OPS

    FORK_FIXTURE --> FORK_REPO
    FORK_FIXTURE --> FORK_FORMAT
    TEST_DATA --> FORK_FIXTURE

    ENV_BUILDER --> COMPONENTS

    NET_CLIENT --> RM_FIXTURE
    NET_CLIENT --> GF_FIXTURE
    FS_CLIENT --> LM_FIXTURE
    FS_CLIENT --> RM_FIXTURE
    FS_CLIENT --> GF_FIXTURE

    style FACTORIES fill:#e1f5e1
    style ENVIRONMENT fill:#e1f0f5
    style DATA fill:#fff4e1
    style COMPONENTS fill:#f5e1f5
    style MOCKS fill:#f5e1e1
```

---

## 6. Test Pattern Catalog

```mermaid
graph TB
    subgraph PATTERNS["8 Test Patterns"]
        P1["P1: Complete Workflow<br/>All mocks → execute → verify interactions"]
        P2["P2: Error Handling<br/>Configure error → assert exception"]
        P3["P3: Parametrized Fork<br/>@parametrize over ForkName enum"]
        P4["P4: Real Integration<br/>tmp_path + real FileSystemClient"]
        P5["P5: CLI Argument Parsing<br/>patch sys.argv → parse → assert"]
        P6["P6: CLI Mocked Fetcher<br/>patch fetcher class → main() → capsys"]
        P7["P7: Feature Test Suite<br/>ArgParse → Flow → Integration → E2E"]
        P8["P8: Platform Adapter<br/>URL construction + header verification"]
    end

    subgraph EXAMPLES["Example Files"]
        E1["test_github_fetcher.py"]
        E2["test_github_fetcher.py"]
        E3["test_link_manager_e2e.py"]
        E4["test_link_manager_e2e.py"]
        E5["test_cli.py::TestArgumentParsing"]
        E6["test_cli.py::TestListReleasesOperation"]
        E7["test_prune.py"]
        E8["test_forgejo_fetcher.py"]
    end

    subgraph NEW_TESTS["New Tests (2026-05)"]
        NT1["TestAdapterSelection<br/>2 tests in test_base_release_fetcher.py"]
        NT2["TestBuildDownloadUrl<br/>2 tests in test_base_release_fetcher.py"]
        NT3["TestHandleAlreadyExtracted<br/>2 tests in test_base_release_fetcher.py"]
        NT4["TestUpdateAllManagedForksPlatformFiltering<br/>2 tests in test_base_release_fetcher.py"]
        NT5["TestForkConfigPlatformDispatch<br/>4 tests in test_cli.py"]
        NT6["TestReleaseManagerForgejoAdapter<br/>5 tests in test_release_manager_e2e.py"]
    end

    P1 --> E1
    P2 --> E2
    P3 --> E3
    P4 --> E4
    P5 --> E5
    P6 --> E6
    P7 --> E7
    P8 --> E8

    style PATTERNS fill:#e1f5e1
    style EXAMPLES fill:#fff4e1
    style NEW_TESTS fill:#e1f0f5
```

---

## 7. Golden Rules

```mermaid
graph LR
    subgraph RULES["5 Golden Rules"]
        R1["Rule 1: Never Mock the SUT<br/>Real class, mocked deps"]
        R2["Rule 2: Real FS for Symlinks<br/>tmp_path + FileSystemClient"]
        R3["Rule 3: Use pytest Features<br/>parametrize, fixtures, capsys, mocker"]
        R4["Rule 4: Test Adapter Selection<br/>Verify platform → adapter mapping"]
        R5["Rule 5: DRY Tests<br/>One behavior per test, no overlap"]
    end

    subgraph VIOLATIONS["Common Violations"]
        V1["❌ mock_github_fetcher.fetch.return_value"]
        V2["❌ LinkManager(mock_fs)"]
        V3["❌ Manual loop over forks"]
        V4["❌ Indirect-only adapter tests"]
        V5["❌ Copy-paste tests"]
    end

    R1 -.-> V1
    R2 -.-> V2
    R3 -.-> V3
    R4 -.-> V4
    R5 -.-> V5

    style RULES fill:#e1f5e1
    style VIOLATIONS fill:#f5e1e1
```

---

## 8. Feature Test Structure (New Feature Checklist)

```mermaid
graph TD
    subgraph FEATURE["New Feature Test Structure (test_prune.py template)"]
        A["Argument Parsing Tests<br/>- CLI flags<br/>- Mutual exclusivity<br/>- Default values"]
        B["Operation Flow Tests<br/>- Happy path<br/>- Dry-run mode<br/>- Confirmation workflow"]
        C["Integration Tests<br/>- Real FileSystemClient<br/>- Symlink protection<br/>- Directory iteration"]
        D["E2E Tests<br/>- Complete workflow<br/>- All forks<br/>- Error recovery"]
        E["Error Handling Tests<br/>- Invalid inputs<br/>- Edge cases<br/>- Exception chaining"]
    end

    A --> B --> C --> D
    E -.-> B
    E -.-> C

    style A fill:#e1f5e1
    style B fill:#e1f5e1
    style C fill:#e1f5e1
    style D fill:#e1f5e1
    style E fill:#fff4e1
```

---

## 9. CLI Operation Test Coverage

```mermaid
graph LR
    subgraph CLI_MAIN["test_cli.py — Main Entry (31 tests)"]
        OP_CHECK["--check<br/>TestCheckOperationFlow<br/>TestCheckCLI"]
        OP_DRYRUN["--dry-run<br/>TestDryRunCLI<br/>TestDryRunWorkflow<br/>TestDryRunOutput<br/>TestDryRunIntegration"]
        OP_LIST["--list<br/>TestListReleasesOperation"]
        OP_LINKS["--list-links<br/>TestListLinksOperation"]
        OP_REMOVE["--remove<br/>TestRemoveOperation"]
        OP_RELINK["--relink<br/>TestRelinkOperation"]
        OP_DOWNLOAD["--download<br/>TestDownloadOperation"]
        OP_PRUNE["--prune<br/>test_prune.py"]
        OP_FORK["--fork flag<br/>TestForkConversion<br/>TestForkFlagWithoutValue"]
        OP_DEBUG["--debug<br/>TestDebugLogging"]
        OP_ERROR["Error handling<br/>TestErrorHandling"]
    end

    subgraph CLI_DISPATCH["test_cli_dispatch.py — Dispatch Logic (30 tests)"]
        DD["Operation routing per flag<br/>30 tests<br/>Verify _dispatch() paths"]
    end

    subgraph CLI_HANDLERS["test_cli_handlers.py — Handler Functions (9 tests)"]
        DH["_handle_* functions<br/>9 tests<br/>Verify handler behavior"]
    end

    subgraph CLI_VALIDATORS["test_cli_validators.py — Validation (7 tests)"]
        DV["Mutual exclusivity, defaults<br/>7 tests<br/>Verify _validate_* functions"]
    end

    subgraph PARSING["Argument Parsing"]
        PARSE["TestArgumentParsing<br/>test_cli.py"]
    end

    subgraph VERSIONS["Version Checks"]
        INSTALLED["TestGetInstalledVersions"]
        UPDATES["TestCheckForUpdates"]
        NEWER["TestCheckForNewerRelease"]
    end

    PARSING --> CLI_MAIN
    VERSIONS --> OP_CHECK
    CLI_MAIN --> CLI_DISPATCH
    CLI_MAIN --> CLI_HANDLERS
    CLI_MAIN --> CLI_VALIDATORS

    style CLI_MAIN fill:#e1f5e1
    style CLI_DISPATCH fill:#fff4e1
    style CLI_HANDLERS fill:#fff4e1
    style CLI_VALIDATORS fill:#fff4e1
    style PARSING fill:#fff4e1
    style VERSIONS fill:#fff4e1
```

---

## 10. Test Execution Flow — What Happens When You Run `pytest`

```mermaid
sequenceDiagram
    autonumber
    participant PY as pytest
    participant CF as conftest.py
    participant FIX as Fixtures (factories, mocks, env)
    participant SUT as SUT (real classes)
    participant MOCK as Mocks (network, fs, tar)
    participant FS as Real FS (tmp_path)

    PY->>CF: Load shared fixtures
    CF->>FIX: Register factories, mock fixtures, test_data
    PY->>FIX: Resolve fixture dependencies per test
    FIX->>MOCK: Create protocol-based mocks
    FIX->>SUT: Instantiate real SUT with mocked deps

    alt Symlink test (LinkManager)
        FIX->>FS: Create tmp_path directories
        SUT->>FS: Real symlink operations
        FS-->>SUT: resolve() works correctly
    else Network/Extraction test
        SUT->>MOCK: Call mocked network/fs
        MOCK-->>SUT: Return configured responses
    end

    PY->>SUT: Execute test assertions
    PY->>PY: Pass/Fail + coverage
```

---

## 11. Adding a New Platform — Test Flow

```mermaid
graph TD
    subgraph STEP1["1. PlatformAdapter"]
        A1["Create adapter in platform_adapters.py"]
        A2["Set api_base, host_base, headers"]
        A3["Implement URL builders"]
    end

    subgraph STEP2["2. Marker Fetcher"]
        B1["Create subclass of BaseReleaseFetcher"]
        B2["Set platform = 'new-platform'"]
        B3["Zero method overrides"]
    end

    subgraph STEP3["3. ForkConfig"]
        C1["Add entry in common.py"]
        C2["Set platform field"]
        C3["Configure repo, archive, version"]
    end

    subgraph STEP4["4. Tests (11+ new tests)"]
        D1["PlatformAdapter URL tests<br/>(Pattern 8, test_forgejo_fetcher.py)"]
        D2["Adapter selection test<br/>(TestAdapterSelection, test_base_release_fetcher.py)"]
        D3["ForkConfig.platform dispatch test<br/>(TestForkConfigPlatformDispatch, test_cli.py)"]
        D4["update_all_managed_forks filter test<br/>(TestUpdateAllManagedForksPlatformFiltering)"]
        D5["_build_download_url delegation test<br/>(TestBuildDownloadUrl)"]
        D6["ReleaseManager adapter integration<br/>(TestReleaseManagerForgejoAdapter)"]
    end

    A1 --> A2 --> A3
    B1 --> B2 --> B3
    C1 --> C2 --> C3
    D1 --> D2 --> D3 --> D4

    A3 -.-> D1
    B3 -.-> D2
    C3 -.-> D3
    B2 -.-> D5
    A1 -.-> D6

    style STEP1 fill:#e1f5e1
    style STEP2 fill:#e1f5e1
    style STEP3 fill:#e1f5e1
    style STEP4 fill:#fff4e1
```

---

## 12. New Source Modules — Extracted from LinkManager

> LinkManager (~400 lines) was refactored into 5 focused modules. Each has its own test file.

```mermaid
graph LR
    subgraph EXTRACTED["Extracted Modules"]
        VF["version_finder.py<br/>Version discovery & dedup<br/>find_version_candidates()"]
        CS["candidate_selection.py<br/>Top-3 candidate selection<br/>select_top_3_candidates()"]
        LS["link_status.py<br/>Read-only link inspection<br/>list_links(), get_link_status()"]
        SO["symlink_operations.py<br/>Symlink CRUD<br/>create_symlink_specs(), cleanup_symlinks()"]
        PO["prune_operations.py<br/>Prune plan & execution<br/>get_installed_versions(), execute_prune()"]
        RO["release_operations.py<br/>Release removal<br/>remove_release()"]
    end

    subgraph TESTS["Test Files"]
        TVF["test_version_finder.py<br/>19 tests"]
        TLS["test_link_status.py<br/>16 tests"]
        TSO["test_symlink_operations.py<br/>14 tests"]
        TPO["test_prune_operations.py<br/>20 tests"]
        TRO["test_release_operations.py<br/>16 tests"]
    end

    VF --> TVF
    CS -.-> TVF
    LS --> TLS
    SO --> TSO
    PO --> TPO
    RO --> TRO

    style EXTRACTED fill:#e1f5e1
    style TESTS fill:#fff4e1
```

**Module responsibilities:**

| Module                   | Responsibility                                | Key Functions                                  |
| ------------------------ | --------------------------------------------- | ---------------------------------------------- |
| `version_finder.py`      | Scan directories, parse versions, deduplicate | `find_version_candidates()`                    |
| `candidate_selection.py` | Select top-3 candidates for symlinks          | `select_top_3_candidates()`                    |
| `link_status.py`         | Read-only link inspection                     | `list_links()`, `get_link_status()`            |
| `symlink_operations.py`  | Symlink CRUD (create, cleanup, manage)        | `create_symlink_specs()`, `cleanup_symlinks()` |
| `prune_operations.py`    | Prune plan computation & execution            | `get_installed_versions()`, `execute_prune()`  |
| `release_operations.py`  | Remove specific releases                      | `remove_release()`                             |

---

## 13. Coverage Strategy — What Gets Covered by What

```mermaid
graph TD
    subgraph E2E_COV["One E2E Test Covers 8+ Modules"]
        USER["User: 'fetch latest GE-Proton'"]
        CLI_MOD["cli.py — argument parsing"]
        FETCHER_MOD["github_fetcher.py — orchestrate()"]
        RELEASE_MOD["release_manager.py — find_asset()"]
        DOWNLOAD_MOD["asset_downloader.py — download()"]
        EXTRACT_MOD["archive_extractor.py — extract()"]
        VERSION_MOD["version_finder.py — discover versions"]
        CANDIDATE_MOD["candidate_selection.py — select top-3"]
        SYMLINK_MOD["symlink_operations.py — create symlinks"]
        LINK_STATUS_MOD["link_status.py — verify links"]
        RESULT["Symlinks created ✓"]
    end

    USER --> CLI_MOD --> FETCHER_MOD --> RELEASE_MOD --> DOWNLOAD_MOD --> EXTRACT_MOD --> VERSION_MOD --> CANDIDATE_MOD --> SYMLINK_MOD --> LINK_STATUS_MOD --> RESULT

    style E2E_COV fill:#e1f5e1
```

---

## 14. Test Suite Statistics & Quick Reference

```mermaid
mindmap
    root((Test Suite - 331 tests))
        Files
            conftest.py - shared fixtures
            test_cli.py - 31 tests - CLI main entry
            test_cli_dispatch.py - 30 tests - CLI dispatch logic
            test_base_release_fetcher.py - 25 tests - shared workflow
            test_prune.py - 27 tests - prune feature
            test_release_manager_e2e.py - 28 tests - discovery
            test_integration.py - 22 tests - NetworkClient, Spinner
            test_prune_operations.py - 20 tests - prune standalone ops
            test_version_finder.py - 19 tests - version discovery
            test_link_status.py - 16 tests - link inspection
            test_release_operations.py - 16 tests - release removal
            test_forgejo_fetcher.py - 23 tests - Forgejo + adapters
            test_symlink_operations.py - 14 tests - symlink CRUD
            test_github_fetcher.py - 12 tests - GitHub edge cases
            test_extraction.py - 12 tests - archive extraction
            test_link_manager_e2e.py - 10 tests - symlink E2E
            test_utils.py - 10 tests - version parsing
            test_cli_handlers.py - 9 tests - CLI handler functions
            test_cli_validators.py - 7 tests - CLI validation
        Stats
            18 test files
            331 tests total
            ~85% coverage
            <0.5s execution
        Markers
            integration
            unit
            slow
        Commands
            uv run pytest -xvs
            uv run pytest -k ge_proton
            uv run pytest --cov=protonfetcher
            uv run make quality
        Recent Additions
            2026-05 - 8 new test files (323 → 331)
            CLI split: dispatch, handlers, validators
            New modules: version_finder, prune_operations,
            release_operations, symlink_operations,
            link_status, candidate_selection
            Adapter selection tests
            URL delegation tests
            Platform dispatch tests
            ReleaseManager adapter tests
```

---

## 15. conftest.py Fixture Architecture

```mermaid
graph TB
    subgraph ROOT["conftest.py — Fixture Hierarchy"]
        subgraph PARAM["Parametrized Fixtures"]
            FORK["fork<br/>params=[GE_PROTON, PROTON_EM, CACHYOS]"]
        end

        subgraph FACTORY_FIXTURES["Factory Fixtures"]
            NET_FACT["mock_network_factory<br/>configurable mock creation"]
            FS_FACT["mock_filesystem_factory<br/>configurable FS mock"]
            ARCH_FACT["sample_archive_factory<br/>tarball simulation"]
        end

        subgraph MOCK_FIXTURES["Mock Fixtures"]
            MC_NET["mock_network_client"]
            MC_FS["mock_filesystem_client"]
            MC_TAR["mock_tarfile_operations"]
            MC_URL["mock_urllib_download"]
            MC_SUB["mock_subprocess_tar"]
            MC_OPEN["mock_builtin_open"]
            MC_RATE["mock_network_with_rate_limit"]
        end

        subgraph DATA_FIXTURES["Data Fixtures"]
            TDATA["test_data<br/>fork configurations"]
            FREPO["fork_repo"]
            FFORMAT["fork_archive_format"]
        end

        subgraph ENV_FIXTURES["Environment Fixtures"]
            ENVB["test_environment_builder<br/>fluent builder pattern"]
        end

        subgraph SUT_FIXTURES["SUT Fixtures"]
            FMGR["release_manager"]
            LMGR["link_manager"]
            GFETCH["github_fetcher"]
        end

        FORK --> FREPO
        FORK --> FFORMAT
        TDATA --> FORK

        NET_FACT --> MC_NET
        NET_FACT --> MC_RATE
        FS_FACT --> MC_FS

        MC_NET --> FMGR
        MC_NET --> GFETCH
        MC_FS --> LMGR
        MC_FS --> FMGR
        MC_FS --> GFETCH
        ENVB --> SUT_FIXTURES
    end

    style ROOT fill:#f0f0f0
    style PARAM fill:#e1f5e1
    style FACTORY_FIXTURES fill:#fff4e1
    style MOCK_FIXTURES fill:#f5e1e1
    style DATA_FIXTURES fill:#e1f0f5
    style ENV_FIXTURES fill:#f5e1f5
    style SUT_FIXTURES fill:#e1f5e1
```

---

## 16. New Test Classes — 2026-05 Refinement

```mermaid
graph TB
    subgraph NEW_CLASSES["8 New Test Files (323 → 331)"]
        subgraph BASE_TESTS["test_base_release_fetcher.py — 8 tests"]
            AT["TestAdapterSelection<br/>2 tests<br/>Verify adapter per fetcher"]
            BD["TestBuildDownloadUrl<br/>2 tests<br/>Verify URL per platform"]
            HA["TestHandleAlreadyExtracted<br/>2 tests<br/>Verify DRY helper behavior"]
            UF["TestUpdateAllManagedForksPlatformFiltering<br/>2 tests<br/>Verify platform filtering"]
        end

        subgraph CLI_TESTS["test_cli.py + test_cli_dispatch.py — 4 tests"]
            FD["TestForkConfigPlatformDispatch<br/>4 tests<br/>Verify CLI dispatch per fork"]
        end

        subgraph RM_TESTS["test_release_manager_e2e.py — 5 tests"]
            RA["TestReleaseManagerForgejoAdapter<br/>5 tests<br/>Verify adapter integration"]
        end

        subgraph FJ_TESTS["test_forgejo_fetcher.py — 1 test"]
            GA["test_github_adapter_url_construction<br/>1 test<br/>Symmetric adapter tests"]
        end

        subgraph CLI_SPLIT["test_cli_dispatch.py — 30 tests"]
            CD["CLI dispatch logic<br/>30 tests<br/>Verify operation routing per flag"]
        end

        subgraph CLI_HANDLERS["test_cli_handlers.py — 9 tests"]
            CH["CLI handler functions<br/>9 tests<br/>Verify _handle_* function behavior"]
        end

        subgraph CLI_VALIDATORS["test_cli_validators.py — 7 tests"]
            CV["CLI validation<br/>7 tests<br/>Verify mutual exclusivity, defaults"]
        end

        subgraph PRUNE_OPS["test_prune_operations.py — 20 tests"]
            PO["prune_operations.py<br/>20 tests<br/>Standalone prune functions"]
        end

        subgraph VERSION["test_version_finder.py — 19 tests"]
            VF["version_finder.py<br/>19 tests<br/>Version discovery & dedup"]
        end

        subgraph LINK_STATUS["test_link_status.py — 16 tests"]
            LS["link_status.py<br/>16 tests<br/>Read-only link inspection"]
        end

        subgraph RELEASE_OPS["test_release_operations.py — 16 tests"]
            RO["release_operations.py<br/>16 tests<br/>Release removal functions"]
        end

        subgraph SYMLINK_OPS["test_symlink_operations.py — 14 tests"]
            SO["symlink_operations.py<br/>14 tests<br/>Symlink CRUD operations"]
        end
    end

    AT --> BASE_TESTS
    BD --> BASE_TESTS
    HA --> BASE_TESTS
    UF --> BASE_TESTS
    FD --> CLI_TESTS
    RA --> RM_TESTS
    GA --> FJ_TESTS
    CD --> CLI_SPLIT
    CH --> CLI_HANDLERS
    CV --> CLI_VALIDATORS
    PO --> PRUNE_OPS
    VF --> VERSION
    LS --> LINK_STATUS
    RO --> RELEASE_OPS
    SO --> SYMLINK_OPS

    style NEW_CLASSES fill:#e1f5e1
    style BASE_TESTS fill:#e1f0f5
    style CLI_TESTS fill:#fff4e1
    style RM_TESTS fill:#f5e1e1
    style FJ_TESTS fill:#e1f5e1
    style CLI_SPLIT fill:#e1f5e1
    style CLI_HANDLERS fill:#e1f5e1
    style CLI_VALIDATORS fill:#e1f5e1
    style PRUNE_OPS fill:#e1f5e1
    style VERSION fill:#e1f5e1
    style LINK_STATUS fill:#e1f5e1
    style RELEASE_OPS fill:#e1f5e1
    style SYMLINK_OPS fill:#e1f5e1
```

### Test Class Summary

| Class                                        | File                                   | Tests | Purpose                                                    |
| -------------------------------------------- | -------------------------------------- | ----- | ---------------------------------------------------------- |
| `TestAdapterSelection`                       | `test_base_release_fetcher.py`         | 2     | Verify `github_adapter` / `forgejo_adapter` selection      |
| `TestBuildDownloadUrl`                       | `test_base_release_fetcher.py`         | 2     | Verify `_build_download_url` delegates to adapter          |
| `TestHandleAlreadyExtracted`                 | `test_base_release_fetcher.py`         | 2     | Verify DRY helper: skip vs. update paths                   |
| `TestUpdateAllManagedForksPlatformFiltering` | `test_base_release_fetcher.py`         | 2     | Verify GitHub/Forgejo fork filtering                       |
| `TestForkConfigPlatformDispatch`             | `test_cli.py` + `test_cli_dispatch.py` | 4     | Verify CLI dispatches DW-Proton→Forgejo, others→GitHub     |
| `TestReleaseManagerForgejoAdapter`           | `test_release_manager_e2e.py`          | 5     | Verify adapter injection, URL construction, URL difference |
| `test_github_adapter_url_construction`       | `test_forgejo_fetcher.py`              | 1     | Symmetric to existing `forgejo_adapter` tests              |
| CLI dispatch logic                           | `test_cli_dispatch.py`                 | 30    | Verify operation routing per flag                          |
| CLI handler functions                        | `test_cli_handlers.py`                 | 9     | Verify `_handle_*` function behavior                       |
| CLI validation                               | `test_cli_validators.py`               | 7     | Verify mutual exclusivity, defaults                        |
| prune_operations.py                          | `test_prune_operations.py`             | 20    | Standalone prune functions                                 |
| version_finder.py                            | `test_version_finder.py`               | 19    | Version discovery & dedup                                  |
| link_status.py                               | `test_link_status.py`                  | 16    | Read-only link inspection                                  |
| release_operations.py                        | `test_release_operations.py`           | 16    | Release removal functions                                  |
| symlink_operations.py                        | `test_symlink_operations.py`           | 14    | Symlink CRUD operations                                    |
