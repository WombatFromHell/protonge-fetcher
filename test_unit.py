"""
Unit tests for protonfetcher module.
Testing individual functions and methods in isolation.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from protonfetcher import (
    DEFAULT_TIMEOUT,
    FetchError,
    GitHubReleaseFetcher,
    NetworkClient,
    FileSystemClient,
    DefaultNetworkClient,
    DefaultFileSystemClient,
    Spinner,
    compare_versions,
    format_bytes,
    get_proton_asset_name,
    parse_version,
)


class TestSpinnerUnit:
    """Unit tests for Spinner class methods."""

    def test_spinner_initialization(self):
        """Test Spinner class initialization with various parameters."""
        spinner = Spinner(
            desc="Test", total=100, unit="B", disable=False, fps_limit=30.0
        )

        assert spinner.desc == "Test"
        assert spinner.total == 100
        assert spinner.unit == "B"
        assert spinner.disable is False
        assert spinner.fps_limit == 30.0

    def test_spinner_update(self):
        """Test Spinner update method."""
        spinner = Spinner(total=10)
        spinner.update(1)

        assert spinner.current == 1

    def test_spinner_update_multiple(self):
        """Test Spinner update method with multiple increments."""
        spinner = Spinner(total=10)
        spinner.update(1)
        spinner.update(3)
        spinner.update(2)

        assert spinner.current == 6

    def test_spinner_with_iterable(self):
        """Test Spinner with an iterable."""
        items = [1, 2, 3]
        spinner = Spinner(iterable=iter(items), total=3, disable=True)

        result = list(spinner)

        assert result == [1, 2, 3]
        assert spinner.current == 3

    def test_spinner_iter_method(self):
        """Test Spinner.__iter__ method."""
        spinner = Spinner(total=3, disable=True)
        result = list(spinner)
        assert result == [0, 1, 2]  # Should iterate 0 to total-1

    def test_spinner_finish_method(self):
        """Test Spinner finish method when total is set."""
        spinner = Spinner(total=10, disable=True)
        spinner.current = 5
        spinner.finish()
        assert spinner.current == 10  # Should set current to total
        assert spinner._completed is True

    def test_spinner_finish_method_no_total(self):
        """Test Spinner finish method when total is not set."""
        spinner = Spinner(disable=True)  # No total specified
        spinner.current = 5
        initial_completed = spinner._completed  # Store initial state
        spinner.finish()
        # When no total, the finish method does nothing (no change)
        assert spinner.current == 5
        assert spinner._completed == initial_completed  # Should remain unchanged

    def test_spinner_context_manager_exit(self):
        """Test Spinner context manager exit functionality."""
        spinner = Spinner(disable=True)
        with spinner:
            pass  # Just enter and exit the context
        # Should complete without errors

    def test_spinner_context_manager_with_progress(self):
        """Test Spinner with progress display enabled."""
        spinner = Spinner(
            total=5, desc="Test", unit="it", disable=False, show_progress=True
        )
        with spinner:
            spinner.update(2)
        assert spinner.current == 2

    def test_spinner_with_fps_limit(self):
        """Test Spinner with FPS limit functionality."""
        spinner = Spinner(
            total=10,
            desc="Test",
            unit="it",
            disable=True,  # Disable actual printing for test
            fps_limit=10.0,  # Limit to 10 FPS
            show_progress=True,
        )
        # Basic functionality test with FPS limit
        with spinner:
            spinner.update(1)
        assert spinner.current == 1

    def test_spinner_without_progress_display(self):
        """Test Spinner when progress display is disabled."""
        spinner = Spinner(
            total=5,
            desc="Test",
            unit="it",
            disable=False,
            show_progress=False,  # Progress display disabled
        )
        with spinner:
            spinner.update(2)
        assert spinner.current == 2


class TestUtilityFunctions:
    """Unit tests for utility functions."""

    @pytest.mark.parametrize(
        "tag,fork,expected",
        [
            ("GE-Proton10-25", "GE-Proton", ("GE-Proton", 10, 0, 25)),
            ("GE-Proton8-5", "GE-Proton", ("GE-Proton", 8, 0, 5)),
            ("EM-10.0-30", "Proton-EM", ("EM", 10, 0, 30)),
            ("EM-9.5-25", "Proton-EM", ("EM", 9, 5, 25)),
            ("invalid-format", "GE-Proton", ("invalid-format", 0, 0, 0)),
            ("", "GE-Proton", ("", 0, 0, 0)),
        ],
    )
    def test_parse_version(self, tag: str, fork: str, expected: tuple):
        """Test parse_version function with various inputs."""
        result = parse_version(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag1,tag2,fork,expected",
        [
            ("GE-Proton10-1", "GE-Proton10-2", "GE-Proton", -1),
            ("GE-Proton11-1", "GE-Proton10-50", "GE-Proton", 1),
            ("GE-Proton9-15", "GE-Proton9-15", "GE-Proton", 0),
            ("EM-10.0-30", "EM-10.0-31", "Proton-EM", -1),
            ("EM-10.1-1", "EM-10.0-50", "Proton-EM", 1),
            ("EM-9.0-20", "EM-9.0-20", "Proton-EM", 0),
        ],
    )
    def test_compare_versions(self, tag1: str, tag2: str, fork: str, expected: int):
        """Test compare_versions function."""
        result = compare_versions(tag1, tag2, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag,fork,expected",
        [
            ("GE-Proton10-1", "GE-Proton", "GE-Proton10-1.tar.gz"),
            ("GE-Proton9-20", "GE-Proton", "GE-Proton9-20.tar.gz"),
            ("EM-10.0-30", "Proton-EM", "proton-EM-10.0-30.tar.xz"),
            ("EM-9.5-25", "Proton-EM", "proton-EM-9.5-25.tar.xz"),
        ],
    )
    def test_get_proton_asset_name(self, tag: str, fork: str, expected: str):
        """Test get_proton_asset_name function."""
        result = get_proton_asset_name(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (512, "512 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 2, "2.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
        ],
    )
    def test_format_bytes(self, bytes_value: int, expected: str):
        """Test format_bytes function."""
        result = format_bytes(bytes_value)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected_pattern",
        [
            (0, "0 B"),
            (1023, "1023 B"),  # Just under 1KB
            (1024 * 1024 - 1, "1024.00 KB"),  # Just under 1MB
            (1024**3 + 500, "1.00 GB"),  # 1GB + 500 bytes
        ],
    )
    def test_format_bytes_edge_cases(self, bytes_value: int, expected_pattern: str):
        """Test format_bytes function with edge cases using parametrization."""
        result = format_bytes(bytes_value)
        assert (
            expected_pattern in result
            if "GB" in expected_pattern
            else result == expected_pattern
        )

    def test_spinner_attributes_default_values(self):
        """Test Spinner object attributes with default values."""
        spinner = Spinner()

        # Test default attributes
        assert spinner.desc == ""
        assert spinner.total is None
        assert spinner.unit is None
        assert spinner.unit_scale is False  # since unit is None and not "B"
        assert spinner.disable is False
        assert spinner.current == 0
        assert spinner.width == 10
        assert spinner.show_progress is False
        assert spinner.show_file_details is False
        assert spinner.fps_limit is None
        assert spinner.spinner_chars == "⠟⠯⠷⠾⠽⠻"
        assert spinner.spinner_idx == 0
        assert spinner._completed is False
        assert spinner._current_line == ""

    def test_spinner_attributes_with_custom_values(self):
        """Test Spinner object attributes with custom values."""
        import time

        _ = time.time()
        spinner = Spinner(
            desc="Test Progress",
            total=100,
            unit="B",
            unit_scale=True,
            disable=True,
            fps_limit=25.0,
            width=20,
            show_progress=True,
            show_file_details=True,
        )
        # Test custom attributes
        assert spinner.desc == "Test Progress"
        assert spinner.total == 100
        assert spinner.unit == "B"
        assert spinner.unit_scale is True  # Overridden to True
        assert spinner.disable is True
        assert spinner.current == 0
        assert spinner.width == 20
        assert spinner.show_progress is True
        assert spinner.show_file_details is True
        assert spinner.fps_limit == 25.0
        assert spinner.spinner_chars == "⠟⠯⠷⠾⠽⠻"
        assert spinner.spinner_idx == 0
        assert spinner._completed is False
        assert spinner._current_line == ""

    def test_spinner_unit_scale_logic(self):
        """Test Spinner's unit_scale attribute logic."""
        # Test default behavior when unit is "B"
        spinner_b = Spinner(unit="B")
        assert spinner_b.unit_scale is True  # unit=="B" sets unit_scale=True

        # Test default behavior when unit is not "B"
        spinner_other = Spinner(unit="KB")
        assert (
            spinner_other.unit_scale is False
        )  # other units don't set it to True with default None

        # Test explicit True override
        spinner_explicit_true = Spinner(unit="MB", unit_scale=True)
        assert spinner_explicit_true.unit_scale is True

        # Test explicit False override
        spinner_explicit_false = Spinner(unit="B", unit_scale=False)
        assert spinner_explicit_false.unit_scale is False

    def test_spinner_with_context_manager_and_updates(self):
        """Test Spinner in context manager with updates - covers _spin method."""
        import time

        # Test with disable=True to avoid actual printing/animation
        spinner = Spinner(
            total=5, desc="Test", unit="it", disable=True, show_progress=True
        )

        with spinner:
            spinner.update(1)  # This triggers the update method logic
            time.sleep(0.01)  # Small delay to allow any internal processing
            spinner.update(2)
            assert spinner.current == 3

        # This should trigger finish method logic
        assert spinner.current >= 0

    def test_spinner_update_method_with_fps_logic(self):
        """Test the update method FPS limit logic."""
        spinner = Spinner(
            total=10,
            disable=True,  # Don't actually print
            fps_limit=10.0,  # Set FPS limit to test that path
            show_progress=True,
        )

        # Test update with n parameter
        spinner.update(5)
        assert spinner.current == 5

        # Test another update
        spinner.update(3)
        assert spinner.current == 8

    def test_spinner_with_no_total_and_unit(self):
        """Test Spinner without total but with unit - covers alternative display path."""
        spinner = Spinner(unit="B", disable=True)

        with spinner:
            spinner.update(100)
        assert spinner.current == 100

    def test_spinner_synchronous_behavior(self):
        """Test Spinner synchronous behavior."""
        spinner = Spinner(total=5, desc="Test", unit="it", disable=True, fps_limit=5.0)

        # Start the spinner context
        with spinner:
            # Update to trigger display logic immediately in same thread
            spinner.update(2)
            assert spinner.current == 2

        # Test after context exit
        assert spinner.current == 2

    def test_module_constants(self):
        """Test module-level constants and configuration."""
        from protonfetcher import (
            DEFAULT_TIMEOUT,
            GITHUB_URL_PATTERN,
            FORKS,
            DEFAULT_FORK,
        )

        # Test DEFAULT_TIMEOUT
        assert DEFAULT_TIMEOUT == 30
        assert isinstance(DEFAULT_TIMEOUT, int)

        # Test GITHUB_URL_PATTERN
        assert isinstance(GITHUB_URL_PATTERN, str)
        assert "releases/tag" in GITHUB_URL_PATTERN

        # Test FORKS structure and content
        assert isinstance(FORKS, dict)
        assert "GE-Proton" in FORKS
        assert "Proton-EM" in FORKS
        assert "repo" in FORKS["GE-Proton"]
        assert "archive_format" in FORKS["GE-Proton"]
        assert "repo" in FORKS["Proton-EM"]
        assert "archive_format" in FORKS["Proton-EM"]

        # Test specific values in FORKS configuration
        ge_config = FORKS["GE-Proton"]
        em_config = FORKS["Proton-EM"]

        assert ge_config["repo"] == "GloriousEggroll/proton-ge-custom"
        assert ge_config["archive_format"] == ".tar.gz"
        assert em_config["repo"] == "Etaash-mathamsetty/Proton"
        assert em_config["archive_format"] == ".tar.xz"

        # Test DEFAULT_FORK
        assert DEFAULT_FORK == "GE-Proton"
        assert isinstance(DEFAULT_FORK, str)

    @pytest.mark.parametrize(
        "timeout_value,expected_timeout",
        [
            (None, DEFAULT_TIMEOUT),  # Default timeout
            (120, 120),  # Custom timeout
            (60, 60),  # Another custom timeout
        ],
    )
    def test_github_release_fetcher_attributes(self, timeout_value, expected_timeout):
        """Test GitHubReleaseFetcher attributes with various timeout values."""
        from protonfetcher import GitHubReleaseFetcher, DEFAULT_TIMEOUT

        if timeout_value is None:
            fetcher = GitHubReleaseFetcher()
            assert fetcher.timeout == DEFAULT_TIMEOUT
        else:
            fetcher = GitHubReleaseFetcher(timeout=timeout_value)
            assert fetcher.timeout == expected_timeout


class TestClientClasses:
    """Unit tests for the new client classes."""

    def test_network_client_abstract_methods(self):
        """Test that NetworkClient abstract methods raise NotImplementedError."""
        client = NetworkClient()

        with pytest.raises(NotImplementedError):
            client.get("http://example.com")

        with pytest.raises(NotImplementedError):
            client.head("http://example.com")

        with pytest.raises(NotImplementedError):
            client.download("http://example.com", Path("/tmp/test"))

    def test_filesystem_client_abstract_methods(self):
        """Test that FileSystemClient abstract methods raise NotImplementedError."""
        client = FileSystemClient()

        with pytest.raises(NotImplementedError):
            client.exists(Path("/tmp"))

        with pytest.raises(NotImplementedError):
            client.is_dir(Path("/tmp"))

        with pytest.raises(NotImplementedError):
            client.mkdir(Path("/tmp"), parents=True, exist_ok=True)

        with pytest.raises(NotImplementedError):
            client.write(Path("/tmp/test"), b"test")

        with pytest.raises(NotImplementedError):
            client.read(Path("/tmp/test"))

        with pytest.raises(NotImplementedError):
            client.symlink_to(Path("/tmp/link"), Path("/tmp/target"))

        with pytest.raises(NotImplementedError):
            client.resolve(Path("/tmp"))

        with pytest.raises(NotImplementedError):
            client.unlink(Path("/tmp/file"))

        with pytest.raises(NotImplementedError):
            client.rmtree(Path("/tmp/dir"))

    def test_default_network_client_initialization(self):
        """Test DefaultNetworkClient initialization."""
        client = DefaultNetworkClient()
        assert client.timeout == 30

        client = DefaultNetworkClient(timeout=60)
        assert client.timeout == 60

    def test_default_filesystem_client_methods(self):
        """Test DefaultFileSystemClient method implementations."""
        client = DefaultFileSystemClient()

        # Test with temporary directory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test exists and is_dir
            assert client.exists(temp_path) is True
            assert client.is_dir(temp_path) is True
            assert client.exists(temp_path / "nonexistent") is False

            # Test mkdir
            new_dir = temp_path / "new_dir"
            client.mkdir(new_dir, parents=True, exist_ok=True)
            assert client.exists(new_dir) is True
            assert client.is_dir(new_dir) is True

            # Test write and read
            test_file = temp_path / "test.txt"
            test_data = b"Hello, World!"
            client.write(test_file, test_data)
            assert client.exists(test_file) is True
            read_data = client.read(test_file)
            assert read_data == test_data

            # Test symlink functionality
            link_path = temp_path / "test_link"
            if link_path.exists():
                client.unlink(link_path)  # Clean up if exists
            client.symlink_to(link_path, test_file, target_is_directory=False)
            assert link_path.is_symlink()

            # Test resolve
            resolved = client.resolve(link_path)
            assert str(resolved) == str(test_file.resolve())

            # Test unlink
            client.unlink(test_file)
            assert client.exists(test_file) is False

    def test_default_filesystem_client_rmtree(self):
        """Test DefaultFileSystemClient rmtree method."""
        import tempfile

        client = DefaultFileSystemClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a directory with some content
            test_dir = temp_path / "test_rmtree"
            test_dir.mkdir(parents=True)
            (test_dir / "file.txt").write_text("content")

            # Verify it exists
            assert test_dir.exists()

            # Remove it with rmtree
            client.rmtree(test_dir)

            # Verify it's gone
            assert not test_dir.exists()


class TestExtractedHelperMethods:
    """Unit tests for the extracted helper methods in _manage_proton_links."""

    def test_get_link_names_for_fork_ge_proton(self):
        """Test _get_link_names_for_fork with GE-Proton."""
        fetcher = GitHubReleaseFetcher()
        extract_dir = Path("/test")

        main, fb1, fb2 = fetcher._get_link_names_for_fork(extract_dir, "GE-Proton")

        assert main == extract_dir / "GE-Proton"
        assert fb1 == extract_dir / "GE-Proton-Fallback"
        assert fb2 == extract_dir / "GE-Proton-Fallback2"

    def test_get_link_names_for_fork_proton_em(self):
        """Test _get_link_names_for_fork with Proton-EM."""
        fetcher = GitHubReleaseFetcher()
        extract_dir = Path("/test")

        main, fb1, fb2 = fetcher._get_link_names_for_fork(extract_dir, "Proton-EM")

        assert main == extract_dir / "Proton-EM"
        assert fb1 == extract_dir / "Proton-EM-Fallback"
        assert fb2 == extract_dir / "Proton-EM-Fallback2"

    def test_find_tag_directory_manual_release_ge_proton(self, tmp_path):
        """Test _find_tag_directory for GE-Proton manual release."""
        fetcher = GitHubReleaseFetcher()

        # Create the expected directory
        expected_dir = tmp_path / "GE-Proton10-11"
        expected_dir.mkdir()

        result = fetcher._find_tag_directory(
            tmp_path, "GE-Proton10-11", "GE-Proton", is_manual_release=True
        )

        assert result == expected_dir

    def test_find_tag_directory_manual_release_proton_em_with_prefix(self, tmp_path):
        """Test _find_tag_directory for Proton-EM manual release with proton- prefix."""
        fetcher = GitHubReleaseFetcher()

        # Create the expected directory with proton- prefix
        expected_dir = tmp_path / "proton-EM-10.0-30"
        expected_dir.mkdir()

        result = fetcher._find_tag_directory(
            tmp_path, "EM-10.0-30", "Proton-EM", is_manual_release=True
        )

        assert result == expected_dir

    def test_find_tag_directory_manual_release_proton_em_without_prefix(self, tmp_path):
        """Test _find_tag_directory for Proton-EM manual release without proton- prefix."""
        fetcher = GitHubReleaseFetcher()

        # Create the expected directory without proton- prefix (fallback)
        expected_dir = tmp_path / "EM-10.0-30"
        expected_dir.mkdir()

        result = fetcher._find_tag_directory(
            tmp_path, "EM-10.0-30", "Proton-EM", is_manual_release=True
        )

        assert result == expected_dir

    def test_find_tag_directory_not_found(self, tmp_path):
        """Test _find_tag_directory when directory doesn't exist."""
        fetcher = GitHubReleaseFetcher()

        result = fetcher._find_tag_directory(
            tmp_path, "nonexistent", "GE-Proton", is_manual_release=True
        )

        assert result is None

    def test_find_version_candidates_empty_dir(self, tmp_path):
        """Test _find_version_candidates with empty directory."""
        fetcher = GitHubReleaseFetcher()

        candidates = fetcher._find_version_candidates(tmp_path, "GE-Proton")

        assert candidates == []

    def test_find_version_candidates_ge_proton(self, tmp_path):
        """Test _find_version_candidates with GE-Proton versions."""
        fetcher = GitHubReleaseFetcher()

        # Create some version directories
        v1_dir = tmp_path / "GE-Proton10-10"
        v2_dir = tmp_path / "GE-Proton10-11"
        v1_dir.mkdir()
        v2_dir.mkdir()

        # Also create a non-version directory (this will still be included but with fallback parsing)
        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        candidates = fetcher._find_version_candidates(tmp_path, "GE-Proton")

        # Should have 3 candidates (all directories are included but parsed differently)
        assert len(candidates) == 3
        versions = [candidate[0] for candidate in candidates]
        # Parse expected versions
        expected_v1 = parse_version("GE-Proton10-10", "GE-Proton")
        expected_v2 = parse_version("GE-Proton10-11", "GE-Proton")
        expected_other = parse_version("other_dir", "GE-Proton")  # fallback parsing
        assert expected_v1 in versions
        assert expected_v2 in versions
        assert expected_other in versions

    def test_find_version_candidates_proton_em(self, tmp_path):
        """Test _find_version_candidates with Proton-EM versions (with proton- prefix)."""
        fetcher = GitHubReleaseFetcher()

        # Create some Proton-EM version directories with proton- prefix
        v1_dir = tmp_path / "proton-EM-10.0-30"
        v2_dir = tmp_path / "proton-EM-10.0-31"
        v1_dir.mkdir()
        v2_dir.mkdir()

        # Also create a non-version directory (this will still be included but with fallback parsing)
        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        candidates = fetcher._find_version_candidates(tmp_path, "Proton-EM")

        # Should have 3 candidates (all directories are included but parsed differently)
        assert len(candidates) == 3
        versions = [candidate[0] for candidate in candidates]
        # Parse expected versions (the method strips the proton- prefix for parsing)
        expected_v1 = parse_version("EM-10.0-30", "Proton-EM")  # Strips "proton-"
        expected_v2 = parse_version("EM-10.0-31", "Proton-EM")
        expected_other = parse_version("other_dir", "Proton-EM")  # fallback parsing
        assert expected_v1 in versions
        assert expected_v2 in versions
        assert expected_other in versions


class TestDependencyInjection:
    """Unit tests for the dependency injection functionality."""

    def test_github_release_fetcher_with_mocks(self, mocker):
        """Test GitHubReleaseFetcher with mocked dependencies."""
        # Create mock clients
        mock_network_client = mocker.Mock(spec=NetworkClient)
        mock_file_system_client = mocker.Mock(spec=FileSystemClient)

        # Setup mock return values
        mock_network_client.get.return_value = mocker.Mock(
            returncode=0, stdout='{"assets": [{"name": "test.tar.gz"}]}'
        )
        mock_network_client.head.return_value = mocker.Mock(
            returncode=0, stdout="Content-Length: 12345\nLocation: /redirect/path"
        )
        mock_network_client.download.return_value = mocker.Mock(returncode=0)

        mock_file_system_client.exists.return_value = False
        mock_file_system_client.is_dir.return_value = True
        mock_file_system_client.mkdir.return_value = None
        mock_file_system_client.unlink.return_value = None
        mock_file_system_client.rmtree.return_value = None
        mock_file_system_client.symlink_to.return_value = None
        mock_file_system_client.resolve.return_value = Path("/resolved/path")

        # Create fetcher with mocked dependencies
        fetcher = GitHubReleaseFetcher(
            timeout=DEFAULT_TIMEOUT,
            network_client=mock_network_client,
            file_system_client=mock_file_system_client,
        )

        # Test a method that uses the network client directly
        _ = fetcher._curl_get("http://example.com")

        # Verify that the mocked method was called
        mock_network_client.get.assert_called_once_with(
            "http://example.com", None, False
        )


class TestGitHubReleaseFetcherMethods:
    """Unit tests for GitHubReleaseFetcher methods."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        return GitHubReleaseFetcher()

    def test_init_default_timeout(self, fetcher):
        """Test GitHubReleaseFetcher initialization with default timeout."""
        assert fetcher.timeout == DEFAULT_TIMEOUT

    def test_init_custom_timeout(self):
        """Test GitHubReleaseFetcher initialization with custom timeout."""
        custom_timeout = 60
        fetcher = GitHubReleaseFetcher(timeout=custom_timeout)
        assert fetcher.timeout == custom_timeout

    @pytest.mark.parametrize(
        "method_name,method_params,expected_in_args,expected_not_in_args",
        [
            (
                "_curl_get",
                {"url": "https://example.com/test", "headers": None},
                ["-L"],
                ["-H"],
            ),  # -L always in _curl_get
            (
                "_curl_get",
                {
                    "url": "https://example.com/test",
                    "headers": {"User-Agent": "test-agent"},
                },
                ["-L", "-H", "User-Agent: test-agent"],
                [],
            ),  # -L always in _curl_get
            (
                "_curl_head",
                {"url": "https://example.com/test", "follow_redirects": False},
                ["-I"],
                ["-L"],
            ),
            (
                "_curl_head",
                {"url": "https://example.com/test", "follow_redirects": True},
                ["-I", "-L"],
                [],
            ),
        ],
    )
    def test_curl_methods(
        self,
        fetcher,
        mock_subprocess_success,
        method_name,
        method_params,
        expected_in_args,
        expected_not_in_args,
    ):
        """Parametrized test for curl methods with different parameters."""
        url = method_params.pop("url")
        method = getattr(fetcher, method_name)
        method(url, **method_params)

        call_args = mock_subprocess_success.call_args[0][0]

        for expected_arg in expected_in_args:
            assert expected_arg in call_args

        for expected_not_arg in expected_not_in_args:
            assert expected_not_arg not in call_args

    def test_curl_download_constructs_command(
        self, fetcher, mock_subprocess_success, tmp_path
    ):
        """Test _curl_download constructs correct command."""
        url = "https://example.com/file.tar.gz"
        output_path = tmp_path / "output.tar.gz"
        headers = {"User-Agent": "test"}

        fetcher._curl_download(url, output_path, headers)

        call_args = mock_subprocess_success.call_args[0][0]
        assert "-L" in call_args
        assert "-o" in call_args
        assert str(output_path) in call_args
        assert url in call_args
        assert "User-Agent: test" in " ".join(call_args)

    def test_curl_methods_respect_timeout(self, mocker, mock_subprocess_success):
        """Test that curl methods respect custom timeout."""
        custom_timeout = 120
        fetcher = GitHubReleaseFetcher(timeout=custom_timeout)

        fetcher._curl_get("https://example.com")

        call_args = mock_subprocess_success.call_args[0][0]
        assert "--max-time" in call_args
        timeout_idx = call_args.index("--max-time")
        assert call_args[timeout_idx + 1] == str(custom_timeout)

    def test_get_remote_asset_size_success(self, fetcher, mocker):
        """Test get_remote_asset_size with successful response."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 1024

    def test_get_remote_asset_size_case_insensitive(self, fetcher, mocker):
        """Test get_remote_asset_size handles case-insensitive headers."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        test_cases = [
            "content-length: 1024\r\n",
            "Content-Length: 2048\r\n",
            "CONTENT-LENGTH: 4096\r\n",
        ]

        for header_line in test_cases:
            mock_result = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"HTTP/1.1 200 OK\r\n{header_line}",
                stderr="",
            )
            mocker.patch("subprocess.run", return_value=mock_result)

            match = re.search(r":\s*(\d+)", header_line)
            assert match is not None
            expected_size = int(match.group(1))
            size = fetcher.get_remote_asset_size(repo, tag, asset_name)
            assert size == expected_size

    def test_get_remote_asset_size_multiple_headers(self, fetcher, mocker):
        """Test get_remote_asset_size handles multiple content-length headers."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 2048\r\nContent-Length: 4096\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 2048  # Should return the first value found

    def test_get_remote_asset_size_zero_content_length(self, fetcher, mocker):
        """Test handling of Content-Length: 0."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Length: 0\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Could not determine size"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)

    def test_get_remote_asset_size_redirect_chain(self, fetcher, mocker):
        """Test following redirect chain to get final size."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        responses = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 302 Found\r\nLocation: https://redirect1.com/file\r\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="HTTP/1.1 200 OK\r\nContent-Length: 3072\r\n",
                stderr="",
            ),
        ]
        mock_run = mocker.patch("subprocess.run", side_effect=responses)

        size = fetcher.get_remote_asset_size(repo, tag, asset_name)
        assert size == 3072
        assert mock_run.call_count == 2

    def test_find_asset_by_name_api_success(self, fetcher, mocker):
        """Test find_asset_by_name with successful API response."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        api_response = {
            "assets": [
                {"name": "GE-Proton8-25.zip"},
                {"name": "GE-Proton8-25.tar.gz"},
                {"name": "GE-Proton8-25.sha512sum"},
            ]
        }

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        asset = fetcher.find_asset_by_name(repo, tag, "GE-Proton")
        assert asset == "GE-Proton8-25.tar.gz"  # Should pick tar.gz format

    def test_find_asset_by_name_api_empty_assets(self, fetcher, mocker):
        """Test find_asset_by_name when API returns empty assets list."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        api_response = {"assets": []}

        # First API call fails, second HTML call succeeds
        responses = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset = fetcher.find_asset_by_name(repo, tag)
        assert asset == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_missing_assets_field(self, fetcher, mocker):
        """Test find_asset_by_name when API response lacks 'assets' field."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        api_response = {"tag_name": tag, "name": "Release"}

        responses = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(api_response), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset = fetcher.find_asset_by_name(repo, tag)
        assert asset == "GE-Proton8-25.tar.gz"

    def test_find_asset_by_name_api_json_decode_error(self, fetcher, mocker):
        """Test find_asset_by_name when API returns invalid JSON."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        responses = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="invalid json {", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='<a href="/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        asset = fetcher.find_asset_by_name(repo, tag)
        assert asset == "GE-Proton8-25.tar.gz"

    def test_extract_archive_dispatch_gz(self, fetcher, mocker, tmp_path):
        """Test extract_archive dispatches to correct method for .tar.gz."""
        archive = tmp_path / "test.tar.gz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_extract_gz = mocker.patch.object(fetcher, "extract_gz_archive")

        fetcher.extract_archive(archive, extract_dir)

        mock_extract_gz.assert_called_once_with(archive, extract_dir)

    def test_extract_archive_dispatch_xz(self, fetcher, mocker, tmp_path):
        """Test extract_archive dispatches to correct method for .tar.xz."""
        archive = tmp_path / "test.tar.xz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_extract_xz = mocker.patch.object(fetcher, "extract_xz_archive")

        fetcher.extract_archive(archive, extract_dir)

        mock_extract_xz.assert_called_once_with(archive, extract_dir)

    def test_extract_gz_archive_success(self, fetcher, mocker, tmp_path):
        """Test extract_gz_archive with successful extraction."""
        archive = tmp_path / "test.tar.gz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        fetcher.extract_gz_archive(archive, extract_dir)

        # Verify subprocess.run was called with correct parameters
        assert mock_subprocess.called
        call_args = mock_subprocess.call_args[0][0]
        assert "tar" in call_args
        assert "-xzf" in call_args  # .tar.gz specific flag

    def test_extract_xz_archive_success(self, fetcher, mocker, tmp_path):
        """Test extract_xz_archive with successful extraction."""
        archive = tmp_path / "test.tar.xz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        fetcher.extract_xz_archive(archive, extract_dir)

        # Verify subprocess.run was called with correct parameters
        assert mock_subprocess.called
        call_args = mock_subprocess.call_args[0][0]
        assert "tar" in call_args
        assert "-xJf" in call_args  # .tar.xz specific flag

    def test_extract_archive_tar_error(self, fetcher, mocker, tmp_path):
        """Test extract_archive with tar command failure."""
        archive = tmp_path / "test.tar.gz"
        archive.touch()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        error_msg = "tar: Unexpected EOF in archive"
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=error_msg
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match=error_msg):
            fetcher.extract_gz_archive(archive, extract_dir)

    def test_fetch_latest_tag_success(self, fetcher, mocker):
        """Test fetch_latest_tag with successful response."""
        repo = "owner/repo"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 302 Found\r\nLocation: https://github.com/owner/repo/releases/tag/GE-Proton10-1\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        tag = fetcher.fetch_latest_tag(repo)
        assert tag == "GE-Proton10-1"

    def test_fetch_latest_tag_url_pattern(self, fetcher, mocker):
        """Test fetch_latest_tag with URL pattern instead of Location header."""
        repo = "owner/repo"

        response_with_url = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 302 Found\r\nURL: https://github.com/owner/repo/releases/tag/GE-Proton10-1\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=response_with_url)

        tag = fetcher.fetch_latest_tag(repo)
        assert tag == "GE-Proton10-1"

    def test_fetch_latest_tag_no_redirect(self, fetcher, mocker):
        """Test fetch_latest_tag when no redirect headers found."""
        repo = "owner/repo"

        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Could not determine latest tag"):
            fetcher.fetch_latest_tag(repo)

    def test_ensure_directory_is_writable_creates_dir(self, fetcher, tmp_path):
        """Test _ensure_directory_is_writable creates directory if it doesn't exist."""
        test_dir = tmp_path / "new_dir"

        fetcher._ensure_directory_is_writable(test_dir)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_is_writable_existing_dir(self, fetcher, tmp_path):
        """Test _ensure_directory_is_writable with existing directory."""
        test_dir = tmp_path / "existing_dir"
        test_dir.mkdir()

        fetcher._ensure_directory_is_writable(test_dir)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_is_writable_not_a_dir(self, fetcher, tmp_path):
        """Test _ensure_directory_is_writable when path exists but is not a directory."""
        test_file = tmp_path / "not_a_dir"
        test_file.write_text("some content")

        with pytest.raises(FetchError, match="not a directory"):
            fetcher._ensure_directory_is_writable(test_file)

    def test_ensure_directory_is_writable_permission_error(
        self, fetcher, mocker, tmp_path
    ):
        """Test _ensure_directory_is_writable handles permission errors."""
        test_dir = tmp_path / "no_access"

        mocker.patch.object(Path, "exists", side_effect=PermissionError("No access"))

        with pytest.raises(FetchError, match="No access"):
            fetcher._ensure_directory_is_writable(test_dir)

    def test_download_with_spinner(self, fetcher, mocker, tmp_path):
        """Test _download_with_spinner method."""
        url = "https://example.com/file.tar.gz"
        output_path = tmp_path / "output.tar.gz"

        # Mock the urllib.request parts
        mock_request = mocker.patch("urllib.request.Request")
        mock_urlopen = mocker.patch("urllib.request.urlopen")

        # Create a mock response
        mock_response = mocker.Mock()
        mock_response.headers.get.return_value = "1024"  # Content-Length
        mock_response.read.side_effect = [
            b"chunk1",
            b"chunk2",
            b"",
        ]  # Two chunks then EOF
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mock open to write to file
        _ = mocker.patch("builtins.open", mocker.mock_open())

        fetcher._download_with_spinner(url, output_path)

        # Verify that urllib.request was called correctly
        mock_request.assert_called_once()
        mock_urlopen.assert_called_once()

    def test_download_with_spinner_exception_handling(self, fetcher, mocker):
        """Test _download_with_spinner handles exceptions."""
        url = "https://example.com/file.tar.gz"
        output_path = Path("/tmp/test.tar.gz")

        # Mock urllib to raise an exception
        mocker.patch("urllib.request.urlopen", side_effect=Exception("Network error"))

        with pytest.raises(FetchError, match="Failed to download"):
            fetcher._download_with_spinner(url, output_path)

    def test_raise_method(self, fetcher):
        """Test _raise method."""
        with pytest.raises(FetchError, match="Test error message"):
            fetcher._raise("Test error message")

    def test_extract_archive_fallback_path(self, fetcher, mocker, tmp_path):
        """Test extract_archive fallback path for unsupported archive formats."""
        # Create an archive with unsupported extension
        archive_path = tmp_path / "test.unsupported"
        archive_path.write_text("fake archive content")
        target_dir = tmp_path / "target"

        # Mock tar subprocess to fail so it goes to fallback
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1  # Simulate failure
        mock_result.stderr = "tar error"
        mocker.patch("subprocess.run", return_value=mock_result)

        # Mock _is_tar_file to return False so it doesn't use tarfile fallback
        mocker.patch.object(fetcher, "_is_tar_file", return_value=False)

        # Should raise error when archive can't be extracted
        with pytest.raises(FetchError):
            fetcher.extract_archive(archive_path, target_dir)

    def test_is_tar_file_method(self, fetcher, mocker, tmp_path):
        """Test _is_tar_file method with both valid and invalid tar files."""
        # Create a test file that's not a tar file
        fake_file = tmp_path / "not_tar.txt"
        fake_file.write_text("not a tar file")

        # Mock tarfile.open to raise ReadError for non-tar files
        import tarfile

        original_open = tarfile.open
        tarfile.open = mocker.MagicMock(side_effect=tarfile.ReadError("Not a tar file"))

        try:
            result = fetcher._is_tar_file(fake_file)
            assert result is False
        finally:
            # Restore original function
            tarfile.open = original_open

    def test_extract_with_tarfile_method(self, fetcher, mocker, tmp_path):
        """Test _extract_with_tarfile method for tar extraction."""
        archive_path = tmp_path / "test.tar"
        target_dir = tmp_path / "extracted"

        # Mock _get_archive_info to return test values
        mocker.patch.object(fetcher, "_get_archive_info", return_value=(2, 1024))

        # Mock tarfile operations
        mock_tarfile = mocker.MagicMock()
        mock_member1 = mocker.MagicMock()
        mock_member1.name = "file1.txt"
        mock_member1.size = 512
        mock_member2 = mocker.MagicMock()
        mock_member2.name = "file2.txt"
        mock_member2.size = 512
        mock_tarfile.__enter__.return_value = mock_tarfile
        mock_tarfile.__iter__.return_value = [mock_member1, mock_member2]

        # Mock tarfile.open context manager
        mocker.patch("tarfile.open", return_value=mock_tarfile)

        # Mock Spinner methods
        mock_spinner = mocker.MagicMock()
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)

        # Mock the extract method to avoid actual file operations
        mocker.patch.object(mock_tarfile, "extract")

        # Call the method - should complete without errors
        fetcher._extract_with_tarfile(archive_path, target_dir)

        # Verify that tarfile operations were called
        assert mock_tarfile.__enter__.called
        assert mock_tarfile.extract.called

    def test_main_function_full_execution(self, mocker, tmp_path):
        """Test main function execution paths."""
        # Mock all the external dependencies that main() uses
        mocker.patch(
            "argparse.ArgumentParser.parse_args",
            return_value=mocker.Mock(
                extract_dir=str(tmp_path / "extract"),
                output=str(tmp_path / "output"),
                release=None,
                fork="GE-Proton",
                debug=False,
                no_progress=False,
                no_file_details=False,
            ),
        )

        # Mock Path operations
        mock_expanduser = mocker.patch("pathlib.Path.expanduser")
        mock_expanduser.return_value = tmp_path / "expanded_path"

        # Mock GitHubReleaseFetcher
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock logging
        _ = mocker.patch("logging.basicConfig")
        _ = mocker.patch("logging.getLogger")

        # Import and call main function
        from protonfetcher import main

        # Mock the fetch_and_extract method to avoid network calls
        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Capture print calls
        mock_print = mocker.patch("builtins.print")

        # Run main function
        # We need to handle the SystemExit that happens when there's an error
        # But in this case, we mock success
        main()  # This should run without raising SystemExit

        # Verify the correct calls were made
        mock_fetcher.fetch_and_extract.assert_called_once()
        mock_print.assert_called_with("Success")

    def test_main_function_with_debug_logging(self, mocker, tmp_path):
        """Test main function with debug logging enabled."""
        # Mock arguments with debug enabled
        mock_args = mocker.Mock(
            extract_dir=str(tmp_path / "extract"),
            output=str(tmp_path / "output"),
            release=None,
            fork="GE-Proton",
            debug=True,  # Enable debug
            no_progress=False,
            no_file_details=False,
        )
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=mock_args)

        # Mock Path operations
        mock_expanduser = mocker.patch("pathlib.Path.expanduser")
        mock_expanduser.return_value = tmp_path / "expanded_path"

        # Mock GitHubReleaseFetcher
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock logging
        mock_debug_log = mocker.patch("protonfetcher.logger.debug")

        # Mock the fetch_and_extract method
        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Capture print calls
        mock_print = mocker.patch("builtins.print")

        from protonfetcher import main

        # Run main
        main()  # Should succeed

        # Verify debug logging was called
        mock_debug_log.assert_called()
        mock_print.assert_called_with("Success")

    def test_github_release_fetcher_attributes(self):
        """Test GitHubReleaseFetcher object attributes."""
        # Test default timeout initialization
        fetcher = GitHubReleaseFetcher()
        assert fetcher.timeout == 30  # DEFAULT_TIMEOUT

        # Test custom timeout initialization
        custom_timeout = 60
        fetcher_custom = GitHubReleaseFetcher(timeout=custom_timeout)
        assert fetcher_custom.timeout == custom_timeout

    @pytest.mark.parametrize(
        "method,expected_behavior",
        [
            ("_curl_get", "makes GET request using curl"),
            ("_curl_head", "makes HEAD request using curl"),
            ("extract_gz_archive", "extracts .tar.gz archive"),
            ("extract_xz_archive", "extracts .tar.xz archive"),
        ],
    )
    def test_method_existence(self, method, expected_behavior):
        """Test that key methods exist on GitHubReleaseFetcher."""
        from protonfetcher import GitHubReleaseFetcher

        fetcher = GitHubReleaseFetcher()

        # Check that the method exists
        assert hasattr(fetcher, method)
        # Check that it's callable
        assert callable(getattr(fetcher, method, None))


class TestAdditionalCoverage:
    """Additional tests to cover uncovered scenarios."""

    @pytest.fixture
    def fetcher(self):
        """Create a GitHubReleaseFetcher instance for testing."""
        from protonfetcher import GitHubReleaseFetcher

        return GitHubReleaseFetcher()

    def test_create_symlinks_with_resolve_oserror(self, fetcher, mocker, tmp_path):
        """Test _create_symlinks when resolve raises OSError (broken symlink)."""
        # Create some version candidates
        dir1 = tmp_path / "GE-Proton10-1"
        dir1.mkdir()
        dir2 = tmp_path / "GE-Proton9-15"
        dir2.mkdir()
        dir3 = tmp_path / "GE-Proton8-20"
        dir3.mkdir()

        # Create symlinks
        main = tmp_path / "GE-Proton"
        fallback = tmp_path / "GE-Proton-Fallback"
        fallback2 = tmp_path / "GE-Proton-Fallback2"

        # Create a broken symlink
        main.symlink_to(tmp_path / "nonexistent")

        # Set up candidates (version, path) tuples
        top_3 = [
            ((10, 1, 0, 0), dir1),  # Newest
            ((9, 15, 0, 0), dir2),  # Second newest
            ((8, 20, 0, 0), dir3),  # Third newest
        ]

        # Mock file system client methods
        mock_fs = mocker.MagicMock()
        fetcher.file_system_client = mock_fs

        # Configure mocks for the different scenarios
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        mock_fs.resolve.side_effect = OSError("Broken symlink")
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        # Test the _create_symlinks method
        fetcher._create_symlinks(main, fallback, fallback2, top_3)

        # Verify the unlink was called (to remove broken symlink)
        mock_fs.unlink.assert_called()

    def test_create_symlinks_with_oserror_during_creation(
        self, fetcher, mocker, tmp_path
    ):
        """Test _create_symlinks when symlink creation raises OSError."""
        # Create some version candidates
        dir1 = tmp_path / "GE-Proton10-1"
        dir1.mkdir()

        # Create symlinks
        main = tmp_path / "GE-Proton"

        # Set up candidates (version, path) tuples
        top_3 = [
            ((10, 1, 0, 0), dir1),  # Newest
        ]

        # Mock file system client methods
        mock_fs = mocker.MagicMock()
        fetcher.file_system_client = mock_fs

        # Configure mocks
        mock_fs.exists.return_value = False  # symlink doesn't exist yet
        mock_fs.is_dir.return_value = False
        mock_fs.resolve.return_value = dir1  # For comparison
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.side_effect = OSError("Permission denied")  # Simulate error

        # Mock logger to verify error is logged
        mock_logger = mocker.patch("protonfetcher.logger")

        # Test the _create_symlinks method
        fetcher._create_symlinks(
            main, main, main, top_3
        )  # Use same links for single item

        # Verify the error was logged
        assert mock_logger.error.called

    def test_extract_with_tarfile_exception_handling(self, fetcher, mocker, tmp_path):
        """Test _extract_with_tarfile method exception handling path."""
        archive_path = tmp_path / "test.tar"
        target_dir = tmp_path / "extracted"

        # Mock _get_archive_info to raise an exception
        mock_error = Exception("Archive read error")
        mocker.patch.object(fetcher, "_get_archive_info", side_effect=mock_error)

        # Mock Spinner to avoid actual output
        mock_spinner = mocker.MagicMock()
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)

        # Mock logger to verify error logging
        mock_logger = mocker.patch("protonfetcher.logger")

        # Create an archive file
        archive_path.write_text("fake archive")

        with pytest.raises(FetchError, match="Failed to read archive"):
            fetcher._extract_with_tarfile(archive_path, target_dir)

        # Verify error was logged
        assert mock_logger.error.called

    def test_extract_with_tarfile_tarfile_exception(self, fetcher, mocker, tmp_path):
        """Test _extract_with_tarfile with tarfile module exception."""
        archive_path = tmp_path / "test.tar"
        target_dir = tmp_path / "extracted"

        # Mock _get_archive_info to return normal values
        mocker.patch.object(fetcher, "_get_archive_info", return_value=(2, 1024))

        # Mock tarfile operations to simulate an exception during extraction
        import tarfile

        _ = tarfile.open
        mock_tar = mocker.MagicMock()

        # Set up the mock to raise an exception during iteration
        mock_member1 = mocker.MagicMock()
        mock_member1.name = "file1.txt"
        mock_member1.size = 512
        mock_members = [mock_member1]

        mock_tar.__enter__.return_value = mock_tar
        mock_tar.__exit__.return_value = None
        mock_tar.__iter__.return_value = mock_members
        mock_tar.getmembers.return_value = mock_members

        # Extract should raise an exception
        def extract_side_effect(*args, **kwargs):
            raise Exception("Extraction failed")

        mock_tar.extract.side_effect = extract_side_effect

        # Mock tarfile.open to return our mock
        mocker.patch("tarfile.open", return_value=mock_tar)

        # Mock Spinner
        mock_spinner = mocker.MagicMock()
        mocker.patch("protonfetcher.Spinner", return_value=mock_spinner)

        # Mock logger to verify error logging
        mock_logger = mocker.patch("protonfetcher.logger")

        # Create an archive file
        archive_path.write_text("fake archive")

        with pytest.raises(FetchError, match="Failed to extract archive"):
            fetcher._extract_with_tarfile(archive_path, target_dir)

        # Verify error was logged
        assert mock_logger.error.called

    def test_extract_archive_fallback_to_tarfile(self, fetcher, mocker, tmp_path):
        """Test extract_archive fallback to tarfile extraction."""
        archive_path = tmp_path / "test.zip"
        target_dir = tmp_path / "extracted"
        target_dir.mkdir()

        # Create a fake archive
        archive_path.write_text("fake archive content")

        # Mock _is_tar_file to return True so it uses tarfile fallback
        mocker.patch.object(fetcher, "_is_tar_file", return_value=True)

        # Mock _extract_with_tarfile method
        mock_extract_tarfile = mocker.patch.object(fetcher, "_extract_with_tarfile")

        # This should trigger the tarfile fallback path
        # Since the file isn't actually a tar file, this would fail in _extract_with_tarfile
        mock_extract_tarfile.side_effect = Exception("Not a tar file")

        with pytest.raises(Exception, match="Not a tar file"):
            fetcher.extract_archive(archive_path, target_dir)

    def test_create_symlinks_with_real_directory_conflict(
        self, fetcher, mocker, tmp_path
    ):
        """Test _create_symlinks when a real directory exists where symlink should be."""
        # Create some version candidates
        dir1 = tmp_path / "GE-Proton10-1"
        dir1.mkdir()

        # Create a real directory where the symlink should go
        main = tmp_path / "GE-Proton"
        main.mkdir()  # Create as real directory, not symlink

        # Set up candidates (version, path) tuples
        top_3 = [((10, 1, 0, 0), dir1)]

        # Mock file system client
        mock_fs = mocker.MagicMock()
        fetcher.file_system_client = mock_fs

        # Configure mocks to simulate real directory exists
        def mock_path_is_symlink(path):
            if path == main:
                return False  # It's a directory, not a symlink
            return False  # Default behavior

        def mock_exists(path):
            if path == main:
                return True  # main path exists
            return False  # Other paths don't exist unless specified

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_path_is_symlink
        mock_fs.rmtree.return_value = None
        mock_fs.symlink_to.return_value = None

        # Test the _create_symlinks method
        fetcher._create_symlinks(main, main, main, top_3)

        # Verify rmtree was called to remove the real directory
        mock_fs.rmtree.assert_called()

    def test_fetch_latest_tag_error_response(self, fetcher, mocker):
        """Test fetch_latest_tag with error response from curl."""
        repo = "owner/repo"

        # Mock a curl response that returns an error
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="404 Not Found"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Failed to fetch latest tag"):
            fetcher.fetch_latest_tag(repo)

    def test_find_asset_by_name_api_failure_then_html_success(self, fetcher, mocker):
        """Test find_asset_by_name when API fails completely but HTML parsing succeeds."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"

        # First call (API) fails completely, second call (HTML) succeeds
        responses = [
            subprocess.CompletedProcess(  # API call fails
                args=[], returncode=22, stdout="", stderr="API Error"
            ),
            subprocess.CompletedProcess(  # HTML request succeeds
                args=[],
                returncode=0,
                stdout='<a href="/releases/download/GE-Proton8-25/GE-Proton8-25.tar.gz">GE-Proton8-25.tar.gz</a>',
                stderr="",
            ),
        ]
        mocker.patch("subprocess.run", side_effect=responses)

        # Should fall back to HTML parsing and find the asset
        asset = fetcher.find_asset_by_name(repo, tag)
        assert asset == "GE-Proton8-25.tar.gz"

    def test_get_remote_asset_size_not_found_error(self, fetcher, mocker):
        """Test get_remote_asset_size with 404 Not Found error."""
        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=22, stdout="", stderr="404 Not Found"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        with pytest.raises(FetchError, match="Remote asset not found"):
            fetcher.get_remote_asset_size(repo, tag, asset_name)
