import tarfile
from pathlib import Path

import pytest

# Import the classes and constants from your script
from fetcher import GitHubReleaseFetcher, FetchError, PROTONGE_ASSET_PATTERN

# --- Mock Data and Fixtures ---

MOCK_REPO = "GloriousEggroll/proton-ge-custom"
MOCK_TAG = "GE-Proton8-25"
MOCK_ASSET_NAME = "GE-Proton8-25.tar.gz"
MOCK_RELEASE_PAGE_HTML = f'<a href="/{MOCK_REPO}/releases/download/{MOCK_TAG}/{MOCK_ASSET_NAME}">{MOCK_ASSET_NAME}</a>'
MOCK_TAR_GZ_CONTENT = b"dummy tar.gz content for testing"


@pytest.fixture
def mock_session(mocker):
    """A mock requests.Session to control network responses."""
    session = mocker.MagicMock()

    # Mock the HEAD request for fetching the latest tag
    head_response = mocker.MagicMock()
    head_response.url = f"https://github.com/{MOCK_REPO}/releases/tag/{MOCK_TAG}"
    head_response.raise_for_status = mocker.MagicMock()
    session.head.return_value = head_response

    # Mock the GET request for finding the asset on the release page
    get_page_response = mocker.MagicMock()
    get_page_response.text = MOCK_RELEASE_PAGE_HTML
    get_page_response.raise_for_status = mocker.MagicMock()

    # Mock the streaming GET request for downloading the asset
    download_response = mocker.MagicMock()
    download_response.status_code = 200
    download_response.raise_for_status = mocker.MagicMock()
    download_response.iter_content.return_value = [MOCK_TAR_GZ_CONTENT]

    # Configure session.get to return different responses for each call
    session.get.side_effect = [get_page_response, download_response]

    return session


@pytest.fixture
def fetcher(mock_session):
    """A GitHubReleaseFetcher instance with a mocked session."""
    return GitHubReleaseFetcher(session=mock_session)


# --- Tests for GitHubReleaseFetcher ---


def test_fetch_and_extract_success(fetcher, tmp_path, mocker):
    """Test the full fetch_and_extract workflow with mocked I/O."""
    output_dir = tmp_path / "output"
    extract_dir = tmp_path / "extract"

    # Mock tarfile.open to prevent actual file extraction
    mock_tar = mocker.MagicMock()
    mock_extractall = mocker.MagicMock()
    mock_tar.extractall = mock_extractall
    # Make the mock tar support the context manager protocol
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)
    mocker.patch("tarfile.open", return_value=mock_tar)

    # Create a real file for the download to write to
    expected_download_path = output_dir / MOCK_ASSET_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create fresh responses instead of trying to access the iterator
    get_page_response = mocker.MagicMock()
    get_page_response.text = MOCK_RELEASE_PAGE_HTML
    get_page_response.raise_for_status = mocker.MagicMock()

    # Mock the download response with context manager support
    download_response = mocker.MagicMock()
    download_response.status_code = 200
    download_response.raise_for_status = mocker.MagicMock()
    download_response.iter_content.return_value = [MOCK_TAR_GZ_CONTENT]
    download_response.__enter__ = mocker.MagicMock(return_value=download_response)
    download_response.__exit__ = mocker.MagicMock(return_value=None)

    fetcher.session.get.side_effect = [
        get_page_response,
        download_response,
    ]

    result_path = fetcher.fetch_and_extract(
        repo=MOCK_REPO,
        asset_name=PROTONGE_ASSET_PATTERN,
        output_dir=output_dir,
        extract_dir=extract_dir,
    )

    # 1. Assert the method returns the correct extraction directory
    assert result_path == extract_dir

    # 2. Assert the download was called to the correct output path
    fetcher.session.get.assert_called_with(
        f"https://github.com/{MOCK_REPO}/releases/download/{MOCK_TAG}/{MOCK_ASSET_NAME}",
        stream=True,
        timeout=30,
    )

    # 3. Assert the file was written to the output directory
    assert expected_download_path.exists()
    with open(expected_download_path, "rb") as f:
        assert f.read() == MOCK_TAR_GZ_CONTENT

    # 4. Assert extraction was called from the output path to the extract dir
    mock_extractall.assert_called_once_with(
        path=extract_dir, filter=tarfile.data_filter
    )


def test_fetch_and_extract_creates_directories(fetcher, tmp_path, mocker):
    """Test that output and extract directories are created if they don't exist."""
    output_dir = tmp_path / "new_output_dir"
    extract_dir = tmp_path / "new_extract_dir"

    assert not output_dir.exists()
    assert not extract_dir.exists()

    mock_tar = mocker.MagicMock()
    mock_extractall = mocker.MagicMock()
    mock_tar.extractall = mock_extractall
    # Make the mock tar support the context manager protocol
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)
    mocker.patch("tarfile.open", return_value=mock_tar)

    # Create a real file for the download to write to
    expected_download_path = output_dir / MOCK_ASSET_NAME

    # Mock the download to write to a real file
    def mock_download_side_effect(url, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(expected_download_path, "wb") as f:
            f.write(MOCK_TAR_GZ_CONTENT)

    # Create fresh responses instead of trying to access the iterator
    get_page_response = mocker.MagicMock()
    get_page_response.text = MOCK_RELEASE_PAGE_HTML
    get_page_response.raise_for_status = mocker.MagicMock()

    # Mock the download response with context manager support
    download_response = mocker.MagicMock()
    download_response.status_code = 200
    download_response.raise_for_status = mocker.MagicMock()
    download_response.iter_content.side_effect = mock_download_side_effect
    download_response.__enter__ = mocker.MagicMock(return_value=download_response)
    download_response.__exit__ = mocker.MagicMock(return_value=None)

    fetcher.session.get.side_effect = [
        get_page_response,
        download_response,
    ]

    fetcher.fetch_and_extract(
        repo=MOCK_REPO,
        asset_name=MOCK_ASSET_NAME,  # Use a direct name to skip find_asset
        output_dir=output_dir,
        extract_dir=extract_dir,
    )

    assert output_dir.is_dir()
    assert extract_dir.is_dir()


def test_find_asset_by_pattern(fetcher):
    """Test that find_asset_by_pattern correctly extracts asset names from HTML."""
    # The mock session is already set up with the release page HTML
    tag = "GE-Proton8-25"
    pattern = PROTONGE_ASSET_PATTERN

    asset_name = fetcher.find_asset_by_pattern(MOCK_REPO, tag, pattern)

    assert asset_name == MOCK_ASSET_NAME


def test_find_latest_tag(fetcher):
    """Test that find_latest_tag correctly extracts the tag from the URL."""
    # The mock session is already set up with the tag in the URL
    tag = fetcher.fetch_latest_tag(
        MOCK_REPO
    )  # Changed from find_latest_tag to fetch_latest_tag

    assert tag == MOCK_TAG


# --- Tests for the main() CLI function ---


def test_main_default_args(mocker, tmp_path):
    """Test main() with default arguments."""
    mock_fetcher = mocker.MagicMock()
    mock_fetcher_class = mocker.patch(
        "fetcher.GitHubReleaseFetcher", return_value=mock_fetcher
    )

    mock_downloads = tmp_path / "Downloads"
    mock_compat = tmp_path / ".steam" / "steam" / "compatibilitytools.d"

    # Patch Path.expanduser for all Path instances
    original_expanduser = Path.expanduser

    def mock_expanduser_impl(self):
        if "Downloads" in str(self):
            return mock_downloads
        elif "compatibilitytools.d" in str(self):
            return mock_compat
        return original_expanduser(self)

    mocker.patch.object(Path, "expanduser", mock_expanduser_impl)

    # Mock sys.argv
    mocker.patch("sys.argv", ["fetcher.py"])

    from fetcher import main

    main()

    # Assert fetcher was instantiated
    mock_fetcher_class.assert_called_once()

    # Assert fetch_and_extract was called with the correct default paths
    mock_fetcher.fetch_and_extract.assert_called_once()
    args, kwargs = mock_fetcher.fetch_and_extract.call_args
    assert args[0] == MOCK_REPO
    assert args[1] == PROTONGE_ASSET_PATTERN
    assert args[2] == mock_downloads
    assert args[3] == mock_compat


def test_main_custom_args(mocker):
    """Test main() with custom -o and -x arguments."""
    mock_fetcher = mocker.MagicMock()
    _ = mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

    # Mock sys.argv with custom arguments
    mocker.patch(
        "sys.argv",
        ["fetcher.py", "-o", "/some/output/path", "-x", "/some/extract/path"],
    )

    from fetcher import main

    main()

    # Assert fetch_and_extract was called with the custom paths
    mock_fetcher.fetch_and_extract.assert_called_once()
    args, kwargs = mock_fetcher.fetch_and_extract.call_args
    assert args[0] == MOCK_REPO
    assert args[1] == PROTONGE_ASSET_PATTERN
    assert args[2] == Path("/some/output/path")
    assert args[3] == Path("/some/extract/path")


def test_main_handles_fetch_error(mocker, tmp_path):
    """Test that main() catches FetchError and exits gracefully."""
    mock_fetcher = mocker.MagicMock()
    mock_fetcher.fetch_and_extract.side_effect = FetchError("Test error")
    _ = mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

    # Mock expanduser to prevent real path resolution
    original_expanduser = Path.expanduser
    mocker.patch.object(
        Path, "expanduser", lambda path_self: original_expanduser(path_self)
    )

    # Mock sys.argv
    mocker.patch("sys.argv", ["fetcher.py"])

    # Mock print
    mock_print = mocker.patch("builtins.print")

    from fetcher import main

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 1
    mock_print.assert_any_call("Error: Test error")
