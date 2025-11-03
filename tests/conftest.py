"""
Shared pytest configuration and fixtures for protonfetcher tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))


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
def mock_fetcher(mocker):
    """Create a mocked GitHubReleaseFetcher instance."""
    from protonfetcher import GitHubReleaseFetcher

    fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
    fetcher.timeout = 30
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
def mock_network_client(mocker):
    """Create a mocked NetworkClientProtocol instance."""
    from protonfetcher import NetworkClientProtocol

    mock = mocker.MagicMock(spec=NetworkClientProtocol)
    mock.timeout = 30
    return mock


@pytest.fixture
def mock_filesystem_client(mocker):
    """Create a mocked FileSystemClientProtocol instance."""
    from protonfetcher import FileSystemClientProtocol

    mock = mocker.MagicMock(spec=FileSystemClientProtocol)
    return mock


@pytest.fixture
def mock_clients(mock_network_client, mock_filesystem_client):
    """Create both network and filesystem client mocks together."""
    return {"network": mock_network_client, "filesystem": mock_filesystem_client}


@pytest.fixture
def mock_release_manager(mocker):
    """Create a mocked ReleaseManager instance."""
    from protonfetcher import ReleaseManager

    mock = mocker.MagicMock(spec=ReleaseManager)
    return mock


@pytest.fixture
def mock_asset_downloader(mocker):
    """Create a mocked AssetDownloader instance."""
    from protonfetcher import AssetDownloader

    mock = mocker.MagicMock(spec=AssetDownloader)
    return mock


@pytest.fixture
def mock_archive_extractor(mocker):
    """Create a mocked ArchiveExtractor instance."""
    from protonfetcher import ArchiveExtractor

    mock = mocker.MagicMock(spec=ArchiveExtractor)
    return mock


@pytest.fixture
def mock_link_manager(mocker):
    """Create a mocked LinkManager instance."""
    from protonfetcher import LinkManager

    mock = mocker.MagicMock(spec=LinkManager)
    return mock


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
