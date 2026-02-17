"""
Shared pytest configuration and fixtures for ProtonFetcher test suite.

This module provides comprehensive fixtures for e2e and integration testing,
following the protocol-based design of ProtonFetcher.
"""

import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest

# Add src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from protonfetcher.common import (
    DEFAULT_TIMEOUT,
    FileSystemClientProtocol,
    ForkName,
    NetworkClientProtocol,
)

# =============================================================================
# Centralized Test Data
# =============================================================================


@pytest.fixture
def test_data() -> dict[str, Any]:
    """
    Centralized test data for all test scenarios.

    This fixture provides fork-specific configurations, CLI outputs, and
    GitHub API patterns to avoid hardcoding strings in tests.

    Returns:
        Dictionary with test data organized by category:
        - FORKS: Fork-specific configurations (repo, asset patterns, link names)
        - CLI_OUTPUTS: Expected CLI output strings
        - GITHUB_API: GitHub API error messages and patterns

    Usage:
        def test_fork_configuration(test_data: dict[str, Any], fork: ForkName):
            repo = test_data["FORKS"][fork]["repo"]
            expected_tag = test_data["FORKS"][fork]["example_tag"]
            assert repo == "GloriousEggroll/proton-ge-custom"

        def test_asset_pattern(test_data, fork):
            pattern = test_data["FORKS"][fork]["asset_pattern"]
            assert pattern.endswith(test_data["FORKS"][fork]["archive_format"])
    """
    return {
        "FORKS": {
            ForkName.GE_PROTON: {
                "repo": "GloriousEggroll/proton-ge-custom",
                "asset_pattern": "GE-Proton*.tar.gz",
                "link_names": (
                    "GE-Proton",
                    "GE-Proton-Fallback",
                    "GE-Proton-Fallback2",
                ),
                "example_tag": "GE-Proton10-20",
                "example_asset": "GE-Proton10-20.tar.gz",
                "archive_format": ".tar.gz",
            },
            ForkName.PROTON_EM: {
                "repo": "Etaash-mathamsetty/Proton",
                "asset_pattern": "proton-EM*.tar.xz",
                "link_names": (
                    "Proton-EM",
                    "Proton-EM-Fallback",
                    "Proton-EM-Fallback2",
                ),
                "example_tag": "EM-10.0-30",
                "example_asset": "proton-EM-10.0-30.tar.xz",
                "archive_format": ".tar.xz",
            },
            ForkName.CACHYOS: {
                "repo": "CachyOS/proton-cachyos",
                "asset_pattern": "proton-cachyos*.tar.xz",
                "link_names": (
                    "CachyOS",
                    "CachyOS-Fallback",
                    "CachyOS-Fallback2",
                ),
                "example_tag": "cachyos-10.0-20260207-slr",
                "example_asset": "proton-cachyos-10.0-20260207-slr-x86_64.tar.xz",
                "archive_format": ".tar.xz",
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


# =============================================================================
# NetworkClientProtocol Fixtures
# =============================================================================


@pytest.fixture
def mock_network_client(mocker: Any) -> Any:
    """
    Create a realistic mock of NetworkClientProtocol.

    Provides realistic behavior for:
    - HTTP GET requests (GitHub API responses)
    - HTTP HEAD requests (redirect following, content-length)
    - Download operations

    Returns:
        MagicMock configured as NetworkClientProtocol
    """
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.timeout = DEFAULT_TIMEOUT
    mock_network.PROTOCOL_VERSION = "1.0"

    # Default GET response (successful API call)
    mock_get_response = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"assets": [{"name": "test.tar.gz", "size": 1048576}]}',
        stderr="",
    )
    mock_network.get.return_value = mock_get_response

    # Default HEAD response (successful redirect with content-length)
    mock_head_response = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="Location: https://github.com/repo/releases/download/v1.0/test.tar.gz\nContent-Length: 1048576",
        stderr="",
    )
    mock_network.head.return_value = mock_head_response

    # Default download response
    mock_download_response = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    mock_network.download.return_value = mock_download_response

    return mock_network


@pytest.fixture
def mock_network_with_github_redirect(mocker: Any) -> Any:
    """
    Create a mock that simulates GitHub's /releases/latest redirect behavior.

    Returns:
        MagicMock configured with GitHub redirect response
    """
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.timeout = DEFAULT_TIMEOUT

    # Simulate GitHub redirect from /releases/latest to specific tag
    mock_head_response = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="Location: https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/GE-Proton10-20",
        stderr="",
    )
    mock_network.head.return_value = mock_head_response

    return mock_network


@pytest.fixture
def mock_network_with_api_response(
    mocker: Any, release_assets: list[dict[str, Any]]
) -> Any:
    """
    Create a mock with specific GitHub API release assets.

    Args:
        release_assets: List of asset dictionaries to return

    Returns:
        MagicMock configured with specific API response
    """
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.timeout = DEFAULT_TIMEOUT

    import json

    api_response = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=json.dumps({"assets": release_assets}), stderr=""
    )
    mock_network.get.return_value = api_response

    return mock_network


@pytest.fixture
def mock_network_with_rate_limit(mocker: Any) -> Any:
    """Create a mock that simulates GitHub API rate limiting."""
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.timeout = DEFAULT_TIMEOUT

    mock_response = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"message": "API rate limit exceeded"}',
        stderr="403 Forbidden",
    )
    mock_network.get.return_value = mock_response

    return mock_network


@pytest.fixture
def mock_network_with_404(mocker: Any) -> Any:
    """Create a mock that simulates 404 Not Found responses."""
    mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
    mock_network.timeout = DEFAULT_TIMEOUT

    mock_response = subprocess.CompletedProcess(
        args=[],
        returncode=22,
        stdout="",
        stderr="404 Not Found",
    )
    mock_network.get.return_value = mock_response
    mock_network.head.return_value = mock_response

    return mock_network


# =============================================================================
# FileSystemClientProtocol Fixtures
# =============================================================================


@pytest.fixture
def mock_filesystem_client(mocker: Any) -> Any:
    """
    Create a realistic mock of FileSystemClientProtocol.

    Provides realistic behavior for:
    - Path existence checks
    - Directory operations
    - File I/O
    - Symlink operations

    Returns:
        MagicMock configured as FileSystemClientProtocol
    """
    mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
    mock_fs.PROTOCOL_VERSION = "1.0"

    # Default existence checks
    mock_fs.exists.return_value = True
    mock_fs.is_dir.return_value = True
    mock_fs.is_symlink.return_value = False

    # Default file operations
    mock_fs.read.return_value = b"test content"
    mock_fs.size.return_value = 1048576  # 1MB
    mock_fs.mtime.return_value = 1234567890.0

    # Default directory operations
    mock_fs.mkdir.return_value = None
    mock_fs.iterdir.return_value = iter([])

    # Default symlink operations
    mock_fs.symlink_to.return_value = None
    mock_fs.resolve.side_effect = lambda p: p  # Return path as-is
    mock_fs.unlink.return_value = None
    mock_fs.rmtree.return_value = None

    return mock_fs


@pytest.fixture
def real_filesystem_client() -> Any:
    """
    Create a real FileSystemClient for integration tests.

    Returns:
        Actual FileSystemClient instance
    """
    from protonfetcher.filesystem import FileSystemClient

    return FileSystemClient()


@pytest.fixture
def mock_filesystem_with_directory_structure(mocker: Any, tmp_path: Path) -> Any:
    """
    Create a mock filesystem that tracks a temporary directory structure.

    Args:
        mocker: pytest-mock fixture
        tmp_path: pytest temporary path

    Returns:
        MagicMock that delegates to real tmp_path operations
    """
    mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
    mock_fs.PROTOCOL_VERSION = "1.0"

    # Delegate to real tmp_path operations
    mock_fs.exists.side_effect = lambda p: p.exists()
    mock_fs.is_dir.side_effect = lambda p: p.is_dir()
    mock_fs.is_symlink.side_effect = lambda p: p.is_symlink()
    mock_fs.read.side_effect = lambda p: p.read_bytes()
    mock_fs.write.side_effect = lambda p, d: p.write_bytes(d)
    mock_fs.size.side_effect = lambda p: p.stat().st_size
    mock_fs.mtime.side_effect = lambda p: p.stat().st_mtime
    mock_fs.mkdir.side_effect = lambda p, **kwargs: p.mkdir(**kwargs)
    mock_fs.iterdir.side_effect = lambda p: p.iterdir()
    mock_fs.symlink_to.side_effect = lambda p, t, **kwargs: p.symlink_to(t)
    mock_fs.resolve.side_effect = lambda p: p.resolve()
    mock_fs.unlink.side_effect = lambda p: p.unlink()
    mock_fs.rmtree.side_effect = lambda p: p.rmdir() if p.is_dir() else p.unlink()

    return mock_fs


# =============================================================================
# Mock Data Factories
# =============================================================================


@pytest.fixture
def release_assets(request: pytest.FixtureRequest) -> list[dict[str, Any]]:
    """
    Factory for creating GitHub release assets.

    Can be parametrized or used with indirect=True for custom asset lists.
    Default: Returns assets for both GE-Proton and Proton-EM.

    Args:
        request: pytest request object (for parametrization)

    Returns:
        List of asset dictionaries with 'name' and 'size' keys

    Usage:
        # Direct use - returns default assets
        def test_with_default_assets(release_assets):
            assert len(release_assets) > 0

        # Parametrized with indirect=True
        @pytest.mark.parametrize(
            "release_assets",
            [[{"name": "custom.tar.gz", "size": 1024}]],
            indirect=True,
        )
        def test_with_custom_assets(release_assets):
            assert release_assets[0]["name"] == "custom.tar.gz"
    """
    # Check if test has parametrized assets
    if hasattr(request, "param"):
        return request.param

    # Default assets
    return [
        {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
        {"name": "GE-Proton10-19.tar.gz", "size": 1048575},
        {"name": "proton-EM-10.0-30.tar.xz", "size": 2097152},
    ]


@pytest.fixture
def github_release_response(
    request: pytest.FixtureRequest,
) -> dict[str, Any]:
    """
    Factory for creating GitHub API release responses.

    Can be parametrized with specific release data for custom scenarios.

    Args:
        request: pytest request object (for parametrization)

    Returns:
        Dictionary with 'tag_name', 'name', and 'assets' keys

    Usage:
        # Direct use - returns default response
        def test_with_default_response(github_release_response):
            assert "tag_name" in github_release_response

        # Parametrized with custom data
        @pytest.mark.parametrize(
            "github_release_response",
            [{"tag_name": "custom-tag", "name": "Custom Release"}],
            indirect=True,
        )
        def test_with_custom_response(github_release_response):
            assert github_release_response["tag_name"] == "custom-tag"
    """
    params = getattr(request, "param", {})
    return {
        "tag_name": params.get("tag_name", "GE-Proton10-20"),
        "name": params.get("name", "GE-Proton10-20 Release"),
        "assets": params.get(
            "assets",
            [
                {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
                {"name": "source.tar.gz", "size": 1024},
            ],
        ),
    }


@pytest.fixture
def recent_releases(request: pytest.FixtureRequest) -> list[str]:
    """
    Factory for creating list of recent release tags.

    Can be parametrized for custom release lists.
    Default: Returns 5 recent GE-Proton releases.

    Args:
        request: pytest request object (for parametrization)

    Returns:
        List of release tag strings

    Usage:
        # Direct use - returns default releases
        def test_with_default_releases(recent_releases):
            assert len(recent_releases) == 5

        # Parametrized with custom list
        @pytest.mark.parametrize(
            "recent_releases",
            [["custom-1", "custom-2"]],
            indirect=True,
        )
        def test_with_custom_releases(recent_releases):
            assert recent_releases[0] == "custom-1"
    """
    if hasattr(request, "param"):
        return request.param

    return [
        "GE-Proton10-20",
        "GE-Proton10-19",
        "GE-Proton10-18",
        "GE-Proton10-17",
        "GE-Proton10-16",
    ]


# =============================================================================
# Archive Factories
# =============================================================================


@pytest.fixture
def sample_tar_gz_archive(tmp_path: Path) -> Path:
    """
    Create a sample .tar.gz archive for testing extraction.

    Contains a realistic ProtonGE-like directory structure.

    Args:
        tmp_path: pytest temporary path

    Returns:
        Path to the created archive
    """
    archive_path = tmp_path / "GE-Proton10-20.tar.gz"

    # Create temporary content directory
    content_dir = tmp_path / "content" / "GE-Proton10-20"
    content_dir.mkdir(parents=True)

    # Create sample files
    (content_dir / "version").write_text("GE-Proton10-20")
    (content_dir / "file.txt").write_text("test content")

    # Create subdirectory structure similar to real ProtonGE
    lib_dir = content_dir / "lib"
    lib_dir.mkdir()
    (lib_dir / "libwine.so").write_text("fake libwine")

    # Create the archive - add the directory itself, not the parent
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(content_dir, arcname="GE-Proton10-20")

    return archive_path


@pytest.fixture
def sample_tar_xz_archive(tmp_path: Path) -> Path:
    """
    Create a sample .tar.xz archive for testing extraction.

    Contains a realistic Proton-EM-like directory structure.

    Args:
        tmp_path: pytest temporary path

    Returns:
        Path to the created archive
    """
    archive_path = tmp_path / "proton-EM-10.0-30.tar.xz"

    # Create temporary content directory
    content_dir = tmp_path / "content" / "proton-EM-10.0-30"
    content_dir.mkdir(parents=True)

    # Create sample files
    (content_dir / "version").write_text("EM-10.0-30")
    (content_dir / "file.txt").write_text("test content")

    # Create subdirectory structure
    lib_dir = content_dir / "lib"
    lib_dir.mkdir()
    (lib_dir / "libwine.so").write_text("fake libwine")

    # Create the archive - add the directory itself, not the parent
    with tarfile.open(archive_path, "w:xz") as tar:
        tar.add(content_dir, arcname="proton-EM-10.0-30")

    return archive_path


@pytest.fixture
def sample_archive(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    sample_tar_gz_archive: Path,
    sample_tar_xz_archive: Path,
) -> Path:
    """
    Parametrized fixture for sample archives.

    Use with @pytest.mark.parametrize("sample_archive", ["gz", "xz"])

    Args:
        request: pytest request object
        tmp_path: pytest temporary path
        sample_tar_gz_archive: .tar.gz archive fixture
        sample_tar_xz_archive: .tar.xz archive fixture

    Returns:
        Path to the requested archive type
    """
    archive_type = getattr(request, "param", "gz")
    if archive_type == "xz":
        return sample_tar_xz_archive
    return sample_tar_gz_archive


# =============================================================================
# Directory Structure Fixtures
# =============================================================================


@pytest.fixture
def temp_environment(tmp_path: Path) -> dict[str, Path]:
    """
    Create temporary directories for testing download/extraction workflows.

    Args:
        tmp_path: pytest temporary path

    Returns:
        Dictionary with output_dir and extract_dir paths
    """
    output_dir = tmp_path / "Downloads"
    extract_dir = tmp_path / "compatibilitytools.d"
    output_dir.mkdir(parents=True)
    extract_dir.mkdir(parents=True)

    return {
        "tmp": tmp_path,
        "output_dir": output_dir,
        "extract_dir": extract_dir,
    }


@pytest.fixture
def installed_proton_versions(tmp_path: Path, fork: ForkName) -> list[Path]:
    """
    Create fake installed Proton directories for testing link management.

    Requires fork parameter from parametrized fixture or explicit value.

    Args:
        tmp_path: pytest temporary path
        fork: Which fork's directories to create (from parametrized fixture)

    Returns:
        List of created directory paths

    Usage:
        @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
        def test_with_installed_versions(fork, installed_proton_versions, ...):
            # installed_proton_versions will match the fork parameter
    """
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)

    versions = []
    if fork == ForkName.GE_PROTON:
        version_names = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
    elif fork == ForkName.PROTON_EM:
        version_names = ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]
    else:  # CACHYOS
        version_names = [
            "cachyos-10.0-20260207-slr",
            "cachyos-10.0-20260206-slr",
            "cachyos-10.0-20260205-slr",
        ]

    for version_name in version_names:
        version_dir = extract_dir / version_name
        version_dir.mkdir()
        (version_dir / "version").write_text(version_name)
        versions.append(version_dir)

    return versions


@pytest.fixture
def symlink_environment(tmp_path: Path, fork: ForkName) -> dict[str, Any]:
    """
    Create a complete symlink testing environment.

    Sets up:
    - Extract directory with installed versions
    - Existing symlinks (main, fallback1, fallback2)

    Requires fork parameter from parametrized fixture or explicit value.

    Args:
        tmp_path: pytest temporary path
        fork: Which fork's symlinks to create (from parametrized fixture)

    Returns:
        Dictionary with environment details

    Usage:
        @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
        def test_with_symlinks(fork, symlink_environment, ...):
            # symlink_environment will match the fork parameter
    """
    from protonfetcher.filesystem import FileSystemClient

    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Create version directories
    if fork == ForkName.GE_PROTON:
        version_names = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
        link_names = ["GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"]
    elif fork == ForkName.PROTON_EM:
        version_names = ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]
        link_names = ["Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"]
    else:  # CACHYOS
        version_names = [
            "cachyos-10.0-20260207-slr",
            "cachyos-10.0-20260206-slr",
            "cachyos-10.0-20260205-slr",
        ]
        link_names = ["CachyOS", "CachyOS-Fallback", "CachyOS-Fallback2"]

    fs = FileSystemClient()
    version_dirs = []

    for version_name in version_names:
        version_dir = extract_dir / version_name
        version_dir.mkdir(exist_ok=True)
        (version_dir / "version").write_text(version_name)
        version_dirs.append(version_dir)

    # Create symlinks
    symlinks = {}
    for i, link_name in enumerate(link_names):
        if i < len(version_dirs):
            link_path = extract_dir / link_name
            target_path = version_dirs[i]
            fs.symlink_to(link_path, target_path, target_is_directory=True)
            symlinks[link_name] = link_path

    return {
        "extract_dir": extract_dir,
        "version_dirs": version_dirs,
        "symlinks": symlinks,
        "link_names": link_names,
        "fork": fork,
    }


# =============================================================================
# Parametrized Fork Fixtures
# =============================================================================


@pytest.fixture(params=[ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS])
def fork(request: pytest.FixtureRequest) -> ForkName:
    """
    Parametrized fixture for testing both forks.

    Use in tests to automatically run for both GE-Proton and Proton-EM.

    Args:
        request: pytest request object

    Returns:
        ForkName enum value
    """
    return request.param


@pytest.fixture
def fork_repo(fork: ForkName) -> str:
    """
    Get the repository name for a given fork.

    Use this fixture to avoid hardcoding repository strings in tests.
    Works with the parametrized `fork` fixture for comprehensive testing.

    Args:
        fork: ForkName enum value (from parametrized fixture)

    Returns:
        Repository string in format 'owner/repo'

    Usage:
        @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
        def test_repo_configuration(fork, fork_repo):
            # fork_repo automatically matches the fork parameter
            assert "proton" in fork_repo.lower()
    """
    from protonfetcher.common import FORKS

    return FORKS[fork].repo


@pytest.fixture
def fork_archive_format(fork: ForkName) -> str:
    """
    Get the archive format for a given fork.

    Use this fixture to avoid hardcoding archive format extensions.

    Args:
        fork: ForkName enum value (from parametrized fixture)

    Returns:
        Archive format extension (e.g., '.tar.gz', '.tar.xz')

    Usage:
        @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
        def test_archive_format(fork, fork_archive_format):
            # fork_archive_format automatically matches the fork parameter
            assert fork_archive_format.startswith(".tar")
    """
    from protonfetcher.common import FORKS

    return FORKS[fork].archive_format


@pytest.fixture
def fork_link_names(fork: ForkName, extract_dir: Path) -> tuple[Path, Path, Path]:
    """
    Get the symlink names for a given fork as Path objects.

    Use this fixture to get fork-specific symlink paths without hardcoding names.

    Args:
        fork: ForkName enum value (from parametrized fixture)
        extract_dir: Directory where symlinks are created (from fixture)

    Returns:
        Tuple of (main, fallback1, fallback2) Path objects

    Usage:
        @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
        def test_symlink_paths(fork, fork_link_names):
            main_link, fb1, fb2 = fork_link_names
            # fork_link_names automatically matches the fork parameter
            assert "Proton" in main_link.name
    """
    from protonfetcher.filesystem import FileSystemClient
    from protonfetcher.link_manager import LinkManager

    fs = FileSystemClient()
    lm = LinkManager(fs)
    return lm.get_link_names_for_fork(extract_dir, fork)


# =============================================================================
# Component Fixtures (SUT Factories)
# =============================================================================


@pytest.fixture
def release_manager(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """
    Create a ReleaseManager with mocked dependencies.

    Args:
        mock_network_client: NetworkClientProtocol mock
        mock_filesystem_client: FileSystemClientProtocol mock

    Returns:
        ReleaseManager instance
    """
    from protonfetcher.release_manager import ReleaseManager

    return ReleaseManager(mock_network_client, mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def asset_downloader(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """
    Create an AssetDownloader with mocked dependencies.

    Args:
        mock_network_client: NetworkClientProtocol mock
        mock_filesystem_client: FileSystemClientProtocol mock

    Returns:
        AssetDownloader instance
    """
    from protonfetcher.asset_downloader import AssetDownloader

    return AssetDownloader(mock_network_client, mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def archive_extractor(mock_filesystem_client: Any) -> Any:
    """
    Create an ArchiveExtractor with mocked dependencies.

    Args:
        mock_filesystem_client: FileSystemClientProtocol mock

    Returns:
        ArchiveExtractor instance
    """
    from protonfetcher.archive_extractor import ArchiveExtractor

    return ArchiveExtractor(mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def link_manager(mock_filesystem_client: Any) -> Any:
    """
    Create a LinkManager with mocked dependencies.

    Args:
        mock_filesystem_client: FileSystemClientProtocol mock

    Returns:
        LinkManager instance
    """
    from protonfetcher.link_manager import LinkManager

    return LinkManager(mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def github_fetcher(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """
    Create a GitHubReleaseFetcher with mocked dependencies.

    This is the main SUT (System Under Test) for e2e tests.

    Args:
        mock_network_client: NetworkClientProtocol mock
        mock_filesystem_client: FileSystemClientProtocol mock

    Returns:
        GitHubReleaseFetcher instance
    """
    from protonfetcher.github_fetcher import GitHubReleaseFetcher

    return GitHubReleaseFetcher(
        network_client=mock_network_client,
        file_system_client=mock_filesystem_client,
        timeout=DEFAULT_TIMEOUT,
    )


# =============================================================================
# CLI Test Helpers
# =============================================================================


@pytest.fixture
def cli_args(args: list[str]) -> list[str]:
    """
    Fixture for passing CLI arguments in tests.

    Override in tests to test specific argument combinations.

    Args:
        args: List of argument strings

    Returns:
        List of CLI arguments
    """
    return args


@pytest.fixture
def extract_dir(tmp_path: Path) -> Path:
    """
    Create a temporary extract directory.

    Args:
        tmp_path: pytest temporary path

    Returns:
        Path to extract directory
    """
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)
    return extract_dir


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """
    Create a temporary output/download directory.

    Args:
        tmp_path: pytest temporary path

    Returns:
        Path to output directory
    """
    output_dir = tmp_path / "Downloads"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# =============================================================================
# Mocking Helper Fixtures
# =============================================================================


@pytest.fixture
def mock_tarfile_operations(mocker: Any) -> Any:
    """
    Fixture for mocking tarfile operations.

    Provides a factory function to configure tarfile mocks with custom members.

    Returns:
        Callable that sets up tarfile mock with specified members.
        Returns dict with keys:
            - 'tarfile_mock': The patched tarfile.open mock
            - 'tar_mock': The mock tar object returned by __enter__

    Example:
        mocks = mock_tarfile_operations(
            members=[
                {"name": "test_dir", "is_dir": True, "size": 0},
                {"name": "test_dir/file.txt", "is_dir": False, "size": 1024},
            ]
        )
        assert mocks['tarfile_mock'].called
    """

    def _setup_tarfile_mock(
        members: list[dict[str, Any]] | None = None,
        raise_on_open: Exception | None = None,
    ) -> dict[str, Any]:
        """
        Set up tarfile mock with specified members.

        Args:
            members: List of member dicts with keys: name, is_dir, size
            raise_on_open: Exception to raise when tarfile.open is called

        Returns:
            Dict with 'tarfile_mock' and 'tar_mock' keys
        """
        mock_tarfile = mocker.patch("tarfile.open")

        if raise_on_open:
            mock_tarfile.side_effect = raise_on_open
            return {"tarfile_mock": mock_tarfile, "tar_mock": None}

        mock_tar = mocker.MagicMock()

        if members:
            mock_members = []
            for member_data in members:
                mock_member = mocker.MagicMock()
                mock_member.name = member_data.get("name", "unknown")
                mock_member.isdir.return_value = member_data.get("is_dir", False)
                mock_member.size = member_data.get("size", 0)
                mock_members.append(mock_member)
            mock_tar.getmembers.return_value = mock_members
        else:
            mock_tar.getmembers.return_value = []

        mock_tarfile.return_value.__enter__.return_value = mock_tar
        return {"tarfile_mock": mock_tarfile, "tar_mock": mock_tar}

    return _setup_tarfile_mock


@pytest.fixture
def mock_urllib_download(mocker: Any) -> Any:
    """
    Fixture for mocking urllib download operations.

    Provides a factory function to configure urllib mocks with custom response data.

    Returns:
        Callable that sets up urllib mock with specified chunks

    Example:
        mock_resp = mock_urllib_download(
            chunks=[b"chunk1", b"chunk2", b""],
            content_length=1048576
        )
    """

    def _setup_urllib_mock(
        chunks: list[bytes] | None = None,
        content_length: int | None = None,
        raise_on_open: Exception | None = None,
    ) -> Any:
        """
        Set up urllib mock with specified response data.

        Args:
            chunks: List of byte chunks to return from read()
            content_length: Content-Length header value
            raise_on_open: Exception to raise when urlopen is called

        Returns:
            Mock response object
        """
        mock_urllib = mocker.patch("urllib.request.urlopen")

        if raise_on_open:
            mock_urllib.side_effect = raise_on_open
            return None

        mock_resp_obj = mocker.MagicMock()
        mock_resp_obj.__enter__.return_value = mock_resp_obj

        if content_length is not None:
            mock_resp_obj.headers.get.return_value = str(content_length)
        else:
            mock_resp_obj.headers.get.return_value = "0"

        if chunks:
            mock_resp_obj.read.side_effect = chunks
        else:
            mock_resp_obj.read.side_effect = [b"chunk", b""]

        mock_urllib.return_value = mock_resp_obj
        return mock_resp_obj

    return _setup_urllib_mock


@pytest.fixture
def mock_subprocess_tar(mocker: Any) -> Any:
    """
    Fixture for mocking subprocess tar command.

    Provides a factory function to configure subprocess.run mocks for tar commands.

    Returns:
        Callable that sets up subprocess mock with specified return code

    Example:
        mock_run = mock_subprocess_tar(returncode=0, stderr="")
    """

    def _setup_subprocess_mock(
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        raise_on_call: Exception | None = None,
    ) -> Any:
        """
        Set up subprocess mock for tar command.

        Args:
            returncode: Return code for the CompletedProcess
            stdout: Stdout for the CompletedProcess
            stderr: Stderr for the CompletedProcess
            raise_on_call: Exception to raise when subprocess.run is called

        Returns:
            Mock subprocess.run
        """
        mock_run = mocker.patch("subprocess.run")

        if raise_on_call:
            mock_run.side_effect = raise_on_call
            return mock_run

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr=stderr
        )
        return mock_run

    return _setup_subprocess_mock


@pytest.fixture
def mock_builtin_open(mocker: Any) -> Any:
    """
    Fixture for mocking built-in open() function.

    Provides a factory function to capture writes without creating real files.

    Returns:
        Tuple of (mock_open, written_data list)

    Example:
        mock_file, written_data = mock_builtin_open()
        # After code runs, written_data contains all bytes written
    """

    def _setup_builtin_open() -> tuple[Any, list[bytes]]:
        """
        Set up built-in open mock.

        Returns:
            Tuple of (mock_file, written_data list)
        """
        written_data: list[bytes] = []
        mock_file = mocker.MagicMock()

        def capture_write(data: bytes) -> None:
            written_data.append(data)

        mock_file.write.side_effect = capture_write

        mock_open_cm = mocker.MagicMock()
        mock_open_cm.__enter__.return_value = mock_file
        mock_open_cm.__exit__.return_value = None
        mocker.patch("builtins.open", return_value=mock_open_cm)

        return mock_file, written_data

    return _setup_builtin_open
