import pytest
import tarfile
from pathlib import Path

# Import the module directly to allow for reloading
from fetcher import (
    FetchError,
    GitHubReleaseFetcher,
    get_proton_ge_asset_name,
    DEFAULT_TIMEOUT,
    Spinner,
)

# --- Test Constants ---
MOCK_REPO = "owner/repo"
MOCK_TAG = "GE-Proton8-25"
MOCK_ASSET_NAME = f"{MOCK_TAG}.tar.gz"
MOCK_RELEASE_PAGE_HTML = f"""
<html>
<body>
    <a href="/{MOCK_REPO}/releases/download/{MOCK_TAG}/{MOCK_ASSET_NAME}">
        {MOCK_ASSET_NAME}
    </a>
</body>
</html>
"""
MOCK_TAR_GZ_CONTENT = b"fake tar.gz content"


@pytest.fixture
def fetcher_instance(mocker):
    """Fixture for GitHubReleaseFetcher with mocked curl methods."""
    fetcher = GitHubReleaseFetcher()

    # Mock the curl methods
    mock_curl_head = mocker.MagicMock()
    # Set up a mock response for curl head
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = f"HTTP/1.1 302 Found\r\nLocation: https://github.com/{MOCK_REPO}/releases/tag/{MOCK_TAG}\r\n"
    mock_curl_head.return_value = mock_head_result
    fetcher._curl_head = mock_curl_head

    mock_curl_get = mocker.MagicMock()
    mock_get_result = mocker.MagicMock()
    mock_get_result.returncode = 0
    mock_get_result.stdout = MOCK_RELEASE_PAGE_HTML
    mock_curl_get.return_value = mock_get_result
    fetcher._curl_get = mock_curl_get

    mock_curl_download = mocker.MagicMock()
    mock_download_result = mocker.MagicMock()
    mock_curl_download.return_value = mock_download_result
    fetcher._curl_download = mock_curl_download

    return fetcher


@pytest.fixture
def fetcher_instance_with_size_check(mocker):
    """Fixture for GitHubReleaseFetcher with mocked curl methods for size check tests."""
    fetcher = GitHubReleaseFetcher()

    # Mock the curl methods
    mock_curl_head = mocker.MagicMock()
    # Set up a mock response for curl head that includes content-length for size checks
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    # Include content-length header for asset size checking
    mock_head_result.stdout = f"HTTP/1.1 200 OK\r\nContent-Length: {len(MOCK_TAR_GZ_CONTENT)}\r\nContent-Type: application/gzip\r\n"
    mock_curl_head.return_value = mock_head_result
    fetcher._curl_head = mock_curl_head

    mock_curl_get = mocker.MagicMock()
    mock_get_result = mocker.MagicMock()
    mock_get_result.returncode = 0
    mock_get_result.stdout = MOCK_RELEASE_PAGE_HTML
    mock_curl_get.return_value = mock_get_result
    fetcher._curl_get = mock_curl_get

    mock_curl_download = mocker.MagicMock()
    mock_download_result = mocker.MagicMock()
    mock_curl_download.return_value = mock_download_result
    fetcher._curl_download = mock_curl_download

    return fetcher


def test_get_proton_ge_asset_name():
    """Test the get_proton_ge_asset_name function."""
    assert get_proton_ge_asset_name("GE-Proton10-20") == "GE-Proton10-20.tar.gz"
    assert get_proton_ge_asset_name("GE-Proton8-25") == "GE-Proton8-25.tar.gz"


def test_fetch_latest_tag_success(fetcher_instance):
    """Test successful fetching of latest tag."""
    result = fetcher_instance.fetch_latest_tag(MOCK_REPO)
    assert result == MOCK_TAG


def test_fetch_latest_tag_failure(fetcher_instance, mocker):
    """Test failure when fetching the latest release tag."""
    mocker.patch.object(
        fetcher_instance, "_curl_head", side_effect=Exception("Network error")
    )
    with pytest.raises(FetchError, match="Failed to fetch latest tag"):
        fetcher_instance.fetch_latest_tag(MOCK_REPO)


def test_fetch_latest_tag_invalid_url(fetcher_instance, mocker):
    """Test failure when the redirect URL doesn't match the expected pattern."""
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = "HTTP/1.1 302 Found\r\nLocation: https://github.com/owner/repo/releases/latest\r\n"
    fetcher_instance._curl_head.return_value = mock_head_result

    with pytest.raises(FetchError, match="Could not determine latest tag"):
        fetcher_instance.fetch_latest_tag(MOCK_REPO)


def test_find_asset_by_name_success(fetcher_instance):
    """Test successful finding of asset by name."""
    asset_name = fetcher_instance.find_asset_by_name(MOCK_REPO, MOCK_TAG)
    assert asset_name == MOCK_ASSET_NAME


def test_find_asset_by_name_failure(fetcher_instance, mocker):
    """Test failure when asset is not found."""
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<html><body>No assets here</body></html>"
    mock_result.stderr = ""
    fetcher_instance._curl_get.return_value = mock_result

    with pytest.raises(
        FetchError,
        match=f"Asset '{MOCK_ASSET_NAME}' not found in {MOCK_REPO}/{MOCK_TAG}",
    ):
        fetcher_instance.find_asset_by_name(MOCK_REPO, MOCK_TAG)


def test_find_asset_by_name_request_exception(fetcher_instance, mocker):
    """Test find_asset_by_name when request fails."""
    mocker.patch.object(
        fetcher_instance,
        "_curl_get",
        side_effect=Exception("Network error"),
    )

    with pytest.raises(FetchError, match="Failed to fetch release page"):
        fetcher_instance.find_asset_by_name(MOCK_REPO, MOCK_TAG)


def test_download_asset_success(fetcher_instance_with_size_check, tmp_path, mocker):
    """Test successful asset download."""
    output_path = tmp_path / "output.tar.gz"
    output_path.write_bytes(MOCK_TAR_GZ_CONTENT)

    # Mock the curl download to return success
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    fetcher_instance_with_size_check._curl_download.return_value = mock_result

    result_path = fetcher_instance_with_size_check.download_asset(
        MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME, output_path
    )

    assert result_path == output_path
    assert output_path.exists()


def test_download_asset_failure(fetcher_instance, tmp_path, mocker):
    """Test download failure with 404 error."""
    mock_result = mocker.MagicMock()
    mock_result.returncode = 22  # curl returns 22 for 404 errors
    mock_result.stderr = "404 Not Found"
    fetcher_instance._curl_download.return_value = mock_result

    with pytest.raises(FetchError, match="Asset not found"):
        fetcher_instance.download_asset(
            MOCK_REPO, MOCK_TAG, "nonexistent.tar.gz", tmp_path / "out"
        )


def test_download_asset_request_exception(fetcher_instance, tmp_path, mocker):
    """Test download failure due to a request exception."""
    mocker.patch.object(
        fetcher_instance,
        "_curl_download",
        side_effect=Exception("Network error"),
    )

    with pytest.raises(FetchError, match="Failed to download"):
        fetcher_instance.download_asset(
            MOCK_REPO, MOCK_TAG, "nonexistent.tar.gz", tmp_path / "out"
        )


def test_extract_archive_success(fetcher_instance, tmp_path, mocker):
    """Test successful archive extraction."""
    # Don't create a real file, just mock the path
    archive_path = tmp_path / "test.tar.gz"
    extract_dir = tmp_path / "extract"

    mock_tar = mocker.MagicMock()
    mock_member = mocker.MagicMock()
    mock_tar.getmembers.return_value = [mock_member]
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)
    mocker.patch("tarfile.open", return_value=mock_tar)

    # Mock the Path operations that might be called during extraction
    mocker.patch("pathlib.Path.mkdir")

    fetcher_instance.extract_archive(archive_path, extract_dir)

    mock_tar.extract.assert_called_once_with(
        mock_member, path=extract_dir, filter=tarfile.data_filter
    )


def test_extract_archive_failure(fetcher_instance, tmp_path, mocker):
    """Test archive extraction failure."""
    # Don't create a real file, just mock the path
    archive_path = tmp_path / "test.tar.gz"
    extract_dir = tmp_path / "extract"

    mocker.patch("tarfile.open", side_effect=tarfile.TarError("Invalid tar file"))

    # Mock Path operations
    mocker.patch("pathlib.Path.mkdir")

    with pytest.raises(FetchError, match="Failed to extract archive"):
        fetcher_instance.extract_archive(archive_path, extract_dir)


def test_extract_archive_creates_directories(fetcher_instance, tmp_path, mocker):
    """Test that extract_archive creates directories if they don't exist."""
    # Don't create a real file, just mock the path
    archive_path = tmp_path / "test.tar.gz"
    extract_dir = tmp_path / "nonexistent" / "extract_dir"

    mock_tar = mocker.MagicMock()
    mock_member = mocker.MagicMock()
    mock_tar.getmembers.return_value = [mock_member]
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)
    mocker.patch("tarfile.open", return_value=mock_tar)

    # Mock the Path.mkdir to avoid actual directory creation
    mock_mkdir = mocker.patch("pathlib.Path.mkdir")

    fetcher_instance.extract_archive(archive_path, extract_dir)

    # Verify that mkdir was called with proper parameters
    mock_mkdir.assert_called()


def test_fetch_and_extract_success(fetcher_instance, tmp_path, mocker):
    """Test the full fetch_and_extract workflow."""
    output_dir = tmp_path / "output"
    extract_dir = tmp_path / "extract"

    # Mock the tarfile extraction
    mock_tar = mocker.MagicMock()
    mock_member = mocker.MagicMock()
    mock_tar.getmembers.return_value = [mock_member]
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)
    mocker.patch("tarfile.open", return_value=mock_tar)

    # Mock curl_download to simulate the download process
    mock_download_result = mocker.MagicMock()
    mock_download_result.returncode = 0
    mock_download_result.stdout = ""
    mock_download_result.stderr = ""
    fetcher_instance._curl_download.return_value = mock_download_result

    # Mock directory validation to avoid real file system operations
    mocker.patch.object(fetcher_instance, "_ensure_directory_is_writable")

    # Execute the method
    result_path = fetcher_instance.fetch_and_extract(
        repo=MOCK_REPO,
        output_dir=output_dir,
        extract_dir=extract_dir,
    )

    # Assertions
    assert result_path == extract_dir


def test_fetch_and_extract_failure(fetcher_instance, tmp_path, mocker):
    """Test fetch_and_extract when fetching the latest tag fails."""
    mocker.patch.object(
        fetcher_instance, "fetch_latest_tag", side_effect=FetchError("Test error")
    )

    with pytest.raises(FetchError, match="Test error"):
        fetcher_instance.fetch_and_extract(
            repo=MOCK_REPO,
            output_dir=tmp_path / "output",
            extract_dir=tmp_path / "extract",
        )


def test_init_with_custom_timeout():
    """Test initialization with custom timeout."""
    timeout = 60
    fetcher = GitHubReleaseFetcher(timeout=timeout)
    assert fetcher.timeout == timeout


def test_init_with_default_timeout():
    """Test initialization with default timeout."""
    fetcher = GitHubReleaseFetcher()
    assert fetcher.timeout == DEFAULT_TIMEOUT


def test_raise_method():
    """Test the _raise method raises FetchError without logging."""
    fetcher = GitHubReleaseFetcher()
    with pytest.raises(FetchError, match="test error message"):
        fetcher._raise("test error message")


def test_spinner_class_basic_functionality():
    """Test Spinner class basic functionality."""
    spinner = Spinner()
    assert spinner.current == 0
    assert not spinner.disable
    assert spinner.spinner_chars == "|/-\\"


def test_spinner_with_description_and_unit():
    """Test Spinner class with description, unit, and unit_scale."""
    spinner = Spinner(desc="Testing spinner", unit="B", unit_scale=True)
    assert spinner.desc == "Testing spinner"
    assert spinner.unit == "B"
    assert spinner.unit_scale


def test_spinner_disable_functionality(mocker):
    """Test Spinner class with disable=True."""
    spinner = Spinner(disable=True, desc="Test", unit="it")
    mock_print = mocker.patch("builtins.print")

    spinner.update(1)
    spinner.close()

    # When disabled, print should not be called
    mock_print.assert_not_called()


def test_spinner_with_total_progress_bar(mocker):
    """Test Spinner class with total set to show progress bar."""
    mock_print = mocker.patch("builtins.print")
    spinner = Spinner(total=10, desc="Testing progress")

    with spinner:
        for _ in range(10):
            spinner.update(1)

    # Verify print was called with progress bar
    assert mock_print.call_count >= 10
    calls = [str(call) for call in mock_print.call_args_list]
    assert any("Testing progress: [=====" in call for call in calls)


@pytest.mark.parametrize(
    "unit_scale,unit,update_amount,expected_rate",
    [
        (True, "B", 1024, "1024.00B/s"),
        (True, "B", 1024 * 1024, "1.00MB/s"),
        (True, "B", 1024 * 1024 * 100, "100.00MB/s"),  # Reduced from 1GB to 100MB
        (False, "it", 10, "10.0it/s"),
    ],
)
def test_spinner_rate_formatting(
    mocker, unit_scale, unit, update_amount, expected_rate
):
    """Test Spinner class rate formatting with different units and scales."""
    mock_print = mocker.patch("builtins.print")
    mock_time = mocker.patch("time.time")

    # Mock time to control rate calculation
    mock_time.side_effect = [0, 1]  # Start at 0, then 1 second later

    spinner = Spinner(total=10, desc="Testing rate", unit=unit, unit_scale=unit_scale)

    with spinner:
        spinner.update(update_amount)

    # Verify print was called with the expected rate
    calls = [str(call) for call in mock_print.call_args_list]
    assert any(expected_rate in call for call in calls)


def test_spinner_iter_without_iterable():
    """Test Spinner class __iter__ method without iterable."""
    spinner = Spinner(total=5, desc="Testing iter")

    items = list(spinner)
    assert len(items) == 5
    assert spinner.current == 5


def test_spinner_iter_with_iterable():
    """Test Spinner class __iter__ method with iterable."""
    test_list = [1, 2, 3]
    spinner = Spinner(iterable=iter(test_list), desc="Testing iter")

    items = list(spinner)
    assert items == test_list


def test_fetch_latest_tag_with_fallback_pattern(fetcher_instance, mocker):
    """Test fetch_latest_tag with fallback URL pattern."""
    # Mock the curl head response with a different pattern
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = "HTTP/1.1 302 Found\r\nURL: https://github.com/owner/repo/releases/tag/GE-Proton8-25\r\n"
    fetcher_instance._curl_head.return_value = mock_head_result

    result = fetcher_instance.fetch_latest_tag(MOCK_REPO)
    assert result == MOCK_TAG


def test_find_asset_by_name_with_debug_logging(fetcher_instance, mocker, caplog):
    """Test find_asset_by_name with debug logging enabled."""
    # Mock the curl get response with a large HTML
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<html>" + "x" * 600 + "</html>"  # Over 500 chars
    mock_result.stderr = ""
    fetcher_instance._curl_get.return_value = mock_result

    # Enable debug logging
    import logging

    caplog.set_level(logging.DEBUG)

    with pytest.raises(FetchError):
        fetcher_instance.find_asset_by_name(MOCK_REPO, MOCK_TAG)

    # Check that HTML snippet was logged
    assert "HTML snippet:" in caplog.text


def test_download_asset_with_non_404_error(fetcher_instance, tmp_path, mocker):
    """Test download_asset with non-404 error."""
    mock_result = mocker.MagicMock()
    mock_result.returncode = 22  # curl error code
    mock_result.stderr = "Some other error"
    fetcher_instance._curl_download.return_value = mock_result

    with pytest.raises(FetchError, match="Failed to download"):
        fetcher_instance.download_asset(
            MOCK_REPO, MOCK_TAG, "nonexistent.tar.gz", tmp_path / "out"
        )


def test_extract_archive_with_eof_error(fetcher_instance, tmp_path, mocker):
    """Test extract_archive with EOFError."""
    # Don't create a real file, just mock the path
    archive_path = tmp_path / "test.tar.gz"
    extract_dir = tmp_path / "extract"

    mocker.patch("tarfile.open", side_effect=EOFError("Unexpected EOF"))

    # Mock Path operations
    mocker.patch("pathlib.Path.mkdir")

    with pytest.raises(FetchError, match="Failed to extract archive"):
        fetcher_instance.extract_archive(archive_path, extract_dir)


def test_manage_ge_proton_links_with_existing_real_directory(
    fetcher_instance, tmp_path
):
    """Test _manage_ge_proton_links when GE-Proton exists as a real directory."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create a real GE-Proton directory
    ge_proton_dir = extract_dir / "GE-Proton"
    ge_proton_dir.mkdir()

    # Create an extracted directory that matches the pattern
    extracted_dir = extract_dir / MOCK_TAG
    extracted_dir.mkdir()

    fetcher_instance._manage_ge_proton_links(extract_dir, MOCK_TAG)

    # GE-Proton should still be a real directory, not a symlink
    assert ge_proton_dir.is_dir()
    assert not ge_proton_dir.is_symlink()


def test_manage_ge_proton_links_with_existing_symlink(fetcher_instance, tmp_path):
    """Test _manage_ge_proton_links when GE-Proton exists as a symlink."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create a fake old directory for the symlink to point to
    old_dir = extract_dir / "old-version"
    old_dir.mkdir()

    # Create a symlink GE-Proton pointing to the old directory
    ge_proton_link = extract_dir / "GE-Proton"
    ge_proton_link.symlink_to(old_dir)

    # Create an extracted directory that matches the pattern
    extracted_dir = extract_dir / MOCK_TAG
    extracted_dir.mkdir()

    fetcher_instance._manage_ge_proton_links(extract_dir, MOCK_TAG)

    # GE-Proton should now be a symlink pointing to the new directory
    assert ge_proton_link.is_symlink()
    assert ge_proton_link.resolve() == extracted_dir

    # GE-Proton-Fallback should exist and point to the old directory
    fallback_link = extract_dir / "GE-Proton-Fallback"
    assert fallback_link.is_symlink()
    assert fallback_link.resolve() == old_dir


def test_manage_ge_proton_links_with_existing_real_fallback_directory(
    fetcher_instance, tmp_path
):
    """Test _manage_ge_proton_links when GE-Proton-Fallback exists as a real directory."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create a real GE-Proton-Fallback directory
    fallback_dir = extract_dir / "GE-Proton-Fallback"
    fallback_dir.mkdir()

    # Create an extracted directory that matches the pattern
    extracted_dir = extract_dir / MOCK_TAG
    extracted_dir.mkdir()

    fetcher_instance._manage_ge_proton_links(extract_dir, MOCK_TAG)

    # GE-Proton should be a symlink pointing to the new directory
    ge_proton_link = extract_dir / "GE-Proton"
    assert ge_proton_link.is_symlink()
    assert ge_proton_link.resolve() == extracted_dir

    # The real GE-Proton-Fallback directory should be removed
    assert not fallback_dir.exists()


def test_manage_ge_proton_links_no_extracted_directory(
    fetcher_instance, tmp_path, caplog
):
    """Test _manage_ge_proton_links when no matching extracted directory is found."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create a directory that doesn't match the pattern
    other_dir = extract_dir / "other-dir"
    other_dir.mkdir()

    fetcher_instance._manage_ge_proton_links(extract_dir, MOCK_TAG)

    # Check that a warning was logged
    assert "Could not find extracted directory" in caplog.text


def test_ensure_directory_is_writable_with_file_path(fetcher_instance, mocker):
    """Test _ensure_directory_is_writable when path exists as a file."""
    # Create a mock path object that behaves like a file, not a directory
    mock_path = mocker.MagicMock()
    mock_path.exists.return_value = True
    mock_path.is_dir.return_value = False  # This makes it behave like a file

    with pytest.raises(FetchError, match="Path exists but is not a directory"):
        fetcher_instance._ensure_directory_is_writable(mock_path)


def test_ensure_directory_is_writable_with_permission_error(fetcher_instance, mocker):
    """Test _ensure_directory_is_writable with permission error."""
    mock_path = mocker.MagicMock()
    mock_path.exists.return_value = True
    mock_path.is_dir.return_value = True
    mock_path.mkdir.side_effect = OSError("Permission denied")

    # Mock TemporaryFile to raise OSError
    mocker.patch("tempfile.TemporaryFile", side_effect=OSError("Permission denied"))

    with pytest.raises(FetchError, match="Directory is not writable"):
        fetcher_instance._ensure_directory_is_writable(mock_path)


def test_ensure_curl_available_missing(fetcher_instance, mocker):
    """Test _ensure_curl_available when curl is not available."""
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(FetchError, match="curl is not available"):
        fetcher_instance._ensure_curl_available()


def test_main_function_success(mocker, tmp_path):
    """Test the main function with successful execution."""
    # Mock command line arguments
    mock_args = mocker.MagicMock()
    mock_args.extract_dir = str(tmp_path / "extract")
    mock_args.output = str(tmp_path / "output")
    mock_args.debug = False

    # Mock argparse
    mock_parser = mocker.MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mocker.patch("fetcher.argparse.ArgumentParser", return_value=mock_parser)

    # Mock the fetcher
    mock_fetcher = mocker.MagicMock()
    mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

    # Mock sys.exit to prevent it from actually exiting
    mock_exit = mocker.patch("sys.exit")

    # Call main
    from fetcher import main

    main()

    # Verify the fetcher was called correctly
    mock_fetcher.fetch_and_extract.assert_called_once()
    args, kwargs = mock_fetcher.fetch_and_extract.call_args
    assert args[0] == "GloriousEggroll/proton-ge-custom"
    assert isinstance(args[1], Path)  # output_dir
    assert isinstance(args[2], Path)  # extract_dir

    # Verify sys.exit was not called (success case)
    mock_exit.assert_not_called()


def test_main_function_with_fetch_error(mocker, tmp_path):
    """Test the main function when a FetchError occurs."""
    # Mock command line arguments
    mock_args = mocker.MagicMock()
    mock_args.extract_dir = str(tmp_path / "extract")
    mock_args.output = str(tmp_path / "output")
    mock_args.debug = False

    # Mock argparse
    mock_parser = mocker.MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mocker.patch("fetcher.argparse.ArgumentParser", return_value=mock_parser)

    # Mock the fetcher to raise an exception
    mock_fetcher_instance = mocker.MagicMock()
    mock_fetcher_instance.fetch_and_extract.side_effect = FetchError("Test error")
    mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher_instance)

    # Mock sys.exit
    _ = mocker.patch("sys.exit")

    # Call main and catch the SystemExit
    from fetcher import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    # Verify sys.exit was called with exit code 1
    assert exc_info.value.code == 1


def test_main_with_debug_logging(mocker, tmp_path, caplog):
    """Test the main function with debug logging enabled."""
    # Mock command line arguments
    mock_args = mocker.MagicMock()
    mock_args.extract_dir = str(tmp_path / "extract")
    mock_args.output = str(tmp_path / "output")
    mock_args.debug = True

    # Mock argparse
    mock_parser = mocker.MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mocker.patch("fetcher.argparse.ArgumentParser", return_value=mock_parser)

    # Mock the fetcher
    mock_fetcher = mocker.MagicMock()
    mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

    # Call main
    from fetcher import main

    main()

    # Verify debug logging was enabled
    assert "DEBUG" in caplog.text


def test_main_with_expanded_paths(mocker, tmp_path):
    """Test the main function with paths that need expansion."""
    # Mock command line arguments with ~ in paths
    mock_args = mocker.MagicMock()
    mock_args.extract_dir = "~/extract"
    mock_args.output = "~/output"
    mock_args.debug = False

    # Mock argparse
    mock_parser = mocker.MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mocker.patch("fetcher.argparse.ArgumentParser", return_value=mock_parser)

    # Mock the fetcher
    mock_fetcher = mocker.MagicMock()
    mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

    # Mock Path.expanduser to return our tmp_path
    mocker.patch("pathlib.Path.expanduser", side_effect=lambda: tmp_path)

    # Call main
    from fetcher import main

    main()

    # Verify the fetcher was called with expanded paths
    args, kwargs = mock_fetcher.fetch_and_extract.call_args
    assert isinstance(args[1], Path)  # output_dir
    assert isinstance(args[2], Path)  # extract_dir


def test_main_function_with_error_output(mocker, tmp_path, capsys):
    """Test the main function error output when a FetchError occurs."""
    # Mock command line arguments
    mock_args = mocker.MagicMock()
    mock_args.extract_dir = str(tmp_path / "extract")
    mock_args.output = str(tmp_path / "output")
    mock_args.debug = False

    # Mock argparse
    mock_parser = mocker.MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mocker.patch("fetcher.argparse.ArgumentParser", return_value=mock_parser)

    # Mock the fetcher to raise an exception
    mock_fetcher_instance = mocker.MagicMock()
    mock_fetcher_instance.fetch_and_extract.side_effect = FetchError(
        "Test error message"
    )
    mocker.patch("fetcher.GitHubReleaseFetcher", return_value=mock_fetcher_instance)

    # Call main and catch the SystemExit
    from fetcher import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    # Verify the error message was printed
    captured = capsys.readouterr()
    assert "Error: Test error message" in captured.out

    # Verify sys.exit was called with exit code 1
    assert exc_info.value.code == 1


@pytest.mark.parametrize(
    "redirect_pattern,expected_tag",
    [
        (
            r"Location: https://github.com/owner/repo/releases/tag/GE-Proton8-26",
            "GE-Proton8-26",
        ),
        (
            r"URL: https://github.com/owner/repo/releases/tag/GE-Proton9-15",
            "GE-Proton9-15",
        ),
        (
            r"Location: https://github.com/owner/repo/releases/tag/GE-Proton10-30",
            "GE-Proton10-30",
        ),
    ],
)
def test_integration_fetch_latest_tag_patterns(mocker, redirect_pattern, expected_tag):
    """Integration test for fetching latest tag with different redirect patterns."""
    fetcher = GitHubReleaseFetcher()

    # Mock the curl methods
    mock_curl_head = mocker.MagicMock()
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = f"HTTP/1.1 302 Found\r\n{redirect_pattern}\r\n"
    mock_curl_head.return_value = mock_head_result
    fetcher._curl_head = mock_curl_head

    result = fetcher.fetch_latest_tag(MOCK_REPO)
    assert result == expected_tag


@pytest.mark.parametrize(
    "repo,tag,asset_name",
    [
        ("GloriousEggroll/proton-ge-custom", "GE-Proton8-25", "GE-Proton8-25.tar.gz"),
        ("GloriousEggroll/proton-ge-custom", "GE-Proton9-15", "GE-Proton9-15.tar.gz"),
        ("GloriousEggroll/proton-ge-custom", "GE-Proton10-30", "GE-Proton10-30.tar.gz"),
    ],
)
def test_integration_find_asset_by_name(mocker, repo, tag, asset_name):
    """Integration test for finding asset by name."""
    fetcher = GitHubReleaseFetcher()

    # Mock curl methods
    mock_curl_get = mocker.MagicMock()
    mock_get_result = mocker.MagicMock()
    mock_get_result.returncode = 0
    mock_get_result.stdout = f'<html><body><a href="/{repo}/releases/download/{tag}/{asset_name}">{asset_name}</a></body></html>'
    mock_curl_get.return_value = mock_get_result
    fetcher._curl_get = mock_curl_get

    result = fetcher.find_asset_by_name(repo, tag)
    assert result == asset_name


def test_integration_full_workflow(mocker, tmp_path):
    """Integration test for the full workflow."""
    # Set up paths
    output_dir = tmp_path / "output"
    extract_dir = tmp_path / "extract"

    # Mock the curl methods
    mock_curl_head = mocker.MagicMock()
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = f"HTTP/1.1 302 Found\r\nLocation: https://github.com/{MOCK_REPO}/releases/tag/{MOCK_TAG}\r\n"
    mock_curl_head.return_value = mock_head_result

    mock_curl_get = mocker.MagicMock()
    mock_get_result = mocker.MagicMock()
    mock_get_result.returncode = 0
    mock_get_result.stdout = MOCK_RELEASE_PAGE_HTML
    mock_curl_get.return_value = mock_get_result

    mock_curl_download = mocker.MagicMock()

    # Mock download to avoid creating real files
    def mock_download(url, output_path, headers=None):
        # Don't create real file, just return success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        return mock_result

    mock_curl_download.side_effect = mock_download

    # Mock tarfile.open to avoid creating a real tar file
    mock_tar = mocker.MagicMock()
    mock_member = mocker.MagicMock()
    mock_tar.getmembers.return_value = [mock_member]
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)

    # Capture the mock object returned by the patch
    mock_tarfile_open = mocker.patch("tarfile.open", return_value=mock_tar)

    # Mock directory validation to avoid real file system operations
    mock_ensure_directory_is_writable = mocker.patch.object(
        GitHubReleaseFetcher, "_ensure_directory_is_writable"
    )

    # Mock Path.iterdir to return a fake extracted directory
    mock_extracted_dir = mocker.MagicMock()
    mock_extracted_dir.is_dir.return_value = True
    mock_extracted_dir.is_symlink.return_value = False
    mock_extracted_dir.name = MOCK_TAG

    mock_iterdir = mocker.MagicMock()
    mock_iterdir.return_value = [mock_extracted_dir]
    mocker.patch.object(Path, "iterdir", return_value=mock_iterdir.return_value)

    # Create a fetcher with mocked methods
    fetcher = GitHubReleaseFetcher()
    fetcher._curl_head = mock_curl_head
    fetcher._curl_get = mock_curl_get
    fetcher._curl_download = mock_curl_download

    # Run the full workflow
    result = fetcher.fetch_and_extract(MOCK_REPO, output_dir, extract_dir)

    # Verify the result
    assert result == extract_dir

    # Verify tarfile.open was called using the captured mock
    assert mock_tarfile_open.called

    # Verify directory validation was called
    mock_ensure_directory_is_writable.assert_called()


@pytest.mark.parametrize(
    "header_type,response_code,expected_success",
    [
        ("Location", 0, True),
        ("URL", 0, True),
        ("Location", 22, False),  # Simulate curl error
    ],
)
def test_curl_head_method_behavior(
    mocker, header_type, response_code, expected_success
):
    """Parametrized test for _curl_head method with different responses."""
    fetcher = GitHubReleaseFetcher()

    # Mock subprocess.run to simulate different curl responses
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = response_code
    if header_type == "Location":
        mock_result.stdout = f"HTTP/1.1 302 Found\r\n{header_type}: https://github.com/owner/repo/releases/tag/GE-Proton8-26\r\n"
    else:  # URL
        mock_result.stdout = f"HTTP/1.1 302 Found\r\n{header_type}: https://github.com/owner/repo/releases/tag/GE-Proton8-26\r\n"
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    result = fetcher._curl_head("https://example.com")

    assert result.returncode == response_code
    assert header_type in result.stdout


@pytest.mark.parametrize(
    "headers",
    [
        ({"User-Agent": "test-agent"}),
        ({"Authorization": "Bearer token"}),
        ({"User-Agent": "test-agent", "Authorization": "Bearer token"}),
        (None),  # No headers
    ],
)
def test_curl_methods_with_headers(mocker, headers):
    """Parametrized test for curl methods with different header combinations."""
    fetcher = GitHubReleaseFetcher()

    # Test _curl_get with headers
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "response content"
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    result = fetcher._curl_get("https://example.com", headers=headers)

    # Verify subprocess.run was called
    mock_subprocess.assert_called_once()
    args, kwargs = mock_subprocess.call_args
    cmd = args[0]

    # Check that headers are properly included in command if provided
    if headers:
        for key, value in headers.items():
            assert "-H" in cmd
            assert f"{key}: {value}" in cmd
    else:
        assert "-H" not in cmd

    assert result == mock_result


@pytest.mark.parametrize(
    "error_type,error_message",
    [
        ("404", "404 Not Found"),
        ("500", "500 Internal Server Error"),
        ("timeout", "Operation timed out"),
        ("connection", "Failed to connect"),
    ],
)
def test_download_asset_error_scenarios(
    fetcher_instance, tmp_path, mocker, error_type, error_message
):
    """Parametrized test for download_asset with different error scenarios."""
    mock_result = mocker.MagicMock()
    mock_result.returncode = 22  # curl error code
    mock_result.stderr = error_message
    fetcher_instance._curl_download.return_value = mock_result

    with pytest.raises(FetchError):
        fetcher_instance.download_asset(
            MOCK_REPO, MOCK_TAG, "nonexistent.tar.gz", tmp_path / "out"
        )


@pytest.mark.parametrize(
    "extract_dir_exists,ge_proton_is_dir,expected_behavior",
    [
        (True, True, "bail_early"),  # GE-Proton exists as real directory, should bail
        (
            True,
            False,
            "create_link",
        ),  # GE-Proton exists as symlink, should move and create new
        (False, False, "create_link"),  # GE-Proton doesn't exist, should create
    ],
)
def test_manage_ge_proton_links_scenarios(
    mocker, tmp_path, extract_dir_exists, ge_proton_is_dir, expected_behavior
):
    """Parametrized test for _manage_ge_proton_links with different directory states."""
    fetcher = GitHubReleaseFetcher()

    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Set up the GE-Proton directory/link based on test parameters
    ge_proton_path = extract_dir / "GE-Proton"
    extracted_dir = extract_dir / MOCK_TAG
    extracted_dir.mkdir()

    if extract_dir_exists:
        if ge_proton_is_dir:
            # Create GE-Proton as a real directory
            ge_proton_path.mkdir()
        else:
            # Create GE-Proton as a symlink to some other directory
            other_dir = tmp_path / "other_version"
            other_dir.mkdir()
            ge_proton_path.symlink_to(other_dir)

    # Run the method
    fetcher._manage_ge_proton_links(extract_dir, MOCK_TAG)

    # Verify behavior based on expected outcome
    if expected_behavior == "bail_early":
        # When GE-Proton exists as real directory, it should remain unchanged
        assert ge_proton_path.is_dir()
        assert not ge_proton_path.is_symlink()
    else:  # create_link
        # When GE-Proton should be created as a link, verify it's a symlink
        if ge_proton_path.exists():
            assert ge_proton_path.is_symlink()
            assert ge_proton_path.resolve() == extracted_dir


@pytest.mark.parametrize(
    "curl_available,expected_result",
    [
        (True, None),  # curl is available, no exception
        (False, FetchError),  # curl is not available, should raise FetchError
    ],
)
def test_ensure_curl_available_scenarios(mocker, curl_available, expected_result):
    """Parametrized test for _ensure_curl_available with available/unavailable curl."""
    fetcher = GitHubReleaseFetcher()

    mocker.patch(
        "shutil.which", return_value="/usr/bin/curl" if curl_available else None
    )

    if expected_result:
        with pytest.raises(expected_result):
            fetcher._ensure_curl_available()
    else:
        # Should not raise an exception
        fetcher._ensure_curl_available()


@pytest.mark.parametrize(
    "dir_exists,dir_is_writable,expected_result",
    [
        (True, True, None),  # Directory exists and is writable, no exception
        (True, False, FetchError),  # Directory exists but not writable, should raise
        (False, True, None),  # Directory doesn't exist, should be created
        (False, False, FetchError),  # Directory creation fails, should raise
    ],
)
def test_ensure_directory_is_writable_scenarios(
    mocker, tmp_path, dir_exists, dir_is_writable, expected_result
):
    """Parametrized test for _ensure_directory_is_writable with various directory states."""
    fetcher = GitHubReleaseFetcher()

    test_dir = tmp_path / "test_dir"

    # Set up the directory state based on parameters
    if dir_exists:
        test_dir.mkdir(parents=True, exist_ok=True)

    # Mock the tempfile.TemporaryFile to simulate write permission
    if not dir_is_writable:
        mocker.patch("tempfile.TemporaryFile", side_effect=OSError("Permission denied"))
    else:
        mocker.patch("tempfile.TemporaryFile")

    if expected_result:
        with pytest.raises(expected_result):
            fetcher._ensure_directory_is_writable(test_dir)
    else:
        # Should not raise an exception
        fetcher._ensure_directory_is_writable(test_dir)
        assert test_dir.exists()


def test_extract_archive_edge_cases(fetcher_instance, tmp_path, mocker):
    """Test extract_archive with different archive scenarios."""
    archive_path = tmp_path / "test.tar.gz"
    extract_dir = tmp_path / "extract"

    # Test with empty members list
    mock_tar = mocker.MagicMock()
    mock_tar.getmembers.return_value = []
    mock_tar.__enter__ = mocker.MagicMock(return_value=mock_tar)
    mock_tar.__exit__ = mocker.MagicMock(return_value=None)
    mocker.patch("tarfile.open", return_value=mock_tar)

    # Mock Path operations
    mock_mkdir = mocker.patch("pathlib.Path.mkdir")

    fetcher_instance.extract_archive(archive_path, extract_dir)

    # Verify that extraction was attempted with empty members list
    assert mock_tar.getmembers.call_count == 1
    mock_mkdir.assert_called()


def test_fetch_latest_tag_url_parsing_scenarios(fetcher_instance, mocker):
    """Test fetch_latest_tag with different URL parsing scenarios."""
    # Test with URL pattern (not Location)
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = "HTTP/1.1 302 Found\r\nURL: https://github.com/owner/repo/releases/tag/GE-Proton8-26\r\n"
    fetcher_instance._curl_head.return_value = mock_head_result

    result = fetcher_instance.fetch_latest_tag(MOCK_REPO)
    assert result == "GE-Proton8-26"

    # Test with no Location or URL header (should raise FetchError)
    mock_head_result.stdout = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
    fetcher_instance._curl_head.return_value = mock_head_result

    with pytest.raises(FetchError, match="Could not determine latest tag"):
        fetcher_instance.fetch_latest_tag(MOCK_REPO)


def test_manage_ge_proton_links_correct_version(fetcher_instance, tmp_path):
    """Test that _manage_ge_proton_links correctly links to the newly downloaded version."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Create the expected extracted directory (new version) - this matches the tag
    new_version = "GE-Proton10-20"
    new_version_dir = extract_dir / new_version
    new_version_dir.mkdir()

    # Create an old version directory
    old_version = "GE-Proton10-18"
    old_version_dir = extract_dir / old_version
    old_version_dir.mkdir()

    # Create a GE-Proton symlink pointing to the old version initially
    ge_proton_link = extract_dir / "GE-Proton"
    ge_proton_link.symlink_to(old_version_dir)

    # Run the link management
    fetcher_instance._manage_ge_proton_links(extract_dir, new_version)

    # Verify that GE-Proton now points to the new version
    assert ge_proton_link.is_symlink()
    assert ge_proton_link.resolve() == new_version_dir

    # Verify that GE-Proton-Fallback now points to the old version
    fallback_link = extract_dir / "GE-Proton-Fallback"
    assert fallback_link.is_symlink()
    assert fallback_link.resolve() == old_version_dir


def test_get_remote_asset_size_success(fetcher_instance_with_size_check, mocker):
    """Test successful retrieval of remote asset size."""
    # Mock the curl head response to return a content-length
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = "HTTP/1.1 200 OK\r\nContent-Length: 1234567\r\nContent-Type: application/gzip\r\n"
    fetcher_instance_with_size_check._curl_head.return_value = mock_head_result

    size = fetcher_instance_with_size_check.get_remote_asset_size(
        MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME
    )

    assert size == 1234567


def test_get_remote_asset_size_failure_no_content_length(
    fetcher_instance_with_size_check, mocker
):
    """Test failure when content-length header is not present."""
    # Mock the curl head response without content-length
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = "HTTP/1.1 200 OK\r\nContent-Type: application/gzip\r\n"
    fetcher_instance_with_size_check._curl_head.return_value = mock_head_result

    with pytest.raises(FetchError, match="Could not determine size of remote asset"):
        fetcher_instance_with_size_check.get_remote_asset_size(
            MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME
        )


def test_get_remote_asset_size_failure_404(fetcher_instance_with_size_check, mocker):
    """Test failure when remote asset is not found."""
    # Mock the curl head response with 404 error
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 22  # curl error code for 404
    mock_head_result.stderr = "404 Not Found"
    fetcher_instance_with_size_check._curl_head.return_value = mock_head_result

    with pytest.raises(FetchError, match="Remote asset not found"):
        fetcher_instance_with_size_check.get_remote_asset_size(
            MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME
        )


def test_download_asset_skip_if_same_size(
    fetcher_instance_with_size_check, tmp_path, mocker
):
    """Test that download is skipped if local file exists with matching size."""
    # Create a local file with matching size
    output_path = tmp_path / "output.tar.gz"
    matching_size = len(MOCK_TAR_GZ_CONTENT)
    output_path.write_bytes(MOCK_TAR_GZ_CONTENT)  # Write content of specific size

    # Mock the curl head response to return the same size
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = f"HTTP/1.1 200 OK\r\nContent-Length: {matching_size}\r\nContent-Type: application/gzip\r\n"
    fetcher_instance_with_size_check._curl_head.return_value = mock_head_result

    # Mock the curl download to verify it's not called
    mock_download_result = mocker.MagicMock()
    mock_download_result.returncode = 0
    mock_download_result.stdout = ""
    mock_download_result.stderr = ""
    fetcher_instance_with_size_check._curl_download.return_value = mock_download_result

    result_path = fetcher_instance_with_size_check.download_asset(
        MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME, output_path
    )

    # Verify the download method was not called
    fetcher_instance_with_size_check._curl_download.assert_not_called()

    # Verify the correct path is returned
    assert result_path == output_path

    # Original file should still exist with original content
    assert output_path.read_bytes() == MOCK_TAR_GZ_CONTENT


def test_download_asset_different_size_downloads(
    fetcher_instance_with_size_check, tmp_path, mocker
):
    """Test that download happens if local file exists with different size."""
    # Create a local file with different size
    output_path = tmp_path / "output.tar.gz"
    different_content = b"smaller content"
    output_path.write_bytes(different_content)
    _ = len(different_content)
    remote_size = len(MOCK_TAR_GZ_CONTENT)

    # Mock the curl head response to return a different size
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = f"HTTP/1.1 200 OK\r\nContent-Length: {remote_size}\r\nContent-Type: application/gzip\r\n"
    fetcher_instance_with_size_check._curl_head.return_value = mock_head_result

    # Mock the curl download to simulate successful download
    mock_download_result = mocker.MagicMock()
    mock_download_result.returncode = 0
    mock_download_result.stdout = ""
    mock_download_result.stderr = ""
    fetcher_instance_with_size_check._curl_download.return_value = mock_download_result

    result_path = fetcher_instance_with_size_check.download_asset(
        MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME, output_path
    )

    # Verify the download method was called (since sizes differ)
    fetcher_instance_with_size_check._curl_download.assert_called_once()

    # Verify the correct path is returned
    assert result_path == output_path


def test_download_asset_local_file_not_exists(
    fetcher_instance_with_size_check, tmp_path, mocker
):
    """Test that download happens if local file doesn't exist."""
    output_path = tmp_path / "output.tar.gz"

    # Verify file doesn't exist yet
    assert not output_path.exists()

    # Mock the curl head response to return the expected size
    remote_size = len(MOCK_TAR_GZ_CONTENT)
    mock_head_result = mocker.MagicMock()
    mock_head_result.returncode = 0
    mock_head_result.stdout = f"HTTP/1.1 200 OK\r\nContent-Length: {remote_size}\r\nContent-Type: application/gzip\r\n"
    fetcher_instance_with_size_check._curl_head.return_value = mock_head_result

    # Mock the curl download to simulate successful download
    mock_download_result = mocker.MagicMock()
    mock_download_result.returncode = 0
    mock_download_result.stdout = ""
    mock_download_result.stderr = ""
    fetcher_instance_with_size_check._curl_download.return_value = mock_download_result

    result_path = fetcher_instance_with_size_check.download_asset(
        MOCK_REPO, MOCK_TAG, MOCK_ASSET_NAME, output_path
    )

    # Verify the download method was called (since file doesn't exist)
    fetcher_instance_with_size_check._curl_download.assert_called_once()

    # Verify the correct path is returned
    assert result_path == output_path
