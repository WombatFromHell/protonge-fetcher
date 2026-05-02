"""
All pytest fixtures for the ProtonFetcher test suite.

Contains:
- Backward compatibility fixtures (mock_network_client, mock_filesystem_client, etc.)
- Directory structure fixtures (temp_environment, extract_dir, etc.)
- Parametrized fork fixtures (fork)
- Mocking helper fixtures (mock_tarfile_operations, mock_urllib_download, etc.)
"""

import subprocess
from pathlib import Path
from typing import Any, Callable, TypedDict

import pytest

from protonfetcher.common import DEFAULT_TIMEOUT, ForkName


class SymlinkEnvironment(TypedDict):
    """Typed dictionary for symlink test environment fixture."""

    extract_dir: Path
    version_dirs: list[Path]
    symlinks: dict[str, Path]
    link_names: list[str]
    fork: ForkName


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
def installed_proton_versions(tmp_path: Path, fork: ForkName) -> list[Path]:
    """Create fake installed Proton directories."""
    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if fork == ForkName.GE_PROTON:
        version_names = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
    elif fork == ForkName.PROTON_EM:
        # Use actual directory naming convention (with proton- prefix)
        version_names = ["proton-EM-10.0-30", "proton-EM-10.0-29", "proton-EM-10.0-28"]
    elif fork == ForkName.DW_PROTON:
        # DW-Proton uses {tag}-x86_64 directory naming
        version_names = [
            "dwproton-10.0-26-x86_64",
            "dwproton-10.0-25-x86_64",
            "dwproton-10.0-24-x86_64",
        ]
    else:
        # Use actual directory naming convention (with proton- prefix and -x86_64 suffix)
        version_names = [
            "proton-cachyos-10.0-20260207-slr-x86_64",
            "proton-cachyos-10.0-20260206-slr-x86_64",
            "proton-cachyos-10.0-20260205-slr-x86_64",
        ]

    versions = []
    for version_name in version_names:
        version_dir = extract_dir / version_name
        version_dir.mkdir()
        (version_dir / "version").write_text(version_name)
        versions.append(version_dir)

    return versions


@pytest.fixture
def symlink_environment(tmp_path: Path, fork: ForkName) -> SymlinkEnvironment:
    """Create a complete symlink testing environment."""
    from protonfetcher.filesystem import FileSystemClient

    extract_dir = tmp_path / "compatibilitytools.d"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if fork == ForkName.GE_PROTON:
        version_names = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
        link_names = ["GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"]
    elif fork == ForkName.PROTON_EM:
        # Use actual directory naming convention (with proton- prefix)
        version_names = ["proton-EM-10.0-30", "proton-EM-10.0-29", "proton-EM-10.0-28"]
        link_names = ["Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"]
    elif fork == ForkName.DW_PROTON:
        # DW-Proton uses {tag}-x86_64 directory naming
        version_names = [
            "dwproton-10.0-26-x86_64",
            "dwproton-10.0-25-x86_64",
            "dwproton-10.0-24-x86_64",
        ]
        link_names = ["DW-Proton", "DW-Proton-Fallback", "DW-Proton-Fallback2"]
    else:
        # Use actual directory naming convention (with proton- prefix and -x86_64 suffix)
        version_names = [
            "proton-cachyos-10.0-20260207-slr-x86_64",
            "proton-cachyos-10.0-20260206-slr-x86_64",
            "proton-cachyos-10.0-20260205-slr-x86_64",
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


@pytest.fixture(
    params=[
        ForkName.GE_PROTON,
        ForkName.PROTON_EM,
        ForkName.CACHYOS,
        ForkName.DW_PROTON,
    ]
)
def fork(request: pytest.FixtureRequest) -> ForkName:
    """Parametrized fixture for testing all forks."""
    return request.param


# =============================================================================
# Component Fixtures (SUT Factories)
# =============================================================================


@pytest.fixture
def link_manager(mock_filesystem_client: Any) -> Any:
    """Create LinkManager with mocked dependencies."""
    from protonfetcher.link_manager import LinkManager

    return LinkManager(mock_filesystem_client, DEFAULT_TIMEOUT)


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
