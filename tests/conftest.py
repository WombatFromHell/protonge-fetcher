"""
Shared pytest configuration and fixtures for ProtonFetcher test suite.

Streamlined fixtures using factory pattern for flexibility and reduced duplication.
"""

import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any, Callable

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

    Usage:
        def test_fork_configuration(test_data: dict[str, Any], fork: ForkName):
            repo = test_data["FORKS"][fork]["repo"]
    """
    return {
        "FORKS": {
            ForkName.GE_PROTON: {
                "repo": "GloriousEggroll/proton-ge-custom",
                "example_tag": "GE-Proton10-20",
                "example_asset": "GE-Proton10-20.tar.gz",
                "archive_format": ".tar.gz",
            },
            ForkName.PROTON_EM: {
                "repo": "Etaash-mathamsetty/Proton",
                "example_tag": "EM-10.0-30",
                "example_asset": "proton-EM-10.0-30.tar.xz",
                "archive_format": ".tar.xz",
            },
            ForkName.CACHYOS: {
                "repo": "CachyOS/proton-cachyos",
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
# Factory Fixtures (Network, Filesystem, Archive)
# =============================================================================


@pytest.fixture
def mock_network_factory(mocker: Any) -> Callable[..., Any]:
    """
    Factory for creating configured NetworkClientProtocol mocks.

    Usage:
        def test_with_custom_response(mock_network_factory):
            mock_network = mock_network_factory(
                get_response={"assets": [{"name": "test.tar.gz", "size": 1024}]},
                rate_limit=False,
            )

        def test_rate_limit(mock_network_factory):
            mock_network = mock_network_factory(rate_limit=True)
    """

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

        if rate_limit:
            mock_network.get.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"message": "API rate limit exceeded"}',
                stderr="403 Forbidden",
            )
        elif not_found:
            mock_response = subprocess.CompletedProcess(
                args=[], returncode=22, stdout="", stderr="404 Not Found"
            )
            mock_network.get.return_value = mock_response
            mock_network.head.return_value = mock_response
        else:
            import json

            if get_response is None:
                get_response = {"assets": [{"name": "test.tar.gz", "size": 1048576}]}
            if isinstance(get_response, dict):
                get_response = json.dumps(get_response)

            mock_network.get.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=get_response, stderr=""
            )

            if head_response is None:
                head_response = "Location: https://github.com/repo/releases/tag/v1.0"
            if isinstance(head_response, dict):
                head_response = "\n".join(f"{k}: {v}" for k, v in head_response.items())

            mock_network.head.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=head_response, stderr=""
            )

        if download_response:
            mock_network.download.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=download_response.get("returncode", 0),
                stdout=download_response.get("stdout", ""),
                stderr=download_response.get("stderr", ""),
            )
        else:
            mock_network.download.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        return mock_network

    return _create_mock


@pytest.fixture
def mock_filesystem_factory(mocker: Any, tmp_path: Path) -> Callable[..., Any]:
    """
    Factory for creating configured FileSystemClientProtocol mocks.

    Usage:
        def test_with_custom_structure(mock_filesystem_factory):
            mock_fs = mock_filesystem_factory(
                exists_map={"/dir": True, "/file": True},
                is_dir_map={"/dir": True, "/file": False},
                read_map={"/file": b"content"},
            )

        def test_with_real_tmp(mock_filesystem_factory):
            mock_fs = mock_filesystem_factory(use_tmp_path=True)
    """

    def _create_mock(
        exists_map: dict[str, bool] | None = None,
        is_dir_map: dict[str, bool] | None = None,
        is_symlink_map: dict[str, bool] | None = None,
        read_map: dict[str, bytes] | None = None,
        size_map: dict[str, int] | None = None,
        use_tmp_path: bool = False,
    ) -> Any:
        mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
        mock_fs.PROTOCOL_VERSION = "1.0"

        if use_tmp_path:
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
            mock_fs.rmtree.side_effect = lambda p: (
                p.rmdir() if p.is_dir() else p.unlink()
            )
        else:
            # Default: return True for exists/is_dir unless explicitly overridden
            exists_map = exists_map or {}
            mock_fs.exists.side_effect = lambda p: exists_map.get(str(p), True)

            is_dir_map = is_dir_map or {}
            mock_fs.is_dir.side_effect = lambda p: is_dir_map.get(str(p), True)

            is_symlink_map = is_symlink_map or {}
            mock_fs.is_symlink.side_effect = lambda p: is_symlink_map.get(str(p), False)

            read_map = read_map or {}
            mock_fs.read.side_effect = lambda p: read_map.get(str(p), b"test content")

            size_map = size_map or {}
            mock_fs.size.side_effect = lambda p: size_map.get(str(p), 1048576)

            mock_fs.mkdir.return_value = None
            mock_fs.iterdir.return_value = iter([])
            mock_fs.symlink_to.return_value = None
            mock_fs.resolve.side_effect = lambda p: p
            mock_fs.unlink.return_value = None
            mock_fs.rmtree.return_value = None

        return mock_fs

    return _create_mock


@pytest.fixture
def sample_archive_factory(tmp_path: Path) -> Callable[..., Path]:
    """
    Factory for creating sample archives.

    Usage:
        def test_extraction(sample_archive_factory):
            archive = sample_archive_factory(
                format="gz",
                tag="GE-Proton10-20",
                files=[
                    ("version", "GE-Proton10-20"),
                    ("lib/libwine.so", "fake libwine"),
                ],
            )
    """

    def _create_archive(
        format: str = "gz",
        tag: str = "GE-Proton10-20",
        files: list[tuple[str, str]] | None = None,
    ) -> Path:
        if format == "gz":
            archive_path = tmp_path / f"{tag}.tar.gz"
            mode = "w:gz"
        else:
            archive_path = tmp_path / f"proton-{tag}.tar.xz"
            mode = "w:xz"

        content_dir = tmp_path / "content" / tag
        content_dir.mkdir(parents=True)

        if files is None:
            files = [("version", tag), ("file.txt", "test content")]

        for filename, content in files:
            file_path = content_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        with tarfile.open(archive_path, mode) as tar:
            tar.add(content_dir, arcname=tag)

        return archive_path

    return _create_archive


# =============================================================================
# Backward Compatibility Fixtures (use factories internally)
# =============================================================================


@pytest.fixture
def mock_network_client(mock_network_factory: Callable[..., Any]) -> Any:
    """Create a default NetworkClientProtocol mock (backward compatibility)."""
    return mock_network_factory()


@pytest.fixture
def mock_filesystem_client(mock_filesystem_factory: Callable[..., Any]) -> Any:
    """Create a default FileSystemClientProtocol mock (backward compatibility)."""
    return mock_filesystem_factory()


@pytest.fixture
def sample_tar_gz_archive(sample_archive_factory: Callable[..., Path]) -> Path:
    """Create a sample .tar.gz archive (backward compatibility)."""
    return sample_archive_factory(format="gz", tag="GE-Proton10-20")


@pytest.fixture
def sample_tar_xz_archive(sample_archive_factory: Callable[..., Path]) -> Path:
    """Create a sample .tar.xz archive (backward compatibility)."""
    return sample_archive_factory(format="xz", tag="EM-10.0-30")


# =============================================================================
# Data Factory Fixtures
# =============================================================================


@pytest.fixture
def release_assets(request: pytest.FixtureRequest) -> list[dict[str, Any]]:
    """Factory for creating GitHub release assets."""
    if hasattr(request, "param"):
        return request.param
    return [
        {"name": "GE-Proton10-20.tar.gz", "size": 1048576},
        {"name": "GE-Proton10-19.tar.gz", "size": 1048575},
        {"name": "proton-EM-10.0-30.tar.xz", "size": 2097152},
    ]


@pytest.fixture
def github_release_response(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Factory for GitHub API release responses."""
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
    """Factory for recent release tag lists."""
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
# Directory Structure Fixtures
# =============================================================================


@pytest.fixture
def temp_environment(tmp_path: Path) -> dict[str, Path]:
    """Create temporary directories for testing workflows."""
    output_dir = tmp_path / "Downloads"
    extract_dir = tmp_path / "compatibilitytools.d"
    output_dir.mkdir(parents=True)
    extract_dir.mkdir(parents=True)
    return {"tmp": tmp_path, "output_dir": output_dir, "extract_dir": extract_dir}


@pytest.fixture
def extract_dir(tmp_path: Path) -> Path:
    """Create a temporary extract directory."""
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)
    return extract_dir


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create a temporary output/download directory."""
    output_dir = tmp_path / "Downloads"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def installed_proton_versions(tmp_path: Path, fork: ForkName) -> list[Path]:
    """Create fake installed Proton directories."""
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if fork == ForkName.GE_PROTON:
        version_names = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
    elif fork == ForkName.PROTON_EM:
        version_names = ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]
    else:
        version_names = [
            "cachyos-10.0-20260207-slr",
            "cachyos-10.0-20260206-slr",
            "cachyos-10.0-20260205-slr",
        ]

    versions = []
    for version_name in version_names:
        version_dir = extract_dir / version_name
        version_dir.mkdir()
        (version_dir / "version").write_text(version_name)
        versions.append(version_dir)

    return versions


@pytest.fixture
def symlink_environment(tmp_path: Path, fork: ForkName) -> dict[str, Any]:
    """Create a complete symlink testing environment."""
    from protonfetcher.filesystem import FileSystemClient

    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if fork == ForkName.GE_PROTON:
        version_names = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
        link_names = ["GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"]
    elif fork == ForkName.PROTON_EM:
        version_names = ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]
        link_names = ["Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"]
    else:
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
    """Parametrized fixture for testing all forks."""
    return request.param


@pytest.fixture
def fork_repo(fork: ForkName) -> str:
    """Get repository name for a given fork."""
    from protonfetcher.common import FORKS

    return FORKS[fork].repo


@pytest.fixture
def fork_archive_format(fork: ForkName) -> str:
    """Get archive format for a given fork."""
    from protonfetcher.common import FORKS

    return FORKS[fork].archive_format


@pytest.fixture
def fork_link_names(fork: ForkName, extract_dir: Path) -> tuple[Path, Path, Path]:
    """Get symlink paths for a given fork."""
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
    """Create ReleaseManager with mocked dependencies."""
    from protonfetcher.release_manager import ReleaseManager

    return ReleaseManager(mock_network_client, mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def asset_downloader(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """Create AssetDownloader with mocked dependencies."""
    from protonfetcher.asset_downloader import AssetDownloader

    return AssetDownloader(mock_network_client, mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def archive_extractor(mock_filesystem_client: Any) -> Any:
    """Create ArchiveExtractor with mocked dependencies."""
    from protonfetcher.archive_extractor import ArchiveExtractor

    return ArchiveExtractor(mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def link_manager(mock_filesystem_client: Any) -> Any:
    """Create LinkManager with mocked dependencies."""
    from protonfetcher.link_manager import LinkManager

    return LinkManager(mock_filesystem_client, DEFAULT_TIMEOUT)


@pytest.fixture
def github_fetcher(mock_network_client: Any, mock_filesystem_client: Any) -> Any:
    """Create GitHubReleaseFetcher with mocked dependencies."""
    from protonfetcher.github_fetcher import GitHubReleaseFetcher

    return GitHubReleaseFetcher(
        network_client=mock_network_client,
        file_system_client=mock_filesystem_client,
        timeout=DEFAULT_TIMEOUT,
    )


# =============================================================================
# Mocking Helper Fixtures
# =============================================================================


@pytest.fixture
def mock_tarfile_operations(mocker: Any) -> Any:
    """Factory for mocking tarfile operations."""

    def _setup_tarfile_mock(
        members: list[dict[str, Any]] | None = None,
        raise_on_open: Exception | None = None,
    ) -> dict[str, Any]:
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
    """Factory for mocking urllib download operations."""

    def _setup_urllib_mock(
        chunks: list[bytes] | None = None,
        content_length: int | None = None,
        raise_on_open: Exception | None = None,
    ) -> Any:
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
    """Factory for mocking subprocess tar command."""

    def _setup_subprocess_mock(
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        raise_on_call: Exception | None = None,
    ) -> Any:
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
    """Factory for mocking built-in open() function."""

    def _setup_builtin_open() -> tuple[Any, list[bytes]]:
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
