"""
Shared pytest configuration and fixtures for protonfetcher tests.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import pytest

# Add src to path for testing
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir / "src"))

from protonfetcher.common import ForkName  # noqa: E402
from protonfetcher.asset_downloader import AssetDownloader  # noqa: E402


@pytest.fixture
def TEST_DATA():
    """Centralized test data dictionary for all test scenarios."""
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
                "version_pattern": r"GE-Proton(\d+)-(\d+)",
                "example_tag": "GE-Proton10-20",
                "example_asset": "GE-Proton10-20.tar.gz",
            },
            ForkName.PROTON_EM: {
                "repo": "Etaash-mathamsetty/Proton",
                "asset_pattern": "proton-EM*.tar.xz",
                "link_names": (
                    "Proton-EM",
                    "Proton-EM-Fallback",
                    "Proton-EM-Fallback2",
                ),
                "version_pattern": r"EM-(\d+)\.(\d+)-(\d+)",
                "example_tag": "EM-10.0-30",
                "example_asset": "proton-EM-10.0-30.tar.xz",
            },
        },
        "CLI_OUTPUTS": {
            "success": "Success",
            "error_prefix": "Error:",
        },
        "EXPECTED_DIRECTORIES": {
            "extract_base": "compatibilitytools.d",
            "download_base": "Downloads",
        },
    }


@pytest.fixture
def mock_subprocess_success(mocker):
    """Mock successful subprocess.run calls."""
    return mocker.patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        ),
    )


@pytest.fixture
def mock_urllib_response(mocker):
    """Mock successful urllib response."""
    mock_response = mocker.MagicMock()
    mock_response.headers.get.return_value = "1048576"  # 1MB
    mock_response.read.side_effect = [b"chunk1", b"chunk2", b""]
    mock_response.__enter__ = mocker.MagicMock(return_value=mock_response)
    mock_response.__exit__ = mocker.MagicMock(return_value=None)
    return mock_response


@pytest.fixture
def mock_path_operations(mocker):
    """Mock common Path operations."""
    return {
        "mkdir": mocker.patch.object(Path, "mkdir"),
        "touch": mocker.patch.object(Path, "touch"),
        "unlink": mocker.patch.object(Path, "unlink"),
        "exists": mocker.patch.object(Path, "exists", return_value=True),
        "is_dir": mocker.patch.object(Path, "is_dir", return_value=True),
        "is_symlink": mocker.patch.object(Path, "is_symlink", return_value=False),
        "symlink_to": mocker.patch.object(Path, "symlink_to"),
        "rename": mocker.patch.object(Path, "rename"),
        "resolve": mocker.patch.object(Path, "resolve"),
        "stat": mocker.patch.object(Path, "stat"),
        "iterdir": mocker.patch.object(Path, "iterdir"),
    }


@pytest.fixture
def temp_structure(tmp_path):
    """Create a temporary directory structure for testing."""
    output_dir = tmp_path / "output"
    extract_dir = tmp_path / "extract"
    output_dir.mkdir(parents=True)
    extract_dir.mkdir(parents=True)
    return {"tmp": tmp_path, "output": output_dir, "extract": extract_dir}


@pytest.fixture
def mock_fetcher(mocker, network_client=None, filesystem_client=None):
    """
    Create a properly mocked GitHubReleaseFetcher instance.

    Args:
        mocker: pytest-mock fixture
        network_client: Optional custom network client mock
        filesystem_client: Optional custom filesystem client mock

    Returns:
        GitHubReleaseFetcher with mocked dependencies
    """
    from protonfetcher.filesystem import FileSystemClient
    from protonfetcher.github_fetcher import GitHubReleaseFetcher
    from protonfetcher.network import NetworkClient

    # Create default mocks if not provided
    mock_network = network_client or mocker.MagicMock(spec=NetworkClient)
    mock_network.timeout = 30

    mock_fs = filesystem_client or mocker.MagicMock(spec=FileSystemClient)

    # Actually instantiate the fetcher with mocked dependencies
    fetcher = GitHubReleaseFetcher(
        network_client=mock_network, file_system_client=mock_fs, timeout=30
    )

    # Mock the link manager's manage_proton_links to avoid side effects in tests
    fetcher.link_manager.manage_proton_links = mocker.MagicMock(return_value=True)

    return fetcher


@pytest.fixture
def test_constants():
    """Test constants for consistent test data."""
    return {
        "MOCK_REPO": "owner/repo",
        "MOCK_TAG": "GE-Proton8-25",
        "MOCK_EM_TAG": "EM-10.0-30",
        "MOCK_ASSET_NAME": "GE-Proton8-25.tar.gz",
        "MOCK_EM_ASSET_NAME": "proton-EM-10.0-30.tar.xz",
        "MOCK_ASSET_SIZE": 1024 * 1024,
    }


@pytest.fixture
def fork_params():
    """Parameterized data for fork testing."""
    return [
        ("GE-Proton", "GE-Proton10-1", "GE-Proton10-1.tar.gz"),
        ("GE-Proton", "GE-Proton9-20", "GE-Proton9-20.tar.gz"),
        ("Proton-EM", "EM-10.0-30", "proton-EM-10.0-30.tar.xz"),
        ("Proton-EM", "EM-9.5-25", "proton-EM-9.5-25.tar.xz"),
    ]


@pytest.fixture
def fork_test_data():
    """Comprehensive parameterized test data for both forks."""
    return [
        (ForkName.GE_PROTON, "GE-Proton10-20", "GE-Proton10-20.tar.gz", ".tar.gz"),
        (ForkName.GE_PROTON, "GE-Proton9-15", "GE-Proton9-15.tar.gz", ".tar.gz"),
        (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30.tar.xz", ".tar.xz"),
        (ForkName.PROTON_EM, "EM-9.5-25", "proton-EM-9.5-25.tar.xz", ".tar.xz"),
    ]


@pytest.fixture
def mock_network_client(mocker, standardized_test_data):
    """Create a mocked NetworkClientProtocol instance with standardized responses."""
    from protonfetcher.common import NetworkClientProtocol

    mock = mocker.MagicMock(spec=NetworkClientProtocol)
    mock.timeout = 30

    return mock


@pytest.fixture
def mock_filesystem_client(mocker, standardized_test_data):
    """Create a mocked FileSystemClientProtocol instance with standardized behavior."""
    from protonfetcher.common import FileSystemClientProtocol

    mock = mocker.MagicMock(spec=FileSystemClientProtocol)

    # Add standardized filesystem behaviors based on test data
    def standard_exists(path):
        """Standard file existence check."""
        # For test directories, return True if they're in our test structure
        path_str = str(path)
        return (
            "Downloads" in path_str
            or "compatibilitytools.d" in path_str
            or "extract" in path_str
        )

    def standard_is_dir(path):
        """Standard directory check."""
        return standard_exists(path)

    def standard_is_symlink(path):
        """Standard symlink check - return False by default."""
        return False

    def standard_resolve(path):
        """Standard path resolution."""
        return Path(str(path).replace("~", "/home/test"))

    def standard_iterdir(path):
        """Standard iterator for directory contents - return empty by default."""
        return iter([])

    def standard_size(path):
        """Standard file size - return 1MB by default."""
        return 1024 * 1024

    def standard_mtime(path):
        """Standard modification time - return current time by default."""
        return time.time()

    mock.exists.side_effect = standard_exists
    mock.is_dir.side_effect = standard_is_dir
    mock.is_symlink.side_effect = standard_is_symlink
    mock.resolve.side_effect = standard_resolve
    mock.iterdir.side_effect = standard_iterdir
    mock.size.side_effect = standard_size
    mock.mtime.side_effect = standard_mtime

    return mock


@pytest.fixture
def mock_clients(mock_network_client, mock_filesystem_client):
    """Create both network and filesystem client mocks together."""
    return {"network": mock_network_client, "filesystem": mock_filesystem_client}


@pytest.fixture
def mock_release_manager(mocker):
    """Create a mocked ReleaseManager instance."""
    from protonfetcher.release_manager import ReleaseManager

    mock = mocker.MagicMock(spec=ReleaseManager)
    return mock


@pytest.fixture
def mock_asset_downloader(mocker):
    """Create a mocked AssetDownloader instance."""
    from protonfetcher.asset_downloader import AssetDownloader

    mock = mocker.MagicMock(spec=AssetDownloader)
    return mock


@pytest.fixture
def mock_archive_extractor(mocker):
    """Create a mocked ArchiveExtractor instance."""
    from protonfetcher.archive_extractor import ArchiveExtractor

    mock = mocker.MagicMock(spec=ArchiveExtractor)
    return mock


@pytest.fixture
def mock_link_manager(mocker):
    """Create a mocked LinkManager instance."""
    from protonfetcher.link_manager import LinkManager

    mock = mocker.MagicMock(spec=LinkManager)
    return mock


@pytest.fixture
def create_test_archive():
    """Helper fixture to create real archive files for testing."""
    import os

    def _create_test_archive(
        archive_path: Path, format_extension: str, files: dict[str, bytes] | None = None
    ) -> Path:
        if files is None:
            files = {"test.txt": b"test content"}

        if format_extension == ".tar.gz":
            import tarfile

            with tarfile.open(archive_path, "w:gz") as tar:
                for file_name, content in files.items():
                    # Create a temporary file to add to the archive
                    import tempfile

                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_file.flush()

                        # Add the file to the archive
                        tarinfo = tarfile.TarInfo(name=file_name)
                        tarinfo.size = len(content)
                        with open(temp_file.name, "rb") as f:
                            tar.addfile(tarinfo, f)
                        os.unlink(temp_file.name)
        elif format_extension == ".tar.xz":
            import tarfile

            with tarfile.open(archive_path, "w:xz") as tar:
                for file_name, content in files.items():
                    # Create a temporary file to add to the archive
                    import tempfile

                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_file.flush()

                        # Add the file to the archive
                        tarinfo = tarfile.TarInfo(name=file_name)
                        tarinfo.size = len(content)
                        with open(temp_file.name, "rb") as f:
                            tar.addfile(tarinfo, f)
                        os.unlink(temp_file.name)

        return archive_path

    return _create_test_archive


@pytest.fixture
def mock_successful_download(mocker):
    """Mock successful download operation."""
    mock_response = mocker.MagicMock()
    mock_response.returncode = 0
    mock_response.stderr = ""
    return mock_response


@pytest.fixture
def mock_failed_download(mocker):
    """Mock failed download operation."""
    mock_response = mocker.MagicMock()
    mock_response.returncode = 1
    mock_response.stderr = "Download failed"
    return mock_response


@pytest.fixture
def mock_extraction_result(mocker):
    """Mock extraction result."""
    return {"status": "success", "files_extracted": 10, "size": 1024 * 1024}


@pytest.fixture
def mock_cache_dir(tmp_path):
    """Create a mock cache directory for testing."""
    cache_dir = tmp_path / ".cache" / "protonfetcher"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def mock_redirect_chain():
    """Provide a mock redirect chain for testing."""
    return [
        ("https://example.com/initial", "https://redirect1.example.com"),
        ("https://redirect1.example.com", "https://redirect2.example.com"),
        ("https://redirect2.example.com", "https://final.example.com/file"),
    ]


@pytest.fixture
def standardized_test_data(TEST_DATA):
    """Return standardized test data from centralized fixture."""
    return TEST_DATA


@pytest.fixture
def corrupted_archive(tmp_path):
    """Create a corrupted archive for testing extraction fallbacks."""
    archive_path = tmp_path / "corrupted.tar.gz"
    archive_path.write_bytes(b"not a valid archive")
    return archive_path


@pytest.fixture
def create_mock_cache_file():
    """Helper fixture to create a mock cache file for testing."""

    def _create_mock_cache_file(
        cache_dir: Path,
        repo: str,
        tag: str,
        asset_name: str,
        size: int,
        timestamp: Optional[float] = None,
    ):
        import hashlib
        import json
        import time

        if timestamp is None:
            timestamp = time.time()

        # Generate the cache key as ReleaseManager would
        key_data = f"{repo}_{tag}_{asset_name}_size"
        cache_key = hashlib.md5(key_data.encode()).hexdigest()

        cache_path = cache_dir / cache_key

        cache_data = {
            "size": size,
            "timestamp": timestamp,
            "repo": repo,
            "tag": tag,
            "asset_name": asset_name,
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        return cache_path

    return _create_mock_cache_file


@pytest.fixture
def create_broken_symlink():
    """Helper fixture to create a broken symlink for testing."""

    def _create_broken_symlink(link_path: Path, target_path: Path):
        # Create a symlink to a non-existent target
        link_path.symlink_to(target_path)
        return link_path

    return _create_broken_symlink


@pytest.fixture
def create_test_asset_file():
    """Helper fixture to create a test asset file with specified size."""

    def _create_test_asset_file(asset_path: Path, size: int = 1024):
        asset_path.write_bytes(b"x" * size)
        return asset_path

    return _create_test_asset_file


@pytest.fixture
def get_expected_link_names():
    """Get the expected link names for a given fork."""

    def _get_expected_link_names(extract_dir: Path, fork: ForkName):
        if fork == ForkName.PROTON_EM:
            return (
                extract_dir / "Proton-EM",
                extract_dir / "Proton-EM-Fallback",
                extract_dir / "Proton-EM-Fallback2",
            )
        else:  # GE-Proton
            return (
                extract_dir / "GE-Proton",
                extract_dir / "GE-Proton-Fallback",
                extract_dir / "GE-Proton-Fallback2",
            )

    return _get_expected_link_names


@pytest.fixture
def archive_formats():
    """Parameterized test data for different archive formats."""
    return [
        (".tar.gz", "extract_gz_archive"),
        (".tar.xz", "extract_xz_archive"),
    ]


@pytest.fixture
def error_scenarios():
    """Parameterized test data for different error scenarios."""
    return [
        ("network_timeout", "fetch_latest_tag", "NetworkError"),
        ("extraction_failure", "extract_archive", "ExtractionError"),
        ("invalid_asset", "download_asset", "ProtonFetcherError"),
        ("link_management_failure", "manage_proton_links", "LinkManagementError"),
    ]


@pytest.fixture
def cli_flag_combinations():
    """Parameterized test data for CLI flag combinations."""
    return [
        (["--list"], "list_recent_releases"),
        (["--ls"], "list_links"),
        (["--rm", "GE-Proton10-20"], "remove_release"),
        (["--release", "GE-Proton10-20"], "fetch_and_extract"),
    ]


@pytest.fixture
def test_directory_structure(tmp_path):
    """Create a comprehensive test directory structure."""
    # Create base directories
    downloads_dir = tmp_path / "Downloads"
    extract_dir = tmp_path / "compatibilitytools.d"
    downloads_dir.mkdir(parents=True)
    extract_dir.mkdir(parents=True)

    # Create some version directories for testing
    ge_versions = ["GE-Proton10-20", "GE-Proton9-15", "GE-Proton8-10"]
    em_versions = ["proton-EM-10.0-30", "proton-EM-9.5-25"]

    for version in ge_versions:
        (extract_dir / version).mkdir()

    for version in em_versions:
        (extract_dir / version).mkdir()

    return {"downloads": downloads_dir, "extract": extract_dir, "tmp_path": tmp_path}


@pytest.fixture
def mock_version_candidates():
    """Mock version candidates for link management testing."""
    from protonfetcher.utils import parse_version

    def create_candidates(base_path, fork, versions):
        candidates = []
        for version in versions:
            if fork == ForkName.GE_PROTON:
                parsed = parse_version(version, fork)
            else:  # Proton-EM
                parsed = parse_version(version.replace("proton-", ""), fork)
            candidates.append((parsed, base_path / version))
        return candidates

    return create_candidates


@pytest.fixture
def test_data_by_fork(standardized_test_data):
    """Return test data organized by fork for parametrized tests."""
    forks_data = []
    for fork, data in standardized_test_data["FORKS"].items():
        forks_data.append(
            (fork, data["example_tag"], data["example_asset"], data["repo"])
        )
    return forks_data


@pytest.fixture
def asset_downloader_dependencies(mocker):
    """
    Creates a context with all necessary mocks pre-configured for AssetDownloader.
    This reduces setup boilerplate and object creation overhead.
    """
    # Create a spinner mock instance with context manager support
    spinner_mock = mocker.patch("protonfetcher.asset_downloader.Spinner")
    # Create the spinner instance that will be returned by Spinner(...)
    spinner_instance = mocker.MagicMock()
    # Setup context manager protocol for the spinner instance
    spinner_instance.__enter__.return_value = spinner_instance
    spinner_instance.__exit__.return_value = None
    # Set the mock's return value to be our instance
    spinner_mock.return_value = spinner_instance

    return {
        "network": mocker.Mock(),
        "fs": mocker.Mock(),
        "release_manager": mocker.Mock(),
        "spinner_cls": spinner_mock,
        "open": mocker.patch("builtins.open", mocker.mock_open()),
        "time": mocker.patch("time.time", return_value=0),
        "sleep": mocker.patch("time.sleep"),  # strictly prevent sleeping
        "urlopen": mocker.patch("urllib.request.urlopen"),
    }


@pytest.fixture
def asset_downloader(asset_downloader_dependencies):
    """Returns an initialized AssetDownloader with mocked clients."""
    return AssetDownloader(
        asset_downloader_dependencies["network"],
        asset_downloader_dependencies["fs"],
        timeout=60,
    )
